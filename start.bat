@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech (GPT-SoVITS) - one-click start
rem  - guards against double-click: detects an already-running
rem    service (port 8060) or a starting watchdog, then exits.
rem  - kills leftover tts_api python from an old run, then starts
rem    the watchdog (tts_service\tts_watchdog.ps1), which launches
rem    python and auto-restarts the service if it crashes (3s).
rem  - waits until /health is up, then opens the browser.
rem ============================================================
setlocal
title WenZiQuDong TTS - Start
set "ROOT=%~dp0"
set "PIDFILE=%ROOT%tts_service\tmp\tts_watchdog.pid"
if not defined TTS_DEVICE set "TTS_DEVICE=cuda"

echo ============================================
echo   WenZiQuDong TTS (GPT-SoVITS)  -  port 8060
echo ============================================
echo.

rem ---------- 1) already running on 8060 ? ----------
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8060/health' -TimeoutSec 3; $c = Get-NetTCPConnection -LocalPort 8060 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; Write-Output ('Service already running (PID ' + $c.OwningProcess + '), roles: ' + ($r.ready_roles -join ',')); exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo  Service already running - no need to start again.
    echo  Double-clicking again will NOT create a second service.
    timeout /t 5 >nul 2>nul
    exit /b 0
)

rem ---------- 2) watchdog alive (service still loading) ? ----------
powershell -NoProfile -Command "if (Test-Path '%PIDFILE%') { $j = Get-Content '%PIDFILE%' -Raw | ConvertFrom-Json; if ($j.watchdog) { $wp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.watchdog) -ErrorAction SilentlyContinue; if ($wp -and $wp.Name -eq 'powershell.exe' -and $wp.CommandLine -match 'tts_watchdog') { Write-Output ('Watchdog alive (PID ' + $j.watchdog + '), service is loading'); exit 0 } } }; exit 1"
if %errorlevel% equ 0 (
    echo  Service is starting - first model load takes 5-10 minutes.
    echo  Please wait and do not double-click again.
    timeout /t 5 >nul 2>nul
    exit /b 0
)

rem ---------- 3) clean up leftover tts_api python from an old run ----------
echo Starting service...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'tts_api' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if exist "%PIDFILE%" del /f /q "%PIDFILE%"

rem ---------- 4) launch watchdog (minimized, auto-restart on crash) ----------
echo Starting watchdog (auto-restart on crash, 3s delay)...
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tts_service\tts_watchdog.ps1"

rem ---------- 5) wait until service is ready, then open browser ----------
echo.
echo  Waiting for the service to become ready (first load: 5-10 min)...
set /a tries=0
:waitloop
set /a tries+=1
if %tries% gtr 60 goto notready
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8060/health' -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 goto ready
timeout /t 10 /nobreak >nul 2>&1
goto waitloop

:ready
echo  Service is ready.
echo    UI      : http://127.0.0.1:8060/
echo    health  : http://127.0.0.1:8060/health
echo    stop    : run stop.bat
timeout /t 2 >nul 2>nul
start "" "http://127.0.0.1:8060/"
exit /b 0

:notready
echo  Service is not ready yet after 10 minutes.
echo  Open http://127.0.0.1:8060/health in your browser later.
echo  See logs under tts_service\tmp\ (tts_python.log.err) for details.
exit /b 0
