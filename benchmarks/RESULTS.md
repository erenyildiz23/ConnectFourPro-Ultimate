# Connect Four Pro - Performans Sonuclari

> Bu dosya `benchmarks/visualize_all_results.py` tarafindan `results/*.json` dosyalarindan otomatik uretilir. Tum sayilar olculmustur; ornek/varsayilan veri yoktur.

## Ortam

- **AI:** Intel(R) Xeon(R) Processor @ 2.10GHz (4 mantiksal cekirdek), Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, Python 3.11.17, commit `1113e42`, 2026-10-21T11:32:04
- **AI kalitesi:** Intel(R) Xeon(R) Processor @ 2.10GHz (4 mantiksal cekirdek), Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, Python 3.11.17, commit `1113e42`, 2026-10-21T11:27:05
- **Ag:** Intel(R) Xeon(R) Processor @ 2.10GHz (4 mantiksal cekirdek), Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, Python 3.11.17, commit `ae20f22`, 2026-10-21T10:23:36
- **Locust:** Intel(R) Xeon(R) Processor @ 2.10GHz (4 mantiksal cekirdek), Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, Python 3.11.17, commit `ae20f22`, 2026-10-21T10:41:46
- **GUI:** Intel(R) Xeon(R) Processor @ 2.10GHz (4 mantiksal cekirdek), Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, Python 3.11.17, commit `1113e42`, 2026-10-21T11:27:05

Sunucu, istemciler (yuk ureticileri) ve PostgreSQL ayni makinede calisti; sunucu Flask-SocketIO `threading` modunda (Werkzeug). Sonuclar donanima baglidir, farkli makinede yeniden olculmelidir.

## Gereksinim dogrulama

| Gereksinim | Hedef | Olculen | Sonuc | Not |
|---|---|---|---|---|
| NFR-01 AI yanit suresi | < 500 ms (ortalama) | D6 ort 11 ms, p95 28 ms; Zor (D8) ort 41 ms, p95 120 ms | **GECTI** |  |
| NFR-02 WebSocket gecikmesi | < 5 ms (ortalama) | ort 1.64 ms, p99 3.37 ms | **GECTI** | tasima: websocket |
| NFR-03 Eszamanli baglanti | >= 50, hatasiz | 100 eszamanli baglantiya kadar 0 hata | **GECTI** |  |
| NFR-04 Sunucu verimi | > 500 istek/sn | REST (DB) 712, WS 1465 istek/sn | **GECTI** | REST, veritabani okuyan uc nokta |
| NFR-07 Veritabani islemleri | < 100 ms | leaderboard 2.2 ms, login 66.6 ms | **GECTI** | login sureyi PBKDF2 belirler |
| NFR-05 GUI kare hizi | >= 30 FPS | AI ararken ort 47 FPS, p99 kare 22 ms | **GECTI** | ekransiz (SDL dummy) olcum |
| Locust yuk testi | hata < %1 | 200 kullanici: %0.00 hata, p95 86 ms | **GECTI** |  |

![Ozet](visualization_outputs/summary_dashboard.png)

## AI performansi

Yontem: derinlik basina 30 rastgele pozisyon (erken/orta/gec oyun esit, tohum 2024); tum derinlikler ayni pozisyonlarda olculdu. Acilis kitabi kapali (saf arama).

| Derinlik | Ortalama (ms) | Std (ms) | Medyan | p95 (ms) | Maks (ms) | Ort. dugum | Ort. budama | us/dugum |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.09 | 0.02 | 0.08 | 0.13 | 0.15 | 6 | 0 | 13.8 |
| 2 | 0.30 | 0.11 | 0.31 | 0.47 | 0.51 | 24 | 4 | 12.5 |
| 3 | 1.84 | 1.43 | 1.67 | 3.48 | 7.94 | 69 | 14 | 26.6 |
| 4 | 3.81 | 2.47 | 3.76 | 6.97 | 11.42 | 163 | 40 | 23.4 |
| 5 | 7.37 | 6.83 | 5.19 | 18.50 | 27.24 | 379 | 95 | 19.4 |
| 6 | 10.92 | 8.46 | 10.48 | 28.06 | 30.74 | 807 | 222 | 13.5 |
| 7 | 25.44 | 28.45 | 15.94 | 78.97 | 123.02 | 1,686 | 467 | 15.1 |
| 8 | 40.73 | 41.24 | 33.80 | 119.63 | 148.54 | 2,974 | 876 | 13.7 |

![AI gecikme](visualization_outputs/ai_latency_vs_depth.png)
![AI karmasiklik](visualization_outputs/ai_computational_complexity.png)

### Taktik senaryolar

Dogru cevap kumesi 4 yari-hamlelik kesin aramayla (zorla kazanc/kayip) hesaplandi.

| Senaryo | Dogru hamle(ler) | D1 | D2 | D3 | D4 | D6 | D8 |
|---|---|---|---|---|---|---|---|
| Win in 1 (vertical) | [3] | OK | OK | OK | OK | OK | OK |
| Win in 1 (horizontal) | [3] | OK | OK | OK | OK | OK | OK |
| Win in 1 (diagonal) | [3] | OK | OK | OK | OK | OK | OK |
| Block (vertical) | [3] | OK | OK | OK | OK | OK | OK |
| Block (horizontal) | [3] | OK | OK | OK | OK | OK | OK |
| Block (diagonal) | [3] | OK | OK | OK | OK | OK | OK |
| Win before block | [0] | OK | OK | OK | OK | OK | OK |
| Avoid trap square | [0, 1, 3, 4, 5, 6] | OK | OK | OK | OK | OK | OK |
| Double threat (win in 3) | [2, 5] | OK | OK | OK | OK | OK | OK |
| **Dogruluk** | | **%100** | **%100** | **%100** | **%100** | **%100** | **%100** |

![Senaryolar](visualization_outputs/ai_scenarios.png)

### Turnuva

Her eslesme 10 farkli rastgele acilistan (4 yari-hamle), her acilis renkler degistirilerek iki kez oynandi. Toplam 420 oyun. Kazanan oyunlarda ilk oyuncunun kazanma orani: %66.

| Eslesme | 1. derinlik galibiyet | 2. derinlik galibiyet | Beraberlik |
|---|---|---|---|
| D2 vs D2 | 4 | 4 | 12 |
| D2 vs D3 | 8 | 9 | 3 |
| D2 vs D4 | 5 | 11 | 4 |
| D2 vs D5 | 7 | 11 | 2 |
| D2 vs D6 | 5 | 12 | 3 |
| D2 vs D8 | 5 | 13 | 2 |
| D3 vs D3 | 9 | 9 | 2 |
| D3 vs D4 | 5 | 10 | 5 |
| D3 vs D5 | 6 | 12 | 2 |
| D3 vs D6 | 5 | 13 | 2 |
| D3 vs D8 | 2 | 15 | 3 |
| D4 vs D4 | 8 | 8 | 4 |
| D4 vs D5 | 8 | 10 | 2 |
| D4 vs D6 | 7 | 11 | 2 |
| D4 vs D8 | 6 | 8 | 6 |
| D5 vs D5 | 7 | 7 | 6 |
| D5 vs D6 | 10 | 7 | 3 |
| D5 vs D8 | 5 | 11 | 4 |
| D6 vs D6 | 9 | 9 | 2 |
| D6 vs D8 | 7 | 9 | 4 |
| D8 vs D8 | 8 | 8 | 4 |

![Turnuva](visualization_outputs/tournament_heatmap.png)

## AI kalitesi - kusursuz cozucuye karsi

Hakem: Pascal Pons connect4 solver (c4solver -a, 7x6.book). Sadece kritik pozisyonlar (hamle secimi oyunun teorik sonucunu degistirebiliyorsa) sayilir. v1 = onceki motor (`legacy_ai_v1.py`), v2 = yeni motor.

### Acilis kitabi

| Motor | Giris | Hatali | Sonucu degistiren |
|---|---|---|---|
| v1 | 12 | 5 | 4 |
| v2 | 57 | 0 | 0 |

### Hamle kalitesi - Gercekci oyun pozisyonlari (159 kritik pozisyon)

| Motor | Optimal % | Sonucu koruyan % | Hata % | Erken % | Orta % | Gec % | Ort. sure (ms) |
|---|---|---|---|---|---|---|---|
| v1 D2 | 63 | 72 | 28 | 70 | 66 | 93 | 1.1 |
| v1 D4 | 67 | 76 | 24 | 77 | 76 | 74 | 17.6 |
| v1 D6 | 70 | 78 | 22 | 76 | 74 | 93 | 185.0 |
| v2 D2 | 72 | 80 | 20 | 73 | 82 | 96 | 0.3 |
| v2 D4 | 78 | 84 | 16 | 82 | 82 | 96 | 2.4 |
| v2 D6 | 82 | 86 | 14 | 78 | 92 | 100 | 12.9 |
| v2 D8 | 86 | 91 | 9 | 89 | 88 | 100 | 49.2 |

### Hamle kalitesi - Rastgele oyun pozisyonlari (189 kritik pozisyon)

| Motor | Optimal % | Sonucu koruyan % | Hata % | Erken % | Orta % | Gec % | Ort. sure (ms) |
|---|---|---|---|---|---|---|---|
| v1 D2 | 67 | 77 | 23 | 59 | 86 | 97 | 1.2 |
| v1 D4 | 70 | 80 | 20 | 61 | 90 | 100 | 14.9 |
| v1 D6 | 76 | 84 | 16 | 70 | 90 | 100 | 196.2 |
| v2 D2 | 78 | 84 | 16 | 70 | 90 | 100 | 0.3 |
| v2 D4 | 81 | 88 | 12 | 75 | 95 | 100 | 1.7 |
| v2 D6 | 79 | 86 | 14 | 70 | 95 | 100 | 9.8 |
| v2 D8 | 81 | 86 | 14 | 71 | 95 | 100 | 43.2 |

![AI kalitesi](visualization_outputs/ai_quality.png)

### Kusursuz rakibe karsi

Cozucuye gore berabere olan acilislardan baslayip beraberligi koruyabilme orani (her acilis iki renkle).

| Motor | Oyun | Beraberligi koruma % | Kayba kadar ort. hamle |
|---|---|---|---|
| v1 D6 | 20 | 5 | 33.1 |
| v2 D4 | 20 | 10 | 31.2 |
| v2 D6 | 20 | 5 | 33.7 |
| v2 D8 | 20 | 5 | 35.3 |

### v2 - v1 karsilasmalari

| Eslesme | v2 galibiyet | v1 galibiyet | Beraberlik |
|---|---|---|---|
| v2 D2 - v1 D2 | 12 | 5 | 3 |
| v2 D4 - v1 D4 | 16 | 1 | 3 |
| v2 D6 - v1 D6 | 14 | 4 | 2 |
| v2 D8 - v1 D6 | 18 | 2 | 0 |

## Ag performansi

Socket.IO tasima katmani: **websocket**. Protokol karsilastirmasinda iki uc nokta da veritabanina dokunmaz; fark yalnizca protokol maliyetidir.

| Olcum | n | Ortalama | Medyan | p95 | p99 | Jitter (ms) |
|---|---|---|---|---|---|---|
| WebSocket latency_ping | 500 | 1.640 | 1.564 | 1.963 | 3.369 | 0.291 |
| REST GET /health | 500 | 1.924 | 1.894 | 2.298 | 3.008 | 0.195 |

| Islem | Ortalama (ms) | p95 (ms) | Hata |
|---|---|---|---|
| ws_create_game | 2.03 | 2.41 | 0 |
| rest_leaderboard | 2.18 | 2.62 | 0 |
| rest_active_games | 1.63 | 2.05 | 0 |
| rest_login | 66.59 | 91.76 | 0 |
| rest_signup_validation | 1.75 | 2.15 | 0 |

![Protokol](visualization_outputs/protocol_comparison.png)
![Islemler](visualization_outputs/operation_latency.png)
![Mesaj boyutu](visualization_outputs/payload_vs_latency.png)

### Eszamanlilik

| Istemci | REST istek/sn | REST ort (ms) | REST hata % | WS istek/sn | WS ort (ms) | WS hata % |
|---|---|---|---|---|---|---|
| 1 | 447 | 2.24 | 0.00 | 729 | 1.37 | 0.00 |
| 5 | 693 | 7.21 | 0.00 | 1405 | 3.56 | 0.00 |
| 10 | 697 | 14.33 | 0.00 | 1465 | 6.82 | 0.00 |
| 20 | 712 | 28.02 | 0.00 | 1459 | 13.70 | 0.00 |
| 50 | 684 | 72.68 | 0.00 | 1274 | 39.18 | 0.00 |
| 100 | 656 | 150.76 | 0.00 | 1081 | 92.17 | 0.00 |

![Eszamanlilik](visualization_outputs/concurrency_analysis.png)

### Eszamanli oyunlar

Her oda iki WebSocket istemcisi; rastgele yasal hamlelerle tam oyun.

| Oyun | Baglanti | Tamamlanan | Hamle RTT ort (ms) | p95 (ms) | p99 (ms) | Hamle/sn |
|---|---|---|---|---|---|---|
| 1 | 2 | 1/1 | 1.99 | 2.49 | 2.61 | 40 |
| 10 | 20 | 10/10 | 3.76 | 9.00 | 12.78 | 286 |
| 25 | 50 | 25/25 | 12.64 | 29.06 | 39.03 | 543 |
| 50 | 100 | 50/50 | 44.30 | 84.68 | 109.28 | 655 |

![Eszamanli oyunlar](visualization_outputs/concurrent_games.png)

## Locust yuk testi

Profiller: Casual %30, Active %50, Power %20 (REST API).

| Kullanici | Istek | Hata % | Istek/sn | Medyan (ms) | Ortalama (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| 50 | 4577 | 0.00 | 38.4 | 3 | 10 | 68 | 100 |
| 100 | 9038 | 0.00 | 75.8 | 3 | 12 | 68 | 170 |
| 200 | 18049 | 0.00 | 151.5 | 3 | 19 | 86 | 380 |

![Locust](visualization_outputs/locust_load.png)

## GUI kare hizi

Gercek ana dongu (60 FPS siniri), ekransiz SDL surucusu; kareler arasi sure.

| Durum | Ort. FPS | p99 kare (ms) | En uzun kare (ms) | >33 ms kare |
|---|---|---|---|---|
| Bos | 62.2 | 17.1 | 19.4 | 0 / 249 |
| AI (D8) ararken | 47.0 | 21.8 | 21.9 | 0 / 52 |

