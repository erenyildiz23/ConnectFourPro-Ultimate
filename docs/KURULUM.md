# Connect Four Pro Ultimate — Kurulum ve Çalıştırma Rehberi

## Hızlı kurulum (önerilen)

Python 3.12 kurulu olduktan sonra (bkz. bölüm 1) proje klasöründe **tek komut** yeterlidir.

| Terminal | Kurulum | Çalıştırma |
|---|---|---|
| Windows **cmd** (veya `setup.bat` dosyasına çift tık) | `setup.bat` | `run.bat client` |
| Windows **PowerShell** | `.\setup.bat` | `.\run.bat client` |
| **Git Bash**, WSL, macOS, Linux | `./setup.sh` | `./run.sh client` |

Kurulum betiği şunları yapar:
1. Python 3.10–3.13'ü bulur.
2. Sanal ortamı (`venv`) oluşturur ve paketleri yükler.
3. Online mod isteyip istemediğinizi sorar. "Evet" derseniz PostgreSQL kullanıcı adı ve şifresini ister (şifre yazılırken görünmez).
4. `connect4` ve `connect4_test` veritabanlarını yoksa oluşturur, tabloları kurar. Mevcut `connect4` veritabanınız varsa aynen kullanılır.
5. Ayarları proje kökündeki **`.env`** dosyasına yazar.

Bundan sonra ortam değişkeni yazmanıza veya sanal ortamı etkinleştirmenize gerek kalmaz. Uygulama ayarları `.env` dosyasından okur; terminalde ayarladığınız bir değişken her zaman önceliklidir. `.env` git'e eklenmez, çünkü şifre içerir.

| Komut (Windows'ta `run.bat`, bash'te `./run.sh`) | Ne yapar |
|---|---|
| `run build-web` | Unity WebGL build'ini alır (bir kez ve Unity kodu değişince; bkz. bölüm 11) |
| `run web` | Sunucuyu başlatır ve Unity oyununu tarayıcıda açar: `http://localhost:5000/play/` |
| `run test-cs` | C# testlerini çalıştırır (.NET 8 SDK gerekir) |
| `run client` | Python/Pygame istemcisini açar. AI'ya karşı oynamak için sunucu gerekmez |
| `run client 192.168.1.20:5000` | Başka bilgisayardaki sunucuya bağlanır |
| `run server` | Online mod için sunucuyu başlatır |
| `run online` | Sunucuyu ve iki oyuncu penceresini birlikte açar (tek bilgisayarda deneme) |
| `run test` | Testleri çalıştırır; önce `setup --dev` ile test paketlerini kurun |

Kurulum seçenekleri:
- `setup --dev`: test ve benchmark paketlerini de kurar.
- `setup --no-db`: veritabanı adımını atlar (yalnızca AI'ya karşı ve misafir modu).

Betiği istediğiniz kadar tekrar çalıştırabilirsiniz: mevcut kurulumu ve `.env` ayarlarını tanır.

Aşağıdaki bölümler aynı adımları elle yapmak isteyenler ve sorun giderme içindir.

---

Komutlar **Windows** için yazılmıştır; Linux/Mac karşılıkları her adımda ayrıca verilmiştir.

| Ne yapmak istiyorum? | Gerekenler | Bölüm |
|---|---|---|
| AI'ya karşı oynamak | Python | 1, 2, 3 |
| Online oynamak (giriş, lobi, ELO) | Python + PostgreSQL | 1–6 |
| Başka bilgisayarla oynamak | + ağ ayarı | 7 |
| Testleri çalıştırmak | + test veritabanı | 8 |
| Performans ölçümlerini tekrarlamak | + benchmark veritabanı | 9 |
| EXE oluşturmak | Windows | 10 |
| Unity (tarayıcı) istemcisini derlemek | Unity 6 LTS + WebGL modülü | 11 |

---

## 1. Gerekli programlar

1. **Python 3.12** (3.10–3.13 arası çalışır): https://www.python.org/downloads/
   Kurulumda **"Add python.exe to PATH"** kutusunu işaretleyin.
2. **Git**: https://git-scm.com/download/win
3. **PostgreSQL** (yalnızca online mod için): https://www.postgresql.org/download/windows/
   Kurulumda belirlediğiniz `postgres` kullanıcısının şifresini not edin.

Kontrol (yeni bir terminalde):

```bat
python --version
git --version
```

`python` bulunamazsa `py --version` deneyin. O zaman aşağıdaki komutlarda `python` yerine `py -3.12` yazın.

## 2. Kodu indirme ve kurulum

```bat
git clone https://github.com/erenyildiz23/ConnectFourPro-Ultimate.git
cd ConnectFourPro-Ultimate
```

Repo bilgisayarınızda zaten varsa: `git pull`.

**Sanal ortam ve bağımlılıklar** (proje klasöründe, bir kez):

```bat
python -m venv venv
venv\Scripts\activate
pip install -r src\requirements.txt
```

- PowerShell kullanıyorsanız etkinleştirme komutu `venv\Scripts\Activate.ps1` olur. "running scripts is disabled" hatası alırsanız bir kez şunu çalıştırın: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- Linux/Mac: `python3 -m venv venv && source venv/bin/activate && pip install -r src/requirements.txt`

Satırın başında `(venv)` görünüyorsa sanal ortam etkindir. **Her yeni terminalde** `venv\Scripts\activate` komutunu tekrar çalıştırmanız gerekir.

## 3. AI'ya karşı oynama (sunucu gerekmez)

```bat
cd src
python gui_app.py
```

1. **Misafir Olarak Devam**
2. **Yapay Zekaya Karşı** → Kolay (D2), Orta (D4) veya Zor (D8). İsterseniz aynı ekrandaki **İlk hamle: Sen / AI** düğmesiyle ilk hamleyi AI'ya verin (varsayılan: ilk siz başlarsınız).
3. Sütunun üstüne tıklayarak veya `1`–`7` tuşlarıyla taşınızı bırakın (siz her zaman kırmızısınız).

Oyun sırasında **Geri Al** (`U`) son hamlenizi ve AI'nın cevabını geri alır; **Yeni Oyun** aynı zorlukta yeniden başlatır ve ilk hamleyi yapan tarafı değiştirir; `Esc` menüye döner. Kolay seviye kasıtlı olarak ara sıra rastgele bir hamle oynar (ayrıntı: [AI.md](AI.md)). Ses efektleri pygame istemcisinde çalışma anında üretilir; `M` tuşu veya menüdeki **Ses** düğmesi açıp kapatır. Ses kartı olmayan makinede `CONNECT4_MUTE=1` ortam değişkeniyle sessiz başlatın (ses aygıtı hiç açılmaz).

Sunucu çalışmıyorsa giriş/kayıt ekranında "Sunucuya bağlanılamadı" yazar; bu normaldir, misafir modu yine çalışır.

## 4. Veritabanı (online mod için, bir kez)

**Mevcut `connect4` veritabanınız varsa aynen kullanabilirsiniz.** Yeni sunucu tabloları otomatik günceller; eski hesaplar, ELO puanları ve maç geçmişi korunur. Eski şifreler ilk girişte güvenli formata yükseltilir.

**Yoksa** oluşturun:
- **pgAdmin ile:** Databases → sağ tık → Create → Database → adı `connect4`.
- **Komut satırıyla:**
  ```bat
  "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres connect4
  ```
  Sürüm numarası (16) sizin kurulumunuza göre değişebilir.

> **Güvenlik:** Eski koddaki veritabanı şifresi (`230198`) git geçmişinde açıkça duruyor. Repo herkese açıksa PostgreSQL şifrenizi değiştirin (pgAdmin → Query Tool):
> `ALTER USER postgres PASSWORD 'yeni-guclu-sifre';`

## 5. Sunucuyu başlatma

**Terminal 1** (proje klasöründe):

```bat
venv\Scripts\activate
set DATABASE_URL=postgresql://postgres:SIFRENIZ@localhost/connect4
cd src
python server.py
```

- **PowerShell'de** ortam değişkeni şöyle verilir: `$env:DATABASE_URL = "postgresql://postgres:SIFRENIZ@localhost/connect4"`
- **Linux/Mac'te:** `export DATABASE_URL=postgresql://postgres:SIFRENIZ@localhost/connect4`
- `set` satırında tırnak kullanmayın. Şifrede `@`, `:`, `/`, `#` gibi karakterler varsa URL kodlamasıyla yazın (örneğin `@` → `%40`).
- Ortam değişkeni yalnızca o terminal penceresinde geçerlidir; terminali kapatınca yeniden vermeniz gerekir.

Başarılı başlangıçta logda şunlar görünür:

```
CONNECT FOUR PRO SERVER v3.0
Dinleniyor: http://0.0.0.0:5000
Veritabani: bagli
```

`Veritabani: YOK` yazıyorsa şifreyi, veritabanı adını ve PostgreSQL servisinin çalıştığını kontrol edin (bkz. Sorun giderme). Tarayıcıda http://localhost:5000/health adresi `"database": true` göstermelidir.

## 6. Online oynama (aynı bilgisayarda iki oyuncu)

**Terminal 2** ve **Terminal 3** (her birinde):

```bat
venv\Scripts\activate
cd src
python gui_app.py
```

1. İki pencerede farklı kullanıcı adlarıyla **Kayıt Ol** (3–20 karakter; harf, rakam, `_ . -`).
2. 1. pencere: **Online Lobi → + Yeni Oyun** → oda kodu görünür.
3. 2. pencere: **Online Lobi** → odanın yanındaki **Katıl**.
4. Oyun başlar (ilk hamleyi 1. pencere, kırmızı yapar); maç sonunda ekran başlığında sonuç, durum satırında ELO değişimi ve hamle analizi gösterilir.
   Oyun bitince iki pencerede de **Rovans** düğmesine (veya `R` tuşuna) basarsanız aynı odada yeni oyun başlar; koltuklar yer değiştirir, yani önceki oyunun sarısı bu kez kırmızı olur ve ilk hamleyi yapar. Rakip odadan ayrıldıysa düğme pasifleşir.
5. İsterseniz 4. bir pencereyle lobiden **İzle** diyerek seyirci olarak bağlanabilirsiniz.
6. Menüdeki **Maç Geçmişi** ekranında kayıtlı maçlarınızı görebilirsiniz.

Online oyundan "Menü" ile (veya `Esc` ile) çıkmak hükmen yenilgi sayılır (iki kez basmak gerekir). Bağlantınız koparsa istemci otomatik olarak yeniden bağlanır; 30 saniye içinde dönmezseniz rakibiniz hükmen kazanır. Oyun siz yokken bittiyse döndüğünüzde sonucu (nedeniyle birlikte) görürsünüz. Hükmen yenilgi nedeni iki tarafa da yazılır: süre doldu, bağlantı koptu veya oyundan ayrıldı.

**Hamle süresi (isteğe bağlı).** Sunucu varsayılan olarak hamle süresi uygulamaz. Açmak için sunucuyu başlatırken `MOVE_TIME_SECONDS` verin (ör. `set MOVE_TIME_SECONDS=30`; kalıcı olması için `.env` dosyasına `MOVE_TIME_SECONDS=30` yazın, Docker'da `docker-compose.yml` `.env`'deki `MOVE_TIME_SECONDS` değerini konteynere iletir; `MOVE_TIME_GRACE_SECONDS` iletilmez, varsayılan kalır). Süre dolarsa sırası gelen hükmen kaybeder; `MOVE_TIME_GRACE_SECONDS` (varsayılan 2 sn) gecikme payıdır. Her iki istemci de sırası gelenin kalan süresini gösterir; son 10 saniyede sayaç uyarı rengine döner. Rakibin bağlantısı kopukken süre işlemez. Sunucuyu yeniden başlatmak gerekir.

## 7. Başka bilgisayarlarla oynama

**Aynı ağda (ev/okul Wi-Fi):**
1. Sunucu bilgisayarında IP adresini öğrenin: `ipconfig` → "IPv4 Address" (ör. `192.168.1.20`).
2. Sunucu ilk açıldığında Windows Güvenlik Duvarı izin sorarsa **Özel ağlar** için izin verin. Sormazsa 5000 numaralı TCP portuna gelen bağlantılara izin veren bir kural ekleyin.
3. Diğer cihazda (bilgisayar, telefon, tablet) tarayıcıyla `http://192.168.1.20:5000/play/` adresini açın. Kurulum gerekmez.
   Pygame istemcisiyle bağlanmak için:
   ```bat
   python gui_app.py 192.168.1.20:5000
   ```

**İnternet üzerinden (ngrok):**
1. Sunucu bilgisayarında [ngrok](https://ngrok.com/) kurun ve `ngrok http 5000` komutunu çalıştırın.
2. Verilen adresle bağlanın: tarayıcıda `https://abc123.ngrok-free.app/play/` veya `python gui_app.py https://abc123.ngrok-free.app`

Adres her seferinde komut satırında vermek yerine `CONNECT4_SERVER` ortam değişkeniyle de ayarlanabilir.

## 8. Testleri çalıştırma

```bat
venv\Scripts\activate
pip install -r requirements-dev.txt
```

**Veritabanı gerektirmeyen birim testleri** (~5 sn):

```bat
pytest tests\unit
```

**Tüm testler** (554 test, ~100 sn) için **ayrı** bir test veritabanı oluşturun. Testler bu veritabanını her testte boşaltır; gerçek `connect4` veritabanınızı kesinlikle kullanmayın.

```bat
"C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres connect4_test
set TEST_DATABASE_URL=postgresql://postgres:SIFRENIZ@localhost/connect4_test
pytest
pytest --cov          REM kapsam raporuyla
```

`TEST_DATABASE_URL` erişilemezse veritabanı gerektiren testler "skipped" olarak atlanır. Sonunda `554 passed` görmelisiniz.

**C# testleri** (Unity istemcisinin oyun motoru, AI, protokol; Unity gerekmez): [.NET 8 SDK](https://dotnet.microsoft.com/download) kurun, sonra `dotnet test tests\csharp`. Socket.IO testleri için önce sunucuyu başlatıp `set CONNECT4_TEST_SERVER=http://localhost:5000` ayarlayın.

## 9. Performans ölçümleri (isteğe bağlı)

```bat
"C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres connect4_bench
set DATABASE_URL=postgresql://postgres:SIFRENIZ@localhost/connect4_bench
cd benchmarks
python run_all.py --quick      REM ~3 dk, kontrol amaçlı
python run_all.py              REM ~30 dk, tam ölçüm
```

- Betik sunucuyu kendisi başlatır (port 5055) ve oluşturduğu test hesaplarını sonda siler.
- Sonuçlar `benchmarks\RESULTS.md` ve `benchmarks\visualization_outputs\*.png` dosyalarına yazılır.
- Ölçüm sırasında bilgisayarda ağır başka iş çalıştırmayın; sonuçlar etkilenir.
- AI kalitesini kusursuz çözücüye karşı ölçmek (`--solver-dir`) için C++ derleyicisi gerekir; Windows'ta en kolayı WSL'dir (bkz. `benchmarks/README.md`).

## 10. EXE oluşturma (Windows)

EXE depoda tutulmaz; proje klasöründe, etkin sanal ortamda oluşturun:

```bat
venv\Scripts\activate
build_exe.bat
```

- Çıktı: `src\dist\ConnectFourPro.exe`
- EXE varsayılan olarak `localhost:5000` adresine bağlanır.
- Başka bir sunucu için bir kısayol oluşturup "Hedef" alanının sonuna adresi ekleyin, ör. `...\ConnectFourPro.exe 192.168.1.20:5000`.
- AI'ya karşı oynamak için sunucu gerekmez.

## 11. Unity (tarayıcı) istemcisi

Unity istemcisi `unity/` klasöründedir ve WebGL olarak derlenir. Derlenen oyunu Python sunucusu `/play/` adresinden sunar; oyuncuların bir şey kurması gerekmez. Mimari ve geliştirme notları: [`unity/README.md`](../unity/README.md).

### 11.1 Unity CLI ve Editor (bir kez)

Unity'nin komut satırı aracı (Unity CLI) Editor'ü, lisansı ve build'i yönetir. Unity Hub ile de aynı adımlar yapılabilir.

```powershell
# Windows PowerShell
$env:UNITY_CLI_CHANNEL='beta'; irm https://public-cdn.cloud.unity3d.com/hub/prod/cli/install.ps1 | iex
```
```bash
# macOS / Linux
curl -fsSL https://public-cdn.cloud.unity3d.com/hub/prod/cli/install.sh | UNITY_CLI_CHANNEL=beta bash
```

Yeni bir terminal açın, sonra:

```bash
unity --version
unity auth login                     # tarayıcıda Unity hesabınızla giriş
unity license activate               # ücretsiz Personal lisans
unity install lts --module webgl --yes --accept-eula   # Unity 6 LTS + WebGL modülü (birkaç GB)
unity editors --installed            # kurulumu doğrulayın
```

### 11.2 Projeyi ilk kez açma

```bash
unity open unity                     # veya Unity Hub > Add > proje klasöründeki "unity" klasörü
```

İlk açılışta Unity `ProjectSettings/`, `Packages/` ve `.meta` dosyalarını oluşturur. Ardından proje kendini kurar:
- `Assets/Scenes/Main.unity` sahnesi oluşturulur (menü: **Tools > Connect Four > Build Scenes**).
- WebGL ayarları uygulanır (menü: **Tools > Apply Web Release Settings**): Gzip sıkıştırma, kod ayıklama, `ConnectFour` web şablonu.

Oluşan dosyaları bir kez commit'leyin (`Library/`, `Temp/`, `Build/` zaten `.gitignore`'da):

```bash
git add unity && git commit -m "Unity proje ayarlari ve meta dosyalari"
```

**Editor'de deneme:** sunucuyu başlatın (`run server`), Unity'de `Main` sahnesini açıp **Play**'e basın. Editor `CONNECT4_SERVER` ortam değişkenine, yoksa `http://localhost:5000` adresine bağlanır.

### 11.3 WebGL build ve oynama

```bash
run build-web        # = unity build unity --target WebGL --execute-method ConnectFourPro.EditorTools.ProjectSetup.BuildWebGL
run web              # sunucu + http://localhost:5000/play/
```

Build `unity/Build/WebGL` klasörüne yazılır (Editor'den: **Tools > Connect Four > Build WebGL**). Başka bir klasör kullanmak için `CONNECT4_WEB_BUILD` ayarlayın.

**GitHub Actions'tan indirilen build'i oynatmak:** başarılı bir "Unity WebGL" çalışmasının sayfasında en altta **Artifacts → `webgl-build`** zip'ini indirip açın (ör. `C:\ConnectFour\webgl`; içinde `index.html` ve `Build\` olmalı). Sonra terminalinize göre:

| Terminal | Komut |
|---|---|
| PowerShell | `$env:CONNECT4_WEB_BUILD = "C:\ConnectFour\webgl"` ve sonra `.\run.bat web` |
| cmd | `set CONNECT4_WEB_BUILD=C:\ConnectFour\webgl` ve sonra `run.bat web` |
| Git Bash | `CONNECT4_WEB_BUILD=/c/ConnectFour/webgl ./run.sh web` |

Kalıcı olması için proje kökündeki `.env` dosyasına `CONNECT4_WEB_BUILD=C:\ConnectFour\webgl` satırını ekleyebilirsiniz. `index.html`'e çift tıklamak çalışmaz; dosyalar gzip'li olduğu için oyun sunucu üzerinden açılmalıdır.

### 11.4 Claude Code + Unity eklentisi ile canlı düzenleme (isteğe bağlı)

Unity Editor açıkken Claude Code'daki Unity eklentisi Editor'ü komut satırından yönetebilir (nesne ekleme, ayar okuma, C# çalıştırma):

```bash
unity pipeline install   # projeye com.unity.pipeline paketini ekler (bir kez)
unity status             # bağlı Editor'ü gösterir ("ready")
unity command            # Editor'ün sunduğu komutlar
```

### 11.5 GitHub Actions ile otomatik build

`unity/` klasörü değişince GitHub Actions oyunu WebGL olarak derler (GameCI) ve derlenen oyunu Chromium'da, gerçek sunucuya karşı oynatır (`tests/e2e/webgl.spec.mjs`). Build ve ekran görüntüleri **Actions → Unity WebGL → Artifacts** altından indirilebilir (`webgl-build`, `e2e-screenshots`).

Bunun için bir kez *repository secret*'lar eklenmelidir. GitHub'da repo → **Settings → Secrets and variables → Actions → New repository secret**:

**A) Student / Pro / Plus lisansı (seri numaralı, önerilen)**

1. https://id.unity.com → **Subscriptions** (Abonelikler) → "Unity Student" aboneliği → **seri numarasını** kopyalayın. (Unity Hub → Preferences → Licenses altında da görünür.)
2. Üç secret ekleyin:

   | Ad | Değer |
   |---|---|
   | `UNITY_SERIAL` | Seri numarası |
   | `UNITY_EMAIL` | Unity hesabınızın e-postası |
   | `UNITY_PASSWORD` | Unity hesabınızın şifresi |

CI her çalışmada lisansı etkinleştirir ve iş sonunda iade eder.

**B) Personal lisansı**

1. Unity Hub'ı açın, giriş yapın: **Preferences (Tercihler) → Licenses → Add → Get a free personal license**.
2. Oluşan lisans dosyasını bir metin düzenleyiciyle açıp **tüm içeriğini** kopyalayın:
   - Windows: `C:\ProgramData\Unity\Unity_lic.ulf`
   - macOS: `/Library/Application Support/Unity/Unity_lic.ulf`
   - Linux: `~/.local/share/unity3d/Unity/Unity_lic.ulf`
3. Secret'lar: `UNITY_LICENSE` (dosya içeriği), `UNITY_EMAIL`, `UNITY_PASSWORD`.

Sonra:

**Actions → Unity WebGL → Run workflow** ile ilk build'i başlatın (sonrakiler push ile kendiliğinden çalışır).

Her değer **ayrı** bir secret olmalıdır (tek bir secret içinde hepsi çalışmaz). Secret'lar yalnızca GitHub'da şifreli saklanır; loglarda `***` olarak görünür. Secret yoksa iş hata vermez, "atlandı" notuyla geçer. Unity hesabında iki adımlı doğrulama açıksa CI'da giriş başarısız olabilir.

İlk başarılı build, Unity'nin ürettiği proje dosyalarını (`ProjectSettings/`, `Packages/`, `.meta`) `unity-project-files` adlı artifact olarak da yükler; bunlar repoya eklenmelidir (bölüm 11.2'deki commit'in CI karşılığı).

## 12. Docker ile sunucu (internete açık kurulum)

`python server.py` Werkzeug'un geliştirme sunucusunu kullanır; ev ağı ve denemeler için yeterlidir. Sunucuyu kalıcı olarak veya internete açık çalıştıracaksanız [Docker](https://docs.docker.com/get-docker/) ile gunicorn üzerinde çalıştırın. `docker-compose.yml` sunucuyu ve PostgreSQL 16'yı birlikte başlatır; Python veya PostgreSQL kurmanız gerekmez.

```bash
docker compose up --build -d     # sunucu + veritabanı
docker compose logs -f server    # loglar
docker compose down              # durdurur (veritabanı "connect4-db" volume'unda kalır)
```

Sonra http://localhost:5000/health adresi `"database": true` göstermelidir.

- **`SECRET_KEY` zorunludur.** Oturum token'ları bu anahtarla imzalanır. Compose, proje kökündeki `.env` dosyasını okur; `setup` betiğini çalıştırdıysanız anahtar zaten oradadır. Yoksa `.env` dosyasına `SECRET_KEY=uzun-rastgele-bir-deger` satırını ekleyin (üretmek için: `python -c "import secrets; print(secrets.token_hex(32))"`). Anahtar tanımlı değilse `docker compose up` hata verip durur. Anahtarı değiştirirseniz herkesin yeniden giriş yapması gerekir.
- **Veritabanı şifresi:** `.env` dosyasına `POSTGRES_PASSWORD=...` yazarak belirleyin (varsayılan `connect4`; şifre veritabanı ilk oluşturulurken belirlenir). Veritabanı portu dışarıya açılmaz, yalnızca sunucu konteyneri erişir. `.env` içindeki `DATABASE_URL` Docker'da kullanılmaz.
- **Tek worker:** Açık odalar sunucu sürecinin belleğinde tutulur. Birden fazla worker çalışırsa oyuncular farklı süreçlere düşer ve birbirlerinin odasını göremez. Bu yüzden gunicorn tek worker ve çok thread ile çalışır (`-k gthread -w 1 --threads 100`); `-w` değerini artırmayın. Her WebSocket bağlantısı bir thread kullanır; aynı anda 100'den fazla oyuncu bekliyorsanız `.env` dosyasına `GUNICORN_THREADS=200` yazın.
- **Tarayıcı istemcisi:** `unity/Build/WebGL` klasörü konteynere bağlanır. Build'i aldıysanız veya Actions'tan indirip bu klasöre açtıysanız (bölüm 11.3) oyun `http://localhost:5000/play/` adresinde açılır. Klasör yoksa Docker boş bir klasör oluşturur ve `/play/` "WebGL build bulunamadi" yanıtını verir; sunucunun geri kalanı çalışır.
- **Farklı port:** `.env` dosyasına `CONNECT4_PORT=8080` yazın.
- **İnternete açarken HTTPS kullanın.** Sunucu düz HTTP konuşur; kullanıcı adı, şifre ve oturum token'ı şifrelenmeden gider. Sunucuyu doğrudan internete açmayın. Önüne TLS sonlandıran bir ters vekil (Caddy, nginx, Traefik) veya bir tünel (Cloudflare Tunnel, ngrok) koyun. Vekil, WebSocket yükseltmesini (`Upgrade` başlığı) ve özgün `Host` ile `X-Forwarded-Proto` başlıklarını iletmelidir; sunucu tarayıcıdan gelen Socket.IO bağlantısının kendi adresinden geldiğini bu başlıklarla doğrular. Caddy (`reverse_proxy localhost:5000`) ve ngrok bunu kendiliğinden yapar. nginx'te `proxy_set_header Host $host;` ve `proxy_set_header X-Forwarded-Proto $scheme;` satırlarını ekleyin. Vekili değiştiremiyorsanız `.env` dosyasına `CORS_ALLOWED_ORIGINS=https://oyun.example.com` yazın.

Docker olmadan aynı komut (Linux/macOS; gunicorn Windows'ta çalışmaz):

```bash
pip install gunicorn
gunicorn --chdir src -k gthread -w 1 --threads 100 -b 0.0.0.0:5000 wsgi:app
```

---

## 13. İnternette ücretsiz yayın (Render + Supabase)

Herkesin tarayıcıdan oynayabilmesi için sunucunun internette, HTTPS arkasında çalışması gerekir. En düşük maliyetli yol: sunucu [Render](https://render.com)'ın ücretsiz planında, veritabanı [Supabase](https://supabase.com)'in ücretsiz planında. Alan adı gerekmez; Render `https://...onrender.com` adresi verir.

**Ücretsiz planın sınırları:** Sunucu 15 dakika kimse bağlanmazsa uyur; sonraki ilk ziyaretçi yaklaşık bir dakika bekler (uyurken açık oda kalmaz, kayıtlı veriler veritabanında durur). Supabase bir hafta hiç kullanılmayan ücretsiz projeyi duraklatır; panelden tek tıkla geri açılır. Oyuncu sayısı artınca aynı imaj bölüm 12'deki gibi küçük bir VPS'e taşınabilir.

1. **İmaj:** Bu depoyu `main`'e birleştirin. `Docker image` iş akışı, `Unity WebGL` iş akışının son başarılı derlemesini içine koyarak `ghcr.io/KULLANICI/connectfourpro-ultimate:latest` imajını yayınlar (Unity secret'ları tanımlı olmalı, bkz. 11.5).
2. **İmajı herkese açın:** GitHub'da profil → **Packages** → `connectfourpro-ultimate` → **Package settings** → **Change visibility** → **Public**. (Özel bırakırsanız Render'a kayıt defteri kimlik bilgisi eklemeniz gerekir.)
3. **Veritabanı:** Supabase'te yeni bir proje oluşturun ve veritabanı şifresini not edin. **Connect** → **Session pooler** altındaki adresi kopyalayın (`postgresql://postgres.PROJE:SIFRE@...pooler.supabase.com:5432/postgres`). "Direct connection" adresi yalnızca IPv6 üzerinden erişilebildiği için Render'da çalışmaz. Tabloları sunucu ilk açılışta kendisi oluşturur.
4. **Sunucu:** Render'da **New** → **Blueprint** ile bu depoyu seçin; `render.yaml` servisi tanımlar. Sorulduğunda `DATABASE_URL` alanına 3. adımdaki adresi yapıştırın. `SECRET_KEY`'i Render kendisi üretir. `render.yaml` içindeki imaj adresinde kullanıcı adı farklıysa düzeltin.
5. **Kontrol:** `https://ADRESINIZ.onrender.com/health` → `"database": true`. Oyun: `https://ADRESINIZ.onrender.com/play/`.
6. **Otomatik güncelleme (isteğe bağlı):** Render'da servis → **Settings** → **Deploy Hook** adresini kopyalayıp GitHub'da `RENDER_DEPLOY_HOOK_URL` adlı repository secret'ı olarak ekleyin. Böylece her yeni imajdan sonra Render kendiliğinden güncellenir; yoksa Render panelinden **Manual Deploy** gerekir.

Ayarlar `render.yaml` içindedir: `DB_POOL_SIZE=5` (ücretsiz veritabanının bağlantı sınırı için) ve `GUNICORN_THREADS=60`. Sunucu, yönetilen veritabanlarının boşta kapattığı bağlantıları kendisi yeniler (`DB_PING_AFTER_SECONDS`).

**itch.io:** Oyunu itch.io'da tarayıcıda oynanan çok oyunculu bir oyun olarak yayınlamak için bkz. bölüm 14. Bu sunucu orada da gereklidir (odalar, giriş, sıralama).

## 14. itch.io'da yayınlama

itch.io yalnızca statik dosya barındırır: Unity WebGL build'i bir zip olarak yüklenir ve itch.io'nun kendi CDN adresinden (HTTPS) bir iframe içinde açılır. Oyun sunucusu bölüm 13'teki gibi başka yerde (Render) çalışmaya devam eder. Bu durumda oyun sayfası ile sunucu **farklı origin'lerdedir**, bu yüzden üç şey gerekir:

- **Build'e gömülü sunucu adresi.** WebGL şablonundaki `server-config.js` dosyası `window.CF4_SERVER_URL` değerini tanımlar. Depoda bu değer boştur, yani oyun sayfanın kendi adresini kullanır (`/play/` için doğru davranış). itch.io zip'i üretilirken bu dosya sunucunuzun adresiyle yeniden yazılır. Dosya oyun koduyla birlikte yayınlandığı için ona oyun kadar güvenilir; `?server=` parametresinin aksine release build'de de geçerlidir.
- **Sunucuda CORS.** Sunucu, itch.io sayfasının REST (`/login`, `/leaderboard` …) ve Socket.IO isteklerini kabul etmelidir: `CORS_ALLOWED_ORIGINS`.
- **Statik sunucuya uygun build.** Varsayılan build Gzip ile sıkıştırılır ve Decompression Fallback kapalıdır. Bu build, `.gz` dosyalarını `Content-Encoding: gzip` başlığıyla gönderen bir sunucu ister; Flask'in `/play/` rotası bunu yapar. itch.io'nun [HTML5 belgelerine](https://itch.io/docs/creators/html5) göre itch.io da içeriği gzip olan dosyalara bu başlığı ekler (`.br` dosyalarına `br`), yani varsayılan build orada da açılmalıdır. Yine de itch.io build'i **Decompression Fallback açık** alınır: dosyalar `.unityweb` uzantılı olur ve tarayıcı başlığı uygulamazsa Unity'nin yükleyicisi dosyaları JavaScript ile açar. Böylece zip, itch.io CDN'inin ayarı değişse de ya da başlık göndermeyen başka bir statik sunucuda da çalışır; bedeli biraz daha büyük yükleyici ve WebAssembly akışlı derlemenin kapanmasıdır ([Unity belgesi](https://docs.unity3d.com/Manual/webgl-deploying.html)). Varsayılan build (e2e testi, Docker imajı, `/play/`) değişmez.

**Sunucu adresinin önceliği** (`unity/Assets/Scripts/Net/ServerConfig.cs`):

1. `?server=ADRES`, yalnızca sayfa `localhost` / `127.0.0.1` / `[::1]` adresinden sunuluyorsa veya development build'de geçerlidir (yerel geliştirme).
2. `server-config.js` içindeki adres. Mutlak bir `https://host[:port]` adresi olmalıdır; yol, sorgu ve kullanıcı bilgisi içeremez. Sayfa `https` iken `http` bir adres reddedilir, çünkü tarayıcı karışık içeriği (mixed content) zaten engeller. Geçersiz adreste tarayıcı konsoluna `[CF4] CF4_SERVER_URL ...` uyarısı yazılır ve 3. adıma geçilir.
3. Sayfanın kendi adresi.

Böylece itch.io sayfasına eklenen bir `?server=https://saldirgan` parametresi hiçbir etki yaratmaz.

### 14.1 Adımlar

1. **Sunucuyu yayına alın** (bölüm 13). `https://ADRESINIZ.onrender.com/health` → `"database": true` görünmelidir.
2. **Sunucuda `CORS_ALLOWED_ORIGINS` ayarlayın.** Render → servis → **Environment** → `CORS_ALLOWED_ORIGINS` → kaydedin. Servis yeniden başlar. Değer için iki seçenek vardır:
   - **Liste (önerilen):** itch.io HTML5 oyunlarını yalnızca iki CDN adresinden sunar: varsayılan `https://html-classic.itch.zone` ve isteğe bağlı `https://html.itch.zone` ([itch.io duyurusu, 2023](https://itch.io/post/8952630/view-in-topic)). Oyunun `/play/` adresinden de oynanabilmesi için sunucunun kendi adresini de ekleyin, çünkü liste verildiğinde Socket.IO yalnızca listedeki origin'leri kabul eder:
     `CORS_ALLOWED_ORIGINS=https://html-classic.itch.zone,https://html.itch.zone,https://ADRESINIZ.onrender.com`
     Origin'ler tam eşleşir: sonda `/` ve yol yoktur, `http`/`https` farklıdır. itch.io ileride başka bir `*.itch.zone` adresi kullanırsa oyun "Sunucuya bağlanılamadı" der ve konsoldaki CORS hatasında yeni origin görünür; onu listeye ekleyin.
   - **`*`:** Her origin kabul edilir; itch.io adres değiştirse de çalışır. Sunucu çerez kullanmadığı (oturum token'ı JSON gövdesinde ve socket mesajlarında açıkça gönderilir) ve `Access-Control-Allow-Credentials` göndermediği için başka bir site tarayıcınızdaki oturumu kullanamaz. Ancak herhangi bir site ziyaretçilerinin tarayıcısından sunucunuza giriş denemesi ve socket bağlantısı açtırabilir (giriş sınırları `LOGIN_MAX_FAILURES`, `AUTH_IP_MAX_REQUESTS` yine geçerlidir). Listeyi tercih edin.
3. **GitHub'da sunucu adresini tanımlayın.** Repo → **Settings → Secrets and variables → Actions → Variables** sekmesi → **New repository variable**: Ad `CONNECT4_PUBLIC_SERVER_URL`, değer `https://ADRESINIZ.onrender.com` (sonda `/` yok). Bu bir *secret* değil, *variable*'dır: adres zaten oyunun içinde herkese açıktır. Unity secret'ları da tanımlı olmalıdır (bölüm 11.5).
4. **itch.io zip'ini üretin.** `main`'de **Unity WebGL** iş akışı başarıyla bitince (build ve tarayıcı e2e testi geçti) **itch.io WebGL** iş akışı kendiliğinden başlar; hemen denemek için **Actions → itch.io WebGL → Run workflow** (`main` dalı) da kullanılabilir. Bu iş Decompression Fallback açık ikinci bir build alır, `scripts/make_itch_zip.py` ile zip'i üretir ve **Artifacts → `itch-webgl`** olarak yükler. İndirdiğiniz dosyayı açın; içinden çıkan `itch-webgl.zip` itch.io'ya yüklenecek dosyadır (GitHub artifact'leri bir zip daha sarar). Variable tanımlı değilse iş sessizce atlanır. Ayrı bir iş akışı olduğu için buradaki bir hata Docker imajını (bölüm 13) etkilemez.

   *Yerelde (Unity kuruluysa):* Unity'yi `-cf4DecompressionFallback` argümanıyla (veya `CONNECT4_WEBGL_DECOMPRESSION_FALLBACK=1` ortam değişkeniyle) build alın, sonra:

   ```bash
   CONNECT4_WEBGL_DECOMPRESSION_FALLBACK=1 ./run.sh build-web    # Windows cmd: set CONNECT4_WEBGL_DECOMPRESSION_FALLBACK=1 && run.bat build-web
   python scripts/make_itch_zip.py unity/Build/WebGL --server https://ADRESINIZ.onrender.com --out itch-webgl.zip
   ```

   Betik yalnızca standart kütüphaneyi kullanır. Adresi doğrular (mutlak, `https`, sonda `/` yok, kullanıcı/yol/sorgu yok), build klasörünü değiştirmeden bir kopyasını zip'e yazar ve `server-config.js`'i adresinizle doldurur. `index.html` zip'in kökündedir ve itch.io sınırları (1000 dosya, 500 MB, dosya başına 200 MB, 240 karakter yol) denetlenir. Decompression Fallback kapalı (`.gz`) bir build verirseniz hata verir. `--allow-precompressed` bu denetimi atlar; yalnızca itch.io'nun dosyaları `Content-Encoding: gzip` ile sunduğunu kendiniz doğruladıysanız kullanın. Bu build'den sonra `/play/` için tekrar normal build alın (`run build-web`).
5. **itch.io'da proje oluşturun.** https://itch.io/game/new:
   - **Kind of project:** `HTML`.
   - **Uploads → Upload files:** `itch-webgl.zip` → yükleme bitince **This file will be played in the browser** kutusunu işaretleyin.
   - **Embed options:** *Viewport dimensions* `1280 × 720` (oyun 16:9 çizilir ve pencereye sığar). **Mobile friendly** işaretleyin, *Orientation*: `Landscape` (dikey telefonda oyun zaten yan çevirmeyi önerir). **Fullscreen button** işaretleyin. *Automatically start on page load* yerine *Click to launch* seçeneği, mobil kullanıcıların oyunu kendi isteğiyle yüklemesini sağlar (build birkaç MB'tır).
   - Fiyat: HTML oyunlarda yalnızca bağış alınabilir.
   - **Visibility:** test bitene kadar `Draft` (veya `Restricted`) bırakın, sonra **Save**.
6. **Test edin.** Sayfayı açın, F12 → Console: `[App] Hazir (sunucu: https://ADRESINIZ.onrender.com)` görünmelidir. Hesapla giriş yapın, liderlik tablosunu açın, iki ayrı tarayıcıdan (biri gizli pencere) online bir maç oynayın. Render'ın ücretsiz planında sunucu uykudaysa ilk bağlantı yaklaşık bir dakika sürebilir; önce `/health` adresini açarak sunucuyu uyandırabilirsiniz. Her şey çalışınca **Visibility → Public** yapın.

**Güncelleme:** Yeni bir sürüm için 4. adımı tekrarlayın ve itch.io'da eski dosyayı silip yenisini yükleyin (veya aşağıdaki otomatik gönderimi kullanın).

### 14.2 butler ile otomatik gönderim (isteğe bağlı)

İki ayar birlikte tanımlıysa **itch.io WebGL** iş akışı zip'i her seferinde itch.io'nun komut satırı aracı **butler** ile kendiliğinden yükler:

| Ad | Tür | Değer |
|---|---|---|
| `BUTLER_API_KEY` | **secret** | itch.io → Settings → API keys → *Generate new API key* |
| `ITCH_TARGET` | variable | `kullanici/oyun:kanal`, ör. `kullanici/connect-four-pro:html5` (oyun sayfasının adresi: `kullanici.itch.io/connect-four-pro`) |

butler sürümü ve SHA-256 özeti iş akışında sabittir; anahtar yalnızca gönderim adımına verilir ve loglara yazılmaz. İlk gönderimden sonra itch.io'da *Edit game* sayfasında kanalın **This file will be played in the browser** işaretini bir kez kontrol edin. Ayarlardan biri eksikse gönderim adımı atlanır ve zip yine artifact olarak indirilebilir. Anahtar bir loga sızarsa itch.io'da hemen iptal edin.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| `'python' is not recognized` | Python'u PATH seçeneğiyle yeniden kurun veya `py -3.12` kullanın |
| `pip install` sırasında psycopg2 derleme hatası | Python sürümünüzü kontrol edin (3.10–3.13); `python -m pip install --upgrade pip` çalıştırıp tekrar deneyin |
| PowerShell'de "running scripts is disabled" | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Sunucu logunda `Veritabani: YOK` / `Connection refused` | PostgreSQL servisi kapalı: Windows Hizmetler'de "postgresql-x64-16" servisini başlatın |
| `password authentication failed` | `DATABASE_URL` içindeki şifre yanlış |
| `database "connect4" does not exist` | 4. bölümdeki gibi veritabanını oluşturun |
| Girişte "Sunucu veritabanına ulaşamıyor" | Sunucu çalışıyor ama veritabanına bağlanamadı (yukarıdaki iki satıra bakın) |
| Pygame istemcisi ses aygıtı hatası veriyor / sessiz çalışsın istiyorum | `CONNECT4_MUTE=1` ile başlatın; ses aygıtı hiç açılmaz |
| Girişte "Sunucuya bağlanılamadı" | Sunucu çalışmıyor veya adres yanlış (`python gui_app.py ADRES`) |
| `Address already in use` / port 5000 dolu | Başka bir program 5000'i kullanıyor: `set CONNECT4_PORT=5001` ile sunucuyu başlatın, istemciyi `python gui_app.py localhost:5001` ile açın |
| Diğer bilgisayar bağlanamıyor | Güvenlik duvarında 5000 numaralı TCP portunu açın; iki bilgisayarın aynı ağda olduğunu kontrol edin |
| `/play/` adresi `WebGL build bulunamadi` diyor | Önce `run build-web` ile build alın (bölüm 11.3) |
| Tarayıcıda oyun "Unable to parse Build/....gz" hatası veriyor | Build'i Python sunucusu dışında (ör. `python -m http.server`) sunuyorsunuz; gzip dosyaları için `Content-Encoding: gzip` gerekir. `run web` kullanın. itch.io gibi statik sunucular için Decompression Fallback açık build alın (bölüm 14) |
| itch.io'da konsolda "blocked by CORS policy" / giriş "Sunucuya bağlanılamadı" | Sunucuda `CORS_ALLOWED_ORIGINS` ayarlı değil veya listede hatadaki origin yok (bölüm 14.1, 2. adım). Origin tam eşleşmelidir: sonda `/` olmadan |
| itch.io'da oyun kendi sayfasına (`html-classic.itch.zone`) bağlanmaya çalışıyor | Zip `make_itch_zip.py` ile üretilmemiş veya konsolda `[CF4] CF4_SERVER_URL ...` uyarısı var: adres `https://` ile başlamalı (bölüm 14) |
| Actions'ta "itch.io WebGL" işi atlandı | Yalnızca `main`'de, Unity secret'ları ve `CONNECT4_PUBLIC_SERVER_URL` *variable*'ı tanımlıysa çalışır (bölüm 14.1, 3. adım) |
| Actions'ta "Unity WebGL" işi "atlandı" diyor | Secret'lar eksik (bölüm 11.5) |
| Actions'ta Unity lisans hatası | E-posta/şifre doğru olmalı; 2 adımlı doğrulama kapalı olmalı; `UNITY_LICENSE` kullanıyorsanız dosyanın tamamı kopyalanmalı |
| Seri lisansta "activation limit" / `Code 20111` hatası | id.unity.com → Subscriptions → aboneliğiniz → eski aktivasyonları kaldırın (CI normalde her işin sonunda iade eder) |
| PowerShell'de `set ...` yazınca `PositionalParameterNotFound` | PowerShell'de `set` farklı bir komuttur: `$env:AD = "deger"` kullanın |
| `unity: command not found` | Unity CLI kurulumundan sonra yeni bir terminal açın (bölüm 11.1) |
| Unity'de `unity status` bağlanamıyor | Projede derleme hatası varsa Editor "Safe Mode"da açılır; Console'daki hatayı düzeltin. `unity pipeline list` ile kontrol edin |
| Unity Console'da `WebGL modulu bulunamadi` uyarısı | `unity install-modules --module webgl` |
| Testlerde çok sayıda "skipped" | `TEST_DATABASE_URL` ayarlanmamış veya veritabanı yok |
