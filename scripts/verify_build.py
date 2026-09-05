#!/usr/bin/env python3
import argparse, hashlib, html, json, re, shutil, sqlite3, subprocess, tempfile, zipfile
from pathlib import Path

SC1_DID=2084677101
SC2_DID=2084677201
EXPECTED_NOTES=3336
EXPECTED_CARDS=10008
EXPECTED_ROOT='HT Joyo 2136'
EXPECTED_MODEL_ID='2084677010'
EXPECTED_FIELDS=['Kanji','HanViet','Meaning','On','Kun','KunWords','Furigana','Mnemonic','Key','KvgFile','StrokeDataB64','StrokeSVG','Disambiguator','ComponentsHTML','StrokeCount']

def sha_order(chars): return hashlib.sha256(''.join(chars).encode('utf-8')).hexdigest()
def strip_html(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(s or ''))).strip()
# Count only URLs that can actually trigger a runtime network fetch.
# Inline SVG namespaces (for example xmlns="http://www.w3.org/2000/svg")
# are identifiers, not network resources.
REMOTE_RESOURCE_RE = re.compile(
    r'''(?i)(?:\b(?:src|href|xlink:href)\s*=\s*["']https?://|url\(\s*["']?https?://)'''
)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apkg',required=True); ap.add_argument('--sc1',required=True); ap.add_argument('--sc2',required=True)
    ap.add_argument('--builder-report'); ap.add_argument('--output')
    a=ap.parse_args()
    if Path(a.apkg).name!='HT Joyo 2136.apkg': raise SystemExit('APKG filename must stay exactly "HT Joyo 2136.apkg"')
    sc1=[r['kanji'] for r in json.load(open(a.sc1,encoding='utf-8'))]
    sc2=[r['kanji'] for r in json.load(open(a.sc2,encoding='utf-8'))]
    builder=json.load(open(a.builder_report,encoding='utf-8')) if a.builder_report else {}

    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(a.apkg) as z:z.extract('collection.anki2',td)
        con=sqlite3.connect(Path(td)/'collection.anki2'); c=con.cursor()
        models=json.loads(c.execute('select models from col').fetchone()[0]); decks=json.loads(c.execute('select decks from col').fetchone()[0]); model=list(models.values())[0]
        notes=c.execute('select count(*) from notes').fetchone()[0]; cards=c.execute('select count(*) from cards').fetchone()[0]
        def order(did):
            parent_name=decks[str(did)]['name']
            dids=[int(k) for k,d in decks.items() if d.get('name')==parent_name or d.get('name','').startswith(parent_name+'::')]
            marks=','.join('?' for _ in dids)
            rs=c.execute(f'select n.flds,c.due from cards c join notes n on n.id=c.nid where c.did in ({marks}) and c.ord=0 order by c.due',dids).fetchall()
            return [x[0].split('\x1f')[0] for x in rs]
        actual1,actual2=order(SC1_DID),order(SC2_DID)
        fields=[f['name'] for f in model['flds']]; fidx={n:i for i,n in enumerate(fields)}
        rows=c.execute('select tags,flds from notes').fetchall()
        first_vals=next(f for t,f in rows if f.split('\x1f')[0]=='一').split('\x1f'); first=dict(zip(fields,first_vals))
        component_stats={'entity_code_fallbacks':0,'remote_urls':0,'hanamin_svg_notes':0,'glyphwiki_embedded_notes':0}
        examples={}
        if 'ComponentsHTML' in fidx:
            for tags,flds in rows:
                vals=flds.split('\x1f'); comp=vals[fidx['ComponentsHTML']]
                component_stats['entity_code_fallbacks']+=comp.count('comp-entity-code')
                component_stats['remote_urls']+=len(REMOTE_RESOURCE_RE.findall(comp))
                if 'hanamin-glyph' in comp: component_stats['hanamin_svg_notes']+=1
                if 'data:image/svg+xml;base64,' in comp: component_stats['glyphwiki_embedded_notes']+=1
            for target in ('図','卒'):
                arr=[]
                for tags,flds in rows:
                    vals=flds.split('\x1f')
                    if vals[0]==target:
                        comp=vals[fidx['ComponentsHTML']]
                        arr.append({'tags':tags,'has_hanamin':('hanamin-glyph' in comp),'has_glyphwiki':('data:image/svg+xml;base64,' in comp),'has_entity_code':('comp-entity-code' in comp),'text':strip_html(comp)[:600]})
                examples[target]=arr
        con.close()

    js=[]; node=shutil.which('node')
    for tpl in model['tmpls']:
        for side in ('qfmt','afmt'):
            for idx,src in enumerate(re.findall(r'<script>(.*?)</script>',tpl[side],re.S),1):
                if not node: js.append({'template':tpl['name'],'side':side,'script':idx,'ok':None}); continue
                p=subprocess.run([node,'--check'],input=src,text=True,capture_output=True)
                js.append({'template':tpl['name'],'side':side,'script':idx,'ok':p.returncode==0,'stderr':p.stderr.strip()})

    model_text=json.dumps(model,ensure_ascii=False); deck_names=[d.get('name') for d in decks.values()]
    glyph_report=builder.get('component_glyphs') or {}
    result={
      'notes':notes,'cards':cards,'counts_ok':notes==EXPECTED_NOTES and cards==EXPECTED_CARDS,
      'stable_identity':{
        'apkg_filename':Path(a.apkg).name,'root_deck_present':EXPECTED_ROOT in deck_names,
        'model_id':str(model.get('id')),'model_id_ok':str(model.get('id'))==EXPECTED_MODEL_ID,
        'model_name':model.get('name'),'model_name_ok':model.get('name')==EXPECTED_ROOT,
        'no_version_suffix_in_deck_or_model_names':not any(re.search(r'\bv\d+\b',n or '',re.I) for n in deck_names+[model.get('name') or ''])},
      'repo_order':{'sc1_exact_match':actual1==sc1,'sc2_exact_match':actual2==sc2,'sc1_count':len(actual1),'sc2_count':len(actual2),'sc1_sha256':sha_order(actual1),'sc2_sha256':sha_order(actual2)},
      'fields':{'field_names':fields,'exact_current_schema':fields==EXPECTED_FIELDS,'formation_field_removed':'FormationHTML' not in fields,'native_furigana_filter':'{{furigana:Furigana}}' in model_text},
      'fronts':{'reverse_meaning_visible':'Nghĩa: {{Meaning}}' in model['tmpls'][1]['qfmt'],'writing_meaning_visible':'Nghĩa: {{Meaning}}' in model['tmpls'][2]['qfmt']},
      'writer':{'embedded_stroke_data_present':bool(first.get('StrokeDataB64')),'auto_flip_bridge':'ankitap' in model_text,'tappable_writer':'tappable' in model['tmpls'][2]['qfmt'],'stable_pointer_capture':'setPointerCapture' in model_text,'lost_pointer_recovery':'lostpointercapture' in model_text,'flip_fix':'Bạn đã lật sớm' in model_text},
      'components':{
        'strategy':glyph_report.get('strategy'),
        'kanjivg_used_for_unresolved_components':bool(builder.get('unresolved_entity_kvg_fallback')),
        'entity_code_fallback_count':component_stats['entity_code_fallbacks'],
        'runtime_component_url_count':component_stats['remote_urls'],
        'hanamin_svg_notes':component_stats['hanamin_svg_notes'],
        'glyphwiki_embedded_notes':component_stats['glyphwiki_embedded_notes'],
        'builder_missing_entities':glyph_report.get('missing_entities',[]),
        'builder_missing_unicode':glyph_report.get('missing_unicode',[]),
        'examples':examples,
      },
      'js_syntax':{'node_available':bool(node),'checked':len(js),'all_ok':all(x['ok'] is not False for x in js),'details':js},
      'back_sections':{'Thành phần':'Thành phần' in model_text,'Thứ tự nét':'Thứ tự nét' in model_text,'Nguồn gốc cấu tạo removed':'Nguồn gốc cấu tạo' not in model_text},
    }
    fig_ok=bool(examples.get('図')) and all(x['has_glyphwiki'] and not x['has_entity_code'] for x in examples['図'])
    sotsu_ok=bool(examples.get('卒')) and all((x['has_hanamin'] or x['has_glyphwiki']) and not x['has_entity_code'] for x in examples['卒'])
    result['components']['図_exact_glyph_render_ok']=fig_ok
    result['components']['卒_rare_glyph_render_ok']=sotsu_ok
    ok=(result['counts_ok'] and result['stable_identity']['root_deck_present'] and result['stable_identity']['model_id_ok'] and result['stable_identity']['model_name_ok'] and result['stable_identity']['no_version_suffix_in_deck_or_model_names'] and result['repo_order']['sc1_exact_match'] and result['repo_order']['sc2_exact_match'] and result['fields']['exact_current_schema'] and result['fields']['formation_field_removed'] and result['fields']['native_furigana_filter'] and result['fronts']['reverse_meaning_visible'] and result['fronts']['writing_meaning_visible'] and result['writer']['embedded_stroke_data_present'] and result['writer']['auto_flip_bridge'] and result['writer']['stable_pointer_capture'] and result['writer']['lost_pointer_recovery'] and result['writer']['flip_fix'] and not result['components']['kanjivg_used_for_unresolved_components'] and result['components']['entity_code_fallback_count']==0 and result['components']['runtime_component_url_count']==0 and not result['components']['builder_missing_entities'] and not result['components']['builder_missing_unicode'] and fig_ok and sotsu_ok and result['js_syntax']['all_ok'] and all(result['back_sections'].values()))
    result['ok']=ok
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:Path(a.output).write_text(text,encoding='utf-8')
    else:print(text)
    raise SystemExit(0 if ok else 1)
if __name__=='__main__':main()
