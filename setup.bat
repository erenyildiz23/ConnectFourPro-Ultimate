@echo off
REM ============================================================================
REM Connect Four Pro - tek komutla kurulum (Windows cmd / PowerShell / cift tik)
REM
REM   setup.bat            calisma zamani paketleri + (istege bagli) veritabani
REM   setup.bat --dev      + test ve benchmark paketleri
REM   setup.bat --no-db    veritabani adimini atla (sadece AI'ya karsi / misafir)
REM
REM Git Bash / WSL / macOS / Linux icin: ./setup.sh
REM ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "DEV=0"
set "PASS_ARGS="
:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--dev" (
    set "DEV=1"
) else (
    set "PASS_ARGS=%PASS_ARGS% %1"
)
shift
goto parse
:parsed

echo == Python araniyor
set "PY="
for %%C in ("py -3.12" "py -3.13" "py -3.11" "py -3.10" "python") do (
    if not defined PY (
        %%~C -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>&1 && set "PY=%%~C"
    )
)
if not defined PY (
    echo   [!!] Python 3.10 - 3.13 bulunamadi.
    echo        https://www.python.org/downloads/ adresinden Python 3.12 kurun ve
    echo        kurulumda "Add python.exe to PATH" secenegini isaretleyin.
    goto fail
)
for /f "delims=" %%V in ('%PY% --version 2^>^&1') do echo   [OK] %%V (%PY%)

echo == Sanal ortam (venv)
if exist "venv\Scripts\python.exe" (
    echo   [OK] venv zaten var
) else (
    %PY% -m venv venv
    if errorlevel 1 (
        echo   [!!] venv olusturulamadi
        goto fail
    )
    echo   [OK] venv olusturuldu
)
set "VPY=%~dp0venv\Scripts\python.exe"

echo == Paketler yukleniyor (birkac dakika surebilir)
"%VPY%" -m pip install --quiet --upgrade pip
"%VPY%" -m pip install --quiet -r src\requirements.txt
if errorlevel 1 (
    echo   [!!] Paketler yuklenemedi ^(internet baglantisini kontrol edin^)
    goto fail
)
if "%DEV%"=="1" (
    "%VPY%" -m pip install --quiet -r requirements-dev.txt
    if errorlevel 1 (
        echo   [!!] Gelistirme paketleri yuklenemedi
        goto fail
    )
)
echo   [OK] Paketler yuklendi

"%VPY%" scripts\setup_env.py %PASS_ARGS%
if errorlevel 1 goto fail
call :maybe_pause
exit /b 0

:fail
echo.
echo Kurulum tamamlanamadi. Ayrintilar icin docs\KURULUM.md dosyasina bakin.
call :maybe_pause
exit /b 1

:maybe_pause
REM Cift tiklayarak acildiysa pencere hemen kapanmasin
echo %cmdcmdline% | find /i "/c" >nul && pause
exit /b 0
