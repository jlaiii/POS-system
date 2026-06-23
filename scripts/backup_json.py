#!/usr/bin/env python3
"""
POS System — JSON Data Backup Script
======================================
Creates timestamped backups of all JSON data files in the project root,
then applies retention cleanup to keep only:
  - All hourly backups from last 24 hours
  - One per day for last 7 days
  - One per week for last 4 weeks
  - One per month for last 12 months

Usage:
  python3 scripts/backup_json.py                      # normal run (backup + cleanup)
  python3 scripts/backup_json.py --dry-run            # show what would be done
  python3 scripts/backup_json.py --quiet              # only output errors
  python3 scripts/backup_json.py --cleanup-only       # only run retention cleanup
  python3 scripts/backup_json.py --dry-run --cleanup-only  # preview cleanup only

Returns exit code 0 on success, non-zero on failure.
"""

import json
import os
import re
import sys
import tarfile
import glob
import shutil
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────

# Files to EXCLUDE from backup (non-data JSON files)
EXCLUDED_FILES = {
    'package.json',
    'package-lock.json',
    'manifest.json',
}

# Project root (parent of scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Backup directory inside project: backups/json/
BACKUP_BASE = os.path.join(PROJECT_ROOT, 'backups', 'json')


# ── Helpers ────────────────────────────────────────────────────────────────

def log(msg, quiet=False):
    if not quiet:
        print(msg)


def get_data_json_files():
    """Return sorted list of .json file paths in the project root,
    excluding non-data files like package.json."""
    pattern = os.path.join(PROJECT_ROOT, '*.json')
    all_files = sorted(glob.glob(pattern))
    return [
        f for f in all_files
        if os.path.basename(f) not in EXCLUDED_FILES
    ]


def validate_json_file(filepath):
    """Return (is_valid, error_msg). Tries to parse the file as JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, None
    except json.JSONDecodeError as e:
        return False, f"JSON decode error: {e}"
    except FileNotFoundError:
        return False, "File not found"
    except Exception as e:
        return False, str(e)


def readable_size(size_bytes):
    """Convert bytes to human-readable string."""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def parse_backup_timestamp(name):
    """Parse YYYY-MM-DD_HH-MM-SS from a backup filename or directory name.
    Returns a datetime object or None if no match."""
    match = re.match(r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', name)
    if match:
        return datetime.strptime(match.group(1), '%Y-%m-%d_%H-%M-%S')
    return None


def get_all_backups():
    """Return sorted list of (timestamp, path, is_archive, name) for all
    backup items (both .tar.gz files and timestamped directories) in BACKUP_BASE."""
    if not os.path.isdir(BACKUP_BASE):
        return []
    backups = []
    for entry in sorted(os.listdir(BACKUP_BASE)):
        path = os.path.join(BACKUP_BASE, entry)
        ts = parse_backup_timestamp(entry)
        if ts:
            is_archive = entry.endswith('.tar.gz')
            backups.append((ts, path, is_archive, entry))
    return sorted(backups, key=lambda x: x[0])


# ── Retention Cleanup ──────────────────────────────────────────────────────

def retention_cleanup(dry_run=False, quiet=False):
    """Apply retention policy to backups/json/ directory.

    Rules:
      - Keep ALL backups from the last 24 hours (hourly granularity)
      - Keep 1 per day for days 1-7 ago (daily granularity)
      - Keep 1 per week for weeks 1-4 ago (weekly granularity)
      - Keep 1 per month for months 1-12 ago (monthly granularity)
      - Delete everything outside these windows

    dry_run: if True, only print what would be deleted, don't actually delete.
    Returns 0 on success, 1 on error.
    """
    now = datetime.now()
    backups = get_all_backups()

    if not backups:
        log("  📭 No backups found for cleanup.", quiet)
        return 0

    # Timestamp thresholds
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    cutoff_4w = now - timedelta(weeks=4)
    cutoff_12m = now - timedelta(days=365)

    # Phase 1: Keep ALL backups from last 24 hours
    keep = set()
    for ts, path, is_archive, name in backups:
        if ts >= cutoff_24h:
            keep.add(name)

    # Phase 2: Keep 1 per day for days 1-7 ago
    # Consider backups older than 24h but within 7 days
    daily_candidates = [
        (ts, name) for ts, _, _, name in backups
        if ts < cutoff_24h and ts >= cutoff_7d
    ]
    by_day = {}
    for ts, name in daily_candidates:
        day_key = ts.strftime('%Y-%m-%d')
        if day_key not in by_day or ts > by_day[day_key][0]:
            by_day[day_key] = (ts, name)
    for ts, name in by_day.values():
        keep.add(name)

    # Phase 3: Keep 1 per ISO week for weeks 1-4 ago
    # Consider backups older than 7 days but within 4 weeks
    weekly_candidates = [
        (ts, name) for ts, _, _, name in backups
        if ts < cutoff_7d and ts >= cutoff_4w and name not in keep
    ]
    by_week = {}
    for ts, name in weekly_candidates:
        week_key = ts.strftime('%Y-W%W')
        if week_key not in by_week or ts > by_week[week_key][0]:
            by_week[week_key] = (ts, name)
    for ts, name in by_week.values():
        keep.add(name)

    # Phase 4: Keep 1 per month for months 1-12 ago
    # Consider backups older than 4 weeks but within 12 months
    monthly_candidates = [
        (ts, name) for ts, _, _, name in backups
        if ts < cutoff_4w and ts >= cutoff_12m and name not in keep
    ]
    by_month = {}
    for ts, name in monthly_candidates:
        month_key = ts.strftime('%Y-%m')
        if month_key not in by_month or ts > by_month[month_key][0]:
            by_month[month_key] = (ts, name)
    for ts, name in by_month.values():
        keep.add(name)

    # Phase 5: Identify items to delete (anything NOT in keep)
    to_delete = [
        (name, path, is_archive) for ts, path, is_archive, name in backups
        if name not in keep
    ]

    if not to_delete:
        log(f"  🧹 Retention cleanup: nothing to delete ({len(keep)} kept).", quiet)
        return 0

    log(f"", quiet)
    log(f"  {'='*60}", quiet)
    log(f"  Retention Cleanup", quiet)
    log(f"  {'='*60}", quiet)
    log(f"  Total backups   : {len(backups)}", quiet)
    log(f"  Kept            : {len(keep)}", quiet)
    log(f"  To delete       : {len(to_delete)}", quiet)

    if dry_run:
        log(f"  {'─'*60}", quiet)
        log(f"  Would delete ({len(to_delete)} items):", quiet)
        for name, path, is_archive in sorted(to_delete, key=lambda x: x[0]):
            size_str = ""
            try:
                if os.path.isfile(path):
                    size_str = f" ({readable_size(os.path.getsize(path))})"
                elif os.path.isdir(path):
                    total = sum(os.path.getsize(os.path.join(dp, f))
                                for dp, dn, filenames in os.walk(path)
                                for f in filenames)
                    size_str = f" ({readable_size(total)})"
            except OSError:
                pass
            log(f"     - {name}{size_str}", quiet)
        log(f"  🏁 Dry-run — no files deleted.", quiet)
        log(f"  {'='*60}", quiet)
        return 0

    # Actually delete
    deleted_count = 0
    failed_count = 0
    for name, path, is_archive in sorted(to_delete, key=lambda x: x[0]):
        try:
            if os.path.isfile(path):
                os.remove(path)
                log(f"  🗑️  Deleted archive: {name}", quiet)
            elif os.path.isdir(path):
                shutil.rmtree(path)
                log(f"  🗑️  Deleted dir   : {name}", quiet)
            deleted_count += 1
        except Exception as e:
            log(f"  ❌ Failed to delete {name}: {e}", quiet)
            failed_count += 1

    log(f"  {'─'*60}", quiet)
    log(f"  🧹 Retention cleanup complete.", quiet)
    if failed_count > 0:
        log(f"  ⚠️  {failed_count} item(s) could not be deleted.", quiet)
    log(f"  Kept {len(keep)}, deleted {deleted_count}.", quiet)
    log(f"  {'='*60}", quiet)

    return 1 if failed_count > 0 else 0


# ── Backup Logic ───────────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    dry_run = '--dry-run' in args
    quiet = '--quiet' in args
    cleanup_only = '--cleanup-only' in args

    # ── Cleanup-only mode ──
    if cleanup_only:
        return retention_cleanup(dry_run=dry_run, quiet=quiet)

    files = get_data_json_files()

    if not files:
        log("No JSON data files found to back up.", quiet)
        # Still run cleanup even if no new files to back up
        return retention_cleanup(dry_run=dry_run, quiet=quiet)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = os.path.join(BACKUP_BASE, timestamp)
    tarball_path = os.path.join(BACKUP_BASE, f'{timestamp}.tar.gz')

    log(f"\n{'='*60}", quiet)
    log(f"  JSON Backup — {timestamp}", quiet)
    log(f"{'='*60}", quiet)
    log(f"  Source   : {PROJECT_ROOT}", quiet)
    log(f"  Target   : {backup_dir}", quiet)
    log(f"  Archive  : {tarball_path}", quiet)
    log(f"  Files    : {len(files)} JSON data files found", quiet)
    log(f"{'='*60}\n", quiet)

    # ── Validate all files first ──
    invalid_files = []
    file_sizes = {}
    log(f"  {'FILE':<40} {'SIZE':>10}  STATUS", quiet)
    log(f"  {'-'*40} {'-'*10}  {'-'*10}", quiet)

    for fpath in files:
        fname = os.path.basename(fpath)
        size = os.path.getsize(fpath)
        file_sizes[fpath] = size
        is_valid, err = validate_json_file(fpath)

        size_str = readable_size(size)
        if is_valid:
            log(f"  {fname:<40} {size_str:>10}  ✅", quiet)
        else:
            log(f"  {fname:<40} {size_str:>10}  ❌ {err}", quiet)
            invalid_files.append((fname, err))

    log(f"\n  {'='*60}", quiet)

    # ── Report invalid files ──
    if invalid_files:
        log(f"\n  ⚠️  {len(invalid_files)} file(s) failed validation:", quiet)
        for fname, err in invalid_files:
            log(f"     - {fname}: {err}", quiet)
        log("  These files will NOT be backed up.", quiet)
    else:
        log(f"\n  ✅ All JSON files validated successfully.", quiet)

    # ── Spot anomalies (0-byte or suspiciously small/large) ──
    anomalies = []
    for fpath in files:
        size = file_sizes[fpath]
        fname = os.path.basename(fpath)
        if size == 0:
            anomalies.append(f"     ⚠️ {fname}: 0 bytes (empty file!)")
        elif size < 10:
            anomalies.append(f"     ⚠️ {fname}: {size} bytes (suspiciously small)")

    if anomalies:
        log(f"\n  🔍 Size anomalies:", quiet)
        for a in anomalies:
            log(a, quiet)
    else:
        log(f"\n  📊 No size anomalies detected.", quiet)

    # ── Dry-run: stop here ──
    if dry_run:
        log(f"\n  🏁 Dry-run complete. No files were copied.\n", quiet)
        return 0

    # ── Create backup directory ──
    os.makedirs(backup_dir, exist_ok=True)

    # ── Copy validated files ──
    copied_count = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        is_valid, _ = validate_json_file(fpath)
        if not is_valid:
            continue
        try:
            dest = os.path.join(backup_dir, fname)
            with open(fpath, 'rb') as src_f:
                with open(dest, 'wb') as dst_f:
                    dst_f.write(src_f.read())
            copied_count += 1
        except Exception as e:
            log(f"  ❌ Failed to copy {fname}: {e}", quiet)

    log(f"\n  📦 Copied {copied_count}/{len(files)} files to {backup_dir}", quiet)

    if copied_count == 0:
        log("  ❌ No files were copied. Backup ABORTED.", quiet)
        # Remove empty directory
        try:
            os.rmdir(backup_dir)
        except OSError:
            pass
        return 1

    # ── Create tar.gz archive ──
    try:
        with tarfile.open(tarball_path, 'w:gz') as tar:
            tar.add(backup_dir, arcname=timestamp)
        archive_size = os.path.getsize(tarball_path)
        log(f"  🗜️  Created archive: {tarball_path} ({readable_size(archive_size)})", quiet)
    except Exception as e:
        log(f"  ❌ Failed to create tar.gz: {e}", quiet)
        return 1

    # ── Summary ──
    total_size = sum(
        file_sizes[f] for f in files
        if validate_json_file(f)[0]
    )
    log(f"\n{'='*60}", quiet)
    log(f"  ✅ Backup complete!", quiet)
    log(f"  📍 Directory : {backup_dir}", quiet)
    log(f"  🗜️  Archive   : {tarball_path}", quiet)
    log(f"  📄 Files     : {copied_count}", quiet)
    log(f"  📦 Data size : {readable_size(total_size)} (uncompressed)", quiet)
    log(f"{'='*60}", quiet)

    # ── Retention cleanup ──
    ret = retention_cleanup(dry_run=False, quiet=quiet)
    if ret != 0:
        log("  ⚠️  Retention cleanup had warnings.", quiet)

    log("", quiet)
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nBackup cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
