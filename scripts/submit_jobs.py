"""Submit local ComfyUI workflows once. --dry-run is entirely offline.

Derived from TFboy1/oh-my-minimaxh3-director (MIT). Unknown submissions require
--recover-unknown; no force option silently replays a possibly accepted job.
"""
from __future__ import annotations
import argparse
import copy
import json
import mimetypes
import urllib.request
import uuid
from pathlib import Path
from pipeline_common import (console, digest, file_sha, http_json, load_json,
                             now_iso, project_lock, resolve_base_url, save_json)


def upload_image(base_url, path, subfolder):
    boundary = '----h3' + uuid.uuid4().hex
    # Content-addressed names prevent colliding basenames from replacing prior refs.
    filename = file_sha(path) + path.suffix.lower()
    pieces = []
    for field, value in [('type', 'input'), ('overwrite', 'false'), ('subfolder', subfolder)]:
        pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode())
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
    pieces.extend([path.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()])
    req = urllib.request.Request(base_url + '/upload/image', data=b''.join(pieces),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.load(response)
    if not result.get('name'):
        raise RuntimeError('Upload returned no filename')
    return '/'.join(x for x in [result.get('subfolder', ''), result['name']] if x)


def local_assets(workflow, project):
    refs = []
    for node_id, node in workflow.items():
        if node.get('class_type') != 'LoadImage':
            continue
        name = node.get('inputs', {}).get('image')
        if not isinstance(name, str):
            raise ValueError('LoadImage.image must be a local filename')
        path = (project / name).resolve()
        if not path.is_file():
            raise ValueError(f'Missing local reference at LoadImage node {node_id}')
        refs.append((node_id, path))
    return refs


def upload_workflow_assets(workflow, project, base_url):
    refs = local_assets(workflow, project)
    cache = {}
    subfolder = 'h3-ecommerce/' + digest(str(project.resolve()))[:16]
    for node_id, path in refs:
        key = file_sha(path)
        if key not in cache:
            cache[key] = upload_image(base_url, path, subfolder)
        workflow[node_id]['inputs']['image'] = cache[key]
    return len(cache)


def job_path(project, seg_id):
    return project / 'jobs' / f'seg_{int(seg_id):02d}_job.json'


def ensure_original_inputs(project, workflow, job):
    if digest(workflow) != job['source_workflow_sha256']:
        raise RuntimeError('Workflow changed after submission; use a new project revision')
    snapshot = job.get('request_snapshot')
    if snapshot:
        expected = load_json(snapshot).get('refs', [])
        actual = [{'node': node, 'path': str(path), 'sha256': file_sha(path)}
                  for node, path in local_assets(workflow, project)]
        if actual != expected:
            raise RuntimeError('Reference content changed after submission; use a new project revision')


def submit_segment(project, segment, workflow, base_url, attempt=1, previous=None):
    """Caller holds project_lock. Persist identity before any generation POST."""
    seg_id = int(segment['id'])
    source = copy.deepcopy(workflow)
    assets = [{'node': node, 'path': str(path), 'sha256': file_sha(path)}
              for node, path in local_assets(source, project)]
    upload_workflow_assets(workflow, project, base_url)
    client_id = 'h3-ecommerce-' + uuid.uuid4().hex
    snapshot = project / 'jobs' / 'requests' / f'{client_id}.json'
    save_json(snapshot, {'workflow': workflow, 'source_workflow_sha256': digest(source), 'refs': assets})
    job = {'segment': seg_id, 'base_url': base_url, 'client_id': client_id,
           'attempt': attempt, 'status': 'submitting_unknown', 'submitted_at': now_iso(),
           'source_workflow_sha256': digest(source), 'request_snapshot': str(snapshot),
           'seed': segment.get('seed'), 'history': (previous or {}).get('history', [])}
    if previous:
        job['history'] = job['history'] + [{k: v for k, v in previous.items() if k != 'history'}]
    save_json(job_path(project, seg_id), job)
    try:
        response = http_json(base_url, '/prompt', method='POST',
                             payload={'prompt': workflow, 'client_id': client_id,
                                      'extra_data': {'h3_request_id': client_id}}, timeout=180)
    except Exception:
        job['last_error'] = 'Submission outcome unknown; run --recover-unknown before any retry'
        save_json(job_path(project, seg_id), job)
        raise RuntimeError(job['last_error']) from None
    # A returned task id must always be retained, even if the response has warnings.
    if response.get('prompt_id'):
        job.update(prompt_id=str(response['prompt_id']), status='submitted', number=response.get('number'))
    elif response.get('node_errors') or response.get('error'):
        job.update(status='validation_failed', last_error='Server rejected workflow; inspect node/model compatibility')
    else:
        job['last_error'] = 'No task id; submission outcome unknown'
    save_json(job_path(project, seg_id), job)
    if job['status'] != 'submitted':
        raise RuntimeError(job.get('last_error', job['status']))
    return job


def recover_unknown(project, job):
    """Read-only reconciliation with server; only local job state is changed."""
    base = job['base_url']
    candidates = []
    queue = http_json(base, '/queue')
    candidates.extend(queue.get('queue_running', []))
    candidates.extend(queue.get('queue_pending', []))
    history = http_json(base, '/history')
    candidates.extend(v.get('prompt', []) for v in history.values() if isinstance(v, dict))
    matches = set()
    for entry in candidates:
        if not isinstance(entry, list) or len(entry) < 4 or not isinstance(entry[3], dict):
            continue
        extra = entry[3]
        if job['client_id'] in (extra.get('client_id'), extra.get('h3_request_id')):
            matches.add(str(entry[1]))
    if len(matches) != 1:
        raise RuntimeError('No unique server match. Keep unknown state; inspect server before creating another revision')
    job.update(prompt_id=matches.pop(), status='submitted', recovered_at=now_iso())
    save_json(job_path(project, job['segment']), job)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--base-url')
    parser.add_argument('--segments')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--recover-unknown', action='store_true')
    parser.add_argument('--retry-failed', action='store_true', help='Retry known generation/validation failures only')
    args = parser.parse_args()
    if args.dry_run and (args.recover_unknown or args.retry_failed):
        parser.error('dry-run cannot be combined with recovery/retry')
    project = args.project.resolve()
    params = load_json(project / 'jobs/params.json')
    base = resolve_base_url(args.workspace, args.base_url)
    selected = {int(n) for n in args.segments.split(',')} if args.segments else None
    with project_lock(project):
        for segment in params['segments']:
            seg_id = int(segment['id'])
            if selected is not None and seg_id not in selected:
                continue
            workflow = load_json(project / 'workflows' / f'seg_{seg_id:02d}_api.json')
            local_assets(workflow, project)
            if args.dry_run:
                console(f'[dry-run] seg {seg_id}: local files valid; no requests sent')
                continue
            path = job_path(project, seg_id)
            previous = load_json(path) if path.exists() else None
            if previous:
                if previous['base_url'] != base:
                    raise RuntimeError('Existing job belongs to another server; use a new project revision')
                ensure_original_inputs(project, workflow, previous)
                status = previous['status']
                if status in ('submitting_unknown', 'needs_reconciliation') and args.recover_unknown:
                    recover_unknown(project, previous)
                    continue
                if status in ('submitted', 'generated', 'download_failed', 'downloaded'):
                    console(f'[skip] seg {seg_id}: {status}; resume with monitor_jobs.py')
                    continue
                if not args.retry_failed or status not in ('generation_failed', 'validation_failed'):
                    raise RuntimeError(f'seg {seg_id}: {status}; no automatic resubmission')
            elif args.recover_unknown:
                raise RuntimeError('No prior job to reconcile; recovery never creates tasks')
            job = submit_segment(project, segment, workflow, base,
                                 1 if previous is None else previous['attempt'] + 1, previous)
            console(f'[submitted] seg {seg_id}: {job["prompt_id"]}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        console(f'ERROR: {exc}')
        raise SystemExit(2)
