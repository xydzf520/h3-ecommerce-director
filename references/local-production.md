# 环境配置

支持目标：Linux、Python 3.11+、ffmpeg/ffprobe，以及用户自行安装的 ComfyUI 与 H3 节点/模型。GPU 显存需求取决于模型量化、工作流与输出规格；本包不以某台机器的成功记录保证其他环境表现。图像备用与联系表依赖 requirements.txt；纯 ComfyUI 提交/监控使用 Python 标准库。使用 fcntl 的锁机制，当前不承诺 Windows 兼容。

在独立项目工作区的 `.config/pipeline-config.json` 配置服务，公开样例见 `examples/pipeline-config.example.json`。配置中的 templates_dir 相对于工作区；项目、模型和资产目录不写死。没有配置时地址为 `http://127.0.0.1:8188`。脚本不会开通云实例、启动隧道、重启服务或下载模型。

- `python scripts/runtime_check.py --offline`：仅检查当前解释器、ffmpeg/ffprobe和可选图片包，不联网。
- `python scripts/runtime_check.py --workspace /path/to/workspace`：只读查询 ComfyUI。
- 构建后加 `--workflow /path/to/project/workflows/seg_01_api.json`：检查节点是否存在及模型/枚举是否匹配。此检查不保证生成质量，也不是所有自定义节点输入语义的完整验证。

模型文件名须与 ComfyUI `/object_info` 返回的可选项一致；模板中的量化版本只是起点。保存修改后的工作流到项目模板目录，不覆盖用户已有已验证版本。Python 环境与 ComfyUI 的推理环境可分开；无需给 ComfyUI 安装本 Skill 的图片 API 客户端依赖。

本包不包含 Whisper/SenseVoice、工作台同步器、第三方云视频适配器、剪映自动化或历史批次脚本。缺少可选工具时注明未执行相应检查，不将其当成已安装依赖。
