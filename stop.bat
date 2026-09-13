@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech - stop
rem  Kills the watchdog first (so it cannot restart python),
rem  then the tts_api python of THIS project copy, then frees the
rem  service port. Safe matching: only processes whose command line
rem  points at THIS project's tts_service\tts_api.py are touched,
rem  so sibling projects (duihuamoxing etc.) are never affected.
rem ============================================================
setlocal
title WenZiQuDong TTS - Stop
set "ROOT=%~dp0"
set "PIDFILE=%ROOT%tts_service\tmp\tts_watchdog.pid"
rem this project's FIXED port is 18062; port.txt (written by start.bat) is
rem only used to follow a manual TTS_API_PORT override
set "TTS_API_PORT=18062"
if exist "%ROOT%tts_service\tmp\port.txt" set /p TTS_API_PORT=<"%ROOT%tts_service\tmp\port.txt"

echo Stopping WenZiQuDong TTS service (port %TTS_API_PORT%)...
powershell -NoProfile -Command "$f='%PIDFILE%'; if (Test-Path $f) { try { $j = Get-Content $f -Raw | ConvertFrom-Json; if ($j.watchdog) { $wp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.watchdog) -ErrorAction SilentlyContinue; if ($wp -and $wp.Name -eq 'powershell.exe' -and $wp.CommandLine -match 'tts_watchdog') { Stop-Process -Id $j.watchdog -Force -ErrorAction SilentlyContinue } }; if ($j.python) { $pp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.python) -ErrorAction SilentlyContinue; if ($pp -and $pp.Name -eq 'python.exe' -and $pp.CommandLine -like '*%ROOT%tts_service\tts_api.py*') { Stop-Process -Id $pp.ProcessId -Force -ErrorAction SilentlyContinue } } } catch {}; Remove-Item $f -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*%ROOT%tts_service\tts_api.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; $c = Get-NetTCPConnection -LocalPort %TTS_API_PORT% -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | ForEach-Object { $pp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $_.OwningProcess) -ErrorAction SilentlyContinue; if ($pp -and $pp.CommandLine -like '*%ROOT%tts_service\tts_api.py*') { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } }; Write-Output 'Service stopped - watchdog killed, it will NOT auto-restart.'"
echo.
echo Service stopped. Watchdog killed, no auto-restart.
timeout /t 5 >nul 2>nul
exit /b 0
