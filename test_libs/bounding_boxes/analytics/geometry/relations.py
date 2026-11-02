"""Audit declared caption/parent geometry; never infer a replacement relation."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys
from pathlib import Path
from collections import Counter
from analytics.geometry.run import SOURCE,BASE,readlines,csvout,jsonout,sha
from analytics.geometry.metrics import box_state

def main(out):
    if (out/'caption_parent_geometry.csv').exists():raise RuntimeError('Relation audit exists')
    source=SOURCE/'detections.jsonl';before=sha(source);rows=readlines(source)
    byref={(r['tool'],r['original_ref']):r for r in rows};diagnostics=[]
    for r in rows:
        if r['raw_label'] not in ('image_caption','chart_caption','table_caption','caption'):continue
        ref=r.get('native_parent_ref');parent=byref.get((r['tool'],ref))
        if not ref or not parent or box_state(r.get('bbox_normalized'))!='valid' or box_state(parent.get('bbox_normalized'))!='valid':continue
        c,p=r['bbox_normalized'],parent['bbox_normalized']
        pos='above' if c[3]<=p[1] else 'below' if c[1]>=p[3] else 'overlapping_vertical_extent'
        diagnostics.append(dict(tool=r['tool'],paper_sha256=r['paper_sha256'],page_idx=r['page_idx'],caption_id=r['analysis_uid'],parent_id=parent['analysis_uid'],caption_label=r['raw_label'],parent_label=parent['raw_label'],caption_bbox=c,parent_bbox=p,position=pos,caption_to_parent_width=(c[2]-c[0])/(p[2]-p[0]),meaning='declared_relation_geometry_not_correctness'))
    csvout(out/'caption_parent_geometry.csv',diagnostics)
    counts=Counter((r['tool'],r['caption_label'],r['position']) for r in diagnostics)
    summary=[dict(tool=t,label=l,position=p,count=n) for (t,l,p),n in sorted(counts.items())]
    native=BASE/'raw_results/code/mineru-nativefix-20261101T034122Z/assembled/basic/6/middle.json';nh=sha(native)
    import json
    d=json.loads(native.read_text(encoding='utf-8'));pg=d['pages'][14];caption=pg['blocks'][4]['content'][0]
    case=dict(paper='6.pdf',page_idx=14,tool='basic',native_file=str(native),native_sha256=nh,
              parent_pointer='/pages/14/blocks/4',parent_type=pg['blocks'][4]['type'],parent_bbox=pg['blocks'][4]['bbox'],
              caption_pointer='/pages/14/blocks/4/content/0',caption_bbox=caption['bbox'],caption_text=caption['content'][0]['content'],
              observation='Existing raster shows Figure8 is upper four-panel hoop stress/strain group; declared parent is first lower chart (Figure9 fuel temperature). Agent visual observation, not human review; no replacement relation created.')
    jsonout(out/'caption_parent_diagnostics.json',dict(counts=summary,localized_relations=len(diagnostics),concrete_agent_observation=case))
    assert sha(source)==before and sha(native)==nh
    jsonout(out/'relations_verification.json',dict(inputs={str(source):before,str(native):nh,str(Path(__file__)):sha(__file__)},unchanged=True))
    with (out/'report.md').open('a',encoding='utf-8') as f:
        f.write('''\n\n## 12. Comprobación adicional del caption compartido: un caso concreto\n\nLa inspección del fondo existente de6.pdf,página15 muestra Figure8 (cuatro paneles de deformación/tensión) encima y Figure9 (temperatura/presión/gas/óxido) debajo. En el JSON Basic, el caption deFigure8 es hijo de `/pages/14/blocks/4`, cuya caja es el primer gráfico del grupo inferior deFigure9. Los cuatro gráficos superiores son bloques0–3. Por tanto, en este caso la salida conserva el caption y las imágenes pero la pertenencia declarada no representa el grupo deFigure8. Es una observación visual del agente contrastada con texto/estructura originales; no una revisión humana acumulada ni una regla global.\n\nEsto demuestra por qué el acuerdo de área de la figura y el conteo de padres con caption no bastan para tu definición de precisión. No se crea una asociación por proximidad ni se cambia el original. `caption_parent_diagnostics.json` conserva texto, coordenadas, punteros y hash para revisar este caso. `caption_parent_geometry.csv` describe todas las relaciones caption–padre localizadas (por encima/debajo/solapadas), sin declarar incorrectas las que están por encima: captions de tablas o disposiciones particulares pueden ser válidos.\n''')
    print('Caption relation diagnostics:',len(diagnostics),'localized relations')

if __name__=='__main__':main(Path(sys.argv[1]))
