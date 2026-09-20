@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech - stop (COMPLETE shutdown)
rem  Behavior contract (do NOT revert):
rem    - Stopping this project must stop it PERMANENTLY. Nothing
rem      restarts it afterwards (the old auto-restart watchdog was
rem      removed on purpose). Starting again is a manual action:
rem      the user double-clicks start.bat.
rem    - Matching is by full command-line path of THIS project only
rem      (tts_service\tts_api.py / tts_run.ps1 / legacy tts_watchdog.ps1),
rem      so sibling projects (duihuamoxing etc.) and foreign programs
rem      are NEVER touched. A foreign process holding port 18062 is
rem      reported, not killed.
rem    - Every stop is verified: the script re-checks the port until
rem      it is free (or reports a foreign holder) before claiming done.
rem ============================================================
setlocal
title WenZiQuDong TTS - Stop
set "ROOT=%~dp0"
set "TTS_API_PORT=18062"
rem port.txt only exists when start.bat was run with a manual TTS_API_PORT override
if exist "%ROOT%tts_service\tmp\port.txt" set /p TTS_API_PORT=<"%ROOT%tts_service\tmp\port.txt"

echo Stopping WenZiQuDong TTS (port %TTS_API_PORT%) - complete shutdown...
echo.

rem ---------- 1) kill service windows and service python of THIS project ----------
powershell -NoProfile -Command "$root='%ROOT%'; $hit=0; Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -and ($_.CommandLine -like ('*' + $root + 'tts_service\tts_run.ps1*') -or $_.CommandLine -like ('*' + $root + 'tts_service\tts_watchdog.ps1*')) } | ForEach-Object { $script:hit=1; Write-Output ('  stopped service window (PID ' + $_.ProcessId + ')'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine -like ('*' + $root + 'tts_service\tts_api.py*') } | ForEach-Object { $script:hit=1; Write-Output ('  stopped service python (PID ' + $_.ProcessId + ')'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Remove-Item ($root + 'tts_service\tmp\tts_service.pid'),($root + 'tts_service\tmp\tts_watchdog.pid') -Force -ErrorAction SilentlyContinue; if ($script:hit -eq 0) { Write-Output '  no running service of this project found' }"

rem ---------- 2) verify: port must be free before we call it done ----------
set /a tries=0
:verify
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort %TTS_API_PORT% -State Listen -ErrorAction SilentlyContinue; if (-not $c) { exit 0 }; $o = ($c | Select-Object -First 1).OwningProcess; $p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $o) -ErrorAction SilentlyContinue; if ($p -and $p.CommandLine -and $p.CommandLine -like '*%ROOT%tts_service\tts_api.py*') { Stop-Process -Id $o -Force -ErrorAction SilentlyContinue; exit 2 }; exit 3"
if %errorlevel% equ 0 goto stopped
if %errorlevel% equ 3 goto foreign
rem ours still shutting down - re-check for a few seconds
set /a tries+=1
if %tries% lss 8 (
    ping -n 2 127.0.0.1 >nul
    goto verify
)
echo  WARNING: port %TTS_API_PORT% did not free up in time. Check the service window.
ping -n 9 127.0.0.1 >nul
exit /b 1

:foreign
echo  NOTE: port %TTS_API_PORT% is held by a DIFFERENT program (not this project).
echo  This script does not touch other programs. This project is fully stopped.
ping -n 9 127.0.0.1 >nul
exit /b 0

:stopped
echo.
echo  Verified: nothing of this project is left, port %TTS_API_PORT% is free.
echo  Service is COMPLETELY stopped - nothing will auto-restart it.
echo  Start again any time with start.bat.
ping -n 9 127.0.0.1 >nul
exit /b 0
