# 可选图片服务：ToAPIs Gemini

此适配器只处理图片，不替代本地 H3 视频。默认模型为 `gemini-3-pro-image-preview`，默认 API 基址 `https://toapis.cn`，也保留 `https://toapis.com` 客户端支持。第三方代理与模型官方服务不是同一服务；调用前确认所选供应商、素材外发范围及预算。当前版本保留已有接口协议，未重新做付费在线兼容性测试，实际使用前核对 [供应商文档](https://docs.toapis.com/docs/cn/api-reference/images/gemini-3-pro-image/generation)。

凭据读取 `TOAPIS_API_KEY`，其次为 `~/.config/toapis/api-key`（仅当前用户可读写）。不要把 key 写入 Skill、工作区配置、命令行参数、日志或示例。图片参考会上传至第三方，提示词也会发送；没有当前任务的服务/上传授权时保持本地路线。

## 错误与状态

- 明确技术错误可在已选择的备用服务内切换一次；原服务有任务 ID 时先查明终态。收到任务 ID 后不得因为超时再创建同一任务。
- 审核拒绝由脚本阻断，先复核实际内容并说明可行修改，不能自动换供应商规避限制。
- 鉴权、余额、参数、未知错误由脚本阻断；缺图先查状态。画面质量失败走返修流程，不当成接口故障。
- 同一 job 目录仅允许一次 submit；`submitting_unknown` 没有 ID 时保留记录并联系供应商查证，不删目录重提。
- `--direct` 仅用于当前用户独立要求的 Gemini 任务。已有审核拒绝的逻辑请求不能改用此开关隐藏失败来源。

```bash
python scripts/gemini_image.py submit --job-dir /path/to/project/image-jobs/master-v1 --prompt-file /path/to/prompt.txt --failure-json /path/to/redacted-error.json --ref /path/to/product.png --size 9:16 --resolution 2K
python scripts/gemini_image.py poll --job-dir /path/to/project/image-jobs/master-v1
```

无参考则省略 ref；独立任务用 `--direct` 代替 `--failure-json`。prompt 上限1000字符、参考上限6张及1K/2K/4K为当前客户端约束，超限在上传前报错，不静默截断。poll 一次查询一次，按供应商限流要求间隔执行；本包没有后台监听器或自动计费预算系统。

任务记录保留 provider/model、base、原失败类别、输入 SHA、task_id、输出路径/SHA。生成成功只得到 technical_status，visual_status 保持 pending_review。下载不发送 API Authorization，检查图片可解码后仍须人工/Agent 核对人物、商品、文字、手部及清晰度。
