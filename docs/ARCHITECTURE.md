# Architecture

## 1. Canonical learning data

The source model is intentionally split by responsibility.

### `data/master/kanji.json`

Exactly 2,136 Jōyō rows with only canonical card metadata:

- kanji / Unicode
- Hán-Việt
- Vietnamese meaning
- On/Kun readings
- Kun words
- Furigana source

It contains **no mnemonic** and no component tree.

### `data/ht/mnemonics.json`

The single learner-facing mnemonic map. It covers all 2,136 Jōyō characters plus the HT course component/radical cards that need standalone mnemonic text.

### `data/ht/learner_decomp.json`

The single learner-facing visual decomposition graph. Visual decomposition is explicitly separate from etymology/origin analysis.

### `data/ht/sc1.json` / `data/ht/sc2.json`

Course ordering/page snapshots only. Legacy `mnemonic` fields are forbidden at every nesting level. The builder overlays the centralized mnemonic and decomposition sources at build time.

`data/ht/SOURCE.json` records SHA-256 checksums for the imported HT snapshot.

## 2. Refreshing HT data

Use:

```bash
python scripts/sync_from_ht.py --ht-root /path/to/HT
```

The command validates 400/844 row counts, centralized mnemonic coverage, 2,136 decomposition scope and absence of legacy mnemonic keys before copying anything.

The normal APKG build therefore does not need network access to HT and cannot accidentally build against a different HT revision.

## 3. External build inputs

`SOURCE_REFS.env` pins only:

- KanjiVG: stroke-order paths / writer target data
- HanaMin: rare Unicode glyph outlines

GlyphWiki SVGs are fetched only for rare/named component identities reachable from the committed learner decomposition.

## 4. Component rendering

`builder/build_anki.py` consumes the centralized decomposition graph for **all three subsets** (`sc1`, `sc2`, `all`). Existing HT component metadata can preserve position/role when the identity matches, but the component graph and mnemonic always come from the centralized source.

Recursive children are rendered as nested native `<details>` elements. This keeps expansion functional on desktop and AnkiMobile without custom expansion JavaScript.

KanjiVG is never used to guess a component glyph.

## 5. Stable deck identity

- APKG: `HT Joyo 2136.apkg`
- root deck: `HT Joyo 2136`
- model: `HT Joyo 2136`
- model ID: `2084677010`
- deck IDs: existing `2084677xxx` IDs

Normal releases must not rotate these identifiers.

## 6. Note schema

15 fields:

`Kanji, HanViet, Meaning, On, Kun, KunWords, Furigana, Mnemonic, Key, KvgFile, StrokeDataB64, StrokeSVG, Disambiguator, ComponentsHTML, StrokeCount`

Formation/origin is not a note field.

## 7. Reproducibility and QA

The workflow validates source shape before downloading external assets. After build, `scripts/verify_build.py` checks note/card counts, source ordering, centralized mnemonic equality, mnemonic technical-code leakage, learner-decomposition regressions, component glyph embedding, writer JavaScript and stable package identity.
