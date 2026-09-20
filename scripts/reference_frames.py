#!/usr/bin/env python3
"""Extract a selected source interval into a new review directory."""
import argparse
import json
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from pipeline_common import file_sha, save_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--step', type=float, default=1)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if not a.input.is_file():
        p.error('Input video does not exist')
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(a.input.resolve())], timeout=60))
    duration = float(info['format']['duration'])
    if not all(math.isfinite(v) for v in (a.start, a.end, a.step)) or not (0 <= a.start < a.end <= duration and a.step > 0):
        p.error('Require finite 0 <= start < end <= duration, and positive step')
    if a.out.exists() and (not a.out.is_dir() or any(a.out.iterdir())):
        p.error('Output must be a new or empty directory; partial runs must not overwrite evidence')
    a.out.mkdir(parents=True, exist_ok=True)
    count = math.ceil((a.end - a.start) / a.step)
    if count > 2000:
        p.error('More than 2000 frames; narrow the review interval or increase step')
    times = [round(a.start + i * a.step, 6) for i in range(count)]
    frames = []
    for i, t in enumerate(t for t in times if t < a.end):
        dest = a.out / f'frame_{i:04d}_{t:.3f}s.png'
        subprocess.run(['ffmpeg', '-nostdin', '-n', '-v', 'error', '-ss', str(t), '-i', str(a.input.resolve()), '-frames:v', '1', str(dest.resolve())], check=True, timeout=120)
        frames.append({'time': t, 'file': dest.name, 'sha256': file_sha(dest)})
    sheets = []
    for base in range(0, len(frames), 8):
        batch = frames[base:base + 8]
        sheet = Image.new('RGB', (1280, 580 * math.ceil(len(batch) / 4)), '#202020')
        draw = ImageDraw.Draw(sheet)
        for i, item in enumerate(batch):
            x, y = (i % 4) * 320, (i // 4) * 580
            with Image.open(a.out / item['file']) as source:
                im = source.convert('RGB')
                im.thumbnail((316, 548))
                sheet.paste(im, (x, y + 28))
            draw.text((x + 5, y + 7), f'{item["time"]:.3f}s', fill='white')
        dest = a.out / f'contact_{base // 8:02d}.jpg'
        sheet.save(dest, quality=92)
        sheets.append(dest.name)
    report = {'source': str(a.input.resolve()), 'source_sha256': file_sha(a.input), 'source_duration': duration,
              'selected_interval': [a.start, a.end], 'step': a.step, 'frames': frames, 'contact_sheets': sheets,
              'limitation': 'Still frames do not prove performance, lip sync, motion continuity or reference fidelity.'}
    save_json(a.out / 'frames.json', report)
    print(json.dumps({'frames': len(frames), 'interval': [a.start, a.end]}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
