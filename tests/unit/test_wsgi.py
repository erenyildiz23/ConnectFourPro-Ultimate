"""wsgi.py (gunicorn giris noktasi) testleri."""

import importlib
import sys

import pytest


@pytest.fixture
def wsgi_calls(server, monkeypatch):
    """wsgi'yi, veritabanina ve arka plan thread'ine dokunmadan (yeniden) yukler."""
    import database as db

    calls = {'init_db': 0, 'cleanup': 0}

    def fake_init_db():
        calls['init_db'] += 1
        return False

    def fake_cleanup():
        calls['cleanup'] += 1

    monkeypatch.setattr(db, 'init_db', fake_init_db)
    monkeypatch.setattr(server, 'start_cleanup_thread', fake_cleanup)
    sys.modules.pop('wsgi', None)
    module = importlib.import_module('wsgi')
    yield module, calls
    sys.modules.pop('wsgi', None)


def test_import_bootstraps_once_and_exposes_app(server, wsgi_calls):
    module, calls = wsgi_calls
    assert module.app is server.app
    assert calls == {'init_db': 1, 'cleanup': 1}


def test_bootstrap_is_idempotent(wsgi_calls):
    module, calls = wsgi_calls
    assert module.bootstrap() is False
    assert importlib.import_module('wsgi') is module
    assert calls == {'init_db': 1, 'cleanup': 1}


def test_health_served_through_wsgi_app(wsgi_calls):
    module, _ = wsgi_calls
    response = module.app.test_client().get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'
