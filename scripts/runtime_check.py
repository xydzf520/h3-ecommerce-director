#!/usr/bin/env python3
"""Read-only environment check. Offline mode never contacts a service."""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from pipeline_common import http_json, load_json, resolve_base_url


def check(workspace, url=None, offline=False, workflow=None):
    result = {'python_supported': sys.version_info >= (3, 11), 'platform_supported': sys.platform.startswith('linux'),
              'tools': {name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe')},
              'optional_image_dependencies': {name: importlib.util.find_spec(name) is not None for name in ('requests', 'PIL')},
              'network_checked': not offline}
    errors = []
    if not result['python_supported'] or not result['platform_supported']:
        errors.append('This release supports Linux with Python 3.11 or newer')
    if not all(result['tools'].values()):
        errors.append('ffmpeg and ffprobe are required for media inspection')
    if not offline:
        try:
            base = resolve_base_url(workspace, url)
            stats = http_json(base, '/system_stats', timeout=10, attempts=1)
            result['comfyui_reachable'] = True
            result['gpu_names'] = [x.get('name') for x in stats.get('devices', [])]
            if workflow:
                graph = load_json(workflow)
                schema = http_json(base, '/object_info', timeout=20, attempts=1)
                for node in graph.values():
                    kind = node.get('class_type')
                    if kind not in schema:
                        errors.append(f'Missing node: {kind}')
                        continue
                    fields = {**schema[kind].get('input', {}).get('required', {}),
                              **schema[kind].get('input', {}).get('optional', {})}
                    for key, val in node.get('inputs', {}).items():
                        spec = fields.get(key, [])
                        if spec and isinstance(spec[0], list) and not isinstance(val, list) and val not in spec[0]:
                            errors.append(f'Unsupported model/enum for {kind}.{key}')
                result['workflow_checked'] = True
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError):
            errors.append('ComfyUI or workflow schema unavailable; check URL and local environment')
    result['errors'] = errors
    result['ready'] = not errors
    result['limitation'] = 'Offline readiness is not GPU/model readiness. Schema checks do not prove video quality.'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--url')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--workflow', type=Path)
    a = p.parse_args()
    if a.offline and a.workflow:
        p.error('--workflow requires a live ComfyUI schema; omit --offline')
    result = check(a.workspace, a.url, a.offline, a.workflow)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
