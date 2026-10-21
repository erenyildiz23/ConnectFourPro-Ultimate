#!/usr/bin/env bash
# =============================================================================
# Connect Four Pro - calistirma kisayollari (Git Bash, WSL, macOS, Linux)
#
#   ./run.sh web              sunucu + Unity WebGL oyunu tarayicida (http://localhost:5000/play/)
#   ./run.sh build-web        Unity WebGL build'i al (Unity CLI gerekir, docs/KURULUM.md)
#   ./run.sh client [ADRES]   Python (pygame) istemcisini ac (ADRES: orn. 192.168.1.20:5000)
#   ./run.sh server           sunucuyu baslat (online mod)
#   ./run.sh online           sunucu + iki Python oyuncu penceresi (tek bilgisayarda deneme)
#   ./run.sh test             Python testlerini calistir (once: ./setup.sh --dev)
#   ./run.sh test-cs          C# (Unity'siz) testlerini calistir (.NET 8 SDK gerekir)
#
# Ayarlar proje kokundeki .env dosyasindan okunur (./setup.sh olusturur).
# Windows cmd / PowerShell icin: run.bat
# =============================================================================
cd "$(dirname "$0")"

# Python gerektirmeyen komutlar
case "$1" in
    build-web)
        if ! command -v unity >/dev/null 2>&1; then
            echo "Unity CLI bulunamadi. Kurulum: docs/KURULUM.md -> Unity istemcisi"
            exit 1
        fi
        exec unity build unity --target WebGL \
            --execute-method ConnectFourPro.EditorTools.ProjectSetup.BuildWebGL
        ;;
    test-cs)
        shift
        exec dotnet test tests/csharp "$@"
        ;;
esac

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
    web)
        if [ ! -f unity/Build/WebGL/index.html ] && [ -z "$CONNECT4_WEB_BUILD" ]; then
            echo "Uyari: unity/Build/WebGL bulunamadi. Once build alin: ./run.sh build-web"
        fi
        (cd src && exec "$VPY" server.py) &
        SERVER_PID=$!
        trap 'kill $SERVER_PID 2>/dev/null' EXIT
        if ! "$VPY" scripts/wait_for_server.py; then
            echo "Sunucu baslamadi (yukaridaki hataya bakin)."
            exit 1
        fi
        PORT=$(cd src && "$VPY" -c "import config; print(config.SERVER_PORT)")   # .env'deki port
        URL="http://localhost:$PORT/play/"
        echo "Oyun: $URL  (ayni agdaki cihazlar: http://<bu-bilgisayarin-IP'si>:$PORT/play/)"
        echo "Durdurmak icin Ctrl+C."
        "$VPY" -m webbrowser "$URL" >/dev/null 2>&1
        wait "$SERVER_PID"
        ;;
    test)
        shift
        exec "$VPY" -m pytest "$@"
        ;;
    *)
        sed -n '2,14p' "$0"
        exit 1
        ;;
esac
