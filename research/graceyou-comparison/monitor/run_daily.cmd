@echo off
rem 7개 브랜드 일일 관찰 (기획서 §14): 수집 → 새 상품 소재 → CSV → 상품 썸네일 → 분석 페이지. 작업 스케줄러가 매일 20:00에 부른다.
rem 로그: monitor\logs\YYYY-MM-DD.log (하루에 여러 번 돌면 이어 붙임)
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
set PYTHONIOENCODING=utf-8
set AGENT_BROWSER_SESSION=gu-monitor
cd /d %~dp0..
if not exist monitor\logs mkdir monitor\logs
for /f %%d in ('%PY% -c "from datetime import datetime;print(datetime.now().strftime('%%Y-%%m-%%d'))"') do set TODAY=%%d
set LOG=monitor\logs\%TODAY%.log
echo ===== start %DATE% %TIME% >> %LOG%
%PY% -u monitor\collect.py >> %LOG% 2>&1
%PY% -u monitor\materials.py >> %LOG% 2>&1
%PY% -u monitor\build.py >> %LOG% 2>&1
%PY% -u monitor\thumbs.py >> %LOG% 2>&1
%PY% -u monitor\brief.py >> %LOG% 2>&1
echo ===== end %DATE% %TIME% exit=%ERRORLEVEL% >> %LOG%
