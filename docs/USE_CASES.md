# Connect Four Pro — Use Case Belgesi

Sürüm 3.0 · Python istemci/sunucu

Bu belge sistemin kullanım senaryolarını (use case), bunların tez gereksinimleriyle (FR / NFR) ilişkisini ve her senaryoyu doğrulayan otomatik testleri tanımlar. Diyagram: [`diagrams/use_case_diagram.puml`](diagrams/use_case_diagram.puml) ([PNG](diagrams/use_case_diagram.png)).

## Aktörler

| Aktör | Tür | Açıklama |
|---|---|---|
| **Kayıtlı Oyuncu** | Birincil | Hesabı olan kullanıcı. ELO puanı, maç geçmişi ve liderlik tablosunda yeri vardır. |
| **Misafir** | Birincil | Hesap açmadan oynayan kullanıcı. AI'ya karşı ve online oynayabilir, izleyebilir; ELO ve geçmiş tutulmaz. |
| **Seyirci** | Birincil | Devam eden bir maçı izleyen kullanıcı (kayıtlı veya misafir). Hamle yapamaz. |
| **AI Motoru** | Sistem | Negamax + Alpha-Beta ile hamle hesaplar (Kolay D2, Orta D4, Zor D8). Ayrıntı: [AI.md](AI.md) |
| **Zamanlayıcı** | Sistem | Sunucunun arka plan görevleri: oda temizliği, yeniden bağlanma süresi. |

"Oyuncu" ifadesi Kayıtlı Oyuncu ve Misafir'i birlikte kapsar.

## Use Case Listesi

| ID | Use Case | Birincil aktör | Gereksinim |
|---|---|---|---|
| UC-01 | Kayıt ol | Misafir | FR-01 |
| UC-02 | Giriş yap | Kayıtlı Oyuncu | FR-02 |
| UC-03 | Misafir olarak devam et | Misafir | FR-02 |
| UC-04 | Çıkış yap | Kayıtlı Oyuncu | — |
| UC-05 | Yapay zekaya karşı oyna | Oyuncu, AI Motoru | FR-05, FR-06, NFR-01 |
| UC-06 | Online oyun odası oluştur | Oyuncu | FR-03 |
| UC-07 | Lobiyi görüntüle | Oyuncu | FR-03, FR-04, FR-09 |
| UC-08 | Online oyuna katıl | Oyuncu | FR-04 |
| UC-09 | Online hamle yap | Oyuncu | FR-05, FR-08, NFR-02 |
| UC-10 | Maç izle | Seyirci | FR-09 |
| UC-11 | Bağlantı kopması ve yeniden bağlanma | Oyuncu, Zamanlayıcı | NFR-08 |
| UC-12 | Oyundan ayrıl (hükmen yenilgi) | Oyuncu | NFR-08 |
| UC-13 | Oyunu sonuçlandır, ELO güncelle ve kaydet | Sistem | FR-07, FR-10 |
| UC-14 | Liderlik tablosunu görüntüle | Oyuncu | FR-07 |
| UC-15 | Maç geçmişini görüntüle | Kayıtlı Oyuncu | FR-10 |
| UC-16 | Hamle analizini görüntüle | Oyuncu | — |
| UC-17 | Eski odaları temizle | Zamanlayıcı | NFR-03 |

İlişkiler: UC-09 ve UC-05 **«include»** hamle doğrulama ve kazanma kontrolü (oyun motoru). UC-09 sonunda **«include»** UC-13. UC-08, oda doluysa **«extend»** UC-10 (seyirci olarak katılım). UC-11 ve UC-12, UC-09'u **«extend»** eder.

---

## Ayrıntılı Senaryolar

### UC-01 Kayıt ol
- **Aktör:** Misafir · **Gereksinim:** FR-01
- **Ön koşul:** Giriş ekranı açık; sunucu ve veritabanı erişilebilir.
- **Ana akış:**
  1. Kullanıcı adı ve şifreyi girer, "Kayıt Ol"a basar.
  2. İstemci alanların dolu olduğunu, kullanıcı adının en az 3, şifrenin en az 8 karakter olduğunu kontrol eder.
  3. Sunucu kullanıcı adını (3–20 karakter; harf, rakam, `_ . -`) ve şifreyi (8–128) doğrular.
  4. Şifre tuzlu PBKDF2-SHA256 ile özetlenip hesap oluşturulur (ELO 1200).
  5. Kullanıcı ana menüye alınır, "Kayıt başarılı" mesajı gösterilir.
- **Alternatif akışlar:**
  - 2a. Alan boş/kısa → yerel uyarı, istek gönderilmez.
  - 3a. Geçersiz karakter veya `Misafir_` ön eki → HTTP 400, "Geçersiz kullanıcı adı".
  - 4a. Kullanıcı adı alınmış → HTTP 409, "Bu kullanıcı adı zaten alınmış".
  - 4b. Veritabanı yok → HTTP 503, kullanıcıya misafir modu önerilir.
- **Son koşul:** Hesap veritabanında; şifre düz metin olarak saklanmaz.
- **Testler:** `tests/gui/test_gui_use_cases.py::TestAccountUseCases::test_uc01_*`, `tests/integration/test_server_rest.py::TestSignup`, `tests/integration/test_database.py::TestUsers`

### UC-02 Giriş yap
- **Aktör:** Kayıtlı Oyuncu · **Gereksinim:** FR-02
- **Ön koşul:** Hesap mevcut.
- **Ana akış:** Kullanıcı bilgilerini girer → sunucu şifreyi doğrular → profil (ELO, galibiyet, mağlubiyet) döner → ana menü.
- **Alternatif akışlar:**
  - Yanlış şifre / bilinmeyen kullanıcı → HTTP 401, "Yanlış kullanıcı adı veya şifre".
  - Sunucuya ulaşılamıyor → "Sunucuya bağlanılamadı" (arayüz donmaz; istek arka planda).
  - Eski SHA-256 ile kayıtlı hesap → giriş başarılı, şifre özeti otomatik PBKDF2'ye yükseltilir.
- **Son koşul:** Oturum açık; şifre özeti istemciye hiç gönderilmez.
- **Testler:** `TestAccountUseCases::test_uc02_*`, `test_uc02_server_unreachable`, `test_server_rest.py::TestLogin`, `test_database.py::test_legacy_account_logs_in_and_is_upgraded`

### UC-03 Misafir olarak devam et
- **Aktör:** Misafir · **Gereksinim:** FR-02 (kimlik doğrulamasız erişim kapsamı)
- **Ana akış:** "Misafir Olarak Devam"a basar → `Misafir_NNNNNN` adı atanır → ana menü.
- **Kısıtlar:** ELO değişmez, maç geçmişi tutulmaz, liderlik tablosunda yer almaz.
- **Testler:** `test_uc03_guest`, `test_uc15_history_not_available_for_guest`, `test_server_socket.py::TestGameEnd::test_win_ends_game` (misafire ELO bildirimi yok)

### UC-04 Çıkış yap
- **Aktör:** Kayıtlı Oyuncu
- **Ana akış:** Menüde "Çıkış Yap" → oturum bilgileri temizlenir → giriş ekranı.
- **Testler:** `test_uc01_register_and_uc04_logout`

### UC-05 Yapay zekaya karşı oyna
- **Aktör:** Oyuncu, AI Motoru · **Gereksinim:** FR-05, FR-06, NFR-01
- **Ön koşul:** Oturum açık (kayıtlı veya misafir). Sunucu gerekmez.
- **Ana akış:**
  1. "Yapay Zekaya Karşı" → zorluğu ("Kolay - yeni başlayanlar için", "Orta - dengeli rakip", "Zor - en güçlü rakip"; arka planda D2/D4/D8) ve ilk hamleyi kimin yapacağını ("İlk hamle: Sen / AI") seçer. Boş tahtada "Kırmızı sensin" ipucu gösterilir; oyuncu hep kırmızıdır.
  2. Oyuncu (kırmızı) sütuna tıklar veya 1–7 tuşlarından birine basar; taş düşme animasyonu oynar. Fare bir sütunun üzerindeyken taşın ineceği hücre oyuncunun renginde bir halkayla, son oynanan taş beyaz bir halkayla işaretlenir.
  3. Oyun motoru hamleyi doğrular ve kazanma/beraberlik kontrol eder.
  4. AI ayrı thread'de hamlesini hesaplar ("AI düşünüyor..."), sonra hamle animasyonla uygulanır.
  5. 2–4, oyun bitene kadar tekrarlanır; sonuç ekran başlığında (KAZANDIN! / AI KAZANDI / BERABERE) ve renkli durum satırında gösterilir, kazanan dörtlü parlatılır, diğer taşlar soluklaşır.
- **Alternatif akışlar:**
  - Sıra AI'dayken veya animasyon sürerken yapılan tıklamalar yok sayılır.
  - Dolu sütuna tıklanırsa hamle yapılmaz, "Bu sütun dolu!" uyarısı gösterilir; tahta dışı tıklama yok sayılır.
  - Oyuncu AI düşünürken menüye dönerse AI oturumu geçersiz kılınır; geç gelen AI hamlesi uygulanmaz.
  - "Geri Al" (veya U): oyuncunun son hamlesini ve AI'nın cevabını geri alır; oyun bittikten sonra da çalışır. Taş düşerken ve AI düşünürken reddedilir; online oyunda yoktur.
  - "Yeni Oyun": aynı zorlukta yeni oyun; ilk hamleyi yapan taraf her seferinde değişir.
  - Kolay seviye kasıtlı hata yapar (arama bittikten sonra, oyun ve hamle sırasından türeyen deterministik zarla: %40; kendi kazanan hamlesini kaçırmaz). Orta ve Zor hata yapmaz.
- **Son koşul:** Oyun sonucu ekranda; sunucuya kayıt yapılmaz.
- **Kısayollar:** 1–7 hamle, Esc geri, M ses aç/kapat (ses menüden de kapatılabilir; `CONNECT4_MUTE=1` ile kapalı başlar), U geri al (AI oyunu), R rovans (biten online oyun).
- **Testler:** `TestPlayVsAI` (3 test), `tests/gui/test_gui_feedback.py` (animasyon, işaretler, klavye, ses), `tests/unit/test_ai.py` (taktik, arama doğruluğu, oyun sonu), `tests/unit/test_game_core.py`; hamle kalitesi: `benchmarks/ai_quality_benchmark.py`

### UC-06 Online oyun odası oluştur
- **Aktör:** Oyuncu · **Gereksinim:** FR-03
- **Ana akış:** Lobide "+ Yeni Oyun" → sunucu 5 karakterlik oda kodu üretir → oyuncu kırmızı (P1) olarak bekleme ekranına geçer → oda lobide "Bekliyor" olarak listelenir.
- **Alternatif akışlar:**
  - Oyuncunun zaten bekleyen odası varsa eskisi silinir (tek bekleyen oda kuralı).
  - "İptal" (veya Esc) → oda silinir, oyuncu lobiye döner. Bekleyen oyuncunun bağlantısı koparsa oda silinir.
  - Sunucuya ulaşılamıyor → lobiye dönülür, hata mesajı.
- **Testler:** `TestOnlineUseCases::_start_online_match`, `test_uc06_cancel_waiting_room`, `test_server_socket.py::TestRooms`

### UC-07 Lobiyi görüntüle
- **Aktör:** Oyuncu · **Gereksinim:** FR-03, FR-04, FR-09
- **Ana akış:** "Online Lobi" → aktif odalar (oda kodu, oyuncular ve ELO'ları, durum) listelenir; liste 2 saniyede bir arka planda yenilenir. Bekleyen odalarda "Katıl", oynanan odalarda "İzle" düğmesi gösterilir.
- **Kural:** Bitmiş oyunlar listelenmez.
- **Testler:** `TestOnlineUseCases` (lobi adımları), `test_server_socket.py::test_create_game`, `test_finished_game_not_listed_in_lobby`

### UC-08 Online oyuna katıl
- **Aktör:** Oyuncu · **Gereksinim:** FR-04
- **Ön koşul:** Bekleyen bir oda var.
- **Ana akış:** "Katıl" → oyuncu sarı (P2) olur → iki oyuncuya da `game_start` gider, rakip adı ve ELO'su gösterilir → oyun başlar (sıra kırmızıda).
- **Alternatif akışlar:**
  - Oda bulunamadı / geçersiz kod → hata mesajı.
  - Oyuncu kendi bekleyen odasına katılamaz.
  - Oda doluysa kullanıcı seyirci olarak katılır (→ UC-10).
- **Testler:** `TestOnlineUseCases`, `test_server_socket.py::test_join_*`, `test_cannot_join_own_waiting_room`

### UC-09 Online hamle yap
- **Aktör:** Oyuncu · **Gereksinim:** FR-05, FR-08, NFR-02
- **Ön koşul:** Oyun başlamış ve sıra oyuncuda.
- **Ana akış:**
  1. Oyuncu sütuna tıklar; hamle yerelde animasyonla uygulanır ve sunucuya gönderilir.
  2. Sunucu doğrular: oda var, rakip katılmış, gönderen bağlantı o taşın sahibi, sütun geçerli, sıra doğru, oyun bitmemiş.
  3. Sunucu yeni durumu odadaki herkese (rakip + seyirciler) yayınlar.
  4. Rakibin ekranında hamle animasyonla görünür; sıra ona geçer.
  5. Hamle oyunu bitirirse → UC-13.
- **Alternatif akışlar (sunucu reddeder, durum değişmez):** sıra sende değil · başkası adına hamle (yetkisiz) · geçersiz sütun (tip/aralık/dolu) · rakip henüz katılmadı · oyun bitti.
- **Testler:** `test_uc09_uc13_uc16_full_online_match`, `test_server_socket.py::TestMoveValidation` (13 test)

### UC-10 Maç izle
- **Aktör:** Seyirci · **Gereksinim:** FR-09
- **Ana akış:** Lobide "İzle" → anlık oyun durumu ve oyuncu bilgileri yüklenir (son oynanan taş halkayla işaretlidir) → sonraki hamleler canlı izlenir → oyun sonucu gösterilir (KIRMIZI KAZANDI / SARI KAZANDI / BERABERE) → "Lobiye Dön" ile lobiye dönülür.
- **Kural:** Seyirci hiçbir şekilde hamle yapamaz (sunucu reddeder).
- **Testler:** `test_uc09_uc13_uc16_full_online_match` (seyirci istemci), `test_third_user_becomes_spectator_and_sees_moves`, `test_spectator_cannot_move`

### UC-11 Bağlantı kopması ve yeniden bağlanma
- **Aktör:** Oyuncu, Zamanlayıcı · **Gereksinim:** NFR-08
- **Tetikleyici:** Aktif oyunda bir oyuncunun bağlantısı beklenmedik şekilde kopar.
- **Ana akış:**
  1. Sunucu rakibe "Rakibin bağlantısı koptu, 30 sn içinde dönmezse kazanırsın" bildirir; rakibin ekranında kalan süre saniye saniye geri sayar. Bağlantısı kopan oyuncu "Bağlantı koptu - yeniden bağlanılıyor..." mesajını görür ve bağlantı dönene kadar hamle yapamaz (hamle sunucuya ulaşmayacağı için yerelde de oynatılmaz).
  2. İstemci otomatik olarak yeniden bağlanır ve aynı odaya katılır.
  3. Sunucu oyuncuyu koltuğuna geri oturtur ve güncel oyun durumunu gönderir; rakibe "Rakip geri döndü" bildirilir.
  4. Oyun kaldığı yerden devam eder.
- **Alternatif akışlar:**
  - 2a. Oyuncu süre (`RECONNECT_GRACE_SECONDS`, varsayılan 30 sn) içinde dönmezse rakip **hükmen** kazanır (→ UC-13, `reason=forfeit`, `detail=disconnect`). Oyuncu daha sonra dönerse sıra mesajı yerine sunucunun gönderdiği sonucu (neden ve ELO değişimi dahil) görür.
  - 2b. Yeniden bağlanma 20 sn'den uzun sürerse oyuncuya bekleyebileceği veya lobiye dönebileceği hatırlatılır.
  - 2c. Oda artık yoksa (geri dönüş reddedilirse) "Oyuna geri dönülemedi" mesajı gösterilir; oyuncu onay istenmeden lobiye dönebilir.
  - 2d. Seyircinin bağlantısı koparsa "Yayın bağlantısı koptu" mesajı gösterilir; lobiden yeniden izlemeye girer.
- **Güvenlik:** Bağlı bir oyuncunun koltuğu ikinci bir bağlantıyla ele geçirilemez.
- **Testler:** `test_server_socket.py::TestDisconnectAndReconnect`, `TestOnlineUseCases::test_uc11_*`, `tests/gui/test_gui_feedback.py::TestConnectionState`

### UC-12 Oyundan ayrıl (hükmen yenilgi)
- **Aktör:** Oyuncu · **Gereksinim:** NFR-08
- **Ana akış:** Aktif online oyunda "Lobiye Dön" (veya Esc) → istemci uyarır: "Çıkmak hükmen yenilgi sayılır, onaylamak için tekrar basın" → tekrar basılır → oyun rakip lehine hükmen biter (→ UC-13), oyuncu lobiye döner.
- **Alternatif akış:** Onay 3 saniye içinde verilmezse işlem iptal olur.
- **Not:** `leave_game` sunucudan onay (ack) döner (`{ok: true/false}`); Pygame istemcisi, bağlantıyı kapatmadan önce onayı (en çok 2 sn) bekler. Böylece kopma olayı ayrılma isteğinden önce işlenip rakibe "bağlantı koptu" gibi görünmez. Kopma olayı önce işlense bile koltuk kopan bağlantının kimliğini taşımaya devam eder; o bağlantının gecikmiş `leave_game`'i çalışırsa yine hükmen yenilgi (`detail=leave`) sayılır. Başka bir bağlantı veya koltuğu devralınmış eski bağlantı rakibi hükmen yenik sayamaz.
- **Testler:** `test_uc12_leaving_requires_confirmation_and_forfeits`, `test_leave_game_is_immediate_forfeit`

### UC-13 Oyunu sonuçlandır, ELO güncelle ve kaydet
- **Aktör:** Sistem · **Gereksinim:** FR-07, FR-10
- **Tetikleyici:** Dörtlü, beraberlik (42 hamle) veya hükmen yenilgi.
- **Ana akış:**
  1. İki oyuncu da kayıtlıysa ELO tek veritabanı transaction'ında güncellenir (K=30, en az ±10): kazanana +Δ, kaybedene −Δ; galibiyet/mağlubiyet sayaçları artar.
  2. Oyun hamle listesi ve bitiş nedeniyle (`normal` / `forfeit`) kaydedilir.
  3. Oyunculara `elo_update`, odadaki herkese `game_over` gönderilir; istemci başlıkta "KAZANDIN!" / "KAYBETTİN" / "BERABERE", durum satırında "Kazandın! ELO +15 (1215)" gösterir (kazanç yeşil, kayıp kırmızı).
- **Alternatif akışlar:** Beraberlikte ELO değişmez ama oyun kaydedilir. Misafir varsa ELO/kayıt atlanır, ELO bildirimi gönderilmez.
- **Hükmen nedeni (`game_over.detail`):** istemci metni nedene göre seçer: `timeout` → "Süre doldu - hükmen kaybettin." / "Rakibin süresi doldu - Kazandın!"; `disconnect` → "Bağlantı kopması nedeniyle hükmen kaybettin." / "Rakibin bağlantısı koptu - Kazandın!"; `leave` veya alan yoksa (eski sunucu) → "Hükmen kaybettin." / "Rakip oyunu terk etti - Kazandın!".
- **Hamle süresi:** sunucuda `MOVE_TIME_SECONDS` > 0 ise (varsayılan 0 = kapalı) sunucu `move_time` ve `turn_seconds_left` gönderir; istemcide bilgi panelinde sırası gelenin yanında kalan saniye geri sayar; kendi hamle sürenin son 10 saniyesinde sayaç uyarı rengine döner ve bir uyarı sesi çalar. Sayaç kapalıyken, rakip koptuğu için duraklatılmışken ve oyun bitince gösterilmez.
- **Rovans:** oyun bitince oyuncuya (seyirciye ve AI oyununa değil) "Rovans" düğmesi / R tuşu çıkar; rakip istediğinde "Rakip rovans istiyor", kendin istediğinde "Rovans istendi, rakip bekleniyor" görünür. Rakip odadan ayrıldıysa düğme pasifleşir. İki taraf da isterse koltuklar yer değiştirir (yeni kırmızı ilk hamleyi yapar), tahta ve sonuç sıfırlanır; seyirci yeni oyunu boş tahtayla izlemeye devam eder.
- **Testler:** `test_uc09_uc13_uc16_full_online_match`, `test_server_socket.py::TestRegisteredPlayers`, `test_database.py::TestEloAndGames`, `tests/unit/test_security_and_elo.py::TestElo`

### UC-14 Liderlik tablosunu görüntüle
- **Aktör:** Oyuncu · **Gereksinim:** FR-07
- **Ana akış:** "Liderlik Tablosu" → en yüksek ELO'lu 10 oyuncu (ELO, galibiyet, mağlubiyet) arka planda tek istekle yüklenir.
- **Alternatif akışlar:** Sunucuya ulaşılamıyor → "Sunucuya bağlanılamadı". Kayıtlı oyuncu yok → bilgilendirme.
- **Testler:** `test_uc14_leaderboard`, `test_server_rest.py::TestQueries::test_leaderboard_limit_is_clamped`

### UC-15 Maç geçmişini görüntüle
- **Aktör:** Kayıtlı Oyuncu · **Gereksinim:** FR-10
- **Ana akış:** "Maç Geçmişi" → son 10 online maç: tarih, rakip, sonuç (Kazandın / Kaybettin / Berabere, hükmen ise belirtilir), hamle sayısı.
- **Alternatif akış:** Misafirlere "Maç geçmişi sadece kayıtlı oyuncular için tutulur" gösterilir.
- **Testler:** `test_uc15_*`, `test_server_rest.py::test_game_history`, `test_database.py::test_record_and_history`

### UC-16 Hamle analizini görüntüle
- **Aktör:** Oyuncu
- **Ana akış:** Online maç sırasında her hamleden önceki pozisyon arka planda D8 AI ile analiz edilir. Maç sonunda bilgi panelinde "Hamle analizi (isabet): Sen %X, Rakip %Y" gösterilir (oynanan hamlenin AI'nın en iyi hamlelerinden biri olma oranı: D8 aramasında eşit iyi çıkan tüm sütunlar ve doğrulanmış açılış kitabı hamlesi isabetli sayılır).
- **Testler:** `test_uc09_uc13_uc16_full_online_match`

### UC-17 Eski odaları temizle
- **Aktör:** Zamanlayıcı · **Gereksinim:** NFR-03 (kaynak kullanımı)
- **Ana akış:** Her 60 saniyede: 5 dk'dan uzun süredir rakip bekleyen, 10 dk hamle yapılmayan ve 1 dk önce bitmiş odalar silinir; odadakilere `game_ended (timeout)` bildirilir.
- **Testler:** `test_server_socket.py::TestCleanup`

---

## Gereksinim İzlenebilirlik Matrisi

| Gereksinim | Use Case | Otomatik doğrulama |
|---|---|---|
| FR-01 Kayıt | UC-01 | GUI + REST + DB testleri |
| FR-02 Kimlik doğrulama | UC-02, UC-03 | GUI + REST + DB testleri |
| FR-03 Oda oluşturma | UC-06, UC-07 | GUI + Socket testleri |
| FR-04 Odaya katılma | UC-07, UC-08 | GUI + Socket testleri |
| FR-05 Oyun kuralları | UC-05, UC-09 | `test_game_core.py` (sınır durumları dahil), Socket doğrulama testleri |
| FR-06 Üç seviyeli AI | UC-05 | `test_ai.py`, GUI AI oyunu, kusursuz çözücüye karşı kalite ölçümü |
| FR-07 ELO / liderlik | UC-13, UC-14 | DB + Socket + GUI testleri |
| FR-08 Gerçek zamanlı senkron | UC-09 | GUI iki istemci + seyirci testi, Socket yayın testleri |
| FR-09 Seyirci modu | UC-07, UC-10 | GUI + Socket testleri |
| FR-10 Sonuç kaydı | UC-13, UC-15 | DB + Socket + GUI testleri |
| NFR-01 AI yanıt < 500 ms (D6 ve Zor D8) | UC-05 | `benchmarks/ai_performance_suite.py` |
| NFR-02 WebSocket < 5 ms | UC-09 | `benchmarks/network_benchmark.py` |
| NFR-03 ≥ 50 eşzamanlı bağlantı | UC-17 | `benchmarks/network_benchmark.py`, Locust |
| NFR-04 > 500 istek/sn | — | `benchmarks/network_benchmark.py`, Locust |
| NFR-05 GUI ≥ 30 FPS | — | İstemci 60 FPS'e sabitlenir; ağ/HTTP işleri ana döngüyü bloklamaz |
| NFR-06 Üretimde güvenli protokol | — | Kapsam dışı: sunucu HTTP; üretimde TLS sonlandırıcı (ör. nginx) arkasında çalıştırılmalı |
| NFR-07 DB işlemi < 100 ms | UC-01, UC-13 | Benchmark (REST gecikmeleri) |
| NFR-08 Kopmalardan zarifçe kurtulma | UC-11, UC-12 | Socket yeniden bağlanma/hükmen testleri |
