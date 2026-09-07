# 知微 · Beauty Care Copilot

天池 532503「赛题一：数据共情者 — 消费者的 AI 管家」本地参赛项目。围绕千牛式客服工作台右侧辅助区，融合聊天、订单、工单，提供可追溯洞察与人工确认的服务流程。

## 立即运行

Windows 双击 **start.cmd**，浏览器打开 http://127.0.0.1:8765 。需要 Python 3.11 或以上；运行 Demo 本身不需要安装第三方包。已附导入好的数据。

也可以直接运行：

```powershell
python server.py --port 8765
```

端口占用时改为 `python server.py --port 8766`，访问对应地址。命令行运行时按 Ctrl+C 关闭。启动脚本使用隐藏后台进程，日志文件不会提交到仓库。

## 已实现

- 官方 138 会话、998 消息、113 订单、80 工单全量导入，保留来源表和行号，长订单号保持字符串。
- 会话搜索、首条消息风险筛选、逐条回放、三源服务时间线、情绪线索、风险提醒和原文定位。
- **历史回放**只读选定消息及此前信息。全部工单都创建于对应聊天结束之后，所以历史回放不提前展示它们。
- **归档快照**显式展示官方表格最终订单、工单与历史对话，支持事后复盘；不把归档记录伪装成实时信息。
- 回复建议可编辑、可本地模拟发送；跟进任务人工确认后保存到 SQLite，重复创建自动去重，可标记完成。
- 当前快照导出 JSON；统计看板与可重跑的规则评估。
- 默认 Qwen + Hybrid：会话与回放先即时呈现安全基线，再由前端按快照自动异步增强，模型等待不阻塞操作；包含最小上下文、JSON 与证据校验、语义风险门控、内存缓存、实际 token 与延迟显示。
- 顶栏提供 Qwen 配置入口。API Key 只保存在服务进程内存，不写入浏览器存储、文件或日志，服务重启后清除。

## Qwen + Hybrid 配置

启动后点击顶栏 **配置 Qwen**，填写 API Key、模型和兼容 API 地址即可启用默认 Hybrid 流程。也可在 PowerShell 中设置环境变量后启动；`.env.example` 仅为说明，项目不会自动读取 `.env`。

```powershell
$env:DASHSCOPE_API_KEY = '在本机填写您自己的密钥'
$env:QWEN_MODEL = 'qwen3.7-flash-2026-07-15'
$env:QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
python server.py --port 8766
```

地域与业务空间地址以阿里云控制台为准。配置完成后，Qwen + Hybrid 仍是正常模式：切换会话或回放点会先显示安全基线，并在后台自动增强；右侧“重新分析”可手动重试。不要将密钥写入源码或提交包。接口不可用或输出不合法时，规则只作为最差兜底，并明确标识“已安全回退”。

## 数据与评估

原始 XLSX、DOCX、PPT 模板保留在开发仓库。全部为官方虚构 MOCK 数据。原图文件未提供，页面仅提示图片缺失，不执行或伪装图像识别。

### 在线实测结果（2026-09-06）

使用 `qwen3.7-flash-2026-07-15` 评测全部 **138 个会话、276 个场景**，覆盖首条消息和完整会话。结果已通过原适配器离线复核。

| 评测时点 | 样本数 | 方法 | 主意图准确率 | Macro-F1 |
|---|---:|---|---:|---:|
| 首条消息 | 138 | 当前规则 | 77.54% | 0.8439 |
| 首条消息 | 138 | Qwen 原始意图 | 73.91% | 0.7955 |
| 首条消息 | 138 | 当前 Hybrid 重放 | 83.33% | 0.8817 |
| 完整会话 | 138 | 当前规则 | 90.58% | 0.9032 |
| 完整会话 | 138 | Qwen 原始意图 | 84.06% | 0.8385 |
| 完整会话 | 138 | 当前 Hybrid 重放 | 92.75% | 0.9202 |

“Qwen 原始意图”来自已保存的 276 次真实调用；当前 Hybrid 指标将这些输出按当前规则与意图决策重新离线重放，未再次发起网络请求。270 个模型响应通过校验，3 个引用无效响应回退规则，另有 3 个无可见买家消息场景弃权。安全语义修复会降低部分同源开发集规则意图分数，但优先消除了否定/假设风险误报。统一口径见 `data/release_summary.json`。

### 评测边界与复现

数据为官方同源 MOCK 开发数据，**不是独立测试集，也不代表生产环境泛化**。另建的 50 条人工审核 Challenge Set 与官方数据分开保存，当前报告针对 Rules + Safety Gate（未调用 Qwen），并同时校验风险 `risk_type`、语义状态与证据引用：Intent 88.00%，Risk Type Accuracy 100.00%、Risk Recall 100.00%、Risk False Positive 0.00%、Evidence Support 100.00%、Unsafe Commitment Recall 100.00%、安全回复误拦截 0.00%。这些是小型边界回归结果，不是生产结论。详见 [Challenge Set 报告](docs/CHALLENGE_EVALUATION.md)。

详见 [在线评测报告](docs/ONLINE_EVALUATION.md) 和用于复核指标的精简记录 `data/qwen_evaluation_summary.json`。原始请求、失败尝试与开发分析不进入比赛提交包。

以下命令重跑规则评估和项目测试，不发起在线模型调用：

```powershell
python -m unittest discover -s tests -v
python scripts/evaluate.py
python scripts/evaluate_challenge.py
python scripts/build_release_summary.py
# 重新导入或生成 PPT 才需要下列依赖
python -m pip install -r requirements.txt
python scripts/import_data.py
python scripts/build_deliverables.py
```

浏览器验证：Node.js 20+，运行 `npm install`、`npx playwright install msedge` 后执行 `npm test`；`npm run record` 录制实际操作（需保持未配置模型密钥的默认演示模式）。测试任务名称以“演示”标注，会在本地任务列表保留。

## 交付文件

- deliverables/知微_参赛展示.pptx：基于官方模板，队伍名称为“待填写”。
- deliverables/知微_参赛展示.pdf：方便预览的导出版本。
- deliverables/知微_实际操作演示.mp4：约 80 秒真实浏览器操作录屏，字幕已压入画面；无配音。
- deliverables/知微_项目源码.zip：可独立解压运行的源码、数据、说明和测试。
- docs/AGENT_DESIGN.md：Agent 工作流、接口与边界。
- docs/DEMO_SCRIPT.md：讲解稿与演示步骤。
- docs/EVALUATION.md、docs/CHALLENGE_EVALUATION.md、deliverables/browser-checks.json：评估与验证记录。
- data/release_summary.json：版本、Rules/Qwen/Hybrid 指标与测试数量的统一来源。

## 冻结状态

当前版本完成最终回归后冻结，不再增加功能。队伍名称仍为待填写；正式提交前仅需按个人账号页面核对文件大小与格式限制。本项目未报名或向天池提交任何文件，也未连接真实千牛、物流或支付系统。

## 来源

- 官方赛题：https://tianchi.aliyun.com/competition/entrance/532503/information
- 阿里云结构化输出：https://help.aliyun.com/zh/model-studio/qwen-structured-output
- 阿里云模型调用：https://help.aliyun.com/zh/model-studio/model-calling-in-sub-workspace
