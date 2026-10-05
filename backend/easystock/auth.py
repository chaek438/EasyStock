from functools import wraps
from hashlib import sha256
from datetime import timedelta
import secrets
import time
from flask import Blueprint, request, jsonify, current_app, g
from sqlalchemy import delete
from werkzeug.security import check_password_hash, generate_password_hash
from .models import db, User, AuthSession, now
from .validation import ApiError, email, text

auth = Blueprint('auth', __name__)

def token_hash(token):
    return sha256(token.encode()).hexdigest()

def current_session():
    token = request.cookies.get('easystock_session', '')
    record = db.session.get(AuthSession, token_hash(token)) if token else None
    if not record or record.expires_at <= now() or not record.user.active:
        raise ApiError('Увійдіть у систему.', 401)
    return record

def require(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            record = current_session()
            g.user = record.user
            if roles and g.user.role not in roles:
                raise ApiError('Ваша роль не має дозволу на цю дію.', 403)
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), record.csrf):
                    raise ApiError('Сеанс форми застарів. Оновіть сторінку.', 403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@auth.post('/auth/login')
def login():
    # Local MVP rate limiter; shared storage is needed for multiple API workers.
    attempts = current_app.extensions['login_attempts']
    key = request.remote_addr or 'local'
    recent = [t for t in attempts.get(key, []) if time.monotonic() - t < 60]
    if len(recent) >= 10:
        raise ApiError('Забагато спроб. Спробуйте через хвилину.', 429)
    attempts[key] = recent + [time.monotonic()]
    data = request.get_json()
    if not isinstance(data, dict):
        raise ApiError('Очікується JSON-об’єкт.')
    address = email(data)
    password = text(data, 'password', 256)
    user = db.session.scalar(db.select(User).where(User.email == address))
    # Equal password-hash work for unknown and known accounts.
    password_valid = check_password_hash(user.password_hash if user else current_app.extensions['dummy_hash'], password)
    if not user or not user.active or not password_valid:
        raise ApiError('Неправильна електронна адреса або пароль.', 401)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    previous = request.cookies.get('easystock_session')
    if previous:
        db.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(previous)))
    db.session.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
    db.session.add(AuthSession(token_hash=token_hash(token), user_id=user.id, csrf=csrf, expires_at=now() + timedelta(hours=8)))
    db.session.commit()
    attempts.pop(key, None)
    response = jsonify(user=user.public(), csrf_token=csrf)
    response.set_cookie('easystock_session', token, max_age=28800, httponly=True, samesite='Strict', secure=current_app.config['COOKIE_SECURE'], path='/')
    return response

@auth.get('/auth/me')
@require()
def me():
    return jsonify(user=g.user.public(), csrf_token=current_session().csrf)

@auth.post('/auth/logout')
@require()
def logout():
    db.session.delete(current_session())
    db.session.commit()
    response = jsonify(message='Сеанс завершено.')
    response.delete_cookie('easystock_session', path='/')
    return response
