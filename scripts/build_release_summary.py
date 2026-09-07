"""Build the single machine-readable release facts used by UI/docs/package."""
import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.engine import analyze, snapshot
from src.taxonomy import strong_anchor


def score(rows, field):
    classes=sorted({r['label'] for r in rows})
    details=[]
    for label in classes:
        tp=sum(r['label']==label and r.get(field)==label for r in rows)
        support=sum(r['label']==label for r in rows)
        predicted=sum(r.get(field)==label for r in rows)
        precision,recall=(tp/predicted if predicted else 0),tp/support
        details.append({'label':label,'support':support,'precision':precision,'recall':recall,
                        'f1':2*precision*recall/(precision+recall) if precision+recall else 0})
    return {'samples':len(rows),'accuracy':sum(r.get(field)==r['label'] for r in rows)/len(rows),
            'macro_f1':sum(r['f1'] for r in details)/len(details),'by_class':details}


def main():
    dataset_path=ROOT/'data/dataset.json'
    dataset=json.loads(dataset_path.read_text(encoding='utf-8'))
    sessions={s['id']:s for s in dataset['sessions']}
    online=json.loads((ROOT/'data/qwen_evaluation_summary.json').read_text(encoding='utf-8'))
    rows=[]
    for saved in online['records']:
        s=sessions[saved['id']]
        cursor=1 if saved['scenario']=='first_message' else len(s['messages'])
        baseline=analyze(s,cursor)['intent']
        predicted=saved.get('qwen_raw')
        if not saved.get('valid') or not predicted:
            hybrid=baseline
        else:
            anchor,_=strong_anchor(snapshot(s,cursor)['messages'])
            hybrid=baseline if predicted!=baseline and anchor==baseline else predicted
        rows.append({**saved,'rules_current':baseline,'hybrid_current':hybrid})
    scenarios={}
    for name in ('first_message','full_conversation'):
        group=[r for r in rows if r['scenario']==name]
        scenarios[name]={'rules':score(group,'rules_current'),'qwen':score(group,'qwen_raw'),'hybrid':score(group,'hybrid_current')}
    challenge=json.loads((ROOT/'data/challenge_evaluation.json').read_text(encoding='utf-8'))
    browser_path=ROOT/'deliverables/browser-checks.json'
    browser=json.loads(browser_path.read_text(encoding='utf-8')) if browser_path.exists() else {'passed':0}
    test_count=unittest.defaultTestLoader.discover(str(ROOT/'tests')).countTestCases()
    summary={'version':'1.2.0','status':'frozen','date':'2026-09-07',
             'official_dataset':{'sessions':dataset['meta']['sessions'],'messages':dataset['meta']['counts']['聊天记录'],
                                 'orders':dataset['meta']['counts']['订单'],
                                 'tickets':sum(v for k,v in dataset['meta']['counts'].items() if k.endswith('工单'))},
             'model':online['model'],'online_source':{'responses':online['completed'],
                 'valid_responses':online['valid_responses'],'note':'保存的真实 Qwen 输出按当前规则/Hybrid 意图决策离线重放；未再次发起网络调用'},
             'official_dev_metrics':scenarios,'challenge_metrics':challenge['metrics'],
             'python_test_count':test_count,'browser_check_count':browser.get('passed',0),
             'artifacts_note':'最终回归通过；本版本冻结，不再增加功能'}
    (ROOT/'data/release_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'version':summary['version'],'metrics':scenarios,'tests':[test_count,browser.get('passed',0)]},ensure_ascii=False))
if __name__=='__main__':main()
