# Challenge Set 评估

独立人工编写边界集；确定性规则离线复核
；共 50 条，与官方 138 会话分开保存。

| 指标 | 结果 |
|---|---:|
| Intent Accuracy | 88.00% |
| Risk Recall | 100.00% |
| Risk False Positive | 0.00% |
| Evidence Support | 100.00% |
| Unsafe Commitment Recall | 100.00% |
| Safe Reply False Positive | 0.00% |

Evidence Support 在本集合中要求引用同一条语义支持消息，不以“ID 合法”替代语义审核。
该小集合用于冲刺边界回归，不宣称生产泛化或盲测成绩。