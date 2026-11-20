"""wsgi.py (gunicorn giris noktasi) testleri."""

import importlib
import sys

import pytest


class _Calls(dict):
    """Cagri sayilari; .order cagri sirasini tutar (dict karsilastirmasina girmez)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.order = []


@pytest.fixture
def wsgi_calls(server, monkeypatch):
    """wsgi'yi, veritabanina ve arka plan thread'ine dokunmadan (yeniden) yukler."""
    import database as db

    calls = _Calls(init_db=0, cleanup=0, load_arenas=0)
    order = calls.order

    def fake_init_db():
        calls['init_db'] += 1
        order.append('init_db')
        return False

    def fake_load_arenas():
        calls['load_arenas'] += 1
        order.append('load_arenas')

    def fake_cleanup():
        calls['cleanup'] += 1

    monkeypatch.setattr(db, 'init_db', fake_init_db)
    monkeypatch.setattr(server, 'start_cleanup_thread', fake_cleanup)
    monkeypatch.setattr(server, '_load_arenas_from_db', fake_load_arenas)
    sys.modules.pop('wsgi', None)
    module = importlib.import_module('wsgi')
    yield module, calls
    sys.modules.pop('wsgi', None)


def test_import_bootstraps_once_and_exposes_app(server, wsgi_calls):
    module, calls = wsgi_calls
    assert module.app is server.app
    assert calls == {'init_db': 1, 'cleanup': 1, 'load_arenas': 1}


def test_bootstrap_loads_running_arenas_after_init_db(wsgi_calls, server):
    # Uretimde server.main() calismaz: suren turnuvalar acilista (tablolar kurulunca) yuklenir
    module, calls = wsgi_calls
    assert calls['load_arenas'] == 1
    assert calls.order == ['init_db', 'load_arenas']


def test_bootstrap_is_idempotent(wsgi_calls):
    module, calls = wsgi_calls
    assert module.bootstrap() is False
    assert importlib.import_module('wsgi') is module
    assert calls == {'init_db': 1, 'cleanup': 1, 'load_arenas': 1}


def test_health_served_through_wsgi_app(wsgi_calls):
    module, _ = wsgi_calls
    response = module.app.test_client().get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'
