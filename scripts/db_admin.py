"""Create or restore a verified EasyStock SQLite copy without replacing files."""

import argparse
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from easystock.db_backup import copy_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'restore'))
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path, help='New path; existing files are never overwritten')
    args = parser.parse_args()
    try:
        result = copy_database(args.source, args.destination)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f'EasyStock {args.action}: {error}\n')
    print(f'EasyStock {args.action}: {result.resolve()}')


if __name__ == '__main__':
    main()
