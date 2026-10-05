from datetime import timedelta
from werkzeug.security import generate_password_hash
from .models import db, User, Category, Supplier, Product, Stock, Receipt, ReceiptItem, StockMovement, now

DEMO_PASSWORD = 'DemoStock2026!'

def seed_demo():
    if db.session.scalar(db.select(User.id).limit(1)):
        return False
    users = [User(name=name, email=f'{role}@easystock.local', role=role, password_hash=generate_password_hash(DEMO_PASSWORD)) for role, name in [('admin', 'Сергій Бондаренко'), ('keeper', 'Андрій Коваленко'), ('manager', 'Олена Мельник')]]
    categories = [Category(name=n, name_key=n.casefold()) for n in ['Накопичувачі', 'Периферія', 'Комплектуючі', 'Аксесуари']]
    suppliers = [Supplier(name='TechSupply Україна', phone='+380 44 555 01 20', email='sales@techsupply.example'), Supplier(name='Дистриб’ютор IT-Line', phone='+380 67 555 03 11', email='orders@itline.example')]
    db.session.add_all(users + categories + suppliers)
    db.session.flush()
    data = [('SSD-480', 'SSD Kingston A400 480 GB', 0, 145000, 17, 10), ('MSE-LOG', 'Миша Logitech M185', 1, 65000, 42, 15), ('KBD-K120', 'Клавіатура Logitech K120', 1, 58000, 8, 10), ('RAM-16', 'Оперативна пам’ять Kingston 16 GB', 2, 189000, 24, 8), ('USB-64', 'Флешнакопичувач SanDisk 64 GB', 0, 32000, 6, 10), ('HDMI-2', 'Кабель HDMI 2 м', 3, 21000, 65, 20), ('CPU-I5', 'Процесор Intel Core i5-12400', 2, 589000, 12, 5), ('PAD-XL', 'Килимок для миші XL', 3, 45000, 3, 5), ('SSD-1TB', 'SSD Samsung 980 1 TB', 0, 329000, 21, 8), ('HUB-USBC', 'USB-C хаб 6-в-1', 3, 129000, 0, 5), ('FAN-120', 'Вентилятор Arctic P12', 2, 38000, 32, 10), ('WEB-C920', 'Вебкамера Logitech C920', 1, 285000, 11, 5)]
    for index, (sku, name, category, price, quantity, minimum) in enumerate(data):
        product = Product(sku=sku, name=name, name_search=name.casefold(), category_id=categories[category].id, supplier_id=suppliers[index % 2].id, price_cents=price, min_stock=minimum, unit='шт.', stock=Stock(quantity=quantity))
        db.session.add(product)
        db.session.flush()
        initial = quantity + 3
        moment = now() - timedelta(days=index % 7, hours=2 + index)
        receipt = Receipt(supplier_id=product.supplier_id, user_id=users[1].id, created_at=moment, note='Початкова демонстраційна поставка')
        db.session.add(receipt)
        db.session.flush()
        db.session.add(ReceiptItem(receipt_id=receipt.id, product_id=product.id, quantity=initial, price_cents=price))
        db.session.add(StockMovement(product_id=product.id, user_id=users[1].id, receipt_id=receipt.id, type='receipt', quantity=initial, balance_after=initial, created_at=moment, note=receipt.note))
        db.session.add(StockMovement(product_id=product.id, user_id=users[1].id, type='writeoff', quantity=3, balance_after=quantity, created_at=moment + timedelta(hours=1), note='Демонстраційне списання'))
    db.session.commit()
    return True
