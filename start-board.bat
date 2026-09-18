@echo off
title FirstMate Fleet Board (Bearings Lavish)
echo ===================================================
echo Launching FirstMate Bearings Fleet Board...
echo ===================================================
cd /d C:\AIOS\firstmate

powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 4387 -ErrorAction SilentlyContinue)) { wsl -d Ubuntu -u gray -- systemctl --user start firstmate-board.service; Start-Sleep -Seconds 2 }"

start "" "http://127.0.0.1:4387/session/dfcd2e184dd18f6b"

echo.
echo Fleet Board is live: http://127.0.0.1:4387/session/dfcd2e184dd18f6b
echo Standalone file:     C:\AIOS\firstmate\bearings-board.html
echo.
