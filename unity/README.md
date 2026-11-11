# Connect Four Pro Ultimate — Unity / C# istemcisi

Unity 6 LTS ile yazılmış, **WebGL** (tarayıcı) için derlenen istemci. Python sunucusu (`src/server.py`) hiç değiştirilmeden kullanılır; derlenen oyunu da aynı sunucu `/play/` adresinden sunar. Kurulum ve build adımları: [docs/KURULUM.md → 11](../docs/KURULUM.md#11-unity-tarayıcı-istemcisi).

## Klasörler ve derlemeler (assembly)

| Klasör | Assembly | Unity'ye bağımlı mı? | Python karşılığı |
|---|---|---|---|
| `Assets/Scripts/Core` | `ConnectFourPro.Core` | Hayır | `game_core.py` |
| `Assets/Scripts/AI` | `ConnectFourPro.AI` | Hayır | `ai_vs_human.py` |
| `Assets/Scripts/Net/Protocol` | `ConnectFourPro.Protocol` | Hayır | `network_client.py` (protokol), JSON |
| `Assets/Scripts/Net`, `Game`, `UI` | `ConnectFourPro.Runtime` | Evet | `network_client.py`, `gui_app.py` |
| `Assets/Editor` | `ConnectFourPro.Editor` | Evet (yalnızca Editor) | `build_exe.bat` |

Unity'ye bağımlı olmayan üç assembly, `tests/csharp` altındaki .NET test projesine doğrudan bağlanır. Böylece Unity olmadan `dotnet test` ile test edilir. Uygulama mantığı (`AppController`, `GameSocket`, `AIRunner`, `ServerConfig`) da aynı testlerde, `tests/csharp/stubs` altındaki küçük bir UnityEngine taklidine karşı derlenip sınanır; `ApiClient`, taşıma katmanları ve `UI/` yalnızca Unity derlemesiyle doğrulanır.

## Önemli tasarım kararları

**AI, Python motoruyla birebir aynı.** `AIEngine.cs`, `ai_vs_human.py`'nin satır satır karşılığıdır. Aynı bitboard yerleşimi, aynı hamle sıralaması, aynı transpozisyon tablosu kuralları ve aynı değerlendirme ağırlıkları kullanılır. `scripts/export_ai_vectors.py` Python motorundan 110 arama ve 200 değerlendirme kaydeder. C# testleri, aynı hamleyi ve skoru almanın ötesinde **aynı düğüm ve budama sayısını** bekler. Bu yüzden iki motor arasındaki en küçük fark bile testi kırar. CI vektörleri her çalıştırmada yeniden üretir ve repodakiyle karşılaştırır.

**WebGL'de thread yok → arama karelere bölünür.** `AIEngine.BeginSearch()` adım adım bir arama döndürür. Her `Step()` kök düğümün bir çocuğunu arar. `Game/AIRunner.cs` her karede en fazla ~8 ms adım atar, böylece AI düşünürken animasyonlar akmaya devam eder. Online maçlardaki hamle analizi (isabet oranı) de aynı zamanlayıcıyla, AI hamlesinden sonra sırayla yürütülür.

**Socket.IO iki taşıma katmanıyla çalışır** (`ISocketTransport`):
- **WebGL:** `Plugins/WebGL/SocketBridge.jslib`, tarayıcıdaki resmi `socket.io-client` 4.7.5'i kullanır. Kütüphane `WebGLTemplates/ConnectFour/socket.io.min.js` içinde sabit sürüm olarak gelir. Olaylar C#'a `SendMessage` ile `"olay\n{json}"` biçiminde ulaşır.
- **Editor / masaüstü:** `Net/Protocol/SocketIOClient.cs`, `ClientWebSocket` üzerinde bağımlılıksız bir Engine.IO v4 / Socket.IO v5 istemcisidir. Arka plan thread'inden gelen olaylar `EditorSocketTransport` tarafından ana thread'e taşınır.

`GameSocket`, `network_client.py` ile aynı davranır: önce bağlanır, sonra bekleyen isteği gönderir; bağlantı koparsa yeniden bağlanınca odaya kendiliğinden geri katılır.

**Aynı origin.** WebGL'de sunucu adresi sayfanın adresidir (`ServerConfig`), bu yüzden CORS gerekmez. Yerel geliştirmede başka bir sunucuya bağlanmak için `?server=http://ADRES:5000` kullanılır. Bu parametre yalnızca sayfa `localhost` / `127.0.0.1` / `[::1]` adresinden sunuluyorsa veya development build'de dikkate alınır; diğer durumlarda yok sayılır. Hedef sunucu varsayılan olarak yalnızca kendi origin'ini kabul ettiğinden orada `CORS_ALLOWED_ORIGINS` da ayarlanmalıdır. Aksi halde `https://site/play/?server=https://saldırgan` biçimindeki bir bağlantı, adres çubuğunda gerçek site görünürken kullanıcı adı ve şifreyi başka bir sunucuya gönderirdi.

**Arayüz koddan kurulur.** `GameBootstrap`, uGUI hiyerarşisini `UI/UIKit.cs` ile oluşturur. Sahnede tek bir nesne bulunur; bu nesne sahneye eklenmemişse bile oyun başlarken otomatik oluşturulur. Bunun nedenleri: sahne/prefab YAML'ı Git'te çakışma üretmez, kod incelemesinde okunabilir ve Unity olmadan da derlenip denetlenebilir. Yazı tipi Unity'nin yerleşik `LegacyRuntime.ttf`'idir; Türkçe karakterleri içerir ve TMP kurulumu gerektirmez. Yerleşim 1280×720 referans çözünürlüğündedir; `CanvasScaler` ekrana göre ölçekler.

**Durum makinesi `gui_app.py` ile aynı.** `Game/AppController.cs` ekranları, kimlik doğrulamayı, AI oyununu, online oyunu, seyirci modunu, hükmen yenilgi onayını, maç sonu analizini, rövanşı (`rematch_*` olayları), sunucunun hamle süresi geri sayımını (`move_time`, `turn_seconds_left`), hükmen nedenini (`detail`: `timeout` / `disconnect` / `leave`), bitmiş oyunun sonucunu geri katılımda gösterilmesini ve kendi bağlantı kaybını yönetir. Klavye: `1`–`7` hamle, `Esc` geri (`UI/Keys.cs`). Rövanş ve hamle süresi eski sunucularla da çalışır: ilgili alanlar yoksa özellik kapalı kalır. Sunucu olayları geldikçe hamle geçmişinin uzunluğuna bakılarak eski olay, kendi hamlenin yankısı, rakip hamlesi ve kaçırılmış hamle ayrımı yapılır.

## WebGL ayarları (`Editor/WebOptimizer.cs`)

| Ayar | Değer | Neden |
|---|---|---|
| Sıkıştırma | Gzip | LAN'da `http://` ile de çalışsın diye. Brotli yalnızca HTTPS/localhost'ta çalışır |
| Decompression Fallback | Kapalı | Flask `/play`, `.gz` dosyalarını `Content-Encoding: gzip` ile gönderir |
| Managed Stripping | High | `link.xml` kendi assembly'lerimizi korur (`SendMessage` hedefleri) |
| Exceptions | Explicitly Thrown Only | Kod `try/catch` kullanır (JSON, AI iptali) |
| IL2CPP | Optimize Size, .NET Standard 2.1 | Daha küçük wasm |
| Kare hızı | `targetFrameRate = -1`, vSync 0 | Tempoyu tarayıcı belirler |

`codeOptimization` (Disk Size LTO) `Library/` altında saklanır ve repoya geçmez. Bu yüzden `ProjectSetup.BuildWebGL` her build'de bu ayarı yeniden uygular.

## Geliştirme

```bash
dotnet test tests/csharp                                         # Unity'siz testler
CONNECT4_TEST_SERVER=http://localhost:5000 dotnet test tests/csharp   # + gerçek sunucuya karşı Socket.IO
python scripts/export_ai_vectors.py                              # AI değişirse altın vektörleri yenile
```

Python AI'da (`src/ai_vs_human.py`) yapılan her değişiklik `AIEngine.cs`'e de yansıtılmalıdır. Vektörleri yeniden üretip `dotnet test` çalıştırmak, iki motorun hâlâ birebir aynı olduğunu doğrular.
