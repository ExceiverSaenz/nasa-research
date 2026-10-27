"""Canonical responsive inspection, extending immutable reading viewer templates."""
import html
import json
import shutil
from pathlib import Path
from reading_order.export import digest,write


def build_view(path,destination):
    path=Path(path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    reading=json.loads(path.read_text(encoding='utf-8'));baseline=json.loads((path.parent/'baseline-docling.json').read_text(encoding='utf-8'));ref=reading['reconciliation_source']
    if digest(ref['path'])!=ref['sha256']:raise ValueError('view source changed')
    rec=json.loads(Path(ref['path']).read_text(encoding='utf-8'));pages=[];images=[];source_images={}
    for p in rec['pages']:
        i=p['identity'];image=Path(p['render_path']);sha=digest(image)
        if sha!=i['render_sha256']:raise ValueError('render changed')
        rel=f"images/{i['physical_page']:04d}.png";pages.append(dict(n=i['physical_page'],w=i['width_px'],h=i['height_px'],image=rel));images.append((image,rel,sha));source_images[str(image)]=sha
    units=[]
    for i in reading['inventory']:
        u=i['original_unit'];units.append(dict(id=i['unit_ref'],page=i['page'],kind=i['kind'],bbox=u.get('bbox_xyxy'),text=u.get('original_record',{}).get('text',''),classification=u['classification'],disposition=i['disposition'],appearance_ref=i['appearance_ref'],parent_step_ref=i.get('parent_step_ref')))
    model=dict(document=Path(reading['document']).name,pages=pages,units=units,steps=reading['steps'],routes=reading['routes'],relations=reading['relations'],metrics=reading['metrics'],structure=reading['structure'],semantics={s['unit_ref']:s for s in reading['operational_semantics']},native_links={s['unit_ref']:s for s in reading['native_links']},baseline={k:baseline[k] for k in ('steps','routes','relations')})
    here=Path(__file__).parent;old=here.parent/'reading_order';template=(old/'viewer.html').read_text(encoding='utf-8');js=(old/'viewer.js').read_text(encoding='utf-8');token=' render();\n})();'
    if token not in js:raise ValueError('immutable viewer extension anchor changed')
    js=js.replace(token,(here/'viewer_extra.js').read_text(encoding='utf-8')+'\n'+token).replace('let page=data.pages.some(p=>p.n===3)?3:data.pages[0].n','let page=data.pages[0].n').replace('`12.pdf · página','`${data.document} · página')
    template=template.replace('12.pdf',html.escape(model['document'])).replace('<div class="navigation">','<label>Versión <select id="order-mode"><option value="operational">Operativa</option><option value="baseline">Docling baseline</option></select></label><div class="navigation">').replace('<aside>','<aside><details open><summary>Estructura propuesta del paper</summary><div id="sections-tree"></div></details><p><a href="../document.json">JSON canónico</a> · <a href="../review-queue.json">Advertencias</a></p>')
    css=(old/'viewer.css').read_text(encoding='utf-8')+'\n#sections-tree{max-height:250px;overflow:auto}#sections-tree button{display:block;width:100%;text-align:left;margin:4px 0;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto;font-size:12px}'
    template=template.replace('__CSS__',css).replace('__JS__',js).replace('__DATA__',json.dumps(model,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
    dest.mkdir(parents=True,exist_ok=False)
    for image,rel,sha in images:
        target=dest/rel;target.parent.mkdir(exist_ok=True);shutil.copyfile(image,target)
        if digest(target)!=sha:raise ValueError('image bytes changed')
    (dest/'index.html').write_text(template,encoding='utf-8')
    result=dict(pages=len(pages),source_images=source_images,render_copies={rel:sha for _,rel,sha in images},image_recompression=False,source_sha256=digest(path),html_sha256=digest(dest/'index.html'),visual_QA=False)
    write(dest/'verification.json',result);return result


def build_index(summary,path):
    rows=[]
    for d in sorted(summary['documents'],key=lambda x:x['paper']):
        m=d['metrics'];rows.append('<tr>'+f'<td><a href="{d["view"]}">{d["paper"]}.pdf</a> · <a href="{d["data"]}">JSON</a></td>'+''.join(f'<td>{m[k]}</td>' for k in ('pages','inventory_units','sections','sections_with_parent','sections_unknown_level','deferred_children','changed_content_positions_vs_Docling'))+'</tr>')
    text='<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Parsing operativo · colección</title><style>body{font:16px/1.5 system-ui;margin:24px;color:#193047}table{border-collapse:collapse;min-width:800px}td,th{border:1px solid #ccd5df;padding:9px;text-align:left}.scroll{overflow:auto}a{color:#16599a}</style><h1>Parsing operativo automatizado</h1><p>'+str(summary['papers'])+' papers · misma configuración · originales conservados. Sin OCR ni modelos neuronales.</p><p>Advertencias y revisión humana al final del MVP. Cobertura y cambios de recorrido no son exactitud.</p><p><a href="summary.json">Métricas completas</a> · <a href="review-queue.json">Cola de revisión</a> · <a href="manifest.json">Procedencia y hashes</a></p><div class="scroll"><table><tr><th>Paper / datos</th><th>Páginas</th><th>Unidades</th><th>Secciones propuestas</th><th>Con padre</th><th>Nivel desconocido</th><th>Hijos diferidos</th><th>Posiciones distintas de Docling</th></tr>'+''.join(rows)+'</table></div></html>'
    Path(path).write_text(text,encoding='utf-8')
