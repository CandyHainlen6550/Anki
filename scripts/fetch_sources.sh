#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source SOURCE_REFS.env

rm -rf build/sources build/glyphwiki
mkdir -p build/sources build/glyphwiki

fetch_sparse() {
  local repo="$1" ref="$2" dest="$3"; shift 3
  git init -q "$dest"
  git -C "$dest" remote add origin "$repo"
  if ! git -C "$dest" -c protocol.version=2 fetch -q --depth=1 --filter=blob:none origin "$ref"; then
    git -C "$dest" fetch -q --depth=1 origin "$ref"
  fi
  git -C "$dest" sparse-checkout init --no-cone >/dev/null
  : > "$dest/.git/info/sparse-checkout"
  for path in "$@"; do printf '/%s\n' "$path" >> "$dest/.git/info/sparse-checkout"; done
  git -C "$dest" checkout -q --detach FETCH_HEAD
}

fetch_sparse "$KANJIVG_REPO" "$KANJIVG_REF" build/sources/kanjivg kanji
fetch_sparse "$HANAMIN_REPO" "$HANAMIN_REF" build/sources/chinese \
  fonts/HanaMin/HanaMinA.ttf fonts/HanaMin/HanaMinB.ttf fonts/HanaMin/LICENSE.txt fonts/HanaMin/README.txt

python3 scripts/fetch_glyphwiki.py \
  --decomp data/ht/learner_decomp.json \
  --output-dir build/glyphwiki \
  --base-url "$GLYPHWIKI_BASE" \
  --hanamin-a build/sources/chinese/fonts/HanaMin/HanaMinA.ttf \
  --hanamin-b build/sources/chinese/fonts/HanaMin/HanaMinB.ttf

printf 'Fetched pinned external sources:\n'
printf '  KanjiVG  %s\n' "$KANJIVG_REF"
printf '  HanaMin  %s\n' "$HANAMIN_REF"
printf 'Using committed HT learning snapshot in data/ht/.\n'
