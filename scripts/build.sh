#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p dist
rm -f dist/*.apkg

# Build directly from the committed renderer; CI must not rewrite builder source.
bash scripts/fetch_sources.sh

SC1=data/ht/sc1.json
SC2=data/ht/sc2.json
KVG=build/sources/kanjivg/kanji
HMA=build/sources/chinese/fonts/HanaMin/HanaMinA.ttf
HMB=build/sources/chinese/fonts/HanaMin/HanaMinB.ttf
GW=build/glyphwiki/manifest.json

python3 builder/build_anki.py \
  --kanji-source data/master/kanji.json \
  --mnemonics-source data/ht/mnemonics.json \
  --decomp-source data/ht/learner_decomp.json \
  --sc1-source "$SC1" \
  --sc2-source "$SC2" \
  --kanjivg-dir "$KVG" \
  --hanamin-a "$HMA" \
  --hanamin-b "$HMB" \
  --glyphwiki-manifest "$GW" \
  --output "dist/HT Joyo 2136.apkg" \
  > dist/builder_report.json

if ! python3 scripts/verify_build.py \
  --apkg "dist/HT Joyo 2136.apkg" \
  --kanji data/master/kanji.json \
  --mnemonics data/ht/mnemonics.json \
  --decomp data/ht/learner_decomp.json \
  --sc1 "$SC1" \
  --sc2 "$SC2" \
  --builder-report dist/builder_report.json \
  --output dist/QA.json; then
  echo 'Build verification failed. QA follows:' >&2
  cat dist/QA.json >&2 || true
  echo 'Builder report follows:' >&2
  cat dist/builder_report.json >&2 || true
  exit 1
fi

python3 scripts/make_snapshot.py \
  --kanji data/master/kanji.json \
  --sc1 "$SC1" \
  --sc2 "$SC2" \
  --output dist/repo_order_snapshot.json

python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
refs={}
for line in Path('SOURCE_REFS.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1); refs[k]=v
local_files=['data/master/kanji.json','data/ht/sc1.json','data/ht/sc2.json','data/ht/mnemonics.json','data/ht/learner_decomp.json','data/ht/SOURCE.json']
manifest={
  'refs':{k:v for k,v in refs.items() if k.endswith('_REF')},
  'checked_out':{
    'KanjiVG':subprocess.check_output(['git','-C','build/sources/kanjivg','rev-parse','HEAD'],text=True).strip(),
    'HanaMin':subprocess.check_output(['git','-C','build/sources/chinese','rev-parse','HEAD'],text=True).strip(),
  },
  'local_sources':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in local_files},
  'glyphwiki':json.loads(Path('build/glyphwiki/manifest.json').read_text()),
}
Path('dist/source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
PY

sha256sum \
  "dist/HT Joyo 2136.apkg" \
  dist/QA.json \
  dist/repo_order_snapshot.json \
  dist/source_manifest.json \
  data/ht/SOURCE.json \
  SOURCE_REFS.env \
  > dist/SHA256SUMS.txt

cat dist/QA.json
