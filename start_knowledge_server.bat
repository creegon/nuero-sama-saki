@echo off
chcp 65001 >nul
title 知识库服务
echo ========================================
echo   知识库服务 (进程隔离模式)
echo ========================================
echo.
echo 此窗口运行知识库服务，请保持打开
echo 按 Ctrl+C 停止服务
echo.

cd /d "%~dp0"
call venv\Scripts\activate.bat

python knowledge\server.py

pause
