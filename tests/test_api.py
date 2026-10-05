from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import time
import pytest
from sqlalchemy import event, func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash
from easystock.models import db, User, Product, Stock, StockMovement, Receipt, ReceiptItem, AuthSession, now


def product(client, sku='SSD-480'):
    return client.get('/api/products', query_string={'q': sku}).json['items'][0]

def counts(app):
    with app.app_context():
        return tuple(db.session.scalar(db.select(func.count()).select_from(model)) for model in (StockMovement, Receipt, ReceiptItem))

def test_auth_success_wrong_and_logout(app, admin):
    client, headers = admin
    assert client.get('/api/auth/me').json['user']['role'] == 'admin'
    token = client.get_cookie('easystock_session').value
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/products').status_code == 401
    client.set_cookie('easystock_session', token)
    assert client.get('/api/auth/me').status_code == 401
    assert app.test_client().post('/api/auth/login', json={'email':'admin@easystock.local','password':'wrong'}).status_code == 401


def test_passwords_hashed(app):
    with app.app_context():
        for user in db.session.scalars(db.select(User)):
            assert user.password_hash != 'DemoStock2026!'
            assert check_password_hash(user.password_hash, 'DemoStock2026!')


def test_session_expiry(app, admin):
    client, _ = admin
    with app.app_context():
        session = db.session.scalar(db.select(AuthSession))
        session.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get('/api/auth/me').status_code == 401


def test_unauthenticated_and_csrf(app, admin):
    assert app.test_client().get('/api/products').status_code == 401
    client, _ = admin
    assert client.post('/api/stock/receipt', json={'product_id':1,'quantity':20}).status_code == 403
    assert product(client)['quantity'] == 17

@pytest.mark.parametrize('role', ['keeper','manager'])
def test_admin_only_endpoints(login, role):
    client, headers = login(role)
    for method, path, payload in [('POST','/api/products',{}),('POST','/api/categories',{}),('POST','/api/suppliers',{}),('POST','/api/users',{}),('PUT','/api/products/1',{}),('DELETE','/api/products/1',{})]:
        assert client.open(path, method=method, json=payload, headers=headers).status_code == 403
    assert client.get('/api/users').status_code == 403


def test_manager_cannot_move(login):
    client, headers = login('manager')
    for kind in ['receipt','writeoff']:
        assert client.post('/api/stock/' + kind, json={'product_id':1,'quantity':1}, headers=headers).status_code == 403
    assert client.get('/api/stock/history').status_code == 200


def test_critical_receipt_writeoff_history(app, login):
    client, headers = login('keeper')
    before = counts(app)
    p = product(client)
    response = client.post('/api/stock/receipt', json={'product_id':p['id'],'quantity':20,'note':'Тест поставки'}, headers=headers)
    assert response.status_code == 201
    assert product(client)['quantity'] == 37
    assert response.json['receipt_id']
    history = client.get('/api/stock/history', query_string={'product_id':p['id']}).json['items']
    assert history[0]['type'] == 'receipt' and history[0]['quantity'] == 20
    assert history[0]['balance_after'] == 37 and history[0]['author'] == 'Андрій Коваленко'
    assert history[0]['created_at'].endswith('Z') and history[0]['note'] == 'Тест поставки'
    assert counts(app) == tuple(x+1 for x in before)
    before = counts(app)
    response = client.post('/api/stock/writeoff', json={'product_id':p['id'],'quantity':40}, headers=headers)
    assert response.status_code == 409 and '37' in response.json['error']
    assert product(client)['quantity'] == 37 and counts(app) == before
    assert client.post('/api/stock/writeoff', json={'product_id':p['id'],'quantity':3}, headers=headers).status_code == 201
    assert product(client)['quantity'] == 34

@pytest.mark.parametrize('kind', ['receipt','writeoff'])
@pytest.mark.parametrize('quantity', [0,-1,1.5,True,None,'abc','2.0',1000000001])
def test_invalid_quantity_unchanged(app, admin, kind, quantity):
    client, headers = admin
    before = counts(app)
    assert client.post('/api/stock/' + kind, json={'product_id':1,'quantity':quantity}, headers=headers).status_code == 400
    assert product(client)['quantity'] == 17 and counts(app) == before


def test_multi_item_receipt_and_invalid_rollback(app, admin):
    client, headers = admin
    before = counts(app)
    response = client.post('/api/stock/receipt', json={'items':[{'product_id':1,'quantity':20,'price':1250.50},{'product_id':2,'quantity':5,'price':600}],'supplier_id':1}, headers=headers)
    assert response.status_code == 201 and len(response.json['items']) == 2
    assert product(client)['quantity'] == 37
    assert counts(app) == (before[0]+2,before[1]+1,before[2]+2)
    before = counts(app)
    for rows in [[{'product_id':1,'quantity':5},{'product_id':999,'quantity':1}], [{'product_id':1,'quantity':5},{'product_id':1,'quantity':1}]]:
        assert client.post('/api/stock/receipt', json={'items':rows}, headers=headers).status_code in (400,404)
        assert counts(app) == before and product(client)['quantity'] == 37


def test_failure_between_stock_and_audit_rolls_back(app, admin):
    client, headers = admin
    before = counts(app)
    def fail(*args):
        raise IntegrityError('injected audit failure', {}, Exception('test'))
    event.listen(StockMovement, 'before_insert', fail)
    try:
        response = client.post('/api/stock/receipt', json={'product_id':1,'quantity':20}, headers=headers)
        assert response.status_code == 409
    finally:
        event.remove(StockMovement, 'before_insert', fail)
    assert product(client)['quantity'] == 17 and counts(app) == before


def test_concurrent_writeoffs(app, login):
    sessions = [login('keeper'), login('keeper')]
    before = counts(app)
    def request_writeoff(pair):
        client, headers = pair
        return client.post('/api/stock/writeoff', json={'product_id':1,'quantity':15}, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request_writeoff, sessions))
    assert sorted(results) == [201,409]
    assert product(sessions[0][0])['quantity'] == 2
    assert counts(app)[0] == before[0]+1


def test_search_case_unicode_and_literal_wildcards(admin):
    client, _ = admin
    assert len(client.get('/api/products?q=ssd-480').json['items']) == 1
    assert len(client.get('/api/products',query_string={'q':'КЛАВІАТУРА'}).json['items']) == 1
    assert not client.get('/api/products',query_string={'q':'%'}).json['items']
    result = client.get('/api/products?per_page=5&page=2').json
    assert len(result['items']) == 5 and result['total'] == 12
    assert client.get('/api/products?page=0').status_code == 400
    low = client.get('/api/products?status=low').json['items']
    assert len(low) == 4 and all(p['quantity']<=p['min_stock'] for p in low)


def test_product_crud_duplicate_sku_and_category(app, admin):
    client, headers = admin
    data = dict(name='Тестовий товар',sku='TEST-01',category_id=1,price=12.34,min_stock=3)
    created = client.post('/api/products',json=data,headers=headers)
    assert created.status_code == 201 and created.json['quantity'] == 0
    assert client.post('/api/products',json=data,headers=headers).status_code == 409
    identifier = created.json['id']
    data['price'] = 24.50
    assert client.put(f'/api/products/{identifier}',json=data,headers=headers).json['price'] == 24.5
    assert client.delete('/api/categories/1',headers=headers).status_code == 409
    assert client.delete('/api/products/1',headers=headers).status_code == 409
    assert client.delete(f'/api/products/{identifier}',headers=headers).status_code == 200
    assert not client.get('/api/products?q=TEST-01').json['items']
    assert client.post('/api/stock/receipt',json={'product_id':identifier,'quantity':1},headers=headers).status_code == 404

@pytest.mark.parametrize('price', [-1,'NaN','Infinity',1.234])
def test_invalid_price(admin, price):
    client, headers = admin
    assert client.post('/api/products',json=dict(name='Тест',sku='BAD',category_id=1,price=price),headers=headers).status_code == 400


def test_category_supplier_crud(admin):
    client, headers = admin
    category=client.post('/api/categories',json={'name':'Тестова'},headers=headers)
    assert category.status_code == 201
    assert client.post('/api/categories',json={'name':'тестова'},headers=headers).status_code == 409
    assert client.put('/api/categories/'+str(category.json['id']),json={'name':'Інша'},headers=headers).status_code == 200
    assert client.delete('/api/categories/'+str(category.json['id']),headers=headers).status_code == 200
    supplier=client.post('/api/suppliers',json={'name':'Новий постачальник','email':'test@example.com'},headers=headers)
    assert supplier.status_code == 201
    assert client.delete('/api/suppliers/'+str(supplier.json['id']),headers=headers).status_code == 200
    assert client.delete('/api/suppliers/1',headers=headers).status_code == 409


def test_users_deactivation_and_self_protection(login, admin):
    client, headers = admin
    user=client.post('/api/users',json={'name':'Новий','email':'new@example.com','password':'Password123','role':'manager'},headers=headers)
    assert user.status_code == 201
    assert client.put('/api/users/1',json={'active':False},headers=headers).status_code == 409
    keeper, _ = login('keeper')
    assert client.put('/api/users/2',json={'active':False},headers=headers).status_code == 200
    assert keeper.get('/api/products').status_code == 401
    assert client.post('/api/users',json={'name':'Новий','email':'new@example.com','password':'Password123','role':'manager'},headers=headers).status_code == 409


def test_history_date_filters_empty_errors(admin):
    client, _ = admin
    assert not client.get('/api/stock/history?from=2099-01-01').json['items']
    assert client.get('/api/stock/history?type=unknown').status_code == 400
    assert client.get('/api/stock/history?from=not-a-date').status_code == 400
    assert client.get('/api/stock/history?product_id=1&type=receipt').json['total'] == 1
    assert client.get('/api/stock/history?q=ssd-480').json['total'] == 2


def test_db_constraints(app):
    with app.app_context():
        stock = db.session.scalar(db.select(Stock))
        stock.quantity = -1
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()
        assert db.session.scalar(db.select(Stock.quantity).where(Stock.product_id==1)) == 17
        db.session.add(Stock(product_id=9999,quantity=0))
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()


def test_500_product_p95(app, admin):
    client, _ = admin
    with app.app_context():
        for i in range(488):
            db.session.add(Product(name=f'Тестовий {i:03}',name_search=f'тестовий {i:03}',sku=f'PERF-{i}',category_id=1,price_cents=100,stock=Stock(quantity=1)))
        db.session.commit()
    durations=[]
    for _ in range(30):
        start=time.perf_counter()
        response=client.get('/api/products?per_page=25')
        durations.append(time.perf_counter()-start)
        assert response.status_code == 200 and response.json['total']==500
    p95=sorted(durations)[int(len(durations)*.95)-1]
    print(f'\n500 products / 30 requests: p95={p95:.4f}s')
    assert p95<2


def test_unknown_api_route_does_not_return_spa(app):
    assert app.test_client().get('/api/missing').status_code == 404
