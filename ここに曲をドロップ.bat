@echo off
chcp 65001 > nul
cd /d "%~dp0"
if "%~1"=="" (
  echo Drop a song file onto this bat icon.
  echo.
  pause
  exit /b 0
)
echo Analyzing: %~nx1
echo.
python chord_transcribe.py "%~1"
echo.
pause
