#!/usr/bin/env python3
"""Inspect and fully decode a local video. Does not judge dialogue or visual quality."""
import argparse
import json
import subprocess
from pathlib import Path
from pipeline_common import file_sha, save_json


def inspect(path, require_audio=False):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Media file does not exist')
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], timeout=60))
    videos = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
    audios = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
    process = subprocess.run(['ffmpeg', '-nostdin', '-v', 'warning', '-xerror', '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True, timeout=600)
    # Warnings remain visible and block the technical pass pending diagnosis.
    errors = []
    if not videos:
        errors.append('No video stream')
    if require_audio and not audios:
        errors.append('Required audio missing')
    if float(info.get('format', {}).get('duration', 0)) <= 0:
        errors.append('Invalid duration')
    if process.returncode or process.stderr.strip():
        errors.append('Decoder failed or emitted warnings; inspect decoder_log')
    return {'path': str(path), 'sha256': file_sha(path), 'technical_status': 'pass' if not errors else 'fail',
            'duration': info.get('format', {}).get('duration'),
            'video': [{k: s.get(k) for k in ('codec_name', 'width', 'height', 'pix_fmt', 'avg_frame_rate')} for s in videos],
            'audio_streams': len(audios), 'errors': errors, 'decoder_log': process.stderr[-8000:],
            'visual_status': 'needs_review', 'dialogue_status': 'needs_review'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--require-audio', action='store_true')
    a = p.parse_args()
    if a.output.exists():
        p.error('Output exists; use a new evidence file')
    result = inspect(a.input, a.require_audio)
    save_json(a.output, result)
    print(json.dumps({'technical_status': result['technical_status'], 'errors': result['errors']}))
    return 0 if result['technical_status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
