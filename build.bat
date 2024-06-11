@echo off
@REM set starttime=%time%

call %~dp0\.venv\Scripts\activate.bat > nul 2>&1
if %errorlevel% neq 0 (
	echo Setup enviroment...
	python -m venv %~dp0\.venv
	call %~dp0\.venv\Scripts\activate.bat
)

@REM venv start
setlocal EnableDelayedExpansion
set shell_cmd="python -m pip list 2>&1"
FOR /F "tokens=* delims=" %%F IN ('%shell_cmd%') DO (
	if defined result set "result=!result!!LF!"
	set "result=!result!%%F"
)

set need=0
FOR /F %%a IN (%~dp0\requirements_build.txt) do (
	@REM echo line:%%a
	if "!result:%%a=!" neq "%result%" (
@REM 		echo %%a O
	) else (
@REM 		echo %%a X
		set need=1
	)
)

if %need% == 1 (
	echo on
	python -m pip install -r %~dp0\requirements_build.txt --no-cache-dir
	echo off
)

@REM echo %starttime%
@REM echo %time%

@rem python %~dp0\main.py
cd /d %~dp0
python setup.py build_exe --silent -O2