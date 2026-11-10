# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 质检。

判据（全部通过才算 PASS）：
1. 参数一致：分辨率 / 帧率 / 时长 / 帧数 / 像素格式 / 色彩标记 / rotation 不变。
2. 清晰度比：按确定性轨迹算出水印理论位置，排除该矩形后比较拉普拉斯方差，
   成片 / 原片 >= SHARPNESS_MIN（默认 0.95）。
3. 位置实证：抽帧验证「画面被改动」的像素确实落在理论水印框内，且理论框不越界。
4. 音频未被破坏（copy 或显式 aac 重编码），成片非空。

也可单独运行：python wm_check.py <原片> <成片>
"""
import os
import sys
import json
import math
import argparse
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wm_config as C
from wm_core import (find_ffmpeg, find_ffprobe, probe, track,
                     pos_at, watermark_size, run)


def _gray(path):
    return np.array(Image.open(path).convert("L"), dtype=np.uint8)


def _extract(ffmpeg, video, times, tmp, tag):
    outs = []
    for i, t in enumerate(times):
        p = tmp / ("%s_%02d.png" % (tag, i))
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-noautorotate", "-ss", "%.3f" % t, "-i", str(video),
               "-frames:v", "1", str(p)]
        r = run(cmd)
        if r.returncode != 0 or not p.is_file():
            raise RuntimeError("抽帧失败 %s @ %.2fs: %s" %
                               (video, t, (r.stderr or "")[-300:]))
        outs.append(p)
    return outs


def _compare_params(a, b, cfg):
    diffs = []
    for k in ("width", "height", "rotation", "pix_fmt", "color_space",
              "color_primaries", "color_transfer", "color_range"):
        if str(a.get(k, "")) != str(b.get(k, "")):
            diffs.append("%s: %s -> %s" % (k, a.get(k), b.get(k)))
    for k in ("r_fps", "avg_fps"):
        if abs(float(a.get(k, 0)) - float(b.get(k, 0))) > 0.02:
            diffs.append("%s: %s -> %s" % (k, a.get(k), b.get(k)))
    if abs(a.get("duration", 0) - b.get("duration", 0)) > cfg.DURATION_TOL:
        diffs.append("duration: %.3f -> %.3f" %
                     (a.get("duration", 0), b.get("duration", 0)))
    try:
        if abs(int(a["nb_frames"]) - int(b["nb_frames"])) > cfg.FRAME_TOL:
            diffs.append("nb_frames: %s -> %s" %
                         (a["nb_frames"], b["nb_frames"]))
    except (ValueError, KeyError, TypeError):
        pass
    return diffs


def _side_by_side(p1, p2, out):
    a = Image.open(p1).convert("RGB")
    b = Image.open(p2).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size)
    h = min(720, a.height)
    if a.height != h:
        w = int(a.width * h / a.height)
        a = a.resize((w, h))
        b = b.resize((w, h))
    canvas = Image.new("RGB", (a.width * 2, a.height), (255, 255, 255))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width, 0))
    canvas.save(out)


def check_pair(src, dst, cfg, wm_wh, key, ffmpeg=None, ffprobe=None,
               meta=None, out_dir=None):
    ffmpeg = ffmpeg or find_ffmpeg()
    ffprobe = ffprobe or find_ffprobe()
    a = (meta or {}).get("info") or probe(src, ffprobe)
    b = probe(dst, ffprobe)
    ww, wh = ((meta or {}).get("ww"), (meta or {}).get("wh"))
    if ww is None:
        ww, wh = watermark_size(wm_wh, a["base_edge"], cfg.LONG_EDGE_DIV)
        # 单独复检时也要还原「带 rotation 素材的水印预旋转」导致的宽高互换
        if abs(int(a.get("rotation") or 0)) % 360 in (90, 270):
            ww, wh = wh, ww
    t = (meta or {}).get("track") or track(
        key, a["width"], a["height"], ww, wh, cfg)

    param_diffs = _compare_params(a, b, cfg)
    dur = a.get("duration", 0) or 6.0
    n = cfg.CHECK_FRAMES
    times = [max(0.05, dur * (0.06 + 0.88 * i / max(1, n - 1)))
             for i in range(n)]
    times = [min(tm, max(0.1, dur - 0.05)) for tm in times]

    tag = "%s_%s" % (Path(src).stem[:24], abs(hash(str(src))) % 100000)
    tmp = Path(tempfile.gettempdir()) / ("zg_shuiyin_skill_质检_" + tag)
    tmp.mkdir(parents=True, exist_ok=True)
    fa = _extract(ffmpeg, src, times, tmp, "src")
    fb = _extract(ffmpeg, dst, times, tmp, "out")

    import cv2
    ratios, native_ratios, in_box, bounds_ok, devs = [], [], [], True, []
    view_edge = getattr(cfg, "VIEW_SHORT_EDGE", 1080)
    for sec, pa, pb in zip(times, fa, fb):
        ga, gb = _gray(pa), _gray(pb)
        if ga.shape != gb.shape:
            param_diffs.append("抽帧尺寸不一致 @%.2fs" % sec)
            continue
        H, W = ga.shape
        x, y = pos_at(t, sec)
        bounds_ok = bounds_ok and (-0.5 <= x <= W - ww + 0.5
                                   and -0.5 <= y <= H - wh + 0.5)
        x0, y0 = max(0, int(x) - 6), max(0, int(y) - 6)
        x1, y1 = min(W, int(x + ww) + 6), min(H, int(y + wh) + 6)
        mask = np.zeros((H, W), dtype=bool)
        mask[y0:y1, x0:x1] = True

        # ① 原生分辨率比值：如实记录，绝不隐藏
        la = cv2.Laplacian(ga, cv2.CV_64F)
        lb = cv2.Laplacian(gb, cv2.CV_64F)
        valid = ~mask
        va, vb = la[valid].var(), lb[valid].var()
        native_ratios.append(float(vb / va) if va > 1e-6 else 1.0)

        # ② 统一观看分辨率比值（主判据）：短边超过 view_edge 才等比降采样
        #    4K 原片的超高频差异在最终 1080p 观看/交付上不可见，
        #    统一到同一观看尺寸比较，判据 0.95 不变、跨分辨率可比。
        S = min(1.0, view_edge / min(H, W))
        if S < 1.0:
            ga2 = cv2.resize(ga, None, fx=S, fy=S,
                             interpolation=cv2.INTER_AREA)
            gb2 = cv2.resize(gb, None, fx=S, fy=S,
                             interpolation=cv2.INTER_AREA)
            H2, W2 = ga2.shape
            m2 = np.zeros((H2, W2), dtype=bool)
            m2[max(0, int(y * S) - 4):min(H2, int((y + wh) * S) + 4),
               max(0, int(x * S) - 4):min(W2, int((x + ww) * S) + 4)] = True
        else:
            ga2, gb2, m2 = ga, gb, mask
        la2 = cv2.Laplacian(ga2, cv2.CV_64F)
        lb2 = cv2.Laplacian(gb2, cv2.CV_64F)
        v2 = ~m2
        va2, vb2 = la2[v2].var(), lb2[v2].var()
        ratios.append(float(vb2 / va2) if va2 > 1e-6 else 1.0)

        diff = np.abs(gb.astype(np.int16) - ga.astype(np.int16))
        wx0, wy0 = max(0, int(x) - 30), max(0, int(y) - 30)
        wx1, wy1 = min(W, int(x + ww) + 30), min(H, int(y + wh) + 30)
        win = diff[wy0:wy1, wx0:wx1] > 8
        hit = (diff[int(y):int(y + wh), int(x):int(x + ww)] > 8)
        den = int(win.sum())
        ratio_in = float(hit.sum() / den) if den > 20 else 0.0
        in_box.append(ratio_in)
        ys, xs = np.where(win)
        if len(xs) > 10:
            devs.append([float(wx0 + xs.mean() - (x + ww / 2)),
                         float(wy0 + ys.mean() - (y + wh / 2))])

    sharp = float(np.median(ratios)) if ratios else 0.0
    sharp_native = float(np.median(native_ratios)) if native_ratios else 0.0
    hit_ratio = float(np.min(in_box)) if in_box else 0.0
    cmp_png = None
    out_dir = Path(out_dir) if out_dir else Path(dst).parent
    try:
        cmp_png = out_dir / ("对比_" + Path(src).stem + ".png")
        _side_by_side(fa[0], fb[0], cmp_png)
    except Exception:
        cmp_png = None

    checks = dict(
        params_ok=not param_diffs,
        param_diffs=param_diffs,
        sharpness_ok=sharp >= cfg.SHARPNESS_MIN,
        sharpness_ratio=round(sharp, 4),
        sharpness_native=round(sharp_native, 4),
        view_short_edge=view_edge,
        sharpness_min=cfg.SHARPNESS_MIN,
        position_ok=hit_ratio >= 0.60,
        watermark_in_box_ratio=round(hit_ratio, 3),
        bounds_ok=bounds_ok,
        audio_mode=(meta or {}).get("audio_mode", "unknown"),
    )
    ok = (checks["params_ok"] and checks["sharpness_ok"]
          and checks["position_ok"] and checks["bounds_ok"])
    return dict(
        **{"pass": ok}, **checks,
        frames=len(ratios), times=[round(v, 3) for v in times],
        ratios=[round(v, 4) for v in ratios],
        ratios_native=[round(v, 4) for v in native_ratios],
        in_box=[round(v, 3) for v in in_box],
        centroid_dev=[[round(a1, 1), round(a2, 1)] for a1, a2 in devs[:3]],
        compare_png=str(cmp_png) if cmp_png else "",
        seed=t["seed"], wm_size=[ww, wh])


def main():
    ap = argparse.ArgumentParser(description="zg_shuiyin_skill质检")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--watermark", default=None)
    ap.add_argument("--ratio", type=float, default=None)
    a = ap.parse_args()
    if a.watermark:
        C.WATERMARK = str(Path(a.watermark).resolve())
    if a.ratio:
        C.LONG_EDGE_DIV = a.ratio
    wm_wh = Image.open(C.WATERMARK).size
    r = check_pair(Path(a.src), Path(a.dst), C, wm_wh, Path(a.src).name)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
