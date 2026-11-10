# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 渲染主入口（单文件 / 整目录批量）。

用法：
  python wm_render.py <视频或文件夹> [更多路径...] [--out 输出根目录]
  python wm_render.py <视频> --watermark 新图.png --alpha 0.6 --ratio 16
  python wm_render.py <文件夹> --overwrite --no-check

默认参数全部来自 wm_config.py；只有明确给出命令行参数才覆盖当次。
原片只读，成片写到 <源目录>/水印版/<原名>_水印版.mp4。
"""
import os
import sys
import json
import argparse
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wm_config as C
from wm_core import (find_ffmpeg, find_ffprobe, probe, track,
                     expr_x, expr_y, watermark_size, run)
from PIL import Image


def collect(inputs, exts, out_dirname):
    items = []
    for raw in inputs:
        p = Path(raw).resolve()
        if p.is_file():
            if p.suffix.lower() in exts:
                items.append((p, p.name))
        elif p.is_dir():
            for q in sorted(p.rglob("*")):
                if (q.is_file() and q.suffix.lower() in exts
                        and out_dirname not in q.parts):
                    items.append((q, str(q.relative_to(p))))
        else:
            print("WARN 路径不存在:", p)
    return items


def out_path_for(src, rel, out_root, out_dirname, suffix, ext):
    stem = src.stem + suffix + ext
    if out_root:
        return Path(out_root) / Path(rel).parent / stem
    return src.parent / out_dirname / stem


def build_cmd(src, dst, wm_use, ww, wh, t, info, cfg, ffmpeg):
    filt = ("[1:v]scale={w}:{h}:flags=lanczos,format=rgba,"
            "colorchannelmixer=aa={a}[wm];"
            "[0:v][wm]overlay=x='{x}':y='{y}':eval=frame:"
            "format=yuv420:repeatlast=1[v]").format(
                w=ww, h=wh, a=cfg.ALPHA, x=expr_x(t), y=expr_y(t))
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-noautorotate", "-i", str(src), "-i", str(wm_use),
           "-filter_complex", filt,
           "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", cfg.PRESET, "-crf", str(cfg.CRF),
           "-pix_fmt", info["pix_fmt"],
           "-aq-mode", "3", "-fps_mode", "passthrough",
           "-map_metadata", "0", "-map_chapters", "0",
           "-movflags", "+faststart"]
    for opt, val in (("-colorspace", info["color_space"]),
                     ("-color_primaries", info["color_primaries"]),
                     ("-color_trc", info["color_transfer"]),
                     ("-color_range", info["color_range"])):
        if val and val not in ("unknown", "unspecified", "N/A"):
            cmd += [opt, str(val)]
    if info["acodec"] and info["acodec"] not in cfg.MP4_AUDIO_OK:
        cmd += ["-c:a", "aac", "-b:a", cfg.AUDIO_FALLBACK_BPS]
        audio_mode = "aac-reencode"
    else:
        cmd += ["-c:a", "copy"]
        audio_mode = "copy"
    cmd += [str(dst)]
    return cmd, audio_mode


def prepare_watermark(wm_path, ww, wh, rotation):
    """带 rotation 侧数据的素材：预旋转水印，保证播放器旋转画面后水印仍是正的。

    -noautorotate 保留原片帧坐标系与 rotation 元数据（参数不变），
    但横向水印叠在横帧上，播放旋转 90° 后会变成竖的。
    正解：水印预旋转 -rotation，并互换目标宽高；轨迹按互换后的框计算。
    """
    import tempfile
    rot = int(rotation or 0)
    if rot % 360 == 0:
        return str(wm_path), ww, wh, 0
    back = (-rot) % 360
    im = Image.open(wm_path).convert("RGBA")
    if back == 90:
        im2 = im.transpose(Image.Transpose.ROTATE_90)
    elif back == 270:
        im2 = im.transpose(Image.Transpose.ROTATE_270)
    elif back == 180:
        im2 = im.transpose(Image.Transpose.ROTATE_180)
    else:
        im2 = im.rotate(back, expand=True, resample=Image.BICUBIC)
    work = Path(tempfile.gettempdir()) / "zg_shuiyin_skill_wm"
    work.mkdir(parents=True, exist_ok=True)
    out = work / ("_wm_rot%d.png" % rot)
    im2.save(out)
    swap = back in (90, 270)
    nw, nh = (wh, ww) if swap else (ww, wh)
    return str(out), nw, nh, rot


def render_one(src, dst, cfg, wm_img, wm_wh, key, ffmpeg, ffprobe):
    info = probe(src, ffprobe)
    ww, wh = watermark_size(wm_wh, info["base_edge"], cfg.LONG_EDGE_DIV)
    wm_use, ww, wh, wm_rot = prepare_watermark(
        wm_img, ww, wh, info["rotation"])
    t = track(key, info["width"], info["height"], ww, wh, cfg)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd, audio_mode = build_cmd(src, dst, wm_use, ww, wh, t,
                                info, cfg, ffmpeg)
    r = run(cmd)
    pix_note = "original"
    if r.returncode != 0:
        info2 = dict(info)
        info2["pix_fmt"] = "yuv420p"
        cmd2, audio_mode = build_cmd(src, dst, wm_use, ww, wh, t,
                                     info2, cfg, ffmpeg)
        r2 = run(cmd2)
        if r2.returncode != 0:
            raise RuntimeError("ffmpeg 渲染失败:\n" + (r2.stderr or r.stderr or "")[-1200:])
        pix_note = "fallback-yuv420p"
    return dict(info=info, track=t, ww=ww, wh=wh, wm_rot=wm_rot,
                audio_mode=audio_mode, pix_note=pix_note)


def main():
    ap = argparse.ArgumentParser(description="zg_shuiyin_skill：给视频加确定性浮动水印")
    ap.add_argument("inputs", nargs="+", help="视频文件或文件夹，可多个")
    ap.add_argument("--out", default=None, help="输出根目录（默认各源目录下 水印版/）")
    ap.add_argument("--watermark", default=None, help="当次指定新水印图（不写则用默认）")
    ap.add_argument("--alpha", type=float, default=None, help="透明度，默认 0.5")
    ap.add_argument("--ratio", type=float, default=None, help="基准边除数，默认 20")
    ap.add_argument("--crf", type=int, default=None, help="CRF，默认 14")
    ap.add_argument("--overwrite", action="store_true", help="覆盖已有成片")
    ap.add_argument("--no-check", action="store_true", help="跳过质检（仅调试用）")
    ap.add_argument("--report", default=None, help="质检报告输出路径")
    a = ap.parse_args()

    if a.watermark:
        C.WATERMARK = str(Path(a.watermark).resolve())
    if a.alpha is not None:
        C.ALPHA = a.alpha
    if a.ratio is not None:
        C.LONG_EDGE_DIV = a.ratio
    if a.crf is not None:
        C.CRF = a.crf

    wm = Path(C.WATERMARK)
    if not wm.is_file():
        raise SystemExit("找不到水印图片: %s" % wm)
    wm_wh = Image.open(wm).size
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()

    items = collect(a.inputs, C.VIDEO_EXTS, C.OUT_DIRNAME)
    if not items:
        raise SystemExit("没有找到可处理的视频文件")
    print("找到 %d 个视频 | 水印 %s %s | alpha=%.2f | 1/%s | CRF=%d"
          % (len(items), wm.name, wm_wh, C.ALPHA, C.LONG_EDGE_DIV, C.CRF))

    results = []
    for i, (src, rel) in enumerate(items, 1):
        dst = out_path_for(src, rel, a.out, C.OUT_DIRNAME,
                           C.OUT_SUFFIX, C.OUTPUT_EXT)
        if (dst.exists() and dst.stat().st_size > 0
                and C.SKIP_EXISTING and not a.overwrite):
            print("[%d/%d] SKIP 已存在 %s" % (i, len(items), dst.name))
            results.append(dict(src=str(src), dst=str(dst), status="SKIP"))
            continue
        try:
            meta = render_one(src, dst, C, str(wm), wm_wh, rel,
                              ffmpeg, ffprobe)
            chk = None
            if not a.no_check:
                import wm_check
                chk = wm_check.check_pair(src, dst, C, wm_wh, rel,
                                          ffmpeg, ffprobe, meta)
            st = "PASS" if (chk is None or chk["pass"]) else "FAIL"
            print("[%d/%d] %s %s -> %s" % (i, len(items), st, src.name, dst.name))
            results.append(dict(src=str(src), dst=str(dst), status=st,
                                size_mb=round(dst.stat().st_size / 1048576, 2),
                                wm_size=[meta["ww"], meta["wh"]],
                                seed=meta["track"]["seed"],
                                audio=meta["audio_mode"],
                                pix=meta["pix_note"],
                                info=meta["info"], check=chk))
        except Exception as e:
            print("[%d/%d] FAIL %s : %s" % (i, len(items), src.name, e))
            results.append(dict(src=str(src), dst=str(dst), status="FAIL",
                                error=str(e), trace=traceback.format_exc()))

    report_dir = Path(a.report).parent if a.report else (
        Path(a.out) if a.out else Path(results[0]["dst"]).parent)
    report_dir.mkdir(parents=True, exist_ok=True)
    rp = Path(a.report) if a.report else (report_dir / "质检报告.json")
    payload = dict(skill="zg_shuiyin_skill", watermark=str(wm),
                   config=dict(alpha=C.ALPHA, div=C.LONG_EDGE_DIV,
                               crf=C.CRF, preset=C.PRESET,
                               track=C.TRACK_MODE, bounds=C.BOUNDS),
                   results=results)
    rp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    md = report_dir / "质检报告.md"
    lines = ["# zg_shuiyin_skill · 质检报告", "",
             "水印：`%s`　透明度：%.2f　尺寸：基准边 1/%s　CRF：%d"
             % (wm.name, C.ALPHA, C.LONG_EDGE_DIV, C.CRF), "",
             "| 文件 | 结果 | 水印尺寸 | 清晰度比 | 音频 | 轨迹种子 |",
             "|---|---|---|---|---|---|"]
    for r in results:
        c = r.get("check") or {}
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            Path(r["src"]).name, r["status"],
            r.get("wm_size", "-"),
            ("%.3f" % c["sharpness_ratio"]) if c.get("sharpness_ratio") else "-",
            r.get("audio", "-"), r.get("seed", "-")))
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    print("汇总: PASS=%d SKIP=%d FAIL=%d | 报告 %s" % (
        sum(1 for r in results if r["status"] == "PASS"),
        sum(1 for r in results if r["status"] == "SKIP"), n_fail, rp))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
