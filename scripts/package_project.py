"""Build a review-ready source package from a strict reproduction allowlist."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables'

ROOT_FILES = ['README.md','server.py','start.cmd','start.ps1','requirements.txt','package.json','.env.example']
DOCS = ['AGENT_DESIGN.md','SPEC.md','SUBMISSION.md','VERIFICATION.md','EVALUATION.md',
        'CHALLENGE_EVALUATION.md','ONLINE_EVALUATION.md','DEMO_SCRIPT.md']
SCRIPTS = ['import_data.py','evaluate.py','evaluate_challenge.py','build_release_summary.py','browser_test.cjs']
TESTS = ['test_engine.py','test_api.py','test_model_contract.py','test_model_store.py','test_taxonomy.py']
DATA = ['dataset.json','evaluation.json','challenge_set.json','challenge_evaluation.json',
        'release_summary.json','qwen_evaluation_summary.json']


def main():
    files = [ROOT/n for n in ROOT_FILES]
    files += [ROOT/'src'/n for n in ('__init__.py','engine.py','model.py','store.py','taxonomy.py')]
    files += [ROOT/'web'/n for n in ('index.html','app.js','style.css')]
    files += [ROOT/'docs'/n for n in DOCS]
    files += [ROOT/'scripts'/n for n in SCRIPTS]
    files += [ROOT/'tests'/n for n in TESTS]
    files += [ROOT/'data'/n for n in DATA]
    files += [ROOT/'赛题 1：数据共情者-业务数据.xlsx', ROOT/'赛题 1：数据共情者-客服工作台示说明.docx']
    missing=[str(p.relative_to(ROOT)) for p in files if not p.exists()]
    if missing: raise FileNotFoundError('Missing package inputs: '+', '.join(missing))
    contents={'purpose':'最小可复现比赛源码包','file_count':len(files),
              'excluded':['开发计划与内部分析','原始模型调试响应','缓存与日志','本地数据库','PPT 生成中间截图','Git 元数据']}
    target=OUT/'知微_项目源码.zip'
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for p in files:
            z.write(p,Path('zhiwei')/p.relative_to(ROOT))
        z.writestr('zhiwei/PACKAGE_CONTENTS.json',json.dumps(contents,ensure_ascii=False,indent=2))
    with ZipFile(target) as z:
        assert z.testzip() is None
        names=z.namelist()
        forbidden=('IMPROVEMENT','online_evaluation_v2','server.log','.sqlite','.git/','__pycache__','recordings/')
        assert not any(any(word in n for word in forbidden) for n in names)
    manifest=[]
    for name in ['知微_参赛展示.pptx','知微_参赛展示.pdf','知微_实际操作演示.mp4','知微_项目源码.zip']:
        p=OUT/name
        manifest.append({'file':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    (OUT/'交付清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Packaged {len(files)} reproduction files; source ZIP integrity OK')

if __name__=='__main__': main()
