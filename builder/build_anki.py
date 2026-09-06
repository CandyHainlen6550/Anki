#!/usr/bin/env python3
import argparse, base64, collections, hashlib, html, json, re, sqlite3, time, zipfile, gzip
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA = r'''
CREATE TABLE col (id integer primary key, crt integer not null, mod integer not null, scm integer not null, ver integer not null, dty integer not null, usn integer not null, ls integer not null, conf text not null, models text not null, decks text not null, dconf text not null, tags text not null);
CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null, mod integer not null, usn integer not null, tags text not null, flds text not null, sfld integer not null, csum integer not null, flags integer not null, data text not null);
CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null, ord integer not null, mod integer not null, usn integer not null, type integer not null, queue integer not null, due integer not null, ivl integer not null, factor integer not null, reps integer not null, lapses integer not null, left integer not null, odue integer not null, odid integer not null, flags integer not null, data text not null);
CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null, ease integer not null, ivl integer not null, lastIvl integer not null, factor integer not null, time integer not null, type integer not null);
CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
CREATE INDEX ix_notes_usn on notes (usn); CREATE INDEX ix_cards_usn on cards (usn); CREATE INDEX ix_revlog_usn on revlog (usn); CREATE INDEX ix_cards_nid on cards (nid); CREATE INDEX ix_cards_sched on cards (did, queue, due); CREATE INDEX ix_revlog_cid on revlog (cid); CREATE INDEX ix_notes_csum on notes (csum);
'''

# Stable IDs and stable names are intentional. Do not change them between releases;
# existing users must be able to import a new HT Joyo 2136.apkg as an in-place update.
DECK_ROOT = 2084677001
DECK_400 = 2084677100; DECK_400_K2HV = 2084677101; DECK_400_HV2K = 2084677102; DECK_400_WRITE = 2084677103
DECK_800 = 2084677200; DECK_800_K2HV = 2084677201; DECK_800_HV2K = 2084677202; DECK_800_WRITE = 2084677203
DECK_ALL = 2084677300; DECK_ALL_K2HV = 2084677301; DECK_ALL_HV2K = 2084677302; DECK_ALL_WRITE = 2084677303
MODEL_ID = 2084677010
ROOT_NAME = 'HT Joyo 2136'

DECK_NAMES = {
    DECK_ROOT: ROOT_NAME,
    DECK_400: ROOT_NAME+'::01 Sơ cấp 1 — 400',
    DECK_400_K2HV: ROOT_NAME+'::01 Sơ cấp 1 — 400::01 Kanji → Hán Việt',
    DECK_400_HV2K: ROOT_NAME+'::01 Sơ cấp 1 — 400::02 Hán Việt → Kanji',
    DECK_400_WRITE: ROOT_NAME+'::01 Sơ cấp 1 — 400::03 Viết Kanji',
    DECK_800: ROOT_NAME+'::02 Sơ cấp 2 — 800',
    DECK_800_K2HV: ROOT_NAME+'::02 Sơ cấp 2 — 800::01 Kanji → Hán Việt',
    DECK_800_HV2K: ROOT_NAME+'::02 Sơ cấp 2 — 800::02 Hán Việt → Kanji',
    DECK_800_WRITE: ROOT_NAME+'::02 Sơ cấp 2 — 800::03 Viết Kanji',
    DECK_ALL: ROOT_NAME+'::03 All — 2136 từ',
    DECK_ALL_K2HV: ROOT_NAME+'::03 All — 2136 từ::01 Kanji → Hán Việt',
    DECK_ALL_HV2K: ROOT_NAME+'::03 All — 2136 từ::02 Hán Việt → Kanji',
    DECK_ALL_WRITE: ROOT_NAME+'::03 All — 2136 từ::03 Viết Kanji',
}
SUBSET_DECKS = {
    'sc1': (DECK_400_K2HV, DECK_400_HV2K, DECK_400_WRITE),
    'sc2': (DECK_800_K2HV, DECK_800_HV2K, DECK_800_WRITE),
    'all': (DECK_ALL_K2HV, DECK_ALL_HV2K, DECK_ALL_WRITE),
}



def render_inline_glyphs(text):
    """
    Wrap uncommon CJK glyphs inside mnemonic text so they use
    the same glyph renderer as decomposition cards instead of
    relying on the browser font fallback.
    """
    if not text:
        return text
    out = []
    for ch in str(text):
        cp = ord(ch)
        if (
            0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF
            or 0x20000 <= cp <= 0x2FA1F
        ):
            out.append(render_glyph_inline(ch))
        else:
            out.append(ch)
    return "".join(out)

def page_deck_id(parent_did,page):
    # Stable child deck ID: existing mode deck ID + repo page.
    return int(parent_did)*100+int(page)

def repo_pages(rows):
    pages=sorted({int(r.get('repo_page') or 0) for r in rows})
    if not pages or pages[0] < 1:
        raise ValueError('Sơ cấp repo rows must contain valid page numbers.')
    return pages

FIELDS = [
    'Kanji','HanViet','Meaning','On','Kun','KunWords','Furigana','Mnemonic',
    'Key','KvgFile','StrokeDataB64','StrokeSVG','Disambiguator','ComponentsHTML','StrokeCount'
]

CSS = r'''
.card{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Arial,sans-serif;text-align:center;color:#eaf2ff;background:#0c1b2b;margin:0;padding:18px;box-sizing:border-box}.ht-card{max-width:920px;margin:0 auto;background:#102338;border:1px solid #27435d;border-radius:22px;padding:28px;box-sizing:border-box;box-shadow:0 10px 30px rgba(0,0,0,.18)}.eyebrow,.section-title,.mini-label{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8ea5ba;font-weight:800}.eyebrow{margin-bottom:10px}.kanji{font-family:"Noto Serif JP","Yu Mincho","Hiragino Mincho ProN",serif;font-size:108px;line-height:1.05;color:#13c8ff;font-weight:500}.hv{font-size:42px;font-weight:800;line-height:1.2}.meaning{margin-top:12px;color:#b4c6d8;font-size:20px;line-height:1.45}.answer-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:20px;text-align:left}.fact{background:#0a1827;border:1px solid #284158;border-radius:14px;padding:13px}.fact b{display:block;color:#8198ad;font-size:11px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:5px}.fact span{font-size:16px}.furigana-render{font-family:"Noto Sans JP","Yu Gothic","Hiragino Sans",sans-serif;line-height:2.15}.furigana-render ruby{ruby-position:over}.furigana-render rt{font-size:.62em;color:#91a9bd;font-weight:600}.mnemonic{margin-top:14px;text-align:left;background:#2a1604;border:1px solid #8a5200;border-radius:14px;padding:14px;color:#ffe4ad;line-height:1.55}.small{font-size:14px;color:#8fa5b9;margin-top:10px}.disambig{font-size:16px;color:#9fb4c8;margin-top:8px}.detail-section{margin-top:24px;padding-top:20px;border-top:1px solid #294158;text-align:left}.section-title{font-size:14px;color:#d6e7f5;margin-bottom:12px}.comp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.comp-card{background:#081727;border:1px solid #31516b;border-left:4px solid #13c8ff;border-radius:16px;padding:14px;min-width:0}.comp-head{display:flex;gap:13px;align-items:center}.comp-glyph{width:72px;height:72px;flex:0 0 72px;border:1px solid #31516b;border-radius:14px;background:#102338;display:flex;align-items:center;justify-content:center;font-family:"Noto Serif JP","Yu Mincho",serif;font-size:50px;color:#eef7ff;overflow:hidden}.comp-glyph img{width:82%;height:82%;object-fit:contain;filter:invert(1)}.comp-glyph svg{width:84%;height:84%;display:block;color:#eef7ff;fill:currentColor}.comp-entity-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;line-height:1.15;color:#9fb4c8;overflow-wrap:anywhere;padding:4px}.comp-name{font-size:21px;font-weight:800}.comp-meta{color:#99aec2;font-size:14px;line-height:1.45;margin-top:3px}.comp-role{color:#13c8ff;font-weight:700;font-size:13px;margin-top:3px}.comp-box{margin-top:12px;padding:10px 11px;border:1px solid #263f56;border-radius:12px;line-height:1.5;color:#cfdeeb}.comp-box.mn{background:#271503;border-color:#755000;color:#ffe5b5}.comp-empty{color:#91a7bb;padding:14px;border:1px dashed #38536a;border-radius:12px}.origin-card{background:#081727;border:1px solid #2f4d66;border-radius:16px;padding:15px;line-height:1.55}.origin-type{font-size:20px;font-weight:800;color:#eaf2ff}.origin-summary{margin-top:7px;color:#cad9e7}.origin-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:13px}.origin-fact{background:#0f2133;border:1px solid #29445b;border-radius:11px;padding:10px}.origin-fact b{display:block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#8198ad;margin-bottom:5px}.ids-text{font-family:"Noto Sans CJK JP","Noto Sans JP","Yu Gothic",sans-serif;overflow-wrap:anywhere}.conflict{margin-top:12px;color:#ffbd52;background:#2d1d06;border:1px solid #80591b;border-radius:10px;padding:10px}.stroke-area{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.stroke-preview{width:250px;height:250px;border:1px solid #31516b;background:#13243a;border-radius:14px;overflow:hidden;display:flex;align-items:center;justify-content:center}.stroke-preview svg{width:100%;height:100%;display:block}.stroke-info{min-width:180px;flex:1;color:#bfd0df;line-height:1.55}.stroke-count{font-size:24px;font-weight:800;color:#eaf2ff}.stroke-replay{margin-top:12px;border:1px solid #365b73;background:#102b3f;color:#e9f7ff;border-radius:10px;padding:9px 14px;font-weight:700}.writer-wrap{max-width:390px;margin:18px auto 0}.writer-box{width:min(82vw,340px);aspect-ratio:1/1;margin:0 auto;background:#13243a;border:2px solid #2c526c;border-radius:16px;overflow:hidden;touch-action:none}.writer-box svg{display:block;width:100%;height:100%;touch-action:none}.writer-tools{display:flex;justify-content:center;gap:10px;margin-top:12px}.writer-tools button{border:1px solid #365b73;background:#102b3f;color:#e9f7ff;border-radius:10px;padding:9px 14px;font-weight:700}.writer-status{min-height:24px;margin-top:10px;font-weight:700;color:#a9c3d6}.writer-status.ok{color:#4ade80}.writer-status.bad{color:#fb7185}.locked{background:#30150f;border:1px solid #874838;border-radius:14px;padding:18px;color:#ffd0c3;font-weight:700}.nightMode .card,.night_mode .card{background:#0c1b2b;color:#eaf2ff}@media(max-width:680px){.ht-card{padding:20px 14px;border-radius:16px}.kanji{font-size:84px}.hv{font-size:32px}.answer-grid,.comp-grid,.origin-grid{grid-template-columns:1fr}.comp-glyph{width:64px;height:64px;flex-basis:64px;font-size:44px}.stroke-preview{width:min(74vw,240px);height:min(74vw,240px)}}
'''

CSS += r'''
.comp-grid{align-items:start}.comp-recursive{width:100%;box-sizing:border-box;margin-top:12px;border:1px solid #31516b;border-radius:14px;overflow:hidden;background:#0b1c2d;color:#dbeaf7}.comp-recursive-summary{box-sizing:border-box;min-height:48px;padding:10px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;list-style:none;font-weight:800;line-height:1.35;-webkit-tap-highlight-color:transparent;touch-action:manipulation;user-select:none;-webkit-user-select:none}.comp-recursive-summary::-webkit-details-marker{display:none}.comp-recursive-summary::marker{content:''}.comp-recursive-summary-title{min-width:0;overflow-wrap:anywhere}.comp-recursive-summary-title b{font-family:"Noto Serif JP","Yu Mincho",serif;color:#13c8ff;font-size:1.12em}.comp-recursive-summary-side{display:flex;align-items:center;gap:8px;flex:0 0 auto;color:#8fa9bd;font-size:12px;white-space:nowrap}.comp-recursive-chevron{width:18px;height:18px;flex:0 0 18px;display:inline-flex;align-items:center;justify-content:center;transition:transform .18s ease;transform-origin:center}.comp-recursive-chevron svg{width:14px;height:14px;display:block;overflow:visible}.comp-recursive-chevron path{fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}.comp-recursive[open]>.comp-recursive-summary .comp-recursive-chevron{transform:rotate(180deg)}.comp-recursive-body{box-sizing:border-box;padding:12px;border-top:1px solid #294158;background:#081727}.comp-recursive-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;width:100%}.comp-recursive-child{box-sizing:border-box;min-width:0;padding:10px;background:#102338;border:1px solid #294962;border-radius:12px;text-align:left}.comp-recursive-child-head{display:grid;grid-template-columns:72px minmax(0,1fr);gap:12px;align-items:start}.comp-recursive-child .comp-glyph{width:72px;height:72px;flex-basis:72px;font-size:48px;border-radius:12px}.comp-recursive-child .comp-glyph img,.comp-recursive-child .comp-glyph svg{max-width:100%;max-height:100%}.comp-recursive-copy{min-width:0}.comp-recursive-copy strong,.comp-recursive-copy span,.comp-recursive-copy small{display:block;min-width:0;overflow-wrap:anywhere;word-break:break-word}.comp-recursive-copy strong{font-size:22px;line-height:1.25;color:#eef7ff}.comp-recursive-copy span{margin-top:3px;font-size:16px;line-height:1.45;color:#c4d4e2}.comp-recursive-copy small{margin-top:4px;font-size:12px;line-height:1.35;color:#13c8ff}.comp-recursive-role{color:#8fa9bd!important}.comp-recursive-mn{margin-top:8px;color:#ffe5b5;font-size:13px;line-height:1.45}.comp-recursive .comp-recursive{margin-top:9px}
@media(max-width:680px){.comp-recursive{margin-top:10px}.comp-recursive-summary{min-height:50px;padding:11px 12px}.comp-recursive-summary-side>span:first-child{display:none}.comp-recursive-body{padding:10px}.comp-recursive-grid{grid-template-columns:1fr}.comp-recursive-child{padding:9px}.comp-recursive-child-head{grid-template-columns:52px minmax(0,1fr)}.comp-recursive-child .comp-glyph{width:52px;height:52px;flex-basis:52px;font-size:36px}}@media(min-width:681px) and (max-width:1100px){.comp-recursive-grid{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}@media(hover:hover){.comp-recursive-summary:hover{background:#102a40}}
'''

STROKE_BACK = r'''
<div class="detail-section">
  <div class="section-title">Thứ tự nét</div>
  <div class="stroke-area">
    <div class="stroke-preview"><div class="ht-stroke-order" aria-label="Thứ tự nét {{Kanji}}">{{StrokeSVG}}</div></div>
    <div class="stroke-info"><div class="stroke-count">{{StrokeCount}} nét</div><div>Tự động vẽ từng nét theo thứ tự; màu và số nét tương ứng nhau.</div><button type="button" class="stroke-replay">Vẽ lại</button></div>
  </div>
</div>
<script>
(function(){'use strict';
var P=['#1687ff','#ff5b55','#23c483','#ffb31a','#a970ff','#00c2ff','#ff66c4','#9bd34f','#f97316','#22d3ee','#e879f9','#84cc16','#f43f5e','#14b8a6','#facc15','#8b5cf6'];
function animate(el){
  var svg=el&&el.querySelector('svg.kvg-inline'); if(!svg)return;
  if(svg.getAttribute('data-normalize')==='1'){var gs=svg.querySelector('.kvg-strokes'),gn=svg.querySelector('.kvg-numbers');try{var b=gs.getBBox();if(b&&b.width>0&&b.height>0){var s=Math.min(89/b.width,89/b.height),tx=54.5-(b.x+b.width/2)*s,ty=54.5-(b.y+b.height/2)*s,tr='matrix('+s+' 0 0 '+s+' '+tx+' '+ty+')';gs.setAttribute('transform',tr);if(gn)gn.setAttribute('transform',tr)}}catch(e){}}
  var paths=svg.querySelectorAll('path.kvg-stroke'), labels=svg.querySelectorAll('text.kvg-number');
  for(var i=0;i<paths.length;i++){
    var p=paths[i], col=P[i%P.length], L=0;
    p.setAttribute('stroke',col); p.style.transition='none';
    try{L=p.getTotalLength()}catch(e){}
    if(L>0){p.style.strokeDasharray=String(L);p.style.strokeDashoffset=String(L)}else{p.style.strokeDasharray='none';p.style.strokeDashoffset='0'}
    if(labels[i]){labels[i].setAttribute('fill',col);labels[i].style.transition='none';labels[i].style.opacity='0'}
  }
  void svg.getBoundingClientRect();
  setTimeout(function(){requestAnimationFrame(function(){
    for(var j=0;j<paths.length;j++){
      var delay=j*.44;
      paths[j].style.transition='stroke-dashoffset .38s ease '+delay+'s';
      paths[j].style.strokeDashoffset='0';
      if(labels[j]){labels[j].style.transition='opacity .12s linear '+Math.max(0,delay-.04)+'s';labels[j].style.opacity='1'}
    }
  })},90);
}
function init(){var els=document.querySelectorAll('.ht-stroke-order');for(var i=0;i<els.length;i++){(function(el){animate(el);var area=el.closest('.stroke-area');var b=area&&area.querySelector('.stroke-replay');if(b&&!b.dataset.bound){b.dataset.bound='1';b.addEventListener('click',function(){animate(el)})}})(els[i])}}
setTimeout(init,20);setTimeout(init,240);
})();
</script>
'''

COMMON_BACK = r'''
<div class="ht-card">
  <div class="eyebrow">Đáp án</div>
  <div class="kanji">{{Kanji}}</div>
  <div class="hv">{{HanViet}}</div>
  <div class="meaning">{{Meaning}}</div>
  <div class="answer-grid">
    <div class="fact"><b>Âm On</b><span>{{On}}</span></div>
    <div class="fact"><b>Âm Kun</b><span>{{Kun}}</span></div>
    <div class="fact"><b>Từ Kun</b><span>{{KunWords}}</span></div>
    <div class="fact"><b>Furigana</b><span class="furigana-render">{{furigana:Furigana}}</span></div>
  </div>
  <div class="mnemonic"><b>Mẹo nhớ</b><br>{{Mnemonic}}</div>
  <div class="detail-section"><div class="section-title">Thành phần</div><div class="comp-grid">{{ComponentsHTML}}</div></div>
''' + STROKE_BACK + r'''
</div>
'''

Q_K2HV = r'''<div class="ht-card"><div class="eyebrow">Kanji → Hán Việt</div><div class="kanji">{{Kanji}}</div><div class="small">Nhớ âm Hán Việt rồi lật thẻ</div></div>'''
A_K2HV = COMMON_BACK
Q_HV2K = r'''<div class="ht-card"><div class="eyebrow">Hán Việt → Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="small">Nhớ chữ Kanji rồi lật thẻ</div></div>'''
A_HV2K = COMMON_BACK

WRITER_JS = r'''
<script>
(function(){'use strict';
var root=document.getElementById('ht-write-root');if(!root||root.dataset.init==='1')return;root.dataset.init='1';
var P=['#1687ff','#ff5b55','#23c483','#ffb31a','#a970ff','#00c2ff','#ff66c4','#9bd34f','#f97316','#22d3ee','#e879f9','#84cc16','#f43f5e','#14b8a6','#facc15','#8b5cf6'];
var target=root.getAttribute('data-kanji')||'',key=root.getAttribute('data-key')||target,embedded=root.getAttribute('data-strokes')||'',side=root.getAttribute('data-side')||'front';
var box=document.getElementById('ht-writer-box'),status=document.getElementById('ht-writer-status'),resetBtn=document.getElementById('ht-reset'),hintBtn=document.getElementById('ht-hint');
var NS='http://www.w3.org/2000/svg',paths=[],idx=0,drawing=false,pts=[],active=null,activePointer=null,raf=0,watchdog=0,liveD='',renderedCount=0,strokeNorm=false,norm=null;

/* Use one storage backend only. This avoids stale progress leaking through localStorage. */
var store=null;try{sessionStorage.setItem('__ht_writer_probe','1');sessionStorage.removeItem('__ht_writer_probe');store=sessionStorage}catch(e){try{localStorage.setItem('__ht_writer_probe','1');localStorage.removeItem('__ht_writer_probe');store=localStorage}catch(e2){store=null}}
function gateName(){return 'ht-write-ok:'+key}function progressName(){return 'ht-write-progress:'+key}
function storageGet(n){try{return store?store.getItem(n):null}catch(e){return null}}
function storageSet(n,v){try{if(store)store.setItem(n,v)}catch(e){}}
function storageRemove(n){try{if(store)store.removeItem(n)}catch(e){}}
function putGate(){storageSet(gateName(),String(Date.now()))}function clearGate(){storageRemove(gateName())}
function saveProgress(){storageSet(progressName(),JSON.stringify({i:idx,t:Date.now()}))}function clearProgress(){storageRemove(progressName())}
function msg(t,c){status.textContent=t;status.className='writer-status '+(c||'')}
function decode(){try{var x=JSON.parse(atob(embedded));if(Array.isArray(x))return x;if(x&&Array.isArray(x.p)){strokeNorm=!!x.z;return x.p}}catch(e){}return []}
function E(n,a){var e=document.createElementNS(NS,n);if(a)Object.keys(a).forEach(function(k){e.setAttribute(k,a[k])});return e}
var svg=E('svg',{viewBox:'0 0 109 109','class':'tappable'}),bg=E('g'),done=E('g'),live=E('g'),hints=E('g');
svg.style.touchAction='none';svg.style.userSelect='none';svg.style.webkitUserSelect='none';
svg.appendChild(E('rect',{x:'0',y:'0',width:'109',height:'109',fill:'#13243a'}));svg.appendChild(bg);svg.appendChild(hints);svg.appendChild(done);svg.appendChild(live);box.appendChild(svg);
[['0','54.5','109','54.5'],['54.5','0','54.5','109']].forEach(function(v){bg.appendChild(E('line',{x1:v[0],y1:v[1],x2:v[2],y2:v[3],stroke:'#60738c','stroke-width':'.65','stroke-dasharray':'4 3','stroke-opacity':'.7'}))});
var measure=E('path',{fill:'none',stroke:'none'});measure.style.visibility='hidden';svg.appendChild(measure);
function dist(a,b){var dx=a.x-b.x,dy=a.y-b.y;return Math.sqrt(dx*dx+dy*dy)}
function plen(p){var n=0;for(var i=1;i<p.length;i++)n+=dist(p[i-1],p[i]);return n}
function resample(p,n){if(p.length<2)return p;var L=plen(p),step=L/(n-1),out=[p[0]],acc=0,next=step;for(var i=1;i<p.length;i++){var a=p[i-1],b=p[i],d=dist(a,b);if(!d)continue;while(acc+d>=next&&out.length<n){var t=(next-acc)/d;out.push({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});next+=step}acc+=d}while(out.length<n)out.push(p[p.length-1]);return out}
function centroid(p){var x=0,y=0;for(var i=0;i<p.length;i++){x+=p[i].x;y+=p[i].y}return{x:x/p.length,y:y/p.length}}
function mapTarget(q){return norm?{x:q.x*norm.s+norm.tx,y:q.y*norm.s+norm.ty}:{x:q.x,y:q.y}}
function pathAttrs(d,i){var a={d:d,fill:'none',stroke:P[i%P.length],'stroke-width':'4.1','stroke-linecap':'round','stroke-linejoin':'round'};if(norm){a.transform='matrix('+norm.s+' 0 0 '+norm.s+' '+norm.tx+' '+norm.ty+')';a['vector-effect']='non-scaling-stroke'}return a}
function initNorm(){if(!strokeNorm||!paths.length)return;var g=E('g',{visibility:'hidden'});for(var i=0;i<paths.length;i++)g.appendChild(E('path',{d:paths[i],fill:'none'}));svg.appendChild(g);try{var b=g.getBBox();if(b&&b.width>0&&b.height>0){var s=Math.min(89/b.width,89/b.height);norm={s:s,tx:54.5-(b.x+b.width/2)*s,ty:54.5-(b.y+b.height/2)*s}}}catch(e){}try{g.remove()}catch(e){}}
function targetPts(d){measure.setAttribute('d',d);var L=measure.getTotalLength(),o=[];for(var i=0;i<64;i++){var q=measure.getPointAtLength(L*i/63);o.push(mapTarget(q))}return o}
function evalStroke(u,d){if(!u||u.length<2)return false;var t=targetPts(d),ur=resample(u,64),ul=plen(u),tl=plen(t),ratio=ul/tl;if(ratio<.48||ratio>1.58)return false;if(dist(ur[0],t[0])>34)return false;var uc=centroid(ur),tc=centroid(t),dx=tc.x-uc.x,dy=tc.y-uc.y,shape=0;for(var i=0;i<64;i++)shape+=dist({x:ur[i].x+dx,y:ur[i].y+dy},t[i]);shape/=64;return shape*.72+dist(uc,tc)*.28<18.5}
function pos(ev){var p=svg.createSVGPoint();p.x=ev.clientX;p.y=ev.clientY;var ctm=svg.getScreenCTM();return ctm?p.matrixTransform(ctm.inverse()):{x:0,y:0}}
function paintDone(n){done.innerHTML='';for(var i=0;i<n&&i<paths.length;i++)done.appendChild(E('path',pathAttrs(paths[i],i)))}
function restoreProgress(){if(side==='front'){clearGate()}var raw=storageGet(progressName());if(!raw)return;try{var o=JSON.parse(raw),age=Date.now()-Number(o.t||0),n=Number(o.i||0);if(age>=0&&age<10*60*1000&&n>0&&n<paths.length){idx=n;paintDone(idx);msg('Tiếp tục từ nét '+(idx+1)+'/'+paths.length,'')}else clearProgress()}catch(e){clearProgress()}}
function flipToBack(){
  try{if(typeof pycmd!=='undefined'){pycmd('ans');return}}catch(e){}
  try{if(typeof showAnswer==='function'){showAnswer();return}}catch(e){}
  try{if(typeof study!=='undefined'&&study&&typeof study.drawAnswer==='function'){study.drawAnswer();return}}catch(e){}
  /* AnkiMobile has no public showAnswer() API. Its native bridge can invoke the
     configured Mid Center tap action. Keep Question → Mid Center = Show Answer. */
  try{if(window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.cb){window.webkit.messageHandlers.cb.postMessage(JSON.stringify({scheme:'ankitap',msg:'midCenter'}));setTimeout(function(){if(document.getElementById('ht-write-root'))msg('✓ Đã viết đúng. Nếu iPad chưa lật: Taps → Question → Mid Center = Show Answer.','ok')},900);return}}catch(e){}
  try{if(window.anki&&typeof window.sendMessage2==='function'){window.sendMessage2('ankitap','midCenter');return}}catch(e){}
  try{if(window.anki&&typeof window.sendMessage==='function'){window.sendMessage('ankitap','midCenter');return}}catch(e){}
  msg('✓ Đã xác nhận. Bấm “Hiện đáp án” để xem đáp án.','ok')
}
function finish(){putGate();clearProgress();msg('✓ Viết đúng toàn bộ '+target+'.','ok');if(side==='back'&&typeof window.htRevealWriteAnswer==='function'){window.htRevealWriteAnswer()}else{setTimeout(flipToBack,180)}}

function cancelRAF(){if(raf){cancelAnimationFrame(raf);raf=0}}
function cancelWatchdog(){if(watchdog){clearTimeout(watchdog);watchdog=0}}
function armWatchdog(){cancelWatchdog();watchdog=setTimeout(function(){if(drawing)failActive('Sai nét — thao tác bị ngắt, viết lại nét '+(idx+1))},3500)}
function appendPoint(p){if(pts.length&&dist(pts[pts.length-1],p)<.7)return;pts.push({x:p.x,y:p.y})}
function renderLive(){raf=0;if(!active||!pts.length)return;if(!liveD){liveD='M '+pts[0].x.toFixed(2)+' '+pts[0].y.toFixed(2);renderedCount=1}for(var i=renderedCount;i<pts.length;i++)liveD+=' L '+pts[i].x.toFixed(2)+' '+pts[i].y.toFixed(2);renderedCount=pts.length;active.setAttribute('d',liveD)}
function scheduleRender(){if(!raf)raf=requestAnimationFrame(renderLive)}
function releaseCapture(){if(activePointer!==null){try{if(svg.hasPointerCapture&&svg.hasPointerCapture(activePointer))svg.releasePointerCapture(activePointer)}catch(e){}}}
function clearActiveNow(){cancelRAF();cancelWatchdog();releaseCapture();drawing=false;activePointer=null;pts=[];liveD='';renderedCount=0;if(active){try{active.remove()}catch(e){}active=null}}
function failActive(text){cancelRAF();cancelWatchdog();releaseCapture();drawing=false;activePointer=null;if(active){var bad=active;try{bad.setAttribute('stroke','#ff334e');bad.setAttribute('stroke-width','4.8');bad.style.opacity='1';bad.style.transition='opacity .32s ease'}catch(e){}setTimeout(function(){try{bad.style.opacity='0'}catch(e){}},360);setTimeout(function(){try{bad.remove()}catch(e){}},720)}active=null;pts=[];liveD='';renderedCount=0;msg(text||('Sai nét — viết lại nét '+(idx+1)),'bad')}
function begin(ev){if(idx>=paths.length)return;if(ev.isPrimary===false)return;ev.preventDefault();if(drawing||active)failActive('Sai nét — nét trước bị ngắt, viết lại nét '+(idx+1));drawing=true;activePointer=(typeof ev.pointerId==='number'?ev.pointerId:null);pts=[];liveD='';renderedCount=0;var p=pos(ev);appendPoint(p);active=E('path',{fill:'none',stroke:P[idx%P.length],'stroke-width':'4.4','stroke-linecap':'round','stroke-linejoin':'round',d:'M '+p.x+' '+p.y});live.appendChild(active);if(activePointer!==null)try{svg.setPointerCapture(activePointer)}catch(e){}armWatchdog()}
function move(ev){if(!drawing)return;if(activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;ev.preventDefault();var list=(typeof ev.getCoalescedEvents==='function'?ev.getCoalescedEvents():null);if(list&&list.length){for(var i=0;i<list.length;i++)appendPoint(pos(list[i]))}else appendPoint(pos(ev));scheduleRender();armWatchdog()}
function end(ev){if(!drawing)return;if(ev&&activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;if(ev)ev.preventDefault();if(ev)appendPoint(pos(ev));renderLive();cancelRAF();cancelWatchdog();releaseCapture();drawing=false;activePointer=null;var ok=false;try{ok=evalStroke(pts,paths[idx])}catch(e){ok=false}if(ok){if(active)active.remove();active=null;var col=P[idx%P.length];done.appendChild(E('path',pathAttrs(paths[idx],idx)));idx++;saveProgress();pts=[];liveD='';renderedCount=0;if(idx>=paths.length){finish()}else msg('✓ Đúng nét '+idx+'/'+paths.length+' · tiếp nét '+(idx+1),'ok')}else failActive('Sai nét — viết lại nét '+(idx+1))}
function cancelGesture(ev){if(!drawing)return;if(ev&&activePointer!==null&&typeof ev.pointerId==='number'&&ev.pointerId!==activePointer)return;failActive('Sai nét — thao tác bị ngắt, viết lại nét '+(idx+1))}
svg.addEventListener('pointerdown',begin,{passive:false});svg.addEventListener('pointermove',move,{passive:false});svg.addEventListener('pointerup',end,{passive:false});svg.addEventListener('pointercancel',cancelGesture,{passive:false});svg.addEventListener('lostpointercapture',function(){if(drawing)setTimeout(function(){if(drawing)failActive('Sai nét — thao tác bị ngắt, viết lại nét '+(idx+1))},0)});
resetBtn.addEventListener('click',function(){clearActiveNow();idx=0;done.innerHTML='';live.innerHTML='';hints.innerHTML='';clearProgress();clearGate();msg('Viết từ nét 1/'+paths.length,'')});
hintBtn.addEventListener('click',function(){if(idx>=paths.length)return;hints.innerHTML='';var p=E('path',pathAttrs(paths[idx],idx));p.style.opacity='.35';p.style.pointerEvents='none';hints.appendChild(p);try{var L=p.getTotalLength();p.style.strokeDasharray=String(L)+' '+String(L);p.style.strokeDashoffset=String(L);p.style.transition='none';void p.getBoundingClientRect();requestAnimationFrame(function(){requestAnimationFrame(function(){p.style.transition='stroke-dashoffset .14s linear';p.style.strokeDashoffset='0'})})}catch(e){}setTimeout(function(){try{hints.innerHTML=''}catch(e){}},320)});
paths=decode();if(paths.length){initNorm();restoreProgress();if(idx===0)msg(side==='back'?'Bạn đã lật sớm — tiếp tục viết ở đây. Đáp án vẫn bị khóa.':'Viết đúng '+paths.length+' nét để mở đáp án.','')}else{msg('Thiếu dữ liệu nét được nhúng trong thẻ.','bad');resetBtn.disabled=true;hintBtn.disabled=true}
})();
</script>
'''

# Card 02: optional handwriting. Correct writing auto-flips; normal Show Answer stays available.
Q_HV2K = r'''<div class="ht-card tappable" id="ht-write-root" data-side="front" data-kanji="{{Kanji}}" data-key="hv2k:{{Key}}" data-strokes="{{StrokeDataB64}}"><div class="eyebrow">Hán Việt → Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="writer-wrap"><div class="writer-box tappable" id="ht-writer-box"></div><div class="writer-tools"><button type="button" id="ht-reset">Viết lại</button><button type="button" id="ht-hint">Gợi ý nét</button></div><div id="ht-writer-status" class="writer-status"></div></div><div class="small">Vẽ đúng sẽ tự lật thẻ. Nếu chưa vẽ được, bạn vẫn có thể lật thủ công để xem đáp án.</div></div>''' + WRITER_JS
A_HV2K = COMMON_BACK

Q_WRITE = r'''<div class="ht-card tappable" id="ht-write-root" data-side="front" data-kanji="{{Kanji}}" data-key="{{Key}}" data-strokes="{{StrokeDataB64}}"><div class="eyebrow">Hán Việt → viết Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="writer-wrap"><div class="writer-box tappable" id="ht-writer-box"></div><div class="writer-tools"><button type="button" id="ht-reset">Viết lại</button><button type="button" id="ht-hint">Gợi ý nét</button></div><div id="ht-writer-status" class="writer-status"></div></div><div class="small">Đáp án chỉ hiện sau khi hệ thống xác nhận đủ nét đúng.</div></div>''' + WRITER_JS

A_WRITE = r'''<div id="ht-write-answer" data-key="{{Key}}"><div id="ht-back-writer"><div class="ht-card tappable" id="ht-write-root" data-side="back" data-kanji="{{Kanji}}" data-key="{{Key}}" data-strokes="{{StrokeDataB64}}"><div class="eyebrow">Hán Việt → viết Kanji</div><div class="hv">{{HanViet}}</div><div class="disambig">Nghĩa: {{Meaning}}</div><div class="writer-wrap"><div class="writer-box tappable" id="ht-writer-box"></div><div class="writer-tools"><button type="button" id="ht-reset">Viết lại</button><button type="button" id="ht-hint">Gợi ý nét</button></div><div id="ht-writer-status" class="writer-status"></div></div><div class="small">Bạn đã lật sớm: cứ tiếp tục viết ở đây. Đáp án vẫn bị khóa cho tới khi đủ nét đúng.</div></div></div><div id="ht-unlocked" style="display:none">''' + COMMON_BACK + r'''</div></div>''' + WRITER_JS + r'''<script>(function(){var wrap=document.getElementById('ht-write-answer');if(!wrap)return;var key=wrap.getAttribute('data-key')||'',gate='ht-write-ok:'+key;var store=null;try{sessionStorage.setItem('__ht_writer_probe','1');sessionStorage.removeItem('__ht_writer_probe');store=sessionStorage}catch(e){try{localStorage.setItem('__ht_writer_probe','1');localStorage.removeItem('__ht_writer_probe');store=localStorage}catch(e2){store=null}}function getGate(){var v=null;try{v=store?store.getItem(gate):null}catch(e){}var t=Number(v||0);return !!(t&&Date.now()-t>=0&&Date.now()-t<10*60*1000)}function clearGate(){try{if(store)store.removeItem(gate)}catch(e){}}window.htRevealWriteAnswer=function(){var w=document.getElementById('ht-back-writer'),a=document.getElementById('ht-unlocked');if(w)w.style.display='none';if(a)a.style.display='block';clearGate()};if(getGate())window.htRevealWriteAnswer();})();</script>'''

POS_VI={'left':'bên trái','right':'bên phải','top':'phía trên','bottom':'phía dưới','middle':'ở giữa','inside':'bên trong','outside':'bao ngoài','overlay':'chồng nét','surround_upper_left':'bao phía trên–trái','surround_upper_right':'bao phía trên–phải','surround_lower_left':'bao phía dưới–trái'}
ROLE_VI={'semantic':'phần nghĩa','phonetic':'phần âm','visual_only':'thành phần hình thể'}
MANUAL_COMP={
 '⺫':{'han_viet':'Mục/Võng','meaning_vi':'mắt / lưới ở phía trên','mnemonic_vi':'⺫ gợi hình con mắt hoặc tấm lưới nằm ngang.'},
 '𰃮':{'meaning_vi':'dạng giản hóa/shinjitai dùng làm component; tương ứng với phần hình thể phía trên của 學, Nhật dùng trong 学・覚・栄・労…','mnemonic_vi':'Nhớ mảnh hình này là phần giản hóa xuất hiện trong 学・覚・栄・労…; không coi nó là một chữ nghĩa độc lập mới.'}
}

def h(s): return html.escape(str(s or ''), quote=False)
def safe(s): return h(s).replace('\n','<br>')
def cap_hv(s):
    parts=re.split(r'([,;/])',str(s or ''))
    out=[]
    for p in parts:
        if p in (',',';'): out.append(p+' ')
        elif p=='/': out.append('/')
        else: out.append(p.strip().capitalize())
    return ''.join(out).strip()
def anki_furigana(s,target=''):
    """Convert source `語る【かたる】` to Anki ruby notation `語[かた]る`."""
    text=str(s or '').strip()
    if not text:return ''
    parts=[]
    for raw in re.split(r'\s*;\s*',text):
        raw=raw.strip()
        if not raw:continue
        m=re.fullmatch(r'(.+?)【([^】]+)】',raw)
        if not m:
            parts.append(raw.replace('【','[').replace('】',']'));continue
        surface,reading=m.group(1),m.group(2)
        if target and target in surface:
            i=surface.find(target);prefix=surface[:i];suffix=surface[i+len(target):]
            if reading.startswith(prefix) and (not suffix or reading.endswith(suffix)) and len(reading)>=len(prefix)+len(suffix):
                end=len(reading)-len(suffix) if suffix else len(reading);ruby=reading[len(prefix):end]
                if ruby:
                    parts.append(prefix+target+'['+ruby+']'+suffix);continue
        parts.append(surface+'['+reading+']')
    return ' ; '.join(parts)

def kvg_filename(ch): return f'{ord(ch):05x}.svg'

ENTITY_UNICODE_RE = re.compile(r'\+([0-9A-Fa-f]{4,6})(?:;|$)')

class GlyphRenderer:
    """Build-time glyph renderer for component cards.

    KanjiVG is intentionally NOT used here. KanjiVG remains stroke-order data only.
    Rare Unicode glyphs are outlined from HanaMin; named non-Unicode entities use
    build-time cached GlyphWiki SVGs and are embedded as data URIs in the APKG.
    """
    def __init__(self, hanamin_a=None, hanamin_b=None, glyphwiki_manifest=None):
        self.cache={}
        self.fonts={}
        self.gw={}
        self.gw_unicode={}
        self.stats=collections.Counter()
        self.missing_entities=set()
        self.missing_unicode=set()
        if hanamin_a: self.fonts['A']=self._load_font(hanamin_a)
        if hanamin_b: self.fonts['B']=self._load_font(hanamin_b)
        if glyphwiki_manifest and Path(glyphwiki_manifest).is_file():
            base=Path(glyphwiki_manifest).parent
            raw=json.load(open(glyphwiki_manifest,encoding='utf-8'))
            for key,info in raw.items():
                if not isinstance(info,dict):
                    continue
                if info.get('status')=='ok' and info.get('file'):
                    f=base/info['file']
                    if f.is_file(): self.gw[key]=(f,info)
                elif info.get('status')=='unicode_fallback' and info.get('char'):
                    self.gw_unicode[key]=str(info['char'])

    def _load_font(self,path):
        try:
            from fontTools.ttLib import TTFont
            font=TTFont(str(path),lazy=True)
            return {'font':font,'cmap':font.getBestCmap() or {},'glyphs':font.getGlyphSet()}
        except Exception as e:
            raise RuntimeError(f'Unable to load HanaMin font {path}: {e}')

    @staticmethod
    def entity_unicode(key):
        m=ENTITY_UNICODE_RE.search(str(key or ''))
        if not m:return None
        try:
            cp=int(m.group(1),16)
            return chr(cp) if 0<=cp<=0x10FFFF else None
        except Exception:return None

    def _font_svg(self,ch):
        cp=ord(ch); which=('B','A') if cp>=0x20000 else ('A','B')
        for bucket in which:
            face=self.fonts.get(bucket)
            if not face: continue
            name=face['cmap'].get(cp)
            if not name: continue
            glyph=face['glyphs'][name]
            try:
                from fontTools.pens.svgPathPen import SVGPathPen
                from fontTools.pens.boundsPen import BoundsPen
                pen=SVGPathPen(face['glyphs']); glyph.draw(pen); d=pen.getCommands()
                bp=BoundsPen(face['glyphs']); glyph.draw(bp); bounds=bp.bounds
                if not d or not bounds: continue
                xmin,ymin,xmax,ymax=bounds; w=max(1.0,xmax-xmin); hh=max(1.0,ymax-ymin); pad=max(w,hh)*.055
                vb=(xmin-pad,-ymax-pad,w+2*pad,hh+2*pad)
                return ('<svg class="hanamin-glyph" xmlns="http://www.w3.org/2000/svg" '
                        'viewBox="%.3f %.3f %.3f %.3f" role="img" aria-label="%s">'
                        '<g transform="scale(1,-1)"><path d="%s"/></g></svg>')%(vb[0],vb[1],vb[2],vb[3],h(ch),h(d))
            except Exception:
                continue
        self.missing_unicode.add(ch); return None

    def _glyphwiki_img(self,key):
        rec=self.gw.get(key)
        if not rec:return None
        f,info=rec
        try:
            body=f.read_bytes(); b64=base64.b64encode(body).decode('ascii')
            self.stats['glyphwiki']+=1
            return '<img class="glyphwiki-glyph" src="data:image/svg+xml;base64,'+b64+'" alt="'+h(key)+'">'
        except Exception:return None

    def render(self,key,meta=None):
        meta=meta or {}; ck=(str(key),str(meta.get('render_type') or ''),str(meta.get('render_value') or ''))
        if ck in self.cache:return self.cache[ck]
        key=str(key or ''); rt=str(meta.get('render_type') or '')
        out=None
        # Exact named entity takes precedence because it can preserve a CHISE/GT/MJ variant.
        if key.startswith('&') and key.endswith(';'):
            out=self._glyphwiki_img(key)
            if not out:
                ch=self.gw_unicode.get(key) or self.entity_unicode(key)
                if ch:
                    out=self._font_svg(ch)
                    if out:self.stats['hanamin_entity_unicode']+=1
            if not out:
                self.missing_entities.add(key)
                label=key[1:-1]
                out='<span class="comp-entity-code">'+h(label)+'</span>'
                self.stats['entity_code_fallback']+=1
        elif len(key)==1 and ord(key)>=0x20000:
            out=self._font_svg(key)
            if out:
                self.stats['hanamin_unicode']+=1
                self.missing_unicode.discard(key)
            else:
                out=self._glyphwiki_img(key)
                if out:
                    self.stats['glyphwiki_unicode_fallback']+=1
                    self.missing_unicode.discard(key)
        elif rt=='glyphwiki_svg':
            out=self._glyphwiki_img(key)
        self.cache[ck]=out
        return out

    def report(self):
        return {
            'strategy':'HanaMin SVG outlines for rare Unicode; embedded GlyphWiki SVG for named entities; KanjiVG only for stroke order',
            'hanamin_unicode':self.stats['hanamin_unicode'],
            'hanamin_entity_unicode':self.stats['hanamin_entity_unicode'],
            'glyphwiki':self.stats['glyphwiki'],
            'glyphwiki_unicode_fallback':self.stats['glyphwiki_unicode_fallback'],
            'entity_code_fallback':self.stats['entity_code_fallback'],
            'missing_entities':sorted(self.missing_entities),
            'missing_unicode':sorted(self.missing_unicode),
        }

def glyph_html(key, meta, renderer=None):
    if renderer:
        got=renderer.render(key,meta)
        if got:return got
    rt=str(meta.get('render_type','') or '')
    rv=str(meta.get('render_value','') or '')
    # Never runtime-fetch GlyphWiki or KanjiVG from learner cards. If the build-time
    # cache/font is unavailable, show a readable entity code instead of a broken image.
    if key.startswith('&') and key.endswith(';'):
        return '<span class="comp-entity-code">'+h(key[1:-1])+'</span>'
    return h(key)

def normalize_repo_row(r, mnemonics):
    ch = str(r.get('kanji', ''))
    return {
        'kanji': ch,
        'repo_id': r.get('id', ''),
        'repo_index': r.get('index', ''),
        'repo_page': r.get('page', ''),
        'han_viet': r.get('hanViet', ''),
        'meaning_vi': r.get('meaning', ''),
        'on_reading': r.get('on', ''),
        'kun_reading': r.get('kun', ''),
        'kun_words_jmdict': r.get('kunWords', ''),
        'furigana': r.get('furigana', ''),
        'mnemonic_vi': mnemonics.get(ch, ''),
        '_repo_components': r.get('components') or [],
    }


def _existing_component_index(row):
    out = {}

    def visit(node):
        if not isinstance(node, dict):
            return
        key = str(node.get('component') or node.get('display') or node.get('renderValue') or '')
        if key and key not in out:
            out[key] = node
        for child in node.get('children') or []:
            visit(child)

    for node in (row or {}).get('_repo_components') or []:
        visit(node)
    return out


def _decomp_meta(identity, learner_decomp, existing=None):
    existing = existing or {}
    raw = dict((learner_decomp.get('meta') or {}).get(identity, {}) or {})
    manual = MANUAL_COMP.get(identity, {}) or {}
    return {
        'render_type': raw.get('renderType') or existing.get('renderType') or existing.get('render_type') or 'unicode',
        'render_value': raw.get('renderValue') or existing.get('renderValue') or existing.get('render_value') or raw.get('display') or identity,
        'glyphwiki_name': raw.get('glyphwikiName') or existing.get('glyphwikiName') or existing.get('glyphwiki_name') or '',
        'han_viet': raw.get('hanViet') or existing.get('hanViet') or existing.get('han_viet') or manual.get('han_viet') or '',
        'meaning_vi': raw.get('meaning') or existing.get('meaning') or existing.get('meaning_vi') or manual.get('meaning_vi') or '',
        'mnemonic_vi': raw.get('mnemonic') or manual.get('mnemonic_vi') or '',
        'display': raw.get('display') or existing.get('display') or identity,
        'family': raw.get('family') or '',
        'source_identity': raw.get('sourceIdentity') or identity,
    }


def _component_tree(identity, learner_decomp, existing_by_key, path=()):
    existing = existing_by_key.get(identity, {}) or {}
    meta = _decomp_meta(identity, learner_decomp, existing)
    cycle = identity in path
    children = [] if cycle else list((learner_decomp.get('decomp') or {}).get(identity, []) or [])
    return {
        'key': identity,
        'han_viet': meta.get('han_viet', ''),
        'meaning': meta.get('meaning_vi', ''),
        'mnemonic': meta.get('mnemonic_vi', ''),
        'position': existing.get('position') or '',
        'position_vi': existing.get('positionVi') or existing.get('position_vi') or '',
        'role': existing.get('role') or 'visual_only',
        'meta': meta,
        'children': [_component_tree(str(ch), learner_decomp, existing_by_key, path + (identity,)) for ch in children],
    }


def component_entries(ch, learner_decomp, row=None):
    roots = (learner_decomp.get('roots') or {}).get(ch)
    if not isinstance(roots, list) or not roots:
        return []
    existing = _existing_component_index(row or {})
    return [_component_tree(str(identity), learner_decomp, existing) for identity in roots]


def _recursive_child_html(child, glyph_renderer, depth=2):
    title = cap_hv(child.get('han_viet')) if child.get('han_viet') else '—'
    pos = child.get('position_vi') or POS_VI.get(child.get('position', ''), str(child.get('position') or 'thành phần'))
    role = ROLE_VI.get(child.get('role'), str(child.get('role') or 'thành phần hình thể'))
    attr_key = html.escape(str(child.get('key') or ''), quote=True)
    nested = _recursive_block_html(child, child.get('children') or [], glyph_renderer, depth + 1) if child.get('children') else ''
    mnemonic = child.get('mnemonic') or '—'
    return (
        '<article class="comp-recursive-child" data-recursive-child="' + attr_key + '">'
        '<div class="comp-recursive-child-head"><div class="comp-glyph">' + glyph_html(child['key'], child['meta'], glyph_renderer) + '</div>'
        '<div class="comp-recursive-copy"><strong>' + h(title) + '</strong><span>' + h(child.get('meaning') or '—') + '</span><small>' + h(pos) + '</small><small class="comp-recursive-role">' + h(role) + '</small></div></div>'
        '<div class="comp-recursive-mn"><span class="mini-label">Mẹo nhớ</span><br>' + h(mnemonic) + '</div>'
        + nested + '</article>'
    )


def _recursive_block_html(parent, children, glyph_renderer, depth=2):
    if not children:
        return ''
    root_key = str(parent.get('key') or '')
    attr_root = html.escape(root_key, quote=True)
    child_html = ''.join(_recursive_child_html(child, glyph_renderer, depth) for child in children)
    return (
        '<details class="comp-recursive" data-recursive-depth="' + str(depth) + '" data-recursive-root="' + attr_root + '">'
        '<summary class="comp-recursive-summary"><span class="comp-recursive-summary-title">Cấu tạo của <b>' + h(root_key) + '</b></span>'
        '<span class="comp-recursive-summary-side"><span>' + str(len(children)) + ' phần</span><span class="comp-recursive-chevron" aria-hidden="true"><svg viewBox="0 0 16 16" focusable="false" aria-hidden="true"><path d="M3 5.5L8 10.5L13 5.5"/></svg></span></span></summary>'
        '<div class="comp-recursive-body"><div class="comp-recursive-grid">' + child_html + '</div></div></details>'
    )


def components_html(ch, learner_decomp, row=None, glyph_renderer=None):
    items = component_entries(ch, learner_decomp, row)
    if not items:
        return '<div class="comp-empty">Không tách thành phần ở mức học hiện tại.</div>'
    cards = []
    for item in items:
        title = cap_hv(item.get('han_viet')) if item.get('han_viet') else '—'
        pos = item.get('position_vi') or POS_VI.get(item.get('position', ''), str(item.get('position') or 'thành phần hình thể'))
        role = ROLE_VI.get(item.get('role'), str(item.get('role') or 'thành phần hình thể'))
        recursive = _recursive_block_html(item, item.get('children') or [], glyph_renderer, 2)
        cards.append(
            '<div class="comp-card" data-component="' + html.escape(str(item.get('key') or ''), quote=True) + '">'
            '<div class="comp-head"><div class="comp-glyph">' + glyph_html(item['key'], item['meta'], glyph_renderer) + '</div>'
            '<div><div class="comp-name">' + h(title) + '</div><div class="comp-meta">' + h(pos) + '</div><div class="comp-role">' + h(role) + '</div></div></div>'
            '<div class="comp-box"><span class="mini-label">Nghĩa</span><br>' + h(item.get('meaning') or '—') + '</div>'
            '<div class="comp-box mn"><span class="mini-label">Mẹo nhớ</span><br>' + h(item.get('mnemonic') or '—') + '</div>'
            + recursive + '</div>'
        )
    rendered = ''.join(cards)
    regressions = {
        '調': ('data-component="言"', 'data-component="周"', 'data-recursive-root="周"', 'data-recursive-child="用"', 'data-recursive-child="口"'),
        '三': ('data-component="一"', 'data-component="𠄞"', 'data-recursive-root="𠄞"'),
    }
    if ch in regressions:
        missing = [marker for marker in regressions[ch] if marker not in rendered]
        if missing:
            raise RuntimeError(ch + ' learner decomposition QA failed: ' + ', '.join(missing))
    return rendered

VARIANT_FALLBACK={
    '牜':('07292.svg','牛','true'),
    '⺮':('07b86-Kaisho.svg','竹','true'),
    '⺶':('07f9a.svg','⺶',None),
    '覀':('05ad6.svg','覀',None),
}

def parse_variant_stroke_data(kvg_dir,ch):
    spec=VARIANT_FALLBACK.get(ch)
    if not spec:return None,None
    host,element,variant=spec; sp=find_svg(kvg_dir,host)
    if not sp:return None,None
    try:
        import xml.etree.ElementTree as ET
        root=ET.parse(sp).getroot(); svg_ns='{http://www.w3.org/2000/svg}'; kvg_ns='{http://kanjivg.tagaini.net}'
        for g in root.iter(svg_ns+'g'):
            if g.attrib.get(kvg_ns+'element')!=element:continue
            if variant is not None and g.attrib.get(kvg_ns+'variant')!=variant:continue
            found=[]
            for p in g.iter(svg_ns+'path'):
                d=p.attrib.get('d'); sid=p.attrib.get('id',''); sm=re.search(r'-s(\d+)$',sid)
                if d:found.append((int(sm.group(1)) if sm else len(found)+1,d))
            if found:
                found.sort(key=lambda z:z[0]); return {'p':[d for _,d in found],'n':[None]*len(found),'z':1},host
    except Exception: pass
    return None,None

def load_stroke_counts(path):
    if not path:return {}
    try:
        with gzip.open(path,'rt',encoding='utf-8') as f: arr=json.load(f)
        return {x.get('c'):int(x.get('str') or 0) for x in arr if x.get('c')}
    except Exception:return {}

def parse_stroke_data(svg_text):
    ordered=[]
    for m in re.finditer(r'<path\b([^>]*)>',svg_text,flags=re.I|re.S):
        attrs=m.group(1); iid=re.search(r'\bid=["\']([^"\']+)["\']',attrs,re.I); dd=re.search(r'\bd=["\']([^"\']+)["\']',attrs,re.I|re.S)
        if not dd: continue
        sid=iid.group(1) if iid else ''
        sm=re.search(r'-s(\d+)$',sid)
        if sm: ordered.append((int(sm.group(1)),html.unescape(dd.group(1))))
    ordered.sort(key=lambda x:x[0]); paths=[d for _,d in ordered]
    nums={}
    for m in re.finditer(r'<text\b([^>]*)>(\s*\d+\s*)</text>',svg_text,flags=re.I|re.S):
        attrs=m.group(1); num=int(m.group(2).strip()); x=y=None
        tr=re.search(r'\btransform=["\']([^"\']+)["\']',attrs,re.I)
        if tr:
            mm=re.search(r'matrix\([^)]*?([+-]?(?:\d+(?:\.\d*)?|\.\d+))[, ]+([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\)$',tr.group(1).strip())
            if mm: x=float(mm.group(1)); y=float(mm.group(2))
            else:
                tt=re.search(r'translate\(\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))[, ]+([+-]?(?:\d+(?:\.\d*)?|\.\d+))',tr.group(1))
                if tt: x=float(tt.group(1)); y=float(tt.group(2))
        if x is None:
            xm=re.search(r'\bx=["\']([+-]?(?:\d+(?:\.\d*)?|\.\d+))["\']',attrs,re.I); ym=re.search(r'\by=["\']([+-]?(?:\d+(?:\.\d*)?|\.\d+))["\']',attrs,re.I)
            if xm and ym: x=float(xm.group(1)); y=float(ym.group(1))
        if x is not None: nums[num]=[round(x,2),round(y,2)]
    positions=[nums.get(i+1) for i in range(len(paths))]
    return {'p':paths,'n':positions}


def stroke_svg_html(sd):
    paths=sd.get('p') or []; nums=sd.get('n') or []
    if not paths:return '<div class="comp-empty">Không có dữ liệu nét.</div>'
    norm_attr=' data-normalize="1"' if sd.get('z') else ''
    out=['<svg class="kvg-inline"'+norm_attr+' xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" role="img">',
         '<rect x="0" y="0" width="109" height="109" fill="#13243a"/>',
         '<g class="kvg-grid" fill="none" stroke="#60738c" stroke-width=".65" stroke-dasharray="4 3" stroke-opacity=".72">',
         '<line x1="0" y1="54.5" x2="109" y2="54.5"/><line x1="54.5" y1="0" x2="54.5" y2="109"/></g>',
         '<g class="kvg-strokes" fill="none" stroke-width="4.3" stroke-linecap="round" stroke-linejoin="round">']
    for i,d in enumerate(paths,1):
        out.append(f'<path class="kvg-stroke" data-stroke="{i}" d="{html.escape(d,quote=True)}"/>')
    out.append('</g><g class="kvg-numbers" font-size="7.2" font-weight="800" text-anchor="middle" stroke="#13243a" stroke-width="2.2" paint-order="stroke" stroke-linejoin="round">')
    for i in range(1,len(paths)+1):
        q=nums[i-1] if i-1<len(nums) else None
        if q and len(q)>=2: x,y=q[0],q[1]
        else: x,y=4,10+(i-1)*7
        out.append(f'<text class="kvg-number" data-stroke="{i}" x="{x}" y="{y}">{i}</text>')
    out.append('</g></svg>')
    return ''.join(out)

def find_svg(kvg_dir,filename):
    if not kvg_dir:return None
    p=Path(kvg_dir); candidates=[p/filename,p/'kanji'/filename,p/'main'/filename,p/'min'/'main'/filename,p/'dist'/'min'/'main'/filename,p/'dist'/'orig'/'main'/filename]
    return next((c for c in candidates if c.is_file()),None)

def field_obj(name,ord_):return {'name':name,'ord':ord_,'font':'Arial','media':[],'rtl':False,'size':20,'sticky':False}
def tmpl(name,ord_,qfmt,afmt):return {'name':name,'ord':ord_,'qfmt':qfmt,'afmt':afmt,'bqfmt':'','bafmt':'','bfont':'','bsize':0,'did':None}
def model_json(ts):
    return {'css':CSS,'did':DECK_ROOT,'flds':[field_obj(n,i) for i,n in enumerate(FIELDS)],'id':str(MODEL_ID),'latexPost':'\\end{document}','latexPre':'\\documentclass[12pt]{article}\\begin{document}','latexsvg':False,'mod':ts,'name':'HT Joyo 2136','req':[[0,'all',[0]],[1,'all',[1]],[2,'all',[0,1]]],'sortf':0,'tags':[],'tmpls':[tmpl('01 Kanji → Hán Việt',0,Q_K2HV,A_K2HV),tmpl('02 Hán Việt → Kanji',1,Q_HV2K,A_HV2K),tmpl('03 Viết Kanji',2,Q_WRITE,A_WRITE)],'type':0,'usn':-1,'vers':[]}
def deck_json(did,name,ts,desc=''):return {'collapsed':False,'conf':1,'desc':desc,'dyn':0,'extendNew':0,'extendRev':50,'id':did,'lrnToday':[0,0],'mod':ts,'name':name,'newToday':[0,0],'revToday':[0,0],'timeToday':[0,0],'usn':-1}
def stable_guid(subset,unique_key):
    return hashlib.sha1(('HT-JOYO-2136-REPOORDER|'+subset+'|'+str(unique_key)).encode()).hexdigest()[:12]

def build(kanji_source, mnemonics_source, decomp_source, output, kvg_dir=None, stroke_meta=None, timestamp=None, sc1_source=None, sc2_source=None, hanamin_a=None, hanamin_b=None, glyphwiki_manifest=None):
    master = json.load(open(kanji_source, encoding='utf-8'))
    all_rows = master['kanji']
    mnemonics = json.load(open(mnemonics_source, encoding='utf-8'))
    learner_decomp = json.load(open(decomp_source, encoding='utf-8'))

    if not kvg_dir:
        raise ValueError('This build requires --kanjivg-dir so all stroke data is embedded offline.')
    if len(all_rows) != 2136:
        raise ValueError(f'Expected 2136 kanji, got {len(all_rows)}')
    joyo = [str(r.get('kanji', '')) for r in all_rows]
    if len(set(joyo)) != 2136:
        raise ValueError('Canonical 2136 master contains duplicates.')
    missing_mn = [ch for ch in joyo if not str(mnemonics.get(ch, '')).strip()]
    if missing_mn:
        raise ValueError('Missing centralized mnemonic for: ' + ', '.join(missing_mn[:20]))
    if int(learner_decomp.get('joyoCount') or 0) != 2136:
        raise ValueError('Learner decomposition is not the canonical 2136 dataset.')
    if not sc1_source or not sc2_source:
        raise ValueError('This build requires local HT snapshot sc1/sc2 sources.')

    sc1_raw = json.load(open(sc1_source, encoding='utf-8'))
    sc2_raw = json.load(open(sc2_source, encoding='utf-8'))
    if len(sc1_raw) != 400:
        raise ValueError(f'Expected Sơ cấp 1 = 400 rows, got {len(sc1_raw)}')
    if len(sc2_raw) != 844:
        raise ValueError(f'Expected canonical Sơ cấp 2 = 844 rows (HT800_1→HT800_9), got {len(sc2_raw)}')

    def legacy_mnemonic_paths(value, path=''):
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = path + '/' + str(key)
                if str(key).lower() == 'mnemonic':
                    found.append(child_path)
                found.extend(legacy_mnemonic_paths(child, child_path))
        elif isinstance(value, list):
            for i, child in enumerate(value):
                found.extend(legacy_mnemonic_paths(child, path + '/' + str(i)))
        return found

    for label, rows in [('sc1', sc1_raw), ('sc2', sc2_raw)]:
        stale = legacy_mnemonic_paths(rows)
        if stale:
            raise ValueError(f'{label} snapshot still contains legacy mnemonic fields; run scripts/sync_from_ht.py first.')

    sc1_rows = [normalize_repo_row(r, mnemonics) for r in sc1_raw]
    sc2_rows = [normalize_repo_row(r, mnemonics) for r in sc2_raw]
    all_rows = [dict(r, mnemonic_vi=mnemonics.get(str(r.get('kanji', '')), '')) for r in all_rows]
    missing_course = [r['kanji'] for r in sc1_rows + sc2_rows if not str(r.get('mnemonic_vi', '')).strip()]
    if missing_course:
        raise ValueError('Missing centralized course mnemonic for: ' + ', '.join(missing_course[:20]))

    page_sets = {'sc1': repo_pages(sc1_rows), 'sc2': repo_pages(sc2_rows)}
    counts = load_stroke_counts(stroke_meta)
    glyph_renderer = GlyphRenderer(hanamin_a, hanamin_b, glyphwiki_manifest)
    subsets = [('sc1', sc1_rows), ('sc2', sc2_rows), ('all', all_rows)]
    hv_counts = {k: collections.Counter(str(r.get('han_viet', '')).strip().lower() for r in rows) for k, rows in subsets}

    ts = int(timestamp or time.time())
    dbpath = Path(str(output) + '.collection.anki2')
    if dbpath.exists():
        dbpath.unlink()
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()
    c.executescript(SCHEMA)
    conf = {'activeDecks':[DECK_ROOT],'addToCur':True,'collapseTime':1200,'curDeck':DECK_ROOT,'curModel':str(MODEL_ID),'dueCounts':True,'estTimes':True,'newBury':True,'newSpread':0,'nextPos':1,'sortBackwards':False,'sortType':'noteFld','timeLim':0}
    dconf = {'1':{'autoplay':True,'id':1,'lapse':{'delays':[10],'leechAction':0,'leechFails':8,'minInt':1,'mult':0},'maxTaken':60,'mod':0,'name':'Default','new':{'bury':True,'delays':[1,10],'initialFactor':2500,'ints':[1,4,7],'order':0,'perDay':9999,'separate':True},'replayq':True,'rev':{'bury':True,'ease4':1.3,'fuzz':0.05,'ivlFct':1,'maxIvl':36500,'minSpace':1,'perDay':9999},'timer':0,'usn':0}}
    deck_names = dict(DECK_NAMES)
    for subset in ('sc1', 'sc2'):
        for parent_did in SUBSET_DECKS[subset]:
            for page in page_sets[subset]:
                deck_names[page_deck_id(parent_did, page)] = DECK_NAMES[parent_did] + f'::Trang {page}'
    decks = {str(k): deck_json(k, v, ts, 'Sơ cấp 1 / Sơ cấp 2 dùng snapshot HT sạch: 400 + 844 ô, không chứa mnemonic cũ. Mnemonic và chiết tự dùng nguồn tập trung. All = 2136.' if k == DECK_ROOT else '') for k, v in deck_names.items()}
    models = {str(MODEL_ID): model_json(ts)}
    c.execute('INSERT INTO col VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (1, ts, ts*1000, ts*1000, 11, 0, 0, 0, json.dumps(conf, ensure_ascii=False), json.dumps(models, ensure_ascii=False), json.dumps(decks, ensure_ascii=False), json.dumps(dconf), json.dumps({})))

    base = ts * 1000
    note_seq = 0
    stroke_embedded = 0
    derived_strokes = 0
    missing = []
    for subset, subset_rows in subsets:
        for i, r in enumerate(subset_rows, 1):
            note_seq += 1
            ch = r['kanji']
            hv = cap_hv(r.get('han_viet', ''))
            mean = str(r.get('meaning_vi', '') or '')
            dup = hv_counts[subset][str(r.get('han_viet', '')).strip().lower()] > 1
            disambig = ('Nghĩa: ' + mean) if dup else ''
            filename = kvg_filename(ch)
            b64 = ''
            sd = {'p': [], 'n': []}
            svg_markup = ''
            sp = find_svg(kvg_dir, filename)
            source_filename = filename
            if sp:
                try:
                    sd = parse_stroke_data(sp.read_text(encoding='utf-8'))
                except Exception:
                    sd = {'p': [], 'n': []}
            if not sd.get('p'):
                vsd, vfile = parse_variant_stroke_data(kvg_dir, ch)
                if vsd and vsd.get('p'):
                    sd = vsd
                    source_filename = vfile or filename
                    derived_strokes += 1
            if sd.get('p'):
                b64 = base64.b64encode(json.dumps(sd, ensure_ascii=False, separators=(',', ':')).encode()).decode()
                svg_markup = stroke_svg_html(sd)
                stroke_embedded += 1
            else:
                missing.append({'subset': subset, 'index': i, 'kanji': ch})

            comp_html = components_html(ch, learner_decomp, r if subset in ('sc1', 'sc2') else None, glyph_renderer)
            if subset in ('sc1', 'sc2'):
                unique = r.get('repo_id') or f'{subset}-{i:04d}-{ord(ch):x}'
                tags = ['joyo2136', 'repo_order', 'course::' + subset, 'page::' + str(r.get('repo_page') or '')]
            else:
                unique = f'all-{i:04d}-{ord(ch):x}'
                tags = ['joyo2136', 'repo_order', 'course::all']

            stroke_count = len(sd.get('p', [])) if sd.get('p') else counts.get(ch) or ''
            furigana = anki_furigana(r.get('furigana', ''), ch)
            raw = [ch, hv, mean, r.get('on_reading', ''), r.get('kun_reading', ''), r.get('kun_words_jmdict', ''), furigana, r.get('mnemonic_vi', ''), str(unique), source_filename, b64, svg_markup, disambig, comp_html, str(stroke_count)]
            vals = [str(v or '') if idx in (11, 13) else safe(v) for idx, v in enumerate(raw)]
            flds = '\x1f'.join(vals)
            nid = base + note_seq * 8
            c.execute('INSERT INTO notes VALUES(?,?,?,?,?,?,?,?,?,?,?)', (nid, stable_guid(subset, unique), MODEL_ID, ts, -1, ' ' + ' '.join(t for t in tags if not t.endswith('::')) + ' ', flds, ch, 0, 0, ''))
            for ord_, parent_did in enumerate(SUBSET_DECKS[subset]):
                did = page_deck_id(parent_did, int(r.get('repo_page') or 0)) if subset in ('sc1', 'sc2') else parent_did
                cid = nid + ord_ + 1
                c.execute('INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (cid, nid, did, ord_, ts, -1, 0, 0, i, 0, 0, 0, 0, 0, 0, 0, 0, ''))

    conn.commit()
    conn.close()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(dbpath, 'collection.anki2')
        z.writestr('media', '{}')
    dbpath.unlink()
    return {
        'notes': 3380,
        'cards': 10140,
        'source_schema': 'split-centralized-v1',
        'centralized_mnemonics': len(mnemonics),
        'learner_decomp_roots': len(learner_decomp.get('roots') or {}),
        'subsets': {'sc1': {'label':'Sơ cấp 1','notes':400,'cards':1200}, 'sc2': {'label':'Sơ cấp 2','notes':844,'cards':2532}, 'all': {'notes':2136,'cards':6408}},
        'repo_pages': {'sc1': page_sets['sc1'], 'sc2': page_sets['sc2']},
        'root_deck': ROOT_NAME,
        'repo_order_exact': True,
        'new_card_order': 'added/due sequence',
        'detailed_back_sections': ['Thành phần', 'Thứ tự nét'],
        'formation_field_removed': True,
        'furigana_filter': '{{furigana:Furigana}}',
        'component_glyphs': glyph_renderer.report(),
        'unresolved_entity_kvg_fallback': False,
        'embedded_stroke_records': stroke_embedded,
        'derived_variant_stroke_records': derived_strokes,
        'runtime_kanjivg_fallback': False,
        'offline_stroke_rendering': True,
        'inline_svg_embedded': True,
        'colored_auto_animation': True,
        'missing_embedded_strokes': len(missing),
        'missing': missing,
        'output': str(output),
        'size_bytes': output.stat().st_size,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kanji-source', required=True)
    ap.add_argument('--mnemonics-source', required=True)
    ap.add_argument('--decomp-source', required=True)
    ap.add_argument('--sc1-source', required=True)
    ap.add_argument('--sc2-source', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--kanjivg-dir')
    ap.add_argument('--stroke-meta')
    ap.add_argument('--timestamp', type=int)
    ap.add_argument('--hanamin-a')
    ap.add_argument('--hanamin-b')
    ap.add_argument('--glyphwiki-manifest')
    a = ap.parse_args()
    print(json.dumps(build(a.kanji_source, a.mnemonics_source, a.decomp_source, a.output, a.kanjivg_dir, a.stroke_meta, a.timestamp, a.sc1_source, a.sc2_source, a.hanamin_a, a.hanamin_b, a.glyphwiki_manifest), ensure_ascii=False, indent=2))
if __name__=='__main__':main()
