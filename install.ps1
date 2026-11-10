# zg_shuiyin_skill 一键安装（Windows PowerShell）
# 用法：irm https://raw.githubusercontent.com/630886916/zg_shuiyin_skill/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$repo      = "630886916/zg_shuiyin_skill"
$skillName = "zg_shuiyin_skill"

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function Write-Step($msg) { Write-Host "  $msg" -ForegroundColor Gray }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[X]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  $skillName  安装" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

$tmp = Join-Path $env:TEMP ("zg_shuiyin_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

try {
    Write-Step "下载仓库..."
    $zip = Join-Path $tmp "repo.zip"
    $url = "https://codeload.github.com/$repo/zip/refs/heads/main"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $tmp -Force

    $root = Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "zg_shuiyin_skill-*" } |
            Select-Object -First 1
    if (-not $root) { throw "解压后找不到仓库目录" }
    $src = Join-Path $root.FullName "skills\$skillName"
    if (-not (Test-Path (Join-Path $src "SKILL.md"))) { throw "找不到 skills\$skillName\SKILL.md" }
    Write-Ok "下载完成"

    # ---- 探测目标 skills 目录（已装哪个 Agent 就装哪个）----
    $targets = @()
    foreach ($d in @(".workbuddy", ".claude", ".codex", ".cursor", ".config\opencode")) {
        $p = Join-Path $env:USERPROFILE $d
        if (Test-Path $p) { $targets += (Join-Path $p "skills") }
    }
    if ($targets.Count -eq 0) { $targets += (Join-Path $env:USERPROFILE ".workbuddy\skills") }

    Write-Step "安装到："
    foreach ($t in $targets) {
        if (-not (Test-Path $t)) { New-Item -ItemType Directory -Path $t -Force | Out-Null }
        $dst = Join-Path $t $skillName
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
        Write-Ok $dst
    }

    # ---- Python 依赖 ----
    Write-Host ""
    Write-Step "检查 Python 依赖..."
    $py = Join-Path $env:USERPROFILE ".workbuddy\binaries\python\envs\jy2\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $py = $cmd.Source }
    }
    if (-not $py -or -not (Test-Path $py)) {
        Write-Err "没找到 Python。请先装 Python 3.9+ 后重跑本脚本。"
    } else {
        & $py -c "import imageio_ffmpeg, PIL, numpy, cv2" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "缺依赖，正在安装：imageio-ffmpeg pillow numpy opencv-python"
            & $py -m pip install --quiet --disable-pip-version-check imageio-ffmpeg pillow numpy opencv-python
            if ($LASTEXITCODE -ne 0) { Write-Err "pip 安装失败，请手动执行：`"$py`" -m pip install imageio-ffmpeg pillow numpy opencv-python" }
            else { Write-Ok "依赖已安装" }
        } else {
            Write-Ok "依赖齐全"
        }

        Write-Host ""
        Write-Step "环境自检..."
        # 让 Python 输出与 PowerShell 控制台编码对齐，否则中文乱码
        try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
        $env:PYTHONIOENCODING = "utf-8"
        $check = Join-Path (Join-Path $targets[0] $skillName) "scripts\wm_env_check.py"
        if (Test-Path $check) { & $py $check }
    }
}
finally {
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Write-Host "----------------------------------------------" -ForegroundColor Cyan
Write-Host " 装好了。回到 Agent 里刷新会话（或新开一个），直接说：" -ForegroundColor White
Write-Host '   「给这个视频加水印 D:\素材\a.mp4」' -ForegroundColor Yellow
Write-Host "   多素材就说：「把这几个素材拼起来加水印」+ 拖入文件" -ForegroundColor Gray
Write-Host "   （说「加水印」= 整套默认参数照搬，不会再逐项问你）" -ForegroundColor Gray
Write-Host "----------------------------------------------" -ForegroundColor Cyan
Write-Host ""
