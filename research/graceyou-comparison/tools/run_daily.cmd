@echo off
rem Daily snapshot of the 4 confirmed brands + Grace U. See DAILY.md.
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
set PYTHONIOENCODING=utf-8
cd /d %~dp0..
set AGENT_BROWSER_SESSION=gu-daily
%PY% -u tools\snap_official.py
%PY% -u tools\snap_29cm.py --file data\daily_29cm_ids.txt
%PY% -u tools\snap_wconcept.py --file data\daily_wconcept_ids.txt
%PY% tools\diff_snapshots.py official --all --series
