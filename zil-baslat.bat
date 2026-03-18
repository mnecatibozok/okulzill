@echo off
title Zil Sistemi Sunucusu
cd /d "%~dp0"
set HTML_FILE=zil-programi-v9.html

:: HTML dosyası kontrolü
if not exist "%HTML_FILE%" (
    echo [HATA] %HTML_FILE% bulunamadi!
    echo Dosyanin bu klasorde oldugunu kontrol edin.
    pause & exit /b 1
)

:: Python kontrolü
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [HATA] Python kurulu degil!
        echo https://www.python.org/downloads/ adresinden indirin.
        pause & exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

:: Eski sunucu süreçlerini durdur
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im py.exe >nul 2>&1
timeout /t 1 /nobreak >nul

:: Port dosyasını temizle
if exist "zil-port.txt" del "zil-port.txt"

:: Sunucuyu arka planda gizli başlat (siyah ekran görünmez)
powershell -WindowStyle Hidden -Command "Start-Process '%PYTHON_CMD%' -ArgumentList 'sunucu.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"

:: Sunucunun hazır olmasını bekle — port dosyası oluşana kadar (maks 10 saniye)
set /a WAIT=0
:WAITLOOP
timeout /t 1 /nobreak >nul
set /a WAIT+=1
if exist "zil-port.txt" goto PORTFOUND
if %WAIT% GEQ 10 goto FALLBACK
goto WAITLOOP

:PORTFOUND
:: Port dosyasından numarayı oku
set /p ZIL_PORT=<zil-port.txt

:: Chrome varsa ön planda aç, yoksa varsayılan tarayıcıyı kullan
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --new-window "http://localhost:%ZIL_PORT%/%HTML_FILE%"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --new-window "http://localhost:%ZIL_PORT%/%HTML_FILE%"
) else (
    start "" "http://localhost:%ZIL_PORT%/%HTML_FILE%"
)
goto END

:FALLBACK
:: Port alınamadı, bilinen port ile dene
echo [UYARI] Sunucu port dosyasi 10 saniyede olusmadi, 8765 deneniyor...
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --new-window "http://localhost:8765/%HTML_FILE%"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --new-window "http://localhost:8765/%HTML_FILE%"
) else (
    start "" "http://localhost:8765/%HTML_FILE%"
)

:END
exit
