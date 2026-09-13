@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech (GPT-SoVITS) - one-click start
rem  - PORT: FIXED at 18062. This project's public API address must never
rem    change, so it does NOT auto-switch ports. 18062 sits OUTSIDE the
rem    Windows dynamic port range (1024-15000 on this machine), so the OS
rem    never hands it to a random outbound connection. Sibling project
rem    duihuamoxing uses 8061/18060, fully separated. If 18062 is taken
rem    by another program, start.bat reports it and exits - it NEVER
rem    kills another program.
rem    Emergency override only (not normal use):
rem        set TTS_API_PORT=8070
rem  - guards against double-click: detects an already-running copy
rem    of THIS service or a starting watchdog, then exits.
rem  - if an orphaned copy of THIS project runs without watchdog,
rem    stops it and restarts under watchdog protection.
rem  - kills leftover python of THIS copy only (path-matched), then
rem    starts the watchdog (tts_service\tts_watchdog.ps1) which
rem    auto-restarts the service if it crashes (3s).
rem  - waits until /health is up, then opens the browser.
rem ============================================================
setlocal
title WenZiQuDong TTS - Start
set "ROOT=%~dp0"
set "PIDFILE=%ROOT%tts_service\tmp\tts_watchdog.pid"
set "PORTFILE=%ROOT%tts_service\tmp\port.txt"
if not defined TTS_DEVICE set "TTS_DEVICE=cuda"

rem ---------- 0) FIXED port ----------
rem This project always serves on 18062 - the public API address must stay
rem stable for integrators. No auto-switching, no port scan, no port.txt
rem lookup. Override only if 18062 is genuinely unusable on a new machine.
if not defined TTS_API_PORT set "TTS_API_PORT=18062"

echo ============================================
echo   WenZiQuDong TTS (GPT-SoVITS)  -  port %TTS_API_PORT%
echo ============================================
echo.

rem ---------- 1) is anything answering on our port? ----------
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; exit 0 } catch { exit 1 }"
if not %errorlevel% equ 0 goto start_fresh

rem ---------- 1a) is it THIS copy of the service? ----------
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; if ($r.service -eq 'wenziqudong-tts') { exit 0 }; Write-Output ('  foreign service on port: ' + $r.service); exit 9 } catch { exit 1 }"
if %errorlevel% equ 9 (
    echo  Port %TTS_API_PORT% is held by a DIFFERENT program. This script will NOT kill it.
    echo  This project uses a FIXED port and does NOT switch automatically.
    echo  Fix A: stop that program, then run start.bat again to use port %TTS_API_PORT%.
    echo  Fix B: run this project on another port for this session:
    echo     set TTS_API_PORT=8070
    echo     start.bat
    timeout /t 15 >nul
    exit /b 1
)

rem ---------- 1b) ours: only exit if a live watchdog protects it ----------
powershell -NoProfile -Command "if (Test-Path '%PIDFILE%') { $j = Get-Content '%PIDFILE%' -Raw | ConvertFrom-Json; if ($j.watchdog) { $wp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.watchdog) -ErrorAction SilentlyContinue; if ($wp -and $wp.Name -eq 'powershell.exe' -and $wp.CommandLine -match 'tts_watchdog') { exit 0 } } }; exit 1"
if %errorlevel% equ 0 (
    echo  Service already running - no need to start again.
    echo  Watchdog is protecting it - auto-restart on crash.
    echo  Double-clicking again will NOT create a second service.
    timeout /t 5 >nul 2>nul
    exit /b 0
)
echo  Orphaned copy of this service detected - running without watchdog.
echo  Stopping it and restarting under watchdog protection...

:start_fresh
rem ---------- 2) watchdog alive - service still loading? ----------
powershell -NoProfile -Command "if (Test-Path '%PIDFILE%') { $j = Get-Content '%PIDFILE%' -Raw | ConvertFrom-Json; if ($j.watchdog) { $wp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.watchdog) -ErrorAction SilentlyContinue; if ($wp -and $wp.Name -eq 'powershell.exe' -and $wp.CommandLine -match 'tts_watchdog') { Write-Output ('Watchdog alive (PID ' + $j.watchdog + '), service is loading'); exit 0 } } }; exit 1"
if %errorlevel% equ 0 (
    echo  Service is starting - first model load takes 5-10 minutes.
    echo  Please wait and do not double-click again.
    timeout /t 5 >nul 2>nul
    exit /b 0
)

rem ---------- 3) clean up leftover python of THIS copy only ----------
echo Starting service...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*%ROOT%tts_service\tts_api.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if exist "%PIDFILE%" del /f /q "%PIDFILE%"

rem ---------- 3b) after our own leftovers are gone, is the port still taken? ----------
rem Fixed port means we never drift. If a foreign program holds 18062, refuse
rem to start and tell the user, instead of silently moving to another port.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %TTS_API_PORT% -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo  ERROR: port %TTS_API_PORT% is still in use by another program.
    echo  This project uses a FIXED port and will NOT switch automatically.
    echo  Fix A: stop the program holding port %TTS_API_PORT%, then run start.bat again.
    echo  Fix B: run on another port for this session:
    echo     set TTS_API_PORT=8070
    echo     start.bat
    timeout /t 20 >nul 2>nul
    exit /b 1
)

rem ---------- 4) launch watchdog in a visible console window ----------
rem The window shows live service logs; closing that window stops the service.
echo Opening the service window - live logs there, closing it stops the service...
start "WenZiQuDong TTS" powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tts_service\tts_watchdog.ps1"

rem ---------- 5) wait until service is ready, then open browser ----------
echo.
echo  Waiting for the service to become ready - first load: 5-10 min...
set /a tries=0
:waitloop
set /a tries+=1
if %tries% gtr 60 goto notready
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 goto ready
timeout /t 10 /nobreak >nul 2>nul
goto waitloop

:ready
echo  Service is ready.
echo    UI      : http://127.0.0.1:%TTS_API_PORT%/
echo    health  : http://127.0.0.1:%TTS_API_PORT%/health
echo    stop    : run stop.bat - or just close the service window
>"%PORTFILE%" echo %TTS_API_PORT%
timeout /t 2 >nul 2>nul
start "" "http://127.0.0.1:%TTS_API_PORT%/"
exit /b 0

:notready
echo  Service is not ready yet after 10 minutes.
echo  Open http://127.0.0.1:%TTS_API_PORT%/health in your browser later.
echo  See logs under tts_service\tmp\ for details.
exit /b 0
