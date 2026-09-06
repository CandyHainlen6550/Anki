# HT Joyo 2136 Anki

Source repository for the **HT Joyo 2136** Anki deck.

## Permanent identity

The generated package is always:

`dist/HT Joyo 2136.apkg`

Do **not** add release/version suffixes to the APKG, root deck, note type, model ID, or deck IDs. Stable identity lets Anki import a rebuilt package as an update.

## Deck structure

```text
HT Joyo 2136
├── 01 Sơ cấp 1 — 400
│   ├── 01 Kanji → Hán Việt → Trang 1 … 9
│   ├── 02 Hán Việt → Kanji → Trang 1 … 9
│   └── 03 Viết Kanji → Trang 1 … 9
├── 02 Sơ cấp 2 — 800
│   ├── 01 Kanji → Hán Việt → Trang 1 … 9
│   ├── 02 Hán Việt → Kanji → Trang 1 … 9
│   └── 03 Viết Kanji → Trang 1 … 9
└── 03 All — 2136 từ
    ├── 01 Kanji → Hán Việt
    ├── 02 Hán Việt → Kanji
    └── 03 Viết Kanji
```

`Sơ cấp 2 — 800` is the historical course label. The canonical HT table has **844 cells**, including **83 boxed component/radical rows**; pages 1–8 contain 100 cells each and page 9 contains 44.

## Refactored learning sources

Anki no longer stores the old ~19 MB `joyo2136_learning_bundle.json` and no longer fetches HT during every build.

```text
data/master/kanji.json          # 2136 canonical kanji/readings/meaning only
data/ht/sc1.json                # clean 400-row HT snapshot; no mnemonic fields
data/ht/sc2.json                # clean 844-row HT snapshot; no mnemonic fields
data/ht/mnemonics.json          # one centralized mnemonic source
data/ht/learner_decomp.json     # one centralized learner decomposition source
data/ht/SOURCE.json             # checksums of the imported HT snapshot
```

Mnemonic and learner decomposition are therefore **single-source**. Course JSON is used only for course order/page/source metadata.

To refresh Anki after HT changes, extract/checkout HT and run:

```bash
python scripts/sync_from_ht.py --ht-root /path/to/HT
```

The sync command rejects HT course files that still contain legacy `mnemonic` keys.

## Current package counts

- Total: **3380 notes / 10140 cards**
- Sơ cấp 1: **400 notes / 1200 cards**
- Sơ cấp 2: **844 notes / 2532 cards**
- All: **2136 notes / 6408 cards**

## Components

The answer side uses `data/ht/learner_decomp.json` for every Jōyō card. Recursive child decomposition is rendered with native `<details>` blocks.

Representative regression locks:

- `京 → 亠 + 口 + 小`
- `愛 → ⺤ + 冖 + 心 + 夂`
- `調 → 言 + 周`, with `周 → 用 + 口`
- `三 → 一 + 𠄞`, with `𠄞 → 一 + 一`
- `飛` remains learner-atomic

Glyph identity is separate from stroke data:

- KanjiVG: writing target/stroke order only
- HanaMin: supplementary Unicode component outlines
- GlyphWiki: exact named non-Unicode component SVGs, fetched at build time and embedded

No learner card performs runtime component-image requests.

## Card behavior

- Card 01: Kanji → Hán Việt
- Card 02: Hán Việt → Kanji; handwriting is optional, and a correct drawing auto-flips
- Card 03: strict write-before-answer gate
- reverse/writing prompts show Vietnamese meaning for disambiguation
- Furigana uses Anki native ruby syntax/filter
- answer side includes readings, meaning, centralized mnemonic, recursive components and embedded stroke order

## Build

Only KanjiVG and HanaMin are pinned external Git sources in `SOURCE_REFS.env`. The HT learning snapshot is committed locally under `data/ht/`.

```bash
python -m pip install -r requirements.txt
bash scripts/build.sh
```

GitHub Actions rebuilds and verifies the permanent package `dist/HT Joyo 2136.apkg`.

## QA gates

A release fails unless all of these pass:

- exact 3380 notes / 10140 cards
- exact Sơ cấp 1 400-row order
- exact Sơ cấp 2 844-row order, 83 boxed rows, 100×8 + 44 layout
- `~阝` and `阝~` remain distinct source identities
- no legacy mnemonic fields in `sc1.json` / `sc2.json`
- every generated note mnemonic equals centralized `mnemonics.json`
- no raw CDP/GT/AJ1/MJ technical entity leaks in learner mnemonic text
- learner-decomposition regression locks pass
- permanent APKG/root/model identity unchanged
- all stroke data embedded offline
- no runtime component URLs or unresolved component-code fallback in final APKG
- JavaScript syntax checks pass
