# 交付与证据

`examples/delivery_manifest.example.json` 和 `examples/production_review.example.json` 为结构样例，使用明确的无效示例 SHA/任务 ID，默认待复核；不能拿示例宣称通过。

交付清单含 request_id、revision、sequence（同一需求1..N）、file、sha256、prompt_id，另建议记录时长、原生规格、后期处理、SKU、来源与许可、QA路径和人工审片状态。相对文件路径基于清单目录。一个文件含多个任务时，prompt_id 使用可追溯的主要任务 ID，并附 source_jobs 保存所有输入任务与剪辑区间。

人物任务的 production_review 绑定当前清单全部 file/SHA/prompt_id，并包含：参考还原、节奏与连续性、逐角色表演、对白与画质。每项保存观察、实际证据路径/SHA，动态项保存正常播放观察方式、时间范围与预览 SHA。需要整组观察时可创建内部审片预览；不因此改变对外独立交付范围。

```bash
python scripts/check_media.py --input /path/to/project/materials/clip.mp4 --output /path/to/project/qa/technical-v1.json --require-audio
python scripts/check_production_review.py --review /path/to/project/production_review.json --manifest /path/to/project/delivery_manifest.json
```

`check_media` 检查解码、音轨和媒体规格，任何警告保留为待诊断失败；无对白素材可以省略 require-audio。ASR、口型、表演和商品细节不在其自动判断范围。

`check_production_review` 退出0仅表示证据结构完整、版本与当前文件 SHA 一致；退出2表示阻断。它不验证观察陈述真假，也不自动修改业务审片结果。本包没有统一后台交付门禁，Agent 声明人物生产通过前必须实际运行此命令并完成对应观察。纯产品任务按自身产品/动作/技术检查交付，不机械伪造人物记录来满足此脚本。

返修保留旧文件、请求和审片，写入新revision；更新成品时同步更新SHA与证据。候选和已验收素材分开说明。公开演示使用合成或自有/获准素材，客户原片、声音、商标图不随仓库发布。
