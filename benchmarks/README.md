# Connect Four Pro - Benchmark'lar

Performans ölçümleri (tez "Testing and Results" bölümü). Fonksiyonel testler ayrıdır: `tests/` (pytest).

Son ölçümün sonuçları ve tüm tablolar: **[RESULTS.md](RESULTS.md)**

## Dosyalar

| Dosya | Ölçtüğü |
|---|---|
| `ai_performance_suite.py` | AI gecikmesi ve karmaşıklığı (D1–D8), doğrulanmış taktik senaryolar, AI turnuvası |
| `ai_quality_benchmark.py` | Hamle kalitesi kusursuz çözücüye karşı (v1 ve v2), açılış kitabı doğrulaması, kusursuz rakibe karşı oyunlar, v2–v1 maçları |
| `legacy_ai_v1.py` | AI motorunun ilk sürümü (yalnızca karşılaştırma için) |
| `gui_fps_benchmark.py` | GUI kare hızı; boşta ve Zor (D8) AI ararken (NFR-05) |
| `network_benchmark.py` | WebSocket vs REST, işlem gecikmeleri, mesaj boyutu, eşzamanlılık, eşzamanlı oyunlar |
| `locustfile.py` | Locust REST yük testi (3 kullanıcı profili) |
| `visualize_all_results.py` | `results/*.json` → `visualization_outputs/*.png` + `RESULTS.md` |
| `run_all.py` | Hepsini sırayla çalıştırır |
| `bench_common.py` | Ortak yardımcılar (ortam bilgisi, istatistik) |

## Çalıştırma

```bash
pip install -r requirements-dev.txt          # proje kökünden

# Benchmark için AYRI bir veritabanı kullanın (test hesapları oluşturulur ve sonda silinir)
createdb connect4_bench
export DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4_bench

cd benchmarks
python run_all.py            # tam ölçüm (~30 dk): sunucuyu kendisi başlatır
python run_all.py --quick    # hızlı kontrol (~3 dk)
python run_all.py --server http://localhost:5000 --skip-ai   # çalışan sunucuya karşı
```

Tek tek çalıştırmak da mümkündür, örn. `python ai_performance_suite.py --iterations 45 --seed 7`.

### AI kalite ölçümü için kusursuz çözücü (isteğe bağlı)

Hakem olarak Pascal Pons'un çözücüsü kullanılır. Bu çözücü AGPL-3.0 lisanslıdır ve **repoya dahil değildir**:

```bash
git clone https://github.com/PascalPons/connect4 && cd connect4 && make
curl -LO https://github.com/PascalPons/connect4/releases/download/book/7x6.book
cd -  &&  python run_all.py --solver-dir /yol/connect4
```

## Yöntem

**AI**
- Kalite: her kritik pozisyonda AI'nın hamlesi kusursuz çözücünün kesin puanlarıyla karşılaştırılır. Ölçülenler: optimal hamle oranı, sonucu koruma oranı, hata oranı. İki küme kullanılır: rastgele oyun pozisyonları ve gerçekçi (AI + %25 rastgele) oyun pozisyonları. v2'nin değerlendirme ağırlıkları farklı tohumlu bir eğitim kümesinde ayarlandı; rapordaki kümeler ayarda hiç kullanılmadı.
- Gecikme: derinlik başına 30 rastgele pozisyon (erken/orta/geç oyun eşit, sabit tohum). Bütün derinlikler **aynı pozisyonlarda** ölçülür. Açılış kitabı kapalıdır; kitaptan gelen 0 ms'lik hamleler ortalamayı düşürmez.
- Senaryolar: her senaryonun doğru cevap kümesi 4 yarı-hamlelik **kesin arama** (zorla kazanç/kayıp çözücü) ile hesaplanır, elle yazılmaz.
- Turnuva: AI deterministiktir, aynı başlangıçtan hep aynı oyun çıkar. Bu yüzden her eşleşme 10 farklı rastgele açılıştan oynanır ve her açılış renkler değiştirilerek iki kez oynanır (eşleşme başına 20 oyun). Puan = galibiyet + beraberlik/2.

**Ağ**
- Socket.IO taşıma katmanı kaydedilir. WebSocket değilse (ör. `websocket-client` eksikse) ölçüm geçersiz sayılır ve betik durur.
- Protokol karşılaştırması adil yapılır: `latency_ping` (WebSocket) ile `GET /health` (REST) karşılaştırılır; ikisi de veritabanına dokunmaz.
- Eşzamanlılık: N istemci sabit süre boyunca durmadan istek gönderir. Verim duvar saatiyle hesaplanır; bağlantı kurulumu ölçüme dahil değildir.
- Eşzamanlı oyunlar: K oda (2K WebSocket bağlantısı) aynı anda tam oyun oynar. Olaylar istemcide sırasız gelebildiği için cevaplar içeriğe göre (hamle geçmişinin uzunluğu) eşleştirilir.

**Sınırlamalar**
- Sunucu, yük üreticileri ve PostgreSQL aynı makinede çalışır. Ağ gecikmesi yerel ağa (localhost) aittir.
- Sunucu Flask-SocketIO `threading` modunda (Werkzeug geliştirme sunucusu) çalışır. Üretimde eventlet/gevent veya gunicorn ile verim farklı olur.
- GUI ölçümü ekransız (SDL dummy) yapılır; ekrana çizim maliyeti dahil değildir.

## Önceki sürümle karşılaştırma notları

Önceki grafikler (`tests/visualization_outputs`, Aralık 2025) şu nedenlerle yeni sonuçlarla doğrudan karşılaştırılamaz:
1. `visualize_all_results.py`, ölçüm dosyası bulamadığında koda gömülü **örnek değerleri** çiziyordu. Turnuva ısı haritası her zaman sabit örnek değerlerden üretiliyordu, "Kullanıcı memnuniyeti 4.6/5" de koddaki örnek veriydi.
2. `requirements.txt` içinde `websocket-client` olmadığı için Socket.IO istemcisi **HTTP long-polling** kullanıyordu. "WebSocket" ölçümleri gerçekte polling ölçümüdür.
3. Senaryo testlerinin 3'ünde beklenen hamle yanlıştı veya hamle sırası olmayan oyuncu adına yaptırılıyordu.
4. Turnuvadaki "20 oyun" aynı 2 oyunun tekrarıydı. JSON özetinde düğüm sayısı alanı olmadığı için karmaşıklık grafiği de örnek değerlere düşüyordu.
5. Ölçümler farklı donanımda yapılmıştı (bkz. RESULTS.md "Ortam").
