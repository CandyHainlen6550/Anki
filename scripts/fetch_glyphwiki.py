#!/usr/bin/env python3
import argparse, hashlib, json, re, time, urllib.error, urllib.request
from pathlib import Path

ENTITY_RE = re.compile(r'^&[^;]+;$')
HEX_RE = re.compile(r'\+([0-9A-Fa-f]{4,6})(?:;|$)')


def collect_targets(master, courses):
    """Collect only component keys the builder can actually render."""
    out=set()
    def add_key(key):
        key=str(key or '')
        if not key:return
        if ENTITY_RE.match(key): out.add(key)
        elif len(key)==1 and ord(key)>=0x20000: out.add(key)
        elif key and key[0] in '⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻':
            for ent in re.findall(r'&[^;]+;',key): out.add(ent)
            # supplementary Unicode leaves inside IDS are also drawable targets
            for ch in key:
                if ord(ch)>=0x20000: out.add(ch)
    # All/2136 uses visual_components_l1.
    for r in master.get('visual_components_l1') or []:
        if str(r.get('learning_visible','')).lower() in ('true','1','yes'):
            add_key(r.get('component_key'))
    # SC1/SC2 use only the explicit top-level component cards. IDS wrappers expose
    # their direct children; ordinary components stay atomic.
    for rows in courses:
        for row in rows:
            for c in row.get('components') or []:
                key=str(c.get('component') or c.get('display') or '')
                is_tree=(c.get('renderType')=='ids_tree' or (key and key[0] in '⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻'))
                children=c.get('children') or []
                if is_tree and children:
                    for child in children:add_key(child.get('component') or child.get('display'))
                else:add_key(key)
    return sorted(out)


def preferred_names(master, courses):
    out={}
    for key,meta in (master.get('components') or {}).items():
        key=str(key); meta=meta or {}
        name=str(meta.get('glyphwiki_name') or '').strip().lower()
        rv=str(meta.get('render_value') or '')
        if not name:
            m=re.search(r'glyphwiki\.org/glyph/([^/?#]+)\.svg',rv,re.I)
            if m:name=m.group(1).lower()
        if name:out[key]=name
    def walk(v):
        if isinstance(v,dict):
            key=str(v.get('component') or v.get('display') or '')
            rv=str(v.get('renderValue') or v.get('render_value') or '')
            m=re.search(r'glyphwiki\.org/glyph/([^/?#]+)\.svg',rv,re.I)
            if key and m:out[key]=m.group(1).lower()
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    for c in courses:walk(c)
    return out

def load_cmap(path):
    if not path:return set()
    from fontTools.ttLib import TTFont
    f=TTFont(path,lazy=True)
    return set((f.getBestCmap() or {}).keys())


def candidates(entity, preferred=None):
    preferred=preferred or {}
    if len(entity)==1:
        return ['u'+format(ord(entity),'x')]
    raw=entity[1:-1]
    vals=[]
    def add(x):
        x=x.strip().lower()
        if x and x not in vals: vals.append(x)
    add(preferred.get(entity,''))
    add(raw)
    # CHISE wrappers are often not part of the GlyphWiki glyph name.
    stripped=re.sub(r'^(?:a-|g2-|o-)+','',raw,flags=re.I)
    add(stripped)
    add(re.sub(r'-i\d+','',stripped,flags=re.I))
    # Unicode-bearing entities can usually fall back to the canonical uXXXXX glyph.
    m=HEX_RE.search(entity)
    if m: add('u'+m.group(1).lower())
    # Common component/database aliases.
    for x in list(vals):
        add(x.replace('+','-'))
        add(re.sub(r'-(?:i\d+)-','-',x,flags=re.I))
    return vals


def fetch(url, attempts=3):
    req=urllib.request.Request(url,headers={'User-Agent':'HT-Joyo-2136-builder/1.0 (+GitHub Actions)'})
    last=None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req,timeout=20) as r:
                body=r.read()
                ctype=(r.headers.get('Content-Type') or '').lower()
                if r.status==200 and b'<svg' in body[:2000].lower() and (b'<path' in body.lower() or b'<polygon' in body.lower()):
                    return body
        except Exception as e:
            last=e
        time.sleep(.5*(i+1))
    return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--master',required=True); ap.add_argument('--sc1',required=True); ap.add_argument('--sc2',required=True)
    ap.add_argument('--output-dir',required=True); ap.add_argument('--base-url',default='https://glyphwiki.org/glyph')
    ap.add_argument('--hanamin-a'); ap.add_argument('--hanamin-b')
    a=ap.parse_args()
    master=json.load(open(a.master,encoding='utf-8'))
    courses=[json.load(open(a.sc1,encoding='utf-8')),json.load(open(a.sc2,encoding='utf-8'))]
    dest=Path(a.output_dir); dest.mkdir(parents=True,exist_ok=True)
    cmap=load_cmap(a.hanamin_a)|load_cmap(a.hanamin_b)
    preferred=preferred_names(master,courses)
    manifest={}
    for entity in collect_targets(master,courses):
        if len(entity)==1 and ord(entity) in cmap:
            manifest[entity]={'status':'hanamin','codepoint':'U+'+format(ord(entity),'04X')}
            continue
        hit=None
        tried=[]
        for name in candidates(entity,preferred):
            url=a.base_url.rstrip('/')+'/'+name+'.svg'; tried.append(url)
            body=fetch(url)
            if body:
                fn=hashlib.sha1(entity.encode()).hexdigest()[:16]+'.svg'
                (dest/fn).write_bytes(body)
                hit={'status':'ok','name':name,'file':fn,'url':url,'sha256':hashlib.sha256(body).hexdigest()}
                break
        manifest[entity]=hit or {'status':'missing','tried':tried}
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    ok=sum(1 for x in manifest.values() if x.get('status')=='ok')
    hmin=sum(1 for x in manifest.values() if x.get('status')=='hanamin')
    miss=[k for k,v in manifest.items() if v.get('status') not in ('ok','hanamin')]
    print(json.dumps({'targets':len(manifest),'hanamin':hmin,'glyphwiki_ok':ok,'glyphwiki_missing':miss},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
