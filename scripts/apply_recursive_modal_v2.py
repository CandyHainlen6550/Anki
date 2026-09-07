from pathlib import Path

p = Path('builder/build_anki.py')
s = p.read_text(encoding='utf-8')

marker = '/* recursive-modal-v2 */'
if marker in s:
    print('recursive modal v2 already applied')
    raise SystemExit(0)

old_css_anchor = "\nSTROKE_BACK = r'''"
new_css = """
CSS += r'''
/* recursive-modal-v2 */
.comp-modal-overlay{height:100vh;max-height:100vh;overflow:hidden;touch-action:none}
.comp-modal-panel{width:760px;max-width:calc(100vw - 24px);max-height:calc(100vh - 24px)}
.comp-modal-body{min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;touch-action:pan-y}
@supports (height:100dvh){.comp-modal-overlay{height:100dvh;max-height:100dvh}.comp-modal-panel{max-height:calc(100dvh - 24px)}}
@media(max-width:680px){.comp-modal-panel{max-width:calc(100vw - 12px);max-height:calc(100vh - 12px)}@supports (height:100dvh){.comp-modal-panel{max-height:calc(100dvh - 12px)}}}
'''

STROKE_BACK = r'''"""
if old_css_anchor not in s:
    raise SystemExit('CSS anchor changed; refusing unsafe patch')
s = s.replace(old_css_anchor, new_css, 1)

old_js = """  var title=overlay.querySelector('.comp-modal-title'),body=overlay.querySelector('.comp-modal-body'),closeBtn=overlay.querySelector('.comp-modal-close'),lastTrigger=null;\n  function closeModal(){overlay.classList.remove('is-open');overlay.setAttribute('aria-hidden','true');body.innerHTML='';if(lastTrigger&&lastTrigger.focus){try{lastTrigger.focus()}catch(e){}}lastTrigger=null}\n  function openModal(trigger){\n    var id=trigger&&trigger.getAttribute('data-comp-modal'),source=id&&document.getElementById(id);if(!source)return;\n    var sourceTitle=source.querySelector('.comp-modal-source-title'),sourceContent=source.querySelector('.comp-modal-source-content');if(!sourceTitle||!sourceContent)return;\n    lastTrigger=trigger;title.innerHTML=sourceTitle.innerHTML;body.innerHTML=sourceContent.innerHTML;body.scrollTop=0;overlay.classList.add('is-open');overlay.setAttribute('aria-hidden','false');\n    try{closeBtn.focus()}catch(e){}\n  }\n"""
new_js = """  var title=overlay.querySelector('.comp-modal-title'),body=overlay.querySelector('.comp-modal-body'),closeBtn=overlay.querySelector('.comp-modal-close'),lastTrigger=null,pageLocked=false,lockedY=0,oldBodyStyle='',oldHtmlStyle='';\n  function lockPage(){if(pageLocked)return;lockedY=window.pageYOffset||document.documentElement.scrollTop||document.body.scrollTop||0;oldBodyStyle=document.body.getAttribute('style')||'';oldHtmlStyle=document.documentElement.getAttribute('style')||'';document.documentElement.style.overflow='hidden';document.body.style.position='fixed';document.body.style.top=(-lockedY)+'px';document.body.style.left='0';document.body.style.right='0';document.body.style.width='100%';document.body.style.overflow='hidden';pageLocked=true}\n  function unlockPage(){if(!pageLocked)return;if(oldBodyStyle)document.body.setAttribute('style',oldBodyStyle);else document.body.removeAttribute('style');if(oldHtmlStyle)document.documentElement.setAttribute('style',oldHtmlStyle);else document.documentElement.removeAttribute('style');pageLocked=false;try{window.scrollTo(0,lockedY)}catch(e){}}\n  function closeModal(){overlay.classList.remove('is-open');overlay.setAttribute('aria-hidden','true');body.innerHTML='';unlockPage();if(lastTrigger&&lastTrigger.focus){try{lastTrigger.focus()}catch(e){}}lastTrigger=null}\n  function openModal(trigger){\n    var id=trigger&&trigger.getAttribute('data-comp-modal'),source=id&&document.getElementById(id);if(!source)return;\n    var sourceTitle=source.querySelector('.comp-modal-source-title'),sourceContent=source.querySelector('.comp-modal-source-content');if(!sourceTitle||!sourceContent)return;\n    lastTrigger=trigger;lockPage();title.innerHTML=sourceTitle.innerHTML;body.innerHTML=sourceContent.innerHTML;body.scrollTop=0;overlay.classList.add('is-open');overlay.setAttribute('aria-hidden','false');\n    try{closeBtn.focus()}catch(e){}\n  }\n"""
if old_js not in s:
    raise SystemExit('Modal JS source changed; refusing unsafe patch')
s = s.replace(old_js, new_js, 1)

old_nested = "    nested = _recursive_block_html(child, child.get('children') or [], glyph_renderer, depth + 1) if child.get('children') else ''"
new_nested = "    nested = (_recursive_modal_html(child, child.get('children') or [], glyph_renderer, depth + 1) if depth == 2 else _recursive_block_html(child, child.get('children') or [], glyph_renderer, depth + 1)) if child.get('children') else ''"
if old_nested not in s:
    raise SystemExit('Recursive child source changed; refusing unsafe patch')
s = s.replace(old_nested, new_nested, 1)

old_top = "        recursive = _recursive_modal_html(item, item.get('children') or [], glyph_renderer, 2)"
new_top = "        recursive = _recursive_block_html(item, item.get('children') or [], glyph_renderer, 2)"
if old_top not in s:
    raise SystemExit('Top-level recursive source changed; refusing unsafe patch')
s = s.replace(old_top, new_top, 1)

old_reg = "        '供': ('data-component=\"亻\"', 'data-component=\"共\"', 'class=\"comp-modal-trigger\"', 'class=\"comp-modal-source\"', 'data-recursive-root=\"共\"', 'data-recursive-child=\"卄\"', 'data-recursive-child=\"𬺢\"'),"
new_reg = "        '供': ('data-component=\"亻\"', 'data-component=\"共\"', 'data-recursive-root=\"共\"', 'data-recursive-child=\"卄\"', 'data-recursive-child=\"𬺢\"'),"
if old_reg not in s:
    raise SystemExit('供 regression source changed; refusing unsafe patch')
s = s.replace(old_reg, new_reg, 1)

old_qa = """    for item in items:\n        if item.get('children'):\n            key_attr = html.escape(str(item.get('key') or ''), quote=True)\n            card_start = rendered.find('data-component=\"' + key_attr + '\"')\n            modal_start = rendered.find('class=\"comp-modal-source\"', card_start)\n            details_start = rendered.find('<details class=\"comp-recursive\"', card_start)\n            if card_start < 0 or modal_start < 0 or (details_start >= 0 and details_start < modal_start):\n                raise RuntimeError(ch + ' component modal QA failed for: ' + str(item.get('key') or ''))\n"""
new_qa = """    for item in items:\n        children = item.get('children') or []\n        if children:\n            key_attr = html.escape(str(item.get('key') or ''), quote=True)\n            card_start = rendered.find('data-component=\"' + key_attr + '\"')\n            details_start = rendered.find('<details class=\"comp-recursive\"', card_start)\n            if card_start < 0 or details_start < 0:\n                raise RuntimeError(ch + ' first-level recursive block QA failed for: ' + str(item.get('key') or ''))\n        for child in children:\n            if child.get('children'):\n                child_attr = html.escape(str(child.get('key') or ''), quote=True)\n                child_start = rendered.find('data-recursive-child=\"' + child_attr + '\"')\n                modal_start = rendered.find('class=\"comp-modal-trigger\"', child_start)\n                if child_start < 0 or modal_start < 0:\n                    raise RuntimeError(ch + ' second-level modal QA failed for: ' + str(child.get('key') or ''))\n"""
if old_qa not in s:
    raise SystemExit('Component modal QA source changed; refusing unsafe patch')
s = s.replace(old_qa, new_qa, 1)

p.write_text(s, encoding='utf-8')
print('Applied recursive modal v2: first level inline, second level modal, viewport scroll lock.')
