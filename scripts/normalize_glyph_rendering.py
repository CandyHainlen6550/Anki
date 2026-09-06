#!/usr/bin/env python3
from pathlib import Path

PATH = Path('builder/build_anki.py')
text = PATH.read_text(encoding='utf-8')
original = text


def replace_once(old, new, label):
    global text
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one old snippet, found {count}')
    text = text.replace(old, new, 1)


# Replace the broken helper. The previous implementation called an undefined
# render_glyph_inline(); all rare glyph rendering now goes through glyph_html()
# and the same GlyphRenderer used by component cards.
if 'def render_inline_glyphs(text, renderer=None):' not in text:
    start = text.index('def render_inline_glyphs(text):')
    end = text.index('\ndef page_deck_id', start)
    helper = '''def render_inline_glyphs(text, renderer=None):
    """Render supplementary CJK in inline prose with the component renderer.

    Ordinary text remains escaped text. Supplementary-plane CJK is converted to
    a HanaMin SVG outline (HanaMin B first) with GlyphWiki as the build-time
    fallback, exactly like component glyph boxes.
    """
    if not text:
        return ''
    out = []
    for ch in str(text):
        cp = ord(ch)
        if 0x20000 <= cp <= 0x2FA1F:
            rendered = glyph_html(ch, {'render_type':'unicode', 'render_value':ch}, renderer)
            out.append('<span class="inline-glyph" data-char="' + html.escape(ch, quote=True) + '">' + rendered + '</span>')
        elif ch == '\\n':
            out.append('<br>')
        else:
            out.append(h(ch))
    return ''.join(out)

'''
    text = text[:start] + helper + text[end + 1:]

replace_once(
    "CSS += r'''\n.comp-grid{align-items:start}",
    "CSS += r'''\n.inline-glyph{display:inline-flex;width:1.05em;height:1.05em;align-items:center;justify-content:center;vertical-align:-.16em;line-height:1}.inline-glyph svg,.inline-glyph img{display:block;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain}.inline-glyph svg{fill:currentColor}.inline-glyph img{filter:invert(1)}\n.comp-grid{align-items:start}",
    'inline glyph CSS',
)

replace_once(
    "render_inline_glyphs(mnemonic)",
    "render_inline_glyphs(mnemonic, glyph_renderer)",
    'recursive mnemonic renderer',
)

replace_once(
    "'Cấu tạo của <b>' + h(root_key) + '</b></span>'",
    "'Cấu tạo của <b>' + render_inline_glyphs(root_key, glyph_renderer) + '</b></span>'",
    'recursive summary renderer',
)

replace_once(
    "+ h(item.get('mnemonic') or '—') + '</div>'",
    "+ render_inline_glyphs(item.get('mnemonic') or '—', glyph_renderer) + '</div>'",
    'top-level component mnemonic renderer',
)

replace_once(
    "        '三': ('data-component=\"一\"', 'data-component=\"𠄞\"', 'data-recursive-root=\"𠄞\"'),\n",
    "        '三': ('data-component=\"一\"', 'data-component=\"𠄞\"', 'data-recursive-root=\"𠄞\"'),\n        '供': ('data-component=\"亻\"', 'data-component=\"共\"', 'data-recursive-root=\"共\"', 'data-recursive-child=\"卄\"', 'data-recursive-child=\"𬺢\"'),\n",
    '供 decomposition regression markers',
)

replace_once(
    "    if ch in regressions:\n        missing = [marker for marker in regressions[ch] if marker not in rendered]\n        if missing:\n            raise RuntimeError(ch + ' learner decomposition QA failed: ' + ', '.join(missing))\n    return rendered\n",
    "    if ch in regressions:\n        missing = [marker for marker in regressions[ch] if marker not in rendered]\n        if missing:\n            raise RuntimeError(ch + ' learner decomposition QA failed: ' + ', '.join(missing))\n    if ch == '供':\n        marker = 'data-recursive-child=\"𬺢\"'\n        start = rendered.find(marker)\n        tail = rendered[start:start + 1800] if start >= 0 else ''\n        if not ('hanamin-glyph' in tail or 'glyphwiki-glyph' in tail):\n            raise RuntimeError('供 → 共 → 𬺢 rare-glyph QA failed: expected HanaMin/GlyphWiki rendering')\n    return rendered\n",
    '供 rendered glyph regression',
)

replace_once(
    "    glyph_renderer = GlyphRenderer(hanamin_a, hanamin_b, glyphwiki_manifest)\n    subsets = [('sc1', sc1_rows), ('sc2', sc2_rows), ('all', all_rows)]\n",
    "    glyph_renderer = GlyphRenderer(hanamin_a, hanamin_b, glyphwiki_manifest)\n    rare_probe = render_inline_glyphs('𬺢', glyph_renderer)\n    if not ('hanamin-glyph' in rare_probe or 'glyphwiki-glyph' in rare_probe):\n        raise RuntimeError('Rare glyph renderer QA failed for U+2CEA2 𬺢')\n    subsets = [('sc1', sc1_rows), ('sc2', sc2_rows), ('all', all_rows)]\n",
    'U+2CEA2 renderer probe',
)

if text != original:
    PATH.write_text(text, encoding='utf-8')
    print('Normalized unified rare-glyph rendering in builder/build_anki.py')
else:
    print('Unified rare-glyph rendering already normalized')
