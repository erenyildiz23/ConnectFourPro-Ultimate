@echo off
REM ============================================================================
REM Connect Four Pro - calistirma kisayollari (Windows cmd / PowerShell)
REM
REM   run.bat client [ADRES]   oyunu ac (ADRES: uzak sunucu, orn. 192.168.1.20:5000)
REM   run.bat server           sunucuyu baslat (online mod)
REM   run.bat online           sunucu + iki oyuncu penceresi (tek bilgisayarda deneme)
REM   run.bat test             testleri calistir (once: setup.bat --dev)
REM
REM Ayarlar proje kokundeki .env dosyasindan okunur (setup.bat olusturur).
REM Git Bash / WSL / macOS / Linux icin: ./run.sh
REM ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "VPY=%~dp0venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Sanal ortam bulunamadi. Once kurulum yapin: setup.bat
    exit /b 1
)

if /i "%~1"=="client" goto client
if /i "%~1"=="server" goto server
if /i "%~1"=="online" goto online
if /i "%~1"=="test" goto test
goto usage

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
echo   run.bat client [ADRES]   oyunu ac
echo   run.bat server           sunucuyu baslat
echo   run.bat online           sunucu + iki oyuncu penceresi
echo   run.bat test             testleri calistir
exit /b 1
