#!/usr/bin/env python3
"""Fetch only rare component glyphs reachable from the centralized learner decomposition."""
import argparse, hashlib, json, re, time, urllib.request
from pathlib import Path

ENTITY_RE = re.compile(r'^&[^;]+;$')
HEX_RE = re.compile(r'\+([0-9A-Fa-f]{4,6})(?:;|$)')
ENTITY_UNICODE_FALLBACK = {
    '&GT-K01085;': '弁',
    '&GT-K02380;': '𬺨',
}

GLYPHWIKI_EXACT_ALIASES = {
    '&GT-K00822;': ['u2ff6-u3405-u2e80-var-001'],
    '&GT-K01085;': ['u2ff1-u53b6-u5927-03'],
    '&GT-K03318;': ['u81fd-02-var-001'],
    '&GT-36228;': ['u4343-02-var-001'],
    '&HD-TK-01032130;': ['u226f3-var-001', 'toki-01032130'],
    '&MJ013489;': ['u66f7-02-var-002', 'jmj-013489'],
}


def used_component_keys(decomp):
    roots = decomp.get('roots') or {}
    children = decomp.get('decomp') or {}
    stack = [str(x) for xs in roots.values() if isinstance(xs, list) for x in xs]
    seen = set()
    while stack:
        key = stack.pop()
        if not key or key in seen:
            continue
        seen.add(key)
        stack.extend(str(x) for x in (children.get(key) or []))
    return seen


def collect_targets(decomp):
    out = []
    for key in used_component_keys(decomp):
        if ENTITY_RE.match(key) or (len(key) == 1 and ord(key) >= 0x20000):
            out.append(key)
    return sorted(out)


def preferred_names(decomp):
    out = {}
    for key, meta in (decomp.get('meta') or {}).items():
        meta = meta or {}
        name = str(meta.get('glyphwikiName') or '').strip().lower()
        rv = str(meta.get('renderValue') or '')
        if not name:
            m = re.search(r'glyphwiki\.org/glyph/([^/?#]+)\.svg', rv, re.I)
            if m:
                name = m.group(1).lower()
        if name:
            out[str(key)] = name
    return out


def load_cmap(path):
    if not path:
        return set()
    from fontTools.ttLib import TTFont
    font = TTFont(path, lazy=True)
    return set((font.getBestCmap() or {}).keys())


def candidates(entity, preferred=None):
    preferred = preferred or {}
    if len(entity) == 1:
        return ['u' + format(ord(entity), 'x')]
    raw = entity[1:-1]
    vals = []
    def add(value):
        value = str(value or '').strip().lower()
        if value and value not in vals:
            vals.append(value)
    add(preferred.get(entity, ''))
    for alias in GLYPHWIKI_EXACT_ALIASES.get(entity, ()):
        add(alias)
    m_mj = re.fullmatch(r'MJ(\d{6})', raw, re.I)
    if m_mj:
        add('jmj-' + m_mj.group(1))
    m_hd = re.fullmatch(r'HD-TK-(\d+)', raw, re.I)
    if m_hd:
        add('toki-' + m_hd.group(1))
    add(raw)
    stripped = re.sub(r'^(?:a-|g2-|o-)+', '', raw, flags=re.I)
    add(stripped)
    add(re.sub(r'-i\d+', '', stripped, flags=re.I))
    m = HEX_RE.search(entity)
    if m:
        add('u' + m.group(1).lower())
    for value in list(vals):
        add(value.replace('+', '-'))
        add(re.sub(r'-(?:i\d+)-', '-', value, flags=re.I))
    return vals


def fetch(url, attempts=3):
    req = urllib.request.Request(url, headers={'User-Agent': 'HT-Joyo-2136-builder/2.0 (+GitHub Actions)'})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                body = response.read()
                if response.status == 200 and b'<svg' in body[:2000].lower() and (b'<path' in body.lower() or b'<polygon' in body.lower()):
                    return body
        except Exception:
            pass
        time.sleep(.5 * (i + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--decomp', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--base-url', default='https://glyphwiki.org/glyph')
    ap.add_argument('--hanamin-a')
    ap.add_argument('--hanamin-b')
    a = ap.parse_args()

    decomp = json.load(open(a.decomp, encoding='utf-8'))
    dest = Path(a.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    cmap = load_cmap(a.hanamin_a) | load_cmap(a.hanamin_b)
    preferred = preferred_names(decomp)
    manifest = {}
    for entity in collect_targets(decomp):
        if len(entity) == 1 and ord(entity) in cmap:
            manifest[entity] = {'status': 'hanamin', 'codepoint': 'U+' + format(ord(entity), '04X')}
            continue
        fallback = ENTITY_UNICODE_FALLBACK.get(entity)
        if fallback and ord(fallback) in cmap:
            manifest[entity] = {'status': 'unicode_fallback', 'char': fallback, 'codepoint': 'U+' + format(ord(fallback), '04X')}
            continue
        hit = None
        tried = []
        for name in candidates(entity, preferred):
            url = a.base_url.rstrip('/') + '/' + name + '.svg'
            tried.append(url)
            body = fetch(url)
            if body:
                fn = hashlib.sha1(entity.encode()).hexdigest()[:16] + '.svg'
                (dest / fn).write_bytes(body)
                hit = {'status':'ok','name':name,'file':fn,'url':url,'sha256':hashlib.sha256(body).hexdigest()}
                break
        manifest[entity] = hit or {'status': 'missing', 'tried': tried}

    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(1 for x in manifest.values() if x.get('status') == 'ok')
    hmin = sum(1 for x in manifest.values() if x.get('status') in ('hanamin', 'unicode_fallback'))
    miss = [k for k, v in manifest.items() if v.get('status') not in ('ok', 'hanamin', 'unicode_fallback')]
    print(json.dumps({'targets':len(manifest),'hanamin':hmin,'glyphwiki_ok':ok,'glyphwiki_missing':miss}, ensure_ascii=False, indent=2))
    if miss:
        raise SystemExit('Glyph coverage incomplete: ' + ', '.join(miss))


if __name__ == '__main__':
    main()
