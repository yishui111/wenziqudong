@echo off
chcp 936 >nul
title 配音角色校对台（ref_text 校对）
set "ROOT=%~dp0..\.."
set "PY=%ROOT%runtime\py312\python.exe"
if not exist "%PY%" set "PY=python"

echo ============================================================
echo   配音角色校对台（ref_text 校对）
echo   页面: http://127.0.0.1:18067/
echo   Python: %PY%
echo ============================================================
echo.
echo   前置: 18062 语音服务要先起来（双击 wenziqudong 目录里的
echo         "一键启动文字驱动语音.bat"）。没起也能开页面，只是
echo         不能现场合成。
echo.
echo   关掉这个黑窗口就是停服务。
echo ============================================================
echo.

start "" http://127.0.0.1:18067/
"%PY%" "%~dp0server.py"
pause
