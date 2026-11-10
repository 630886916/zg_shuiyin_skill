# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 默认参数唯一来源。

改这里 = 改全局默认。日常出片不要改这个文件；
只有用户明确点名「用新图 / 改透明度 / 改大小」时，才用命令行参数覆盖当次。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- 水印素材（随技能包分发；替换这张图 = 换默认水印） ---
WATERMARK = str(ROOT / "assets" / "watermark.png")

# --- 叠加规格 ---
ALPHA = 0.50               # 50% 透明度：在图片自身 alpha 基础上再乘 0.5

# ===== 尺寸定稿（2026-11-10 17:36 用户确认「这个大小可以」）=====
# 规则：水印图**最长边** = 画面基准边 / LONG_EDGE_DIV
#   基准边：横屏取画面宽，竖屏取画面高（= 显示宽高的长边）
#   等比缩放，宽高各自取偶数（防 subsampled 色度半像素偏移）
# 内置默认水印图 assets/watermark.png = 中工LOGO-红色.png
#   原图 1882×719，宽高比 2.618 : 1（宽幅横版 LOGO）
# 定稿取值 4（= 初版 1/20 的 5 倍），对应实际像素：
#   720×1280 竖屏  → 320×122（占画面宽 44%）
#   1080×1920 竖屏 → 270×103
#   1280×720 横屏  → 320×122
#   1920×1080 横屏 → 480×183
# 为什么是 4：初版 1/20 → 720 宽只有 64×24px，成片里几乎看不见；
#   放大 5 倍后「中工」+ 圆形 + 英文小字全部清晰；8 倍（2.5）达 512px 会明显压人脸。
# ⚠️ 换水印图时：宽幅 LOGO 沿用 4；若换成正方形/单字标，4 会显得过大，先看观感再定。
LONG_EDGE_DIV = 4
MARGIN_RATIO = 0.02        # 距画面边缘最小留白（按短边算）
MARGIN_MIN_PX = 8
TIME_MODE = "always"       # 全程常驻：第 0 帧到末帧

# --- 浮动轨迹：确定性伪随机 + 缓慢连续斜向漂移 ---
TRACK_MODE = "seeded_sine"
BOUNDS = "full_frame"      # 全画面可飘，只保证不越界
F1_RANGE = (0.025, 0.060)  # Hz 慢漂主频（周期 17~40s）
F2_RANGE = (0.060, 0.115)  # Hz 慢漂副频（周期 9~17s）
AMPLITUDE_USE = 0.90       # 振幅和占可用半径的比例，留 10% 安全余量

# --- 画质：视觉无损 ---
CRF = 14
PRESET = "slow"
AUDIO_COPY = True
AUDIO_FALLBACK_BPS = "192k"
OUTPUT_EXT = ".mp4"
OUT_DIRNAME = "水印版"
OUT_SUFFIX = "_水印版"
FASTSTART = True
MP4_AUDIO_OK = {"aac", "mp3", "alac", "ac3", "eac3", "dts"}

# --- 批量 ---
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm",
              ".ts", ".mts", ".mpg", ".mpeg"}
SKIP_EXISTING = True

# --- 质检判据 ---
SHARPNESS_MIN = 0.95       # 成片/原片 拉普拉斯方差比（避开水印区）
VIEW_SHORT_EDGE = 1080     # 质检统一比较分辨率：短边超过它就等比降到 1080 再比
CHECK_FRAMES = 6           # 均匀抽帧数
POS_TOL_PX = 6             # 水印实测位置与理论轨迹允许偏差
DIFF_THRESHOLD = 12        # 判定「该像素被水印改动」的灰度差阈值
DURATION_TOL = 0.15        # 时长容差（秒）
FRAME_TOL = 1              # 帧数容差

# 允许被当次覆盖的键（防止误改工艺参数）
OVERRIDE_KEYS = {"WATERMARK", "ALPHA", "LONG_EDGE_DIV", "CRF",
                 "PRESET", "OUT_DIRNAME", "OUT_SUFFIX"}

# --- 多素材理解与拼接 ---
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SHEET_FRAMES = 8               # 每条素材均匀抽帧数（供 AI 理解画面）
SHEET_THUMB_W = 320            # contact sheet 单帧宽
SHEET_COLS = 4
ASR_MODEL = "small"            # faster-whisper；本机 HF 缓存已有，找不到则自动跳过转写
ASR_LANG = "zh"

BLEND_TARGET = "first_video"   # 以第一条视频为基准，其余模糊底填充（不裁切）
BLUR_RADIUS = 24
BLUR_DARKEN = -0.12
COMPOSE_FALLBACK_W = 1080      # 全是图片时的兜底规格
COMPOSE_FALLBACK_H = 1920
COMPOSE_FALLBACK_FPS = 30
COMPOSE_SR = 48000
COMPOSE_CHANNELS = 2
COMPOSE_CRF = 14
COMPOSE_SUFFIX = "_拼接版"

TRANSITION_DURATION = 0.5      # 画面转场 0.5s
AUDIO_CROSSFADE = 0.3          # 声音交叉淡化 0.3s
TRANSITIONS = ["fade", "dissolve", "slideleft", "wipeleft", "smoothleft"]
IMG_DURATION_MIN = 2.0
IMG_DURATION_MAX = 5.0
IMG_DURATION_DEFAULT = 3.0
# 预留参数，当前未启用：用户最终定为「图片静帧 2~5s 按节奏自适应，不做强制动效」，
# 故 wm_compose.py 不调用它。若以后要开 Ken Burns，注意 xfade 的 CFR 约束（见 SKILL.md 第 10 条）。
IMG_PAN_SCALE = 1.10
AUDIO_MODE = "keep_original"   # 保留各段原声
