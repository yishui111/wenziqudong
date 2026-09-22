@echo off
rem ============================================================
rem  Wenziqudong TTS - one-click start (original name entry)
rem  Kept as a compatibility launcher for the original project;
rem  delegates to the ASCII start.bat which holds the logic.
rem ============================================================
call "%~dp0start.bat"
exit /b %errorlevel%
