# Arena Turnuvası — Tasarım

Tarih: 2026-11-19 · Durum: taslak (sahip onayı bekliyor)

## 1. Amaç ve neden

Connect Four Pro'yu rakip sitelerden (findfour.io, play4row) ayıracak rekabetçi bir özellik:
kayıtlı oyuncuların açtığı, belirli bir süre boyunca durmadan eşleşip puan topladıkları
**Arena** turnuvaları. Biten oyuncu hemen yeni rakiple eşleşir; süre bitince en çok puanı olan kazanır.

Başarı: iki ya da daha fazla oyuncu bir turnuvayı başından sonuna sorunsuz oynar, sıralamayı
canlı görür, oyunları puanlı olarak Elo'ya işlenir ve şüpheli oyuncular yöneticiye bildirilir.

## 2. Sahibin kararları (değişmez)

- Biçim: **Arena**.
- Turnuvayı **kayıtlı herhangi bir oyuncu** açabilir.
- Yalnızca **kayıtlı oyuncular** katılır (misafir katılamaz).
- Oyunlar **3+2** satranç saatiyle oynanır (mevcut saat kodu, `TIME_CONTROLS['3+2']`).
- Puan: galibiyet **2**, beraberlik **1**, yenilgi **0**; **seri katlaması** var.
- **Canlı sıralama.**
- Turnuva oyunları **puanlıdır** (normal oyunlar gibi Elo'ya işlenir).
- Hamleleri mükemmel çözücüyle **%100 örtüşen** oyuncular yöneticiye bildirilir; yalnızca **kritik hamleler** sayılır (bkz. bölüm 3).
- Hile kontrolü **turnuva bittikten sonra GitHub Actions'ta** çalışır ve bulguları **GitHub issue** olarak açar (seçenek A).

## 3. Konuşmada önerilen ve onaylanan ayrıntılar

**Açma**
- Menüde yeni "Turnuvalar" ekranı; "+ Turnuva Aç" düğmesi yalnızca kayıtlı oyuncuya görünür.
- Süre: **15, 30 veya 60 dakika**.
- Başlangıç: **hemen** ya da **en geç 24 saat sonra** seçilen bir saat.
- Bir kullanıcının aynı anda en fazla **1** bekleyen veya süren turnuvası olabilir.
- Turnuva adı: açanın adıyla otomatik ("<kullanıcı>'nın Arenası" / "<user>'s Arena"); serbest metin yok (küfür/denetim yükü yok).

**Katılma ve oynama**
- Başlamadan önce de, sürerken de katılınabilir; geç gelen kaybettiği süreyle girer.
- Biten oyuncu otomatik olarak yeniden eşleşme kuyruğuna girer.
- Aynı iki oyuncu **art arda** eşleşmez; kuyrukta başka uygun rakip yoksa eşleşebilir.
- "Duraklat" ile oyuncu kuyruktan çıkar; puanı kalır, istediğinde "Devam" ile döner.
- Son dakikadan sonra yeni oyun başlamaz; süren oyunlar biter ve puanları sayılır.

**Puan ve seri**
- Seri: üst üste **2 galibiyetten sonra** her galibiyet **4**, her beraberlik **2** puan.
- Seri bir yenilgi ya da beraberlikle biter (seri içindeki beraberlik 2 puan alır, sonra seri sıfırlanır).
- Seride olan oyuncunun yanında 🔥 gösterilir.
- Eşitlik: puan eşitse **daha çok oyun oynamış** olan, o da eşitse **rating'i yüksek** olan üstte.

**Kimse katılmazsa**
- Başlangıç anında 2'den az katılımcı varsa turnuva **10 dakika** daha bekler; hâlâ 2'den azsa **iptal** olur ve listeden düşer. Bekleme süresi turnuva süresinden düşülür.

**Hile kontrolü**
- Turnuva bitince her oyuncunun o turnuvadaki hamleleri mükemmel çözücüyle değerlendirilir; yalnızca **kritik hamleler** sayılır (sahibin kararı, 2026-11-19).
- **Kritik hamle:** hamlenin seçimi oyunun teorik sonucunu (kazanç / beraberlik / kayıp) değiştirebiliyorsa, yani yanlış bir sütun sonucu kötüleştiriyorsa. Tanım `benchmarks/ai_quality_benchmark.py` içindeki `critical()` ile aynıdır. Zorunlu hamleler (tek sonucu koruyan hamle dışındakilerin hepsi aynı sonuca götürüyorsa ayrım yok), sonucu değiştirmeyen hamleler ve açılış kitabı derinliğindeki hamleler sayılmaz.
- Kritik bir hamle, teorik sonucu koruyorsa "doğru" sayılır.
- Oyuncu **en az 3 oyunda toplam en az 20 kritik hamle** yapmışsa ve bunların **%100'ü** doğruysa bir GitHub issue açılır.

Ekran taslağı:

```
TURNUVALAR                         [+ Turnuva Aç]
─────────────────────────────────────────────────
Akşam Arenası  · 3+2 · 30 dk · 12 oyuncu · 18:42 kaldı  [Katıl]
Eren'in Arenası · 3+2 · 15 dk · başlıyor 21:00          [Katıl]

AKŞAM ARENASI — 18:42                    [Duraklat]
 1. 🔥 ayse     14   ●●●○●
 2.    eren     10   ●○●●
 3.    mehmet    6   ○●●
```

## 3a. Kurucu kontrolünden sonra netleşenler (tasarımcının kararları)

- **Seri kuralı tam tanım:** 1. ve 2. art arda galibiyet 2'şer puan; 3. art arda galibiyetten itibaren her galibiyet 4 puan. Seri sürerken (en az 2 art arda galibiyetten sonra) gelen beraberlik 2 puan alır ve seriyi sıfırlar; seri yokken beraberlik 1 puan. Hükmen galibiyet (rakibin süresi bitti / bağlantısı koptu / ayrıldı) normal galibiyet sayılır. Her türlü yenilgi (süre, kopma, ayrılma dahil) 0 puan ve seriyi sıfırlar. İlk hamle iptali hiç sayılmaz: puan vermez, oyun sayısına girmez, seriyi bozmaz.
- **Beraberlik ve Elo:** mevcut davranış korunur — beraberlik Elo'yu değiştirmez (`_finish_game` bugün böyle).
- **Yeni oyun kesimi:** `ends_at`'ten sonra yeni eşleşme yapılmaz; o anda süren oyunlar biter ve puanları sayılır. "Son dakika" ifadesi `ends_at` anlamındadır.
- **Sunucu yeniden başlarsa / uyursa:** bellekte kalan, bitmemiş turnuva oyunları sonuçsuz düşer (puan ve Elo yok). Turnuva en geç `ends_at + 15 dk`'da `finished` olur (son oyun bitmesini beklemeden). Bağlanan ve duraklatmamış katılımcı, turnuva sürüyorsa otomatik olarak kuyruğa yeniden alınır (veritabanındaki `paused=false`'tan).
- **Uyurken gelen başlangıç:** 10 dakikalık "en az 2 oyuncu" beklemesi, sunucunun turnuvayı fiilen başlattığı andan (`starts_at` ile sunucunun uyanma anının büyüğü) sayılır; uyanır uyanmaz iptal edilmez.
- **Birden çok turnuva:** bir oyuncu birden çok turnuvaya üye olabilir ama aynı anda yalnızca birinin kuyruğunda/oyununda bulunur; birinde oynamaya başlamak diğerlerinde otomatik "duraklat" demektir. Üyelik ve puan (turnuva, kullanıcı) çiftine bağlıdır.
- **Hamle yapmayan oyuncu:** ilk hamleyi yapmadığı için iptal edilen oyunun sorumlusu otomatik olarak duraklatılır; "Devam" ile döner. Rakibi kuyruğa döner.
- **Görünürlük:** turnuva listesi ve canlı sıralamayı herkes (misafir dahil) görebilir; katılmak ve açmak kayıt ister. Biten turnuvalar sonuçlarıyla **7 gün** listede kalır; iptal edilenler listeden düşer.
- **Çözücü notu:** Pons çözücüsü bugün hiçbir iş akışında yok; yalnızca `benchmarks/README.md`'de elle kullanılıyor. Actions işi yeni yazılır; çözücüyü derler ve `7x6.book` açılış kitabını indirir (her ikisi Actions önbelleğine alınır).

## 4. Hedef olmayanlar

- Misafir katılımı, takım turnuvası, İsviçre/eleme biçimleri.
- 3+2 dışındaki süre kontrolleri.
- Berserk (süreyi yarıya indirip ek puan alma).
- Ödül, rozet, turnuva sohbet odası (oyun içi hazır sohbet zaten var).
- Oyun içi yönetici paneli (seçenek B reddedildi).
- pygame istemcisinde turnuva ekranı (pygame turnuvaya katılamaz; mevcut özellikleri bozulmaz).

## 5. İstenmeyenler (çalışsa bile başarısızlık sayılır)

- Sunucu yeniden başladığında ya da uykudan uyandığında turnuvanın kaybolması ya da puanların silinmesi.
- Bir oyuncunun aynı anda iki turnuva oyununda olması ya da turnuva oyunundayken hızlı maça girebilmesi.
- Haksız hile bildirimi: kısa oyunlardaki güçlü oyuncuların işaretlenmesi.
- Hile kontrolünün sunucuyu yavaşlatması.
- Veritabanı şifresinin GitHub'a verilmesini gerektiren bir kurgu.

## 6. Kısıtlar

- **Barındırma:** Render ücretsiz planı, tek işçi (gunicorn gthread, `WEB_CONCURRENCY=1`), kimse kullanmazken uykuya geçer; oyun odaları bellekte (`GAMES`). Turnuva durumu bu yüzden **veritabanında** kalıcı tutulur; bellekteki oyun odaları kaybolursa turnuva puanları zaten kaydedilmiş olur.
- **Uyku ve ileri tarihli başlangıç:** Sunucu başlangıç saatinde uyuyor olabilir. Turnuva saatleri mutlak zamanla (`starts_at`, `ends_at`) tutulur; sunucu uyandığında arka plan döngüsü durumu zamandan yeniden hesaplar (geç başlayan turnuva kalan süreyle devam eder, süresi geçmiş olan biter).
- **Veritabanı:** PostgreSQL, ücretsiz planın bağlantı sınırı (`DB_POOL_SIZE`). Mevcut tablolar `users`, `games`; şema `init_db()` içinde `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... IF NOT EXISTS` ile göç eder — yeni tablolar da böyle eklenir.
- **Mükemmel çözücü:** Pascal Pons'un çözücüsü (AGPL-3.0) projeye **dahil edilmez**; bugün olduğu gibi yalnızca hakem olarak kullanılır — GitHub Actions'ta kaynaktan derlenir (bkz. 3a çözücü notu).
- **Uyumluluk:** Eski istemciler (itch.io'daki eski sürüm, pygame) yeni olayları görmezden gelir; turnuva oyunu onlara normal 3+2 oyun gibi görünür ama eski istemci turnuvaya katılamaz.
- **Yazım kuralları:** kod yorumları ASCII Türkçe; Unity arayüz metinleri Türkçe (diakritikli) + İngilizcesi `Loc.cs`'te; belgeler diakritikli Türkçe.
- **Yapay zekâ arama kodu** (`src/ai_vs_human.py`, `unity/Assets/Scripts/AI/*`) değişmez.
- **Yatay ve dikey ekran** düzeni (dikeyde en küçük yazı 18 pt).

## 7. Yaklaşımlar

| Yaklaşım | Artı | Eksi | Karar |
|---|---|---|---|
| **A. Mevcut sunucuda turnuva motoru + veritabanında kalıcı durum; hile kontrolü Actions'ta, herkese açık bir uç noktadan okur** | Hızlı maç kuyruğu, 3+2 saat ve Elo hazır; ek servis yok; DB şifresi GitHub'a gitmez | Sunucu tek işçi, motor arka plan döngüsünü paylaşır | **Seçildi** |
| B. Ayrı turnuva servisi / işçi | Yük ayrılır | Ücretsiz planda ikinci servis yok; oda durumu paylaşılamaz | Elendi |
| C. Hile kontrolü sunucuda anında + yönetici paneli | Anında sonuç | Ücretsiz sunucuda ağır; yönetici rolü ve ekranı gerekir | Sahip reddetti |
| D. Eşleştirmeyi istemciye bırakmak | Sunucu yükü az | Hileye açık | Elendi |

Hile kontrolü için Actions işi, turnuva oyunlarını veritabanına bağlanmadan sunucunun herkese
açık bir uç noktasından (örn. `GET /tournaments/<id>/games`) okur. Oyun hamleleri zaten maç
geçmişinde herkese gösterildiği için yeni bir gizlilik riski yoktur. Issue'yu iş akışının
kendi `GITHUB_TOKEN`'ı açar.

## 8. Sistem tasarımı

### 8.1 Veri

- `tournaments`: `id`, `creator_id`, `name`, `duration_minutes` (15/30/60), `starts_at`, `ends_at`, `status` (`scheduled` / `running` / `finished` / `cancelled`), `created_at`, `cheat_checked_at` (Actions işinin aynı turnuvayı iki kez kontrol etmemesi için).
- `tournament_players`: `tournament_id`, `user_id`, `score`, `games_played`, `streak` (art arda galibiyet sayısı), `paused`, `joined_at`; birincil anahtar (`tournament_id`, `user_id`).
- `games` tablosuna `tournament_id` (boş olabilir) eklenir; puan ve sıralama bu bağdan yeniden hesaplanabilir.

### 8.2 Sunucu

- Arena eşleştirme kuyruğu, hızlı maç kuyruğunun (`QUICK_QUEUE`, `_quick_pair_locked`) yanında ayrı bir kuyruk olarak; turnuva başına bir kuyruk. Art arda aynı rakip kuralı için her oyuncunun son rakibi tutulur.
- Turnuva oyunu odası: `time_control='3+2'`, `quick` benzeri bir `tournament_id` alanı. Oyun bitince (`_finish_game`) sonuç Elo'ya işlenir, `tournament_players` puanı ve serisi aynı işlemde güncellenir, oyuncu (duraklatmadıysa) kuyruğa geri girer.
- Turnuva oyunlarında **rövanş yoktur**; oyuncu kuyruğa döner.
- **İlk hamle kuralı:** hızlı maçtaki 30 sn puansız iptal kuralı turnuva oyunlarında da geçerlidir; iptal edilen oyun puan vermez, iki oyuncu da kuyruğa döner.
- Arka plan döngüsü (mevcut saat döngüsü) her saniye: başlama zamanı gelenleri başlatır, 10 dk bekleme kuralını uygular, süresi bitenlerde yeni eşleştirmeyi durdurur, son oyun bitince turnuvayı `finished` yapar.
- Yeni Socket.IO olayları (adlar kurucunun kararı): turnuva listesi, açma, katılma, duraklatma/devam, canlı sıralama güncellemesi (değişiklik oldukça odaya yayın), turnuva bitti.
- Bir oyuncu aynı anda yalnızca bir yerde: turnuva kuyruğu / turnuva oyunu, hızlı maç kuyruğu ve normal oda birbirini dışlar (mevcut `_seated_in_active_game` kontrolü genişletilir).
- Kopma: mevcut 3+2 kuralları geçerli (bekleyenin saati durur, dönmezse hükmen). Bağlantısı kopan oyuncu kuyruktan düşer, dönünce yeniden girer.

### 8.3 Unity istemcisi

- Menüye "Turnuvalar" düğmesi (kayıtlı oyuncuda).
- Turnuva listesi, turnuva açma formu (süre 15/30/60, başlangıç: hemen / saat), turnuva sayfası (geri sayım, canlı sıralama, son oyunların ●/○ dizisi, 🔥, Katıl / Duraklat / Devam).
- Turnuva oyunu ekranı mevcut oyun ekranıdır; üstte turnuva adı ve kalan süre; oyun bitince rövanş yerine "Sıradaki oyun" ve kısa bekleme.
- Emoji yazı tipinde yoksa (sohbette 💬 yoktu) 🔥 yerine yazı tipinde bulunan bir işaret ya da renkli etiket kullanılır.

### 8.4 Hile kontrolü (GitHub Actions)

- Zamanlanmış iş (ör. her gece) + elle başlatma.
- Sunucudan bitmiş ve kontrol edilmemiş turnuvaları ve oyunlarını alır.
- Pons çözücüsünü derler (gerekirse açılış kitabıyla), her hamleyi değerlendirir.
- Eşik: en az 3 oyun, en az 20 kritik hamle, kritik hamlelerin %100'ü doğru → issue (oyuncu adı, turnuva, oyunlar, kritik hamle sayısı ve doğruluk oranı). Aynı oyuncu + turnuva için ikinci issue açılmaz.
- Kontrol edilen turnuvayı sunucuda işaretlemek için korumalı bir uç nokta (paylaşılan gizli anahtar, GitHub secret + Render ortam değişkeni) ya da issue başlığına göre tekrarı önleme — kurucunun kararı; DB şifresi GitHub'a verilmez.

## 9. Kurucuya kalanlar

Socket.IO olay ve alan adları; tablo indeksleri; sıralama güncellemesinin sıklığı ve boyutu;
eşleştirmede rating yakınlığının kullanılıp kullanılmayacağı; Actions işinin çalışma saati ve
çözücü performansı (açılış kitabı); arayüz yerleşimi ve renkleri (mevcut ekranlarla tutarlı);
testlerin bölünmesi.
