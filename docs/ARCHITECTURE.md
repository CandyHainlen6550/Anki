# Architecture

## Local canonical input

`data/master/joyo2136_learning_bundle.json` is the 2136-note learning/component master used by the builder.

## Pinned upstream inputs

`SOURCE_REFS.env` pins three Git commits:

- HT: Sơ cấp 1 / Sơ cấp 2 source order.
- KanjiVG: stroke-order paths and stroke labels.
- HanaMin (`googlefonts/chinese`): build-time rare Unicode glyph outlines.

`scripts/fetch_sources.sh` uses partial/sparse Git fetches so upstream files are not duplicated in this repository.

## Component glyph rendering

Component identity and stroke-order data are separate concerns.

- **KanjiVG:** only for writing targets and stroke-order display.
- **HanaMin:** rare Unicode component glyph -> font outline -> inline SVG.
- **GlyphWiki:** named non-Unicode entity -> build-time SVG download -> embedded data URI.

No learner card performs a network request for a component glyph. No unresolved entity is replaced with a visually similar KanjiVG subtree.

This matters for cases such as:

- `卒`: the rare Unicode component `𠦏` remains `𠦏`; HanaMin supplies its outline on platforms whose fonts do not contain it.
- `図`: the entity `&GT-K00822;` remains that exact entity; GlyphWiki supplies its glyph rather than substituting `⺍ + 乂` from stroke structure.

## Deck identity

The permanent identity is intentionally stable:

- APKG: `HT Joyo 2136.apkg`
- root deck: `HT Joyo 2136`
- model: `HT Joyo 2136`
- model ID: `2084677010`
- deck IDs: `2084677xxx`

Do not rotate these for normal releases.

## Note fields

The current schema has 15 fields:

`Kanji, HanViet, Meaning, On, Kun, KunWords, Furigana, Mnemonic, Key, KvgFile, StrokeDataB64, StrokeSVG, Disambiguator, ComponentsHTML, StrokeCount`

There is no Formation/Origin field.

## Writer

The writing card embeds canonical KanjiVG target paths and validates the next expected stroke. Correct strokes snap to canonical colored paths. Incorrect strokes flash red and disappear. Pointer capture/lost-pointer recovery handles iPad WebView interruptions. Completing the final stroke sets the answer gate and calls the platform answer bridge.
