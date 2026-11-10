# =============================================================================
# MODULE: config.py
# Connect Four Pro - Merkezi yapilandirma ve loglama
# =============================================================================
"""
Tum ayarlar ortam degiskenlerinden okunur; koda sifre/anahtar yazilmaz.
Proje kokunde bir `.env` dosyasi varsa (setup betigi olusturur) oradaki
degerler de yuklenir; terminalde ayarlanmis degiskenler her zaman onceliklidir.
Ornek degerler icin `.env.example` dosyasina bakin.

    DATABASE_URL            PostgreSQL baglanti adresi
    SECRET_KEY              Oturum token'larini imzalar (bos ise rastgele uretilir;
                            o zaman sunucu yeniden baslayinca herkes tekrar giris yapar)
    SESSION_MAX_AGE         Oturum token'inin gecerlilik suresi (saniye)
    CONNECT4_HOST / _PORT   Sunucunun dinledigi adres
    CORS_ALLOWED_ORIGINS    Socket.IO'ya tarayicidan baglanabilecek origin'ler (virgulle
                            ayrilmis liste veya `*`). Bos ise sadece sunucunun kendi
                            origin'i (/play); liste verilirse kendi adresinizi de ekleyin
    LOGIN_MAX_FAILURES      Bir kullanici adi icin LOGIN_LOCKOUT_SECONDS icinde izin
    LOGIN_LOCKOUT_SECONDS   verilen hatali giris sayisi; asilirsa /login 429 dondurur
    AUTH_IP_MAX_REQUESTS    Tek IP'den AUTH_IP_WINDOW_SECONDS icinde kabul edilen
    AUTH_IP_WINDOW_SECONDS  /login + /signup istegi (ngrok/proxy arkasinda herkes ayni
                            IP'dir, bu yuzden genis tutulur). 0 = sinir kapali
    CONNECT4_SERVER         Istemcinin baglanacagi sunucu adresi
    LOG_LEVEL               DEBUG, INFO, WARNING, ERROR
"""

import logging
import os
from typing import Dict, List, Optional, Union

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(PROJECT_ROOT, '.env')


def parse_env_file(path: str) -> Dict[str, str]:
    """KEY=VALUE satirlarini okur; bos satir ve # yorumlari atlanir, tirnaklar soyulur."""
    values: Dict[str, str] = {}
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                    value = value[1:-1]
                if key:
                    values[key] = value
    except OSError:
        pass
    return values


def load_env_file(path: str = ENV_FILE) -> None:
    """`.env` degerlerini, ortamda zaten tanimli OLMAYAN degiskenler icin yukler."""
    for key, value in parse_env_file(path).items():
        os.environ.setdefault(key, value)


load_env_file()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def parse_cors_origins(value: Optional[str]) -> Union[None, str, List[str]]:
    """
    CORS_ALLOWED_ORIGINS degerini flask-socketio'nun bekledigi bicime cevirir:
    bos -> None (sadece ayni origin), `*` -> '*' (herkes), aksi halde origin listesi.
    """
    origins = [o.strip().rstrip('/') for o in (value or '').split(',') if o.strip()]
    if not origins:
        return None
    return '*' if '*' in origins else origins


# --- Sunucu ---
SERVER_HOST = os.environ.get("CONNECT4_HOST", "0.0.0.0")
SERVER_PORT = _env_int("CONNECT4_PORT", 5000)
SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24).hex()
# Origin basligi gondermeyen istemciler (pygame, Unity Editor) bundan etkilenmez
CORS_ALLOWED_ORIGINS = parse_cors_origins(os.environ.get("CORS_ALLOWED_ORIGINS"))

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
PASSWORD_MIN_LENGTH = 8      # Sadece kayitta uygulanir; eski kisa sifreler giris yapabilir
PASSWORD_MAX_LENGTH = 128
GUEST_NAME_MAX_LENGTH = USERNAME_MAX_LENGTH + 20
PBKDF2_ITERATIONS = _env_int("PBKDF2_ITERATIONS", 200_000)
SESSION_MAX_AGE = _env_int("SESSION_MAX_AGE", 7 * 24 * 3600)

# Giris/kayit sinirlari (0 = kapali)
LOGIN_MAX_FAILURES = _env_int("LOGIN_MAX_FAILURES", 5)
LOGIN_LOCKOUT_SECONDS = _env_int("LOGIN_LOCKOUT_SECONDS", 300)
AUTH_IP_MAX_REQUESTS = _env_int("AUTH_IP_MAX_REQUESTS", 300)
AUTH_IP_WINDOW_SECONDS = _env_int("AUTH_IP_WINDOW_SECONDS", 60)

# --- Veritabani ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost/connect4")
# psycopg2 havuzu minconn uzerindeki baglantilari iadede KAPATIR; bu yuzden
# havuz sabit boyutludur (min = max). Havuz doluysa istek bos baglanti bekler.
DB_POOL_SIZE = _env_int("DB_POOL_SIZE", 20)
DB_POOL_TIMEOUT = _env_int("DB_POOL_TIMEOUT", 10)

# --- Unity WebGL istemcisi (sunucu /play adresinden sunar) ---
WEB_BUILD_DIR = os.environ.get("CONNECT4_WEB_BUILD", os.path.join(PROJECT_ROOT, 'unity', 'Build', 'WebGL'))

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
