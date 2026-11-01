"""Verify retry persistence and an additive schema upgrade on a disposable server."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request

from smoke_mvp import Client, Server, require, snapshot

ROOT = Path(__file__).resolve().parents[1]


def source_fingerprint():
    """Hash executable source, lockfiles and the served bundle, excluding reports."""
    paths = [ROOT / name for name in ('start.py', 'run_demo.bat', 'run_demo.sh',
             'frontend/package.json', 'frontend/package-lock.json', 'database/schema.sql')]
    for name in ('backend', 'frontend/src', 'frontend/dist', 'scripts', 'tests'):
        paths.extend(p for p in (ROOT / name).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0')
        digest.update(path.read_bytes() + b'\0')
    return digest.hexdigest()


class ReleaseClient(Client):
    def keyed(self, kind, payload, key, expected=201):
        headers = {'Content-Type': 'application/json', 'X-CSRF-Token': self.csrf,
                   'Idempotency-Key': key}
        request = Request(self.base + '/api/stock/' + kind,
                          data=json.dumps(payload).encode(), headers=headers)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            require(response.status == expected, f'Keyed {kind}: HTTP {response.status}, expected {expected}')
            return json.loads(response.read())


def exercise(server, report):
    def passed(name, **facts):
        report['checks'].append(dict(name=name, status='PASS', **facts))
        print(f'PASS {len(report["checks"]):02}: {name}', flush=True)

    server.start()
    with closing(sqlite3.connect(server.database)) as connection:
        require(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0,
                'Startup without --demo created standard accounts.')
    passed('Startup without --demo creates no standard accounts', users=0)
    server.stop()
    server.demo = True
    server.start()
    client = ReleaseClient(server.base)
    client.login('keeper')
    legacy_before = snapshot(server.database, 1)
    server.stop()
    with closing(sqlite3.connect(server.database)) as connection:
        connection.execute('DROP TABLE stock_requests')
        connection.commit()
    server.start()
    require(snapshot(server.database, 1) == legacy_before, 'Schema upgrade changed existing stock or audit.')
    with closing(sqlite3.connect(server.database)) as connection:
        require(connection.execute("SELECT name FROM sqlite_master WHERE name='stock_requests'").fetchone(),
                'The additive table was not created.')
    passed('Startup upgrades a legacy schema without changing demo stock or audit', balance=17)
    client = ReleaseClient(server.base)
    client.login('keeper')
    payload = {'product_id': 1, 'quantity': 20, 'note': 'Lab6 persisted retry'}
    first = client.keyed('receipt', payload, 'persistent-delivery')
    require(snapshot(server.database, 1)[0] == 37, 'The first delivery was not committed.')
    passed('Initial receipt commits once before a simulated discarded reply', http=201, balance=37)
    before_retry = snapshot(server.database, 1)
    server.stop()
    server.start()
    client = ReleaseClient(server.base)
    client.login('keeper')
    retried = client.keyed('receipt', payload, 'persistent-delivery')
    require(retried == first, 'Restarted retry must return the original response.')
    require(snapshot(server.database, 1) == before_retry, 'Restarted retry duplicated stock or audit.')
    passed('Same key survives full restart and re-login without a second receipt', http=201, balance=37)
    client.keyed('receipt', {**payload, 'quantity': 21}, 'persistent-delivery', expected=409)
    require(snapshot(server.database, 1) == before_retry, 'A reused key with changed data changed stock.')
    passed('Changed intent with the same key is rejected without mutation', http=409)
    writeoff = {'product_id': 1, 'quantity': 3, 'note': 'Lab6 safe writeoff'}
    result = client.keyed('writeoff', writeoff, 'persistent-writeoff')
    before_retry = snapshot(server.database, 1)
    require(before_retry[0] == 34, 'Expected 37 minus 3 units.')
    require(client.keyed('writeoff', writeoff, 'persistent-writeoff') == result, 'Writeoff response changed on retry.')
    require(snapshot(server.database, 1) == before_retry, 'Retry duplicated the writeoff.')
    passed('Writeoff retry preserves stock 34 and its single audit entry', http=201, balance=34)
    manager = ReleaseClient(server.base)
    manager.login('manager')
    manager.keyed('receipt', payload, 'persistent-delivery', expected=403)
    require(snapshot(server.database, 1) == before_retry, 'Manager bypassed the role through a request key.')
    passed('Manager cannot use a known key to bypass write permissions', http=403)
    client.request('/api/auth/logout', {})
    client.request('/api/products', expected=401)
    passed('Session logout remains effective after keyed operations', http=401)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
    git = shutil.which('git')
    commit = subprocess.run([git, 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True) if git else None
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), status='FAIL', checks=[],
                  source_commit=commit.stdout.strip() if commit and commit.returncode == 0 else None,
                  source_sha256=source_fingerprint(), platform=platform.platform(),
                  python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                  packages={name: version(name) for name in ('Flask', 'Flask-SQLAlchemy', 'SQLAlchemy', 'waitress', 'pytest')},
                  browser_layout_tested=False)
    try:
        with tempfile.TemporaryDirectory(prefix='easystock-release-') as temporary:
            directory = Path(temporary)
            with (directory / 'server.log').open('w') as log:
                server = Server(directory / 'release.db', log, demo=False)
                try:
                    exercise(server, report)
                finally:
                    server.stop()
        require(not directory.exists(), 'The disposable database was not removed.')
        report.update(status='PASS', temporary_database_removed=True)
    except Exception as error:
        report['error'] = str(error)
        print('FAIL:', error, file=sys.stderr)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
