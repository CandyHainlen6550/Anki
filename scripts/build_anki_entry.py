#!/usr/bin/env python3
"""Configure learner-facing Anki behavior, then run the canonical builder.

- Card 02 (Hán Việt → Kanji): drawing is optional. A correct drawing auto-flips,
  but the normal Anki Show Answer action always remains available.
- Card 03 keeps its existing strict write-before-answer gate.
- HT repo component children are preserved to depth 2 and rendered as native
  expandable <details> blocks so they work without JavaScript on desktop,
  AnkiMobile/iPhone and iPad WebKit.
"""
from pathlib import Path
import html
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import builder.build_anki as core


# ---------------------------------------------------------------------------
# Card 02: optional handwriting. Card 03 remains the strict writer.
# ---------------------------------------------------------------------------
core.Q_HV2K = r'''<div class="ht-card tappable" id="ht-write-root" data-side="front" data-kanji="{{Kanji}}" data-key="hv2k:{{Key}}" data-strokes="{{StrokeDataB64}}"><div class="eyebrow">Hán Việt → Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="writer-wrap"><div class="writer-box tappable" id="ht-writer-box"></div><div class="writer-tools"><button type="button" id="ht-reset">Viết lại</button><button type="button" id="ht-hint">Gợi ý nét</button></div><div id="ht-writer-status" class="writer-status"></div></div><div class="small">Vẽ đúng sẽ tự lật thẻ. Nếu chưa vẽ được, bạn vẫn có thể lật thủ công để xem đáp án.</div></div>''' + core.WRITER_JS
core.A_HV2K = core.COMMON_BACK


# ---------------------------------------------------------------------------
# Depth-2 recursive component rendering.
#
# The canonical HT JSON already contains direct children, e.g.
# 係 -> 亻 + 系 and 系 -> 丿 + 糸. The old Anki builder enriched the first level
# but discarded children for ordinary Unicode components. Keep the existing
# first-level extraction rules, then attach the exact direct children supplied
# by HT. No deeper inference/decomposition is performed here.
# ---------------------------------------------------------------------------
_BASE_REPO_COMPONENT_ENTRIES = core.repo_component_entries


def _component_key(node):
    return str((node or {}).get('component') or (node or {}).get('display') or '')


def _is_ids_wrapper(node):
    key = _component_key(node)
    return bool((node or {}).get('renderType') == 'ids_tree' or (key and key[0] in core.IDS_ARITY))


def _child_entry(child, master_components):
    key = _component_key(child)
    meta = dict(master_components.get(key, {}) or {})
    meta.update(core.MANUAL_COMP.get(key, {}) or {})
    render_type = child.get('renderType') or child.get('render_type') or meta.get('render_type') or ''
    render_value = child.get('renderValue') or child.get('render_value') or meta.get('render_value') or ''
    meta['render_type'] = render_type
    meta['render_value'] = render_value
    position = child.get('position') or ''
    return {
        'key': key,
        'han_viet': child.get('hanViet') or child.get('han_viet') or meta.get('han_viet') or '',
        'meaning': child.get('meaning') or child.get('meaning_vi') or meta.get('meaning_vi') or '',
        'mnemonic': child.get('mnemonic') or child.get('mnemonic_vi') or meta.get('mnemonic_vi') or '',
        # HT's recursive dialog shows the child's own position (not parent → child).
        'position': position,
        'position_vi': child.get('positionVi') or core.POS_VI.get(position, str(position or '')),
        'role': child.get('role') or '',
        'meta': meta,
    }


def _direct_children_for_item(row, item, master_components):
    """Return only direct HT children for this first-level component."""
    for source in row.get('_repo_components') or []:
        if _is_ids_wrapper(source):
            # IDS wrappers are structural syntax; preserve the canonical builder's
            # existing flattening and do not invent a second recursive layer.
            continue
        if _component_key(source) != item.get('key'):
            continue
        children = source.get('children') or []
        if children:
            return [_child_entry(child, master_components) for child in children if _component_key(child)]
    return []


def _recursive_child_html(child, glyph_renderer):
    title = core.cap_hv(child['han_viet']) if child.get('han_viet') else '—'
    position = child.get('position_vi') or core.POS_VI.get(child.get('position', ''), str(child.get('position') or ''))
    role = child.get('role') or ''
    attr_key = html.escape(str(child.get('key') or ''), quote=True)
    role_html = ''
    if role:
        role_html = '<small class="comp-recursive-role">' + core.h(core.ROLE_VI.get(role, str(role))) + '</small>'
    return (
        '<article class="comp-recursive-child" data-recursive-child="' + attr_key + '">'
        '<div class="comp-glyph">' + core.glyph_html(child['key'], child['meta'], glyph_renderer) + '</div>'
        '<div class="comp-recursive-copy">'
        '<strong>' + core.h(title) + '</strong>'
        '<span>' + core.h(child.get('meaning') or '—') + '</span>'
        '<small>' + core.h(position or 'thành phần') + '</small>'
        + role_html +
        '</div></article>'
    )


def _recursive_block_html(parent, children, glyph_renderer):
    root_key = str(parent.get('key') or '')
    attr_root = html.escape(root_key, quote=True)
    child_html = ''.join(_recursive_child_html(child, glyph_renderer) for child in children)
    return (
        '<details class="comp-recursive" data-recursive-depth="2" data-recursive-root="' + attr_root + '">'
        '<summary class="comp-recursive-summary">'
        '<span class="comp-recursive-summary-title">Cấu tạo của <b>' + core.h(root_key) + '</b></span>'
        '<span class="comp-recursive-summary-side"><span>' + str(len(children)) + ' phần</span><span class="comp-recursive-chevron" aria-hidden="true">⌄</span></span>'
        '</summary>'
        '<div class="comp-recursive-body"><div class="comp-recursive-grid">' + child_html + '</div></div>'
        '</details>'
    )


def _repo_components_html_recursive(row, master_components, kvg_dir=None, glyph_renderer=None):
    items = _BASE_REPO_COMPONENT_ENTRIES(row, master_components, kvg_dir)
    if not items:
        return '<div class="comp-empty">Không tách thành phần ở mức học hiện tại.</div>'

    cards = []
    expected_recursive = 0
    for item in items:
        title = core.cap_hv(item['han_viet']) if item.get('han_viet') else '—'
        position = item.get('position_vi') or core.POS_VI.get(item.get('position', ''), str(item.get('position') or ''))
        role = core.ROLE_VI.get(item.get('role'), str(item.get('role') or 'thành phần hình thể'))
        children = _direct_children_for_item(row, item, master_components)
        recursive = ''
        if children:
            expected_recursive += 1
            recursive = _recursive_block_html(item, children, glyph_renderer)

        cards.append(
            '<div class="comp-card">'
            '<div class="comp-head"><div class="comp-glyph">' + core.glyph_html(item['key'], item['meta'], glyph_renderer) + '</div>'
            '<div><div class="comp-name">' + core.h(title) + '</div><div class="comp-meta">' + core.h(position) + '</div><div class="comp-role">' + core.h(role) + '</div></div></div>'
            '<div class="comp-box"><span class="mini-label">Nghĩa</span><br>' + core.h(item.get('meaning') or '—') + '</div>'
            '<div class="comp-box mn"><span class="mini-label">Mẹo nhớ</span><br>' + core.h(item.get('mnemonic') or '—') + '</div>'
            + recursive +
            '</div>'
        )

    rendered = ''.join(cards)

    # Build-time regression guards. Any HT component with direct children must
    # survive as one depth-2 expandable block. 係 is a concrete canonical test:
    # 系 must expand to 丿 + 糸.
    if expected_recursive and rendered.count('data-recursive-depth="2"') != expected_recursive:
        raise RuntimeError('Recursive component rendering lost one or more HT depth-2 branches.')
    if row.get('kanji') == '係':
        source_has_system_children = any(
            _component_key(c) == '系' and len(c.get('children') or []) >= 2
            for c in (row.get('_repo_components') or [])
        )
        if source_has_system_children:
            required = (
                'data-recursive-root="系"',
                'data-recursive-child="丿"',
                'data-recursive-child="糸"',
            )
            missing = [marker for marker in required if marker not in rendered]
            if missing:
                raise RuntimeError('係 recursive QA failed: missing ' + ', '.join(missing))

    return rendered


core.repo_components_html = _repo_components_html_recursive


# Native <details>/<summary> is deliberately used instead of custom JavaScript:
# it expands downward naturally, remains keyboard accessible on desktop, and is
# handled natively by the WebKit used by AnkiMobile on iPhone/iPad.
core.CSS += r'''
.comp-grid{align-items:start}
.comp-recursive{width:100%;box-sizing:border-box;margin-top:12px;border:1px solid #31516b;border-radius:14px;overflow:hidden;background:#0b1c2d;color:#dbeaf7}
.comp-recursive-summary{box-sizing:border-box;min-height:48px;padding:10px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;list-style:none;font-weight:800;line-height:1.35;-webkit-tap-highlight-color:transparent;touch-action:manipulation;user-select:none;-webkit-user-select:none}
.comp-recursive-summary::-webkit-details-marker{display:none}.comp-recursive-summary::marker{content:''}
.comp-recursive-summary-title{min-width:0;overflow-wrap:anywhere}.comp-recursive-summary-title b{font-family:"Noto Serif JP","Yu Mincho",serif;color:#13c8ff;font-size:1.12em}
.comp-recursive-summary-side{display:flex;align-items:center;gap:8px;flex:0 0 auto;color:#8fa9bd;font-size:12px;white-space:nowrap}
.comp-recursive-chevron{display:inline-block;font-size:20px;line-height:1;transition:transform .18s ease;transform-origin:center}
.comp-recursive[open]>.comp-recursive-summary .comp-recursive-chevron{transform:rotate(180deg)}
.comp-recursive-body{box-sizing:border-box;padding:12px;border-top:1px solid #294158;background:#081727}
.comp-recursive-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;width:100%}
.comp-recursive-child{box-sizing:border-box;min-width:0;display:grid;grid-template-columns:58px minmax(0,1fr);gap:10px;align-items:center;padding:10px;background:#102338;border:1px solid #294962;border-radius:12px;text-align:left}
.comp-recursive-child .comp-glyph{width:58px;height:58px;flex-basis:58px;font-size:40px;border-radius:11px}.comp-recursive-child .comp-glyph img,.comp-recursive-child .comp-glyph svg{max-width:100%;max-height:100%}
.comp-recursive-copy{min-width:0}.comp-recursive-copy strong,.comp-recursive-copy span,.comp-recursive-copy small{display:block;min-width:0;overflow-wrap:anywhere;word-break:break-word}.comp-recursive-copy strong{font-size:18px;line-height:1.25;color:#eef7ff}.comp-recursive-copy span{margin-top:3px;font-size:14px;line-height:1.4;color:#c4d4e2}.comp-recursive-copy small{margin-top:4px;font-size:12px;line-height:1.35;color:#13c8ff}.comp-recursive-role{color:#8fa9bd!important}
@media(max-width:680px){.comp-recursive{margin-top:10px}.comp-recursive-summary{min-height:50px;padding:11px 12px}.comp-recursive-summary-side>span:first-child{display:none}.comp-recursive-body{padding:10px}.comp-recursive-grid{grid-template-columns:1fr}.comp-recursive-child{grid-template-columns:52px minmax(0,1fr);padding:9px}.comp-recursive-child .comp-glyph{width:52px;height:52px;flex-basis:52px;font-size:36px}}
@media(min-width:681px) and (max-width:1100px){.comp-recursive-grid{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}
@media(hover:hover){.comp-recursive-summary:hover{background:#102a40}}
'''


if __name__ == '__main__':
    core.main()
