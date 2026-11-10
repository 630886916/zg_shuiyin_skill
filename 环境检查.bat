@echo off
setlocal
set PYTHONIOENCODING=gbk
set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\jy2\Scripts\python.exe"
set "CHECK=%~dp0skills\zg_shuiyin_skill\scripts\wm_env_check.py"

if not exist "%PY%" set "PY=python"
if not exist "%CHECK%" (
  echo [X] 找不到 wm_env_check.py，请在解压后的技能包目录里运行本文件。
  pause
  exit /b 1
)

"%PY%" "%CHECK%"
echo.
pause
