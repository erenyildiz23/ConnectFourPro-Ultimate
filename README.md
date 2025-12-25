# 🎮 Connect Four Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.5+-red.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)
![License](https://img.shields.io/badge/License-Academic-yellow.svg)

**Gelişmiş yapay zeka, çok oyunculu destek ve performans analiz araçları içeren profesyonel Connect Four oyunu.**

[Özellikler](#-özellikler) • [Kurulum](#-kurulum) • [Kullanım](#-kullanım) • [Mimari](#-mimari) • [API](#-api)

</div>

---

## ✨ Özellikler

### 🎯 Oyun Özellikleri
- **Pygame GUI**: Modern, animasyonlu grafik arayüz
- **Çok Oyunculu**: Flask-SocketIO ile gerçek zamanlı online oyun
- **Seyirci Modu**: Aktif oyunları canlı izleme
- **ELO Sistemi**: Rekabetçi sıralama ve matchmaking
- **Liderlik Tablosu**: En iyi oyuncuları görüntüleme
- **Kazanan Vurgulama**: Animasyonlu kazanan taş efekti

### 🤖 Yapay Zeka
- **Minimax Algoritması**: Alpha-beta budama ile optimizasyon
- **Bitboard Temsili**: Ultra hızlı oyun durumu hesaplama
- **Opening Book**: Bilinen açılış hamleleri veritabanı
- **3 Zorluk Seviyesi**:
  - 🟢 Kolay (Depth 2)
  - 🟡 Orta (Depth 4)
  - 🔴 Zor (Depth 6)

### 📊 Analiz ve Test
- **Arka Plan Analizi**: Lichess tarzı hamle değerlendirmesi
- **Performans Testleri**: AI benchmark suite
- **Yük Testleri**: Locust ile sunucu stres testleri
- **Görselleştirme**: Matplotlib ile grafik raporlama

### 🔒 Güvenlik
- **Şifreli Şifreler**: SHA-256 hash
- **Thread-Safe AI**: Lock mekanizması ile güvenli çoklu iş parçacığı
- **Session Yönetimi**: AI oturumlarının güvenli kontrolü

---

## 📁 Proje Yapısı

```
ConnectFour/
├── 📂 src/                       # Ana kaynak kodlar
│   ├── game_core.py              # Bitboard tabanlı oyun motoru
│   ├── gui_app.py                # Pygame GUI uygulaması (v5.0)
│   ├── ai_vs_human.py            # Minimax AI motoru
│   ├── server.py                 # Flask-SocketIO sunucusu (v2.1)
│   ├── database.py               # PostgreSQL veritabanı katmanı
│   └── requirements.txt          # Python bağımlılıkları
│
├── 📂 tests/                     # Test ve benchmark araçları
│   ├── ai_performance_suite.py   # AI performans test paketi
│   ├── network_benchmark.py      # Ağ performans testleri
│   ├── locustfile.py             # Yük testi konfigürasyonu
│   └── visualize_all_results.py  # Sonuç görselleştirme
│
├── 📄 README.md                  # Bu dosya
├── 📄 .gitignore                 # Git ignore kuralları
└── 📄 build_exe.bat              # Windows exe oluşturma scripti
```

---

## 🚀 Kurulum

### Gereksinimler
- Python 3.8+
- PostgreSQL 13+ (opsiyonel, veritabanı özellikleri için)

### Adım 1: Repoyu Klonlayın
```bash
git clone https://github.com/erenyildiz23/ConnectFourPro.git
cd ConnectFourPro
```

### Adım 2: Sanal Ortam Oluşturun
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Adım 3: Bağımlılıkları Yükleyin
```bash
pip install -r src/requirements.txt
```

### Adım 4: Veritabanı Kurulumu (Opsiyonel)
```bash
# PostgreSQL veritabanı oluşturun
createdb connect4

# Veya DATABASE_URL environment variable ayarlayın
export DATABASE_URL="postgresql://user:password@localhost/connect4"
```

---

## 🎮 Kullanım

### Tek Oyunculu (AI'ya Karşı)
```bash
cd src
python gui_app.py
```
- Giriş yapın veya misafir olarak devam edin
- "Yapay Zekaya Karşı" seçeneğini tıklayın
- Zorluk seviyesini seçin ve oynamaya başlayın

### Çok Oyunculu Sunucu
```bash
# Terminal 1: Sunucuyu başlatın
cd src
python server.py
```
Sunucu `http://localhost:5000` adresinde çalışmaya başlar.

```bash
# Terminal 2 & 3: İstemcileri başlatın
cd src
python gui_app.py
```
- Her iki istemcide de giriş yapın
- "Online Lobi" seçeneğinden oyun oluşturun veya mevcut oyuna katılın

### Performans Testleri
```bash
# AI Performance Suite
cd tests
python ai_performance_suite.py

# Network Benchmark
python network_benchmark.py
```

### Yük Testi
```bash
cd tests
locust -f locustfile.py --host=http://localhost:5000
```
Tarayıcıda `http://localhost:8089` adresini açarak yük testini yönetin.

---

## 🏗 Mimari

### Oyun Motoru (game_core.py)
```
┌─────────────────────────────────────┐
│         ConnectFourGame             │
├─────────────────────────────────────┤
│  • Bitboard representation          │
│  • O(1) win detection               │
│  • Move validation                  │
│  • State serialization              │
└─────────────────────────────────────┘
```

### AI Motoru (ai_vs_human.py)
```
┌─────────────────────────────────────┐
│           AIEngine                  │
├─────────────────────────────────────┤
│  • Minimax + Alpha-Beta             │
│  • Opening Book                     │
│  • Position Evaluation              │
│  • Configurable depth               │
└─────────────────────────────────────┘
```

### Sunucu Mimarisi (server.py)
```
┌─────────────────────────────────────┐
│       Flask-SocketIO Server         │
├─────────────────────────────────────┤
│  Events:                            │
│  • create_game                      │
│  • join_game                        │
│  • make_move                        │
│  • game_over                        │
│  • elo_update                       │
├─────────────────────────────────────┤
│  Features:                          │
│  • Room management                  │
│  • Auto-cleanup (5 min timeout)     │
│  • Duplicate prevention             │
│  • Spectator support                │
└─────────────────────────────────────┘
```

---

## 📡 API Referansı

### REST Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/signup` | POST | Yeni kullanıcı kaydı |
| `/login` | POST | Kullanıcı girişi |
| `/user/<username>` | GET | Kullanıcı bilgisi |
| `/leaderboard` | GET | Liderlik tablosu |
| `/active_games` | GET | Aktif oyunlar listesi |

### WebSocket Events

| Event | Direction | Açıklama |
|-------|-----------|----------|
| `create_game` | Client → Server | Yeni oyun odası oluştur |
| `join_game` | Client → Server | Oyuna katıl |
| `make_move` | Client → Server | Hamle yap |
| `game_created` | Server → Client | Oyun oluşturuldu |
| `game_start` | Server → Client | Oyun başladı |
| `move_made` | Server → Client | Hamle yapıldı (broadcast) |
| `game_over` | Server → Client | Oyun bitti |
| `elo_update` | Server → Client | ELO güncellemesi |

---

## 🔧 Teknolojiler

| Kategori | Teknoloji |
|----------|-----------|
| **GUI** | Pygame 2.5+ |
| **Backend** | Flask 3.0, Flask-SocketIO 5.3 |
| **Database** | PostgreSQL, psycopg2 |
| **AI** | Custom Minimax Engine |
| **Testing** | Locust 2.29 |
| **Real-time** | python-socketio, python-engineio |

---

## 📈 Performans

### AI Benchmark Sonuçları
| Zorluk | Depth | Ortalama Hamle Süresi |
|--------|-------|----------------------|
| Kolay | 2 | < 10ms |
| Orta | 4 | < 100ms |
| Zor | 6 | < 500ms |

### Sunucu Performansı
- **Eşzamanlı Bağlantı**: 100+ oyuncu
- **Hamle Latency**: < 50ms
- **Oda Oluşturma**: < 20ms

---

## 🛠 Geliştirme

### Debug Modu
`gui_app.py` içinde debug loglarını açmak için:
```python
DEBUG = True  # Konsol logları aktif
```

### Veritabanı Şeması
```sql
-- Users tablosu
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rating INTEGER DEFAULT 1200,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
);

-- Games tablosu
CREATE TABLE games (
    game_id SERIAL PRIMARY KEY,
    player1_id INTEGER REFERENCES users(user_id),
    player2_id INTEGER REFERENCES users(user_id),
    winner_id INTEGER,
    moves TEXT
);
```

---

## 👨‍💻 Geliştirici

**Eren Yıldız**
- 📧 eren.yildiz@std.yeditepe.edu.tr
- 🎓 Yeditepe Üniversitesi

---

## 📄 Lisans

Bu proje akademik amaçlı geliştirilmiştir - Yeditepe Üniversitesi Bitirme Projesi.

---

## 🙏 Teşekkürler

Bu proje, sıra tabanlı oyunlarda yapay zeka performansı ve ağ optimizasyonu üzerine bir tez çalışmasının parçası olarak geliştirilmiştir.

---

<div align="center">

**⭐ Beğendiyseniz yıldız vermeyi unutmayın! ⭐**

</div>
