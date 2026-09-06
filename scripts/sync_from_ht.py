#!/usr/bin/env python3
"""Import the clean HT learning snapshot into Anki without duplicating mnemonic data in course rows."""
import argparse, hashlib, json, shutil
from pathlib import Path

FILES = {
    'sc1.json': 'public/data/sc1.json',
    'sc2.json': 'public/data/sc2.json',
    'mnemonics.json': 'public/data/mnemonics.json',
    'learner_decomp.json': 'public/data/learner_decomp.json',
}

def mnemonic_paths(value, path=''):
    found=[]
    if isinstance(value,dict):
        for key,child in value.items():
            cp=path+'/'+str(key)
            if str(key).lower()=='mnemonic': found.append(cp)
            found.extend(mnemonic_paths(child,cp))
    elif isinstance(value,list):
        for i,child in enumerate(value): found.extend(mnemonic_paths(child,path+'/'+str(i)))
    return found

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ht-root',required=True,help='Extracted HT repository root')
    ap.add_argument('--dest',default='data/ht')
    a=ap.parse_args()
    src=Path(a.ht_root); dest=Path(a.dest); dest.mkdir(parents=True,exist_ok=True)
    loaded={}
    for name,rel in FILES.items():
        p=src/rel
        if not p.is_file(): raise SystemExit(f'Missing HT source: {p}')
        loaded[name]=json.load(open(p,encoding='utf-8'))
    if len(loaded['sc1.json'])!=400: raise SystemExit('HT sc1 must contain 400 rows')
    if len(loaded['sc2.json'])!=844: raise SystemExit('HT sc2 must contain 844 rows')
    for name in ('sc1.json','sc2.json'):
        stale=mnemonic_paths(loaded[name])
        if stale: raise SystemExit(f'{name} still contains legacy mnemonic fields: {stale[:5]}')
    mn=loaded['mnemonics.json']; decomp=loaded['learner_decomp.json']
    if int(decomp.get('joyoCount') or 0)!=2136: raise SystemExit('learner_decomp joyoCount must be 2136')
    course_chars=[r['kanji'] for name in ('sc1.json','sc2.json') for r in loaded[name]]
    missing=[ch for ch in course_chars if not str(mn.get(ch,'')).strip()]
    if missing: raise SystemExit('Missing course mnemonic: '+', '.join(missing[:20]))
    for name,rel in FILES.items(): shutil.copy2(src/rel,dest/name)
    manifest={'source':'HT clean snapshot','files':{}}
    for name in FILES:
        p=dest/name
        manifest['files'][name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    (dest/'SOURCE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'ok':True,'sc1':400,'sc2':844,'mnemonics':len(mn),'decomposableRoots':len(decomp.get('roots') or {})},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
