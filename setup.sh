#!/usr/bin/env bash
# =============================================================================
# Connect Four Pro - tek komutla kurulum (Git Bash, WSL, macOS, Linux)
#
#   ./setup.sh            # calisma zamani paketleri + (istege bagli) veritabani
#   ./setup.sh --dev      # + test ve benchmark paketleri
#   ./setup.sh --no-db    # veritabani adimini atla (sadece AI'ya karsi / misafir)
#
# Windows cmd / PowerShell icin: setup.bat
# =============================================================================
set -e
cd "$(dirname "$0")"

DEV=0
PASS_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --dev) DEV=1 ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) PASS_ARGS+=("$arg") ;;
    esac
done

echo "== Python araniyor"
PY=""
for cand in python3.12 python3.13 python3.11 python3.10 python3 python "py -3.12" "py -3"; do
    if $cand -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "  [!!] Python 3.10 - 3.13 bulunamadi. https://www.python.org/downloads/ adresinden"
    echo "       Python 3.12 kurun (Windows'ta 'Add python.exe to PATH' secenegini isaretleyin)."
    exit 1
fi
echo "  [OK] $($PY --version 2>&1) ($PY)"

echo "== Sanal ortam (venv)"
if [ ! -d venv ]; then
    $PY -m venv venv
    echo "  [OK] venv olusturuldu"
else
    echo "  [OK] venv zaten var"
fi
if [ -x venv/Scripts/python.exe ]; then
    VPY=venv/Scripts/python.exe        # Windows (Git Bash)
else
    VPY=venv/bin/python                # WSL / macOS / Linux
fi

echo "== Paketler yukleniyor (birkac dakika surebilir)"
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r src/requirements.txt
if [ "$DEV" = 1 ]; then
    "$VPY" -m pip install --quiet -r requirements-dev.txt
fi
echo "  [OK] Paketler yuklendi"

"$VPY" scripts/setup_env.py "${PASS_ARGS[@]}"
