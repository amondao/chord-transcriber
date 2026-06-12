@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting chord-transcriber web app...
echo Open http://127.0.0.1:5000 in your browser.
start "" http://127.0.0.1:5000
python webapp.py
pause
