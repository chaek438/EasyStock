"""Release regression checks on an isolated database; no live warehouse data."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import event, inspect
from sqlalchemy.exc import OperationalError
from easystock.models import db, Stock, StockMovement, Receipt, StockRequest, User


@pytest.mark.parametrize('kind, quantity, expected_balance', [
    ('receipt', 20, 37), ('writeoff', 3, 14),
])
def test_replayed_stock_request_has_one_effect(app, admin, kind, quantity, expected_balance):
    client, headers = admin
    headers = {**headers, 'Idempotency-Key': 'lab6-lost-response'}
    payload = {'product_id': 1, 'quantity': quantity, 'note': 'Lab6 retry'}
    with app.app_context():
        before = db.session.query(StockMovement).count()
    first = client.post('/api/stock/' + kind, json=payload, headers=headers)
    retry = client.post('/api/stock/' + kind, json=payload, headers=headers)
    assert first.status_code == retry.status_code == 201
    assert client.get('/api/products/1').json['quantity'] == expected_balance
    assert retry.json == first.json
    with app.app_context():
        assert db.session.query(StockMovement).count() == before + 1


@pytest.mark.parametrize('path, payload', [
    ('receipt', {'product_id': 1, 'quantity': 3}),
    ('writeoff', {'product_id': 1, 'quantity': 2}),
])
def test_key_cannot_be_reused_for_different_intent(admin, path, payload):
    client, headers = admin
    headers = {**headers, 'Idempotency-Key': 'one-intent'}
    assert client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 2}, headers=headers).status_code == 201
    assert client.post('/api/stock/' + path, json=payload, headers=headers).status_code == 409
    assert client.get('/api/products/1').json['quantity'] == 19


def test_different_keys_allow_intentional_repeated_operations(admin):
    client, headers = admin
    for key in ['separate-delivery-1', 'separate-delivery-2']:
        assert client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 2},
                           headers={**headers, 'Idempotency-Key': key}).status_code == 201
    assert client.get('/api/products/1').json['quantity'] == 21


def test_request_keys_are_scoped_to_author(login):
    for role in ['admin', 'keeper']:
        client, headers = login(role)
        assert client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 2},
                           headers={**headers, 'Idempotency-Key': 'shared-client-key'}).status_code == 201
    assert client.get('/api/products/1').json['quantity'] == 21


def test_retry_survives_new_session_for_same_author(login):
    payload = {'product_id': 1, 'quantity': 2}
    client, headers = login('keeper')
    first = client.post('/api/stock/receipt', json=payload, headers={**headers, 'Idempotency-Key': 'new-session'})
    client, headers = login('keeper')
    retry = client.post('/api/stock/receipt', json=payload, headers={**headers, 'Idempotency-Key': 'new-session'})
    assert first.status_code == retry.status_code == 201
    assert retry.json == first.json
    assert client.get('/api/products/1').json['quantity'] == 19


@pytest.mark.parametrize('kind, expected_balance', [('receipt', 20), ('writeoff', 14)])
def test_concurrent_duplicate_has_one_effect(app, login, kind, expected_balance):
    sessions = [login('keeper'), login('keeper')]
    with app.app_context():
        before = db.session.query(StockMovement).count()
    def send(pair):
        client, headers = pair
        result = client.post('/api/stock/' + kind, json={'product_id': 1, 'quantity': 3},
                             headers={**headers, 'Idempotency-Key': 'parallel-retry'})
        return result.status_code, result.json
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, sessions))
    assert results[0][0] == results[1][0] == 201
    assert results[0][1] == results[1][1]
    assert sessions[0][0].get('/api/products/1').json['quantity'] == expected_balance
    with app.app_context():
        assert db.session.query(StockMovement).count() == before + 1
        assert db.session.query(StockRequest).count() == 1


def test_failed_transaction_does_not_cache_success(app, admin):
    client, headers = admin
    headers = {**headers, 'Idempotency-Key': 'retry-after-db-failure'}
    payload = {'product_id': 1, 'quantity': 2}
    with app.app_context():
        before = db.session.query(Receipt).count()
    def fail(*args):
        raise OperationalError('injected-test-failure', {}, Exception('unavailable'))
    event.listen(StockMovement, 'before_insert', fail)
    try:
        failed = client.post('/api/stock/receipt', json=payload, headers=headers)
        assert failed.status_code == 503
        assert 'injected-test-failure' not in failed.get_data(as_text=True)
    finally:
        event.remove(StockMovement, 'before_insert', fail)
    assert client.get('/api/products/1').json['quantity'] == 17
    with app.app_context():
        assert db.session.query(StockRequest).count() == 0
        assert db.session.query(Receipt).count() == before
    assert client.post('/api/stock/receipt', json=payload, headers=headers).status_code == 201
    assert client.get('/api/products/1').json['quantity'] == 19


def test_rejected_input_does_not_reserve_key(app, admin):
    client, headers = admin
    headers = {**headers, 'Idempotency-Key': 'corrected-input'}
    assert client.post('/api/stock/writeoff', json={'product_id': 1, 'quantity': 40}, headers=headers).status_code == 409
    with app.app_context():
        assert db.session.query(StockRequest).count() == 0
    assert client.post('/api/stock/writeoff', json={'product_id': 1, 'quantity': 3}, headers=headers).status_code == 201
    assert client.get('/api/products/1').json['quantity'] == 14


def test_replay_still_requires_auth_role_and_csrf(app, admin, login):
    client, headers = admin
    payload = {'product_id': 1, 'quantity': 2}
    key = {'Idempotency-Key': 'no-security-bypass'}
    assert client.post('/api/stock/receipt', json=payload, headers={**headers, **key}).status_code == 201
    assert app.test_client().post('/api/stock/receipt', json=payload, headers=key).status_code == 401
    assert client.post('/api/stock/receipt', json=payload, headers=key).status_code == 403
    manager, csrf = login('manager')
    assert manager.post('/api/stock/receipt', json=payload, headers={**csrf, **key}).status_code == 403
    assert client.get('/api/products/1').json['quantity'] == 19


@pytest.mark.parametrize('key', ['', 'contains space', 'bad/key', 'x' * 129])
def test_invalid_request_key_is_rejected(admin, key):
    client, headers = admin
    response = client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 2},
                           headers={**headers, 'Idempotency-Key': key})
    assert response.status_code == 400
    assert client.get('/api/products/1').json['quantity'] == 17


def test_nonfinite_payload_with_key_is_validation_error(admin):
    client, headers = admin
    response = client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 1, 'price': float('nan')},
                           headers={**headers, 'Idempotency-Key': 'not-finite'})
    assert response.status_code == 400
    assert client.get('/api/products/1').json['quantity'] == 17


@pytest.mark.parametrize('length, status', [(1, 201), (200, 201), (201, 400)])
def test_product_name_boundaries(admin, length, status):
    client, headers = admin
    response = client.post('/api/products', json={'name': 'Т' * length, 'sku': 'BOUNDARY', 'category_id': 1}, headers=headers)
    assert response.status_code == status


@pytest.mark.parametrize('length, status', [(500, 201), (501, 400)])
def test_stock_note_boundaries(admin, length, status):
    client, headers = admin
    response = client.post('/api/stock/receipt', json={'product_id': 1, 'quantity': 1, 'note': 'Н' * length},
                           headers={**headers, 'Idempotency-Key': 'note-boundary'})
    assert response.status_code == status
    assert client.get('/api/products/1').json['quantity'] == (18 if status == 201 else 17)


def test_additive_schema_upgrade_preserves_existing_data(app):
    with app.app_context():
        before = (db.session.query(User).count(), db.session.query(StockMovement).count(),
                  db.session.get(Stock, 1).quantity)
        db.session.remove()
        StockRequest.__table__.drop(db.engine)
        assert 'stock_requests' not in inspect(db.engine).get_table_names()
        db.create_all()  # The same additive schema step used by start.py.
        assert 'stock_requests' in inspect(db.engine).get_table_names()
        after = (db.session.query(User).count(), db.session.query(StockMovement).count(),
                 db.session.get(Stock, 1).quantity)
        assert after == before
