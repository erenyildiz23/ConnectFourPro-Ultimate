@echo off
REM ============================================================================
REM Connect Four Pro - calistirma kisayollari (Windows cmd / PowerShell)
REM
REM   run.bat web              sunucu + Unity WebGL oyunu tarayicida (http://localhost:5000/play/)
REM   run.bat build-web        Unity WebGL build'i al (Unity CLI gerekir, docs\KURULUM.md)
REM   run.bat client [ADRES]   Python (pygame) istemcisini ac (ADRES: orn. 192.168.1.20:5000)
REM   run.bat server           sunucuyu baslat (online mod)
REM   run.bat online           sunucu + iki Python oyuncu penceresi (tek bilgisayarda deneme)
REM   run.bat test             Python testlerini calistir (once: setup.bat --dev)
REM   run.bat test-cs          C# (Unity'siz) testlerini calistir (.NET 8 SDK gerekir)
REM
REM Ayarlar proje kokundeki .env dosyasindan okunur (setup.bat olusturur).
REM Git Bash / WSL / macOS / Linux icin: ./run.sh
REM ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

REM Python gerektirmeyen komutlar
if /i "%~1"=="build-web" goto buildweb
if /i "%~1"=="test-cs" goto testcs

set "VPY=%~dp0venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Sanal ortam bulunamadi. Once kurulum yapin: setup.bat
    exit /b 1
)

if /i "%~1"=="web" goto web
if /i "%~1"=="client" goto client
if /i "%~1"=="server" goto server
if /i "%~1"=="online" goto online
if /i "%~1"=="test" goto test
goto usage

:buildweb
where unity >nul 2>nul
if errorlevel 1 (
    echo Unity CLI bulunamadi. Kurulum: docs\KURULUM.md - Unity istemcisi
    exit /b 1
)
unity build unity --target WebGL --execute-method ConnectFourPro.EditorTools.ProjectSetup.BuildWebGL
exit /b %ERRORLEVEL%

:testcs
dotnet test tests\csharp
exit /b %ERRORLEVEL%

:web
if not exist "unity\Build\WebGL\index.html" if "%CONNECT4_WEB_BUILD%"=="" echo Uyari: unity\Build\WebGL bulunamadi. Once build alin: run.bat build-web
start "Connect Four - Sunucu" /d "%~dp0src" "%VPY%" server.py
"%VPY%" scripts\wait_for_server.py
if errorlevel 1 (
    echo Sunucu baslamadi; "Connect Four - Sunucu" penceresindeki hataya bakin.
    exit /b 1
)
REM .env'deki port
pushd src
for /f "delims=" %%P in ('call "%VPY%" -c "import config; print(config.SERVER_PORT)"') do set "WEBPORT=%%P"
popd
if "%WEBPORT%"=="" set "WEBPORT=5000"
start "" "http://localhost:%WEBPORT%/play/"
echo Oyun tarayicida acildi: http://localhost:%WEBPORT%/play/
echo Ayni agdaki cihazlar: http://^<bu-bilgisayarin-IP'si^>:%WEBPORT%/play/
echo Bitince "Connect Four - Sunucu" penceresini kapatin.
exit /b 0

:client
cd src
"%VPY%" gui_app.py %2
exit /b %ERRORLEVEL%

:server
cd src
"%VPY%" server.py
exit /b %ERRORLEVEL%

:online
start "Connect Four - Sunucu" /d "%~dp0src" "%VPY%" server.py
"%VPY%" scripts\wait_for_server.py
if errorlevel 1 (
    echo Sunucu baslamadi; "Connect Four - Sunucu" penceresindeki hataya bakin.
    exit /b 1
)
start "Connect Four - Oyuncu 1" /d "%~dp0src" "%VPY%" gui_app.py
start "Connect Four - Oyuncu 2" /d "%~dp0src" "%VPY%" gui_app.py
echo Sunucu ve iki oyuncu ayri pencerelerde acildi.
echo Bitince "Connect Four - Sunucu" penceresini kapatin.
exit /b 0

:test
"%VPY%" -m pytest %2 %3 %4 %5
exit /b %ERRORLEVEL%

:usage
echo Kullanim:
echo   run.bat web              sunucu + Unity WebGL oyunu tarayicida
echo   run.bat build-web        Unity WebGL build'i al
echo   run.bat test-cs          C# testlerini calistir
echo   run.bat client [ADRES]   Python istemcisini ac
echo   run.bat server           sunucuyu baslat
echo   run.bat online           sunucu + iki oyuncu penceresi
echo   run.bat test             testleri calistir
exit /b 1
