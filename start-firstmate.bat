@echo off
title FirstMate
echo ===================================================
echo Starting FirstMate (Primary Agent Session)...
echo ===================================================
cd /d C:\AIOS\firstmate
wsl -d Ubuntu -u gray -- bash -lc "cd /mnt/c/AIOS/firstmate && claude"
