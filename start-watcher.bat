@echo off
title FirstMate Watcher
echo ===================================================
echo Starting FirstMate Watcher Daemon (Relay + Fleet)...
echo ===================================================
cd /d C:\AIOS\firstmate
wsl -d Ubuntu -u gray -- bash -c cd /mnt/c/AIOS/firstmate && while true; do ./bin/fm-watch.sh; sleep 5; done
