@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run_venv
where py >nul 2>&1
if errorlevel 1 goto run_python
goto run_py

:run_venv
".venv\Scripts\python.exe" bot.py %*
goto done

:run_py
py bot.py %*
goto done

:run_python
python bot.py %*

:done
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo Execucao finalizada com erro (%EXIT_CODE%).

endlocal & exit /b %EXIT_CODE%
