# zg_shuiyin_skill

**先说结论**：你不需要记任何命令，也不用给我讲参数。技能本质就是一个含 `SKILL.md` 的目录，
Agent 自己会拉取、复制、校验 —— **你只要说一句话**。

## 一句话装（把下面这段整个复制给你的 Agent）

```plaintext
帮我装这个技能：https://github.com/630886916/zg_shuiyin_skill
```

装完刷新会话（或新开一个），直接说：

```plaintext
给这个视频加水印 D:\素材\a.mp4
```

多素材就一句：

```plaintext
把这几个素材拼起来加水印
```

（说「加水印」= 整套默认参数照搬，它不会再逐项问你。）

## 不想经过 Agent？复制一行就完事

| 你的情况 | 复制这一行 |
|---|---|
| **Windows，想自己装** | `irm https://raw.githubusercontent.com/630886916/zg_shuiyin_skill/main/install.ps1 \| iex` |
| **Mac / Linux** | `curl -fsSL https://raw.githubusercontent.com/630886916/zg_shuiyin_skill/main/install.sh \| bash` |
| **Claude Code / Cursor / Codex** | `npx -y skills add 630886916/zg_shuiyin_skill --skill zg_shuiyin_skill -g` |
| **完全不想碰命令行** | 下载 [`dist/zg_shuiyin_skill.zip`](dist/zg_shuiyin_skill.zip) → 解压 → 双击 `安装.bat` |

> 四条路都会顺手检查 Python 依赖（`imageio-ffmpeg` / `pillow` / `numpy` / `opencv-python`），
> 缺了自动装。装完想单独确认：`python ~/.workbuddy/skills/zg_shuiyin_skill/scripts/wm_env_check.py`
>
> ⚠️ `npx skills` 的 Agent 列表里**没有 workbuddy**（最接近的 `codebuddy` 会装到 `.codebuddy/skills/`），
> WorkBuddy 用户请用**第一屏那句话**或 `install.ps1`，它们会装到 `~/.workbuddy/skills/`。

## 更新到最新版

| 你的情况 | 复制这一行 |
|---|---|
| 装的时候用了 npx | `npx skills update zg_shuiyin_skill -g` |
| 装的时候用了 install 脚本 | 重跑一次同一条安装命令（会覆盖旧版） |
| WorkBuddy / 不想碰命令行 | 重跑 `install.ps1`，或重新解压 zip 双击 `安装.bat` |
| 只想看看有没有新版 | `npx skills check` |

> 更新是**覆盖式**的：技能文件被仓库最新版替换，你本地改过的内容会被覆盖。

---

## 它到底干什么

把固定设计的水印图叠到视频上，**保持原视频高清**；给多个素材时，先理解内容、自动编排、
拼接成一条完整视频，**再**给这条完整视频加水印。

| 项 | 默认值（说「加水印」就是这套） |
|---|---|
| 水印图 | 内置中工 LOGO（1882×719，RGBA 透明底），随包分发 |
| 透明度 | **50%**（在图片自身 alpha 上再乘 0.5） |
| 尺寸 | 水印最长边 = **画面基准边 ÷ 4**（横屏取宽、竖屏取高） |
| 实际像素 | 720×1280 → **320×122**；1080×1920 → 270×103；1920×1080 → 480×183 |
| 时段 | 全程常驻 |
| 运动 | 确定性伪随机轨迹，缓慢连续斜向漂移（同素材永远同一条） |
| 画质 | libx264 **CRF14** / slow / aq-mode 3；不缩放、不裁剪、不改帧率、不改时长 |
| 音频 | 直通 copy（mp4 不兼容才回退 aac 192k） |
| 输出 | 原片只读 → `水印版/<原名>_水印版.mp4` |
| 质检 | 清晰度比 ≥0.95、水印位置实证、轨迹不越界，逐条出报告 |

### 两条路由（决定画质，不会走错）

| 输入 | 链路 |
|---|---|
| **1 个视频** | 直接加水印，**绝不拼接**（多拼一次就多一代重编码） |
| **≥2 个素材**（视频/图片任意混） | 理解内容 → 编排 → 拼接成完整视频 → **再**加水印 |

多素材会输出两个文件：`拼接成片_拼接版.mp4`（无水印完整版）+ `水印版/..._水印版.mp4`，
并附 `剪辑方案.md`（顺序、每段时长、转场类型、编排依据）和质检报告。

### 你会说的话 → 它做的事

| 你说 | 它做 |
|---|---|
| 给这个视频加水印 `a.mp4` | 单条加水印 + 质检报告 + 首帧对比图 |
| 给这个文件夹下所有视频加水印 `D:\素材\` | 递归批量，自动跳过已处理，汇总报告 |
| 把这几个素材拼起来加水印（4 视频 + 1 图片） | 抽帧理解 → 编排 → 拼接 → 加水印，附剪辑方案 |
| 加水印，这次用 `D:\logo.png` | 只这一次换水印图 |
| 加水印，水印再大一点 | 当次用 `--ratio 2.5`（约 8 倍） |
| 加水印，透明度降到 70% | 当次用 `--alpha 0.7` |

---

## 常见问题

**Q：装完 Agent 还是说没这个技能？**
确认技能目录里有 `SKILL.md`：WorkBuddy 是 `%USERPROFILE%\.workbuddy\skills\zg_shuiyin_skill\SKILL.md`，
Claude Code 是 `~/.claude/skills/`，Codex 是 `~/.codex/skills/`。装完要**刷新会话**才加载。

**Q：加水印会不会降画质？**
叠加水印必须重编码，「不重编码无损」做不到。本技能的做法：原始分辨率/帧率/时长/色彩标记全不变
+ CRF14 + 音频直通，再用「清晰度比 ≥0.95」量化验收（真实口播素材实测 0.96，4K 在观看分辨率下 0.99）。

**Q：手机竖拍素材水印会不会转歪？**
不会。单素材保留原 `rotation` 并按方向预旋转水印；多素材拼接先按播放器视角转正，
再清掉残留 Display Matrix（流拷贝，零画质损失）。

**Q：能不能去掉别人视频上的水印？**
不能，也没这个功能。仅用于给**自有或已获授权**的素材打自己的水印。

**Q：`安装.bat` 在 GitHub 网页里是乱码？**
它是 GBK 编码（Windows cmd 需要），不是损坏，下载到本地双击正常。

---

## 环境要求

| 项 | 要求 |
|---|---|
| 系统 | Windows（已验证）；macOS / Linux 走 `install.sh`，ffmpeg 逻辑一致但未实测 |
| Python | 3.9+ |
| 依赖 | `imageio-ffmpeg`、`pillow`、`numpy`、`opencv-python`（必需）；`faster-whisper`（可选，多素材时辅助理解口播） |
| ffmpeg | **不用单独装**，脚本自动用 `imageio-ffmpeg` 自带的那份 |

## 目录结构

```text
zg_shuiyin_skill/
├─ skills/zg_shuiyin_skill/          # ← npx skills 识别的技能本体
│  ├─ SKILL.md                       # Agent 读这个
│  ├─ assets/watermark.png           # 默认水印图（换图 = 覆盖它）
│  └─ scripts/
│     ├─ wm_config.py                # 参数唯一来源（改默认值只改这里）
│     ├─ wm_core.py                  # ffmpeg 发现 / 元数据探测 / 确定性轨迹
│     ├─ wm_render.py                # 单条与批量渲染 + 质检
│     ├─ wm_check.py                 # 量化质检（清晰度比 / 位置实证）
│     ├─ wm_understand.py            # 抽关键帧 + 口播转写（多素材理解）
│     ├─ wm_compose.py               # 统一规格 + xfade + acrossfade 拼接
│     ├─ wm_pipeline.py              # 总入口与路由
│     └─ wm_env_check.py             # 环境自检
├─ install.ps1 / install.sh          # 一键安装脚本（上面表格里那两条）
├─ dist/zg_shuiyin_skill.zip         # 离线安装包
├─ 安装.bat / 环境检查.bat            # Windows 双击安装（GBK）
└─ README.md
```

## 许可

MIT，见 [LICENSE](LICENSE)。
