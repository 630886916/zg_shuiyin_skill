# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 按 edit_plan.json 拼成完整视频（多素材链路第 3 步）。

关键工艺：
- 以第一条视频为基准统一规格；其余素材等比缩放 + 模糊压暗底填充，**不裁切**。
- overlay 用 format=yuv420（不能用 auto，否则 YUV→RGB→YUV 往返白损清晰度）。
- 画面 xfade 串接 / 声音 acrossfade 串接，最后一次编码出「无水印拼接版」。
- 缺音轨的素材用 anullsrc 补静音，保证音频链能串起来。

用法： python wm_compose.py <edit_plan.json> --out <拼接版.mp4>
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wm_config as C
from wm_core import find_ffmpeg, find_ffprobe, probe, run


def norm_chain(i, kind, clip, W, H, fps, D):
    """把一个输入归一化成 [v{i}] / [a{i}]，含模糊底不裁切。"""
    in_v = "%d:v" % i
    if kind == "video":
        head = ("[{v}]trim=start={s:.3f},setpts=PTS-STARTPTS"
                .format(v=in_v, s=float(clip.get("in", 0))))
    else:
        head = "[{v}]setpts=PTS-STARTPTS".format(v=in_v)
    parts = [
        head + ",split=2[fg{i}][bg{i}]".format(i=i),
        ("[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,"
         "crop={W}:{H},boxblur={R}:2,eq=brightness={K}[bgb{i}]").format(
             i=i, W=W, H=H, R=C.BLUR_RADIUS, K=C.BLUR_DARKEN),
        ("[fg{i}]scale={W}:{H}:force_original_aspect_ratio=decrease:"
         "flags=lanczos[fgs{i}]").format(i=i, W=W, H=H),
        ("[bgb{i}][fgs{i}]overlay=({W}-w)/2:({H}-h)/2:format=yuv420,"
         "setsar=1,format=yuv420p,settb=AVTB,"
         "trim=duration={D:.3f},setpts=N/({F}*TB),fps={F}[v{i}]").format(
             i=i, W=W, H=H, F=fps, D=D),
    ]
    return parts


def audio_chain(i, has_audio, D, SR):
    if has_audio:
        return ("[{i}:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,"
                "aformat=sample_rates={SR}:channel_layouts=stereo[a{i}]").format(
                    i=i, D=D, SR=SR)
    return ("anullsrc=r={SR}:cl=stereo,atrim=duration={D:.3f},"
            "asetpts=PTS-STARTPTS[a{i}]").format(i=i, D=D, SR=SR)


def compose(plan_path, out_path, ffmpeg=None, ffprobe=None):
    ffmpeg = ffmpeg or find_ffmpeg()
    ffprobe = ffprobe or find_ffprobe()
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    clips = plan["clips"]
    if not clips:
        raise RuntimeError("edit_plan.json 里没有 clips")
    t = plan["target"]
    W, H, fps = int(t["width"]), int(t["height"]), int(t["fps"])
    SR = int(t.get("sample_rate", C.COMPOSE_SR))
    TD = float(clips[0].get("transition_duration", C.TRANSITION_DURATION))
    AC = float(plan.get("audio", {}).get("crossfade", C.AUDIO_CROSSFADE))

    # 转场合法性 + 片段最短时长校验
    for c in clips:
        tr = str(c.get("transition", "fade"))
        if tr not in C.TRANSITIONS and tr != "none":
            c["transition"] = "fade"
        D = float(c["duration"])
        if D <= TD + 0.3:
            raise RuntimeError("片段 %s 时长 %.2fs 太短，无法容纳 %.2fs 转场"
                               % (c["id"], D, TD))

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    has_audio = []
    for i, c in enumerate(clips):
        D = float(c["duration"])
        src = c["src"]
        if c["kind"] == "video":
            cmd += ["-i", src]
            info = probe(src, ffprobe)
            has_audio.append(bool(info["acodec"]))
        else:
            cmd += ["-loop", "1", "-framerate", str(fps),
                    "-t", "%.3f" % D, "-i", src]
            has_audio.append(False)

    graph = []
    for i, c in enumerate(clips):
        graph += norm_chain(i, c["kind"], c, W, H, fps, float(c["duration"]))
        graph.append(audio_chain(i, has_audio[i], float(c["duration"]), SR))

    # xfade / acrossfade 链式串接
    durations = [float(c["duration"]) for c in clips]
    vcur, acur = "v0", "a0"
    acc = durations[0]
    for k in range(1, len(clips)):
        offset = acc - k * TD
        tr = str(clips[k].get("transition", "fade"))
        if tr == "none":
            tr = "fade"
        nv, na = "x%d" % k, "y%d" % k
        graph.append("[%s][v%d]xfade=transition=%s:duration=%.3f:offset=%.3f[%s]"
                     % (vcur, k, tr, TD, offset, nv))
        graph.append("[%s][a%d]acrossfade=d=%.3f:c1=tri:c2=tri[%s]"
                     % (acur, k, AC, na))
        vcur, acur = nv, na
        acc += durations[k]
    total_v = sum(durations) - (len(clips) - 1) * TD
    graph.append("[%s]apad,atrim=duration=%.3f,asetpts=PTS-STARTPTS[aout]"
                 % (acur, total_v))
    last_v = vcur
    graph_text = ";\n".join(graph)

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", graph_text,
            "-map", "[%s]" % last_v, "-map", "[aout]",
            "-c:v", "libx264", "-preset", C.PRESET, "-crf", str(C.COMPOSE_CRF),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            "-map_metadata", "-1", "-movflags", "+faststart", str(out_path)]
    r = run(cmd)
    if r.returncode != 0 or not out_path.is_file():
        raise RuntimeError("拼接渲染失败:\n" + (r.stderr or "")[-2000:])

    # ★ 旋转素材二次旋转修复（2026-11-10 真实素材实测）
    # ffmpeg 默认 autorotate：把 rotation=±90 的输入**画面**转成正立输出，
    # 却仍把第一条输入的 Display Matrix 继承到输出流。结果成片是
    # 「720x1280 正立像素 + rotation=-90」，播放器会再转 90° -> 整片横躺，
    # 且下游加水印会误触发「预旋转水印」。
    # -metadata rotate=0 对 side data 无效；只有输入侧 -display_rotation:v:0 0
    # 配 -c copy 能清掉，且是流拷贝、零重编码零画质损失。
    if probe(out_path, ffprobe)["rotation"]:
        fixed = out_path.with_name(out_path.stem + "_norot" + out_path.suffix)
        r2 = run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                  "-display_rotation:v:0", "0", "-i", str(out_path),
                  "-c", "copy", "-map", "0", "-movflags", "+faststart", str(fixed)])
        if r2.returncode != 0 or not fixed.is_file():
            raise RuntimeError("旋转元数据清零失败:\n" + (r2.stderr or "")[-1200:])
        fixed.replace(out_path)
        print("[拼接] 已清除残留 rotation 元数据（流拷贝，无画质损失）")
    meta = dict(plan=str(Path(plan_path).resolve()),
                out=str(out_path), target=dict(width=W, height=H, fps=fps),
                total_duration=round(total_v, 3),
                transition_duration=TD, audio_crossfade=AC,
                clips=[dict(id=c["id"], kind=c["kind"], name=c.get("name", ""),
                            duration=float(c["duration"]),
                            transition=c.get("transition"),
                            reason=c.get("reason", "")) for c in clips],
                filter_complex=graph_text)
    (out_path.parent / "拼接信息.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main():
    ap = argparse.ArgumentParser(description="zg_shuiyin_skill 按方案拼接")
    ap.add_argument("plan")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m = compose(a.plan, a.out)
    print("拼接完成: %s" % m["out"])
    print("规格 %dx%d @%dfps | 时长 %.2fs | %d 段"
          % (m["target"]["width"], m["target"]["height"],
             m["target"]["fps"], m["total_duration"], len(m["clips"])))


if __name__ == "__main__":
    main()
