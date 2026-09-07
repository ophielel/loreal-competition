"""Evaluate the frozen independent challenge set without reading official labels."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.engine import analyze, guard_reply


def ratio(a,b): return a/b if b else 0

RISK_TYPES = {'health', 'complaint'}
RISK_STATES = {'实际发生', '待核实', '否定', '假设/咨询', '既往情况'}


def validate_expected(case):
    """Reject incomplete/unknown risk gold instead of silently scoring by state."""
    expected = case.get('expected')
    if not isinstance(expected, dict) or 'risk_type' not in expected or 'risk_state' not in expected:
        raise ValueError(f"{case.get('id', '?')}: missing risk_type/risk_state")
    risk_type, state = expected['risk_type'], expected['risk_state']
    if (risk_type is None) != (state is None):
        raise ValueError(f"{case.get('id', '?')}: risk_type and risk_state must both be null or non-null")
    if risk_type is not None and (risk_type not in RISK_TYPES or state not in RISK_STATES):
        raise ValueError(f"{case.get('id', '?')}: unknown risk_type/risk_state")
    return expected


def main():
    dataset=json.loads((ROOT/'data/challenge_set.json').read_text(encoding='utf-8'))
    rows=[]
    for case in dataset['cases']:
        session={'id':case['id'],'messages':case['messages'],'orders':[],'tickets':[]}
        actual=analyze(session,len(case['messages']))
        expected=validate_expected(case)
        expected_type, expected_state=expected['risk_type'],expected['risk_state']
        signals=actual['risk_signals']
        matched=next((s for s in signals if s['risk_type']==expected_type and s['semantic_state']==expected_state),None) if expected_type else None
        # “当前风险”只包含实际发生与待核实；风险召回同时要求 type 与 state 正确。
        actionable_expected=expected_state in ('实际发生','待核实')
        actionable_actual=bool(matched) if actionable_expected else any(
            s['semantic_state'] in ('实际发生','待核实') for s in signals)
        checked=guard_reply(expected['candidate_reply'],session)
        actual_types={s['risk_type'] for s in signals}
        risk_type_ok=actual_types == ({expected_type} if expected_type else set())
        evidence_ok=(not expected_type) or bool(matched and matched['evidence_ids']==[case['messages'][0]['id']])
        rows.append({'id':case['id'],'intent_ok':actual['intent']==expected['intent'],
                     'expected_intent':expected['intent'],'actual_intent':actual['intent'],
                     'expected_risk_type':expected_type,'actual_risk_types':sorted(actual_types),
                     'risk_type_ok':risk_type_ok,
                     'actionable_expected':actionable_expected,'actionable_actual':actionable_actual,
                     'negative_risk_case':expected_state in (None,'否定','假设/咨询','既往情况'),
                     'evidence_support':evidence_ok,'unsafe_expected':expected['unsafe_commitment'],
                     'blocked':checked['blocked']})
    positives=[r for r in rows if r['actionable_expected']]
    negatives=[r for r in rows if r['negative_risk_case']]
    risk_cases=[r for r in rows if r['expected_risk_type']]
    unsafe=[r for r in rows if r['unsafe_expected']]
    safe=[r for r in rows if not r['unsafe_expected']]
    report={'dataset':dataset['meta'],'method':'独立人工编写边界集；确定性规则离线复核',
            'metrics':{'intent_accuracy':ratio(sum(r['intent_ok'] for r in rows),len(rows)),
                       'risk_type_accuracy':ratio(sum(r['risk_type_ok'] for r in risk_cases),len(risk_cases)),
                       'risk_recall':ratio(sum(r['actionable_actual'] for r in positives),len(positives)),
                       'risk_false_positive_rate':ratio(sum(r['actionable_actual'] for r in negatives),len(negatives)),
                       'evidence_support_rate':ratio(sum(r['evidence_support'] for r in rows),len(rows)),
                       'unsafe_commitment_recall':ratio(sum(r['blocked'] for r in unsafe),len(unsafe)),
                       'safe_reply_false_positive_rate':ratio(sum(r['blocked'] for r in safe),len(safe))},
            'metric_definitions':{'risk_type_accuracy':'有风险金标案例中 risk_type 完全匹配',
                'risk_recall':'risk_type 与 semantic_state 均匹配的实际发生/待核实当前风险',
                'risk_false_positive_rate':'否定、假设/咨询、既往情况和无风险案例被误升为当前风险',
                'evidence_support_rate':'风险语义状态由同一条人工审核消息支持',
                'unsafe_commitment_recall':'无执行依据承诺被安全门拦截'},
            'counts':{'samples':len(rows),'risk_cases':len(risk_cases),'risk_positives':len(positives),'risk_negatives':len(negatives),
                      'unsafe_replies':len(unsafe),'safe_replies':len(safe)},'errors':[r for r in rows if not (r['intent_ok'] and r['risk_type_ok'] and r['evidence_support'] and r['actionable_actual']==r['actionable_expected'] and r['blocked']==r['unsafe_expected'])]}
    (ROOT/'data/challenge_evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Challenge Set 评估','',f"{report['method']}；共 {len(rows)} 条，与官方 138 会话分开保存。",'',
           '| 指标 | 结果 |','|---|---:|']
    labels={'intent_accuracy':'Intent Accuracy','risk_type_accuracy':'Risk Type Accuracy','risk_recall':'Risk Recall','risk_false_positive_rate':'Risk False Positive','evidence_support_rate':'Evidence Support','unsafe_commitment_recall':'Unsafe Commitment Recall','safe_reply_false_positive_rate':'Safe Reply False Positive'}
    lines += [f"| {labels[k]} | {v:.2%} |" for k,v in report['metrics'].items()]
    lines += ['','Risk Type Accuracy 要求有风险金标案例的 `risk_type` 完全匹配。Risk Recall 同时要求 `risk_type` 与 `semantic_state` 正确，只统计“实际发生/待核实”的当前风险；否定、假设/咨询和既往情况进入非当前风险分母。','Evidence Support 要求引用同一条语义支持消息，不以“ID 合法”替代语义审核。','该小集合用于冻结版本的边界回归，不宣称生产泛化或盲测成绩。']
    (ROOT/'docs/CHALLENGE_EVALUATION.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'metrics':report['metrics'],'errors':len(report['errors'])},ensure_ascii=False))
if __name__=='__main__': main()
