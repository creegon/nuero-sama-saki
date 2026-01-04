@echo off
chcp 65001 >nul
title Neuro AI - Initial Setup

echo ╔════════════════════════════════════════════════════════════╗
echo ║           Neuro AI Desktop Pet - First Time Setup          ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

set NEURO_DIR=d:\neruo

echo [1/3] Creating Python virtual environment...
cd /d %NEURO_DIR%
python -m venv venv


echo [2/3] Activating venv and installing PyTorch (CUDA 12.4)...
call venv\Scripts\activate.bat
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

echo [3/3] Installing other dependencies...
pip install -r requirements.txt

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                    Setup Complete!                         ║
echo ║         Run start.bat to launch the application           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

pause
