#!/usr/bin/env python3
"""Fail closed on incomplete/stale production review evidence; never rate acting or publish."""
import argparse
import hashlib
import json
from pathlib import Path

CATEGORIES = ('reference_fidelity', 'pacing_and_continuity', 'performance', 'dialogue_and_quality')


def check(review, manifest, review_root, manifest_root):
    errors = []
    rows = manifest if isinstance(manifest, list) else manifest.get('items', [])
    if not rows:
        return ['Empty delivery manifest']
    request_ids = {r.get('request_id') for r in rows}
    if request_ids != {review.get('request_id')} or not review.get('request_id'):
        errors.append('Review must cover exactly one matching request_id')
    if {r.get('revision') for r in rows} != {review.get('revision')} or not review.get('revision'):
        errors.append('Review revision must match every delivery item')
    if sorted(r.get('sequence', 0) for r in rows) != list(range(1, len(rows) + 1)):
        errors.append('Delivery sequence must be exactly 1..N')
    if review.get('unresolved_feedback') != []:
        errors.append('Unresolved feedback must be explicitly empty before release')

    def verify_artifact(item, root, label):
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            errors.append(label + ': missing path/SHA'); return
        p = root / item['path']
        if not p.is_file():
            errors.append(label + ': missing file'); return
        with p.open('rb') as stream:
            actual_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual_sha != item['sha256']:
            errors.append(label + ': SHA mismatch')

    current = {(r.get('file'), r.get('sha256'), r.get('prompt_id')) for r in rows}
    reviewed = {(r.get('file'), r.get('sha256'), r.get('prompt_id')) for r in review.get('clips', [])}
    if current != reviewed or len(review.get('clips', [])) != len(rows):
        errors.append('Reviewed clips must match all final file/SHA/prompt_id entries')
    for row in rows:
        verify_artifact({'path': row.get('file'), 'sha256': row.get('sha256')}, manifest_root, 'delivery')
        if not row.get('prompt_id'):
            errors.append('Delivery clip missing prompt_id')
    full = review.get('full_preview')
    verify_artifact(full, review_root, 'full_preview')
    if full and Path(full.get('path', '')).suffix.lower() != '.mp4':
        errors.append('Full review artifact must be MP4')
    if not review.get('roles_reviewed'):
        errors.append('Missing per-role speaker/listener observations')
    else:
        for role in review['roles_reviewed']:
            if not all(role.get(k) for k in ('role', 'speaking_or_listening', 'observed_behavior', 'time_ranges')):
                errors.append('Incomplete role review')
    for key in CATEGORIES:
        item = review.get('checks', {}).get(key, {})
        if item.get('status') == 'not_applicable':
            if key != 'reference_fidelity' or not item.get('reason') or review.get('has_reference_video') is not False:
                errors.append(key + ': unjustified not_applicable')
            continue
        if item.get('status') != 'pass' or not item.get('observations'):
            errors.append(key + ': not passed or missing observations')
        if not item.get('evidence'):
            errors.append(key + ': missing evidence')
        for evidence in item.get('evidence', []):
            verify_artifact(evidence, review_root, key)
        if key in ('pacing_and_continuity', 'performance'):
            dynamic = item.get('dynamic_review', {})
            if (dynamic.get('method') != 'direct_normal_speed_observation'
                    or dynamic.get('playback_rate') != 1
                    or dynamic.get('full_preview_sha256') != (full or {}).get('sha256')
                    or not dynamic.get('reviewer') or not dynamic.get('time_ranges')):
                errors.append(key + ': lacks normal-speed observations of this full preview')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    args = p.parse_args()
    try:
        errors = check(json.loads(args.review.read_text()), json.loads(args.manifest.read_text()),
                       args.review.resolve().parent, args.manifest.resolve().parent)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors = [f'Invalid review input: {exc}']
    print(json.dumps({'status': 'blocked' if errors else 'evidence_consistent', 'errors': errors,
                      'limitation': 'Checks evidence completeness and identity only; does not prove natural acting, '
                                    'validate review truth, change human decisions or publish.'}, ensure_ascii=False, indent=2))
    raise SystemExit(2 if errors else 0)


if __name__ == '__main__':
    main()
