@echo off
setlocal
cd /d "%~dp0"
pyinstaller catguard.spec --clean --noconfirm
exit /b %ERRORLEVEL%
