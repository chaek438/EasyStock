"""Upgrade the existing single-warehouse database in one SQLite transaction."""

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.dialects.sqlite import insert

from .db_backup import copy_database
from .models import MAIN_WAREHOUSE_ID, Warehouse, db, now

SCHEMA_VERSION = 2


def ensure_schema():
    with db.engine.connect() as connection:
        if connection.dialect.name != 'sqlite':
            raise RuntimeError('На цьому етапі EasyStock підтримує SQLite.')
        # A failed DDL or data copy must leave the old database usable.
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        version = connection.exec_driver_sql('PRAGMA user_version').scalar_one()
        if version > SCHEMA_VERSION:
            raise RuntimeError('Базу створено новішою версією EasyStock.')
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if '_stock_v1' in tables or '_movements_v1' in tables:
            raise RuntimeError('Знайдено незавершену міграцію. Відновіть резервну копію.')
        stock_legacy = 'stock' in tables and not any(c['name'] == 'warehouse_id' for c in inspector.get_columns('stock'))
        history_legacy = 'stock_movements' in tables and not any(c['name'] == 'warehouse_id' for c in inspector.get_columns('stock_movements'))
        backup = None
        database = db.engine.url.database
        if (stock_legacy or history_legacy) and database not in (None, ':memory:'):
            original = Path(database)
            suffix = now().strftime('%Y%m%d-%H%M%S-%f')
            backup = copy_database(original, original.with_name(f'{original.stem}-before-phase1-{suffix}.db'))
        if stock_legacy:
            connection.exec_driver_sql('ALTER TABLE stock RENAME TO _stock_v1')
        if history_legacy:
            connection.exec_driver_sql('ALTER TABLE stock_movements RENAME TO _movements_v1')
            connection.exec_driver_sql('DROP INDEX IF EXISTS ix_stock_movements_created_at')
            connection.exec_driver_sql('DROP INDEX IF EXISTS ix_stock_movements_product_id')
        db.metadata.create_all(connection)
        connection.execute(insert(Warehouse).values(id=MAIN_WAREHOUSE_ID, code='MAIN', name='Основний склад', address='')
                           .on_conflict_do_nothing(index_elements=['id']))
        if stock_legacy:
            connection.exec_driver_sql('INSERT INTO stock (id, product_id, warehouse_id, quantity, revision) '
                                       'SELECT id, product_id, 1, quantity, 0 FROM _stock_v1')
            connection.exec_driver_sql('DROP TABLE _stock_v1')
        if history_legacy:
            connection.exec_driver_sql('INSERT INTO stock_movements '
                                       '(id, product_id, user_id, receipt_id, warehouse_id, type, quantity, balance_after, note, created_at) '
                                       'SELECT id, product_id, user_id, receipt_id, 1, type, quantity, balance_after, note, created_at '
                                       'FROM _movements_v1')
            connection.exec_driver_sql('DROP TABLE _movements_v1')
        if (stock_legacy or history_legacy) and connection.exec_driver_sql('PRAGMA foreign_key_check').first():
            raise RuntimeError('У даних порушено зв’язки; міграцію скасовано.')
        connection.exec_driver_sql(f'PRAGMA user_version={SCHEMA_VERSION}')
        connection.commit()
    return backup
