@echo off
rem ============================================================
rem  Wenziqudong Text-to-Speech - stop
rem  Kills the watchdog first (so it cannot restart python),
rem  then the tts_api python process, then frees port 8060.
rem  Safe matching: only processes whose command line contains
rem  tts_watchdog / tts_api are touched (avoids killing a
rem  system process whose PID was reused).
rem ============================================================
setlocal
title WenZiQuDong TTS - Stop
set "ROOT=%~dp0"
set "PIDFILE=%ROOT%tts_service\tmp\tts_watchdog.pid"

echo Stopping WenZiQuDong TTS service (port 8060)...
powershell -NoProfile -Command "$f='%PIDFILE%'; if (Test-Path $f) { try { $j = Get-Content $f -Raw | ConvertFrom-Json; if ($j.watchdog) { $wp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.watchdog) -ErrorAction SilentlyContinue; if ($wp -and $wp.Name -eq 'powershell.exe' -and $wp.CommandLine -match 'tts_watchdog') { Stop-Process -Id $j.watchdog -Force -ErrorAction SilentlyContinue } }; if ($j.python) { $pp = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $j.python) -ErrorAction SilentlyContinue; if ($pp -and $pp.Name -eq 'python.exe' -and $pp.CommandLine -match 'tts_api') { Stop-Process -Id $pp.ProcessId -Force -ErrorAction SilentlyContinue } } } catch {}; Remove-Item $f -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'tts_api' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; $c = Get-NetTCPConnection -LocalPort 8060 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Write-Output 'Service stopped - watchdog killed, it will NOT auto-restart.'"
echo.
echo Service stopped. Watchdog killed, no auto-restart.
timeout /t 5 >nul 2>nul
exit /b 0
