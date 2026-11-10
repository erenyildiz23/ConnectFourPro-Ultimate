# =============================================================================
# MODULE: wsgi.py
# Connect Four Pro - Uretim (gunicorn) giris noktasi
# =============================================================================
"""
`python server.py` Werkzeug gelistirme sunucusunu kullanir. Internete acik
kurulumda sunucu gunicorn ile calistirilir (bkz. Dockerfile, docs/KURULUM.md):

    gunicorn --chdir src -k gthread -w 1 --threads 100 -b 0.0.0.0:5000 wsgi:app

DIKKAT: Oda durumu (server.GAMES) surec belleginde tutulur; bu yuzden TEK
worker (-w 1) zorunludur. Eszamanlilik thread'lerle saglanir; her WebSocket
baglantisi bir thread'i mesgul eder.
"""

import threading

import config
import database as db
import server

log = config.get_logger("wsgi")

_bootstrap_lock = threading.Lock()
_bootstrapped = False


def bootstrap() -> bool:
    """Tablolari kurar ve oda temizligini baslatir; surec basina yalnizca bir kez calisir."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return False
        _bootstrapped = True
    db_ok = db.init_db()
    log.info("CONNECT FOUR PRO SERVER v3.0 (gunicorn)")
    log.info("Veritabani: %s", "bagli" if db_ok else "YOK (sadece misafir modu)")
    server.start_cleanup_thread()
    return True


bootstrap()

app = server.app
