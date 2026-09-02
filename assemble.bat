@echo off
rem ==================================================
rem  WENZIQUDONG - one-key preflight for big assets
rem  Guarantee flow: (A) copy original project folder
rem  with big assets (fastest), or (B) clone this repo
rem  then run this script; details: see DEPLOY.md top.
rem ==================================================
setlocal
cd /d "%~dp0"
set "MISSING=0"
echo Checking required big assets...
if exist "gptsovits\GPT-SoVITS" (echo   OK   gptsovits\GPT-SoVITS) else (echo   MISS gptsovits\GPT-SoVITS ^& set MISSING=1)
if exist "runtime\py312" (echo   OK   runtime\py312) else (echo   MISS runtime\py312 ^& set MISSING=1)
if exist "runtime\ffmpeg\bin" (echo   OK   runtime\ffmpeg\bin) else (echo   MISS runtime\ffmpeg\bin ^& set MISSING=1)
if exist "tts_service\models" (echo   OK   tts_service\models) else (echo   MISS tts_service\models ^& set MISSING=1)
echo.
if %MISSING%==0 (
  echo ALL big assets present. Run start.bat now.
) else (
  echo Some big assets missing. See DEPLOY.md (top section
  "Deployment guarantee") for download instructions.
)
pause
