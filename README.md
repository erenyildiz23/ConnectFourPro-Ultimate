# 🎮 Connect Four Pro Ultimate

<div align="center">

![Unity](https://img.shields.io/badge/Unity-6%20LTS-black.svg)
![C#](https://img.shields.io/badge/C%23-WebGL-purple.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask--SocketIO-5.3-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)
![Tests](https://img.shields.io/badge/tests-266%20Python%20%2B%20129%20C%23-brightgreen.svg)
![License](https://img.shields.io/badge/License-Academic-yellow.svg)

**Minimax yapay zekası, gerçek zamanlı çok oyunculu mod ve ELO sıralaması içeren Connect Four — tarayıcıda oynanan Unity/C# (WebGL) istemcisiyle.**
Yeditepe Üniversitesi bitirme projesi. Python/Pygame sürümü: [ConnectFourPro](https://github.com/erenyildiz23/ConnectFourPro).

[Özellikler](#-özellikler) • [Kurulum](#-kurulum) • [Kullanım](#-kullanım) • [Testler](#-testler) • [Performans](#-performans) • [Mimari](#-mimari) • [API](#-api)

</div>

---

## ✨ Özellikler

**Oyun**
- **Unity 6 / C# WebGL istemcisi:** kurulum gerektirmez, tarayıcıdan `http://SUNUCU:5000/play/` ile açılır; aynı ağdaki telefon/tablet de bağlanabilir
- Animasyonlu taş düşüşü, kazanan dörtlü vurgusu (Unity ve Pygame istemcilerinde)
- Yapay zekaya karşı 3 zorluk: Kolay (D2), Orta (D4), Zor (D8)
- Online çok oyunculu: oda oluştur / katıl, lobi, seyirci modu
- ELO sıralaması, liderlik tablosu, maç geçmişi
- Bağlantı koparsa 30 sn içinde otomatik geri dönüş; dönülmezse rakip hükmen kazanır
- Maç sonu hamle analizi (her iki oyuncunun hamlelerinin D8 AI ile isabet oranı)
- Misafir modu (hesapsız oynama)

**Teknik**
- Unity istemcisi: oyun motoru ve AI v2 C#'a birebir taşındı; Python motoruyla aynı hamleyi, skoru ve **aynı düğüm sayısını** verdiği altın vektör testleriyle doğrulanır. WebGL'de thread olmadığı için AI araması karelere bölünür (kare donmaz). Socket.IO tarayıcıda resmi `socket.io-client` ile, Editor'de bağımlılıksız bir C# istemcisiyle çalışır — ayrıntı: [unity/README.md](unity/README.md)
- Bitboard oyun motoru: O(1) kazanma kontrolü
- AI v2: negamax + alpha-beta, transpozisyon tablosu, yinelemeli derinleştirme, oyun teorisine dayalı (satır paritesi) tehdit değerlendirmesi, oyun sonunda kesin çözüm, kusursuz çözücüyle doğrulanmış açılış kitabı — ayrıntı ve ölçümler: [docs/AI.md](docs/AI.md)
- Flask-SocketIO sunucusu: sunucu tarafında hamle doğrulama, kilitle korunan oda durumu, otomatik oda temizliği
- PostgreSQL: sabit boyutlu bağlantı havuzu, ELO için transaction, tuzlu PBKDF2 şifre özetleri
- 266 Python testi (birim, entegrasyon, uçtan uca GUI) + 129 C# testi (Unity'siz `dotnet test`), GitHub Actions CI

## 📁 Proje Yapısı

```
ConnectFourPro-Ultimate/
├── unity/                    # Unity 6 / C# WebGL istemcisi (ayrıntı: unity/README.md)
│   └── Assets/
│       ├── Scripts/Core      # Bitboard oyun motoru (game_core.py karşılığı)
│       ├── Scripts/AI        # AI v2 (ai_vs_human.py karşılığı), kareye bölünebilir arama
│       ├── Scripts/Net       # REST, Socket.IO (WebGL köprüsü + C# istemcisi), protokol
│       ├── Scripts/Game      # Uygulama durum makinesi, AI zamanlayıcı
│       ├── Scripts/UI        # uGUI ekranları ve tahta
│       ├── Editor/           # Sahne kurulumu, WebGL ayarları, CLI build
│       ├── Plugins/WebGL/    # SocketBridge.jslib
│       └── WebGLTemplates/   # index.html + socket.io-client
├── src/
│   ├── game_core.py          # Bitboard oyun motoru
│   ├── ai_vs_human.py        # Minimax + Alpha-Beta AI
│   ├── server.py             # Flask-SocketIO sunucusu (REST + WebSocket)
│   ├── database.py           # PostgreSQL veri katmanı
│   ├── gui_app.py            # Pygame istemcisi (Unity istemcisiyle aynı özellikler)
│   ├── network_client.py     # İstemci ağ katmanı
│   ├── config.py             # Ortam değişkenlerinden ayarlar, loglama
│   └── requirements.txt      # Çalışma zamanı bağımlılıkları
├── tests/                    # pytest: unit/, integration/, gui/  +  csharp/ (NUnit, dotnet test)
├── benchmarks/               # Performans ölçümleri, grafikler, RESULTS.md
├── docs/
│   ├── USE_CASES.md          # Use case'ler + gereksinim izlenebilirliği
│   ├── AI.md                 # Oyun teorisi, AI v1 sorunları, v2 tasarımı
│   ├── KURULUM.md            # Adım adım kurulum ve çalıştırma
│   └── diagrams/             # UML (PlantUML + PNG)
├── scripts/                  # Kurulum yardımcıları, export_ai_vectors.py (C# altın vektörleri)
├── setup.bat / setup.sh      # Tek komutla kurulum
├── run.bat / run.sh          # Çalıştırma kısayolları
├── requirements-dev.txt      # Test / benchmark bağımlılıkları
├── pyproject.toml            # pytest, coverage, ruff ayarları
└── .env.example              # Örnek ortam değişkenleri
```

## 🚀 Kurulum

Python 3.12 kurulu olduktan sonra proje klasöründe:

```bash
setup.bat            # Windows (cmd veya çift tık)  |  PowerShell: .\setup.bat
./setup.sh           # Git Bash, WSL, macOS, Linux
```

Betik sanal ortamı ve paketleri kurar, isterseniz PostgreSQL veritabanlarını oluşturup ayarları `.env` dosyasına yazar. Sonra:

```bash
run.bat build-web    # Unity WebGL build'i (bir kez; Unity 6 + CLI gerekir)  |  ./run.sh build-web
run.bat web          # sunucu + oyun tarayıcıda: http://localhost:5000/play/ |  ./run.sh web
run.bat client       # Python/Pygame istemcisi                               |  ./run.sh client
run.bat online       # sunucu + iki Pygame oyuncu penceresi                  |  ./run.sh online
```

Unity kurulumu (Unity CLI, Editor, WebGL modülü), adım adım elle kurulum, ağ üzerinden oynama, EXE ve sorun giderme: **[docs/KURULUM.md](docs/KURULUM.md)**

<details>
<summary>Elle kurulum</summary>

```bash
git clone https://github.com/erenyildiz23/ConnectFourPro-Ultimate.git
cd ConnectFourPro-Ultimate
python -m venv venv
source venv/bin/activate              # Windows cmd: venv\Scripts\activate  |  Git Bash: source venv/Scripts/activate
pip install -r src/requirements.txt   # geliştirme için: pip install -r requirements-dev.txt
```

### Veritabanı (online mod için)

```bash
createdb connect4
```

Ayarlar proje kökündeki `.env` dosyasından (setup betiği oluşturur) veya ortam değişkenlerinden okunur; terminaldeki değişken önceliklidir. Şifreler koda yazılmaz (bkz. [`.env.example`](.env.example)):

```bash
export DATABASE_URL="postgresql://postgres:SIFRE@localhost/connect4"   # Linux/Mac
set DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4        # Windows (cmd)
```

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres@localhost/connect4` | PostgreSQL adresi |
| `SECRET_KEY` | rastgele | Flask oturum anahtarı |
| `CONNECT4_HOST` / `CONNECT4_PORT` | `0.0.0.0` / `5000` | Sunucunun dinlediği adres |
| `CONNECT4_SERVER` | `http://localhost:5000` | İstemcinin bağlanacağı sunucu (Pygame istemcisi ve Unity Editor) |
| `CONNECT4_WEB_BUILD` | `unity/Build/WebGL` | `/play` adresinden sunulan Unity WebGL build klasörü |
| `RECONNECT_GRACE_SECONDS` | `30` | Kopan oyuncunun geri dönme süresi |
| `DB_POOL_SIZE` | `20` | Veritabanı bağlantı havuzu boyutu |
| `LOG_LEVEL` | `INFO` | `DEBUG` istemcide ayrıntılı log açar |

Veritabanı yoksa sunucu yine açılır; kayıt ve giriş 503 döner, misafir modu çalışır.
Eski SHA-256 ile kayıtlı hesaplar giriş yapabilir; şifreleri ilk girişte otomatik olarak PBKDF2'ye yükseltilir.

</details>

## 🎮 Kullanım

```bash
cd src
python server.py                                  # sunucu + Unity oyunu: http://localhost:5000/play/
python gui_app.py                                 # Pygame istemcisi (localhost:5000)
python gui_app.py https://abc123.ngrok-free.app   # uzak sunucuya bağlan
```

Tarayıcı istemcisi oyunu sunan sunucuya bağlanır; başka bir sunucu için `http://localhost:5000/play/?server=http://192.168.1.20:5000`.
AI'ya karşı oynamak için hesap gerekmez: "Misafir Olarak Devam" → "Yapay Zekâya Karşı" (AI tarayıcıda çalışır).

## 🧪 Testler

```bash
pip install -r requirements-dev.txt
export TEST_DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4_test   # AYRI veritabanı
pytest                     # 266 test, ~40 sn
pytest --cov               # kapsam raporu (%88)
pytest tests/unit          # sadece birim testleri (veritabanı gerekmez)
ruff check src tests benchmarks

# C# (Unity istemcisinin Unity'siz kodu; .NET 8 SDK)
dotnet test tests/csharp                                         # 129 test (Socket.IO olan 3 test sunucu yoksa atlanir)
CONNECT4_TEST_SERVER=http://localhost:5000 dotnet test tests/csharp   # + Socket.IO'yu çalışan sunucuya karşı dener
```

| Klasör | İçerik |
|---|---|
| `tests/unit` | Oyun motoru sınır durumları, AI taktikleri, aramanın tam genişlikli referans negamax ve kaba kuvvet oyun sonu çözümüyle karşılaştırılması, şifreleme ve ELO |
| `tests/integration` | PostgreSQL katmanı, REST API, Socket.IO odaları, hamle doğrulama, seyirci, yeniden bağlanma/hükmen yenilgi, temizlik |
| `tests/gui` | Ekransız Pygame istemcileri gerçek sunucuya bağlanıp her use case'i uçtan uca oynar (iki oyuncu + seyirci) |
| `tests/csharp` | C# oyun motoru ve AI (Python testlerinin karşılığı + Python motoruyla birebir altın vektör karşılaştırması), JSON/protokol, gerçek sunucuya karşı Socket.IO |

`TEST_DATABASE_URL` erişilemezse veritabanı gerektiren testler atlanır. Testler bu veritabanını her testte boşaltır.

## 📋 Use Case'ler

17 use case, aktörleri, ana/alternatif akışları ve her birini doğrulayan testler: **[docs/USE_CASES.md](docs/USE_CASES.md)**

![Use case diyagramı](docs/diagrams/use_case_diagram.png)

## 📈 Performans

Ölçüm yöntemi, tüm tablolar ve grafikler: **[benchmarks/RESULTS.md](benchmarks/RESULTS.md)**. Yeniden ölçmek için `benchmarks/README.md`.

## 🏗 Mimari

```
┌────────────────────┐   /play (WebGL build, gzip)  ┌──────────────────────────┐      ┌────────────┐
│ Unity WebGL (C#)   │ ◀─────────────────────────── │  Flask-SocketIO sunucu   │ ───▶ │ PostgreSQL │
│ tarayıcıda         │   REST (HTTP)                │  server.py               │      │ database.py│
│ AI: C# AIEngine    │ ───────────────────────────▶ │  game_core.py (doğrulama)│      └────────────┘
└────────────────────┘   WebSocket (Socket.IO)      │  oda durumu + kilit      │
┌────────────────────┐ ◀──────────────────────────▶ │                          │
│ Pygame istemci     │                              └──────────────────────────┘
│ gui_app.py         │
└────────────────────┘
```

- **Unity istemcisi:** Tüm geri çağrılar Unity ana thread'inde çalışır. AI hamlesi ve hamle analizi `AIRunner` ile her karede ~8 ms'lik dilimlerle yürütülür. Oyun sunucuyla aynı origin'den açıldığı için CORS gerekmez. Ayrıntı: [unity/README.md](unity/README.md)

- **İstemci thread modeli:** Oyun durumunu yalnızca Pygame ana thread'i değiştirir. Socket.IO olayları ve HTTP cevapları bir kuyruğa alınır, AI ve analiz aramaları ayrı thread'lerde çalışır ve iptal edilebilir.
- **Sıra güvenliği:** python-socketio istemcisi her mesajı ayrı thread'de işler, olaylar sırasız gelebilir. İstemci gelen hamleleri hamle geçmişinin uzunluğuna göre uygular, yeni ELO'yu da `game_over` mesajından okur.
- **Sunucu:** Oda durumu tek bir kilitle korunur. Hamleyi yalnızca o taşın sahibi olan bağlantı yapabilir.

## 📡 API

### REST

| Endpoint | Method | Açıklama |
|---|---|---|
| `/signup` | POST | Kayıt (`201`, `400` doğrulama, `409` alınmış, `503` veritabanı yok) |
| `/login` | POST | Giriş (`200`, `401`, `503`) |
| `/user/<username>` | GET | Profil |
| `/user/<username>/games` | GET | Maç geçmişi (`?limit=`) |
| `/leaderboard` | GET | Liderlik tablosu (`?limit=` 1–100) |
| `/active_games` | GET | Lobi |
| `/health` | GET | Sunucu ve veritabanı durumu |
| `/play/` | GET | Unity WebGL istemcisi (`/` buraya yönlenir) |
| `/cleanup` | POST | Eski odaları hemen temizle |

### Socket.IO

| Olay | Yön | Açıklama |
|---|---|---|
| `create_game` / `join_game` / `make_move` / `leave_game` | İstemci → Sunucu | Oda ve oyun işlemleri (`join_game` aynı zamanda yeniden bağlanma) |
| `latency_ping` | İstemci → Sunucu | Gecikme ölçümü (`latency_pong` döner) |
| `game_created` / `game_joined` / `game_start` | Sunucu → İstemci | Oda durumu |
| `move_made` | Sunucu → Oda | Hamle sonrası tam oyun durumu |
| `game_over` | Sunucu → Oda | Kazanan, neden (`normal`/`forfeit`), ELO değişimleri ve yeni puanlar |
| `elo_update` | Sunucu → Oyuncu | Oyuncunun yeni ELO'su |
| `opponent_disconnected` / `opponent_reconnected` | Sunucu → Oda | Bağlantı durumu |
| `game_ended` | Sunucu → Oda | Oda zaman aşımıyla kapatıldı |
| `error` | Sunucu → İstemci | Reddedilen istek (`msg`) |

## 🔧 EXE oluşturma (Windows)

```bat
build_exe.bat
```

## 👨‍💻 Geliştirici

**Eren Yıldız** — eren.yildiz@std.yeditepe.edu.tr — Yeditepe Üniversitesi

## 📄 Lisans

Akademik amaçlı geliştirilmiştir — Yeditepe Üniversitesi Bitirme Projesi.
