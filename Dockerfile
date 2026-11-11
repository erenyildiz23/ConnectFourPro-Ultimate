# =============================================================================
# Connect Four Pro - sunucu imaji (Flask-SocketIO + gunicorn)
# =============================================================================
#   docker compose up --build        (PostgreSQL ile birlikte; bkz. docs/KURULUM.md bolum 12)
#
# Unity WebGL build'i git'te tutulmaz. webgl-build/ klasorunde ne varsa imaja
# /app/unity/Build/WebGL olarak girer: CI oraya derlemeyi indirir
# (.github/workflows/docker-image.yml); docker-compose.yml ise yerel
# unity/Build/WebGL klasorunu ayni yere volume olarak baglar.
# Klasor bossa sunucu yine calisir, yalnizca /play/ 404 dondurur.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GUNICORN_THREADS=100

WORKDIR /app

# src/requirements.txt istemci paketlerini de (pygame, requests, websocket-client)
# icerir; sunucu imajinda gereksizdir. Tek kaynak requirements.txt kalsin diye
# "# Istemci" basligindan oncesi (sunucu bolumu) alinir ve gunicorn eklenir.
COPY src/requirements.txt /tmp/requirements.txt
RUN grep -q '^# Istemci' /tmp/requirements.txt \
    && sed '/^# Istemci/,$d' /tmp/requirements.txt > /tmp/requirements-server.txt \
    && grep -q '^Flask-SocketIO' /tmp/requirements-server.txt \
    && pip install -r /tmp/requirements-server.txt gunicorn==27.0.0 \
    && rm /tmp/requirements.txt /tmp/requirements-server.txt

RUN useradd --system --create-home --uid 10001 connect4
COPY --chown=connect4:connect4 src/ /app/src/
COPY --chown=connect4:connect4 webgl-build/ /app/unity/Build/WebGL/
USER connect4

EXPOSE 5000

# PORT: Render gibi platformlar dinlenecek portu bu degiskenle verir (varsayilan 5000)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '5000'), timeout=3)"]

# Oda durumu surec belleginde tutuldugu icin TEK worker zorunludur (-w 1).
# Eszamanlilik thread'lerle saglanir; her WebSocket baglantisi bir thread tutar.
CMD ["sh", "-c", "exec gunicorn --chdir src -k gthread -w 1 --threads ${GUNICORN_THREADS} -b 0.0.0.0:${PORT:-5000} wsgi:app"]
