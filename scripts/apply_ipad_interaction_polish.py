from pathlib import Path

p = Path('builder/build_anki.py')
s = p.read_text(encoding='utf-8')

# 1) Prevent native selection/callouts around the handwriting area.
marker = "CSS += r'''\n/* ipad-interaction-polish-v1 */"
if marker not in s:
    insert_at = "STROKE_BACK = r'''"
    css = r'''CSS += r'''
/* ipad-interaction-polish-v1 */
#ht-write-root,#ht-write-root *{-webkit-user-select:none!important;user-select:none!important;-webkit-touch-callout:none!important}
.writer-box,.writer-box *{touch-action:none!important;-webkit-user-drag:none!important}
.writer-tools button{-webkit-user-select:none!important;user-select:none!important;-webkit-touch-callout:none!important;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.comp-modal-overlay{display:flex!important;visibility:hidden;opacity:0;pointer-events:none;-webkit-backface-visibility:hidden;backface-visibility:hidden;transform:translateZ(0)}
.comp-modal-overlay.is-open{visibility:visible;opacity:1;pointer-events:auto}
.comp-modal-panel{-webkit-backface-visibility:hidden;backface-visibility:hidden;transform:translateZ(0)}
'''

'''
    if insert_at not in s:
        raise SystemExit('CSS insertion anchor changed')
    s = s.replace(insert_at, css + insert_at, 1)

# 2) Avoid reparsing a large recursive subtree on every modal open and show the modal
# before freezing the body. This removes the WKWebView black flash/jank.
old_decl = "var title=overlay.querySelector('.comp-modal-title'),body=overlay.querySelector('.comp-modal-body'),closeBtn=overlay.querySelector('.comp-modal-close'),lastTrigger=null,pageLocked=false,lockedY=0,oldBodyStyle='',oldHtmlStyle='';"
new_decl = "var title=overlay.querySelector('.comp-modal-title'),body=overlay.querySelector('.comp-modal-body'),closeBtn=overlay.querySelector('.comp-modal-close'),lastTrigger=null,pageLocked=false,lockedY=0,oldBodyStyle='',oldHtmlStyle='',activeContent=null,activeSource=null;"
if new_decl not in s:
    if old_decl not in s:
        raise SystemExit('Modal declaration anchor changed')
    s = s.replace(old_decl, new_decl, 1)

old_close = "  function closeModal(){overlay.classList.remove('is-open');overlay.setAttribute('aria-hidden','true');body.innerHTML='';unlockPage();if(lastTrigger&&lastTrigger.focus){try{lastTrigger.focus()}catch(e){}}lastTrigger=null}"
new_close = "  function restoreModalContent(){if(activeContent&&activeSource){try{activeSource.appendChild(activeContent)}catch(e){}}activeContent=null;activeSource=null;while(body.firstChild){body.removeChild(body.firstChild)}}\n  function closeModal(){overlay.classList.remove('is-open');overlay.setAttribute('aria-hidden','true');restoreModalContent();unlockPage();lastTrigger=null}"
if new_close not in s:
    if old_close not in s:
        raise SystemExit('Modal close anchor changed')
    s = s.replace(old_close, new_close, 1)

old_open = "    lastTrigger=trigger;lockPage();title.innerHTML=sourceTitle.innerHTML;body.innerHTML=sourceContent.innerHTML;body.scrollTop=0;overlay.classList.add('is-open');overlay.setAttribute('aria-hidden','false');\n    try{closeBtn.focus()}catch(e){}"
new_open = "    lastTrigger=trigger;restoreModalContent();title.innerHTML=sourceTitle.innerHTML;activeSource=sourceContent;activeContent=sourceContent.firstElementChild;if(!activeContent)return;body.appendChild(activeContent);body.scrollTop=0;overlay.classList.add('is-open');overlay.setAttribute('aria-hidden','false');\n    requestAnimationFrame(function(){if(overlay.classList.contains('is-open'))lockPage()})"
if new_open not in s:
    if old_open not in s:
        raise SystemExit('Modal open anchor changed')
    s = s.replace(old_open, new_open, 1)

# 3) Suppress WebKit text selection while writing with Apple Pencil/stylus.
old_svg_setup = "svg.style.touchAction='none';svg.style.userSelect='none';svg.style.webkitUserSelect='none';"
new_svg_setup = "svg.style.touchAction='none';svg.style.userSelect='none';svg.style.webkitUserSelect='none';svg.style.webkitTouchCallout='none';\nfunction writerNode(n){if(!n)return false;var e=n.nodeType===1?n:n.parentNode;return !!(e&&root.contains(e))}\nfunction clearWriterSelection(){try{var sel=window.getSelection&&window.getSelection();if(sel&&sel.rangeCount&&(writerNode(sel.anchorNode)||writerNode(sel.focusNode)))sel.removeAllRanges()}catch(e){}}\nroot.addEventListener('selectstart',function(ev){ev.preventDefault();clearWriterSelection()},{capture:true,passive:false});\nroot.addEventListener('dragstart',function(ev){ev.preventDefault()},{capture:true,passive:false});\nroot.addEventListener('contextmenu',function(ev){if(writerNode(ev.target))ev.preventDefault()},{capture:true,passive:false});\ndocument.addEventListener('selectionchange',clearWriterSelection,false);"
if new_svg_setup not in s:
    if old_svg_setup not in s:
        raise SystemExit('Writer setup anchor changed')
    s = s.replace(old_svg_setup, new_svg_setup, 1)

# Stop the Anki card / WebKit gesture layer from seeing active pen strokes.
old_begin = "function begin(ev){if(idx>=paths.length)return;if(ev.isPrimary===false)return;ev.preventDefault();"
new_begin = "function begin(ev){if(idx>=paths.length)return;if(ev.isPrimary===false)return;ev.preventDefault();ev.stopPropagation();clearWriterSelection();"
if new_begin not in s:
    if old_begin not in s:
        raise SystemExit('Writer begin anchor changed')
    s = s.replace(old_begin, new_begin, 1)

old_move = "function move(ev){if(!drawing)return;if(activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;ev.preventDefault();"
new_move = "function move(ev){if(!drawing)return;if(activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;ev.preventDefault();ev.stopPropagation();"
if new_move not in s:
    if old_move not in s:
        raise SystemExit('Writer move anchor changed')
    s = s.replace(old_move, new_move, 1)

old_end = "function end(ev){if(!drawing)return;if(ev&&activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;if(ev)ev.preventDefault();"
new_end = "function end(ev){if(!drawing)return;if(ev&&activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;if(ev){ev.preventDefault();ev.stopPropagation()}"
if new_end not in s:
    if old_end not in s:
        raise SystemExit('Writer end anchor changed')
    s = s.replace(old_end, new_end, 1)

p.write_text(s, encoding='utf-8')

# Static regressions for both issues.
s = p.read_text(encoding='utf-8')
checks = [
    'ipad-interaction-polish-v1',
    "activeContent=sourceContent.firstElementChild",
    "requestAnimationFrame(function(){if(overlay.classList.contains('is-open'))lockPage()})",
    "root.addEventListener('selectstart'",
    "document.addEventListener('selectionchange',clearWriterSelection,false)",
    "ev.preventDefault();ev.stopPropagation();clearWriterSelection();",
]
missing = [x for x in checks if x not in s]
if missing:
    raise SystemExit('Interaction polish regression missing: ' + ', '.join(missing))
print('Applied iPad modal + Apple Pencil interaction polish.')
