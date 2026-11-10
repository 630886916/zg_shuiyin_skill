# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 总入口与路由。

路由铁律：
  1 个视频素材           -> 直接加水印，绝不进拼接流程（不多一代重编码）
  >=2 个素材（视频/图片混）-> 理解 -> 编排 -> 拼接成完整视频 -> 再加水印

用法：
  # 单素材
  python wm_pipeline.py D:/素材/a.mp4

  # 多素材：先分析，AI 读 素材卡片.json + contact_sheet/ 后改写 edit_plan.json
  python wm_pipeline.py D:/素材夹 --work D:/work --analyze
  # 按方案出片
  python wm_pipeline.py D:/素材夹 --work D:/work --plan D:/work/edit_plan.json

  # 不经过 AI 编排、直接用默认方案一键出片
  python wm_pipeline.py D:/素材夹 --work D:/work
"""
import sys
import json
import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wm_config as C
from wm_understand import collect_mixed

RENDER = HERE / "wm_render.py"
UNDERSTAND = HERE / "wm_understand.py"
COMPOSE = HERE / "wm_compose.py"


def call(args):
    r = subprocess.run([sys.executable] + [str(x) for x in args])
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def write_plan_md(work, plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    t = plan["target"]
    lines = ["# zg_shuiyin_skill · 剪辑方案", "",
             "输出规格：%dx%d @ %dfps　基准：%s" %
             (t["width"], t["height"], t["fps"], plan.get("basis", "-")),
             "声音：%s，交叉淡化 %.2fs　画面转场 %.2fs" %
             (plan.get("audio", {}).get("mode", C.AUDIO_MODE),
              plan.get("audio", {}).get("crossfade", C.AUDIO_CROSSFADE),
              plan["clips"][0].get("transition_duration", C.TRANSITION_DURATION)),
             "", "| 序 | 素材 | 类型 | 时长 | 转场 | 编排依据 |",
             "|---|---|---|---|---|---|"]
    for n, c in enumerate(plan["clips"], 1):
        lines.append("| %d | %s | %s | %.2fs | %s | %s |" %
                     (n, c.get("name", Path(c["src"]).name), c["kind"],
                      float(c["duration"]), c.get("transition", "-"),
                      c.get("reason", "-")))
    lines += ["", "素材卡片：`素材卡片.json`　关键帧缩略图：`contact_sheet/`",
              "完整方案（可编辑重跑）：`edit_plan.json`　实际滤镜：`拼接信息.json`", ""]
    p = work / "剪辑方案.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser(description="zg_shuiyin_skill 总入口")
    ap.add_argument("inputs", nargs="+", help="视频 / 图片 / 文件夹，可多个")
    ap.add_argument("--work", default=None, help="多素材工作目录")
    ap.add_argument("--plan", default=None, help="指定 edit_plan.json（AI 改写后用）")
    ap.add_argument("--analyze", action="store_true",
                    help="只生成素材卡片与方案，不出片（等 AI 编排）")
    ap.add_argument("--no-asr", action="store_true", help="跳过口播转写")
    ap.add_argument("--force-understand", action="store_true",
                    help="强制重新生成素材卡片与默认方案")
    ap.add_argument("--watermark", default=None)
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--ratio", type=float, default=None)
    ap.add_argument("--crf", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    render_flags = []
    if a.watermark:
        render_flags += ["--watermark", a.watermark]
    if a.alpha is not None:
        render_flags += ["--alpha", str(a.alpha)]
    if a.ratio is not None:
        render_flags += ["--ratio", str(a.ratio)]
    if a.crf is not None:
        render_flags += ["--crf", str(a.crf)]
    if a.overwrite:
        render_flags += ["--overwrite"]

    items = collect_mixed(a.inputs)
    if not items:
        raise SystemExit("没有找到视频或图片素材")

    # --- 单素材：直接加水印，不进拼接 ---
    if len(items) == 1 and items[0][1] == "video":
        print("[路由] 单个视频 -> 直接加水印（跳过拼接，不多一代重编码）")
        call([RENDER, items[0][0]] + render_flags)
        return

    # --- 多素材 ---
    print("[路由] %d 个素材（视频 %d / 图片 %d）-> 理解 -> 编排 -> 拼接 -> 加水印"
          % (len(items), sum(1 for _, k in items if k == "video"),
             sum(1 for _, k in items if k == "image")))
    work = Path(a.work).resolve() if a.work else (
        items[0][0].parent / "_zg_shuiyin_skill_work")
    work.mkdir(parents=True, exist_ok=True)
    plan_path = Path(a.plan).resolve() if a.plan else (work / "edit_plan.json")

    if a.force_understand or not plan_path.exists():
        u = [UNDERSTAND] + [str(p) for p, _ in items] + ["--work", work]
        if a.no_asr:
            u += ["--no-asr"]
        call(u)

    md = write_plan_md(work, plan_path)
    if a.analyze:
        print("[分析完成] 素材卡片 / 缩略图 / 方案已生成：")
        print("  ", work / "素材卡片.json")
        print("  ", work / "contact_sheet")
        print("  ", plan_path)
        print("  ", md)
        print("AI 读完后改写 edit_plan.json，再去掉 --analyze 重跑即出片。")
        return

    composed = work / ("拼接成片" + C.COMPOSE_SUFFIX + C.OUTPUT_EXT)
    call([COMPOSE, plan_path, "--out", composed])
    print("[拼接版]", composed)

    out_dir = work / C.OUT_DIRNAME
    call([RENDER, composed, "--out", out_dir] + render_flags)
    print("[完成] 拼接版 + 水印版 + 剪辑方案 + 质检报告 均在", work)


if __name__ == "__main__":
    main()
