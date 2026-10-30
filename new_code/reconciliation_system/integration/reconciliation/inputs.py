"""Versioned adapter for saved document-trial evaluation sources, never decisions."""
import hashlib
import json
from pathlib import Path
from .engine import PARSERS


def digest(raw):return hashlib.sha256(raw).hexdigest()


def text(node):
    if isinstance(node,str):return node
    if isinstance(node,list):return ' '.join(filter(None,(text(x) for x in node)))
    if isinstance(node,dict):
        if node.get('type') in ('chart_body','image_body'):return ''
        return text(node.get('content',''))
    return ''


def load_evaluation(directory):
    root=Path(directory).resolve();sources={}
    def load(relative,expected=None):
        path=(root/relative).resolve()
        if not path.is_relative_to(root):raise ValueError('Source escapes evaluation directory')
        raw=path.read_bytes();sha=digest(raw)
        sources[str(path)]=sha
        if expected is not None and sha!=expected:raise ValueError('Source integrity: '+relative)
        return json.loads(raw)
    manifest=load('evaluation-manifest.json')
    outputs=manifest['outputs']
    config=load('manifest.json',outputs['manifest.json'])
    execution=load('document-status.json',outputs['document-status.json'])
    statuses={p['page']:p['branches'] for p in execution['pages']}
    pages=[]
    supported_packages={'layoutlmv3':{'torch':'1.10.0+cu111','transformers':'4.12.5','detectron2':'0.6+cu111'},
                        'table_transformer':{'torch':'2.5.1+cu121','transformers':'4.49.0'}}
    external_supported=all(all(config['plan']['models'].get(model,{}).get('packages',{}).get(k)==v for k,v in packages.items()) for model,packages in supported_packages.items())
    folders=[f'page-{n:04d}' for n in sorted(config['plan']['physical_pages'])]
    for folder in folders:
        incidents=[];missing=[]
        def source(name):
            relative=folder+'/'+name
            provenance=dict(path=str(root/relative),sha256=outputs.get(relative,''))
            if relative not in outputs or not (root/relative).is_file():
                missing.append(name);return {},provenance
            try:return load(relative,outputs[relative]),provenance
            except (ValueError,OSError):
                incidents.append('source_integrity');return {},provenance
        native,ns=source('M0-native.json');external,es=source('R-reconciled.json');meta,_=source('source-manifest.json')
        identity=meta.get('identity',external.get('identity',dict(document_sha256=config['plan']['document_sha256'],physical_page=int(folder[5:]),width_px=1,height_px=1,render_sha256='')))
        records=[]
        if not meta:incidents.append('identity_mismatch')
        if (external and external.get('identity')!=identity) or identity['document_sha256']!=config['plan']['document_sha256']:
            incidents.append('identity_mismatch')
        render=root/folder/'render.png'
        if render.is_file():
            sources[str(render)]=digest(render.read_bytes())
            if sources[str(render)]!=identity['render_sha256']:incidents.append('source_integrity')
        else:incidents.append('source_integrity')
        if identity.get('geometry',{}).get('coordinate_system')!={'unit':'pixel','origin':'top-left','bbox_format':'xyxy'}:
            incidents.append('unknown_transform')
        supported=(not native or native.get('metadata',{}).get('producer',{})=={'name':'mineru','version':'4.0.12'}) and external_supported
        if not supported:incidents.append('unsupported_adapter')
        valid_native=native and len(native.get('pages',[]))==1 and native['pages'][0].get('page_idx')==0
        if native and not valid_native:incidents.append('identity_mismatch')
        prefix=identity['document_sha256']+':p'+str(identity['physical_page'])+':'
        w,h=identity['width_px'],identity['height_px']
        def visit(node,pointer,parent=None):
            key=prefix+'mineru:'+pointer;kind=node['type'];raw_box=node.get('bbox')
            box=[v*s for v,s in zip(raw_box,[w,h,w,h])] if isinstance(raw_box,list) and len(raw_box)==4 and all(isinstance(v,(int,float)) for v in raw_box) else None
            container=kind in ('table','chart','image','list','index','code')
            records.append(dict(id=key,parser='mineru',native_type=kind,bbox=box,native_bbox=raw_box,
                parent=parent,role='container' if container else 'segment',native=node,text='' if container else text(node),
                level=node.get('level'),source=dict(**ns,pointer=pointer),transform=[w,0,0,h,0,0]))
            if container:
                children=node.get('content',[])
                if not isinstance(children,list):incidents.append('malformed_container');return
                for index,child in enumerate(children):visit(child,pointer+'/content/'+str(index),key)
        for index,node in enumerate(native['pages'][0].get('blocks',[]) if valid_native else []):
            visit(node,'/pages/0/blocks/'+str(index))
        # Only native_record is consumed from R. Its selected segments, groups,
        # statuses and localized enrichment are deliberately not read.
        for index,e in enumerate(external.get('evidence',[])):
            model=e['model'];node=e['native_record'];pointer='/evidence/'+str(index)+'/native_record'
            if model not in PARSERS:incidents.append('unsupported_adapter')
            records.append(dict(id=prefix+model+':'+pointer,parser=model,native_type=node.get('type','unknown'),
                bbox=node.get('bbox'),native_bbox=node.get('bbox'),parent=None,role='segment',native=node,text='',
                score=node.get('score'),source=dict(**es,pointer=pointer),transform=[1,0,0,1,0,0]))
        parser_status={p:statuses.get(identity['physical_page'],{}).get(p,{}).get('status','missing') for p in PARSERS}
        if not native:parser_status['mineru']='missing'
        if not external:
            for p in ('layoutlmv3','table_transformer'):parser_status[p]='missing'
        if missing:incidents.append('missing_source')
        pages.append(dict(identity=identity,records=records,adapter='canonical-v1',incidents=incidents,
                          parsers=parser_status,missing_sources=missing,
                          render_path=str(render)))
    return dict(adapter='evaluation-mineru4.0.12-lm-tatr/1',pages=pages,source_inputs=sources,parser_configuration=config['plan']['models'])
