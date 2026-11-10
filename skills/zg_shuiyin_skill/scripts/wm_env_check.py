# -*- coding: utf-8 -*-
"""zg_shuiyin_skill · 环境自检。由 环境检查.bat 调用，也可直接 python wm_env_check.py。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
ok_all = True


def line(name, ok, extra=""):
    global ok_all
    ok_all = ok_all and ok
    print("[%s] %-16s %s" % ("OK" if ok else "X ", name, extra))


print("=" * 56)
print("zg_shuiyin_skill · 环境检查")
print("=" * 56)
line("Python", sys.version_info >= (3, 9), sys.version.split()[0])

try:
    from wm_core import find_ffmpeg, find_ffprobe
    line("ffmpeg", True, find_ffmpeg())
    line("ffprobe", True, find_ffprobe())
except Exception as e:
    line("ffmpeg/ffprobe", False, str(e))

for mod in ("PIL", "numpy", "cv2", "imageio_ffmpeg"):
    try:
        __import__(mod)
        line(mod, True)
    except Exception as e:
        line(mod, False, str(e))

try:
    import faster_whisper  # noqa: F401
    line("faster-whisper", True, "可选：口播转写可用")
except Exception:
    print("[--] %-16s %s" % ("faster-whisper",
                             "可选：未安装，自动降级为纯视觉理解（不影响出片）"))

try:
    from wm_understand import find_whisper_model
    mp = find_whisper_model()
    print("[--] %-16s %s" % ("ASR 模型",
                             "本地缓存: " + mp if "/" in mp or "\\" in mp
                             else "用模型名 " + mp + "（首次可能需联网）"))
except Exception as e:
    print("[--] %-16s %s" % ("ASR 模型", str(e)[:60]))

wm = ROOT / "assets" / "watermark.png"
line("默认水印图", wm.is_file(), str(wm))
line("SKILL.md", (ROOT / "SKILL.md").is_file())

print("-" * 56)
print("环境检查通过，可以使用zg_shuiyin_skill。" if ok_all
      else "环境检查未通过，请按上面 [X ] 项修复后再用。")
sys.exit(0 if ok_all else 1)
