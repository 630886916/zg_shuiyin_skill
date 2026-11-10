# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 素材理解（多素材链路第 1 步）。

对每条素材产出：ffprobe 元数据 + 关键帧 contact sheet + 口播转写（faster-whisper，可选）。
同时生成一份可直接执行的默认 edit_plan.json —— AI 读卡片和缩略图后可改写它。

用法：
  python wm_understand.py <素材/文件夹...> --work <工作目录>
  python wm_understand.py <素材...> --work <工作目录> --no-asr
"""
import sys
import json
import math
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wm_config as C
from wm_core import find_ffmpeg, find_ffprobe, probe, run


def collect_mixed(inputs):
    items = []
    for raw in inputs:
        p = Path(raw).resolve()
        if p.is_file():
            if p.suffix.lower() in C.VIDEO_EXTS:
                items.append((p, "video"))
            elif p.suffix.lower() in C.IMAGE_EXTS:
                items.append((p, "image"))
        elif p.is_dir():
            for q in sorted(p.rglob("*")):
                if C.OUT_DIRNAME in q.parts or C.COMPOSE_SUFFIX.strip("_") in q.parts:
                    continue
                if q.suffix.lower() in C.VIDEO_EXTS:
                    items.append((q, "video"))
                elif q.suffix.lower() in C.IMAGE_EXTS:
                    items.append((q, "image"))
    return items


def make_sheet(ffmpeg, path, kind, dur, out):
    """视频：均匀抽 8 帧拼 4 列网格；图片：单张缩略图。供 AI 逐张看。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "image":
        im = Image.open(path).convert("RGB")
        w = 640
        im.resize((w, max(1, int(im.height * w / im.width)))).save(out, quality=88)
        return str(out)
    tmp = out.parent / ("_frames_" + out.stem)
    tmp.mkdir(exist_ok=True)
    times = [max(0.05, dur * (0.07 + 0.86 * i / max(1, C.SHEET_FRAMES - 1)))
             for i in range(C.SHEET_FRAMES)]
    ims = []
    for i, t in enumerate(times):
        p = tmp / ("f%02d.png" % i)
        # 不能加 -noautorotate：手机竖拍素材（rotation=±90）抽出来会是横躺的，
        # AI 据以理解内容就会看歪。让 ffmpeg 自动应用 display matrix，
        # 抽出的帧与播放器视角一致（2026-11-10 实测：4 条 rotation=-90 素材）。
        run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
             "-ss", "%.3f" % t, "-i", str(path),
             "-frames:v", "1", str(p)])
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGB")
        tw = C.SHEET_THUMB_W
        im = im.resize((tw, max(1, int(im.height * tw / im.width))))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 76, 18], fill=(0, 0, 0))
        d.text((4, 3), "t=%.1fs" % t, fill=(255, 255, 255))
        ims.append(im)
    if not ims:
        return ""
    cols = C.SHEET_COLS
    rows = math.ceil(len(ims) / cols)
    cw, ch = max(i.width for i in ims), max(i.height for i in ims)
    canvas = Image.new("RGB", (cw * cols, ch * rows), (24, 24, 24))
    for k, im in enumerate(ims):
        canvas.paste(im, ((k % cols) * cw, (k // cols) * ch))
    canvas.save(out, quality=88)
    return str(out)


def find_whisper_model():
    """优先用本机 HF 缓存里的本地目录，避免联网。"""
    p = (Path.home() / ".cache" / "huggingface" / "hub" /
         "models--Systran--faster-whisper-small" / "snapshots")
    if p.exists():
        for d in sorted(p.iterdir()):
            if d.is_dir() and (d / "model.bin").exists():
                return str(d)
    return C.ASR_MODEL


_MODEL = None


def _audio_is_quiet(wav, threshold_db=-35.0):
    """纯静音/近静音素材跳过 ASR：whisper 会在静音段脑补文字（幻觉词坑）。"""
    import wave
    import numpy as np
    try:
        with wave.open(str(wav), "rb") as f:
            raw = f.readframes(f.getnframes())
        if not raw:
            return True
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(a * a)))
        return 20 * math.log10(rms + 1e-9) < threshold_db
    except Exception:
        return False


def transcribe(ffmpeg, path, out_wav):
    global _MODEL
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
         "-f", "wav", str(out_wav)])
    if not out_wav.is_file() or _audio_is_quiet(out_wav):
        return ""
    try:
        from faster_whisper import WhisperModel
        if _MODEL is None:
            _MODEL = WhisperModel(find_whisper_model(), device="cpu",
                                  compute_type="int8")
        segs, _ = _MODEL.transcribe(str(out_wav), language=C.ASR_LANG,
                                    beam_size=5, vad_filter=False)
        return "".join(s.text for s in segs).strip()
    except Exception as e:
        print("WARN ASR 跳过 (%s): %s" % (type(e).__name__, str(e)[:120]))
        return ""


def default_plan(cards):
    """基准 = 第一条视频的显示尺寸与帧率；其余模糊底填充，不裁切。"""
    vids = [c for c in cards if c["kind"] == "video"]
    if vids:
        b = vids[0]
        W, H = b["disp_w"], b["disp_h"]
        fps = b["avg_fps"] if 15 <= b["avg_fps"] <= 120 else C.COMPOSE_FALLBACK_FPS
        basis = "第一条视频 " + b["name"]
    else:
        W, H = C.COMPOSE_FALLBACK_W, C.COMPOSE_FALLBACK_H
        fps = C.COMPOSE_FALLBACK_FPS
        basis = "全是图片，用兜底规格 1080x1920/30"
    fps = int(round(fps))
    clips = []
    for i, c in enumerate(cards):
        if c["kind"] == "video":
            d = c.get("duration") or 3.0
            reason = "默认：按输入顺序，整段使用"
        else:
            d = C.IMG_DURATION_DEFAULT
            reason = "默认：图片 3s（AI 按前后口播节奏改为 2~5s）"
        clips.append(dict(
            id=c["id"], kind=c["kind"], src=c["path"], name=c["name"],
            **{"in": 0.0}, out=round(float(d), 3), duration=round(float(d), 3),
            transition="none" if i == 0 else "fade",
            transition_duration=C.TRANSITION_DURATION,
            reason=reason))
    return dict(
        version=1, skill="zg_shuiyin_skill",
        target=dict(width=W, height=H, fps=fps,
                    sample_rate=C.COMPOSE_SR, channels=C.COMPOSE_CHANNELS),
        basis=basis,
        audio=dict(mode=C.AUDIO_MODE, crossfade=C.AUDIO_CROSSFADE),
        clips=clips,
        note=("AI 读 素材卡片.json 与 contact_sheet/ 后可改写：clips 顺序、"
              "in/out 截取、图片 duration(2~5)、transition，并填写 reason。"
              "改写后重跑 compose 即按新方案出片，方案随成片一起交付。"))


def main():
    ap = argparse.ArgumentParser(description="zg_shuiyin_skill 素材理解")
    ap.add_argument("inputs", nargs="+", help="视频 / 图片 / 文件夹，可多个")
    ap.add_argument("--work", required=True, help="工作目录（放素材卡片、缩略图、方案）")
    ap.add_argument("--no-asr", action="store_true", help="跳过口播转写")
    a = ap.parse_args()

    work = Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    items = collect_mixed(a.inputs)
    if not items:
        raise SystemExit("没有找到视频或图片素材")
    ffmpeg, ffprobe = find_ffmpeg(), find_ffprobe()

    cards = []
    for i, (p, kind) in enumerate(items, 1):
        cid = "%02d" % i
        c = dict(id=cid, path=str(p), name=p.name, kind=kind, index=i - 1)
        sheet = work / "contact_sheet" / ("sheet_%s.jpg" % cid)
        if kind == "video":
            info = probe(p, ffprobe)
            c.update(duration=round(info["duration"], 3),
                     width=info["width"], height=info["height"],
                     disp_w=info["disp_w"], disp_h=info["disp_h"],
                     rotation=info["rotation"],
                     avg_fps=round(info["avg_fps"], 3),
                     has_audio=bool(info["acodec"]), acodec=info["acodec"])
            make_sheet(ffmpeg, p, kind, info["duration"], sheet)
            c["sheet"] = str(sheet)
            c["asr"] = ("" if (a.no_asr or not c["has_audio"])
                        else transcribe(ffmpeg, p, work / "_asr" / ("a_%s.wav" % cid)))
        else:
            im = Image.open(p)
            c.update(width=im.width, height=im.height,
                     disp_w=im.width, disp_h=im.height,
                     duration=0.0, has_audio=False, asr="")
            make_sheet(ffmpeg, p, kind, 0, sheet)
            c["sheet"] = str(sheet)
        cards.append(c)
        extra = ""
        if c.get("asr"):
            extra = " | 口播: " + c["asr"][:36]
        print("[%s] %-5s %-30s %6.1fs%s"
              % (cid, kind, p.name[:30], c.get("duration") or 0, extra))

    card_path = work / "素材卡片.json"
    card_path.write_text(json.dumps(dict(items=cards,
                                        asr_model=C.ASR_MODEL,
                                        asr_enabled=not a.no_asr),
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path = work / "edit_plan.json"
    plan_path.write_text(json.dumps(default_plan(cards), ensure_ascii=False,
                                    indent=2), encoding="utf-8")
    print("素材卡片:", card_path)
    print("默认方案:", plan_path)
    print("缩略图  :", work / "contact_sheet")


if __name__ == "__main__":
    main()
