# Connect Four Pro - Test Suite

Bu dizin, Connect Four Pro projesinin kapsamlı test altyapısını içerir.

## Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `ai_performance_suite.py` | AI algoritması performans testleri (Latency, Tournament, Scenario) |
| `network_benchmark.py` | Network performans testleri (WebSocket, REST, Concurrency) |
| `locustfile.py` | Locust yük testi senaryoları (50-200 kullanıcı) |
| `visualize_all_results.py` | Test sonuçlarından grafik oluşturma |
| `requirements.txt` | Python bağımlılıkları |

## Kurulum

```bash
# Sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya: venv\Scripts\activate  # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

## Test Çalıştırma

### 1. AI Performance Test

```bash
python ai_performance_suite.py
```

Bu test şunları ölçer:
- Depth 1-7 için AI yanıt süresi (latency)
- Node sayısı ve Alpha-Beta pruning verimliliği
- Kritik pozisyon senaryoları
- AI vs AI turnuva

Çıktılar: `./test_results/ai_*.csv`, `./test_results/ai_results_*.json`

### 2. Network Benchmark

```bash
# Önce server'ı başlat
python server.py

# Sonra testi çalıştır
python network_benchmark.py --server http://localhost:5000
```

Bu test şunları ölçer:
- WebSocket RTT (Round-Trip Time)
- REST API yanıt süreleri
- Payload boyutu vs Latency
- Eşzamanlı bağlantı kapasitesi

Çıktılar: `./test_results/network_*.csv`, `./test_results/network_results_*.json`

### 3. Locust Load Test

```bash
# Server'ın çalıştığından emin ol
python server.py

# Web UI ile (tarayıcıda http://localhost:8089)
locust -f locustfile.py --host=http://localhost:5000

# Veya headless (50 kullanıcı, 2 dakika)
locust -f locustfile.py --host=http://localhost:5000 -u 50 -r 5 -t 2m --headless
```

Parametreler:
- `-u`: Toplam kullanıcı sayısı
- `-r`: Saniyede spawn edilecek kullanıcı
- `-t`: Test süresi (s/m/h)
- `--headless`: Web UI olmadan çalıştır

### 4. Görselleştirme

```bash
python visualize_all_results.py --input ./test_results --output ./visualization_outputs
```

Oluşturulan grafikler:
- `ai_performance_analysis.png` - AI performans özeti
- `ai_latency_vs_depth.png` - Depth vs Latency grafiği
- `ai_computational_complexity.png` - Hesaplama karmaşıklığı
- `protocol_comparison.png` - WebSocket vs REST
- `concurrency_analysis.png` - Ölçeklenebilirlik analizi
- `tournament_heatmap.png` - AI turnuva sonuçları
- `summary_dashboard.png` - Özet dashboard

## Önerilen Test Sırası

1. **AI Performance Test** (server gerektirmez)
   ```bash
   python ai_performance_suite.py
   ```

2. **Server Başlat**
   ```bash
   python server.py
   ```

3. **Network Benchmark** (server gerektirir)
   ```bash
   python network_benchmark.py
   ```

4. **Locust Load Test** (server gerektirir)
   ```bash
   locust -f locustfile.py --host=http://localhost:5000 -u 50 -r 5 -t 2m --headless
   ```

5. **Görselleştirme**
   ```bash
   python visualize_all_results.py
   ```

## Çıktı Dizinleri

```
./test_results/           # Test sonuçları (CSV, JSON)
./visualization_outputs/  # Grafikler (PNG, PDF)
```

## Tez için Kullanım

1. Tüm testleri sırayla çalıştır
2. `./test_results/` dizinindeki JSON dosyalarını sakla
3. `./visualization_outputs/` dizinindeki grafikleri teze ekle
4. Summary dashboard'u sonuç bölümünde kullan

## Sorun Giderme

**Server'a bağlanamıyor:**
- Server'ın çalıştığından emin ol: `python server.py`
- Port 5000'in açık olduğunu kontrol et

**Matplotlib hatası:**
- GUI backend'i için: `export MPLBACKEND=Agg` (Linux)
- Veya: `plt.switch_backend('Agg')` kodu ekle

**Locust import hatası:**
- `pip install locust --upgrade`

**PostgreSQL bağlantı hatası:**
- Database'in çalıştığından emin ol
- `.env` dosyasında DATABASE_URL kontrol et
