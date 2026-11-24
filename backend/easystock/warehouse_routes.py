"""API for warehouses, verifiable documents and data exchange."""

import re

from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy import and_, func, or_

from . import catalog_csv, document_service
from .auth import require
from .balances import get_warehouse, lock_writes
from .db_backup import backup_stream
from .models import Product, Stock, StockDocument, StockMovement, Warehouse, db, now
from .routes import body, catalog_query, history_query, paginate, warehouse_filter
from .validation import ApiError, integer, text

warehouse_api = Blueprint('warehouse', __name__)


@warehouse_api.get('/warehouses')
@require()
def warehouses():
    summaries = {row.id: row for row in db.session.execute(
        db.select(Warehouse.id, func.count(Product.id).label('positions'),
                  func.coalesce(func.sum(Stock.quantity), 0).label('units'),
                  func.total(Stock.quantity * Product.price_cents).label('value_cents'))
        .outerjoin(Stock, and_(Stock.warehouse_id == Warehouse.id, Stock.quantity > 0))
        .outerjoin(Product, Product.id == Stock.product_id).group_by(Warehouse.id))}
    return jsonify(items=[dict(**warehouse.public(), units=summaries[warehouse.id].units,
                               positions=summaries[warehouse.id].positions,
                               value=summaries[warehouse.id].value_cents / 100)
                          for warehouse in db.session.scalars(db.select(Warehouse).order_by(Warehouse.id))])


@warehouse_api.post('/warehouses')
@require('admin')
def create_warehouse():
    data = body()
    code = text(data, 'code', 20).upper()
    if not re.fullmatch('[A-Z0-9][A-Z0-9_-]{0,19}', code):
        raise ApiError('Код складу: використовуйте латинські літери, цифри, дефіс або підкреслення.')
    lock_writes()
    if db.session.scalar(db.select(Warehouse.id).where(Warehouse.code == code)) is not None:
        raise ApiError('Склад з таким кодом уже існує.', 409)
    warehouse = Warehouse(code=code, name=text(data, 'name', 100), address=text(data, 'address', 200, False))
    db.session.add(warehouse)
    db.session.commit()
    return jsonify(warehouse.public()), 201


@warehouse_api.put('/warehouses/<int:identifier>')
@require('admin')
def edit_warehouse(identifier):
    warehouse, data = get_warehouse(identifier), body()
    warehouse.name = text(data, 'name', 100)
    warehouse.address = text(data, 'address', 200, False)
    db.session.commit()
    return jsonify(warehouse.public())


@warehouse_api.get('/documents')
@require()
def documents():
    query = db.select(StockDocument)
    if request.args.get('warehouse_id'):
        identifier = warehouse_filter().id
        query = query.where(or_(StockDocument.warehouse_id == identifier, StockDocument.destination_id == identifier))
    if status := request.args.get('status'):
        if status not in document_service.DOCUMENT_STATUSES:
            raise ApiError('Невідомий стан документа.')
        query = query.where(StockDocument.status == status)
    if kind := request.args.get('kind'):
        if kind not in (*document_service.DOCUMENT_KINDS, 'reversal'):
            raise ApiError('Невідомий тип документа.')
        query = query.where(StockDocument.kind == kind)
    if number := request.args.get('number', '').strip().upper():
        identifier = integer(number.removeprefix('СК-'), 'Номер документа', 1)
        query = query.where(StockDocument.id == identifier)
    return paginate(query.order_by(StockDocument.id.desc()))


@warehouse_api.get('/documents/<int:identifier>')
@require()
def document_details(identifier):
    return jsonify(document_service.details(document_service.get_document(identifier)))


@warehouse_api.post('/documents')
@require('admin', 'keeper')
def create_document():
    data = body()
    lock_writes()
    document = document_service.prepare(data, g.user, data.get('kind'))
    db.session.commit()
    return jsonify(document_service.details(document)), 201


@warehouse_api.put('/documents/<int:identifier>')
@require('admin', 'keeper')
def edit_document(identifier):
    data = body()
    lock_writes()
    document = document_service.get_document(identifier)
    document_service.check_owner(document, g.user)
    document_service.check_revision(document, data)
    if document.status != 'draft':
        raise ApiError('Редагувати можна лише чернетку.', 409)
    document_service.prepare(data, g.user, document.kind, document=document)
    db.session.commit()
    return jsonify(document_service.details(document))


@warehouse_api.post('/documents/<int:identifier>/<action>')
@require('admin', 'keeper')
def document_action(identifier, action):
    if action not in ('submit', 'post', 'cancel', 'return'):
        raise ApiError('Дію не знайдено.', 404)
    document = document_service.transition(identifier, action, body(), g.user)
    db.session.commit()
    return jsonify(document_service.details(document))


@warehouse_api.post('/documents/<int:identifier>/reverse')
@require('admin')
def reverse_document(identifier):
    document, created = document_service.reverse(identifier, body(), g.user)
    db.session.commit()
    return jsonify(document_service.details(document)), 201 if created else 200


@warehouse_api.post('/data/catalog/preview')
@warehouse_api.post('/data/catalog/import')
@require('admin')
def import_catalog():
    raw = text(body(), 'csv', 480_000)
    importing = request.path.endswith('/import')
    if importing:
        lock_writes()
    products, errors, count = catalog_csv.analyze(raw)
    if importing and not errors:
        catalog_csv.insert_products(products)
        db.session.commit()
        return jsonify(imported=len(products), message=f'Додано товарів: {len(products)}.'), 201
    return jsonify(total=count, valid=len(products), errors=errors, items=products[:20]), 400 if importing else 200


@warehouse_api.get('/data/catalog-template.csv')
@require('admin')
def catalog_template():
    return catalog_csv.csv_download('easystock-catalog-template.csv', catalog_csv.FIELDS,
                                    [('NEW-001', 'Приклад товару', 'Назва наявної категорії', '0.00', 5, 'шт.')])


@warehouse_api.get('/data/catalog.csv')
@require()
def export_catalog():
    products = db.session.scalars(db.select(Product).where(Product.archived == False).order_by(Product.sku))
    return catalog_csv.csv_download('easystock-catalog.csv', catalog_csv.FIELDS,
                                    ((p.sku, p.name, p.category.name, f'{p.price_cents / 100:.2f}', p.min_stock, p.unit) for p in products))


@warehouse_api.get('/data/stock.csv')
@require()
def export_stock():
    warehouse = warehouse_filter()
    query, _ = catalog_query(warehouse.id)
    return catalog_csv.csv_download('easystock-stock.csv',
                                    ('warehouse', 'sku', 'name', 'unit', 'quantity', 'min_stock', 'value_uah'),
                                    ((warehouse.code, p.sku, p.name, p.unit, qty, p.min_stock, f'{qty * p.price_cents / 100:.2f}')
                                     for p, qty, _ in db.session.execute(query.order_by(Product.sku))))


@warehouse_api.get('/data/history.csv')
@require()
def export_history():
    query = history_query().order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    rows = (row.public() for row in db.session.scalars(query))
    fields = ('created_at', 'warehouse', 'sku', 'type', 'delta', 'balance_after', 'document_id', 'author', 'note')
    return catalog_csv.csv_download('easystock-history.csv', fields, ([row[k] for k in fields] for row in rows))


@warehouse_api.get('/data/backup')
@require('admin')
def download_backup():
    database = db.engine.url.database
    if database in (None, ':memory:'):
        raise ApiError('Резервне копіювання доступне для файлової бази SQLite.', 409)
    try:
        stream = backup_stream(database)
    except (OSError, ValueError) as error:
        raise ApiError('Не вдалося створити перевірену резервну копію.', 503) from error
    response = send_file(stream, mimetype='application/vnd.sqlite3', as_attachment=True,
                         download_name=f'easystock-backup-{now():%Y%m%d-%H%M}.db')
    response.headers['Cache-Control'] = 'no-store'
    return response
