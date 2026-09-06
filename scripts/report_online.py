"""Publish a compact, credential-free evaluation report from saved responses."""
import argparse
import collections
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_online import score
from src.model import validate


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main(out):
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    verification = json.loads((out/'verification.json').read_text(encoding='utf-8'))
    rows = read_rows(out/'responses.jsonl')
    assert summary['status'] == 'complete' and verification['verified']
    assert verification['scenarios'] == len(rows) == 276
    reasons = collections.Counter()
    for r in rows:
        if r['raw_response'] is None:
            assert r.get('skipped')
            continue
        ctx = json.loads(r['request']['messages'][1]['content'])
        try:
            value = json.loads(r['raw_response']['choices'][0]['message']['content'])
            validate(value, {m['id'] for m in ctx['messages']}, {m['id'] for m in ctx['messages'] if m['role']=='买家'})
        except ValueError as e:
            reasons[str(e)] += 1
    result = {k: summary[k] for k in ('model', 'fingerprint', 'git_commit', 'pilot_session_ids', 'completed',
                                     'model_responses', 'valid_responses', 'skipped_no_buyer', 'scenarios')}
    result.update(validation_failures=dict(reasons),
                  intent_sources=dict(collections.Counter(r['hybrid_result'].get('intent_source', 'fallback') for r in rows)),
                  limitations=['Same-source development diagnostics; no held-out validation.', 'No gold emotion/risk/semantic evidence labels.'],
                  records=[{k: r[k] for k in ('id','scenario','label','rules','qwen_raw','hybrid','valid')} for r in rows])
    lines = ['# Qwen 接入优化后的全量复测', '',
             f"共138个会话、276个场景。模型：`{summary['model']}`。",
             '先完成固定20个会话/40个场景的小样本验证，再复用已有响应完成全量；模型提示词与决策配置保持固定。',
             '**本结果为已用于诊断优化的同源 MOCK 开发集成绩，不是独立测试集。**', '',
             '| 时点 | 方法 | 样本数 | 意图准确率 | Macro-F1 |', '|---|---|---:|---:|---:|']
    names = {'first_message':'首条消息', 'full_conversation':'完整会话'}
    methods = {'rules':'规则基线（未修改）', 'qwen_raw':'Qwen 原始意图', 'hybrid':'Hybrid 最终结果'}
    for scenario, measures in summary['scenarios'].items():
        for field, m in measures.items():
            lines.append(f"| {names[scenario]} | {methods[field]} | {m['samples']} | {m['accuracy']:.2%} | {m['macro_f1']:.4f} |")
    n = summary['model_responses']
    lines += ['', '准确率与Macro-F1分别呈现；总体准确率提高不代表所有类别都改善。',
              f"实际模型响应 {n} 个，其中 {summary['valid_responses']} 个通过校验（{summary['valid_responses']/n:.2%}）。",
              f"{summary['skipped_no_buyer']} 个场景没有可见买家消息，正常弃权，未发起模型调用；它们仍纳入276个场景的计分分母。",
              '模型原始意图在校验前计分；无买家消息时按待确认处理。Hybrid包含业务依据仲裁和校验失败回退。',
              '校验失败原因：' + json.dumps(dict(reasons), ensure_ascii=False), '',
              '## 小样本与健康门控', '',
              '小样本采用固定每类2个会话，名单记录于评测数据的pilot_session_ids；此次验证记录见低分原因分析。',
              '合成回归测试覆盖未来ID、客服单独引用、空字段、长度边界、标签隔离、健康分流/回复及缓存重新决策。全量记录通过原适配器离线回放，请求、意图、风险、回复和用量一致。',
              '健康风险独立于主意图保留；没有风险金标，因此这些检查证明门控行为，而不证明风险识别准确率。', '',
              '## 历史同模型子集参照', '']
    old_path = ROOT/'deliverables/qwen37-flash-eval-20260906/responses.jsonl'
    if old_path.exists():
        old = read_rows(old_path)
        ids = {r['id'] for r in old}
        current = [r for r in rows if r['id'] in ids]
        result['same_model_subset'] = {}
        lines += ['在相同模型、相同60个会话上比较前后应用版本。该子集也已参与开发诊断，不能称为留出集。', '',
                  '| 时点 | 版本 | Qwen准确率 | Hybrid准确率 |', '|---|---|---:|---:|']
        for scenario in names:
            result['same_model_subset'][scenario] = {}
            for version, cohort in [('before', old), ('after', current)]:
                group = [r for r in cohort if r['scenario']==scenario]
                result['same_model_subset'][scenario][version] = {f: score(group, f) for f in ('qwen_raw','hybrid')}
                values = result['same_model_subset'][scenario][version]
                lines.append(f"| {names[scenario]} | {version} | {values['qwen_raw']['accuracy']:.2%} | {values['hybrid']['accuracy']:.2%} |")
    else:
        lines.append('本地历史响应不在当前检出目录，省略历史子集对照。')
    lines += ['', '## 复现', '',
              '先在进程环境设置 DASHSCOPE_API_KEY；脚本固定使用本次模型。原始响应和attempts仅存本地交付目录，不含请求授权头。', '',
              '```powershell', 'python -m unittest discover -s tests -v',
              'python scripts/evaluate_online.py --pilot', 'python scripts/evaluate_online.py',
              'python scripts/verify_online.py deliverables/qwen-v2-eval-20260906',
              'python scripts/report_online.py deliverables/qwen-v2-eval-20260906', '```', '',
              '首次小样本/全量运行会调用模型；同一输出目录自动跳过已完成场景。生产源码或数据指纹变化时必须使用新的 --output 目录。离线复核与报告生成不调用API。',
              '完整指标及最小逐项预测见 data/online_evaluation_v2.json；低分原因与修改说明见 [ONLINE_EVALUATION_ANALYSIS.md](ONLINE_EVALUATION_ANALYSIS.md)。',
              f"本次生产代码与数据指纹：`{summary['fingerprint']}`。"]
    (ROOT/'docs/ONLINE_EVALUATION.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (ROOT/'data/online_evaluation_v2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'completed': len(rows), 'validation_failures': dict(reasons), 'intent_sources': result['intent_sources']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    main(parser.parse_args().output.resolve())
