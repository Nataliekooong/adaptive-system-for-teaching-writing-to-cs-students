# 逐段单次生成（已撤下 v5 独立审核）

默认入口 `feedback.py` 现在调用 `feedback_simple.py`。按用户确认恢复单次生成行为；由于没有 Git 历史，这是功能回退，并非历史源码的逐字还原。

- 完整作文作为上下文，每个自然段生成一句英文反馈，12–40 词（目标约 18–30）。
- 使用用户最新提供的 university writing tutor prompt；写得好时围绕具体优点提出反思问题，不强行要求修改。
- 每批最多 16 个目标，不跨作文；只请求反馈 JSON，不生成诊断、证据摘要或审核记录。
- 没有独立审核，没有质量重写，没有自动 API 重试。
- 本地只做 JSON、ID、词数、句数等基本检查，格式通过不代表内容正确。
- 输出显示 `generated` 和 `format errors`，不再使用 `approved`。

## 当前草稿训练集（产品：点击时送全部已写内容）

产品里用户点 AI feedback 时输入是**当前草稿全文**，不是选中 span。用下面的流水线从自然段做成累计前缀并打标签：

代码在 `source/`，流水线生成的 JSON/JSONL 在 `generated/`。在项目根目录执行：

```bash
.venv/bin/python source/draft_feedback.py prepare-drafts
.venv/bin/python source/draft_feedback.py estimate --model deepseek-v4-pro
.venv/bin/python source/draft_feedback.py generate --model deepseek-v4-pro --limit 40 --budget-usd 2
.venv/bin/python source/draft_feedback.py export-sft
```

`draft_prefixes.jsonl` 里每条是某篇作文写到第 k 段时的全文；标签生成后 `export-sft` 得到干净的 `{assignment, draft, feedback}` 供 SLM 训练。当前只在自然段边界切前缀；句中点击可后续再加句级前缀。

## 使用

在终端设置 `DEEPSEEK_API_KEY`（不自动读取 `.env`）后执行：

```bash
.venv/bin/python source/feedback.py generate --limit 40 --budget-usd 1
```

默认模型是 `deepseek-flash`。对照更强但更贵的 `deepseek-v4-pro` 时必须换新的 `--output`，否则会因 config hash 不同而拒绝写入：

```bash
.venv/bin/python source/feedback.py generate --model deepseek-v4-pro --limit 40 --budget-usd 2 \
  --output generated/paragraph_feedback_pro_sample.jsonl
.venv/bin/python source/feedback.py estimate --model deepseek-v4-pro
```

默认 `--min-target-words 6`：像 `Distracted Driving:` 这类短标题/碎片仍出现在全文上下文里，但不会单独作为反馈 target，避免无意义计费和词数校验失败。需要旧行为时设 `--min-target-words 0`。

默认使用现有 `natural_paragraphs.jsonl`，输出到新文件 `paragraph_feedback_prompt_v2.jsonl`。旧版结果全部保留，不混入新结果。重复运行跳过已生成和已记录格式失败的段落，继续选择新段落。`--limit` 表示本次新选段落数，0 表示全部。

只处理 SEFORA：

```bash
.venv/bin/python source/feedback.py generate --dataset sefora --limit 20 --budget-usd 1
```

日志：`.usage.jsonl` 记录返回 token 用量、峰时费用估值和原始响应，支持中断恢复；`.errors.jsonl` 记录格式失败。格式错误不自动重试，也不会标记为内容审核失败。有未解决的格式错误时退出码为 2。

不再支持 v5 的 `--retry-failed` 和 `--failed-only`。需要主动重做一组数据时请使用新的 `--output` 路径；这会重新计费。网络错误直接停止，手动恢复前核对服务商是否已经计费。

## 费用估算

```bash
.venv/bin/python source/feedback.py estimate
```

报告为 `paragraph_cost_estimate_simple.json`，默认每条反馈含 JSON 估计 60 个输出 token，可用 `--output-tokens` 调整。输入按字符/3.5估计，不计缓存优惠，不含审核或重试。日志金额为 USD，按峰时价格保守估算，不是平台实际扣费；非峰时费率为其一半。

`--budget-usd` 为同一输出文件的累计峰时估值保护阈值。发送前预留输出上限；网络错误未返回用量时无法保证与账单完全一致。

## 数据与备份

保留自然段及全文上下文，不退回逐句，也不按150词切分。PERSUADE 按现有换行恢复段落，缺失的原始排版无法恢复；SEFORA 使用 JSON 段落，不发送教师反馈或成绩。

v5 代码及原 README、测试已备份至 `backups/before_rollback_20261029_184013/`。原 `feedback_pipeline.py` 保留，但默认入口不再调用它。旧输出、审核、费用日志未修改。

## 离线验证

```bash
.venv/bin/python -m unittest discover -s source -p 'test_*.py'
```

测试使用模拟响应，不调用付费 API。

## 字数提示更新

本地硬性词数范围为 12–40 词（prompt 目标约 18–30）。修改 prompt/词数规则后请换新的 `--output`，避免与旧结果和费用日志混用。
