"""run.sh / run.bat icin: yerel sunucu /health cevap verene kadar bekler (en fazla 20 sn)."""
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
import config  # noqa: E402  (.env dosyasini da yukler)

url = f"http://localhost:{config.SERVER_PORT}/health"
deadline = time.time() + 20
while time.time() < deadline:
    try:
        urllib.request.urlopen(url, timeout=1)
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
print(f"Sunucu {url} adresinde cevap vermedi.")
sys.exit(1)
