# Connect Four Pro — Yapay Zekâ: Oyun Teorisi, Sorunlar ve v2 Motoru

Bu belge AI motorunun kuramsal temelini, ilk sürümde (v1) ölçülen sorunları ve yeni sürümün (v2) tasarımını anlatır. Ölçümlerin tamamı: [`benchmarks/RESULTS.md`](../benchmarks/RESULTS.md) → "AI kalitesi".

## 1. Oyun teorisi

**Connect Four çözülmüş bir oyundur.** 7×6 tahta, iki kişilik, sıfır toplamlı ve tam bilgili bir oyundur. 1988'de James D. Allen ve Victor Allis birbirinden bağımsız olarak çözdüler. Allis'in çözümü bilgi tabanlıydı: "zugzwang" ve tehdit kurallarından oluşan 9 strateji ve arama. Daha sonra John Tromp'un 8 hamlelik veritabanıyla kaba kuvvet çözümleri geldi. Toplam yasal pozisyon sayısı 4.531.985.219.092'dir (Edelkamp & Kissmann, 2008).

**Kusursuz oyunda sonuç.** Kusursuz bir çözücüyle bu projede yeniden doğrulandı; boş tahtada sütun değerleri `-2 -1 0 1 0 -1 -2`:

| İlk hamle | Kusursuz oyunda sonuç |
|---|---|
| Orta sütun (4) | İlk oyuncu kazanır |
| Komşu sütunlar (3, 5) | Beraberlik |
| Dış sütunlar (1, 2, 6, 7) | İkinci oyuncu kazanır |

> Bazı ders notları "ortadan başlanmazsa ikinci oyuncu beraberliği zorlar" der. Kusursuz çözücü dış sütunlarda ilk oyuncunun **kaybettiğini** gösteriyor; bu belgede çözücünün sonucu esas alınmıştır.

**Tehditler ve satır paritesi (zugzwang).** "Tehdit", tamamlanınca dörtlü oluşturan boş hücredir. Taşlar yerçekimiyle düştüğü için oyunun sonu tahtanın dolma sırasına bağlıdır. Satırlar alttan 1'den başlayarak numaralandırılırsa:
- İlk oyuncu için **tek satırlardaki** (1, 3, 5) tehditler değerlidir.
- İkinci oyuncu için **çift satırlardaki** (2, 4, 6) tehditler değerlidir.

Aynı sütundaki tehditlerden alttaki genellikle belirleyicidir. İkinci oyuncunun temel savunması "claimeven"dir: rakibin taşının hemen üstüne oynayarak çift satırları sahiplenmek (Allis, 1988).

**Pratik sonuç.** Sınırlı derinlikte arama yapan sezgisel bir AI'nın kusursuz oyuna karşı açılıştan beraberlik tutması çok zordur. Bunun için oyunun sonuna kadar uzanan zugzwang planlaması gerekir. Kusursuz çözücüler bunu tam arama, transpozisyon tablosu ve büyük bir açılış kitabıyla başarır. Sezgisel bir AI'dan beklenen şey, kesin hatalardan kaçınması ve kısa vadeli taktikleri eksiksiz görmesidir.

### Kusursuz çözücülerin teknikleri

Pascal Pons'un açık kaynak çözücüsü ([connect4.gamesolver.org](http://connect4.gamesolver.org), AGPL-3.0) bu projede **yalnızca hakem** olarak kullanıldı; kodu projeye dahil değildir. Kullandığı teknikler:
- Negamax + alpha-beta budama
- Bitboard ile O(1) tehdit hesabı
- "Kaybettirmeyen hamle" budaması: rakibin tehdit hücresinin altına oynamamak, tek tehdidi zorunlu olarak engellemek
- Merkezden dışa ve tehdit sayısına göre hamle sıralaması
- Transpozisyon tablosu
- Sıfır genişlikli pencereyle yinelemeli daraltma
- Açılış kitabı

## 2. v1 motorunda ölçülen sorunlar

v1, tezde ölçülen motordur ve karşılaştırma için `benchmarks/legacy_ai_v1.py` dosyasında saklanmıştır. Kusursuz çözücüyle yapılan ölçümler şunları gösterdi:

1. **Açılış kitabının 12 girişinden 5'i yanlıştı; 4'ü oyunun sonucunu değiştiriyordu.**
   - `(3,2)` ve `(3,4)`: Kazanan konumdaki ilk oyuncuya beraberlik hamlesi oynatıyordu.
   - `(1,)` ve `(5,)`: İkinci oyuncu kazanabilecekken kitap beraberlik hamlesi seçiyordu.
2. **Daha derin arama daha iyi oyun getirmiyordu.** Kritik pozisyonlarda doğru hamle oranı D1 %69, D2 %65, D4 %70, D6 %76 idi. Turnuvada D3 ile D5 ve D4 ile D6 neredeyse eşit çıktı.
3. **Bu anomalinin nedeni değerlendirme fonksiyonuydu:**
   - **Asimetri.** Rakibin açık üçlüsü −6.000.000, AI'nın kendi açık üçlüsü +5.000 puandı; rakibin tehdidi 1200 kat ağır basıyordu.
   - **Tempo yok.** Değerlendirme her zaman AI'nın bakış açısından yapılıyordu, sıranın kimde olduğuna bakılmıyordu. Çift derinlikte yaprak düğümlerde sıra AI'dadır; AI orada tek hamlede kazanabilecekken bile rakibin engellenebilir üçlüsü yüzünden pozisyonu kayıp sayıyordu. Tek ve çift derinliklerin farklı davranmasının kaynağı buydu.
   - **Parite ve oynanabilirlik yok.** Havada kalan ve oynanabilen tehditler aynı sayılıyordu.
4. **Yavaştı.** Her düğümde oyun nesnesi kopyalanıp 6×7 matris yeniden kuruluyordu ve transpozisyon tablosu yoktu. D6 ortalama ~200 ms, D8 ~2,8 sn sürüyordu.

## 3. v2 motoru (`src/ai_vs_human.py`)

| Bileşen | v2 |
|---|---|
| Temsil | Bitboard: `cur` (sıradaki oyuncunun taşları) + `mask` (dolu hücreler); düğüm başına nesne kopyalanmaz |
| Arama | Negamax + alpha-beta, transpozisyon tablosu, yinelemeli derinleştirme |
| Taktik kurallar | Tek hamlede kazanç; tek tehdit → zorunlu engelleme; çift tehdit → kayıp; rakibin tehdidinin altına oynamama |
| Hamle sıralaması | Tablodaki en iyi hamle → yeni tehdit sayısı → merkeze yakınlık |
| Değerlendirme | Simetrik, sıradaki oyuncunun bakış açısından (negamax). Satır paritesine göre ağırlıklı tehditler (lehine parite 8, diğer 4) + hücreden geçen olası 4'lü hat sayısı tablosu |
| Oyun sonu | Zor seviyede kalan ≤ 12 hamlede arama oyunun sonuna kadar gider (kesin çözüm) |
| Açılış kitabı | İlk iki yarı-hamlenin 57 pozisyonu; hepsi kusursuz çözücüyle hesaplandı |
| Zorluk | Kolay D2, Orta D4, **Zor D8** (önceden D6); v2 D8, v1 D6'dan ~4 kat hızlı |

**Ağırlıkların seçimi.** Değerlendirme ağırlıkları, kusursuz çözücüyle etiketlenmiş ayrı bir **eğitim** pozisyon kümesinde ızgara aramasıyla seçildi. Sonuçlar ayara hiç girmemiş bir **test** kümesinde raporlandı. Parite ayrımı yapmayan varyantlar eğitim kümesinde ~1 puan daha kötüydü; oyun teorisindeki parite kuralının katkısı küçük ama ölçülebilir.

**Doğruluk testleri** (`tests/unit/test_ai.py`):
- Bit hilesiyle bulunan tehdit hücreleri kaba kuvvetle karşılaştırılır.
- Transpozisyon tablosu, budama ve sıralama kullanan arama, tam genişlikli referans negamax ile **aynı değeri** vermelidir.
- Tablo paylaşılarak yapılan dar ve sıfır pencereli aramalarda alpha-beta sözleşmesi korunmalıdır.
- Oyun sonu çözümü ve kazanç mesafesi kaba kuvvet sonucuyla birebir tutmalıdır.

Testlerin hata yakalayıp yakalamadığı mutasyon testiyle doğrulandı. Yakalanmayan mutantların performans optimizasyonları gibi sonucu değiştirmeyen "eşdeğer" mutantlar olduğu analiz edildi.

## 4. Sonuçların yorumu

Sayılar için `benchmarks/RESULTS.md`. Özetle:
- v2, aynı derinlikte v1'den daha az kesin hata yapar ve karşılaşmalarda v1'i yener.
- Derinlik sıralaması artık tutarlıdır.
- Kalan hataların çoğu açılışta (ilk ~10 hamle) yoğunlaşır. Bu, sınırlı derinlikli her sezgisel AI'nın doğal sınırıdır; açılışta pozisyonun gerçek değeri 30+ yarı-hamle sonra belli olur.
- Kusursuz rakibe karşı berabere açılışlardan beraberliği tutmak her iki sürüm için de nadirdir. Kusursuz oyuncuya karşı bu beklenen sonuçtur.

**İleride yapılabilecekler:**
- Allis'in kurallarının (claimeven, baseinverse, vertical…) değerlendirmeye eklenmesi
- Daha derin bir açılış kitabı
- Zaman sınırlı arama
- Kendi kendine oynayarak öğrenilmiş değerlendirme

## Kaynaklar

- Allis, L. V. (1988). *A Knowledge-based Approach of Connect-Four*. Yüksek lisans tezi, Vrije Universiteit Amsterdam.
- Allen, J. D. (1988). Connect Four'un bağımsız çözümü (bkz. [Wikipedia: Connect Four](https://en.wikipedia.org/wiki/Connect_Four)).
- Edelkamp, S., & Kissmann, P. (2008). Pozisyon sayısı (bkz. [OEIS A212693](https://oeis.org/A212693)).
- MIT OCW ES.268, *Connect Four* ders notu (tek/çift tehdit örnekleri): [ocw.mit.edu](https://ocw.mit.edu/courses/es-268-the-mathematics-in-toys-and-games-spring-2010/94a5d1da64c57cbc5fdf135d985445a9_MITES_268S10_Ses5_ConFour.pdf)
- Pons, P. *Connect 4 Game Solver* ve öğretici: [connect4.gamesolver.org](http://connect4.gamesolver.org), kaynak: [github.com/PascalPons/connect4](https://github.com/PascalPons/connect4)
