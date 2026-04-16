@echo off
setlocal
cd /d "%~dp0"
python -m catguard
exit /b %ERRORLEVEL%
