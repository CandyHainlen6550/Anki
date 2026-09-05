#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p dist
rm -f dist/*.apkg

bash scripts/fetch_sources.sh

SC1=build/sources/HT/public/data/sc1.json
SC2=build/sources/HT/public/data/sc2.json
KVG=build/sources/kanjivg/kanji
HMA=build/sources/chinese/fonts/HanaMin/HanaMinA.ttf
HMB=build/sources/chinese/fonts/HanaMin/HanaMinB.ttf
GW=build/glyphwiki/manifest.json

python3 builder/build_anki.py \
  --source data/master/joyo2136_learning_bundle.json \
  --sc1-source "$SC1" \
  --sc2-source "$SC2" \
  --kanjivg-dir "$KVG" \
  --hanamin-a "$HMA" \
  --hanamin-b "$HMB" \
  --glyphwiki-manifest "$GW" \
  --output "dist/HT Joyo 2136.apkg" \
  > dist/builder_report.json

python3 scripts/verify_build.py \
  --apkg "dist/HT Joyo 2136.apkg" \
  --sc1 "$SC1" \
  --sc2 "$SC2" \
  --builder-report dist/builder_report.json \
  --output dist/QA.json

python3 scripts/make_snapshot.py \
  --master data/master/joyo2136_learning_bundle.json \
  --sc1 "$SC1" \
  --sc2 "$SC2" \
  --output dist/repo_order_snapshot.json

python3 - <<'PY'
import json, os, subprocess
from pathlib import Path
refs={}
for line in Path('SOURCE_REFS.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1); refs[k]=v
manifest={
  'refs':{k:v for k,v in refs.items() if k.endswith('_REF')},
  'checked_out':{
    'HT':subprocess.check_output(['git','-C','build/sources/HT','rev-parse','HEAD'],text=True).strip(),
    'KanjiVG':subprocess.check_output(['git','-C','build/sources/kanjivg','rev-parse','HEAD'],text=True).strip(),
    'HanaMin':subprocess.check_output(['git','-C','build/sources/chinese','rev-parse','HEAD'],text=True).strip(),
  },
  'glyphwiki':json.loads(Path('build/glyphwiki/manifest.json').read_text()),
}
Path('dist/source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
PY

sha256sum \
  "dist/HT Joyo 2136.apkg" \
  dist/QA.json \
  dist/repo_order_snapshot.json \
  dist/source_manifest.json \
  SOURCE_REFS.env \
  > dist/SHA256SUMS.txt

cat dist/QA.json
