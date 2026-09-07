# 验证记录

统一发布口径：`data/release_summary.json`（v1.1.0-rc1，2026-09-07）。

## 自动回归

- `python -m unittest discover -s tests -v`：48/48 通过。
- `node scripts/browser_test.cjs`：21/21 项真实 Edge 检查通过，控制台错误 0。
- 浏览器覆盖：服务事项卡、风险证据跳转、时点隔离、归档工单、无依据承诺降级、可编辑安全回复、任务闭环、320～1440 px 无横向溢出。
- Challenge Set：50 条独立人工编写边界案例；Intent 88.00%，Risk Recall 100.00%，Risk False Positive 0.00%，Evidence Support 100.00%，Unsafe Commitment Recall 100.00%，安全回复误拦截 0.00%。

## 数据与模型

- 官方开发诊断数据：138 会话、998 消息、113 订单、80 工单；SHA-256 见 release summary。
- 已保存 276 个真实 Qwen 评测场景，270 个响应通过适配器校验。
- 当前 Rules/Qwen/Hybrid 指标全部由 release summary 给出；Hybrid 使用保存的真实模型输出按当前意图决策离线重放，没有伪称再次在线调用。
- 模型契约测试使用本地构造 HTTP 响应，不消耗在线额度。

## 安全不变量

- 历史回放不展示未来消息、订单发货信息或未来工单。
- 展示的确定性风险必须包含同一次匹配生成的 `evidence_ids`。
- 否定与假设风险不进入“已发生”高风险路径。
- 无可见回执的“已退款/已补发/已完成”、到账保证和具体赔付金额会在模拟发送前降级。
- 所有外部动作仍由人工确认；Demo 未连接真实千牛、支付、退款或物流系统。

## 已知边界

官方数据和 Challenge Set 均为模拟数据；没有真实客服 A/B、生产负载或真实系统执行验证。队伍名称仍为“待填写”，正式提交前必须补齐。