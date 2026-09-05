#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
HT_SHA="$(git ls-remote https://github.com/CandyHainlen6550/HT.git refs/heads/main | awk '{print $1}')"
test -n "$HT_SHA"
python3 - "$HT_SHA" <<'PY'
from pathlib import Path
import re,sys
p=Path('SOURCE_REFS.env')
s=p.read_text(encoding='utf-8')
s,n=re.subn(r'(?m)^HT_REF=.*$',f'HT_REF={sys.argv[1]}',s,count=1)
if n!=1: raise SystemExit('HT_REF line not found in SOURCE_REFS.env')
p.write_text(s,encoding='utf-8')
print('Pinned HT_REF='+sys.argv[1])
PY
