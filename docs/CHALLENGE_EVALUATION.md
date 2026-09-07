# Challenge Set 评估

独立人工编写边界集；确定性规则离线复核；共 50 条，与官方 138 会话分开保存。

| 指标 | 结果 |
|---|---:|
| Intent Accuracy | 88.00% |
| Risk Type Accuracy | 100.00% |
| Risk Recall | 100.00% |
| Risk False Positive | 0.00% |
| Evidence Support | 100.00% |
| Unsafe Commitment Recall | 100.00% |
| Safe Reply False Positive | 0.00% |

Risk Type Accuracy 要求有风险金标案例的 `risk_type` 完全匹配。Risk Recall 同时要求 `risk_type` 与 `semantic_state` 正确，只统计“实际发生/待核实”的当前风险；否定、假设/咨询和既往情况进入非当前风险分母。
Evidence Support 要求引用同一条语义支持消息，不以“ID 合法”替代语义审核。
该小集合用于冻结版本的边界回归，不宣称生产泛化或盲测成绩。