"""Warehouse stock invariants shared by documents and the quick forms."""

from sqlalchemy.dialects.sqlite import insert

from .models import MAIN_WAREHOUSE_ID, MAX_STOCK, Product, Stock, StockMovement, Warehouse, db
from .validation import ApiError, integer


def get_warehouse(identifier=MAIN_WAREHOUSE_ID):
    warehouse = db.session.get(Warehouse, integer(identifier, 'Склад', 1))
    if warehouse is None:
        raise ApiError('Склад не знайдено.', 404)
    return warehouse


def lock_writes():
    """Take SQLite's writer lock before reading state for a multi-step action."""
    db.session.execute(db.update(Warehouse).where(Warehouse.id == MAIN_WAREHOUSE_ID)
                       .values(address=Warehouse.address).execution_options(synchronize_session=False))


def snapshot(product_id, warehouse_id):
    row = db.session.execute(db.select(Stock.quantity, Stock.revision)
                             .where(Stock.product_id == product_id, Stock.warehouse_id == warehouse_id)).first()
    return (row.quantity, row.revision) if row else (0, 0)


def change_balance(product, warehouse_id, delta, expected_revision=None):
    if not delta:
        balance, revision = snapshot(product.id, warehouse_id)
        if product.archived:
            raise ApiError('Товар не знайдено або його архівовано.', 404)
        if expected_revision != revision:
            raise ApiError(f'{product.sku}: залишок змінився після підрахунку. Створіть нову інвентаризацію.', 409)
        return balance
    db.session.execute(insert(Stock).values(product_id=product.id, warehouse_id=warehouse_id, quantity=0, revision=0)
                       .on_conflict_do_nothing(index_elements=['product_id', 'warehouse_id']))
    current_product = db.session.scalar(db.select(Product.archived).where(Product.id == product.id))
    if current_product is not False:
        raise ApiError('Товар не знайдено або його архівовано.', 404)
    statement = db.update(Stock).where(Stock.product_id == product.id, Stock.warehouse_id == warehouse_id,
                                       Stock.quantity + delta >= 0, Stock.quantity + delta <= MAX_STOCK)
    if expected_revision is not None:
        statement = statement.where(Stock.revision == expected_revision)
    result = db.session.execute(statement.values(quantity=Stock.quantity + delta, revision=Stock.revision + 1)
                                .execution_options(synchronize_session=False))
    balance, revision = snapshot(product.id, warehouse_id)
    if result.rowcount != 1:
        if expected_revision is not None and expected_revision != revision:
            raise ApiError(f'{product.sku}: залишок змінився після підрахунку. Створіть нову інвентаризацію.', 409)
        if delta < 0:
            raise ApiError(f'Недостатньо товару {product.sku}: доступно {balance} {product.unit}, запитано {-delta}.', 409)
        raise ApiError(f'{product.sku}: перевищено максимальний залишок.', 409)
    return balance


def record_movement(document, product, warehouse_id, delta, movement_type, user, expected_revision=None):
    balance = change_balance(product, warehouse_id, delta, expected_revision)
    if delta:
        db.session.add(StockMovement(product_id=product.id, user_id=user.id, warehouse_id=warehouse_id,
                                     document_id=document.id, receipt_id=document.receipt_id,
                                     type=movement_type, quantity=abs(delta), balance_after=balance,
                                     note=document.note))
    return balance
