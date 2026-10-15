"""Exercise the MVP on a private HTTP server and disposable SQLite database.

Run with the virtualenv Python: python scripts/smoke_mvp.py
Add --with-ui to run the existing React DOM integration using Node.js.
This never accepts the URL of a working warehouse and never changes its DB.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


class CheckFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = None

    def request(self, path, payload=None, expected=200, csrf=True):
        headers = {}
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            if csrf and self.csrf:
                headers['X-CSRF-Token'] = self.csrf
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base + path, data=data, headers=headers)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            code, content_type = response.status, response.headers.get('Content-Type', '')
            raw = response.read()
        require(code == expected, f'{path}: expected HTTP {expected}, received {code}')
        return json.loads(raw) if 'application/json' in content_type else raw

    def login(self, role):
        result = self.request('/api/auth/login', {
            'email': f'{role}@easystock.local', 'password': 'DemoStock2026!'
        })
        self.csrf = result['csrf_token']
        return result['user']


class Server:
    def __init__(self, database, log):
        self.database, self.log = database, log
        self.process = None
        self.base = ''

    def start(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.base = f'http://127.0.0.1:{port}'
        environment = dict(os.environ, DATABASE_URL='sqlite:///' + self.database.as_posix(), COOKIE_SECURE='0')
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / 'start.py'), '--demo', '--port', str(port)],
            cwd=ROOT, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            require(self.process.poll() is None, 'The isolated server exited before becoming ready.')
            try:
                health = Client(self.base).request('/api/health')
                if health.get('status') == 'ok' and health.get('app') == 'EasyStock':
                    return
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(0.1)
        raise CheckFailure('The isolated server did not become ready within 25 seconds.')

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def snapshot(database, product_id):
    with closing(sqlite3.connect(database)) as connection:
        balance = connection.execute('SELECT quantity FROM stock WHERE product_id = ?', (product_id,)).fetchone()[0]
        counts = tuple(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                       for table in ('stock_movements', 'receipts', 'receipt_items'))
    return balance, counts


def exercise(server, database, report):
    def passed(name, **facts):
        report['checks'].append(dict(name=name, status='PASS', **facts))
        print(f'PASS {len(report["checks"]):02}: {name}', flush=True)

    server.start()
    passed('HTTP health endpoint', http=200)
    visitor = Client(server.base)
    html = visitor.request('/').decode()
    require('id="root"' in html, 'The React root is missing from the served HTML.')
    script = re.search(r'<script[^>]+src="([^"]+)"', html)
    require(script is not None and script[1].startswith('/assets/'), 'The frontend bundle is missing.')
    require(len(visitor.request(script[1])) > 100, 'The frontend bundle cannot be loaded.')
    passed('HTML and compiled frontend are served', http=200)
    visitor.request('/api/products', expected=401)
    passed('Unauthenticated catalogue is denied', http=401)
    visitor.request('/api/auth/login', {'email': 'keeper@easystock.local', 'password': 'invalid'}, expected=401)
    passed('Incorrect password is denied', http=401)
    keeper = Client(server.base)
    actor = keeper.login('keeper')
    require(actor['role'] == 'keeper', 'Expected the warehouse keeper role.')
    passed('Keeper login and CSRF token', http=200)
    items = keeper.request('/api/products?q=SSD-480')['items']
    require(len(items) == 1 and items[0]['sku'] == 'SSD-480', 'SKU search must return exactly one product.')
    product_id = items[0]['id']
    require(snapshot(database, product_id)[0] == 17, 'Fresh demo stock must equal 17.')
    passed('SKU search and initial stock', balance=17)
    before = snapshot(database, product_id)
    keeper.request('/api/stock/receipt', {'product_id': product_id, 'quantity': 20}, expected=403, csrf=False)
    require(snapshot(database, product_id) == before, 'Missing CSRF changed the database.')
    passed('Missing CSRF leaves stock and audit unchanged', http=403)
    keeper.request('/api/stock/receipt', {'product_id': product_id, 'quantity': 0}, expected=400)
    require(snapshot(database, product_id) == before, 'Invalid quantity changed the database.')
    passed('Zero quantity leaves stock and audit unchanged', http=400)
    result = keeper.request('/api/stock/receipt', {
        'product_id': product_id, 'quantity': 20, 'note': 'Lab5 smoke receipt'
    }, expected=201)
    require(result['receipt_id'] is not None, 'A successful receipt must have a document ID.')
    require(snapshot(database, product_id) == (37, tuple(n + 1 for n in before[1])), 'Receipt and audit were not saved atomically.')
    passed('Receipt adds 20 with one document and audit entry', http=201, balance=37)
    before = snapshot(database, product_id)
    error = keeper.request('/api/stock/writeoff', {'product_id': product_id, 'quantity': 40}, expected=409)
    require('37' in error.get('error', ''), 'The conflict must explain the available quantity.')
    require(snapshot(database, product_id) == before, 'Excess writeoff changed stock or audit.')
    passed('Excess writeoff is rejected without database changes', http=409, balance=37)
    keeper.request('/api/stock/writeoff', {
        'product_id': product_id, 'quantity': 3, 'note': 'Lab5 smoke writeoff'
    }, expected=201)
    require(snapshot(database, product_id) == (34, (before[1][0] + 1, before[1][1], before[1][2])), 'Writeoff and audit were not saved atomically.')
    passed('Writeoff subtracts 3 and saves an audit entry', http=201, balance=34)
    history_path = f'/api/stock/history?product_id={product_id}'
    history = keeper.request(history_path)
    relevant = {row['note']: row for row in history['items'] if row['note'].startswith('Lab5 smoke ')}
    for note, kind, quantity, balance in [('receipt', 'receipt', 20, 37), ('writeoff', 'writeoff', 3, 34)]:
        row = relevant.get('Lab5 smoke ' + note, {})
        require(row.get('type') == kind and row.get('quantity') == quantity and row.get('balance_after') == balance,
                'The history does not reflect the completed stock operation.')
        require(row.get('author') == actor['name'] and row.get('created_at', '').endswith('Z'), 'Audit author or UTC timestamp is missing.')
    passed('History includes author, UTC timestamp and both balances')
    before = snapshot(database, product_id)
    for _ in range(3):
        keeper.request(f'/api/products/{product_id}')
        keeper.request(history_path)
    require(snapshot(database, product_id) == before, 'Repeated GET duplicated an operation.')
    passed('Repeated reads do not duplicate stock movements')
    server.stop()
    server.start()
    keeper = Client(server.base)
    keeper.login('keeper')
    require(snapshot(database, product_id) == before, 'Data changed after a full server restart.')
    require(keeper.request(history_path)['total'] == history['total'], 'History changed after restart.')
    require(keeper.request(f'/api/products/{product_id}')['quantity'] == 34, 'API stock was not persisted.')
    passed('Full server restart preserves stock and history', balance=34)
    manager = Client(server.base)
    manager.login('manager')
    manager.request('/api/products')
    manager.request('/api/stock/writeoff', {'product_id': product_id, 'quantity': 1}, expected=403)
    require(snapshot(database, product_id) == before, 'Manager writeoff changed the database.')
    passed('Manager can read but cannot change stock', http=403)
    manager.request('/api/users', expected=403)
    passed('Manager cannot read the users administration endpoint', http=403)
    keeper.request('/api/auth/logout', {})
    keeper.request('/api/products', expected=401)
    passed('Logout revokes the session', http=401)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='Write a result report without session tokens.')
    parser.add_argument('--with-ui', action='store_true', help='Also run the existing React DOM integration.')
    parser.add_argument('--node', default='node', help='Node.js executable for --with-ui.')
    args = parser.parse_args()
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), checks=[], status='FAIL', browser_layout_tested=False)
    try:
        with tempfile.TemporaryDirectory(prefix='easystock-smoke-') as directory:
            temporary = Path(directory)
            with (temporary / 'server.log').open('w', encoding='utf-8') as log:
                server = Server(temporary / 'smoke.db', log)
                try:
                    exercise(server, server.database, report)
                    if args.with_ui:
                        node = shutil.which(args.node)
                        require(node is not None, 'Node.js is required for --with-ui.')
                        result = subprocess.run([node, str(ROOT / 'tests/ui.mjs')], cwd=ROOT / 'frontend',
                            env=dict(os.environ, EASYSTOCK_URL=server.base), capture_output=True, text=True, timeout=90)
                        require(result.returncode == 0, 'React DOM integration failed; rerun tests/ui.mjs for its diagnostics.')
                        report['checks'].append(dict(name='React DOM with real HTTP API', status='PASS'))
                        report['react_dom_output'] = result.stdout
                        print('PASS 18: React DOM with real HTTP API', flush=True)
                finally:
                    server.stop()
        require(not temporary.exists(), 'The disposable database was not removed.')
        report.update(status='PASS', temporary_database_removed=True)
    except (CheckFailure, URLError, OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
        print('FAIL:', error, file=sys.stderr)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{report["status"]}: {len(report["checks"])} completed checks; browser layout is not tested.')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
