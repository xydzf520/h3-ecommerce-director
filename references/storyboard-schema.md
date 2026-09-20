# Storyboard 与项目文件

每个需求版本一个项目目录，至少包含 storyboard.json 和 prompts/seg_XX.txt。`examples/minimal` 是合成陶瓷杯的无图 T2V 示例；不包含客户素材。

```json
{
  "meta": {
    "request_id": "demo-cup",
    "revision": "v1",
    "prompt_mode": "official",
    "strict_prompt_validation": true,
    "aspect": "9:16 (Portrait Widescreen)",
    "default_steps": 4,
    "default_seed": 42
  },
  "segments": [{"id": 1, "duration": 5, "mode": "t2v"}]
}
```

段号为唯一正整数。可选字段：prompt_file、template、refs（数组）、first_frame、last_frame、steps、seed、aspect、megapixels、scheduler、sampler。路径相对项目；模板也可从配置 templates_dir 查找。`meta.workflow_map` 可按模式或段号指定图。实际支持的图片条件见 [路由](workflow-routing.md)。参数只适用于对应节点；检查实际图，不把字段存在当作控制生效。

plan.md 维护来源区间、商品 SKU、制作模式、角色母版、对白覆盖、视觉事件、镜头时间线、任务对应关系和返修版本。脚本的 segment 是生成任务，不等同交付文件；必要时剪辑多任务形成一个连续镜头，也可以从原片裁出获准独立素材。最终映射写 delivery_manifest，不能按任务数凑交付数。

六段式提示词字段：subject_definitions、summary、retention_analysis、detailed_description、overall_soundscape、non_diegetic_music。时间线使用 [Shot N] 和实际时间码；对白集中使用 `<d>[Chinese] ...</d>`，没有对白时明确无对白。角色、动作、声音都来自本次计划，不复制示例商品或台词到真实任务。

构建器保留上游 official/wenwu/hybrid 的兼容校验；本发行版建议 official。其他模式的详细导演教程在上游仓库，未随包维护，不把兼容解析视为全部模式均完成实测。平均镜长和标准差只作为描述值，不能代替剪辑判断。
