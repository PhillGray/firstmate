@echo off
title FirstMate Fleet Console (Herdr)
echo ========================================================
echo   FIRSTMATE AGENT FLEET CONSOLE (HERDR)
echo ========================================================
echo Launching Herdr multiplexer in WSL...
cd /d C:\AIOS\firstmate
wsl -d Ubuntu -u gray -- bash -c "cd /mnt/c/AIOS/firstmate && herdr"
