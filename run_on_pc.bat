@echo off
rem Scans the stores that block GitHub's servers and uploads the results to GitHub.
rem Started every morning by Windows Task Scheduler (see setup_pc_task.bat).
cd /d "%~dp0"
git pull --rebase --autostash >nul 2>&1
python scan.py --only etos,spar,vomar --push >> pc_run.log 2>&1
