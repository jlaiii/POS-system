#!/usr/bin/env python3
"""
POS System — Backup Monitor & Daily Summary Script
====================================================
Generates a consolidated backup status report and sends it to Discord
via the configured webhook. Designed to run daily at 6am via cron.

Provides the owner with a single "everything OK" summary so they don't
need to check individual backup logs.

Usage:
  python3 scripts/backup_monitor.py                    # full report to Discord
  python3 scripts/backup_monitor.py --stdout           # print report to stdout only
  python3 scripts/backup_monitor.py --quiet            # only send to Discord, no stdout
  python3 scripts/backup_monitor.py --skip-health      # skip db_health check (faster)

Exit code:
  0 = sent successfully (or printed), no issues
  1 = issues found (corrupt backups, health failures, etc.)
  2 = configuration error (no webhook, no backup dir)
"""

import json
import os
import re
import sys
import glob
import tarfile
import subprocess
import urllib.request
from datetime import datetime, timedelta

# ── Paths ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_BASE = os.path.join(PROJECT_ROOT, 'backups', 'json')
SECURITY_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'security_config.json')
DB_HEALTH_SCRIPT = os.path.join(PROJECT_ROOT, 'scripts', 'db_health.py')

# Non-data JSON files to exclude from backup listing
EXCLUDED_FILES = {'package.json', 'package-lock.json', 'manifest.json'}


# ── Helpers ─────────────────────────────────────────────────────────────────

def log(msg, quiet=False):
    if not quiet:
        print(msg)


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
    """Parse YYYY-MM-DD_HH-MM-SS from a backup filename.
    Returns a datetime object or None."""
    match = re.match(r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', name)
    if match:
        return datetime.strptime(match.group(1), '%Y-%m-%d_%H-%M-%S')
    return None


def get_backup_archives():
    """Return sorted list of (timestamp, filename, full_path, size_bytes)
    for all .tar.gz archives in BACKUP_BASE."""
    if not os.path.isdir(BACKUP_BASE):
        return []
    archives = []
    for entry in sorted(os.listdir(BACKUP_BASE)):
        if not entry.endswith('.tar.gz'):
            continue
        path = os.path.join(BACKUP_BASE, entry)
        ts = parse_backup_timestamp(entry)
        if ts:
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            archives.append((ts, entry, path, size))
    return sorted(archives, key=lambda x: x[0])


def validate_archive(archive_path):
    """Test that a tar.gz archive can be opened and read.
    Returns (is_valid, error_message)."""
    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            members = tar.getmembers()
            json_count = sum(1 for m in members if m.name.endswith('.json'))
            total_size = sum(m.size for m in members)
            return True, f"{len(members)} files, {json_count} JSON files, {readable_size(total_size)}"
    except tarfile.ReadError as e:
        return False, f"Corrupt archive: {e}"
    except Exception as e:
        return False, str(e)


def run_health_check():
    """Run the db_health.py script and return (overall_status, summary, details).
    Returns (True, 'OK', '') on success, (False, 'FAIL', details) on failure."""
    if not os.path.isfile(DB_HEALTH_SCRIPT):
        return None, "SKIPPED — db_health.py not found", ""
    try:
        result = subprocess.run(
            [sys.executable, DB_HEALTH_SCRIPT, '--quiet', '--check-only'],
            capture_output=True, text=True, timeout=60
        )
        healthy = (result.returncode == 0)
        if healthy:
            return True, "PASSED", ""
        else:
            details = result.stdout.strip() or result.stderr.strip() or "Unknown error"
            return False, "FAILED", details
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", "db_health.py timed out after 60s"
    except Exception as e:
        return False, "ERROR", str(e)


def get_backup_stats(archives):
    """Analyze backup archives and return categorized stats dict."""
    now = datetime.now()

    stats = {
        'total': len(archives),
        'total_size': sum(a[3] for a in archives),
        'hourly': 0,    # < 24h old
        'daily': 0,     # 1-7 days old
        'weekly': 0,    # 1-4 weeks old
        'monthly': 0,   # 1-12 months old
        'older': 0,     # > 12 months
        'latest': None,
        'latest_ts': None,
        'latest_size': 0,
        'latest_valid': None,
        'oldest': None,
        'oldest_ts': None,
    }

    if not archives:
        return stats

    # Latest archive
    latest_ts, latest_name, latest_path, latest_size = archives[-1]
    stats['latest'] = latest_name
    stats['latest_ts'] = latest_ts
    stats['latest_size'] = latest_size

    # Validate latest archive
    valid, msg = validate_archive(latest_path)
    stats['latest_valid'] = valid
    stats['latest_valid_msg'] = msg

    # Oldest archive
    oldest_ts = archives[0][0]
    stats['oldest'] = archives[0][1]
    stats['oldest_ts'] = oldest_ts

    # Categorize all archives by age
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    cutoff_4w = now - timedelta(weeks=4)
    cutoff_12m = now - timedelta(days=365)

    for ts, _, _, _ in archives:
        if ts >= cutoff_24h:
            stats['hourly'] += 1
        elif ts >= cutoff_7d:
            stats['daily'] += 1
        elif ts >= cutoff_4w:
            stats['weekly'] += 1
        elif ts >= cutoff_12m:
            stats['monthly'] += 1
        else:
            stats['older'] += 1

    return stats


def load_discord_webhook():
    """Load Discord webhook URL from security_config.json.
    Returns the URL string or None."""
    try:
        with open(SECURITY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        url = (config.get('discord_webhook_url') or '').strip()
        return url if url else None
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def send_discord_message(webhook_url, report_text, summary_line, has_issues):
    """Send a formatted Discord embed with the backup report.
    Returns True on success, False on failure."""
    color = 0xe74c3c if has_issues else 0x2ecc71  # red if issues, green if OK
    title = "📦 DB Backup Report"

    payload = {
        'embeds': [{
            'title': title,
            'description': report_text,
            'color': color,
            'footer': {
                'text': f'POS System · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }
        }]
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url, data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def build_report(stats, health_status, health_detail):
    """Build a human-readable report string from stats."""
    lines = []

    # ── Summary line ──
    total_size_str = readable_size(stats['total_size'])
    status_icon = "✅" if stats['latest_valid'] else "❌"
    lines.append(f"{status_icon} **Backup Overview**: {stats['total']} archives, **{total_size_str}** total")

    # ── Retention breakdown ──
    parts = []
    if stats['hourly'] > 0:
        parts.append(f"**{stats['hourly']}** hourly (<24h)")
    if stats['daily'] > 0:
        parts.append(f"**{stats['daily']}** daily (1-7d)")
    if stats['weekly'] > 0:
        parts.append(f"**{stats['weekly']}** weekly (1-4w)")
    if stats['monthly'] > 0:
        parts.append(f"**{stats['monthly']}** monthly (1-12m)")
    if stats['older'] > 0:
        parts.append(f"**{stats['older']}** older (>12m — needs cleanup)")

    if parts:
        lines.append("📊 **Retention**: " + " | ".join(parts))
    else:
        lines.append("📊 **Retention**: No backups found")

    # ── Date range ──
    if stats['oldest_ts'] and stats['latest_ts']:
        lines.append(f"📅 **Range**: {stats['oldest_ts'].strftime('%b %d')} → {stats['latest_ts'].strftime('%b %d, %Y')}")
    elif stats['latest_ts']:
        lines.append(f"📅 **Latest**: {stats['latest_ts'].strftime('%Y-%m-%d %H:%M')}")

    # ── Latest backup validation ──
    if stats['latest']:
        latest_name = stats['latest'].replace('.tar.gz', '')
        latest_size_str = readable_size(stats['latest_size'])
        valid_icon = "✅" if stats['latest_valid'] else "❌"
        lines.append(f"📦 **Latest backup**: `{latest_name}` ({latest_size_str})")
        if 'latest_valid_msg' in stats and stats['latest_valid_msg']:
            lines.append(f"   {valid_icon} Integrity: {stats['latest_valid_msg']}")

    # ── Integrity check result ──
    if health_status is not None:
        if health_status:
            lines.append(f"✅ **Integrity check**: PASSED")
        else:
            lines.append(f"❌ **Integrity check**: FAILED — {health_detail}")

    # ── Footer note ──
    if stats['latest_valid'] and (health_status is None or health_status):
        lines.append("\n🟢 **All systems OK** — backups are running normally.")
    else:
        lines.append("\n🔴 **Issues detected** — review the details above.")

    return "\n".join(lines)


def main():
    args = set(sys.argv[1:])
    to_stdout = '--stdout' in args
    quiet = '--quiet' in args
    skip_health = '--skip-health' in args

    # ── Scan backups ──
    archives = get_backup_archives()
    stats = get_backup_stats(archives)

    # ── Run health check ──
    health_status = None
    health_detail = ""
    if not skip_health:
        health_status, health_summary, health_detail = run_health_check()
    else:
        health_status = None

    # ── Build report ──
    has_issues = False
    if stats['total'] == 0:
        has_issues = True
        report = "⚠️ **No backup archives found.** Backups may not be running."
    else:
        if stats['latest_valid'] is False:
            has_issues = True
        if health_status is False:
            has_issues = True
        report = build_report(stats, health_status, health_detail)

    # ── Short summary for stdout line ──
    if stats['total'] > 0:
        summary_line = f"📦 {stats['total']} backups, {readable_size(stats['total_size'])} total"
        if stats['latest_ts']:
            summary_line += f", latest: {stats['latest_ts'].strftime('%m/%d %H:%M')}"
        if health_status is True:
            summary_line += ", health: ✅"
        elif health_status is False:
            summary_line += ", health: ❌"
    else:
        summary_line = "⚠️ No backups found"

    # ── Output ──
    if to_stdout or quiet:
        # Print report to stdout if --stdout
        if to_stdout:
            print(report)
        # Send to Discord if webhook configured
        webhook_url = load_discord_webhook()
        if webhook_url:
            sent = send_discord_message(webhook_url, report, summary_line, has_issues)
            if sent:
                log("✅ Backup report sent to Discord.", quiet)
            else:
                log("❌ Failed to send backup report to Discord.", quiet)
                return 1 if has_issues else 0
        elif not quiet:
            log("ℹ️  No Discord webhook configured. Install one in Security Settings.", quiet)
    else:
        # Default: print to stdout
        print(f"\n{'='*60}")
        print(f"  POS Backup Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print()
        print(report)
        print()
        print(f"{'='*60}")

    return 1 if has_issues else 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
