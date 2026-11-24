"""CSV exchange for the catalog. Import cannot bypass the stock ledger."""

import csv
import re
from io import StringIO

from flask import Response
from sqlalchemy import select

from .models import Category, Product, Stock, db
from .validation import ApiError, cents, integer, text

FIELDS = ('sku', 'name', 'category', 'price', 'min_stock', 'unit')
MAX_ROWS = 500


def analyze(raw):
    raw = raw.removeprefix('\ufeff')
    header = raw.splitlines()[0] if raw.splitlines() else ''
    reader = csv.DictReader(StringIO(raw, newline=''), delimiter=';' if ';' in header else ',', strict=True)
    categories = dict(db.session.execute(select(Category.name_key, Category.id)).all())
    existing = set(db.session.scalars(select(Product.sku)))
    products, errors, seen = [], [], set()
    count = 0
    try:
        if not reader.fieldnames or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
            raise ApiError('Перший рядок CSV має містити: ' + ', '.join(FIELDS) + '.')
        for raw_row in reader:
            if not any(raw_row.values()):
                continue
            count += 1
            if count > MAX_ROWS:
                raise ApiError(f'В одному файлі дозволено до {MAX_ROWS} товарів.')
            row = reader.line_num
            try:
                if None in raw_row or None in raw_row.values():
                    raise ApiError('Кількість стовпців не відповідає заголовку.')
                sku = text(raw_row, 'sku', 50).upper()
                if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,49}', sku):
                    raise ApiError('SKU має містити тільки латинські літери, цифри, крапку, дефіс або підкреслення.')
                if sku in existing or sku in seen:
                    raise ApiError(f'SKU «{sku}» вже є в каталозі або повторюється у файлі.')
                seen.add(sku)
                name = text(raw_row, 'name')
                category = text(raw_row, 'category', 100)
                category_id = categories.get(category.casefold())
                if not category_id:
                    raise ApiError(f'Категорію «{category}» не знайдено. Створіть її в довіднику.')
                price = cents((raw_row['price'].strip() or '0').replace(',', '.'))
                minimum = integer(raw_row['min_stock'].strip() or '5', 'Мінімальний залишок')
                unit = text(raw_row, 'unit', 20, required=False) or 'шт.'
                products.append(dict(sku=sku, name=name, category=category, category_id=category_id,
                                     price_cents=price, min_stock=minimum, unit=unit))
            except ApiError as error:
                errors.append(dict(line=row, message=error.message))
    except csv.Error as error:
        raise ApiError(f'Неправильний формат CSV біля рядка {reader.line_num}.') from error
    if count == 0:
        raise ApiError('У файлі немає товарів.')
    return products, errors, count


def insert_products(products):
    db.session.add_all(Product(sku=p['sku'], name=p['name'], name_search=p['name'].casefold(),
                               category_id=p['category_id'], price_cents=p['price_cents'], min_stock=p['min_stock'],
                               unit=p['unit'], stock=Stock(quantity=0)) for p in products)


def csv_cell(value):
    if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\r', '\n', '\t'))):
        # Prevent textual fields from being interpreted as formulas in spreadsheets.
        return "'" + value
    return value


def csv_download(filename, fields, rows):
    output = StringIO(newline='')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(fields)
    for row in rows:
        writer.writerow(csv_cell(value) for value in row)
    return Response('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store',
    })
