# Connect Four Pro - Unity Migration Guide

## Python'dan Unity'ye Gecis Rehberi

Bu rehber, Connect Four Pro projesinin Python (Pygame) versiyonundan Unity (C#) versiyonuna gecis surecini aciklar.

---

## Hizli Baslangic

### 1. Unity Projesi Olusturma

1. Unity Hub'i acin (Unity 2022.3 LTS veya ustu oneriliyor)
2. "New Project" > "2D Core" sablonunu secin
3. Proje adi: `ConnectFourPro`
4. Proje olusturulduktan sonra, `unity/Assets/Scripts` klasorunun icerigini Unity projenizin `Assets/Scripts` klasorune kopyalayin

### 2. Gerekli Paketler

Unity Package Manager'dan su paketleri yukleyin:
- **TextMeshPro** (genellikle varsayilan olarak gelir)
- **Input System** (opsiyonel, yeni input sistemi icin)

Online multiplayer icin:
- **SocketIOUnity**: `https://github.com/itisnajim/SocketIOUnity.git`
  (Package Manager > Add package from git URL)

### 3. Sahne Kurulumu (Otomatik)

1. Unity'de bos bir sahne acin
2. Hierarchy'de sag tikla > "Create Empty" > isim: `SceneSetup`
3. `SceneSetup` objesine `SceneSetup.cs` scriptini ekleyin
4. Play'e basin - tum UI ve oyun objeleri otomatik olusturulacaktir

### 3b. Sahne Kurulumu (Manuel)

Eger otomatik kuruluim calismaszsa:

1. Hierarchy'de "Create Empty" > isim: `GameManager`
   - `GameManager.cs` scriptini ekleyin
2. "Create Empty" > isim: `Board`
   - `BoardController.cs` scriptini ekleyin
3. "Create Empty" > isim: `NetworkClient` (GameManager'in child'i)
   - `NetworkClient.cs` scriptini ekleyin
4. UI > Canvas olusturun
   - `UIManager.cs` scriptini ekleyin
5. Canvas altina her ekran icin bos Panel olusturun ve ilgili scriptleri ekleyin

---

## Mimari Karsilastirma

### Python -> C# Dosya Eslesmesi

| Python Dosyasi | C# Dosyasi(lari) | Aciklama |
|---|---|---|
| `game_core.py` | `Core/GameConstants.cs`, `Core/ConnectFourGame.cs` | Bitboard oyun motoru |
| `ai_vs_human.py` | `AI/AIEngine.cs` | Minimax + Alpha-Beta AI |
| `gui_app.py` (ConnectFourGUI) | `Managers/GameManager.cs` | Ana durum makinesi |
| `gui_app.py` (draw fonksiyonlari) | `UI/*.cs` | UI panelleri (ayri dosyalar) |
| `gui_app.py` (board cizimi) | `Managers/BoardController.cs` | Tahta gorselleri |
| `gui_app.py` (NetworkManager) | `Network/NetworkClient.cs` | Ag istemcisi |
| `server.py` | Degismedi (Python) | Sunucu Python olarak kaliyor |
| `database.py` | Degismedi (Python) | Veritabani Python olarak kaliyor |

### Mimari Degisiklikler

1. **Tek dosya -> Coklu dosya**: Python'daki 1111 satirlik `gui_app.py` Unity'de 15+ ayri C# dosyasina bolundu
2. **Pygame dongusu -> Unity MonoBehaviour**: `while True` dongusu yerine `Update()` kullaniliyor
3. **Dogrudan cizim -> Prefab sistemi**: `pygame.draw` yerine Unity'nin sahne graf sistemi
4. **Thread -> Unity coroutine + thread**: Ag islemleri icin Unity Coroutine, AI icin System.Threading
5. **Event sistemi**: C# event'leri ile gevek bagli (loosely-coupled) mimari

---

## Onemli Notlar

### Sunucu (Server)
Python Flask-SocketIO sunucusu (`server.py`) degistirilmeden kullanilmaya devam eder. Unity istemcisi ayni REST API ve SocketIO endpoint'lerine baglanir.

### SocketIO Entegrasyonu
Gercek zamanli multiplayer icin `SocketIOUnity` paketinin yuklenmesi gerekir. Paket olmadan sadece REST API (login, register, leaderboard) calisir.

### AI Performansi
C#'daki AI performansi Python'a gore daha yuksek olacaktir. `long` (64-bit) tip kullanilarak bitboard islemleri daha verimli yapilir.

### Renk Semasi
Python versiyonundaki renk semasi birebir tasindi:
- Arka plan: `(26, 26, 46)` - Koyu lacivert
- Tahta: `(15, 52, 96)` - Koyu mavi
- Kirmizi tas: `(233, 69, 96)`
- Sari tas: `(241, 196, 15)`
- Kazanan parlama: `(0, 255, 128)`

---

## Klasor Yapisi

```
unity/
├── Assets/
│   ├── Scripts/
│   │   ├── Core/
│   │   │   ├── GameConstants.cs      # Sabitler
│   │   │   └── ConnectFourGame.cs    # Bitboard oyun motoru
│   │   ├── AI/
│   │   │   └── AIEngine.cs           # Minimax + Alpha-Beta
│   │   ├── Managers/
│   │   │   ├── GameManager.cs        # Ana durum makinesi
│   │   │   ├── BoardController.cs    # Tahta gorselleri
│   │   │   └── SceneSetup.cs         # Otomatik sahne kurulumu
│   │   ├── UI/
│   │   │   ├── UIManager.cs          # Panel yonetimi
│   │   │   ├── LoginPanel.cs         # Giris ekrani
│   │   │   ├── MainMenuPanel.cs      # Ana menu
│   │   │   ├── AISelectPanel.cs      # Zorluk secimi
│   │   │   ├── LobbyPanel.cs         # Online lobi
│   │   │   ├── WaitingPanel.cs       # Rakip bekleme
│   │   │   ├── GameHUDPanel.cs       # Oyun ici HUD
│   │   │   └── LeaderboardPanel.cs   # Liderlik tablosu
│   │   ├── Network/
│   │   │   └── NetworkClient.cs      # REST + SocketIO istemci
│   │   └── ConnectFourPro.asmdef     # Assembly definition
│   ├── Prefabs/                      # (Unity Editor'de olusturulacak)
│   ├── Materials/                    # (Unity Editor'de olusturulacak)
│   ├── Scenes/                       # (Unity Editor'de olusturulacak)
│   └── Resources/                    # (Unity Editor'de olusturulacak)
├── Packages/
│   └── manifest.json                 # Unity paket bagimliliklari
├── ProjectSettings/
│   └── ProjectSettings.asset         # Proje ayarlari
└── UNITY_SETUP_GUIDE.md             # Bu dosya
```
