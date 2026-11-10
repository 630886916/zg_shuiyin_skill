#!/usr/bin/env bash
# zg_shuiyin_skill 一键安装（macOS / Linux）
# 用法：curl -fsSL https://raw.githubusercontent.com/630886916/zg_shuiyin_skill/main/install.sh | bash

set -euo pipefail

REPO="630886916/zg_shuiyin_skill"
SKILL="zg_shuiyin_skill"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo ""
echo "=============================================="
echo "  $SKILL  安装"
echo "=============================================="
echo ""

echo "  下载仓库..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" -o "$TMP/repo.tar.gz"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$TMP/repo.tar.gz" "https://codeload.github.com/$REPO/tar.gz/refs/heads/main"
else
  echo "[X] 需要 curl 或 wget" >&2; exit 1
fi
# 用相对路径解压：GNU tar 会把 "C:/path" 误判为 host:path（Git Bash 经典坑）
( cd "$TMP" && tar -xzf repo.tar.gz )
SRC="$(find "$TMP" -maxdepth 3 -type d -name "$SKILL" -path "*/skills/*" | head -1)"
if [ -z "${SRC:-}" ] || [ ! -f "$SRC/SKILL.md" ]; then
  echo "[X] 解压后找不到 skills/$SKILL/SKILL.md" >&2; exit 1
fi
echo "[OK] 下载完成"

# 探测目标 skills 目录
TARGETS=()
for d in "$HOME/.workbuddy" "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.agents"; do
  [ -d "$d" ] && TARGETS+=("$d/skills")
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("$HOME/.workbuddy/skills")

echo "  安装到："
for t in "${TARGETS[@]}"; do
  mkdir -p "$t"
  rm -rf "$t/$SKILL"
  cp -R "$SRC" "$t/$SKILL"
  echo "[OK] $t/$SKILL"
done

# Python 依赖
echo ""
echo "  检查 Python 依赖..."
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[!] 没找到 Python 3，出片前需要装 Python 3.9+"
else
  if ! "$PY" -c "import imageio_ffmpeg, PIL, numpy, cv2" >/dev/null 2>&1; then
    echo "  缺依赖，正在安装：imageio-ffmpeg pillow numpy opencv-python"
    "$PY" -m pip install --quiet --disable-pip-version-check imageio-ffmpeg pillow numpy opencv-python \
      || echo "[!] pip 安装失败，请手动执行：$PY -m pip install imageio-ffmpeg pillow numpy opencv-python"
  else
    echo "[OK] 依赖齐全"
  fi
  echo ""
  echo "  环境自检..."
  [ -f "${TARGETS[0]}/$SKILL/scripts/wm_env_check.py" ] && "$PY" "${TARGETS[0]}/$SKILL/scripts/wm_env_check.py" || true
fi

echo ""
echo "----------------------------------------------"
echo " 装好了。回到 Agent 里刷新会话，直接说："
echo "   「给这个视频加水印 /path/to/a.mp4」"
echo "   多素材就说：「把这几个素材拼起来加水印」+ 拖入文件"
echo "----------------------------------------------"
echo ""
