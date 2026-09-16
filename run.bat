@echo off
cd /d "%~dp0"
if not exist input mkdir input
if not exist output mkdir output
python app.py
pause
