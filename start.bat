@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech (GPT-SoVITS) - one-click start
rem  Behavior contract (do NOT revert):
rem    - The service runs ONLY when the user starts it with this
rem      script. NOTHING auto-starts it, and NOTHING restarts it
rem      after it stops. The old auto-restart watchdog is gone on
rem      purpose: stopped must mean stopped, permanently.
rem    - PORT: FIXED at 18062. This project's public API address
rem      must never change, so it does NOT auto-switch ports.
rem      18062 sits OUTSIDE the Windows dynamic port range, so the
rem      OS never hands it to a random outbound connection.
rem      Sibling project duihuamoxing uses 8061/18060, separated.
rem      Emergency override only (not normal use):
rem          set TTS_API_PORT=8070
rem    - If 18062 is held by another program: report and exit.
rem      This script NEVER kills another program's process.
rem    - The service runs in a visible window (tts_service\tts_run.ps1)
rem      with live logs. Closing that window stops the service for good.
rem    - Stop for good: stop.bat / close the service window /
rem      the web page "stop service" button. No auto-restart ever.
rem ============================================================
setlocal
title WenZiQuDong TTS - Start
set "ROOT=%~dp0"
set "PIDFILE=%ROOT%tts_service\tmp\tts_service.pid"
set "PORTFILE=%ROOT%tts_service\tmp\port.txt"
if not defined TTS_DEVICE set "TTS_DEVICE=cuda"

rem ---------- 0) FIXED port ----------
rem This project always serves on 18062 - the public API address must stay
rem stable for integrators. No auto-switching, no port scan. Override only
rem if 18062 is genuinely unusable on a new machine.
if not defined TTS_API_PORT set "TTS_API_PORT=18062"

echo ============================================
echo   WenZiQuDong TTS (GPT-SoVITS)  -  port %TTS_API_PORT%
echo ============================================
echo.

rem ---------- 1) is anything answering on our port? ----------
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; exit 0 } catch { exit 1 }"
if not %errorlevel% equ 0 goto cleanup

rem ---------- 1a) ours or foreign? ----------
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; if ($r.service -eq 'wenziqudong-tts') { exit 0 }; Write-Output ('  foreign service on port: ' + $r.service); exit 9 } catch { exit 1 }"
if %errorlevel% equ 9 (
    echo  Port %TTS_API_PORT% is held by a DIFFERENT program. This script will NOT kill it.
    echo  This project uses a FIXED port and does NOT switch automatically.
    echo  Fix A: stop that program, then run start.bat again to use port %TTS_API_PORT%.
    echo  Fix B: run this project on another port for this session:
    echo     set TTS_API_PORT=8070
    echo     start.bat
    ping -n 16 127.0.0.1 >nul
    exit /b 1
)
if %errorlevel% equ 1 goto cleanup

echo  Service is already running - no need to start again.
echo  This script never starts a second copy.
echo  To stop it for good, run stop.bat or close the service window.
ping -n 6 127.0.0.1 >nul
exit /b 0

:cleanup
rem ---------- 2) clean up leftovers of THIS project only ----------
rem Kills a forgotten service window and any orphan python of this copy
rem from an earlier session. Path-matched: sibling projects and foreign
rem programs are never touched. There is NO auto-restart anywhere; this
rem only removes leftovers so this start begins from a clean state.
echo Cleaning up leftovers of this project (if any)...
powershell -NoProfile -Command "$root='%ROOT%'; Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -and ($_.CommandLine -like ('*' + $root + 'tts_service\tts_run.ps1*') -or $_.CommandLine -like ('*' + $root + 'tts_service\tts_watchdog.ps1*')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine -like ('*' + $root + 'tts_service\tts_api.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if exist "%PIDFILE%" del /f /q "%PIDFILE%"
if exist "%ROOT%tts_service\tmp\tts_watchdog.pid" del /f /q "%ROOT%tts_service\tmp\tts_watchdog.pid"
ping -n 3 127.0.0.1 >nul

rem ---------- 3) is the port still taken (by a foreign program)? ----------
rem Fixed port means we never drift. If a foreign program holds 18062,
rem refuse to start and tell the user, instead of silently moving ports.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %TTS_API_PORT% -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo  ERROR: port %TTS_API_PORT% is still in use by another program.
    echo  This project uses a FIXED port and will NOT switch automatically.
    echo  Fix A: stop the program holding port %TTS_API_PORT%, then run start.bat again.
    echo  Fix B: run on another port for this session:
    echo     set TTS_API_PORT=8070
    echo     start.bat
    ping -n 21 127.0.0.1 >nul
    exit /b 1
)

rem ---------- 4) open the service window ----------
rem The window shows live service logs; closing that window stops the
rem service permanently (no auto-restart, GPU memory freed immediately).
echo Opening the service window - live logs there, closing it stops the service...
start "WenZiQuDong TTS" powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tts_service\tts_run.ps1"

rem ---------- 5) wait until service is ready, then open browser ----------
echo.
echo  Waiting for the service to become ready - first load: 5-10 min...
set /a tries=0
:waitloop
set /a tries+=1
if %tries% gtr 60 goto notready
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:%TTS_API_PORT%/health' -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 goto ready
ping -n 11 127.0.0.1 >nul
goto waitloop

:ready
echo  Service is ready.
echo    UI      : http://127.0.0.1:%TTS_API_PORT%/
echo    health  : http://127.0.0.1:%TTS_API_PORT%/health
echo    stop    : run stop.bat, close the service window, or use the web page button
>"%PORTFILE%" echo %TTS_API_PORT%
ping -n 3 127.0.0.1 >nul
start "" "http://127.0.0.1:%TTS_API_PORT%/"
exit /b 0

:notready
echo  Service is not ready yet after 10 minutes.
echo  NOTE: the service does NOT auto-retry. If it exited (for example
echo  because GPU/RAM was busy with other AI programs), just run
echo  start.bat again once the resources are free.
echo  Open http://127.0.0.1:%TTS_API_PORT%/health in your browser later.
echo  See logs under tts_service\tmp\ for details.
ping -n 11 127.0.0.1 >nul
exit /b 0
