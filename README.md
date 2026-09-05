# HT Joyo 2136 Anki

Source repository for the **HT Joyo 2136** Anki deck.

## Permanent package identity

The deck file is always:

`dist/HT Joyo 2136.apkg`

Do **not** add version numbers or suffixes to the APKG, root deck, or note type. Stable deck/model IDs are intentional so users can import a newer package as an update.

## Deck structure

```text
HT Joyo 2136
├── 01 Sơ cấp 1 — 400
│   ├── 01 Kanji → Hán Việt
│   │   └── Trang 1 … Trang 9
│   ├── 02 Hán Việt → Kanji
│   │   └── Trang 1 … Trang 9
│   └── 03 Viết Kanji
│       └── Trang 1 … Trang 9
├── 02 Sơ cấp 2 — 800
│   ├── 01 Kanji → Hán Việt
│   │   └── Trang 1 … Trang 9
│   ├── 02 Hán Việt → Kanji
│   │   └── Trang 1 … Trang 9
│   └── 03 Viết Kanji
│       └── Trang 1 … Trang 9
└── 03 All — 2136 từ
    ├── 01 Kanji → Hán Việt
    ├── 02 Hán Việt → Kanji
    └── 03 Viết Kanji
```

`Sơ cấp 2 — 800` is the historical course label. The verified Đông Du HT800_1 → HT800_9 source table contains **844 cells**, including **83 boxed component/radical cells**. Pages 1–8 contain 100 cells each and page 9 contains 44.

Sơ cấp 1 and Sơ cấp 2 are fetched from the pinned `CandyHainlen6550/HT` revision and keep exact repo order. They are not slices of the 2136 master list. Repeated glyphs are not deduplicated; `~阝` and `阝~` retain distinct source identities.

## Current package counts

- Total: **3380 notes / 10140 cards**.
- Sơ cấp 1: **400 notes / 1200 cards**.
- Sơ cấp 2: **844 notes / 2532 cards**.
- All: **2136 notes / 6408 cards**.

## Component glyph strategy

KanjiVG is **stroke-order data only**. It is never used to guess/substitute an unresolved component glyph.

At build time:

1. Normal Unicode components use ordinary text rendering.
2. Rare/supplementary Unicode components are outlined from **HanaMinA/HanaMinB** and embedded as inline SVG.
3. Named non-Unicode entities are fetched from **GlyphWiki** at build time and embedded into the APKG as SVG data URIs.
4. QA rejects learner-facing entity-code fallbacks and runtime component-image URLs.

## Card behavior

- Hán-Việt reverse/writing fronts always show Vietnamese meaning.
- Furigana uses Anki ruby syntax and native `{{furigana:Furigana}}` rendering.
- Formation/Origin is not a note field.
- Answer side includes readings, meaning, mnemonic, components, and stroke order.
- KanjiVG stroke paths are embedded; there is no runtime KanjiVG fetch.
- Colored stroke-order animation + replay.
- Stable Writer includes pointer capture, lost-pointer recovery, wrong-stroke cleanup, and requestAnimationFrame rendering.
- AnkiMobile writer is `tappable`; completing the final correct stroke invokes the native answer bridge.
- Early manual flip keeps the real answer locked until writing is complete.

## Build

Pinned upstream revisions are in `SOURCE_REFS.env`.

After updating the HT source repo, pin its new `main` commit once:

```bash
bash scripts/pin_ht_main.sh
```

Then build:

```bash
python -m pip install -r requirements.txt
bash scripts/build.sh
```

The permanent output name remains exactly `dist/HT Joyo 2136.apkg`.

## QA gates

A release fails unless all of these pass:

- 3380 notes / 10140 cards.
- Sơ cấp 1 exact 400-row source order.
- Sơ cấp 2 exact 844-row canonical source order.
- Sơ cấp 2 exactly 83 component/boxed rows.
- Sơ cấp 2 page layout: 100 × 8 + 44.
- `~阝` and `阝~` source markers remain distinct.
- permanent APKG/root/model name has no version suffix.
- Formation field absent and native Anki Furigana filter present.
- writing auto-flip/flip-lock JavaScript passes syntax checks.
- all stroke data embedded offline.
- KanjiVG is not used for unresolved component glyphs.
- no runtime component-image URLs or unresolved code/box placeholders survive learner-facing HTML.
