# Connect Four Pro — Kurulum ve Çalıştırma Rehberi

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
| `run client` | Oyunu açar. AI'ya karşı oynamak için sunucu gerekmez |
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

Güncel kod `claude/python-to-unity-migration-mUVdC` dalındadır (henüz `main`'e birleştirilmedi).

**Repo bilgisayarınızda zaten varsa:**

```bat
cd C:\yol\ConnectFourPro
git fetch origin
git checkout claude/python-to-unity-migration-mUVdC
git pull
```

**Sıfırdan:**

```bat
git clone -b claude/python-to-unity-migration-mUVdC https://github.com/erenyildiz23/ConnectFourPro.git
cd ConnectFourPro
```

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
2. **Yapay Zekaya Karşı** → Kolay (D2), Orta (D4) veya Zor (D8)
3. Sütunun üstüne tıklayarak taşınızı bırakın (siz kırmızısınız ve ilk siz başlarsınız).

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
4. Oyun başlar; maç sonunda ELO değişimi ve hamle analizi gösterilir.
5. İsterseniz 4. bir pencereyle lobiden **İzle** diyerek seyirci olarak bağlanabilirsiniz.
6. Menüdeki **Maç Geçmişi** ekranında kayıtlı maçlarınızı görebilirsiniz.

Online oyundan "Menü" ile çıkmak hükmen yenilgi sayılır (iki kez basmak gerekir). Bağlantınız koparsa istemci otomatik olarak yeniden bağlanır; 30 saniye içinde dönmezseniz rakibiniz hükmen kazanır.

## 7. Başka bilgisayarlarla oynama

**Aynı ağda (ev/okul Wi-Fi):**
1. Sunucu bilgisayarında IP adresini öğrenin: `ipconfig` → "IPv4 Address" (ör. `192.168.1.20`).
2. Sunucu ilk açıldığında Windows Güvenlik Duvarı izin sorarsa **Özel ağlar** için izin verin. Sormazsa 5000 numaralı TCP portuna gelen bağlantılara izin veren bir kural ekleyin.
3. Diğer bilgisayarda istemciyi sunucunun adresiyle başlatın:
   ```bat
   python gui_app.py 192.168.1.20:5000
   ```

**İnternet üzerinden (ngrok):**
1. Sunucu bilgisayarında [ngrok](https://ngrok.com/) kurun ve `ngrok http 5000` komutunu çalıştırın.
2. Verilen adresle bağlanın: `python gui_app.py https://abc123.ngrok-free.app`

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

**Tüm testler** (250 test, ~40 sn) için **ayrı** bir test veritabanı oluşturun. Testler bu veritabanını her testte boşaltır; gerçek `connect4` veritabanınızı kesinlikle kullanmayın.

```bat
"C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres connect4_test
set TEST_DATABASE_URL=postgresql://postgres:SIFRENIZ@localhost/connect4_test
pytest
pytest --cov          REM kapsam raporuyla
```

`TEST_DATABASE_URL` erişilemezse veritabanı gerektiren testler "skipped" olarak atlanır. Sonunda `250 passed` görmelisiniz.

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

Repodaki eski `src\dist\ConnectFourPro.exe` **eski kodla** derlenmiştir. Yenisini proje klasöründe, etkin sanal ortamda oluşturun:

```bat
venv\Scripts\activate
build_exe.bat
```

- Çıktı: `src\dist\ConnectFourPro.exe`
- EXE varsayılan olarak `localhost:5000` adresine bağlanır.
- Başka bir sunucu için bir kısayol oluşturup "Hedef" alanının sonuna adresi ekleyin, ör. `...\ConnectFourPro.exe 192.168.1.20:5000`.
- AI'ya karşı oynamak için sunucu gerekmez.

---

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
| Girişte "Sunucuya bağlanılamadı" | Sunucu çalışmıyor veya adres yanlış (`python gui_app.py ADRES`) |
| `Address already in use` / port 5000 dolu | Başka bir program 5000'i kullanıyor: `set CONNECT4_PORT=5001` ile sunucuyu başlatın, istemciyi `python gui_app.py localhost:5001` ile açın |
| Diğer bilgisayar bağlanamıyor | Güvenlik duvarında 5000 numaralı TCP portunu açın; iki bilgisayarın aynı ağda olduğunu kontrol edin |
| Testlerde çok sayıda "skipped" | `TEST_DATABASE_URL` ayarlanmamış veya veritabanı yok |
