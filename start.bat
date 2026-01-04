@echo off
echo ========================================
echo   Neuro-like AI - Activating venv
echo ========================================

cd /d %~dp0

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] venv activated
) else (
    echo [WARN] venv not found, using global Python
)

echo.
echo Starting main.py...
echo ========================================
python main.py -s

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo   ERROR: Program exited with code %ERRORLEVEL%
    echo ========================================
    echo.
)

pause
