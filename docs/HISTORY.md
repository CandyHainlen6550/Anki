# History

## Current architecture

- Replaced the old ~19 MB `joyo2136_learning_bundle.json` monolith with split canonical sources.
- Centralized mnemonic data in `data/ht/mnemonics.json`.
- Centralized visual learner decomposition in `data/ht/learner_decomp.json`.
- Removed mnemonic duplication from Sơ cấp 1 / Sơ cấp 2 snapshots.
- Removed HT network pin/fetch from normal APKG builds; HT is imported deliberately with `scripts/sync_from_ht.py`.
- Merged Card 02 writer and recursive component rendering into the canonical builder; removed the monkey-patch entry wrapper.
- Preserved permanent Anki deck/model IDs and APKG filename.

## Deck fixes retained

- Exact Sơ cấp 1 / Sơ cấp 2 ordering.
- Embedded KanjiVG stroke SVG/data for offline learning.
- Stable writer pointer capture, lost-pointer recovery and wrong-stroke cleanup.
- Optional Card 02 handwriting and strict Card 03 write gate.
- Vietnamese meaning on reverse/writing prompts.
- Native Anki Furigana rendering.
- Rare Unicode component glyphs via HanaMin and named entities via build-time GlyphWiki SVG.
