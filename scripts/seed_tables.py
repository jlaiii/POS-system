#!/usr/bin/env python3
"""
Seed tables.json with 20 default tables for a standard restaurant layout.
Run standalone: python3 scripts/seed_tables.py
Or import and call seed_default_tables().

Safe to run multiple times — skips if tables.json already has entries
(unless --force flag is passed).
"""

import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES_FILE = os.path.join(PROJECT_ROOT, 'tables.json')

# 20 default tables across common restaurant zones
DEFAULT_TABLES = {
    # Patio (small 2-tops)
    1: {'name': 'Patio 1', 'section': 'Patio', 'capacity': 2},
    2: {'name': 'Patio 2', 'section': 'Patio', 'capacity': 2},
    3: {'name': 'Patio 3', 'section': 'Patio', 'capacity': 2},
    4: {'name': 'Patio 4', 'section': 'Patio', 'capacity': 4},
    # Main Dining (4-tops)
    5: {'name': 'Main 1', 'section': 'Main Dining', 'capacity': 4},
    6: {'name': 'Main 2', 'section': 'Main Dining', 'capacity': 4},
    7: {'name': 'Main 3', 'section': 'Main Dining', 'capacity': 4},
    8: {'name': 'Main 4', 'section': 'Main Dining', 'capacity': 4},
    # Main Dining (larger tables)
    9: {'name': 'Main 5', 'section': 'Main Dining', 'capacity': 6},
    10: {'name': 'Main 6', 'section': 'Main Dining', 'capacity': 6},
    # Bar Area (high tops)
    11: {'name': 'Bar 1', 'section': 'Bar', 'capacity': 2},
    12: {'name': 'Bar 2', 'section': 'Bar', 'capacity': 2},
    13: {'name': 'Bar 3', 'section': 'Bar', 'capacity': 4},
    14: {'name': 'Bar 4', 'section': 'Bar', 'capacity': 4},
    # Window (romantic 2-tops)
    15: {'name': 'Window 1', 'section': 'Window', 'capacity': 2},
    16: {'name': 'Window 2', 'section': 'Window', 'capacity': 2},
    # VIP / Private
    17: {'name': 'VIP Room', 'section': 'VIP', 'capacity': 8},
    # Additional flexible tables
    18: {'name': 'Side 1', 'section': 'Main Dining', 'capacity': 4},
    19: {'name': 'Side 2', 'section': 'Main Dining', 'capacity': 4},
    20: {'name': 'Party Table', 'section': 'Main Dining', 'capacity': 10},
}


def seed_default_tables(force=False, quiet=False):
    """Seed tables.json with 20 default tables. Skips if already populated (unless force=True).
    Returns (count, created): (number of tables in file, whether new seed was written).
    """
    now = datetime.now().isoformat()

    # Load existing
    if os.path.exists(TABLES_FILE):
        try:
            with open(TABLES_FILE, 'r') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, Exception):
            existing = {}
    else:
        existing = {}

    if existing and not force:
        count = len(existing)
        if not quiet:
            print(f"tables.json already has {count} table(s). Use --force to re-seed. Skipping.")
        return (count, False)

    # Build table entries
    tables = {}
    for num, info in DEFAULT_TABLES.items():
        key = str(num)
        tables[key] = {
            'number': num,
            'name': info['name'],
            'tablet_id': '',
            'status': 'available',
            'section': info['section'],
            'capacity': info['capacity'],
            'created_at': now,
            'last_bussed_at': None,
        }

    # Write
    os.makedirs(os.path.dirname(TABLES_FILE) or '.', exist_ok=True)
    with open(TABLES_FILE, 'w') as f:
        json.dump(tables, f, indent=2)

    if not quiet:
        print(f"✅ Seeded {len(tables)} default tables to {TABLES_FILE}")
        print(f"   Sections: {sorted(set(t['section'] for t in tables.values()))}")

    return (len(tables), True)


def main():
    force = '--force' in sys.argv
    quiet = '--quiet' in sys.argv
    count, created = seed_default_tables(force=force, quiet=quiet)
    if created:
        print(f"Created {count} tables.")
    else:
        print(f"tables.json has {count} table(s). No changes made.")


if __name__ == '__main__':
    main()
