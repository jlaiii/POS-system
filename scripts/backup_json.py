#!/usr/bin/env python3
"""
POS System — JSON Data Backup Script
======================================
Creates timestamped backups of all JSON data files in the project root.

What it does:
  1. Scans for all .json files in the project root directory
  2. Validates each file is well-formed JSON (catches partial writes/corruption)
  3. Copies validated files to a timestamped directory: backups/json/YYYY-MM-DD_HH-MM-SS/
  4. Lists each file's size for anomaly spotting (0-byte files = corruption)
  5. Creates a compressed tar.gz archive of the backup directory

Usage:
  python3 scripts/backup_json.py              # normal run
  python3 scripts/backup_json.py --dry-run    # show what would be done, don't copy
  python3 scripts/backup_json.py --quiet      # only output errors

Returns exit code 0 on success, non-zero on failure.
"""

import json
import os
import sys
import tarfile
import glob
from datetime import datetime

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


def validate_json(filepath):
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


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv
    quiet = '--quiet' in sys.argv

    files = get_data_json_files()

    if not files:
        log("No JSON data files found to back up.", quiet)
        return 0

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
        is_valid, err = validate_json(fpath)

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
        is_valid, _ = validate_json(fpath, quiet)
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
    total_size = sum(file_sizes[f] for f in files if validate_json(f, quiet=True)[0])
    log(f"\n{'='*60}", quiet)
    log(f"  ✅ Backup complete!", quiet)
    log(f"  📍 Directory : {backup_dir}", quiet)
    log(f"  🗜️  Archive   : {tarball_path}", quiet)
    log(f"  📄 Files     : {copied_count}", quiet)
    log(f"  📦 Data size : {readable_size(total_size)} (uncompressed)", quiet)
    log(f"{'='*60}\n", quiet)

    return 0


def validate_json(filepath, quiet=False):
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
