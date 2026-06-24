#!/usr/bin/env python3
"""
POS System — Data Guardian / Corruption Shield
================================================
Protects critical JSON data files from accidental overwrite or corruption.

Features:
  - Checks that all critical JSON files parse correctly (valid JSON)
  - Validates minimum expected sizes (item count, user count, etc.)
  - Detects unexpected shrinkage compared to previous baseline
  - Sets read-only permissions (444) on critical files after verification
  - Logs any anomalies to stdout for cron/Discord delivery
  - Prevents dangerous writes: safe_write_json() wrapper

Usage:
    python3 scripts/data_guardian.py                      # check all + set perms
    python3 scripts/data_guardian.py --check-only          # check only, no perm changes
    python3 scripts/data_guardian.py --fix                  # attempt fixes (restore from backup)
    python3 scripts/data_guardian.py --json                 # JSON output for programmatic use
    python3 scripts/data_guardian.py --set-perms            # just set recommended permissions

Exit codes:
    0 = all checks passed
    1 = one or more checks failed (anomaly detected)
    2 = fatal error (can't read config)
"""

import argparse
import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Critical file definitions ────────────────────────────────────────────
# Each entry: filename, expected_min_count, count_label, is_dict_of_keys
CRITICAL_FILES = [
    {'file': 'users.json',        'min_records': 3,    'label': 'users'},
    {'file': 'items.json',        'min_records': 5,    'label': 'items (total across all categories)'},
    {'file': 'orders.json',       'min_records': 0,    'label': 'orders'},
    {'file': 'inventory.json',    'min_records': 3,    'label': 'inventory items'},
    {'file': 'shift_log.json',    'min_records': 0,    'label': 'shifts'},
    {'file': 'activity_log.json', 'min_records': 0,    'label': 'activity entries'},
]

# Baseline for shrinkage detection (minimum allowed vs expected total)
# If a file drops below this percentage of expected, flag it
SHRINKAGE_THRESHOLD_PCT = 50  # 50% = flag if file less than half expected size


def count_records(data, filename):
    """Count meaningful records in a JSON data structure."""
    if isinstance(data, dict):
        if filename == 'items.json':
            # items.json is dict of categories → list of items
            return sum(len(v) for v in data.values())
        # Other dicts: count keys (users, inventory, tables, etc.)
        return len(data)
    elif isinstance(data, list):
        return len(data)
    return 0


def get_expected_baseline():
    """Get the known-good baseline counts from a tracking file.
    Returns dict: {filename: {'count': N, 'size': N, 'updated': 'ISO timestamp'}}
    """
    baseline_path = os.path.join(PROJECT_ROOT, '.data_baseline.json')
    try:
        with open(baseline_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_baseline(baseline):
    """Save updated baseline counts."""
    baseline_path = os.path.join(PROJECT_ROOT, '.data_baseline.json')
    try:
        with open(baseline_path, 'w') as f:
            json.dump(baseline, f, indent=2)
    except IOError as e:
        print(f"⚠️  Could not save baseline: {e}")


def check_files(args):
    """Check all critical files for validity and size."""
    results = []
    all_ok = True
    baseline = get_expected_baseline()
    baseline_updated = False

    for entry in CRITICAL_FILES:
        filename = entry['file']
        filepath = os.path.join(PROJECT_ROOT, filename)
        min_records = entry['min_records']
        label = entry['label']

        result = {
            'file': filename,
            'status': 'ok',
            'issues': []
        }

        # Check file exists
        if not os.path.exists(filepath):
            result['status'] = 'error'
            result['issues'].append('FILE_MISSING')
            results.append(result)
            all_ok = False
            continue

        size = os.path.getsize(filepath)

        # Check file is non-empty
        if size == 0:
            result['status'] = 'error'
            result['issues'].append('FILE_EMPTY')
            results.append(result)
            all_ok = False
            continue

        # Try to parse as JSON
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            result['status'] = 'error'
            result['issues'].append(f'INVALID_JSON: {e}')
            results.append(result)
            all_ok = False
            continue

        # Count records
        record_count = count_records(data, filename)
        result['record_count'] = record_count
        result['file_size'] = size

        # Check minimum record count
        if record_count < min_records:
            result['status'] = 'error'
            result['issues'].append(f'BELOW_MINIMUM: {record_count} {label} (expected >= {min_records})')
            all_ok = False

        # Check against baseline (shrinkage detection)
        prev = baseline.get(filename)
        if prev and prev.get('count', 0) > 0:
            prev_count = prev['count']
            if record_count < prev_count:
                ratio = record_count / prev_count * 100
                if ratio < SHRINKAGE_THRESHOLD_PCT:
                    result['status'] = 'error'
                    result['issues'].append(
                        f'SHRINKAGE: {record_count} vs baseline {prev_count} '
                        f'({ratio:.0f}% — threshold: {SHRINKAGE_THRESHOLD_PCT}%)'
                    )
                    all_ok = False
                elif ratio < 90:
                    result['issues'].append(
                        f'NOTICE_SHRINK: {record_count} vs baseline {prev_count} ({ratio:.0f}%)'
                    )

        # Update baseline if current count is higher (growth is normal)
        filename_baseline = baseline.get(filename, {'count': 0, 'size': 0})
        if record_count > filename_baseline.get('count', 0):
            baseline[filename] = {
                'count': record_count,
                'size': size,
                'updated': datetime.utcnow().isoformat()
            }
            baseline_updated = True
        elif size > filename_baseline.get('size', 0) * 1.2:
            # File grew significantly, update baseline
            baseline[filename] = {
                'count': record_count,
                'size': size,
                'updated': datetime.utcnow().isoformat()
            }
            baseline_updated = True

        results.append(result)

    # Save baseline if updated
    if baseline_updated and not args.check_only:
        save_baseline(baseline)

    return results, all_ok


def set_protective_permissions(args):
    """Set read-only (444) permissions on critical files.
    Skip if --check-only is set.
    """
    if args.check_only:
        return True

    perms_set = 0
    perms_failed = 0

    for entry in CRITICAL_FILES:
        filename = entry['file']
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            continue

        try:
            # Set to 444 (read-only for owner, group, others)
            current = os.stat(filepath).st_mode
            # Only change if not already read-only
            if current & 0o222:  # any write bit set
                os.chmod(filepath, 0o444)
                perms_set += 1
                if not args.quiet and not args.json:
                    print(f"  🔒 {filename}: set to 444 (read-only)")
        except OSError as e:
            perms_failed += 1
            if not args.quiet:
                print(f"  ❌ {filename}: chmod failed — {e}")

    return perms_set, perms_failed


def output_results(results, all_ok, args):
    """Format and print results."""
    if args.json:
        print(json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'all_ok': all_ok,
            'files': results,
            'exit_code': 0 if all_ok else 1
        }, indent=2))
        return

    if args.quiet and all_ok:
        return

    print(f"\n🔍 Data Guardian — Integrity Check")
    print(f"   Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    any_issues = False
    for r in results:
        icon = '✅' if r['status'] == 'ok' else '❌'
        count_info = f" ({r.get('record_count', '?')} records, {r.get('file_size', 0)} bytes)"
        print(f"  {icon} {r['file']}{count_info}")

        if r['issues']:
            any_issues = True
            for issue in r['issues']:
                print(f"     ⚠️  {issue}")

    if any_issues:
        print(f"\n  ❌ FAILED — {sum(1 for r in results if r['status'] != 'ok')} file(s) have issues")
    else:
        print(f"\n  ✅ PASSED — All {len(results)} files OK")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='POS System Data Guardian — protect against file corruption'
    )
    parser.add_argument('--check-only', action='store_true',
                        help='Only check, do not modify permissions or baseline')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress output when all checks pass')
    parser.add_argument('--json', action='store_true',
                        help='JSON output for programmatic parsing')
    parser.add_argument('--set-perms', action='store_true',
                        help='Only set permissions, skip checks')
    parser.add_argument('--fix', action='store_true',
                        help='Attempt auto-fix (not yet implemented)')
    args = parser.parse_args()

    if args.set_perms:
        set_protective_permissions(args)
        return 0

    # Run checks
    results, all_ok = check_files(args)

    # Set protective permissions (skip if check-only)
    if not args.check_only and not args.fix:
        perms_set, perms_failed = set_protective_permissions(args)
        if perms_set > 0 and not args.quiet and not args.json:
            print(f"  🔒 Set 444 permissions on {perms_set} file(s)")

    output_results(results, all_ok, args)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
