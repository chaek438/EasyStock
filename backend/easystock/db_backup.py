"""Consistent SQLite snapshots, including committed writes in the WAL."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile, TemporaryDirectory


def copy_database(source, destination):
    """Create an independent, verified database. Never overwrite a file."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(f'Файл уже існує: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='easystock-backup-') as directory:
        snapshot = Path(directory) / 'snapshot.db'
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(snapshot)) as copy:
                original.backup(copy)
                copy.execute('PRAGMA trusted_schema=OFF')
                copy.execute('PRAGMA journal_mode=DELETE')
                tables = {row[0] for row in copy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                required = {'users', 'auth_sessions', 'products', 'stock', 'stock_movements'}
                if not required.issubset(tables):
                    raise ValueError('Файл не є резервною копією EasyStock.')
                # Existing users can sign in again; old sessions must not be revived.
                copy.execute('DELETE FROM auth_sessions')
                copy.commit()
                if copy.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('Перевірка цілісності SQLite не пройшла.')
                if copy.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Виявлено порушення зв’язків у резервній копії.')
        # Exclusive output creation also prevents accidentally restoring over a live DB.
        with open(destination, 'xb', opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
            try:
                with snapshot.open('rb') as data:
                    copyfileobj(data, output)
                output.flush()
            except BaseException:
                output.close()
                destination.unlink(missing_ok=True)
                raise
    return destination


def backup_stream(database):
    stream = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        with TemporaryDirectory(prefix='easystock-download-') as directory:
            snapshot = copy_database(database, Path(directory) / 'backup.db')
            with snapshot.open('rb') as data:
                copyfileobj(data, stream)
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
