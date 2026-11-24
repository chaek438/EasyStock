import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import StringIO
from pathlib import Path
import sqlite3

import pytest

from easystock import create_app
from easystock.db_backup import copy_database
from easystock.models import db
from easystock.schema import ensure_schema


def quantity(client, warehouse, product=1):
    result = client.get(f'/api/products/{product}?warehouse_id={warehouse}')
    assert result.status_code == 200
    return result.json['quantity']


def reserve(client):
    return next(w['id'] for w in client.get('/api/warehouses').json['items'] if w['code'] == 'RESERVE')


def create(pair, kind='transfer', items=None, **data):
    client, headers = pair
    response = client.post('/api/documents', headers=headers, json={
        'kind': kind, 'warehouse_id': 1, 'destination_id': reserve(client),
        'items': items if items is not None else [{'product_id': 1, 'quantity': 5}], **data,
    })
    assert response.status_code == 201, response.json
    return response.json


def action(pair, doc, command, **data):
    client, headers = pair
    return client.post(f'/api/documents/{doc["id"]}/{command}', json={'revision': doc['revision'], **data}, headers=headers)


def submit(pair, doc):
    response = action(pair, doc, 'submit')
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'review'
    return response.json


def test_warehouse_catalog_and_quick_receipt_use_selected_stock(admin):
    client, headers = admin
    new = client.post('/api/warehouses', json={'code': 'south-02', 'name': 'Південний склад'}, headers=headers)
    assert new.status_code == 201 and new.json['code'] == 'SOUTH-02'
    warehouse = new.json['id']
    assert quantity(client, warehouse) == 0
    assert client.get(f'/api/products?warehouse_id={warehouse}&status=empty').json['total'] == 12
    receipt = client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 8, 'warehouse_id': warehouse}, headers=headers)
    assert receipt.status_code == 201
    doc = client.get(f'/api/documents/{receipt.json["document_id"]}').json
    assert doc['receipt_id'] == receipt.json['receipt_id'] and doc['status'] == 'posted'
    assert quantity(client, warehouse) == 8 and quantity(client, 1) == 17
    assert client.get(f'/api/dashboard?warehouse_id={warehouse}').json['units'] == 8
    assert client.get(f'/api/stock/history?warehouse_id={warehouse}').json['items'][0]['delta'] == 8
    assert client.get('/api/products?warehouse_id=7777').status_code == 404
    assert client.get(f'/api/warehouses').json['items'][-1]['positions'] == 1


def test_transfer_draft_then_post_is_atomic_and_repeatable(admin, login):
    client, _ = admin
    keeper = login('keeper')
    destination = reserve(client)
    draft = create(keeper)
    assert quantity(client, 1) == 17 and quantity(client, destination) == 0
    review = submit(keeper, draft)
    assert action(keeper, review, 'post').status_code == 403
    assert action(keeper, review, 'return').status_code == 403
    response = action(admin, review, 'post')
    assert response.status_code == 200, response.json
    posted = response.json
    assert [(r['warehouse_id'], r['delta']) for r in posted['movements']] == [(1, -5), (destination, 5)]
    assert posted['author'] != posted['posted_by']
    assert posted['status'] == 'posted'
    assert action(admin, review, 'post').json['movements'] == posted['movements']
    assert quantity(client, 1) == 12 and quantity(client, destination) == 5
    filtered = client.get(f'/api/documents?warehouse_id={destination}&kind=transfer&number={posted["number"]}')
    assert filtered.json['total'] == 1 and filtered.json['items'][0]['id'] == posted['id']
    assert client.get(f'/api/stock/history?document_id={posted["id"]}').json['total'] == 2


def test_multi_item_failure_does_not_apply_the_first_line(admin):
    client, _ = admin
    doc = submit(admin, create(admin, items=[{'product_id': 1, 'quantity': 5}, {'product_id': 2, 'quantity': 50}]))
    response = action(admin, doc, 'post')
    assert response.status_code == 409
    assert quantity(client, 1) == 17 and quantity(client, reserve(client)) == 0
    stored = client.get(f'/api/documents/{doc["id"]}').json
    assert stored['status'] == 'review' and stored['movements'] == []


def test_two_transfers_cannot_spend_the_same_stock(admin, login):
    client, _ = admin
    first, second = [submit(admin, create(admin, items=[{'product_id': 1, 'quantity': 12}])) for _ in range(2)]
    pairs = [(login('admin'), first), (login('admin'), second)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda item: action(item[0], item[1], 'post').status_code, pairs))
    assert sorted(codes) == [200, 409]
    assert quantity(client, 1) == 5 and quantity(client, reserve(client)) == 12


def test_inventory_adjusts_only_the_difference_and_keeps_audit(admin):
    client, _ = admin
    doc = create(admin, 'count', [{'product_id': 1, 'quantity': 16}, {'product_id': 2, 'quantity': 44},
                                  {'product_id': 10, 'quantity': 0}], note='Контрольний підрахунок')
    assert [row['difference'] for row in doc['items']] == [-1, 2, 0]
    assert quantity(client, 1) == 17
    posted = action(admin, submit(admin, doc), 'post')
    assert posted.status_code == 200, posted.json
    assert [row['type'] for row in posted.json['movements']] == ['adjustment_out', 'adjustment_in']
    assert [row['delta'] for row in posted.json['movements']] == [-1, 2]
    assert quantity(client, 1) == 16 and quantity(client, 1, product=2) == 44


def test_inventory_rejects_old_count_even_if_quantity_has_returned(admin):
    client, headers = admin
    doc = submit(admin, create(admin, 'count', [{'product_id': 1, 'quantity': 15}], note='Ревізія'))
    for kind in ('receipt', 'writeoff'):
        assert client.post('/api/stock/'+kind, json={'product_id': 1, 'quantity': 1}, headers=headers).status_code == 201
    response = action(admin, doc, 'post')
    assert response.status_code == 409 and 'після підрахунку' in response.json['error']
    assert quantity(client, 1) == 17
    assert client.get(f'/api/documents/{doc["id"]}').json['movements'] == []


def test_inventory_form_rejects_stock_changed_before_first_save(admin):
    client, headers = admin
    version = client.get('/api/products?warehouse_id=1&q=SSD-480').json['items'][0]['stock_revision']
    assert client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 1}, headers=headers).status_code == 201
    request = {'kind':'count','warehouse_id':1,'items':[{'product_id':1,'quantity':17,'stock_revision':version}], 'note':'Фізичний підрахунок'}
    assert client.post('/api/documents', json=request, headers=headers).status_code == 409
    assert quantity(client, 1) == 18
    assert client.get('/api/documents?kind=count').json['total'] == 0


def test_reversal_keeps_original_and_restores_balances_once(admin):
    client, _ = admin
    posted = action(admin, submit(admin, create(admin)), 'post').json
    unavailable = action(admin, posted, 'reverse', note='')
    assert unavailable.status_code == 400
    assert quantity(client, 1) == 12
    result = action(admin, posted, 'reverse', note='Коригування навчального переміщення')
    assert result.status_code == 201, result.json
    assert result.json['original_id'] == posted['id']
    assert [r['delta'] for r in result.json['movements']] == [-5, 5]
    assert action(admin, posted, 'reverse', note='Повтор').json['id'] == result.json['id']
    original = client.get(f'/api/documents/{posted["id"]}').json
    assert original['status'] == 'reversed' and len(original['movements']) == 2
    assert original['reversal_id'] == result.json['id']
    assert quantity(client, 1) == 17 and quantity(client, reserve(client)) == 0


def test_failed_reversal_does_not_change_balances_or_original_state(admin):
    client, headers = admin
    destination = reserve(client)
    posted = action(admin, submit(admin, create(admin)), 'post').json
    assert client.post('/api/stock/writeoff', json={'product_id': 1, 'quantity': 5, 'warehouse_id': destination}, headers=headers).status_code == 201
    response = action(admin, posted, 'reverse', note='Товар уже відсутній')
    assert response.status_code == 409
    assert quantity(client, 1) == 12 and quantity(client, destination) == 0
    assert client.get(f'/api/documents/{posted["id"]}').json['status'] == 'posted'
    assert client.get('/api/documents?kind=reversal').json['total'] == 0


def test_edit_revision_cancel_and_roles(admin, login):
    client, headers = admin
    keeper = login('keeper')
    manager, manager_headers = login('manager')
    draft = create(keeper)
    draft_endpoint = f'/api/documents/{draft["id"]}'
    new_data = dict(warehouse_id=1, destination_id=reserve(client), revision=draft['revision'],
                    items=[{'product_id': 1, 'quantity': 7}], note='Змінений документ')
    assert manager.get(draft_endpoint).status_code == 200
    assert manager.put(draft_endpoint, headers=manager_headers, json=new_data).status_code == 403
    edit = keeper[0].put(draft_endpoint, headers=keeper[1], json=new_data)
    assert edit.status_code == 200 and edit.json['items'][0]['quantity'] == 7
    assert client.put(draft_endpoint, headers=headers, json=new_data).status_code == 409
    cancelled = action(keeper, edit.json, 'cancel')
    assert cancelled.status_code == 200 and cancelled.json['status'] == 'cancelled'
    assert quantity(client, 1) == 17
    assert manager.post('/api/warehouses', headers=manager_headers, json={'code':'X','name':'Інший'}).status_code == 403
    assert manager.get('/api/data/backup').status_code == 403


def test_archiving_considers_all_warehouses(admin):
    client, headers = admin
    doc = create(admin, items=[{'product_id': 1, 'quantity': 17}])
    assert action(admin, submit(admin, doc), 'post').status_code == 200
    assert quantity(client, 1) == 0 and quantity(client, reserve(client)) == 17
    assert client.delete('/api/products/1', headers=headers).status_code == 409


def test_csv_preview_import_and_exports_are_consistent(admin):
    client, headers = admin
    heading = 'sku;name;category;price;min_stock;unit\n'
    valid = heading + 'NEW-1;Тестова позиція;Накопичувачі;12,50;3;шт.\nNEW-2;=Позначка;Накопичувачі;20;2;шт.'
    invalid = valid + '\nSSD-480;Дублікат;Накопичувачі;30;2;шт.'
    preview = client.post('/api/data/catalog/preview', json={'csv': invalid}, headers=headers)
    assert preview.status_code == 200 and preview.json['valid'] == 2 and preview.json['errors'][0]['line'] == 4
    assert client.post('/api/data/catalog/import', json={'csv': invalid}, headers=headers).status_code == 400
    assert client.get('/api/products?q=NEW-1').json['total'] == 0
    assert client.post('/api/data/catalog/preview', json={'csv': valid}, headers=headers).json['errors'] == []
    assert client.get('/api/products?q=NEW-1').json['total'] == 0
    assert client.post('/api/data/catalog/import', json={'csv': valid}, headers=headers).json['imported'] == 2
    assert client.post('/api/data/catalog/import', json={'csv': valid}, headers=headers).status_code == 400
    catalog = client.get('/api/data/catalog.csv')
    catalog_rows = {row['sku']: row for row in csv.DictReader(StringIO(catalog.data.decode('utf-8-sig')), delimiter=';')}
    assert catalog_rows['NEW-1']['price'] == '12.50'
    assert catalog_rows['NEW-2']['name'] == "'=Позначка"
    report = client.get(f'/api/data/stock.csv?warehouse_id={reserve(client)}')
    stock_rows = list(csv.DictReader(StringIO(report.data.decode('utf-8-sig')), delimiter=';'))
    assert all(row['warehouse'] == 'RESERVE' and row['quantity'] == '0' for row in stock_rows)
    journal = client.get('/api/data/history.csv?warehouse_id=1&product_id=1&type=writeoff')
    assert list(csv.DictReader(StringIO(journal.data.decode('utf-8-sig')), delimiter=';'))[0]['delta'] == '-3'


def test_backup_download_restores_stock_and_documents_but_not_sessions(app, admin, tmp_path):
    client, _ = admin
    doc = action(admin, submit(admin, create(admin)), 'post').json
    response = client.get('/api/data/backup')
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    snapshot = tmp_path / 'downloaded.db'
    snapshot.write_bytes(response.data)
    restored = copy_database(snapshot, tmp_path / 'new-database.db')
    with pytest.raises(FileExistsError):
        copy_database(snapshot, restored)
    with closing(sqlite3.connect(restored)) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert connection.execute('SELECT COUNT(*) FROM auth_sessions').fetchone() == (0,)
        assert connection.execute('SELECT COUNT(*) FROM stock_movements WHERE document_id=?', (doc['id'],)).fetchone() == (2,)
        assert connection.execute('SELECT quantity FROM stock WHERE product_id=1 ORDER BY warehouse_id').fetchall() == [(12,), (5,)]
    reopened = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(restored)})
    with reopened.app_context():
        ensure_schema()
    new_client = reopened.test_client()
    login_response = new_client.post('/api/auth/login', json={'email':'admin@easystock.local','password':'DemoStock2026!'})
    assert login_response.status_code == 200
    assert new_client.get(f'/api/documents/{doc["id"]}').json['status'] == 'posted'
    with reopened.app_context():
        db.engine.dispose()


def test_v1_upgrade_preserves_data_and_leaves_pre_upgrade_backup(tmp_path):
    path = tmp_path / 'legacy.db'
    schema = Path(__file__).parent / 'fixtures' / 'schema_v1.sql'
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(schema.read_text(encoding='utf-8'))
        connection.executescript("""
          INSERT INTO users VALUES (1,'Автор','legacy@example.test','hash','admin',1);
          INSERT INTO categories VALUES (1,'Категорія','категорія');
          INSERT INTO products VALUES (1,'OLD-1','Старий товар','старий товар',1,NULL,12000,2,'шт.',0,'2026-01-01');
          INSERT INTO stock VALUES (7,1,23);
          INSERT INTO stock_movements VALUES (9,1,1,NULL,'receipt',23,23,'Збережений рух','2026-01-01');
        """)
        connection.commit()
    upgraded = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(path)})
    with upgraded.app_context():
        backup = ensure_schema()
        assert backup and backup.exists()
        assert ensure_schema() is None
        db.engine.dispose()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute('PRAGMA user_version').fetchone() == (2,)
        assert connection.execute('SELECT id, product_id, warehouse_id, quantity FROM stock').fetchall() == [(7, 1, 1, 23)]
        assert connection.execute('SELECT id, warehouse_id, note, document_id FROM stock_movements').fetchall() == [(9, 1, 'Збережений рух', None)]
        assert connection.execute('PRAGMA foreign_key_check').fetchone() is None
    with closing(sqlite3.connect(backup)) as connection:
        assert connection.execute('SELECT * FROM stock').fetchall() == [(7, 1, 23)]
        assert connection.execute('PRAGMA user_version').fetchone() == (0,)
