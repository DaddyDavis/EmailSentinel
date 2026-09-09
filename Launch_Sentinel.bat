@echo off
title EmailSentinel: Priority Inbox Monitor
cd /d "%~dp0"
start "EmailSentinel: Priority Inbox Monitor" "%SystemRoot%\System32\conhost.exe" --title "EmailSentinel: Priority Inbox Monitor" "C:\Users\daddy\miniconda3\python.exe" "%~dp0email_sentinel.py"
