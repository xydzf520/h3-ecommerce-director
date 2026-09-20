# H3 Ecommerce Director

**由 Codex 驱动的抖音电商素材制作工作流，以 Agent Skill 形式使用。**

导入商品图、参考视频和文案，直接在 Codex 中生成高质量参考图与分镜，再由本地 MiniMax H3 / ComfyUI 生成视频。先做好商品、人物与构图，再衔接分段生成、审片和返修，提升整条素材的质量与一致性。

**状态：已投入实际生产。维护者主观体验：1–2 分钟素材质量很高，整体效果优于 SD 2.5。** 已通过 34 项离线测试及 Linux / Python 3.11–3.14 CI；新环境需先试产代表镜头。

[下载](https://github.com/xydzf520/h3-ecommerce-director/releases/latest) · [完整使用流程](references/business-workflow.md) · [CI](https://github.com/xydzf520/h3-ecommerce-director/actions/workflows/tests.yml)

## 适合什么场景

- **产品展示与口播**：商品特写、开箱、手持讲解、双人互动。
- **参考复刻与商品替换**：按指定区间还原动作和镜头，支持“只换商品”。
- **1–2 分钟投流素材**：分段制作连续剧情或讲解，检查衔接并定向返修。

可优先试用于美妆个护、家居日用、食品饮料、服饰箱包、数码小家电等商品展示与讲解任务。复杂动作先试片，投放效果以实际数据为准。

## 解决什么问题

| 常见问题 | 核心做法 |
|---|---|
| **参考图质量差、分镜与商品表达脱节** | 用 Codex 生成并检查高质量参考图与分镜，从源头控制商品、人物和构图质量 |
| **长素材接不上，越接越糊** | 用前段实际采用的尾帧续接；固定高清人物/商品参考图，逐段检查动作、声音和清晰度；返修后重查相关接点 |
| **商品换样、变大变小、像贴图** | 对照真实 SKU 检查包装、结构、尺度、受光和遮挡，覆盖转动与切镜过程 |
| **复刻丢动作，人物表演僵硬** | 按参考事件设计动作和说听关系，先验证完整互动，再扩展整组素材 |
| **视频生成了，但内容不合格** | 分别检查商品、参考还原、表演、对白、画质和跨段接点；记录问题与实际视频版本，返修后重新验收 |
| **中断重跑、返修版本混乱** | 保存任务与输入记录；未知提交先核对，下载失败只重下；新版本保留来源和审片记录 |

长视频优化主要通过 **制作规范 + 条件检查 + 任务管理** 实现；动态审片、精剪与跨段依赖由 Agent/制作者配合现有工具完成。

## 与原版有什么区别

基于 [TFboy1/oh-my-minimaxh3-director](https://github.com/TFboy1/oh-my-minimaxh3-director)，对比基准与完整归属见 [UPSTREAM.md](UPSTREAM.md)。

| 方面 | 原版 | 本版 |
|---|---|---|
| 定位 | 通用剧本 → 分镜 → 成片 | 抖音电商素材、参考复刻、商品替换 |
| 制作准备 | 剧本分镜、角色四视图参考 | 用 Codex 制作电商所需的商品/人物/场景参考图与分镜，先检查再生成视频 |
| 长素材 | 已有段级生成与镜头衔接 | 细化真实尾帧接续、画质退化、商品/声音一致性及依赖返修 |
| 工程 | 工作流构建、提交与监控基础 | 修正图片条件绑定，增加未知任务核对、下载独立恢复、审片证据校验 |
| **验收** | 以参数校验、生成状态、下载和剪映草稿检查为主 | 增加内容与跨段质量验收，审片证据绑定当前视频、任务和版本，区分候选、生产通过与业务认可 |
| 运行与交付 | Windows / 剪映导向 | Linux 本地生产，默认独立 MP4 与交付清单；可选第三方图片 API |

**验收如何执行：** 脚本检查完整解码、文件身份及审片证据；Agent/制作者实际观看和试听，判断商品、表演、对白与连续性。缺少观察或证据时保持待复核，返修后重新检查，旧版结论不能套给新视频。[验收细则](references/delivery-contract.md)

本地/远程 ComfyUI、三类 H3 模板和流水线基础继承自原版；本版改进制作流程与工具，不修改模型权重。

## 如何运行

### 1. 准备环境

需要 **Linux、Python 3.11+、ffmpeg/ffprobe、Codex 或兼容 Skill 的 Agent**。实际生成还需已安装并运行的 **ComfyUI + H3 节点与模型**。

```bash
git clone https://github.com/xydzf520/h3-ecommerce-director.git
cd h3-ecommerce-director
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/runtime_check.py --offline
```

将仓库放入 Agent 的 Skill 目录，或让 Codex 读取本仓库的 `SKILL.md`。默认 ComfyUI 地址为 `http://127.0.0.1:8188`；工作区配置见 [配置样例](examples/pipeline-config.example.json)。上述命令安装依赖并检查环境，不会启动视频生成。

### 2. 准备资源，交给 Codex

提供 **商品图路径、参考片及区间、文案、保留/可改项、时长与画幅**。可填写 [需求模板](examples/production-brief.example.md)，然后发送：

> 使用 $h3-ecommerce-director，制作抖音投流素材。商品图在【路径】，参考片在【路径】，使用【起止时间】，文案见【文件】。目标约 90 秒、9:16，只换商品，保留人物和关键动作。先用 Codex 制作并检查所需参考图和分镜，再用本地 H3 试产、分段生成；检查接点、商品、声音与清晰度，交付视频和清单。

**流程：资源导入 → 参考分析 → Codex 生图与分镜 → 本地 H3 试产与分段生成 → 审片返修 → 交付。**

资源目录、实际生成命令、连续段组织和中断恢复，按 [完整业务流程](references/business-workflow.md) 执行。

## 当前范围

- **视频**：默认本地生成，单任务 5–15 秒；长素材由多段组织。内置 I2V 仅首帧，需要尾帧约束时使用兼容的自定义工作流。
- **图片与分镜**：使用 Codex 当前可用的图片生成工具制作参考图、分镜图；图片能力由运行环境提供。也可选 ToAPIs Gemini API，需配置凭据，调用时会外发相关素材。[配置说明](references/image-fallback.md)
- **交付**：包含任务脚本和检查工具；自动剪辑器、双 ASR、飞书及工作台后台未随包提供。

更多细节：[分段长视频](references/segment-continuity.md) · [画质保持](references/sharpness-quality.md) · [验收与返修](references/delivery-contract.md)

## 许可

[MIT](LICENSE)，保留 TFboy1 上游署名与 xydzf520 修改署名。模型、第三方服务和输入素材遵循各自许可。本项目为社区派生版。
