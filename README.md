# HT Joyo 2136 Anki

Source-of-truth repository for the **HT Joyo 2136** Anki deck.

## Permanent package name

The downloadable deck is always:

`dist/HT Joyo 2136.apkg`

**Do not add version numbers, suffixes, or alternate APKG names.** The stable filename, deck IDs, model ID, and root deck name are intentional so users can import a newer package as an update instead of chasing renamed releases.

## Deck structure

```text
HT Joyo 2136
├── 01 Sơ cấp 1 — 400
│   ├── 01 Kanji → Hán Việt
│   ├── 02 Hán Việt → Kanji
│   └── 03 Viết Kanji
├── 02 Sơ cấp 2 — 800
│   ├── 01 Kanji → Hán Việt
│   ├── 02 Hán Việt → Kanji
│   └── 03 Viết Kanji
└── 03 All — 2136 từ
    ├── 01 Kanji → Hán Việt
    ├── 02 Hán Việt → Kanji
    └── 03 Viết Kanji
```

- **Sơ cấp 1 — 400:** exact `data/course/sc1.json` order.
- **Sơ cấp 2 — 800:** exact `data/course/sc2.json` order.
- **All — 2136:** full Jōyō master source.
- 3 modes per course: recognition, reverse recall, and handwriting-gated writing.

## Current card behavior

- Hán-Việt reverse/writing fronts always show the Vietnamese meaning, so homophones remain distinguishable.
- Furigana is stored in Anki ruby syntax and rendered with the native `{{furigana:Furigana}}` filter.
- Answer side includes readings, meaning, mnemonic, components, and stroke order.
- The old formation/origin field is removed from the note type and is not rendered.
- KanjiVG stroke data and inline SVG are embedded for offline use; there is no runtime KanjiVG fetch.
- Stroke order auto-animates with per-stroke colors and replay.
- Stable Writer handles pointer capture, lost-pointer recovery, wrong-stroke cleanup, and throttled drawing.
- AnkiMobile writing areas are `tappable`, and a completed writing card uses the native bridge to show the answer automatically.
- Early manual flips keep the real answer locked and let the user continue writing on the back.
- Composite/unresolved IDS components are resolved generically; learner cards do not show broken square/X placeholders.

## Build

Requirements: Python 3.10+ and Node.js.

```bash
bash scripts/build.sh
```

The build verifies exact 400/800 order, card JavaScript syntax, stable deck/model identity, native Furigana rendering, embedded stroke data, component rendering, and note/card counts.

## Repository layout

```text
builder/build_anki.py
data/master/joyo2136_learning_bundle.json
data/course/sc1.json
data/course/sc2.json
data/course/decks.json
vendor/kanjivg-sources.zip
dist/HT Joyo 2136.apkg
scripts/build.sh
scripts/verify_build.py
scripts/make_snapshot.py
.github/workflows/build.yml
```

GitHub Actions rebuilds and verifies the same permanent APKG path after source/builder changes.
