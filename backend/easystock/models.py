from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, and_

db = SQLAlchemy()
MAIN_WAREHOUSE_ID = 1
MAX_STOCK = 1_000_000_000
INBOUND = ('receipt', 'transfer_in', 'adjustment_in', 'reversal_in')
OUTBOUND = ('writeoff', 'transfer_out', 'adjustment_out', 'reversal_out')
MOVEMENT_TYPES = INBOUND + OUTBOUND

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def timestamp(value):
    return value.isoformat(timespec='seconds') + 'Z'

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("role IN ('admin','keeper','manager')"),)
    def public(self):
        return dict(id=self.id, name=self.name, email=self.email, role=self.role, active=self.active)

class AuthSession(db.Model):
    __tablename__ = 'auth_sessions'
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    csrf = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship(User)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    name_key = db.Column(db.String(100), nullable=False, unique=True)
    def public(self):
        return dict(id=self.id, name=self.name)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(40), nullable=False, default='')
    email = db.Column(db.String(200), nullable=False, default='')
    def public(self):
        return dict(id=self.id, name=self.name, phone=self.phone, email=self.email)

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False, default='')

    def public(self):
        return dict(id=self.id, code=self.code, name=self.name, address=self.address,
                    is_main=self.id == MAIN_WAREHOUSE_ID)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    name_search = db.Column(db.String(200), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=5)
    unit = db.Column(db.String(20), nullable=False, default='шт.')
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    category = db.relationship(Category, lazy='joined')
    supplier = db.relationship(Supplier, lazy='joined')
    # Keep the original relationship for the primary warehouse and old seed/tests.
    stock = db.relationship('Stock', primaryjoin=lambda: and_(
        Product.id == Stock.product_id, Stock.warehouse_id == MAIN_WAREHOUSE_ID),
        uselist=False, lazy='joined', cascade='all, delete-orphan')
    __table_args__ = (CheckConstraint('price_cents >= 0'), CheckConstraint('min_stock >= 0'))
    def public(self, quantity=None):
        if quantity is None:
            quantity = self.stock.quantity if self.stock else 0
        return dict(id=self.id, sku=self.sku, name=self.name, category_id=self.category_id,
                    category=self.category.name, supplier_id=self.supplier_id,
                    supplier=self.supplier.name if self.supplier else None,
                    price=self.price_cents / 100, min_stock=self.min_stock, unit=self.unit,
                    quantity=quantity, low_stock=quantity <= self.min_stock, archived=self.archived)

class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False,
                             default=MAIN_WAREHOUSE_ID, server_default=str(MAIN_WAREHOUSE_ID))
    quantity = db.Column(db.Integer, nullable=False, default=0)
    revision = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    __table_args__ = (
        UniqueConstraint('product_id', 'warehouse_id'),
        Index('ix_stock_warehouse_product', 'warehouse_id', 'product_id'),
        CheckConstraint(f'quantity BETWEEN 0 AND {MAX_STOCK}'),
        CheckConstraint('revision >= 0'),
    )

class StockRequest(db.Model):
    """A committed stock response, keyed by its author and request identifier."""
    __tablename__ = 'stock_requests'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    request_key = db.Column(db.String(128), primary_key=True)
    kind = db.Column(db.String(20), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    response_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (CheckConstraint("kind IN ('receipt','writeoff')"),)

class Receipt(db.Model):
    __tablename__ = 'receipts'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    note = db.Column(db.String(500), nullable=False, default='')
    items = db.relationship('ReceiptItem', cascade='all, delete-orphan')

class ReceiptItem(db.Model):
    __tablename__ = 'receipt_items'
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0'), CheckConstraint('price_cents >= 0'))

class StockDocument(db.Model):
    __tablename__ = 'stock_documents'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='draft')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'), unique=True)
    original_id = db.Column(db.Integer, db.ForeignKey('stock_documents.id'), unique=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    posted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    posted_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    note = db.Column(db.String(500), nullable=False, default='')
    revision = db.Column(db.Integer, nullable=False, default=0)
    warehouse = db.relationship(Warehouse, foreign_keys=[warehouse_id], lazy='joined')
    destination = db.relationship(Warehouse, foreign_keys=[destination_id], lazy='joined')
    supplier = db.relationship(Supplier, lazy='joined')
    author = db.relationship(User, foreign_keys=[created_by_id], lazy='joined')
    posted_by = db.relationship(User, foreign_keys=[posted_by_id], lazy='joined')
    cancelled_by = db.relationship(User, foreign_keys=[cancelled_by_id], lazy='joined')
    lines = db.relationship('StockDocumentLine', cascade='all, delete-orphan', order_by='StockDocumentLine.id')
    __table_args__ = (
        CheckConstraint("kind IN ('receipt','writeoff','transfer','count','reversal')"),
        CheckConstraint("status IN ('draft','review','posted','cancelled','reversed')"),
        CheckConstraint('destination_id IS NULL OR destination_id != warehouse_id'),
        CheckConstraint('revision >= 0'),
        Index('ix_stock_documents_status_date', 'status', 'created_at'),
    )

    def public(self):
        return dict(id=self.id, number=f'СК-{self.id:06d}', kind=self.kind, status=self.status,
                    warehouse_id=self.warehouse_id, warehouse=self.warehouse.name,
                    destination_id=self.destination_id, destination=self.destination.name if self.destination else None,
                    supplier_id=self.supplier_id, supplier=self.supplier.name if self.supplier else None,
                    receipt_id=self.receipt_id, original_id=self.original_id,
                    author=self.author.name, created_by_id=self.created_by_id,
                    posted_by=self.posted_by.name if self.posted_by else None,
                    cancelled_by=self.cancelled_by.name if self.cancelled_by else None,
                    created_at=timestamp(self.created_at),
                    posted_at=timestamp(self.posted_at) if self.posted_at else None,
                    cancelled_at=timestamp(self.cancelled_at) if self.cancelled_at else None,
                    note=self.note, revision=self.revision)

class StockDocumentLine(db.Model):
    __tablename__ = 'stock_document_lines'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('stock_documents.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_cents = db.Column(db.Integer)
    expected_quantity = db.Column(db.Integer)
    expected_revision = db.Column(db.Integer)
    product = db.relationship(Product, lazy='joined')
    __table_args__ = (
        UniqueConstraint('document_id', 'product_id'),
        CheckConstraint(f'quantity BETWEEN 0 AND {MAX_STOCK}'),
        CheckConstraint('price_cents IS NULL OR price_cents >= 0'),
    )

    def public(self):
        return dict(product_id=self.product_id, product=self.product.name, sku=self.product.sku,
                    unit=self.product.unit, quantity=self.quantity,
                    price=None if self.price_cents is None else self.price_cents / 100,
                    expected_quantity=self.expected_quantity,
                    difference=None if self.expected_quantity is None else self.quantity - self.expected_quantity)

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False,
                             default=MAIN_WAREHOUSE_ID, server_default=str(MAIN_WAREHOUSE_ID))
    document_id = db.Column(db.Integer, db.ForeignKey('stock_documents.id'), index=True)
    type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(500), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=now, index=True)
    product = db.relationship(Product, lazy='joined')
    user = db.relationship(User, lazy='joined')
    warehouse = db.relationship(Warehouse, lazy='joined')
    __table_args__ = (CheckConstraint(f'type IN {MOVEMENT_TYPES!r}'), CheckConstraint('quantity > 0'),
                      CheckConstraint('balance_after >= 0'),
                      Index('ix_stock_movements_warehouse_date', 'warehouse_id', 'created_at'))
    def public(self):
        return dict(id=self.id, product_id=self.product_id, product=self.product.name,
                    sku=self.product.sku, type=self.type, quantity=self.quantity,
                    balance_after=self.balance_after, author=self.user.name,
                    created_at=timestamp(self.created_at), note=self.note, receipt_id=self.receipt_id,
                    warehouse_id=self.warehouse_id, warehouse=self.warehouse.name,
                    document_id=self.document_id, delta=self.quantity if self.type in INBOUND else -self.quantity)
