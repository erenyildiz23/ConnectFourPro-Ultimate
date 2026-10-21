#!/usr/bin/env bash
# =============================================================================
# Connect Four Pro - calistirma kisayollari (Git Bash, WSL, macOS, Linux)
#
#   ./run.sh client [ADRES]   oyunu ac (ADRES: uzak sunucu, orn. 192.168.1.20:5000)
#   ./run.sh server           sunucuyu baslat (online mod)
#   ./run.sh online           sunucu + iki oyuncu penceresi (tek bilgisayarda deneme)
#   ./run.sh test             testleri calistir (once: ./setup.sh --dev)
#
# Ayarlar proje kokundeki .env dosyasindan okunur (./setup.sh olusturur).
# Windows cmd / PowerShell icin: run.bat
# =============================================================================
cd "$(dirname "$0")"

if [ -x venv/Scripts/python.exe ]; then
    VPY="$PWD/venv/Scripts/python.exe"
elif [ -x venv/bin/python ]; then
    VPY="$PWD/venv/bin/python"
else
    echo "Sanal ortam bulunamadi. Once kurulum yapin: ./setup.sh"
    exit 1
fi

case "$1" in
    client)
        shift
        cd src && exec "$VPY" gui_app.py "$@"
        ;;
    server)
        cd src && exec "$VPY" server.py
        ;;
    online)
        (cd src && exec "$VPY" server.py) &
        SERVER_PID=$!
        trap 'kill $SERVER_PID 2>/dev/null' EXIT
        if ! "$VPY" scripts/wait_for_server.py; then
            echo "Sunucu baslamadi (yukaridaki hataya bakin)."
            exit 1
        fi
        echo "Sunucu hazir. Iki oyuncu penceresi aciliyor; ikisi de kapaninca sunucu durur."
        (cd src && exec "$VPY" gui_app.py) &
        CLIENT_PID=$!
        (cd src && "$VPY" gui_app.py)
        wait "$CLIENT_PID"
        ;;
    test)
        shift
        exec "$VPY" -m pytest "$@"
        ;;
    *)
        sed -n '2,11p' "$0"
        exit 1
        ;;
esac
