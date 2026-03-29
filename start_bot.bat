@echo off
REM Clean up and start the MeetFlow bot
echo [1] Killing all Python processes...
taskkill /F /IM python.exe 2>nul
echo.

echo [2] Waiting 45 seconds for Telegram to release connection...
timeout /t 45 /nobreak
echo.

echo [3] Starting MeetFlow bot...
python main.py
pause
