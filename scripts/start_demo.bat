@echo off
echo 🚀 Starting Deriv Odd/Even Demo Trading Bot
echo    DEMO MODE ONLY - No real money at risk
echo    Press Ctrl+C to stop gracefully
echo --------------------------------------------------

cd /d "%~dp0\.."
python src\main.py --mode full
