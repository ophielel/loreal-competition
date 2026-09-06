# 知微 · Beauty Care Copilot

## 目标与验收
基于天池 532503 赛题一，完成千牛式三栏工作台，右侧辅助插件为核心。面向人工客服提供带证据的意图、情绪、风险、服务轨迹、回复草稿与本地任务闭环。
- 导入官方 XLSX 全量数据，保留长订单号字符串与来源行号；原文件不变。
- 回放只读取选定消息及此前内容；工单晚于回放时点则不显示，完成状态无法回溯时明确说明。数据检查发现全部工单晚于聊天结束，另设显式归档快照展示表格最终记录。
- 不把脱敏昵称视为唯一客户身份；跨会话关联只作为候选线索。
- 本地规则可离线运行；可选 Qwen 兼容 API 生成有证据引用的建议，清楚显示降级和错误。模型不直接发送消息、付款或修改外部工单。
- 搜索、风险筛选、会话切换、逐条回放、证据跳转、编辑回复、本地模拟发送、任务确认、导出和统计可操作。
- 生成展示 PPT、实际操作视频、运行指南、Agent 设计、评估报告、源码 ZIP。

## 技术与命令
Python 3.11+ 标准库 HTTP 服务；openpyxl 导入；原生 HTML/CSS/JS；SQLite 本地任务。PPT 用 python-pptx。
运行：python server.py --port 8765
导入：python scripts/import_data.py
测试：python -m unittest discover -s tests -v
评估：python scripts/evaluate.py
产物：python scripts/build_deliverables.py
目录：src/ 核心逻辑，web/ 页面，scripts/ 构建，tests/ 回归，docs/ 设计，data/ 导入数据，deliverables/ 交付。
风格：Python snake_case，JS camelCase；按职责拆分；浏览器数据使用 textContent 或 HTML 转义。

## 实施顺序
1. 数据导入与时间截断、规则推断，单测验证不泄漏未来信息。
2. 本地 API 与人工确认任务，验证错误输入、幂等和持久化。
3. 三栏 UI、回放与看板，真实浏览器验证交互和窄屏。
4. 可选 Qwen API、缓存与来源校验，未配置时不伪称模型结果。
5. 标签仅用于离线评估、不作为推断输入；报告样本数、方法与局限。
6. 截图、实际交互录屏、官方模板 PPT、打包与运行检查。

## 边界
始终：保留原始材料、来源可追溯、真实报告验证结果。
不做：真实千牛连接、外部发送/打款、公开部署、虚构业绩改善、将 MOCK 用于生产。
待填写：队伍名称与成员；真实模型凭据由本机环境变量提供。

## 参考
https://tianchi.aliyun.com/competition/entrance/532503/information
本地官方工作台说明：设计目标为右侧辅助区，不能干扰中部沟通。
