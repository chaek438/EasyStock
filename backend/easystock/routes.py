from datetime import datetime, timedelta
import re
from flask import Blueprint, jsonify, request, g
from sqlalchemy import and_, func, or_, delete
from werkzeug.security import generate_password_hash
from .models import MAIN_WAREHOUSE_ID, MOVEMENT_TYPES, db, User, Category, Supplier, Product, Stock, StockMovement, AuthSession, now
from .auth import require
from .balances import get_warehouse, lock_writes, snapshot
from .stock_service import movement
from .validation import ApiError, text, integer, cents, email

api = Blueprint('api', __name__)

def body():
    value = request.get_json()
    if not isinstance(value, dict):
        raise ApiError('Очікується JSON-об’єкт.')
    return value

def get(model, identifier):
    value = db.session.get(model, identifier)
    if not value:
        raise ApiError('Запис не знайдено.', 404)
    return value

def paginate(query, serialize=None):
    page = integer(request.args.get('page', 1), 'Сторінка', 1, 100000)
    size = integer(request.args.get('per_page', 25), 'Розмір сторінки', 1, 100)
    count = db.session.scalar(db.select(func.count()).select_from(query.order_by(None).subquery()))
    window = query.limit(size).offset((page - 1) * size)
    items = ([serialize(row) for row in db.session.execute(window).unique()]
             if serialize else [row.public() for row in db.session.scalars(window).unique()])
    return jsonify(items=items, total=count, page=page, per_page=size)

def warehouse_filter():
    return get_warehouse(request.args.get('warehouse_id', MAIN_WAREHOUSE_ID))

def catalog_query(warehouse_id):
    quantity = func.coalesce(Stock.quantity, 0)
    query = db.select(Product, quantity.label('warehouse_quantity'), func.coalesce(Stock.revision, 0).label('stock_revision')).outerjoin(
        Stock, and_(Stock.product_id == Product.id, Stock.warehouse_id == warehouse_id))
    return query.where(Product.archived == False), quantity

@api.get('/products')
@require()
def products():
    query, quantity = catalog_query(warehouse_filter().id)
    search = request.args.get('q', '').strip().casefold()
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.where(or_(Product.name_search.like('%' + escaped + '%', escape='\\'), func.lower(Product.sku).like('%' + escaped + '%', escape='\\')))
    if request.args.get('category_id'):
        query = query.where(Product.category_id == integer(request.args['category_id'], 'Категорія', 1))
    status = request.args.get('status')
    if status == 'low':
        query = query.where(quantity <= Product.min_stock)
    elif status == 'available':
        query = query.where(quantity > Product.min_stock)
    elif status == 'empty':
        query = query.where(quantity == 0)
    return paginate(query.order_by(Product.name_search, Product.id),
                    lambda row: dict(**row[0].public(row[1]), stock_revision=row[2]))

@api.get('/products/<int:identifier>')
@require()
def product_details(identifier):
    warehouse = warehouse_filter()
    product = get(Product, identifier)
    balance, revision = snapshot(identifier, warehouse.id)
    return jsonify(**product.public(balance), warehouse_id=warehouse.id, stock_revision=revision)

def product_fields(product, data):
    product.name = text(data, 'name')
    product.name_search = product.name.casefold()
    product.sku = text(data, 'sku', 50).upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,49}', product.sku):
        raise ApiError('SKU: використовуйте латинські літери, цифри, крапку, дефіс або підкреслення.')
    product.category_id = get(Category, integer(data.get('category_id'), 'Категорія', 1)).id
    supplier_id = data.get('supplier_id')
    product.supplier_id = get(Supplier, integer(supplier_id, 'Постачальник', 1)).id if supplier_id not in (None, '') else None
    product.price_cents = cents(data.get('price', 0))
    product.min_stock = integer(data.get('min_stock', 5), 'Мінімальний залишок')
    product.unit = text(data, 'unit', 20) if data.get('unit') else 'шт.'

@api.post('/products')
@require('admin')
def create_product():
    product = Product()
    product_fields(product, body())
    product.stock = Stock(quantity=0)
    db.session.add(product)
    db.session.commit()
    return jsonify(product.public()), 201

@api.put('/products/<int:identifier>')
@require('admin')
def edit_product(identifier):
    product = get(Product, identifier)
    if product.archived:
        raise ApiError('Архівований товар не можна редагувати.', 409)
    product_fields(product, body())
    db.session.commit()
    return jsonify(product.public())

@api.delete('/products/<int:identifier>')
@require('admin')
def archive_product(identifier):
    lock_writes()
    product = get(Product, identifier)
    quantity = db.session.scalar(db.select(func.coalesce(func.sum(Stock.quantity), 0)).where(Stock.product_id == product.id))
    if quantity:
        raise ApiError('Перед архівацією потрібен нульовий залишок на всіх складах.', 409)
    product.archived = True
    db.session.commit()
    return jsonify(message='Товар архівовано. Історію збережено.')

@api.get('/categories')
@require()
def categories():
    return jsonify(items=[x.public() for x in db.session.scalars(db.select(Category).order_by(Category.name_key))])

@api.post('/categories')
@require('admin')
def create_category():
    name = text(body(), 'name', 100)
    category = Category(name=name, name_key=name.casefold())
    db.session.add(category)
    db.session.commit()
    return jsonify(category.public()), 201

@api.put('/categories/<int:identifier>')
@require('admin')
def edit_category(identifier):
    category = get(Category, identifier)
    category.name = text(body(), 'name', 100)
    category.name_key = category.name.casefold()
    db.session.commit()
    return jsonify(category.public())

@api.delete('/categories/<int:identifier>')
@require('admin')
def delete_category(identifier):
    category = get(Category, identifier)
    if db.session.scalar(db.select(Product.id).where(Product.category_id == identifier).limit(1)):
        raise ApiError('Категорія використовується товарами.', 409)
    db.session.delete(category)
    db.session.commit()
    return jsonify(message='Категорію видалено.')

@api.get('/suppliers')
@require()
def suppliers():
    return jsonify(items=[x.public() for x in db.session.scalars(db.select(Supplier).order_by(Supplier.name))])

@api.post('/suppliers')
@require('admin')
def create_supplier():
    data = body()
    supplier = Supplier(name=text(data, 'name', 150), phone=text(data, 'phone', 40, False), email=email(data, False))
    db.session.add(supplier)
    db.session.commit()
    return jsonify(supplier.public()), 201

@api.put('/suppliers/<int:identifier>')
@require('admin')
def edit_supplier(identifier):
    data = body()
    supplier = get(Supplier, identifier)
    supplier.name, supplier.phone, supplier.email = text(data, 'name', 150), text(data, 'phone', 40, False), email(data, False)
    db.session.commit()
    return jsonify(supplier.public())

@api.delete('/suppliers/<int:identifier>')
@require('admin')
def delete_supplier(identifier):
    db.session.delete(get(Supplier, identifier))
    db.session.commit()
    return jsonify(message='Постачальника видалено.')

@api.post('/stock/receipt')
@require('admin', 'keeper')
def receipt():
    return jsonify(movement(body(), g.user, 'receipt', request.headers.get('Idempotency-Key'))), 201

@api.post('/stock/writeoff')
@require('admin', 'keeper')
def writeoff():
    return jsonify(movement(body(), g.user, 'writeoff', request.headers.get('Idempotency-Key'))), 201

def history_query():
    query = db.select(StockMovement)
    # An omitted warehouse returns the full journal; the UI sends its active warehouse.
    if request.args.get('warehouse_id'):
        query = query.where(StockMovement.warehouse_id == warehouse_filter().id)
    if request.args.get('product_id'):
        query = query.where(StockMovement.product_id == integer(request.args['product_id'], 'Товар', 1))
    if request.args.get('document_id'):
        query = query.where(StockMovement.document_id == integer(request.args['document_id'], 'Документ', 1))
    if request.args.get('type'):
        if request.args['type'] not in MOVEMENT_TYPES:
            raise ApiError('Невідомий тип операції.')
        query = query.where(StockMovement.type == request.args['type'])
    if request.args.get('q'):
        escaped = request.args['q'].strip().casefold().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.join(Product).where(or_(Product.name_search.like('%' + escaped + '%', escape='\\'), func.lower(Product.sku).like('%' + escaped + '%', escape='\\')))
    for key in ('from', 'to'):
        if request.args.get(key):
            try:
                value = datetime.strptime(request.args[key], '%Y-%m-%d')
            except ValueError:
                raise ApiError('Дата має бути у форматі РРРР-ММ-ДД.')
            query = query.where(StockMovement.created_at >= value) if key == 'from' else query.where(StockMovement.created_at < value + timedelta(days=1))
    return query

@api.get('/stock/history')
@require()
def history():
    return paginate(history_query().order_by(StockMovement.created_at.desc(), StockMovement.id.desc()))

@api.get('/dashboard')
@require()
def dashboard():
    warehouse = warehouse_filter()
    query, _ = catalog_query(warehouse.id)
    rows = [(row[0], row[1]) for row in db.session.execute(query).unique()]
    low = sorted([(p, qty) for p, qty in rows if qty <= p.min_stock], key=lambda row: (row[1], row[0].id))
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    summary = []
    for days in range(6, -1, -1):
        day = start - timedelta(days=days)
        totals = dict(db.session.execute(db.select(StockMovement.type, func.sum(StockMovement.quantity))
                     .where(StockMovement.warehouse_id == warehouse.id, StockMovement.created_at >= day,
                            StockMovement.created_at < day + timedelta(days=1)).group_by(StockMovement.type)).all())
        summary.append(dict(date=day.date().isoformat(), receipt=totals.get('receipt', 0), writeoff=totals.get('writeoff', 0)))
    recent = db.session.scalars(db.select(StockMovement).where(StockMovement.warehouse_id == warehouse.id)
                                .order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(5)).all()
    return jsonify(warehouse=warehouse.public(), products=len(rows), units=sum(qty for _, qty in rows),
                   value=sum(qty * p.price_cents for p, qty in rows) / 100,
                   low_count=len(low), low_products=[p.public(qty) for p, qty in low[:5]],
                   recent=[m.public() for m in recent], activity=summary)

@api.get('/users')
@require('admin')
def users():
    return jsonify(items=[u.public() for u in db.session.scalars(db.select(User).order_by(User.id))])

@api.post('/users')
@require('admin')
def create_user():
    data = body()
    role = data.get('role')
    if role not in ('admin', 'keeper', 'manager'):
        raise ApiError('Оберіть коректну роль.')
    password = text(data, 'password', 256)
    if len(password) < 8:
        raise ApiError('Пароль має містити щонайменше 8 символів.')
    user = User(name=text(data, 'name', 100), email=email(data), role=role, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return jsonify(user.public()), 201

@api.put('/users/<int:identifier>')
@require('admin')
def edit_user(identifier):
    data, user = body(), get(User, identifier)
    role, active = data.get('role', user.role), data.get('active', user.active)
    if role not in ('admin', 'keeper', 'manager') or not isinstance(active, bool):
        raise ApiError('Некоректна роль або статус.')
    if user.id == g.user.id and (not active or role != 'admin'):
        raise ApiError('Не можна позбавити себе прав адміністратора.', 409)
    user.role, user.active = role, active
    if 'name' in data:
        user.name = text(data, 'name', 100)
    if 'email' in data:
        user.email = email(data)
    if data.get('password'):
        password = text(data, 'password', 256)
        if len(password) < 8:
            raise ApiError('Пароль має містити щонайменше 8 символів.')
        user.password_hash = generate_password_hash(password)
        db.session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    if not active:
        db.session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.session.commit()
    return jsonify(user.public())
