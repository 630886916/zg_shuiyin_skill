# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 环境发现 / 元数据探测 / 确定性浮动轨迹。

三件事：
1. 自动找 ffmpeg（优先 imageio 自带，不用 PATH 版，filter 语法有差异）与 ffprobe。
2. ffprobe 读真实参数；手机竖拍读 rotation 侧数据判方向，不信任容器宽高。
3. 由文件名哈希出种子生成正弦叠加轨迹：同一素材永远同一条，不同素材各不同。
"""
import os
import sys
import glob
import json
import math
import hashlib
import random
import shutil
import subprocess
from fractions import Fraction


def _from_env(name):
    p = os.environ.get(name)
    return p if p and os.path.isfile(p) else None


def find_ffmpeg():
    p = _from_env("WM_FFMPEG")
    if p:
        return p
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    hits = glob.glob(os.path.expanduser("~") +
                     "/.workbuddy/binaries/python/envs/*/Lib/site-packages/"
                     "imageio_ffmpeg/binaries/ffmpeg*.exe")
    if hits:
        return hits[0]
    p = shutil.which("ffmpeg")
    if p:
        return p
    raise RuntimeError("找不到 ffmpeg：请双击 环境检查.bat 查看")


def find_ffprobe():
    p = _from_env("WM_FFPROBE")
    if p:
        return p
    try:
        cand = os.path.join(os.path.dirname(find_ffmpeg()), "ffprobe.exe")
        if os.path.isfile(cand):
            return cand
    except Exception:
        pass
    p = shutil.which("ffprobe")
    if p:
        return p
    hits = glob.glob(os.path.expanduser("~") +
                     "/.workbuddy/binaries/ffmpeg/bin/ffprobe*")
    if hits:
        return hits[0]
    raise RuntimeError("找不到 ffprobe：请双击 环境检查.bat 查看")


def run(cmd, check=False):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError("命令失败 (code %d): %s\n%s" %
                           (r.returncode, " ".join(map(str, cmd))[:400],
                            (r.stderr or "")[-800:]))
    return r


def _fps(s):
    try:
        f = Fraction(str(s))
        return float(f) if f.denominator else 0.0
    except Exception:
        return 0.0


def probe(path, ffprobe=None):
    """读视频真实参数。返回 dict，关键字段 base_edge = 显示画面长边。"""
    ffprobe = ffprobe or find_ffprobe()
    r = run([ffprobe, "-v", "error", "-show_streams", "-show_format",
             "-of", "json", str(path)])
    if r.returncode != 0:
        raise RuntimeError("ffprobe 失败: " + (r.stderr or "")[-500:])
    d = json.loads(r.stdout)
    vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
    if not vs:
        raise RuntimeError("没有视频流: " + str(path))
    v = vs[0]
    au = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    a = au[0] if au else {}
    w, h = int(v.get("width", 0)), int(v.get("height", 0))

    # 手机竖拍：容器宽高不可信，必须读 rotation 侧数据
    rot = 0
    for sd in (v.get("side_data_list") or []):
        if "rotation" in sd:
            try:
                rot = int(float(sd["rotation"]))
            except Exception:
                pass
    if rot == 0:
        # 老式手机素材把角度写在 tags.rotate，而不是 Display Matrix
        try:
            rot = int(float((v.get("tags") or {}).get("rotate", 0)))
        except Exception:
            pass
    disp_w, disp_h = (h, w) if abs(rot) in (90, 270) else (w, h)

    fmt = d.get("format", {})
    dur = 0.0
    for cand in (v.get("duration"), fmt.get("duration")):
        try:
            if cand and float(cand) > 0:
                dur = float(cand)
                break
        except Exception:
            pass

    return dict(
        path=str(path), width=w, height=h, rotation=rot,
        disp_w=disp_w, disp_h=disp_h,
        base_edge=max(disp_w, disp_h),
        pix_fmt=v.get("pix_fmt", "") or "yuv420p",
        r_fps=_fps(v.get("r_frame_rate", "0/1")),
        avg_fps=_fps(v.get("avg_frame_rate", "0/1")),
        duration=dur,
        nb_frames=str(v.get("nb_frames", "")),
        color_space=v.get("color_space", ""),
        color_primaries=v.get("color_primaries", ""),
        color_transfer=v.get("color_transfer", ""),
        color_range=v.get("color_range", ""),
        vcodec=v.get("codec_name", ""),
        acodec=a.get("codec_name", ""),
        container=fmt.get("format_name", ""),
    )


def watermark_size(img_wh, base_edge, div):
    """水印图最长边 = 画面基准边 / div，等比缩放，偶数化。"""
    iw, ih = img_wh
    target = max(2.0, float(base_edge) / float(div))
    scale = target / max(iw, ih)
    w = max(2, int(round(iw * scale)))
    h = max(2, int(round(ih * scale)))
    if w % 2:
        w += 1
    if h % 2:
        h += 1
    return w, h


def track(key, W, H, ww, wh, cfg):
    """确定性伪随机轨迹参数。key 相同 -> 轨迹完全相同。"""
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    rnd = random.Random(seed)
    margin = max(int(min(W, H) * cfg.MARGIN_RATIO), cfg.MARGIN_MIN_PX)
    span_x = max(0.0, (W - ww) / 2.0 - margin)
    span_y = max(0.0, (H - wh) / 2.0 - margin)

    def pair(span):
        f1 = rnd.uniform(*cfg.F1_RANGE)
        f2 = rnd.uniform(*cfg.F2_RANGE)
        p1 = rnd.uniform(0, 2 * math.pi)
        p2 = rnd.uniform(0, 2 * math.pi)
        w1 = rnd.uniform(0.45, 0.65)
        a1 = span * cfg.AMPLITUDE_USE * w1
        a2 = span * cfg.AMPLITUDE_USE * (1.0 - w1)
        return (f1, f2, p1, p2, a1, a2)

    return dict(seed=seed, key=key, W=W, H=H, ww=ww, wh=wh,
                cx=(W - ww) / 2.0, cy=(H - wh) / 2.0,
                margin=margin, span_x=span_x, span_y=span_y,
                x=pair(span_x), y=pair(span_y))


def expr_x(t):
    f1, f2, p1, p2, a1, a2 = t["x"]
    return ("{:.3f}+{:.3f}*sin(2*PI*{:.6f}*t+{:.6f})"
            "+{:.3f}*sin(2*PI*{:.6f}*t+{:.6f})").format(
                t["cx"], a1, f1, p1, a2, f2, p2)


def expr_y(t):
    f1, f2, p1, p2, a1, a2 = t["y"]
    return ("{:.3f}+{:.3f}*sin(2*PI*{:.6f}*t+{:.6f})"
            "+{:.3f}*sin(2*PI*{:.6f}*t+{:.6f})").format(
                t["cy"], a1, f1, p1, a2, f2, p2)


def pos_at(t, sec):
    """Python 侧复算某一秒的水印左上角，供质检对照。"""
    def val(pair, c, s):
        f1, f2, p1, p2, a1, a2 = pair
        return (c + a1 * math.sin(2 * math.pi * f1 * s + p1)
                + a2 * math.sin(2 * math.pi * f2 * s + p2))
    return val(t["x"], t["cx"], sec), val(t["y"], t["cy"], sec)


def fmt_num(x):
    return "{:.6f}".format(x)
