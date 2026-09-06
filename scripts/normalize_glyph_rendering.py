#!/usr/bin/env python3
from pathlib import Path

path = Path('builder/build_anki.py')
text = path.read_text(encoding='utf-8')
changed = False


def once(old, new, label):
    global text, changed
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'{label}: expected one source snippet, found {text.count(old)}')
    text = text.replace(old, new, 1)
    changed = True


if 'def render_inline_glyphs(text, renderer=None):' not in text:
    start = text.index('def render_inline_glyphs(text):')
    end = text.index('\ndef page_deck_id', start)
    helper = r'''def render_inline_glyphs(text, renderer=None):
    """Render supplementary CJK inside prose with the component renderer."""
    if not text:
        return ''
    out = []
    for ch in str(text):
        cp = ord(ch)
        if 0x20000 <= cp <= 0x2FA1F:
            rendered = glyph_html(ch, {'render_type':'unicode', 'render_value':ch}, renderer)
            out.append('<span class="inline-glyph" data-char="' + html.escape(ch, quote=True) + '">' + rendered + '</span>')
        elif ch == '\n':
            out.append('<br>')
        else:
            out.append(h(ch))
    return ''.join(out)

'''
    text = text[:start] + helper + text[end + 1:]
    changed = True

once(
    "CSS += r'''\n.comp-grid{align-items:start}",
    "CSS += r'''\n.inline-glyph{display:inline-flex;width:1.08em;height:1.08em;align-items:center;justify-content:center;vertical-align:-.16em;line-height:1}.inline-glyph svg,.inline-glyph img{display:block;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain}.inline-glyph svg{fill:currentColor}.inline-glyph img{filter:invert(1)}\n.comp-grid{align-items:start}",
    'inline glyph CSS',
)
once('render_inline_glyphs(mnemonic)', 'render_inline_glyphs(mnemonic, glyph_renderer)', 'recursive mnemonic')
once("+ h(root_key) + '</b></span>'", "+ render_inline_glyphs(root_key, glyph_renderer) + '</b></span>'", 'recursive title')
once("+ h(item.get('mnemonic') or '—') + '</div>'", "+ render_inline_glyphs(item.get('mnemonic') or '—', glyph_renderer) + '</div>'", 'component mnemonic')
once(
    "        '三': ('data-component=\"一\"', 'data-component=\"𠄞\"', 'data-recursive-root=\"𠄞\"'),\n",
    "        '三': ('data-component=\"一\"', 'data-component=\"𠄞\"', 'data-recursive-root=\"𠄞\"'),\n        '供': ('data-component=\"亻\"', 'data-component=\"共\"', 'data-recursive-root=\"共\"', 'data-recursive-child=\"卄\"', 'data-recursive-child=\"𬺢\"'),\n",
    '供 decomposition regression',
)
once(
    "    glyph_renderer = GlyphRenderer(hanamin_a, hanamin_b, glyphwiki_manifest)\n    subsets = [('sc1', sc1_rows), ('sc2', sc2_rows), ('all', all_rows)]",
    "    glyph_renderer = GlyphRenderer(hanamin_a, hanamin_b, glyphwiki_manifest)\n    rare_probe = render_inline_glyphs('𬺢', glyph_renderer)\n    if not ('hanamin-glyph' in rare_probe or 'glyphwiki-glyph' in rare_probe):\n        raise RuntimeError('Rare glyph renderer QA failed for U+2CEA2 𬺢')\n    subsets = [('sc1', sc1_rows), ('sc2', sc2_rows), ('all', all_rows)]",
    'U+2CEA2 renderer probe',
)

if changed:
    path.write_text(text, encoding='utf-8')
    print('Applied unified rare-glyph rendering to builder/build_anki.py')
else:
    print('Unified rare-glyph rendering already applied')
