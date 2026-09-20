"""Shared local pipeline helpers. Derived from TFboy1/oh-my-minimaxh3-director (MIT)."""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

LOCAL_COMFY_URL = 'http://127.0.0.1:8188'


def now_iso():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@contextlib.contextmanager
def project_lock(project):
    path = Path(project) / 'jobs' / 'pipeline.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another build/submit/monitor process is using this project') from None
        yield


def load_pipeline_config(workspace):
    workspace = Path(workspace).resolve()
    defaults = {'base_url': LOCAL_COMFY_URL, 'templates_dir': None,
                'poll_seconds': 30, 'retry_limit': 0, 'download_retries': 3}
    path = workspace / '.config' / 'pipeline-config.json'
    if path.exists():
        data = load_json(path)
        if not isinstance(data, dict):
            raise ValueError('pipeline-config must be an object')
        defaults.update(data)
    if defaults.get('templates_dir'):
        defaults['templates_dir'] = str((workspace / defaults['templates_dir']).resolve())
    return defaults


def resolve_base_url(workspace, explicit=None):
    url = explicit or load_pipeline_config(workspace)['base_url']
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTP(S) ComfyUI URL without embedded credentials/query/fragment')
    return url.rstrip('/')


def http_json(base_url, path, method='GET', payload=None, timeout=60, attempts=3):
    # A read timeout does not mean the server rejected a POST. Never replay writes.
    count = attempts if method.upper() in ('GET', 'HEAD') else 1
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {} if data is None else {'Content-Type': 'application/json; charset=utf-8'}
    for attempt in range(max(1, count)):
        try:
            request = urllib.request.Request(base_url.rstrip('/') + path, data=data, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
            result = json.loads(raw.decode('utf-8')) if raw else {}
            if not isinstance(result, dict):
                raise ValueError('Expected JSON object')
            return result
        except (urllib.error.URLError, TimeoutError, ValueError):
            if attempt + 1 >= max(1, count):
                # Never print upstream bodies, which can contain prompt or credential data.
                raise RuntimeError(f'{method} {path.split("?")[0]} failed; writes must be reconciled before retry') from None
            time.sleep(min(2 * (attempt + 1), 6))


def console(message):
    print(message, flush=True)
