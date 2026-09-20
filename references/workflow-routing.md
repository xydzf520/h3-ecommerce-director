# 工作流、提交与恢复

## 支持边界

视频默认是本地 ComfyUI HTTP API。用户明确配置远程 ComfyUI 地址时可使用同一协议，但上传图片和请求会离开本机。供应商 fast 云视频 API 不等于 ComfyUI API，本包没有 AutoDL Art 等专用适配器；收到 fast 要求时先确认已安装适配器及授权，不执行历史私人脚本、不自动切云端。

图片层可选 `gemini_image.py`，按 [图片备用](image-fallback.md) 执行。业务规则、服务选择、任务状态和验收记录分开；没有统一预算管理或全自动质量评分器。

## 模板与条件

先运行 `python scripts/scan_workflows.py --project /path/to/project --workspace /path/to/workspace`。扫描项目 workflows/templates、工作区 workflows/pv1min_workflows 及配置的 templates_dir。按能力选择已有图，扫描中的槽位数量只是结构信息，不能证明全部图都受构建器支持。

选择优先级：段内 template > meta.workflow_map[段号] > meta.workflow_map[模式] > 内置模板。模式缺省按 first/last_frame → i2v、refs → ref2va、否则 t2v 推断。UI 格式先用 `convert_ui_workflow.py` 转为 API 格式；不自动修改原图。

| 内置模板 | 图片要求 | 边界 |
|---|---|---|
| t2v | 无 | 上游 Turbo 模板，需匹配本机模型/节点 |
| ref2va | 2 张 refs，可由用户明确提供同图两次 | 不等于首尾帧控制 |
| i2v | 1 张 first_frame | 只有首帧输入；传入 last_frame 必须报错 |

构建器只支持每段一个 H3 生成节点。图片按节点的 first_frame、last_frame、ref_images.ref_image_N 语义字段，沿 image 连线找到独立 LoadImage。复杂批处理/合图路径需先适配为受支持的图；多余参考、缺少条件、共享槽位、未映射 LoadImage 均报错。不会静默重复末图或忽略尾帧。

当前参数范围：时长5–15秒、步数4–40、种子0..2^31-1；24fps。字段变化要与原生模型能力一致，不把构建器范围说成模型全集。现有模板非每个安装环境的已验证生产图；使用 runtime_check 的 workflow 选项查节点/模型后再做代表镜头试产。

## 命令顺序

```bash
python scripts/build_workflows.py --project /path/to/project --workspace /path/to/workspace
python scripts/submit_jobs.py --project /path/to/project --workspace /path/to/workspace --dry-run
python scripts/runtime_check.py --workspace /path/to/workspace --workflow /path/to/project/workflows/seg_01_api.json
python scripts/submit_jobs.py --project /path/to/project --workspace /path/to/workspace
python scripts/monitor_jobs.py --project /path/to/project --workspace /path/to/workspace --once
```

dry-run 只检查本地文件，不探测服务、不上传。构建、提交、监控用项目锁；生成记录已存在后不能原地重建，修改参数/提示词/参考应复制到新版本目录。一次构建先验证全部选定段，再写出；`--segments` 会限定本次 params 的范围，已有提交项目禁止重建。

提交保存实际上传后工作流快照、源工作流指纹、引用 SHA、client_id，再发一次 POST。图片用内容哈希命名，避免同名文件覆盖。默认生成失败不自动重试；监控 `--retry-limit N` 指额外生成次数，0有效，attempt只在实际新提交时增加。鉴权或网络异常可能保守记录为结果未知，需要核对而非盲重发。

## 状态和恢复

- `submitting_unknown`：POST 可能已受理；不得自动重发。
- `submitted`：已有 prompt_id，等待生成；已落盘服务地址随任务保持。
- `generation_failed`：服务端明确生成失败；修正方案通常应新建版本。确需同条件重试时用 submit 的 `--retry-failed`，保留旧尝试记录。
- `validation_failed`：已收到明确拒绝且没有任务 ID；修改图后使用新版本。
- `generated` / `download_failed`：生成完成，下载可重试，保持原 prompt_id。
- `downloaded`：已下载并保存 SHA，production_status 仍为 needs_review。
- `needs_reconciliation`：连续查不到历史与队列中的任务，需核对服务是否重启/清理；不当成生成失败重提。

```bash
python scripts/submit_jobs.py --project /path/to/project --workspace /path/to/workspace --recover-unknown
python scripts/monitor_jobs.py --project /path/to/project --resume-downloads --once
```

recover 只读服务端队列与历史，按保存的 client_id/h3_request_id 找唯一任务，找不到或多匹配均保持待处理。服务端若清理历史，客户端无法凭空判断是否已计费/运行，须由操作者查证后另建版本。resume-downloads 仅重置下载次数，不重新生成。

默认最多120轮监控；未完成退出1，可继续运行。需要处理的状态退出2；全部下载完成退出0，仍不代表生产验收通过。多 MP4 输出全部保存，不擅自只选第一条。脚本不删除队列、不关机、不自动发布。
