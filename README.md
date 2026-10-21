# 🎮 Connect Four Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask--SocketIO-5.3-green.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.5+-red.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)
![Tests](https://img.shields.io/badge/tests-205%20passing-brightgreen.svg)
![License](https://img.shields.io/badge/License-Academic-yellow.svg)

**Minimax yapay zekası, gerçek zamanlı çok oyunculu mod ve ELO sıralaması içeren Connect Four.**
Yeditepe Üniversitesi bitirme projesi.

[Özellikler](#-özellikler) • [Kurulum](#-kurulum) • [Kullanım](#-kullanım) • [Testler](#-testler) • [Performans](#-performans) • [Mimari](#-mimari) • [API](#-api)

</div>

---

## ✨ Özellikler

**Oyun**
- Pygame arayüzü: animasyonlu taş düşüşü, kazanan dörtlü vurgusu
- Yapay zekaya karşı 3 zorluk: Kolay (D2), Orta (D4), Zor (D6)
- Online çok oyunculu: oda oluştur / katıl, lobi, seyirci modu
- ELO sıralaması, liderlik tablosu, maç geçmişi
- Bağlantı koparsa 30 sn içinde otomatik geri dönüş; dönülmezse rakip hükmen kazanır
- Maç sonu hamle analizi (her iki oyuncunun hamlelerinin D6 AI ile isabet oranı)
- Misafir modu (hesapsız oynama)

**Teknik**
- Bitboard oyun motoru: O(1) kazanma kontrolü
- Minimax + Alpha-Beta budama, merkez öncelikli hamle sıralaması, iptal edilebilir arama
- Flask-SocketIO sunucusu: sunucu tarafında hamle doğrulama, kilitle korunan oda durumu, otomatik oda temizliği
- PostgreSQL: sabit boyutlu bağlantı havuzu, ELO için transaction, tuzlu PBKDF2 şifre özetleri
- 205 otomatik test (birim, entegrasyon, uçtan uca GUI), GitHub Actions CI

## 📁 Proje Yapısı

```
ConnectFourPro/
├── src/
│   ├── game_core.py          # Bitboard oyun motoru
│   ├── ai_vs_human.py        # Minimax + Alpha-Beta AI
│   ├── server.py             # Flask-SocketIO sunucusu (REST + WebSocket)
│   ├── database.py           # PostgreSQL veri katmanı
│   ├── gui_app.py            # Pygame istemcisi
│   ├── network_client.py     # İstemci ağ katmanı
│   ├── config.py             # Ortam değişkenlerinden ayarlar, loglama
│   └── requirements.txt      # Çalışma zamanı bağımlılıkları
├── tests/                    # pytest: unit/, integration/, gui/
├── benchmarks/               # Performans ölçümleri, grafikler, RESULTS.md
├── docs/
│   ├── USE_CASES.md          # Use case'ler + gereksinim izlenebilirliği
│   └── diagrams/             # UML (PlantUML + PNG)
├── requirements-dev.txt      # Test / benchmark bağımlılıkları
├── pyproject.toml            # pytest, coverage, ruff ayarları
└── .env.example              # Örnek ortam değişkenleri
```

## 🚀 Kurulum

```bash
git clone https://github.com/erenyildiz23/ConnectFourPro.git
cd ConnectFourPro
python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r src/requirements.txt   # geliştirme için: pip install -r requirements-dev.txt
```

### Veritabanı (online mod için)

```bash
createdb connect4
```

Ayarlar ortam değişkenlerinden okunur; şifreler koda yazılmaz (bkz. [`.env.example`](.env.example)):

```bash
export DATABASE_URL="postgresql://postgres:SIFRE@localhost/connect4"   # Linux/Mac
set DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4        # Windows (cmd)
```

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres@localhost/connect4` | PostgreSQL adresi |
| `SECRET_KEY` | rastgele | Flask oturum anahtarı |
| `CONNECT4_HOST` / `CONNECT4_PORT` | `0.0.0.0` / `5000` | Sunucunun dinlediği adres |
| `CONNECT4_SERVER` | `http://localhost:5000` | İstemcinin bağlanacağı sunucu |
| `RECONNECT_GRACE_SECONDS` | `30` | Kopan oyuncunun geri dönme süresi |
| `DB_POOL_SIZE` | `20` | Veritabanı bağlantı havuzu boyutu |
| `LOG_LEVEL` | `INFO` | `DEBUG` istemcide ayrıntılı log açar |

Veritabanı yoksa sunucu yine açılır; kayıt ve giriş 503 döner, misafir modu çalışır.
Eski SHA-256 ile kayıtlı hesaplar giriş yapabilir; şifreleri ilk girişte otomatik olarak PBKDF2'ye yükseltilir.

## 🎮 Kullanım

```bash
cd src
python server.py                                  # sunucu (online mod için)
python gui_app.py                                 # istemci (localhost:5000)
python gui_app.py https://abc123.ngrok-free.app   # uzak sunucuya bağlan
```

AI'ya karşı oynamak için sunucu gerekmez: "Misafir Olarak Devam" → "Yapay Zekaya Karşı".

## 🧪 Testler

```bash
pip install -r requirements-dev.txt
export TEST_DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4_test   # AYRI veritabanı
pytest                     # 205 test, ~40 sn
pytest --cov               # kapsam raporu (%88)
pytest tests/unit          # sadece birim testleri (veritabanı gerekmez)
ruff check src tests benchmarks
```

| Klasör | İçerik |
|---|---|
| `tests/unit` | Oyun motoru sınır durumları, AI taktikleri, alpha-beta'nın referans uygulamayla düğüm düğüm karşılaştırması, şifreleme ve ELO |
| `tests/integration` | PostgreSQL katmanı, REST API, Socket.IO odaları, hamle doğrulama, seyirci, yeniden bağlanma/hükmen yenilgi, temizlik |
| `tests/gui` | Ekransız Pygame istemcileri gerçek sunucuya bağlanıp her use case'i uçtan uca oynar (iki oyuncu + seyirci) |

`TEST_DATABASE_URL` erişilemezse veritabanı gerektiren testler atlanır. Testler bu veritabanını her testte boşaltır.

## 📋 Use Case'ler

17 use case, aktörleri, ana/alternatif akışları ve her birini doğrulayan testler: **[docs/USE_CASES.md](docs/USE_CASES.md)**

![Use case diyagramı](docs/diagrams/use_case_diagram.png)

## 📈 Performans

Ölçüm yöntemi, tüm tablolar ve grafikler: **[benchmarks/RESULTS.md](benchmarks/RESULTS.md)**. Yeniden ölçmek için `benchmarks/README.md`.

## 🏗 Mimari

```
┌─────────────────┐   REST (HTTP)          ┌──────────────────────────┐      ┌────────────┐
│  Pygame istemci │ ─────────────────────▶ │  Flask-SocketIO sunucu   │ ───▶ │ PostgreSQL │
│  gui_app.py     │   WebSocket (Socket.IO)│  server.py               │      │ database.py│
│  network_client │ ◀────────────────────▶ │  game_core.py (doğrulama)│      └────────────┘
│  ai_vs_human.py │                        │  oda durumu + kilit      │
└─────────────────┘                        └──────────────────────────┘
```

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
