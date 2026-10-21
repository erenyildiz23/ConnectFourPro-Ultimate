#!/usr/bin/env python3
# =============================================================================
# scripts/setup_env.py - Connect Four Pro kurulum yardimcisi
# setup.bat / setup.sh tarafindan sanal ortam kurulduktan sonra calistirilir.
# =============================================================================
"""
Yaptiklari:
  1. Gerekli paketlerin yuklu oldugunu dogrular.
  2. (Istege bagli) PostgreSQL ayarlarini sorar, `.env` dosyasini yazar.
  3. `connect4` ve `connect4_test` veritabanlarini yoksa olusturur, tablolari kurar.
  4. Ozet ve sonraki adimlari yazdirir.

Etkilesimsiz kullanim:
    python scripts/setup_env.py --no-db
    python scripts/setup_env.py --db-url postgresql://postgres:SIFRE@localhost:5432/connect4
"""

import argparse
import getpass
import importlib
import os
import secrets
import sys
from urllib.parse import quote, urlsplit, urlunsplit

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')   # pygame tanitim mesajini gizle
os.environ.setdefault('LOG_LEVEL', 'WARNING')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
ENV_FILE = os.path.join(ROOT, '.env')
REQUIRED = {'flask': 'Flask', 'flask_socketio': 'Flask-SocketIO', 'psycopg2': 'psycopg2-binary',
            'pygame': 'pygame', 'requests': 'requests', 'socketio': 'python-socketio',
            'websocket': 'websocket-client', 'simple_websocket': 'simple-websocket'}


def ok(msg):
    print(f"  [OK]  {msg}")


def warn(msg):
    print(f"  [!!]  {msg}")


def step(msg):
    print(f"\n== {msg}")


def check_packages() -> bool:
    step("Paketler kontrol ediliyor")
    missing = []
    for module, package in REQUIRED.items():
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(package)
    if missing:
        warn("Eksik paketler: " + ", ".join(missing))
        return False
    ok("Tum calisma zamani paketleri yuklu")
    return True


def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"  {prompt}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def ask_yes_no(prompt, default=True):
    answer = ask(f"{prompt} (e/h)", "e" if default else "h")
    return (answer or "").lower().startswith(('e', 'y'))


def build_url(user, password, host, port, dbname):
    auth = quote(user, safe='') + (':' + quote(password, safe='') if password else '')
    return f"postgresql://{auth}@{host}:{port}/{dbname}"


def with_database(url: str, dbname: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, '/' + dbname, parts.query, parts.fragment))


def prompt_database_url():
    print("  PostgreSQL bilgilerini girin (Enter = koseli parantez icindeki varsayilan).")
    user = ask("Kullanici", "postgres")
    try:
        password = getpass.getpass("  Sifre (yazarken gorunmez): ")
    except (EOFError, KeyboardInterrupt):
        password = ""
    host = ask("Sunucu", "localhost")
    port = ask("Port", "5432")
    dbname = ask("Veritabani adi", "connect4")
    return build_url(user, password, host, port, dbname)


def ensure_database(url: str) -> str:
    """Veritabani yoksa olusturur. 'ok' | 'created' | hata mesaji dondurur."""
    import psycopg2
    from psycopg2 import sql

    dbname = urlsplit(url).path.lstrip('/')
    try:
        psycopg2.connect(url, connect_timeout=5).close()
        return 'ok'
    except psycopg2.OperationalError as e:
        if 'does not exist' not in str(e):
            return str(e).strip().splitlines()[0]
    try:
        admin = psycopg2.connect(with_database(url, 'postgres'), connect_timeout=5)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
        admin.close()
        return 'created'
    except Exception as e:
        return str(e).strip().splitlines()[0]


def write_env(values: dict) -> None:
    existing = {}
    if os.path.exists(ENV_FILE):
        sys.path.insert(0, SRC)
        from config import parse_env_file
        existing = parse_env_file(ENV_FILE)
    existing.update(values)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write("# Connect Four Pro yerel ayarlari (setup betigi olusturdu).\n")
        f.write("# Bu dosya git'e eklenmez; sifre icerir, paylasmayin.\n")
        for key, value in existing.items():
            f.write(f"{key}={value}\n")
    ok(f".env yazildi: {ENV_FILE}")


def setup_database(args) -> bool:
    step("Veritabani (online mod icin)")
    if args.no_db:
        print("  Atlandi (--no-db). AI'ya karsi ve misafir modu veritabani olmadan calisir.")
        return False

    existing_url = None
    if os.path.exists(ENV_FILE):
        sys.path.insert(0, SRC)
        from config import parse_env_file
        existing_url = parse_env_file(ENV_FILE).get('DATABASE_URL')

    url = args.db_url
    if not url and existing_url:
        print("  .env dosyasinda kayitli bir veritabani adresi var.")
        if ask_yes_no("Mevcut ayar kullanilsin mi?", True):
            url = existing_url
    if not url:
        if not ask_yes_no("Online mod icin PostgreSQL kurulsun mu? (Kurulu PostgreSQL gerekir)", True):
            print("  Atlandi. Daha sonra tekrar calistirabilirsiniz.")
            return False
        url = prompt_database_url()

    attempts = 0
    while True:
        result = ensure_database(url)
        if result in ('ok', 'created'):
            break
        attempts += 1
        warn(f"Baglanilamadi: {result}")
        if args.db_url or attempts >= 3 or not ask_yes_no("Bilgileri tekrar girmek ister misiniz?", True):
            print("  Veritabani kurulmadi. PostgreSQL'in calistigini ve sifreyi kontrol edin.")
            return False
        url = prompt_database_url()

    dbname = urlsplit(url).path.lstrip('/')
    ok(f"Veritabani '{dbname}' {'olusturuldu' if result == 'created' else 'mevcut'}")

    os.environ['DATABASE_URL'] = url
    sys.path.insert(0, SRC)
    import database
    database.configure(url)
    if database.init_db():
        ok(f"Tablolar hazir ({database.get_user_count()} kayitli kullanici)")
    else:
        warn("Tablolar olusturulamadi")
        return False

    test_url = with_database(url, dbname + '_test')
    test_result = ensure_database(test_url)
    values = {'DATABASE_URL': url}
    if test_result in ('ok', 'created'):
        ok(f"Test veritabani '{dbname}_test' {'olusturuldu' if test_result == 'created' else 'mevcut'}")
        values['TEST_DATABASE_URL'] = test_url
    else:
        warn(f"Test veritabani olusturulamadi ({test_result}); testlerin bir kismi atlanir")

    sys.path.insert(0, SRC)
    from config import parse_env_file
    if not parse_env_file(ENV_FILE).get('SECRET_KEY'):
        values['SECRET_KEY'] = secrets.token_hex(24)
    write_env(values)
    return True


def main():
    parser = argparse.ArgumentParser(description='Connect Four Pro kurulum yardimcisi')
    parser.add_argument('--no-db', action='store_true', help='Veritabani adimini atla')
    parser.add_argument('--db-url', help='PostgreSQL adresi (sorulmadan kullanilir)')
    args = parser.parse_args()

    print("=" * 60)
    print("  CONNECT FOUR PRO - KURULUM")
    print("=" * 60)
    print(f"  Python {sys.version.split()[0]} ({sys.executable})")

    if not check_packages():
        print("\nKurulum tamamlanamadi: paketler eksik.")
        return 1
    db_ready = setup_database(args)

    run = 'run.bat' if os.name == 'nt' else './run.sh'
    step("Kurulum tamamlandi")
    print(f"  AI'ya karsi oyna     : {run} client")
    if db_ready:
        print(f"  Online: sunucu       : {run} server")
        print(f"  Online: hepsi birden : {run} online   (sunucu + iki oyuncu penceresi)")
    else:
        print("  Online mod icin      : PostgreSQL kurup setup betigini tekrar calistirin")
    print(f"  Testler              : {run} test")
    return 0


if __name__ == '__main__':
    sys.exit(main())
