# =============================================================================
# MODULE: config.py
# Connect Four Pro - Merkezi yapilandirma ve loglama
# =============================================================================
"""
Tum ayarlar ortam degiskenlerinden okunur; koda sifre/anahtar yazilmaz.
Ornek degerler icin proje kokundeki `.env.example` dosyasina bakin.

    DATABASE_URL            PostgreSQL baglanti adresi
    SECRET_KEY              Flask oturum anahtari (bos ise rastgele uretilir)
    CONNECT4_HOST / _PORT   Sunucunun dinledigi adres
    CONNECT4_SERVER         Istemcinin baglanacagi sunucu adresi
    LOG_LEVEL               DEBUG, INFO, WARNING, ERROR
"""

import logging
import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# --- Sunucu ---
SERVER_HOST = os.environ.get("CONNECT4_HOST", "0.0.0.0")
SERVER_PORT = _env_int("CONNECT4_PORT", 5000)
SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24).hex()

# Oda temizligi (saniye)
WAITING_TIMEOUT = _env_int("WAITING_TIMEOUT", 300)      # Rakip bekleyen oda
INACTIVE_TIMEOUT = _env_int("INACTIVE_TIMEOUT", 600)    # Hamle yapilmayan oda
FINISHED_TIMEOUT = _env_int("FINISHED_TIMEOUT", 60)     # Bitmis oyun
CLEANUP_INTERVAL = _env_int("CLEANUP_INTERVAL", 60)

# Baglantisi kopan oyuncunun geri donmesi icin taninan sure (NFR-08)
RECONNECT_GRACE_SECONDS = _env_int("RECONNECT_GRACE_SECONDS", 30)

# --- ELO ---
ELO_K_FACTOR = _env_int("ELO_K_FACTOR", 30)
ELO_MIN_CHANGE = _env_int("ELO_MIN_CHANGE", 10)
DEFAULT_RATING = 1200

# --- Kimlik dogrulama ---
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
PASSWORD_MIN_LENGTH = 3
PASSWORD_MAX_LENGTH = 128
PBKDF2_ITERATIONS = _env_int("PBKDF2_ITERATIONS", 200_000)

# --- Veritabani ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost/connect4")
DB_POOL_MIN = _env_int("DB_POOL_MIN", 1)
DB_POOL_MAX = _env_int("DB_POOL_MAX", 10)

# --- Istemci ---
CLIENT_SERVER_URL = os.environ.get("CONNECT4_SERVER", "http://localhost:5000")
HTTP_TIMEOUT = 5

# --- Loglama ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_logging_configured = False


def get_logger(name: str) -> logging.Logger:
    """Modul icin yapilandirilmis logger dondurur."""
    global _logging_configured
    if not _logging_configured:
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        _logging_configured = True
    return logging.getLogger(name)
