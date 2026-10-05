from sqlalchemy import update, select
from .models import db, Product, Stock, Receipt, ReceiptItem, StockMovement, Supplier
from .validation import ApiError, integer, text, cents

def movement(data, user, kind):
    """One commit for the receipt, all balances, items and audit entries.

    SQL increments prevent lost updates. A conditional SQL decrement checks the
    balance at write time, even when concurrent requests read an older value.
    """
    note = text(data, 'note', 500, False)
    rows = data.get('items') if kind == 'receipt' and 'items' in data else [data]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
        raise ApiError('Надходження має містити від 1 до 50 позицій.')
    validated, seen = [], set()
    for item in rows:
        if not isinstance(item, dict):
            raise ApiError('Некоректна позиція документа.')
        product_id = integer(item.get('product_id'), 'Товар', 1)
        product = db.session.get(Product, product_id)
        if not product or product.archived:
            raise ApiError('Товар не знайдено або його архівовано.', 404)
        if product_id in seen:
            raise ApiError('Один товар можна додати до документа лише один раз.')
        seen.add(product_id)
        quantity = integer(item.get('quantity'), minimum=1)
        price = cents(item.get('price', product.price_cents / 100)) if kind == 'receipt' else product.price_cents
        validated.append((product, quantity, price))
    supplier_id = data.get('supplier_id')
    if supplier_id not in (None, ''):
        supplier_id = integer(supplier_id, 'Постачальник', 1)
        if not db.session.get(Supplier, supplier_id):
            raise ApiError('Постачальника не знайдено.', 404)
    else:
        supplier_id = validated[0][0].supplier_id if kind == 'receipt' else None
    receipt = None
    if kind == 'receipt':
        receipt = Receipt(supplier_id=supplier_id, user_id=user.id, note=note)
        db.session.add(receipt)
        db.session.flush()
    result = []
    for product, quantity, price in validated:
        statement = update(Stock).where(Stock.product_id == product.id, Stock.product_id.in_(select(Product.id).where(Product.archived == False)))
        if kind == 'writeoff':
            statement = statement.where(Stock.quantity >= quantity).values(quantity=Stock.quantity - quantity)
        else:
            statement = statement.where(Stock.quantity <= 1000000000 - quantity).values(quantity=Stock.quantity + quantity)
        if db.session.execute(statement.execution_options(synchronize_session=False)).rowcount != 1:
            balance = db.session.scalar(select(Stock.quantity).where(Stock.product_id == product.id))
            raise ApiError(f'Недостатньо товару: доступно {balance} {product.unit}, запитано {quantity}.' if kind == 'writeoff' else 'Перевищено максимальний залишок.', 409)
        balance = db.session.scalar(select(Stock.quantity).where(Stock.product_id == product.id))
        entry = StockMovement(product_id=product.id, user_id=user.id, type=kind, quantity=quantity, balance_after=balance, note=note, receipt_id=receipt.id if receipt else None)
        db.session.add(entry)
        if receipt:
            db.session.add(ReceiptItem(receipt_id=receipt.id, product_id=product.id, quantity=quantity, price_cents=price))
        result.append(dict(product_id=product.id, quantity=balance))
    db.session.commit()
    return dict(message='Надходження збережено.' if kind == 'receipt' else 'Списання збережено.', items=result, receipt_id=receipt.id if receipt else None)
