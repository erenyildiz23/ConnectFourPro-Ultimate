#!/usr/bin/env python3
# =============================================================================
# make_itch_zip.py - Connect Four Pro Ultimate
# Unity WebGL build'inden itch.io'ya yuklenecek zip'i uretir
# =============================================================================
"""
Kullanim:
    python scripts/make_itch_zip.py unity/Build/WebGL --server https://SUNUCU [--out itch-webgl.zip]

itch.io yalnizca statik dosya barindirir; oyun sunucusu baska yerde (Render vb.)
calisir. Betik build klasorunun bir kopyasini zip'e yazarken server-config.js'i
verilen sunucu adresiyle yeniden yazar (window.CF4_SERVER_URL; bkz.
unity/Assets/Scripts/Net/ServerConfig.cs). Build klasoru degistirilmez.

Denetimler:
  * Adres: mutlak https://host[:port]; http yalnizca --allow-http ile ve yalnizca
    localhost / 127.x / [::1] icin (yerel deneme). Sonda /,
    kullanici/sifre, yol, sorgu ve # olamaz.
  * Build: kokte index.html ve Build/ klasoru; index.html server-config.js'i yuklemeli
    (eski sablonla alinan build'de adres yok sayilirdi).
  * Sikistirma: .gz/.br dosyalari tarayicinin acabilmesi icin Content-Encoding basligi
    ister; statik sunucunun bunu gonderecegi garanti degildir. Bu yuzden varsayilan
    olarak Decompression Fallback acik build (.unityweb) beklenir; --allow-precompressed
    ile bu denetim atlanir; o zaman .gz dosyalarinin gercekten gzip oldugu denetlenir
    (itch.io Content-Encoding: gzip basligini dosya icerigine bakarak koyar).
  * itch.io HTML5 sinirlari: en fazla 1000 dosya, toplam 500 MB, dosya basina 200 MB,
    yol uzunlugu 240 karakter. Sembolik baglanti kabul edilmez.

Zip'te yollar ileri egik cizgilidir, index.html zip'in kokundedir ve build klasoru
disindan hicbir sey eklenmez. Yalnizca standart kutuphane kullanilir.
"""

import argparse
import ipaddress
import json
import os
import sys
import time
import zipfile
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

CONFIG_NAME = 'server-config.js'
MAX_FILES = 1000
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_PATH_LENGTH = 240
PRECOMPRESSED_SUFFIXES = ('.gz', '.br')
GZIP_MAGIC = b'\x1f\x8b'


class PackError(Exception):
    """Kullaniciya gosterilecek hata (cikis kodu 2)."""


def _is_loopback_host(host: str) -> bool:
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_server_url(url: str, allow_http: bool = False) -> str:
    """Sunucu adresini dogrular ve aynen dondurur; gecersizse PackError."""
    if not isinstance(url, str) or not url.strip():
        raise PackError("Sunucu adresi bos")
    if url != url.strip() or any(c.isspace() for c in url) or any(c in url for c in '"\'\\<>`'):
        raise PackError(f"Sunucu adresinde bosluk veya gecersiz karakter var: {url!r}")
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        raise PackError(f"Sunucu adresi mutlak bir http(s) adresi olmali (https://host): {url}")
    if url[: len(parts.scheme)] != parts.scheme:
        raise PackError(f"Sema kucuk harfle yazilmali: {url}")
    if parts.scheme == 'http' and not allow_http:
        raise PackError("itch.io oyunu https ile sunar; http sunucuya tarayici baglanmaz (mixed content). "
                        "Yerel deneme icin --allow-http")
    if '@' in parts.netloc:
        raise PackError("Sunucu adresinde kullanici adi/sifre olamaz")
    if url.endswith('/'):
        raise PackError(f"Sunucu adresinin sonunda / olmamali: {url.rstrip('/')}")
    if parts.path or parts.query or parts.fragment or '?' in url or '#' in url:
        raise PackError("Sunucu adresi yalnizca https://host[:port] olmali (yol, sorgu, # yok)")
    try:
        port = parts.port
    except ValueError as exc:
        raise PackError(f"Gecersiz port: {url}") from exc
    if not parts.hostname or (port is not None and not 0 < port < 65536):
        raise PackError(f"Gecersiz sunucu adresi: {url}")
    # --allow-http yalnizca yerel deneme icindir: internetteki bir sunucuya sifre duz metin gitmesin
    if parts.scheme == 'http' and not _is_loopback_host(parts.hostname):
        raise PackError(f"http yalnizca localhost / 127.x / [::1] icin kabul edilir; https kullanin: {url}")
    return url


def server_config_js(url: str) -> str:
    """server-config.js icerigi (sablondakiyle ayni bicim)."""
    return ("// Oyun sunucusunun adresi (REST + Socket.IO); scripts/make_itch_zip.py yazdi.\n"
            f"window.CF4_SERVER_URL = {json.dumps(url)};\n")


def collect_files(build_dir: str) -> List[Tuple[str, str]]:
    """(disk yolu, zip'teki yol) listesi; sembolik baglanti ve kok disina cikan yol reddedilir."""
    root = os.path.realpath(build_dir)
    files: List[Tuple[str, str]] = []
    for current, dirs, names in os.walk(root):
        dirs.sort()
        for d in dirs:
            if os.path.islink(os.path.join(current, d)):
                raise PackError(f"Build'de sembolik baglanti var: {os.path.join(current, d)}")
        for name in sorted(names):
            path = os.path.join(current, name)
            if os.path.islink(path):
                raise PackError(f"Build'de sembolik baglanti var: {path}")
            real = os.path.realpath(path)
            if os.path.commonpath([root, real]) != root:
                raise PackError(f"Build klasoru disina cikan dosya: {path}")
            arcname = os.path.relpath(real, root).replace(os.sep, '/')
            if arcname.startswith('../') or arcname.startswith('/') or '/../' in arcname:
                raise PackError(f"Gecersiz yol: {arcname}")
            files.append((real, arcname))
    return files


def check_build(build_dir: str, files: List[Tuple[str, str]], allow_precompressed: bool) -> None:
    names = {arc for _, arc in files}
    if 'index.html' not in names:
        raise PackError(f"{build_dir} kokunde index.html yok (Unity WebGL build klasoru verin)")
    build_files = [arc for arc in names if arc.startswith('Build/')]
    if not any(arc.endswith('.loader.js') for arc in build_files):
        raise PackError(f"{build_dir}/Build/*.loader.js bulunamadi (Unity WebGL build'i degil mi?)")
    with open(os.path.join(build_dir, 'index.html'), encoding='utf-8', errors='replace') as f:
        if CONFIG_NAME not in f.read():
            raise PackError("index.html server-config.js'i yuklemiyor: build eski WebGL sablonuyla alinmis; "
                            "guncel repodan yeniden build alin")
    precompressed = sorted(arc for arc in build_files if arc.lower().endswith(PRECOMPRESSED_SUFFIXES))
    if precompressed and not allow_precompressed:
        raise PackError(
            "Build Decompression Fallback kapali alinmis (" + ", ".join(precompressed[:3]) + "). "
            "Bu dosyalar Content-Encoding basligi gerektirir; statik sunucunun bunu gonderecegi garanti "
            "degildir. itch.io build'ini -cf4DecompressionFallback ile alin (CI'daki itch-webgl artifact'i "
            "boyledir) veya sunucunun basligi gonderdigini dogruladiysaniz --allow-precompressed kullanin.")
    for arc in precompressed:
        if arc.lower().endswith('.gz'):
            with open(os.path.join(build_dir, arc), 'rb') as f:
                if f.read(2) != GZIP_MAGIC:
                    raise PackError(f"{arc} .gz uzantili ama gzip degil: itch.io Content-Encoding basligini "
                                    "icerige bakarak koyar, bu dosya tarayicida acilmaz")
    if len(files) + (CONFIG_NAME not in names) > MAX_FILES:
        raise PackError(f"itch.io en fazla {MAX_FILES} dosya kabul eder ({len(files)} dosya var)")
    total = 0
    for path, arc in files:
        size = os.path.getsize(path)
        total += size
        if size > MAX_FILE_BYTES:
            raise PackError(f"{arc}: {size / 1048576:.0f} MB, itch.io siniri dosya basina 200 MB")
        if len(arc) > MAX_PATH_LENGTH:
            raise PackError(f"Yol cok uzun (>{MAX_PATH_LENGTH}): {arc}")
    if total > MAX_TOTAL_BYTES:
        raise PackError(f"Build {total / 1048576:.0f} MB, itch.io siniri 500 MB")


def make_zip(build_dir: str, server_url: str, out_path: str,
             allow_http: bool = False, allow_precompressed: bool = False) -> List[str]:
    """Zip'i yazar ve icindeki yollari dondurur."""
    url = validate_server_url(server_url, allow_http)
    if not os.path.isdir(build_dir):
        raise PackError(f"Build klasoru yok: {build_dir}")
    root = os.path.realpath(build_dir)
    out_real = os.path.realpath(out_path)
    if os.path.commonpath([root, out_real]) == root:
        raise PackError("Cikti zip'i build klasorunun icinde olamaz")
    files = collect_files(build_dir)
    check_build(build_dir, files, allow_precompressed)

    os.makedirs(os.path.dirname(out_real) or '.', exist_ok=True)
    tmp = out_real + '.tmp'
    written: List[str] = []
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for path, arc in files:
                if arc == CONFIG_NAME:
                    continue
                zf.write(path, arc)
                written.append(arc)
            zf.writestr(zipfile.ZipInfo(CONFIG_NAME, date_time=time.localtime()[:6]),
                        server_config_js(url), compress_type=zipfile.ZIP_DEFLATED)
            written.append(CONFIG_NAME)
        os.replace(tmp, out_real)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Unity WebGL build'inden itch.io zip'i uretir.")
    parser.add_argument('build_dir', help="WebGL build klasoru (index.html'in oldugu yer)")
    parser.add_argument('--server', required=True, help="Oyun sunucusu, ornek: https://connect4.onrender.com")
    parser.add_argument('--out', default='itch-webgl.zip', help="Cikti zip'i (varsayilan: itch-webgl.zip)")
    parser.add_argument('--allow-http', action='store_true', help="http:// sunucuya izin ver (yerel deneme)")
    parser.add_argument('--allow-precompressed', action='store_true',
                        help="Decompression Fallback kapali (.gz/.br) build'i de kabul et")
    args = parser.parse_args(argv)
    try:
        names = make_zip(args.build_dir, args.server, args.out, args.allow_http, args.allow_precompressed)
    except PackError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2
    size = os.path.getsize(args.out)
    print(f"{args.out}: {len(names)} dosya, {size / 1048576:.1f} MB, sunucu {args.server}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
