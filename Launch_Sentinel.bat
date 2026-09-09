@echo off
title EmailSentinel: Priority Inbox Monitor
cd /d "%~dp0"
cls

echo ======================================================================
echo                  EMAILSENTINEL: LIVE INBOX MONITOR
echo                       Priority Triage HUD
echo ======================================================================
echo.

"C:\Users\daddy\miniconda3\python.exe" email_sentinel.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] EmailSentinel exited with code: %ERRORLEVEL%
    pause
)
