@echo off
chcp 65001 >nul
if not exist .venv (py -m venv .venv)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
pause
