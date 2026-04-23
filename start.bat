@echo off
title YouTube Downloader
echo.
echo  ============================================
echo   يوتيوب داونلودر - جاري التشغيل...
echo  ============================================
echo.
echo  الموقع سيفتح على: http://localhost:5000
echo  لإيقاف التشغيل اضغط Ctrl+C
echo.

cd /d "%~dp0"
start "" "http://localhost:5000"
python app.py

pause
