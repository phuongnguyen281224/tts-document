@echo off
REM Script de chay TTS tu command line de dang hon.
REM Vui long goi script tu thu muc cua du an.
IF NOT EXIST ".\venv\Scripts\python.exe" (
    echo [!] Khong tim thay .\venv\Scripts\python.exe. Vui long chay lenh nay tu thu muc goc cua du an.
    exit /b 1
)
.\venv\Scripts\python.exe tts_cli.py %*
