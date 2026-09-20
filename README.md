# H3 Ecommerce Director

面向电商素材生产的 Agent Skill：以本地 MiniMax H3 / ComfyUI 为默认视频后端，围绕真实商品图与参考视频完成需求分析、素材生成、参考复刻、人物与商品一致性检查、返修和独立视频交付。

基于 [TFboy1/oh-my-minimaxh3-director](https://github.com/TFboy1/oh-my-minimaxh3-director)，保留 MIT 许可与上游署名。详细改造范围见 [UPSTREAM.md](UPSTREAM.md)。这是电商派生版，不是 MiniMax 官方项目。

## 当前范围

| 能力 | 发行版状态 |
|---|---|
| 电商需求分析、商品替换、参考还原、人物自然表达、连续分段 | 随包 Skill 与参考规范，由 Agent 执行并记录观察 |
| 本地 ComfyUI 工作流构建、提交、任务恢复、候选视频下载 | 随包 Python 脚本；离线回归测试覆盖 |
| T2V / Ref2VA / 首帧 I2V 模板 | 上游图经去业务化整理；使用前核对本机节点、模型并试产 |
| 第三方图片备用 | ToAPIs Gemini 客户端；可选，需自行配置凭据与素材外发范围 |
| 全片解码、媒体规格、审片证据身份检查 | 随包脚本；不自动判断表演、口型或产品保真 |
| 双 ASR、fast 专用云视频、飞书账号、线上工作台、剪映 | 未随包提供实现/部署；仅保留必要的可选集成边界 |

本地视频推理不等于所有模式离线。使用第三方图片或远程 ComfyUI 时，提示词和相应参考素材会发送至服务方。纯本地路线没有自动云端回退。

## 安装

仓库：[xydzf520/h3-ecommerce-director](https://github.com/xydzf520/h3-ecommerce-director)。获取源码：

```bash
git clone https://github.com/xydzf520/h3-ecommerce-director.git
cd h3-ecommerce-director
```


运行目标为 Linux、Python 3.11+、ffmpeg/ffprobe。ComfyUI、H3 节点和模型需自行安装；本包不含权重。显存和性能由实际模型量化、节点、时长与原生分辨率决定，本版本没有提供跨硬件性能保证。

下载本发行包后，将 `h3-ecommerce-director` 文件夹放入你的 Skill 目录，或让 Agent 从该目录读取 SKILL.md。若已有同名安装，先比较/备份再替换。

在包目录中建立独立 Python 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/runtime_check.py --offline
```

requirements.txt 用于可选图片客户端和联系表工具。ComfyUI 构建/提交/监控只使用标准库，但要求 Linux 文件锁。推理环境可以与此虚拟环境分离。本包不会自动安装插件、开云实例、开隧道或关机。

## 五分钟离线样例

以下命令在本包根目录执行，只构建无品牌陶瓷杯示例的工作流并检查本地输入，不生成视频、不调用第三方 API。

```bash
mkdir -p work/demo/.config
cp examples/pipeline-config.example.json work/demo/.config/pipeline-config.json
cp -r examples/minimal work/demo/cup-v1
python scripts/build_workflows.py --project work/demo/cup-v1 --workspace work/demo
python scripts/submit_jobs.py --project work/demo/cup-v1 --workspace work/demo --dry-run
```

样例默认 T2V、5秒、4步、竖屏；这些是样例参数，不是所有电商任务的质量推荐。真实 SKU 保真任务需要自己的商品参考和匹配工作流。

本机已安装兼容模型/节点，且你准备实际生成时，再执行：

```bash
python scripts/runtime_check.py --workspace work/demo --workflow work/demo/cup-v1/workflows/seg_01_api.json
python scripts/submit_jobs.py --project work/demo/cup-v1 --workspace work/demo
python scripts/monitor_jobs.py --project work/demo/cup-v1 --workspace work/demo --once
```

默认地址是 `http://127.0.0.1:8188`；工作区 `.config/pipeline-config.json` 可修改地址、模板目录与重试参数，不存密钥。`--once` 未完成时退出1，需继续查询；全部下载退出0仍只是候选完成。详细状态、恢复命令与条件支持见 [工作流路由](references/workflow-routing.md)。

## 在 Agent 中使用

> 使用 $h3-ecommerce-director，读取这个项目的商品图、参考片和需求。只替换商品，保留人物、声音和关键动作；先做代表镜头，再交付独立素材与检查清单。

先给需求、产品资产和允许使用的参考范围。明确需要创意改编还是局部保留；不要依赖其他项目的历史偏好。按需读 [制作约定](references/production-contract.md)、[参考还原](references/reference-fidelity.md)、[自然表达](references/natural-expression.md)。

技术上能生成不等于素材合格。`scripts/check_media.py` 检查完整解码；`scripts/check_production_review.py` 校验人物审片证据与当前文件身份。ASR、观看和听感检查须如实记录，缺能力时保留 needs_review。详见 [交付结构](references/delivery-contract.md)。

## 已知限制

- 内置 I2V 只有首帧；需要尾帧时必须提供真实支持该条件的自定义图，构建器会拒绝静默丢弃条件。
- 构建器适配每段一个 H3 生成节点及可解析的图片输入连线，不是任意 ComfyUI 图编辑器。
- POST 超时不自动重发；结果未知须核对服务端队列/历史。历史被服务端清理后可能需要人工查证。
- 默认生成重试为0；下载失败仅重下，保留任务 ID。没有自动预算管理。
- 图片审核拒绝不会自动跨供应商切换；凭据、素材外发与费用由当前使用者配置。
- 本发行整理只做离线验证；未在当前环境重新跑 GPU 成片、付费图片接口或跨平台验证。不要把旧私人环境成功记录当作当前环境的验收。

## 开发与贡献

```bash
PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

CI 配置覆盖 Linux / Python 3.11–3.14，实际远端运行状态以仓库 Actions 为准。问题报告请附脱敏节点/模型版本、命令和错误类别；不要上传密钥、客户媒体、表 token、签名下载链接或真实业务记录。设计层场景见 [evals/evals.json](evals/evals.json)。

## 许可与素材

Skill 文档与脚本沿用 [MIT](LICENSE)。H3 权重、ComfyUI、自定义节点及第三方服务分别遵循自身许可/条款，本仓库不重新授权它们。参考作品、肖像、声音和商标素材的使用权也不由代码许可授予。公开演示只使用合成、自有或获准公开素材。
