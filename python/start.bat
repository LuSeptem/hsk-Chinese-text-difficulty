@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

echo ============================================
echo   First run: creating virtual environment
echo ============================================
python -m venv .venv 2>nul
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv 2>nul
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [ERROR] Python not found.
  echo Please install Python 3.10 or newer from https://www.python.org/downloads/
  echo Remember to check "Add Python to PATH" during installation.
  echo.
  pause
  exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
  echo Default index failed, retrying with official PyPI...
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
)
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency installation failed. Check your network.
  echo Try manually: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

:run
echo.
echo   Server starting on http://127.0.0.1:8000
echo   First start takes ~20 seconds to load dictionaries, please wait.
echo   Keep this window open. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" server.py
pause
