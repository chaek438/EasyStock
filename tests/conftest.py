import pytest
from easystock import create_app
from easystock.models import db
from easystock.seed import seed_demo

@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'test.db')})
    with app.app_context():
        db.create_all()
        seed_demo()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

@pytest.fixture
def login(app):
    def make(role='admin'):
        client = app.test_client()
        result = client.post('/api/auth/login', json={'email': f'{role}@easystock.local', 'password': 'DemoStock2026!'})
        assert result.status_code == 200
        return client, {'X-CSRF-Token': result.json['csrf_token']}
    return make

@pytest.fixture
def admin(login):
    return login('admin')
