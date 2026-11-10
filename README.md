# zg_shuiyin_skill · 给视频加水印（高清不降级 + 多素材智能拼接）

一个 **AI Agent 技能**：把你固定设计的水印图叠到视频上，**保持原视频高清**；
给多个素材（视频 / 图片任意混合）时，会先理解内容与逻辑、自动编排顺序与转场、
拼成一条完整视频，**再**给这条完整视频加水印。

- 当前版本：**v1.0.0**（2026-11-10）
- 默认水印：中工 LOGO（1882×719 / RGBA 透明底），随包分发
- 适用素材：手机竖拍（含 `rotation=±90`）、横屏、4K、图片

---

## 一、一句话安装

```bash
npx skills add 630886916/zg_shuiyin_skill --skill zg_shuiyin_skill -g
```

`-g` = 装到用户级目录，所有项目可用；去掉 `-g` 则只装到当前项目。

支持 Claude Code、Codex、Cursor、CodeBuddy、Gemini CLI、Windsurf、Cline、Roo Code
等 70+ 个 Agent（由 [`skills`](https://github.com/vercel-labs/skills) CLI 自动探测本机已装的 Agent）。

**只装一次、不想交互？**

```bash
npx skills add 630886916/zg_shuiyin_skill --skill zg_shuiyin_skill -g -y
```

**指定 Agent（例如 Codex）：**

```bash
npx skills add 630886916/zg_shuiyin_skill --skill zg_shuiyin_skill -a codex -g -y
```

---

## 二、一句话更新

```bash
npx skills update zg_shuiyin_skill -g
```

- 只检查有没有新版本：`npx skills check`
- 更新全部已装技能：`npx skills update -g`
- 更新是**覆盖式**的：技能文件会被仓库最新版替换，你自己改过的东西会被覆盖。

---

## 三、其它常用指令

| 目的 | 指令 |
|---|---|
| 先看仓库里有什么 | `npx skills add 630886916/zg_shuiyin_skill --list` |
| 看已装技能 | `npx skills list -g` |
| 卸载 | `npx skills remove zg_shuiyin_skill -g` |
| 装到指定 Agent | 加 `-a claude-code` / `-a codex` / `-a cursor`（可重复） |
| 复制而非软链 | 加 `--copy`（Windows 上更稳） |

---

## 四、WorkBuddy 用户看这里（重要）

`npx skills` 的 Agent 列表里**没有 `workbuddy`**（最接近的是 `codebuddy`，
它会装到 `.codebuddy/skills/`），而 WorkBuddy 读的是 `%USERPROFILE%\.workbuddy\skills\`。
所以 WorkBuddy 里"一句话安装"用它 —— **把下面整段发给你自己的 Agent**：

```text
帮我把 zg_shuiyin_skill 技能装好：
1) 执行 npx skills add 630886916/zg_shuiyin_skill --skill zg_shuiyin_skill -g -y
2) 把生成的 skills/zg_shuiyin_skill 整个目录复制到 %USERPROFILE%\.workbuddy\skills\zg_shuiyin_skill
3) 跑一次 python scripts/wm_env_check.py 自检，缺依赖就装：imageio-ffmpeg pillow numpy opencv-python
4) 不要改动我已有的其他技能
```

**或者不用命令行**：下载 [`dist/zg_shuiyin_skill.zip`](dist/zg_shuiyin_skill.zip) → 解压 →
双击 `安装.bat`（会自动复制到 `~/.workbuddy/skills/`、装 Python 依赖、跑环境自检）。

---

## 五、怎么用（对 Agent 说一句话就行）

| 场景 | 你会说的话 |
|---|---|
| 单条视频 | 「给这个视频加水印 `D:\素材\a.mp4`」 |
| 整个文件夹 | 「给这个文件夹下所有视频加水印 `D:\素材\`」 |
| 多素材拼成一条 | 「把这几个素材拼起来加水印」+ 拖入 4 个视频和 1 张图片 |
| 换水印图（仅当次） | 「加水印，这次用 `D:\logo.png` 这张图」 |
| 调大/调小 | 「加水印，水印再大一点（`--ratio 2.5`）」 |

**说「加水印」= 整套默认参数照搬，技能不会再逐项问你。**
只有你明确点名某一项（换图 / 改透明度 / 改大小），才覆盖那一项。

---

## 六、默认参数（用户已定稿，不要每次改）

| 项 | 默认值 |
|---|---|
| 水印图 | 内置 `assets/watermark.png`（中工 LOGO，1882×719，RGBA 透明底） |
| 透明度 | **50%**（在图片自身 alpha 上再乘 0.5） |
| 尺寸 | 水印图最长边 = **画面基准边 ÷ 4**（横屏取宽、竖屏取高） |
| 实际像素 | 720×1280 → **320×122**；1080×1920 → 270×103；1920×1080 → 480×183 |
| 时段 | 全程常驻（第 0 帧到末帧） |
| 运动 | 确定性伪随机轨迹，缓慢连续斜向漂移；同素材永远同一条轨迹 |
| 画质 | libx264 **CRF14** / preset slow / aq-mode 3；**不缩放、不裁剪、不改帧率、不改时长** |
| 音频 | 直通 copy（mp4 不兼容才回退 aac 192k） |
| 输出 | 原片只读 → `水印版/<原名>_水印版.mp4` |
| 质检 | 清晰度比 ≥0.95、水印位置实证、轨迹不越界，逐条出报告 |

### 两条路由（决定画质，不会走错）

| 输入 | 链路 |
|---|---|
| **1 个视频** | 直接加水印，**绝不拼接**（多一次拼接就多一代重编码） |
| **≥2 个素材**（视频/图片任意混） | 理解内容 → 编排 → 拼接成完整视频 → **再**加水印 |

多素材时输出两个文件：`拼接成片_拼接版.mp4`（无水印完整版）+ `水印版/..._水印版.mp4`，
并附 `剪辑方案.md`（顺序、每段时长、转场类型、编排依据）与质检报告。

---

## 七、环境要求

| 项 | 要求 |
|---|---|
| 系统 | Windows（脚本用 Python + ffmpeg，跨平台理论上可用，未在其中系统实测） |
| Python | 3.9+ |
| Python 库 | `imageio-ffmpeg`、`pillow`、`numpy`、`opencv-python`（必需）；`faster-whisper`（可选，仅多素材时辅助理解口播） |
| ffmpeg | **不用单独装**，脚本自动使用 `imageio-ffmpeg` 自带的那份 |
| ffprobe | 只读元数据，PATH 里有即可；没有时会兜底找常见路径 |

装完先自检：

```bash
python scripts/wm_env_check.py
```

---

## 八、仓库结构

```text
zg_shuiyin_skill/
├─ skills/
│  └─ zg_shuiyin_skill/          # ← npx skills 识别的技能本体
│     ├─ SKILL.md                 # 技能指令（Agent 读这个）
│     ├─ assets/watermark.png     # 默认水印图（换图 = 覆盖它）
│     └─ scripts/
│        ├─ wm_config.py          # 参数唯一来源（改默认值只改这里）
│        ├─ wm_core.py            # ffmpeg 发现 / 元数据探测 / 确定性轨迹
│        ├─ wm_render.py          # 单条与批量渲染 + 质检
│        ├─ wm_check.py           # 量化质检（清晰度比 / 位置实证）
│        ├─ wm_understand.py      # 抽关键帧 + 口播转写（多素材理解）
│        ├─ wm_compose.py         # 统一规格 + xfade + acrossfade 拼接
│        ├─ wm_pipeline.py        # 总入口与路由
│        └─ wm_env_check.py       # 环境自检
├─ dist/zg_shuiyin_skill.zip      # 离线安装包（含 GBK 编码的 安装.bat）
├─ 安装.bat                       # Windows 双击安装（复制 + 装依赖 + 自检）
└─ 环境检查.bat                    # 仅自检
```

---

## 九、常见问题

**Q：装完 Agent 还是说「没有这个技能」？**
确认技能目录里有 `SKILL.md`，且路径在 Agent 的 skills 目录下。
WorkBuddy 是 `%USERPROFILE%\.workbuddy\skills\zg_shuiyin_skill\SKILL.md`；
Claude Code 是 `~/.claude/skills/`；Codex 是 `~/.codex/skills/`。装完需要**重启会话**才加载。

**Q：加水印会不会让画质变差？**
叠加水印必须重编码视频流，「不重编码无损」做不到。本技能的做法是：
原始分辨率/帧率/时长/色彩标记全不变 + CRF14 + 音频直通，
并用「清晰度比 ≥0.95」量化验收（实测真实口播素材 0.96，4K 在观看分辨率下 0.99）。

**Q：手机竖拍素材会不会把水印转歪？**
不会。单素材链路保留原 `rotation` 元数据并按方向预旋转水印；
多素材拼接会先按播放器视角转正，再清掉残留的 Display Matrix（流拷贝，零画质损失）。

**Q：能不能去掉别人视频上的水印？**
不能，本技能也没有这个功能。仅用于给**自有或已获授权**的素材打自己的水印。

**Q：`安装.bat` 在 GitHub 上打开是乱码？**
它是 GBK 编码（Windows cmd 需要），不是损坏。下载到本地双击正常。

---

## 十、许可

MIT，见 [LICENSE](LICENSE)。
