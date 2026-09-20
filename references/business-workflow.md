# 从资源导入到成片交付

本指南把 Skill 的制作规范和现有脚本串成一次完整业务流程，适用于抖音电商独立素材，以及由多段生成组织的 1–2 分钟素材。先按 [README](../README.md) 安装依赖，再准备商品、参考与文案。

制作分析、母版选择、分镜、动态审片和返修决策由 Agent/制作者执行；脚本负责已支持的工作流构建、任务执行、恢复和检查。当前没有一键资源导入界面、全自动长视频依赖调度器或内置剪辑时间线。

## 1. 准备资源与需求

| 你提供什么 | Agent 用来做什么 |
|---|---|
| 商品实图、SKU、包装版本，尽量有正/侧面和手持图 | 确定商品身份、实体结构、尺寸和场景呈现 |
| 参考视频原文件与指定起止区间 | 分析目标创意、动作、说听关系、镜头与节奏 |
| 准确文案，或明确需要创作的卖点简报 | 安排完整表达、角色台词和时间预算 |
| 需要保留/允许修改的项目 | 区分复刻、仅换商品和创意改编 |
| 可选角色/声音资产、已认可版本与反馈 | 复用正确身份与声音，定位返修范围 |
| 时长、画幅、交付形式与使用范围 | 决定生产与验收范围 |

没有参考的原创任务可省略参考片；没有声音参考时说明实际采用的声音方案。需要仅换商品时，人物、声音、动作等保留项必须明确。需求模板见 [production-brief.example.md](../examples/production-brief.example.md)。

## 2. 导入并编目，保留原始资源

使用独立业务工作区。建议结构如下，路径名称可改，`projects/` 下每个可执行项目的脚本结构保持一致：

```text
<业务工作区>/
├── .config/pipeline-config.json
└── campaign-v1/
    ├── brief.md                 # 本次需求与素材用途
    ├── plan.md                  # 资源索引、参考事件、分镜、任务映射、接点与返修
    ├── inputs/
    │   ├── products/            # 商品原图
    │   ├── references/          # 参考视频原文件
    │   ├── characters/          # 可选已认可角色资产
    │   └── audio/               # 可选已获准使用的声音资产
    ├── masters/                # 核对后的角色/商品/场景母版
    ├── projects/
    │   ├── shot-01-v1/          # 可执行项目：storyboard.json、prompts/、workflows/、jobs/、clips/raw/
    │   └── shot-02-v1/          # 依赖前段合格边界时，条件齐备后再建立和提交
    ├── qa/                     # 原帧、接点预览、观察与技术检查
    ├── materials/              # 实际交付视频
    ├── delivery_manifest.json
    └── production_review.json  # 人物任务的审片证据
```

导入可由 Agent 复制本地文件并整理目录；保留原片，派生图和裁切结果另存。对每份资源在 `plan.md` 中记录：资源 ID、本地路径、来源、用途、SHA256、有效区间、原始/派生关系。商品图、动作参考、角色母版、声音和边界帧分别标注用途，避免错用。

若资源来自当前可访问的需求表或网盘，使用已配置工具取得原文件，保留记录身份与来源。飞书读取的接口约定见 [feishu-cli.md](feishu-cli.md)；本包不捆绑这些平台的下载器。缩略图只用于浏览，不能替代原视频或高清商品资产。

以下是手动准备目录的例子，在仓库根目录执行。将路径替换为自己的新工作区；已有项目不重复覆盖配置和需求：

```bash
H3_WORKSPACE="/path/to/new-business-workspace"
H3_CAMPAIGN="$H3_WORKSPACE/campaign-v1"
mkdir -p "$H3_WORKSPACE/.config" "$H3_CAMPAIGN/inputs/products" "$H3_CAMPAIGN/inputs/references" "$H3_CAMPAIGN/inputs/characters" "$H3_CAMPAIGN/inputs/audio" "$H3_CAMPAIGN/masters" "$H3_CAMPAIGN/projects" "$H3_CAMPAIGN/qa" "$H3_CAMPAIGN/materials"
cp examples/pipeline-config.example.json "$H3_WORKSPACE/.config/pipeline-config.json"
cp examples/production-brief.example.md "$H3_CAMPAIGN/brief.md"
cp "/path/to/product-front.png" "$H3_CAMPAIGN/inputs/products/"
cp "/path/to/reference.mp4" "$H3_CAMPAIGN/inputs/references/"
```

按实际资源增减最后两条复制命令，随后填写 `brief.md`。这些命令不生成视频，不调用第三方图片 API。

## 3. 理解需求与参考，先明确要做什么

Agent 读取需求和资源索引，分清用户要求、原片观察事实和本次设计。对目标参考区间进行正常速度观看与试听，在动作、遮挡、说话人变化和切点处补查原帧。

将分析放入同一份 `plan.md`：

- 每份参考的用途和区间；必须保留与允许改变的内容。
- 对白覆盖：谁说哪句、声音来源、说/听/画外音关系，文案一次且完整。
- 视觉事件：准备、触发、路径、接触、缓冲、反应与结果。
- 商品依据：准确 SKU、结构、包装、相对手掌尺度、持续展示区间。

例如“从袋里取出商品再介绍”，要查来源、接触、抓握、离开袋口和展示的完整过程；只看到最后拿着正确商品不足以判断成功。

取帧工具按明确区间运行。下面以参考中第 10–18 秒为例，须替换为本次实际区间：

```bash
python scripts/reference_frames.py --input "$H3_CAMPAIGN/inputs/references/reference.mp4" --start 10 --end 18 --step 0.5 --out "$H3_CAMPAIGN/qa/reference-10-18-v1"
```

输出为带时间记录的帧、联系图和 `frames.json`。它辅助定位静态细节；运动、语气和口型仍需动态检查。详见 [参考还原](reference-fidelity.md)。

## 4. 确定母版、分镜和服务路线

先设计完整动作与交流，再选择能实现它的条件和模板。普通完整动作不按句号拆段；需要手部细节、听者反应或空间转换时，设计有理由的切镜。

三类参考各有职责：原片提供表演和动作依据；固定清晰母版保持人物、商品与材质；最终采用的前段尾帧描述下一段的起始边界。首尾姿态和情绪随剧情变化，人物身份及商品结构保持一致。

每个镜头在计划中对应 `shot_id`、生成项目/段号、参考区间、对白、预期剪辑区间、交付文件和验收重点；连续组补充 `continuity_group`、顺序、前段依赖与 `continuous/cut`。这些是 Agent 的生产记录，脚本不自动解析成依赖队列。

可直接使用 Codex 当前可用的图片生成工具制作商品、人物、场景参考图和分镜图，先检查商品身份、人物、构图与清晰度，再作为视频生成依据。已有合格母版直接复用；图片能力由 Codex 运行环境提供，也可选 [ToAPIs Gemini](image-fallback.md)。视频默认交给本地 H3，整个 Skill 负责组织这条制作工作流。

扫描已有工作流，按 [storyboard 格式](storyboard-schema.md) 编写 `storyboard.json` 与六段式 `prompts/seg_01.txt`。这是 Agent 的制作产物，构建器不会直接把任意需求文档变成分镜。

## 5. 先做代表镜头

选最能暴露本条风险的完整片段：复杂动作看起因到结果，双人对话同时看说话者与听者，长素材至少验证一个关键接点。不要用一张漂亮图片代替动作或连续性试产。

假设 Agent 已在 `projects/shot-01-v1/` 写好一个段号为 1 的项目，并准备好所有引用图片，可执行：

```bash
H3_PROJECT="$H3_CAMPAIGN/projects/shot-01-v1"
python scripts/scan_workflows.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE"
python scripts/build_workflows.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE"
python scripts/submit_jobs.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE" --dry-run
python scripts/runtime_check.py --workspace "$H3_WORKSPACE" --workflow "$H3_PROJECT/workflows/seg_01_api.json"
python scripts/submit_jobs.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE"
python scripts/monitor_jobs.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE" --once
```

先看扫描结果选择模板，再运行构建及后续命令；模型和节点不匹配时先修模板。真正的生成从 `submit_jobs.py` 开始，`--dry-run` 只检查本地输入。监控退出 1 表示仍有任务待完成，可再次查询；退出 2 表示需要处理；退出 0 表示候选已下载。最终候选路径和 SHA 以 `jobs/seg_01_job.json` 的 `outputs` 为准，多输出需逐项查看。

试产通过后按已约定范围扩展。失败先定位母版、动作、实际条件或剪辑问题，再以新项目版本验证，保留其他已认可内容。

## 6. 按依赖扩展分段长视频

**真正依赖前段尾帧的任务，必须等前段的实际采用片段与边界通过后，再构建下一段。** 首帧、尾帧、一般参考图的语义分别校验；内置 I2V 只支持首帧，要求尾帧条件时使用实际支持的自定义图。

1. 确定前段采用的原生输出与最终裁切点，完成动作、对白边界、商品和清晰度检查。
2. 按裁切映射从原生视频提取边界 PNG，记录源视频 SHA、实际帧号、时间及图片 SHA。区间等距抽帧不保证包含最终采用的末帧，需由 Agent 用 ffmpeg 按实际位置单独提取。
3. 检查边界的姿态、持物、尺度、情绪与清晰度；有问题先修前段，不能继续把退化边界传给后段。
4. 为下一段建立 `projects/shot-02-v1/`，将已确认边界绑定到实际首帧输入；固定母版继续作为身份/质量依据，只有图支持时才同时连入。
5. 执行与代表镜头相同的构建、检查、提交和监控步骤，然后在正常速度下检查两段接点；有意切镜则检查同一次动作、空间和声音的承接。

**为什么分开建可执行项目：** 当前构建器要求引用文件在构建时已存在，并且项目一旦有提交记录就禁止原地重建。不要先给所有段填入不存在的未来尾帧，也不要在已提交项目中反复改图。将依赖生成的阶段放入独立项目目录，可保留先前记录并等待真实条件就绪；输入已全部固定、互不依赖的段可在同一项目批量构建。

整条素材的镜头、项目、任务与交付顺序统一维护在根 `plan.md` 中。跨项目依赖、审片和返修范围由 Agent 跟踪；现有脚本不自动释放下游任务，也不自动重新生成所有受影响段。具体规则见 [分段衔接](segment-continuity.md)。

## 7. 审片、精剪与整条检查

先逐段检查，再检查实际交付时间线。按需求使用已有剪辑工具或 ffmpeg 制作精剪片段、接点预览和完整预览，保留源任务与实际采用区间；本包没有自动剪辑器或独立音轨时间线。

重点检查：

- 人物、商品身份和比例：遮挡、转动和切近后仍一致，商品不会越接越小或退回旧包装。
- 动作和情绪：下一段继续已发生的事件，不重复入场/拿取；反应发生在相应信息或接触之后。
- 声音：同一角色的声音来源清楚；跨镜保留对白时，听者不跟读，无漏字、重复、截尾和突兀响度变化。
- 连续性：接点前后正常速度观看约 0.5–1 秒，复杂动作扩大范围；首尾静帧相近仍需检查速度和动作阶段。
- 清晰度：各段首/中/尾的脸、眼睛和商品细节对照固定清晰母版，避免退化逐段累积。
- 编码与完整性：按交付需求统一尺寸、帧率、像素格式、色彩标记、时间基和音频；核对完整时长、解码及首中末内容。

示例命令中的 `clip-01.mp4`、完整预览和审片 JSON 必须已由实际制作产生：

```bash
python scripts/check_media.py --input "$H3_CAMPAIGN/materials/clip-01.mp4" --output "$H3_CAMPAIGN/qa/clip-01-technical-v1.json" --require-audio
python scripts/check_production_review.py --review "$H3_CAMPAIGN/production_review.json" --manifest "$H3_CAMPAIGN/delivery_manifest.json"
```

对每份交付及最终预览分别运行媒体检查，无音频需求时省略 `--require-audio`。人物审片按 [交付约定](delivery-contract.md) 和 [审片结构样例](../examples/production_review.example.json) 整理；样例默认待复核，不能复制成通过结论。证据校验检查完整性与版本身份，不自动评判表演或商品保真。

## 8. 交付、反馈与定向返修

交付约定的独立视频或完整成片、顺序、实际时长、原生规格/后处理说明、任务来源、文件 SHA 与审片状态。一个交付文件使用多个生成任务时记录主要 `prompt_id` 和全部 `source_jobs`、采用区间；不要把生成任务数量当成交付数量。

反馈关联到实际版本与时间点。先定位哪个镜头、哪个边界、哪个引用条件出了问题，再新建受影响项目版本，保留其他已认可镜头。前段重做或改裁切后，重新核对使用旧边界的下游段；有影响的段再修，更新完整预览、交付清单与证据。文件变更后不能沿用旧 SHA 的审片记录。

文件已生成、生产验收通过、业务方认可分别记录。使用外部审片工作台时遵循 [工作台约定](workbench-sync.md)，投放账户与数据回收继续由现有投放工具处理。

## 中断时从哪里继续

| 情况 | 操作 |
|---|---|
| 还在生成 | 对原项目继续运行 `monitor_jobs.py --once`，保留原任务 ID |
| 提交超时、结果未知 | 运行下方 `--recover-unknown` 核对服务端，未找到唯一任务时继续查证 |
| 已生成但下载失败 | 运行下方 `--resume-downloads`，只下载，不重生成 |
| 商品、动作、边界或提示词需要调整 | 新建项目版本，记录改动与受影响接点；不原地修改已提交记录 |
| 只有静态帧、缺动态观看或原声观察 | 保留对应 `needs_review`，补齐真实观察后再声明通过 |

```bash
python scripts/submit_jobs.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE" --recover-unknown
python scripts/monitor_jobs.py --project "$H3_PROJECT" --workspace "$H3_WORKSPACE" --resume-downloads --once
```

以上两个命令分别对应不同故障，按实际状态选择。更多状态含义见 [工作流路由](workflow-routing.md)。
