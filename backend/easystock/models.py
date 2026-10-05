from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint

db = SQLAlchemy()

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
    stock = db.relationship('Stock', uselist=False, lazy='joined', cascade='all, delete-orphan')
    __table_args__ = (CheckConstraint('price_cents >= 0'), CheckConstraint('min_stock >= 0'))
    def public(self):
        quantity = self.stock.quantity if self.stock else 0
        return dict(id=self.id, sku=self.sku, name=self.name, category_id=self.category_id,
                    category=self.category.name, supplier_id=self.supplier_id,
                    supplier=self.supplier.name if self.supplier else None,
                    price=self.price_cents / 100, min_stock=self.min_stock, unit=self.unit,
                    quantity=quantity, low_stock=quantity <= self.min_stock, archived=self.archived)

class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, unique=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (CheckConstraint('quantity >= 0'),)

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

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipts.id'))
    type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(500), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=now, index=True)
    product = db.relationship(Product, lazy='joined')
    user = db.relationship(User, lazy='joined')
    __table_args__ = (CheckConstraint("type IN ('receipt','writeoff')"), CheckConstraint('quantity > 0'), CheckConstraint('balance_after >= 0'))
    def public(self):
        return dict(id=self.id, product_id=self.product_id, product=self.product.name,
                    sku=self.product.sku, type=self.type, quantity=self.quantity,
                    balance_after=self.balance_after, author=self.user.name,
                    created_at=timestamp(self.created_at), note=self.note, receipt_id=self.receipt_id)
