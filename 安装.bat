@echo off
setlocal
chcp 936 >nul 2>&1
set "SRC=%~dp0skills\zg_shuiyin_skill"
set "DST=%USERPROFILE%\.workbuddy\skills\zg_shuiyin_skill"

echo ============================================
echo   zg_shuiyin_skill 技能安装
echo ============================================
echo.

if not exist "%SRC%\SKILL.md" (
  echo [X] 找不到 skills\zg_shuiyin_skill\SKILL.md
  echo     请先把整个 zip 解压出来，再双击本文件。
  pause
  exit /b 1
)

echo 源目录: %SRC%
echo 目标目录: %DST%
echo.

if not exist "%USERPROFILE%\.workbuddy\skills" mkdir "%USERPROFILE%\.workbuddy\skills"
xcopy /E /Y /I /Q "%SRC%" "%DST%" >nul
if errorlevel 1 (
  echo [X] 复制失败，请检查权限后重试。
  pause
  exit /b 1
)
echo [OK] 技能文件已复制

rem ---------- 依赖：Python 库（ffmpeg 由 imageio-ffmpeg 自带） ----------
set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\jy2\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo [1/2] 检查 Python 依赖...
"%PY%" -c "import imageio_ffmpeg, PIL, numpy, cv2" >nul 2>&1
if errorlevel 1 (
  echo       缺依赖，正在安装: imageio-ffmpeg pillow numpy opencv-python
  "%PY%" -m pip install --quiet --disable-pip-version-check imageio-ffmpeg pillow numpy opencv-python
  if errorlevel 1 (
    echo [X] pip 安装失败，请手动执行:
    echo     "%PY%" -m pip install imageio-ffmpeg pillow numpy opencv-python
    pause
    exit /b 1
  )
  echo       OK 依赖已安装
) else (
  echo       OK 依赖齐全
)

rem ---------- 环境自检 ----------
echo.
echo [2/2] 环境自检...
set PYTHONIOENCODING=gbk
"%PY%" "%DST%\scripts\wm_env_check.py"

echo.
echo --------------------------------------------
echo 用法: 在 Agent 里说「给这个文件夹加水印」并给出素材路径。
echo       默认参数已内置（50%% 透明 / 最长边=基准边÷4 / CRF14），不会每次询问。
echo       换默认水印图: 覆盖 %DST%\assets\watermark.png
echo --------------------------------------------
pause
