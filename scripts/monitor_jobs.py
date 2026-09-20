"""Resume ComfyUI jobs, keeping generation retries separate from download retries.

Derived from TFboy1/oh-my-minimaxh3-director (MIT). Downloads are candidates,
not production approval. Default generation retries: zero.
"""
from __future__ import annotations
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from pipeline_common import (console, digest, file_sha, http_json, load_json,
                             load_pipeline_config, now_iso, project_lock, save_json)
from submit_jobs import ensure_original_inputs, job_path, submit_segment


def find_media(entry):
    media = []
    for output in entry.get('outputs', {}).values():
        for value in output.values():
            if isinstance(value, list):
                media.extend(item for item in value if isinstance(item, dict)
                             and str(item.get('filename', '')).lower().endswith('.mp4'))
    # Multiple output nodes may repeat a file. Preserve distinct outputs.
    return list({(x.get('filename'), x.get('subfolder'), x.get('type')): x for x in media}.values())


def download_media(base_url, item, destination):
    query = urllib.parse.urlencode({k: item.get(k, default) for k, default in
                                   [('filename', ''), ('subfolder', ''), ('type', 'output')]})
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix('.mp4.part')
    with urllib.request.urlopen(base_url + '/view?' + query, timeout=120) as response, temp.open('wb') as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    if temp.stat().st_size == 0:
        raise RuntimeError('Empty download')
    temp.replace(destination)


def poll_job(project, segment, job, retry_limit, download_retries):
    """Caller holds project_lock. No unrelated queue mutation."""
    path = job_path(project, job['segment'])
    status = job['status']
    if status == 'downloaded':
        if job.get('outputs') and all(Path(x['path']).is_file() and file_sha(x['path']) == x['sha256'] for x in job['outputs']):
            return 'done'
        job.update(status='generated', download_attempts=0)
        status = 'generated'
    if status in ('submitting_unknown', 'needs_reconciliation', 'validation_failed'):
        return 'attention'
    if status == 'generation_failed':
        if job['attempt'] >= 1 + retry_limit:
            return 'attention'
        workflow = load_json(project / 'workflows' / f'seg_{segment["id"]:02d}_api.json')
        ensure_original_inputs(project, workflow, job)
        submit_segment(project, segment, workflow, job['base_url'], job['attempt'] + 1, job)
        return 'pending'
    if status not in ('submitted', 'generated', 'download_failed'):
        return 'attention'
    if status == 'submitted':
        history = http_json(job['base_url'], '/history/' + urllib.parse.quote(job['prompt_id'], safe=''))
        entry = history.get(job['prompt_id'])
        if not entry:
            queue = http_json(job['base_url'], '/queue')
            ids = {str(x[1]) for k in ('queue_running', 'queue_pending') for x in queue.get(k, []) if isinstance(x, list) and len(x) > 1}
            job['history_misses'] = 0 if job['prompt_id'] in ids else job.get('history_misses', 0) + 1
            if job['history_misses'] >= 3:
                job['status'] = 'needs_reconciliation'
            save_json(path, job)
            return 'attention' if job['status'] == 'needs_reconciliation' else 'pending'
        state = entry.get('status', {})
        if state.get('status_str') == 'error':
            job.update(status='generation_failed', last_error='Server reports generation failure')
            save_json(path, job)
            return 'pending' if job['attempt'] < 1 + retry_limit else 'attention'
        if not state.get('completed'):
            return 'pending'
        job.update(status='generated', media=find_media(entry), generated_at=now_iso())
        save_json(path, job)
    if not job.get('media'):
        job['last_error'] = 'Completed task has no MP4 outputs; inspect workflow, do not regenerate automatically'
        save_json(path, job)
        return 'attention'
    # download_retries is extra retries after the first download attempt.
    if job.get('download_attempts', 0) >= 1 + download_retries:
        return 'attention'
    job['download_attempts'] = job.get('download_attempts', 0) + 1
    save_json(path, job)
    outputs = []
    try:
        for index, item in enumerate(job['media'], 1):
            dest = project / 'clips/raw' / f'seg_{job["segment"]:02d}_a{job["attempt"]}_{index:02d}.mp4'
            download_media(job['base_url'], item, dest)
            outputs.append({'path': str(dest), 'sha256': file_sha(dest)})
    except Exception:
        job.update(status='download_failed', last_error='Download failed; original prompt_id retained')
        save_json(path, job)
        return 'pending' if job['download_attempts'] < 1 + download_retries else 'attention'
    job.update(status='downloaded', outputs=outputs, downloaded_at=now_iso(), production_status='needs_review')
    save_json(path, job)
    return 'done'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', required=True, type=Path)
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--poll', type=int)
    p.add_argument('--retry-limit', type=int, help='Extra generation retries; 0 disables')
    p.add_argument('--download-retries', type=int)
    p.add_argument('--resume-downloads', action='store_true', help='Reset exhausted download counters once; never regenerate')
    p.add_argument('--once', action='store_true')
    p.add_argument('--max-polls', type=int, default=120)
    a = p.parse_args()
    cfg = load_pipeline_config(a.workspace)
    retries = a.retry_limit if a.retry_limit is not None else cfg['retry_limit']
    downloads = a.download_retries if a.download_retries is not None else cfg['download_retries']
    interval = a.poll if a.poll is not None else cfg['poll_seconds']
    if retries < 0 or downloads < 0 or interval < 1 or a.max_polls < 1:
        p.error('Retries must be nonnegative; poll/max-polls must be positive')
    project = a.project.resolve()
    for round_no in range(1 if a.once else a.max_polls):
        results = []
        with project_lock(project):
            params = load_json(project / 'jobs/params.json')
            for segment in params['segments']:
                path = job_path(project, segment['id'])
                if not path.exists():
                    results.append('attention')
                    continue
                job = load_json(path)
                if a.resume_downloads and round_no == 0 and job['status'] == 'download_failed':
                    job['download_attempts'] = 0
                    save_json(path, job)
                results.append(poll_job(project, segment, job, retries, downloads))
        console(json.dumps({'done': results.count('done'), 'pending': results.count('pending'),
                            'attention': results.count('attention')}))
        if results and all(x == 'done' for x in results):
            return 0
        if 'pending' not in results:
            return 2
        if a.once:
            return 1
        time.sleep(interval)
    return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        console(f'ERROR: {exc}')
        raise SystemExit(2)
