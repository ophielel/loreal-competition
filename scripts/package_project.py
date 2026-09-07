"""Package an explicit source/data allowlist; exclude credentials and local task history."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables'


def main():
    files = [ROOT/n for n in ['README.md','server.py','start.cmd','start.ps1','requirements.txt','package.json','.env.example','.gitignore']]
    for folder, suffixes in [('src',{'.py'}),('tests',{'.py'}),('web',{'.html','.js','.css'}),('docs',{'.md'}),('scripts',{'.py','.cjs','.ps1'})]:
        files += [p for p in (ROOT/folder).glob('*') if p.suffix in suffixes and p.name!='inspect.cjs']
    files += [ROOT/'data'/n for n in ['dataset.json','evaluation.json','online_evaluation_v2.json',
                                      'challenge_set.json','challenge_evaluation.json','release_summary.json']]
    files += [p for p in ROOT.iterdir() if p.suffix in {'.xlsx','.docx','.pptx'}]
    # Screenshots required to reproduce the deck, kept with the original path contract.
    files += [OUT/n for n in ['01-workspace.png','02-replay.png','03-journey.png','05-tasks.png']]
    target=OUT/'知微_项目源码.zip'
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p,Path('zhiwei')/p.relative_to(ROOT))
    with ZipFile(target) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert not any(n.endswith('.sqlite') or '/.git/' in n or '/.tools/' in n or n.endswith('/.env') for n in names)
    manifest=[]
    for name in ['知微_参赛展示.pptx','知微_参赛展示.pdf','知微_实际操作演示.mp4','知微_项目源码.zip']:
        p=OUT/name
        manifest.append({'file':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    (OUT/'交付清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Packaged {len(files)} files; source ZIP integrity OK')


if __name__=='__main__':
    main()
