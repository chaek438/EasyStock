"""Prepare, post and reverse stock documents without editing the movement history."""

from .balances import get_warehouse, lock_writes, record_movement, snapshot
from .models import (INBOUND, MAIN_WAREHOUSE_ID, Product, Receipt, ReceiptItem, StockDocument,
                     StockDocumentLine, StockMovement, Supplier, db, now)
from .validation import ApiError, cents, integer, text

DOCUMENT_KINDS = ('receipt', 'writeoff', 'transfer', 'count')
DOCUMENT_STATUSES = ('draft', 'review', 'posted', 'cancelled', 'reversed')


def prepare(data, author, kind, document=None, quick=False):
    if kind not in DOCUMENT_KINDS:
        raise ApiError('Невідомий тип документа.')
    source = get_warehouse(data.get('warehouse_id', MAIN_WAREHOUSE_ID))
    destination = get_warehouse(data.get('destination_id')) if kind == 'transfer' else None
    if destination and destination.id == source.id:
        raise ApiError('Оберіть два різні склади.')
    raw_lines = ([data] if kind == 'writeoff' else data.get('items', [data])) if quick else data.get('items')
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= 50:
        raise ApiError('Документ має містити від 1 до 50 позицій.')
    note = text(data, 'note', 500, required=kind == 'count')
    lines, seen = [], set()
    for item in raw_lines:
        if not isinstance(item, dict):
            raise ApiError('Некоректна позиція документа.')
        product_id = integer(item.get('product_id'), 'Товар', 1)
        product = db.session.get(Product, product_id)
        if not product or product.archived:
            raise ApiError('Товар не знайдено або його архівовано.', 404)
        if product_id in seen:
            raise ApiError('Один товар можна додати до документа лише один раз.')
        seen.add(product_id)
        quantity = integer(item.get('quantity'), minimum=0 if kind == 'count' else 1)
        line = StockDocumentLine(product=product, quantity=quantity)
        if kind == 'receipt':
            line.price_cents = cents(item['price']) if 'price' in item else product.price_cents
        if kind == 'count':
            line.expected_quantity, line.expected_revision = snapshot(product_id, source.id)
            if 'stock_revision' in item and integer(item['stock_revision'], 'Версія залишку') != line.expected_revision:
                raise ApiError(f'{product.sku}: залишок змінився. Оновіть форму й повторіть підрахунок.', 409)
        lines.append(line)
    supplier_id = None
    if kind == 'receipt':
        supplier_id = data.get('supplier_id')
        if supplier_id not in (None, ''):
            supplier_id = integer(supplier_id, 'Постачальник', 1)
            if not db.session.get(Supplier, supplier_id):
                raise ApiError('Постачальника не знайдено.', 404)
        else:
            supplier_id = lines[0].product.supplier_id
    document = document or StockDocument(kind=kind, created_by_id=author.id)
    document.warehouse_id, document.destination_id = source.id, destination.id if destination else None
    document.supplier_id, document.note = supplier_id, note
    if document.id:
        # Remove prior rows before inserting replacements with the same product IDs.
        document.lines.clear()
        db.session.flush()
        document.revision += 1
    document.lines = lines
    db.session.add(document)
    db.session.flush()
    return document


def apply(document, user):
    """Apply an already validated document. The caller controls commit/rollback."""
    result = []
    if document.kind == 'receipt':
        receipt = Receipt(supplier_id=document.supplier_id, user_id=user.id, note=document.note)
        db.session.add(receipt)
        db.session.flush()
        document.receipt_id = receipt.id
    for line in document.lines:
        product, quantity = line.product, line.quantity
        if document.kind == 'transfer':
            balance = record_movement(document, product, document.warehouse_id, -quantity, 'transfer_out', user)
            record_movement(document, product, document.destination_id, quantity, 'transfer_in', user)
        elif document.kind == 'count':
            delta = quantity - line.expected_quantity
            # Even a zero difference must still be checked against concurrent movements.
            balance = record_movement(document, product, document.warehouse_id, delta,
                                      'adjustment_in' if delta >= 0 else 'adjustment_out', user,
                                      expected_revision=line.expected_revision)
        elif document.kind == 'receipt':
            balance = record_movement(document, product, document.warehouse_id, quantity, 'receipt', user)
            db.session.add(ReceiptItem(receipt_id=document.receipt_id, product_id=product.id,
                                      quantity=quantity, price_cents=line.price_cents))
        else:
            balance = record_movement(document, product, document.warehouse_id, -quantity, 'writeoff', user)
        result.append(dict(product_id=product.id, quantity=balance))
    document.status = 'posted'
    document.posted_by_id = user.id
    document.posted_at = now()
    document.revision += 1
    return result


def get_document(identifier):
    document = db.session.get(StockDocument, identifier)
    if document is None:
        raise ApiError('Документ не знайдено.', 404)
    return document


def check_revision(document, data):
    if document.revision != integer(data.get('revision'), 'Версія документа'):
        raise ApiError('Документ змінився. Оновіть його перед повторною дією.', 409)


def check_owner(document, user):
    if user.role != 'admin' and document.created_by_id != user.id:
        raise ApiError('Редагувати документ може лише його автор або адміністратор.', 403)


def transition(identifier, action, data, user):
    lock_writes()
    document = get_document(identifier)
    if action in ('post', 'return'):
        if user.role != 'admin':
            raise ApiError('Погоджувати та проводити документи може адміністратор.', 403)
        if action == 'post' and document.status == 'posted':
            return document
    else:
        check_owner(document, user)
    check_revision(document, data)
    if action == 'submit' and document.status == 'draft':
        document.status = 'review'
    elif action == 'post' and document.status == 'review':
        apply(document, user)
    elif action == 'return' and document.status == 'review':
        document.status = 'draft'
    elif action == 'cancel' and document.status in ('draft', 'review'):
        document.status = 'cancelled'
        document.cancelled_by_id = user.id
        document.cancelled_at = now()
    else:
        raise ApiError('Ця дія недоступна для поточного стану документа.', 409)
    if action != 'post':
        document.revision += 1
    return document


def reverse(identifier, data, user):
    lock_writes()
    original = get_document(identifier)
    if original.status == 'reversed':
        return db.session.scalar(db.select(StockDocument).where(StockDocument.original_id == original.id)), False
    check_revision(original, data)
    if original.status != 'posted' or original.kind == 'reversal':
        raise ApiError('Сторнувати можна лише проведений первинний документ.', 409)
    rows = db.session.scalars(db.select(StockMovement).where(StockMovement.document_id == original.id)
                              .order_by(StockMovement.id)).all()
    if not rows:
        raise ApiError('Документ не змінював залишки; сторнування не потрібне.', 409)
    document = StockDocument(kind='reversal', status='posted', warehouse_id=original.destination_id or original.warehouse_id,
                             destination_id=original.warehouse_id if original.destination_id else None,
                             original_id=original.id, created_by_id=user.id, posted_by_id=user.id,
                             posted_at=now(), note=text(data, 'note', 500))
    seen = set()
    for row in rows:
        if row.product_id not in seen:
            seen.add(row.product_id)
            document.lines.append(StockDocumentLine(product_id=row.product_id, quantity=row.quantity))
    db.session.add(document)
    db.session.flush()
    # Put deductions first; any insufficient balance rolls back both warehouses.
    for row in sorted(rows, key=lambda row: row.type not in INBOUND):
        delta = -row.quantity if row.type in INBOUND else row.quantity
        record_movement(document, row.product, row.warehouse_id, delta,
                        'reversal_in' if delta > 0 else 'reversal_out', user)
    original.status = 'reversed'
    original.revision += 1
    return document, True


def details(document):
    related = db.session.scalar(db.select(StockDocument.id).where(StockDocument.original_id == document.id))
    rows = db.session.scalars(db.select(StockMovement).where(StockMovement.document_id == document.id)
                              .order_by(StockMovement.id)).all()
    return dict(**document.public(), items=[line.public() for line in document.lines],
                movements=[row.public() for row in rows], reversal_id=related)
