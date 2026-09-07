"""Evaluate the frozen independent challenge set without reading official labels."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.engine import analyze, guard_reply


def ratio(a,b): return a/b if b else 0

def main():
    dataset=json.loads((ROOT/'data/challenge_set.json').read_text(encoding='utf-8'))
    rows=[]
    for case in dataset['cases']:
        session={'id':case['id'],'messages':case['messages'],'orders':[],'tickets':[]}
        actual=analyze(session,len(case['messages']))
        expected=case['expected']; expected_state=expected['risk_state']
        signals=actual['risk_signals']
        matched=next((s for s in signals if s['semantic_state']==expected_state),None) if expected_state else None
        # “当前风险”只包含实际发生与待核实；既往情况单独保留语义，但不计当前高风险。
        actionable_expected=expected_state in ('实际发生','待核实')
        actionable_actual=any(s['semantic_state'] in ('实际发生','待核实') for s in signals)
        checked=guard_reply(expected['candidate_reply'],session)
        evidence_ok=(not expected_state) or bool(matched and matched['evidence_ids']==[case['messages'][0]['id']])
        rows.append({'id':case['id'],'intent_ok':actual['intent']==expected['intent'],
                     'expected_intent':expected['intent'],'actual_intent':actual['intent'],
                     'actionable_expected':actionable_expected,'actionable_actual':actionable_actual,
                     'negative_risk_case':expected_state in (None,'否定','假设/咨询','既往情况'),
                     'evidence_support':evidence_ok,'unsafe_expected':expected['unsafe_commitment'],
                     'blocked':checked['blocked']})
    positives=[r for r in rows if r['actionable_expected']]
    negatives=[r for r in rows if r['negative_risk_case']]
    unsafe=[r for r in rows if r['unsafe_expected']]
    safe=[r for r in rows if not r['unsafe_expected']]
    report={'dataset':dataset['meta'],'method':'独立人工编写边界集；确定性规则离线复核',
            'metrics':{'intent_accuracy':ratio(sum(r['intent_ok'] for r in rows),len(rows)),
                       'risk_recall':ratio(sum(r['actionable_actual'] for r in positives),len(positives)),
                       'risk_false_positive_rate':ratio(sum(r['actionable_actual'] for r in negatives),len(negatives)),
                       'evidence_support_rate':ratio(sum(r['evidence_support'] for r in rows),len(rows)),
                       'unsafe_commitment_recall':ratio(sum(r['blocked'] for r in unsafe),len(unsafe)),
                       'safe_reply_false_positive_rate':ratio(sum(r['blocked'] for r in safe),len(safe))},
            'metric_definitions':{'risk_recall':'仅实际发生/待核实的当前风险',
                'risk_false_positive_rate':'否定、假设/咨询、既往情况和无风险案例被误升为当前风险',
                'evidence_support_rate':'风险语义状态由同一条人工审核消息支持',
                'unsafe_commitment_recall':'无执行依据承诺被安全门拦截'},
            'counts':{'samples':len(rows),'risk_positives':len(positives),'risk_negatives':len(negatives),
                      'unsafe_replies':len(unsafe),'safe_replies':len(safe)},'errors':[r for r in rows if not (r['intent_ok'] and r['evidence_support'] and r['actionable_actual']==r['actionable_expected'] and r['blocked']==r['unsafe_expected'])]}
    (ROOT/'data/challenge_evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Challenge Set 评估','',report['method'],f"；共 {len(rows)} 条，与官方 138 会话分开保存。",'',
           '| 指标 | 结果 |','|---|---:|']
    labels={'intent_accuracy':'Intent Accuracy','risk_recall':'Risk Recall','risk_false_positive_rate':'Risk False Positive','evidence_support_rate':'Evidence Support','unsafe_commitment_recall':'Unsafe Commitment Recall','safe_reply_false_positive_rate':'Safe Reply False Positive'}
    lines += [f"| {labels[k]} | {v:.2%} |" for k,v in report['metrics'].items()]
    lines += ['','Risk Recall 只统计“实际发生/待核实”的当前风险；否定、假设/咨询和既往情况进入非当前风险分母。','Evidence Support 要求引用同一条语义支持消息，不以“ID 合法”替代语义审核。','该小集合用于冲刺边界回归，不宣称生产泛化或盲测成绩。']
    (ROOT/'docs/CHALLENGE_EVALUATION.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'metrics':report['metrics'],'errors':len(report['errors'])},ensure_ascii=False))
if __name__=='__main__': main()
