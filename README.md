# 知微 · Beauty Care Copilot

天池 532503「赛题一：数据共情者 — 消费者的 AI 管家」本地参赛项目。围绕千牛式客服工作台右侧辅助区，融合聊天、订单、工单，提供可追溯洞察与人工确认的服务流程。

## 立即运行

Windows 双击 **start.cmd**，浏览器打开 http://127.0.0.1:8765 。需要 Python 3.11 或以上；运行 Demo 本身不需要安装第三方包。已附导入好的数据。

也可以在项目目录运行：

```powershell
python server.py --port 8765
```

端口占用时改为 `python server.py --port 8766`，访问对应地址。命令行运行时按 Ctrl+C 关闭。启动脚本使用隐藏后台进程，日志在 data/server.log 和 data/server-error.log。

## 已实现

- 官方 138 会话、998 消息、113 订单、80 工单全量导入，保留来源表和行号，长订单号保持字符串。
- 会话搜索、首条消息风险筛选、逐条回放、三源服务时间线、情绪线索、风险提醒和原文定位。
- **历史回放**只读选定消息及此前信息。全部工单都创建于对应聊天结束之后，所以历史回放不提前展示它们。
- **归档快照**显式展示官方表格最终订单、工单与历史对话，支持事后复盘；不把归档记录伪装成实时信息。
- 回复建议可编辑、可本地模拟发送；跟进任务人工确认后保存到 SQLite，重复创建自动去重，可标记完成。
- 当前快照导出 JSON；统计看板与可重跑的规则评估。
- 可选 Qwen 兼容 API：服务端密钥、最小上下文、JSON 校验、证据 ID 校验、256 条内存缓存、实际 token 与延迟显示、失败显式降级。

## Qwen 配置（可选）

在一个新的 PowerShell 窗口设置实际环境变量后启动服务。`.env.example` 仅为说明，本项目不会自动读取 `.env`。

```powershell
$env:DASHSCOPE_API_KEY = '在本机填写您自己的密钥'
$env:QWEN_MODEL = 'qwen-plus'
$env:QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
python server.py --port 8766
```

打开相应端口，点击右侧底部 **Qwen 分析**。地域/业务空间地址以您的阿里云控制台为准。启动时不自动调用模型；点击才触发请求。不要将密钥写入源码或提交包。

当前交付没有使用真实密钥进行在线模型调用，因此**不宣称 Qwen 已实测通过**。通过适配器本地测试不能代替在线验证。

## 数据与评估

原始 XLSX、DOCX、PPT 模板保留在根目录。全部为官方虚构 MOCK 数据。原图文件未提供，页面仅提示图片缺失，不执行或伪装图像识别。

规则在同源开发数据上诊断改进：首条消息意图准确率 79.0%，完整会话 92.0%；不是独立测试集，不是大模型成绩，也不代表生产环境泛化。首条消息包含问候/营销内容，无主诉时保留待确认。详见 docs/EVALUATION.md。

```powershell
python -m unittest discover -s tests -v
python scripts/evaluate.py
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
- docs/EVALUATION.md、deliverables/browser-checks.json：评估与验证记录。

## 后续待完成事项

队伍名称仍为待填写；真实 Qwen 接口需要本机配置密钥并在线验证；正式提交前需按个人账号页面核对文件大小与格式限制。本项目未报名或向天池提交任何文件，也未连接真实千牛、物流或支付系统。

## 来源

- 官方赛题：https://tianchi.aliyun.com/competition/entrance/532503/information
- 阿里云结构化输出：https://help.aliyun.com/zh/model-studio/qwen-structured-output
- 阿里云模型调用：https://help.aliyun.com/zh/model-studio/model-calling-in-sub-workspace
