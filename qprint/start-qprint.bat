@echo off
setlocal DisableDelayedExpansion
set "QPRINT_LAUNCH_WORKSPACE=%~dp0"
set "QPRINT_LAUNCH_ROOT=%~dp0"
:find_root
if exist "%QPRINT_LAUNCH_ROOT%qprint\__main__.py" if exist "%QPRINT_LAUNCH_ROOT%environment.yml" goto run
for %%I in ("%QPRINT_LAUNCH_ROOT%..") do set "QPRINT_LAUNCH_PARENT=%%~fI\"
if "%QPRINT_LAUNCH_PARENT%"=="%QPRINT_LAUNCH_ROOT%" goto missing_root
set "QPRINT_LAUNCH_ROOT=%QPRINT_LAUNCH_PARENT%"
goto find_root
:run
pushd "%QPRINT_LAUNCH_ROOT%"
if errorlevel 1 goto failed
if not exist ".conda\python.exe" goto missing_python
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul
".conda\python.exe" -m qprint.launcher
set "QPRINT_LAUNCH_EXIT=%ERRORLEVEL%"
popd
pause >nul
exit /b %QPRINT_LAUNCH_EXIT%
:missing_python
echo Project Python is missing. Open Anaconda Prompt / Miniconda Prompt in the Qprint folder and run:
echo conda init powershell
echo conda env create -p .\.conda -f environment.yml
popd
goto failed
:missing_root
echo Qprint was not found. Put this BAT inside a workspace under the Qprint folder.
:failed
pause
exit /b 1
