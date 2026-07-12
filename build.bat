@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pyinstaller catguard.spec --clean --noconfirm
exit /b %ERRORLEVEL%
