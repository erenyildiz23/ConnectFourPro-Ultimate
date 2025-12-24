@echo off
echo ============================================
echo   Connect Four Pro - EXE Builder
echo ============================================
echo.

REM PyInstaller yüklü mü kontrol et
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] PyInstaller yukleniyor...
    pip install pyinstaller
)

echo.
echo [INFO] EXE olusturuluyor...
echo.

cd src

REM Tek dosya EXE oluştur (GUI için)
pyinstaller --onefile --windowed ^
    --name "ConnectFourPro" ^
    --icon "../assets/icon.ico" ^
    --add-data "game_core.py;." ^
    --add-data "ai_vs_human.py;." ^
    --hidden-import=pygame ^
    --hidden-import=requests ^
    --hidden-import=python_socketio ^
    --hidden-import=engineio ^
    gui_app.py

echo.
echo ============================================
if exist "dist\ConnectFourPro.exe" (
    echo [SUCCESS] EXE olusturuldu!
    echo Konum: src\dist\ConnectFourPro.exe
) else (
    echo [ERROR] EXE olusturulamadi!
)
echo ============================================

cd ..
pause
