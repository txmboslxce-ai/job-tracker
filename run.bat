@echo off
REM Job Tracker runner — called by Windows Task Scheduler.
REM Edit PYTHON and PROJECT_DIR if your paths differ.

set PYTHON=C:\Users\TimDunn\AppData\Local\Programs\Python\Python314\python.exe
set PROJECT_DIR=C:\Users\TimDunn\Claude\job-tracker

REM Set your Gmail App Password here (or set it as a permanent System env var
REM via Control Panel > System > Advanced > Environment Variables).
REM If already set as a system env var, remove the line below.
REM set GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

cd /d "%PROJECT_DIR%"
"%PYTHON%" main.py >> logs\job_tracker.log 2>&1
