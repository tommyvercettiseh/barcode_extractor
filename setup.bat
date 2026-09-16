@echo off
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if not exist input mkdir input
if not exist output mkdir output
echo.
echo Installatie klaar.
pause
