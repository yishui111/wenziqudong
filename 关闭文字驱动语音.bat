@echo off
rem ============================================================
rem  Wenziqudong TTS - stop (original name entry)
rem  Kept as a compatibility launcher for the original project;
rem  delegates to the ASCII stop.bat which holds the logic.
rem ============================================================
call "%~dp0stop.bat"
exit /b %errorlevel%
