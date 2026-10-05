import os
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash
from .models import db
from .validation import ApiError

@event.listens_for(Engine, 'connect')
def sqlite_config(connection, _):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()

def create_app(config=None):
    root = Path(__file__).resolve().parents[2]
    app = Flask(__name__, static_folder=None)
    app.config.update(SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///' + str(root / 'database' / 'easystock.db')),
                      SQLALCHEMY_TRACK_MODIFICATIONS=False, COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1', MAX_CONTENT_LENGTH=1024 * 1024)
    if config:
        app.config.update(config)
    db.init_app(app)
    app.extensions['login_attempts'] = {}
    app.extensions['dummy_hash'] = generate_password_hash('invalid-account-password')
    from .auth import auth
    from .routes import api
    app.register_blueprint(auth, url_prefix='/api')
    app.register_blueprint(api, url_prefix='/api')

    @app.errorhandler(ApiError)
    def api_error(error):
        db.session.rollback()
        return jsonify(error=error.message), error.status

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error='Запис із таким SKU, email або назвою вже існує, або він використовується іншими даними.'), 409

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception('Database operation failed')
        return jsonify(error='База даних тимчасово недоступна. Спробуйте ще раз.'), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error='Некоректний запит.' if error.code == 400 else error.description), error.code

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if response.mimetype == 'text/html':
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        if response.mimetype == 'application/json':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', app='EasyStock')

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path=''):
        if path == 'api' or path.startswith('api/'):
            return jsonify(error='API-маршрут не знайдено.'), 404
        dist = root / 'frontend' / 'dist'
        if not (dist / 'index.html').exists():
            return jsonify(error='Спочатку зберіть frontend: npm run build.'), 503
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, 'index.html')

    @app.cli.command('init-db')
    def init_db():
        """Create empty database tables (no demo accounts)."""
        db.create_all()
        print('Database initialized.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        from .seed import seed_demo
        db.create_all()
        seed_demo()
        print('Demo data ready. admin@easystock.local / DemoStock2026!')

    @app.cli.command('create-admin')
    def create_admin():
        """Interactively create the first admin for an empty database."""
        import click
        from .models import User
        from .validation import email
        db.create_all()
        address = email(dict(email=click.prompt('Email')))
        password = click.prompt('Password (8+ characters)', hide_input=True, confirmation_prompt=True)
        if len(password) < 8:
            raise click.ClickException('Password must have at least 8 characters.')
        db.session.add(User(name=click.prompt('Name'), email=address, role='admin', password_hash=generate_password_hash(password)))
        db.session.commit()
        print('Admin created.')
    return app
