# Online özellikler: maç tekrarı, hızlı eşleşme, hazır sohbet, süreli maç

Tarih: 2026-11-18 · Durum: onaylandı (sahibi: Eren)

## Amaç ve neden

Connect Four Pro'nun online kısmı, en yakın rakipler olan findfour.io ve
play4row.com'un gerisinde kalıyor. Bu iki sitede ELO, seyirci modu ve
analiz zaten var, bunlara ek olarak sohbet, süreli maç, hızlı eşleşme ve
maç tekrarı da sunuyorlar. Bu çalışma bu dört eksiği kapatıyor. Hedef,
itch.io'da puanlı, seyirci modlu ve analizli olan bu tek Connect Four'un
rakiplerle aynı temel özellikleri sunmasıdır.

## Hedefler

1. **Maç tekrarı:** Bitmiş bir online maç hamle hamle izlenebilir.
2. **Hızlı eşleşme:** Tek düğmeyle rastgele bir rakiple maç başlar.
3. **Hazır sohbet:** Oyuncular maç sırasında hazır kısa mesajlar gönderir.
4. **Süreli maç:** Satranç saati gibi, oyuncu başına toplam süre ve her
   hamlede ek süre (3+2).

## Kapsam dışı

- Serbest metinli sohbet. Küfür denetimi gerektirir.
- ELO'ya göre eşleştirme. Oyuncu sayısı az, kuyruk bekletmesin diye
  sırayla eşleşilir.
- Birden fazla süre seçeneği. İlk sürümde sadece 3+2 var.
- Pygame istemcisine yeni özellik eklemek.
- Turnuva. Ayrı bir tasarımda ele alınacak.

## Olmaması gerekenler (başarısızlık sayılır)

- Pygame istemcisinin ya da süresiz odaların bugünkü davranışının
  bozulması. Sunucu geriye uyumlu kalmalı: yeni alanlar ekleniyor, eski
  olaylar ve alanlar değişmiyor.
- Yapay zekânın hamlelerinin, puanlarının ya da düğüm sayılarının
  değişmesi. `src/ai_vs_human.py` ve `AIEngine.cs` dosyalarına
  dokunulmaz, golden-vector testleri bunu sabitliyor.
- Süre hesabını istemciye bırakmak. Saat hilesine açık olur.
- Sohbetin spam aracına dönüşmesi.

## Kısıtlar

- Sunucu: Flask-SocketIO (`src/server.py`). Oda durumu bellekte
  (`GAMES`, `GAMES_LOCK`). Hata kodları `_emit_error` ve `ERROR_CODES`
  üzerinden gider.
- İstemci: Unity 6 WebGL (`unity/Assets/Scripts`). Ekranlar `AppScreen`,
  görünümler `Views.cs` içinde. Yazılar `Loc.cs` ile Türkçe ve
  İngilizce. Unity'deki yazılar diakritikli, kod yorumları ASCII Türkçe.
- Testler: pytest (unit ve integration), C# testleri (`tests/csharp`),
  Playwright e2e (`tests/e2e`). Hiçbir test atlanmaz ya da gevşetilmez.
- Her özellik ayrı dal ve ayrı PR olur. CI yeşil olunca merge edilir.
  Sunucu değişikliği Render'a deploy edilir. Son build itch.io'ya
  yüklenir.

## Yaklaşımlar

- **Teslim:** Dört ayrı PR (seçildi) ya da tek büyük PR. Ayrı PR'lar
  inceleme ve geri alma açısından daha güvenli. Bağımlılık sırası:
  tekrar → hızlı eşleşme → sohbet → süreli maç. Süreli maç, hızlı
  eşleşmenin 3+2 kuralına dayanır.
- **Süre biçimi:** Satranç saati (seçildi) ya da hamle başına süre
  (mevcut `MOVE_TIME_SECONDS` altyapısı, şu an kapalı). Rakiplerle aynı
  seviyede olmak için satranç saati seçildi.
- **Süre hesabı:** Sunucu otoritesi (seçildi). İstemci sadece kalan
  süreyi gösterir ve aradaki zamanı kendi tarafında geri sayar.

## Tasarım

### 1. Maç tekrarı (sadece istemci)

- Sunucu zaten `/user/<ad>/games` yanıtında hamle listesini gönderiyor.
  `moves` alanı `str(list)` biçiminde, yani "[3, 3, 4]". `HistoryEntry`
  şu an sadece hamle sayısını tutuyor; hamle listesi alanı eklenir.
- Geçmiş sadece iki kayıtlı oyuncunun maçlarını tutar (mevcut kural).
  Misafir ya da puansız maçlar geçmişte görünmez; bunlar maç sonundaki
  "Tekrarı izle" ile izlenir. Sunucu değişmez.
- Geçmiş ekranında her satıra "İzle" düğmesi eklenir. Online maç
  bittiğinde oyun ekranında "Tekrarı izle" düğmesi de çıkar (yerel
  `Game.MoveHistory` kullanılır).
- Yeni bir ekran, `AppScreen.Replay`, mevcut `BoardView`'u kullanır.
  Düğmeler: ⏮ ◀ ▶ ⏭, Oynat/Durdur (hamle başına 0,8 sn) ve
  "Hamle k / n" sayacı. Üstte iki oyuncunun adı ve maç sonucu görünür.
  Klavye: ← → ok tuşları, Boşluk ile oynat/durdur, Esc ile geri.
- Tekrar ekranı, `GameState`'i 0'dan k'ya kadar yeniden oynatarak
  oluşturulur. Animasyon sadece tek adım ileri gidince oynar.

### 2. Hızlı eşleşme

- Yeni olaylar:
  - `quick_match_join {user_id, ...kimlik}`: kuyruğa girer. Cevap
    `quick_match_waiting`.
  - `quick_match_cancel`: kuyruktan çıkar. Cevap `quick_match_cancelled`.
- Kuyruk bellekte tutulur ve `GAMES_LOCK` altında değişir. Aynı
  kullanıcı ya da aynı soket kuyruğa iki kez giremez. Kopan soket
  kuyruktan düşer.
- İki oyuncu olunca sunucu normal bir oda kurar (3+2 süreli), ilk
  oyuncuyu P1, ikinciyi P2 yapar ve mevcut olayları gönderir:
  `game_created` yerine iki tarafa `game_joined` ve `game_start`, artı
  `quick: true`. Bundan sonrası normal oda gibi işler: rövanş, yeniden
  bağlanma, seyirci, ELO.
- Misafirler de katılabilir. Misafir ile kayıtlı oyuncu eşleşebilir.
  ELO sadece iki kayıtlı oyuncu arasında değişir (mevcut kural).
- Kuyruğa girmek, oyuncunun bekleyen kendi odasını siler (tek bekleyen
  oda kuralı). Aktif bir maçta koltuğu olan soket kuyruğa giremez, hata
  döner.
- Eşleşmede P1 de, P2 de `game_joined` alır. Bu olay `rejoin_token`
  içerir, böylece iki taraf da kopunca geri dönebilir.
- İstemci: menüye "Hızlı Maç" düğmesi gelir. Bekleme ekranı mevcut
  `Waiting` görünümünü "Rakip aranıyor..." yazısı ve İptal düğmesiyle
  kullanır.
- **İlk hamle gelmezse puansız iptal:** Hızlı eşleşme odası `quick: True`
  bayrağı taşır (rövanşta korunur). İlk hamleyi yapacak oyuncu, 5 sn
  başlangıç payı (`CLOCK_START_DELAY_SECONDS`) bittikten sonra 30 sn
  (`FIRST_MOVE_ABORT_SECONDS`) içinde oynamazsa oyun iptal edilir:
  kazanan yok, ELO değişmez, kimseye yenilgi yazılmaz. İptal edilen oyun
  veritabanına hiç kaydedilmez (geçmişte görünmez). Sunucu bunu satranç
  saatiyle aynı döngüde (`move_clock_loop` → `enforce_move_deadlines`,
  `GAMES_LOCK` altında) denetler; pencere dolduktan sonra gelen ilk hamle
  de geçersizdir ve oyunu iptal eder. Odaya (oyuncular ve seyirciler)
  `game_over {reason: 'aborted', detail: 'first_move', winner: null}`
  gider. İlk hamle yapılınca pencere kapanır, normal 3+2 kuralları
  işler. Her rövanşta pencere yeniden açılır. Normal lobi odaları
  (süreli ya da süresiz) etkilenmez.
- Pencere açıkken kopma: iptal, kopma nedeniyle hükmen yenilgiden
  önce gelir. İlk hamleyi yapacak oyuncu koparsa yeniden bağlanma süresi
  dolsa da hükmen yenilgi verilmez; 30 sn dolunca oyun iptal edilir.
  Sırası gelmeyen oyuncu koparsa da pencere açıkken hükmen yenilgi
  verilmez: ilk hamleyi yapacak oyuncu 30 sn içinde oynamazsa oyun iptal
  edilir; oynarsa pencere kapanır ve kopan oyuncu hâlâ dönmediyse
  hükmen yenilgi (`detail: 'disconnect'`) o anda işlenir. Pencere,
  rakibin kopması yüzünden saat duraklasa da işlemeye devam eder.
- İstemciler: Unity "Oyun iptal edildi (puansız)" / "Game aborted
  (unrated)" yazar, başlıkta "İPTAL EDİLDİ" görünür, rövanş düğmesi
  çıkmaz (ilk hamleyi yapmayan rakiple rövanş anlamsız); "Lobiye Dön"
  ile çıkılıp yeni hızlı maç aranabilir. pygame "Oyun iptal edildi
  (puansiz)" gösterir, rövanş düğmesi yine çıkmaz. Sunucu rövanş
  isteğini reddetmez (eski istemciler için). Eski istemciler bilinmeyen
  `reason`'u kazanansız sonuç olarak "Berabere!" diye gösterir, çökmez.

### 3. Hazır sohbet

- Sabit 8 mesaj, kimlik numaraları 0–7:
  1. İyi oyun! / Good game!
  2. Bol şans! / Good luck!
  3. Güzel hamle! / Nice move!
  4. Hay aksi! / Oops!
  5. Düşünüyorum... / Thinking...
  6. Teşekkürler! / Thanks!
  7. Rövanş? / Rematch?
  8. Selam! / Hi!
- Olay `chat_quick {room_id, msg_id}`. Sunucu şunları denetler:
  gönderenin o odada oyuncu olması, `msg_id`'nin 0–7 arası bir tamsayı
  olması ve aynı soketin son 2 saniyede mesaj göndermemiş olması.
  Geçerliyse odaya `chat_message {room_id, from_piece, msg_id}` yayar,
  seyirciler de alır. Geçersiz istek sessizce yok sayılır, hata
  gönderilmez.
- Hız sınırı soket başına uygulanır. Seyirciler mesaj gönderemez.
- Sohbet maç bittikten sonra da çalışır, çünkü "İyi oyun!" ve
  "Rövanş?" mesajları tam da o an için.
- İstemci: oyun ekranında küçük bir 💬 düğmesi 8 mesajlık bir panel
  açar. Gelen mesaj, gönderenin adının yanında 3 sn balon olarak
  görünür. Metin, alıcının kendi diline `Loc` ile çevrilir.

### 4. Süreli maç (3+2)

- Odaya `time_control` alanı eklenir: `None` (süresiz) ya da
  `{"base": 180, "inc": 2}`. Oda kurulurken `create_game` içinde
  isteğe bağlı `time_control: "3+2"` gönderilir. Alan yoksa oda
  süresizdir, eski istemciler etkilenmez. Hızlı eşleşme her zaman 3+2
  kurar.
- Sunucu her koltuk için kalan süreyi saniye cinsinden tutar ve sıranın
  başladığı anı kaydeder. Hamle gelince geçen süre düşülür, ardından
  ek süre eklenir. Saat ilk hamleyle değil, P2 katıldığında başlar.
  Rövanşta saatler sıfırlanır.
- Süre bitince (gecikme payı `MOVE_TIME_GRACE_SECONDS` uygulanır) mevcut
  yol kullanılır: `_finish_game(..., reason='forfeit', detail='timeout')`.
- *(Düzeltme)* Mevcut `move_clock_loop` arka plan görevi sadece
  `MOVE_TIME_SECONDS > 0` iken başlıyor ve bu değer varsayılan olarak 0.
  Görev bundan sonra her zaman başlar ve hem eski `turn_deadline`'ı hem
  satranç saatini denetler. Saniyede bir odaları taramak çok ucuz.
- Süreli odada satranç saati `turn_deadline`'ın yerine geçer. Süreli
  odada hamle başına sınır uygulanmaz. Süresiz odada `MOVE_TIME_SECONDS`
  bugünkü gibi çalışır.
- Başlangıç payı: saat ilk 5 saniye işlemez, istemciler o sırada ekranı
  yükler. Bu hem hızlı eşleşmede hem P2 katıldığında geçerlidir.
- Kopma: rakip kopunca sırası gelen bekleyen oyuncunun saati durur
  (`_clock_paused`). Sırası gelen oyuncu kendisi koparsa onun saati
  işlemeye devam eder; süresi 30 sn yeniden bağlanma hakkından önce
  biterse süreden kaybeder. Satrançtaki davranış budur.
- P2'ye giden `game_joined` olayına da `_clock_fields` eklenir (şu an
  sadece `game_start` içinde var).
- Olaylardaki saat alanları `_clock_fields` içine eklenir:
  `time_control`, `clock_p1`, `clock_p2` (kalan tam saniye) ve
  `clock_running` (1, 2 ya da 0). Süresiz odada eski alanlar değişmez.
- *(Düzeltme, son inceleme I-1)* Saati okuyamayan eski istemciler
  (pygame, önbellekteki eski WebGL) süreli odada da bir sayaç görsün diye
  süreli odada `turn_seconds_left` işleyen koltuğun kalan süresi artı
  kalan başlangıç payıdır. Duraklamada, bitmiş ya da bekleyen odada
  `None` olur. `move_time` süreli odada 0'dır, böylece eski istemciler
  rakip dönünce sayacı hamle süresiyle yeniden kurmaz. Yeni istemci
  `time_control` varken bu alanları kullanmaz.
- *(Düzeltme, T8-M1)* `opponent_disconnected` ve `opponent_reconnected`
  olayları da `_clock_fields` taşır. Seyirciler dahil herkes duraklama ve
  devam anında saati eşitler.
- İstemci: oda kurma ekranında "Süresiz / 3+2" seçimi olur. Oyun
  ekranında iki oyuncunun adının yanında mm:ss saat görünür. Sırası
  gelen oyuncunun saati yerelde geri sayar ve her sunucu olayında
  düzeltilir. 10 saniyenin altında kırmızıya döner. Lobi listesinde
  süreli odalar "3+2" etiketiyle görünür.

## Test

- **Sunucu (pytest, integration):** kuyrukta eşleşme, iptal, kopunca
  kuyruktan düşme, kendiyle eşleşmeme. Sohbet: yetki, geçersiz
  numara, hız sınırı, seyircinin mesajı alması. Saat: ek süre
  eklenmesi, süre bitince hükmen yenilgi (zaman yapay olarak ileri
  alınır), duraklama, rövanşta sıfırlanma, süresiz odanın aynen
  çalışması.
- **C#:** saat biçimlendirme (mm:ss), tekrar ekranının k. hamle
  durumunu doğru üretmesi, yeni `Loc` anahtarları.
- **E2E (Playwright):** iki tarayıcıyla hızlı eşleşme, bir hazır
  mesajın karşıya ulaşması, geçmişten bir tekrarın açılması.

## Uygulayıcıya bırakılanlar

Düğme ve panel yerleşimi (yatay ve dikey düzen kurallarına uyarak),
balonun tam görünümü, kuyruk veri yapısı ve dahili fonksiyon adları.
