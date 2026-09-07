"""Descriptive evaluation on supplied MOCK corpus; not a held-out benchmark."""
import collections
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.engine import analyze


def main():
    data = json.loads((ROOT / 'data/dataset.json').read_text(encoding='utf-8'))
    results = []
    full_results = []
    timings = []
    for s in data['sessions']:
        start = time.perf_counter()
        a = analyze(s, 1)
        timings.append((time.perf_counter() - start) * 1000)
        results.append({'id': s['id'], 'label': s['label'], 'prediction': a['intent'], 'correct': s['label'] == a['intent']})
        full = analyze(s, len(s['messages']))
        full_results.append({'id': s['id'], 'label': s['label'], 'prediction': full['intent'], 'correct': s['label'] == full['intent']})
    classes = sorted(set(r['label'] for r in results))
    metrics = []
    for label in classes:
        subset = [r for r in results if r['label'] == label]
        tp = sum(r['correct'] for r in subset)
        predicted = sum(r['prediction'] == label for r in results)
        recall = tp / len(subset)
        precision = tp / predicted if predicted else 0
        metrics.append({'label': label, 'support': len(subset), 'correct': tp, 'recall': recall,
                        'precision': precision, 'f1': 2 * recall * precision / (recall + precision) if recall + precision else 0})
    report = {'method': '首条消息预测；全量同源 MOCK 诊断评估；规则未读取标签，不是独立留出集',
              'samples': len(results), 'accuracy': sum(r['correct'] for r in results) / len(results),
              'macro_f1': sum(m['f1'] for m in metrics) / len(metrics), 'by_class': metrics,
              'initial_baseline_accuracy': 58/138,
              'full_conversation_accuracy': sum(r['correct'] for r in full_results) / len(full_results),
              'abstentions': sum(r['prediction'] == '待确认' for r in results),
              'latency_mean_ms': sum(timings) / len(timings), 'latency_p95_ms': sorted(timings)[int(len(timings) * .95)],
              'errors': [r for r in results if not r['correct']], 'scope': 'rules_baseline_only',
              'limitations': ['官方数据为模板化虚构样本', '无独立测试集', '无情绪和风险金标', '无真实业务 A/B 结果']}
    (ROOT / 'data/evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 规则基线评估报告', '', report['method'], '', f"样本数 {report['samples']}；准确率 {report['accuracy']:.2%}；Macro-F1 {report['macro_f1']:.4f}。",
             f"本机单次评估平均 {report['latency_mean_ms']:.3f} ms，P95 {report['latency_p95_ms']:.3f} ms。此耗时只包含规则函数，不包含网络、UI 或模型。", '',
             '| 场景 | 样本数 | 正确 | 精确率 | 召回率 | F1 |', '|---|---:|---:|---:|---:|---:|']
    lines += [f"| {m['label']} | {m['support']} | {m['correct']} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.3f} |" for m in metrics]
    lines += ['', '## 已知局限', *['- '+s for s in report['limitations']], '',
              f"首版基线准确率 42.03%；同数据诊断改进后 {report['accuracy']:.2%}。该提升属于开发集改进，不是泛化结论。首条消息有 {report['abstentions']} 个待确认；问候或营销消息缺少主诉时应保留弃权。",
              f"补充口径：回放至会话结束，主意图准确率 {report['full_conversation_accuracy']:.2%}。它使用更多消息，不能与首条消息指标直接比较。",
              '主要混淆：一条消息可能同时涉及退款、物流与不良反应；当前有序关键词规则只输出一个主意图。保留多风险提示但不能代替语义理解。', '',
              '## 评估口径',
              '本文件只报告确定性规则基线。Qwen 原始输出与 Hybrid 冻结结果已完成评测，统一口径见 `data/release_summary.json` 和 `docs/ONLINE_EVALUATION.md`。',
              '50 条独立人工编写 Challenge Set 用于边界回归，风险评分同时校验 `risk_type`、`semantic_state` 与证据引用；结果见 `docs/CHALLENGE_EVALUATION.md`。',
              '以上评估均不构成生产泛化或真实业务提升结论。', '', '## 错误明细', '| 会话 | 官方主场景 | 规则预测 |', '|---|---|---|']
    lines += [f"| {r['id']} | {r['label']} | {r['prediction']} |" for r in report['errors']]
    (ROOT / 'docs/EVALUATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('by_class','errors')},ensure_ascii=True))


if __name__ == '__main__':
    main()
