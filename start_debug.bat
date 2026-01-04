@echo off
REM 调试模式启动脚本 - 显示完整错误信息

echo ========================================
echo   Neuro-like AI - DEBUG MODE
echo ========================================

cd /d %~dp0

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] venv activated
) else (
    echo [WARN] venv not found, using global Python
)

echo.
echo Starting main.py in debug mode...
echo ========================================
echo.

REM 直接运行，不跳过服务检测，显示所有输出
python -u main.py --debug

echo.
echo ========================================
echo   Program exited. Exit code: %ERRORLEVEL%
echo ========================================
echo.

pause
