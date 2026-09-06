#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

def sha(items):
    return hashlib.sha256(''.join(items).encode()).hexdigest()

p = argparse.ArgumentParser()
p.add_argument('--kanji', required=True)
p.add_argument('--sc1', required=True)
p.add_argument('--sc2', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
master = json.load(open(a.kanji, encoding='utf-8'))['kanji']
sc1 = json.load(open(a.sc1, encoding='utf-8'))
sc2 = json.load(open(a.sc2, encoding='utf-8'))
all_order = [x['kanji'] for x in master]
s1 = [x['kanji'] for x in sc1]
s2 = [x['kanji'] for x in sc2]
out = {'sc1':s1,'sc2':s2,'all':all_order,'sha256':{'sc1':sha(s1),'sc2':sha(s2),'all':sha(all_order)}}
Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
