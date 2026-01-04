@echo off
REM 禁用知识库启动脚本 - 用于诊断 ChromaDB 问题

echo ========================================
echo   Neuro-like AI - NO KNOWLEDGE MODE
echo   (Knowledge Base Disabled)
echo ========================================

cd /d %~dp0

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] venv activated
) else (
    echo [WARN] venv not found, using global Python
)

echo.
echo Setting DISABLE_KNOWLEDGE=true...
set DISABLE_KNOWLEDGE=true

echo Starting main.py without knowledge base...
echo ========================================
echo.

python -u main.py -s

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo   ERROR: Program exited with code %ERRORLEVEL%
    echo ========================================
    echo.
)

pause
