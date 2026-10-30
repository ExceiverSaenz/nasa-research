"""Versioned native ZIP -> canonical-v1 input adapter. No reconciliation/model calls."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

from .engine import PARSERS, valid_box
from .inputs import text, digest

VERSION='consolidated-native-input/1'
SUPPORTED={
    'layoutlmv3':{'torch':'1.10.0+cu111','transformers':'4.12.5','detectron2':'0.6+cu111'},
    'table_transformer':{'torch':'2.5.1+cu121','transformers':'4.49.0'},
    'mineru':{'mineru':'4.0.12','docvortex':'0.6.0','torch':'2.7.1+cu126'}}
CONTAINERS={'image','table','chart','code','list','index'}


def file_digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):result.update(block)
    return result.hexdigest()


def require(condition,message):
    if not condition:raise ValueError(message)


def safe_member(name):
    path=PurePosixPath(name)
    require(bool(name) and not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and ':' not in name and not name.endswith('/'),
            'Unsafe archive member: '+name)


def encoded(value):
    # Preserve native nonfinite floats if ever supplied; engine abstains on their geometry.
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def canonical_page(identity,native,lm,tatr,derived,statuses,sources,render):
    """Read raw MinerU normalized boxes once; external native boxes already use pixels."""
    key=identity['document_sha256'];number=identity['physical_page']
    w,h=identity['width_px'],identity['height_px'];incidents=[];records=[]
    require(native.get('schema')=='docvortex.middle' and native.get('schema_version')=='2.0'
            and native.get('metadata',{}).get('producer')=={'name':'mineru','version':'4.0.12'},'Unsupported native MinerU format/version')
    require(len(native.get('pages',[]))==1 and native['pages'][0].get('page_idx')==0,'MinerU source must contain one image page indexed zero')
    require(lm.get('document_id')==key and lm.get('page')==number
            and lm.get('coordinate_system')==identity['geometry'],'LayoutLMv3 identity/geometry mismatch')
    require(tatr.get('coordinate_system')==identity,'TATR identity/geometry mismatch')
    coord=derived['coordinate_system']
    require((coord.get('width_px'),coord.get('height_px'),coord.get('unit'),coord.get('origin'),coord.get('bbox_format'),coord.get('native_bbox'))==
            (w,h,'pixel','top-left','xyxy','normalized [0,1]'),'Unknown MinerU coordinate transform')
    exported={r['source_pointer']:r for r in derived['regions']}
    require(len(exported)==len(derived['regions']),'Duplicate MinerU source pointer')
    seen=set();prefix=key+':p'+str(number)+':'
    def visit(node,pointer,parent=None):
        require(isinstance(node,dict),'Malformed MinerU node at '+pointer)
        kind=node.get('type','unknown');box=node.get('bbox')
        numeric=isinstance(box,list) and len(box)==4 and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in box)
        pixels=[v*s for v,s in zip(box,[w,h,w,h])] if numeric else None
        require(pointer in exported,'Missing native/derived pointer '+pointer)
        saved=exported[pointer];seen.add(pointer)
        require(saved.get('bbox_normalized')==box and saved.get('bbox')==pixels,'MinerU transform differs from preserved export at '+pointer)
        identifier=prefix+'mineru:'+pointer;container=kind in CONTAINERS
        records.append(dict(id=identifier,parser='mineru',native_type=kind,native_bbox=box,bbox=pixels,
            parent=parent,role='container' if container else 'segment',native=node,text='' if container else text(node),
            level=node.get('level'),source=dict(**sources['mineru'],pointer=pointer),transform=[w,0,0,h,0,0]))
        if container:
            children=node.get('content',[])
            if not isinstance(children,list):incidents.append('malformed_container');return
            for index,child in enumerate(children):visit(child,pointer+'/content/'+str(index),identifier)
    for index,node in enumerate(native['pages'][0].get('blocks',[])):visit(node,'/pages/0/blocks/'+str(index))
    require(seen==set(exported),'Unaccounted MinerU derived records')
    for model,data in [('layoutlmv3',lm),('table_transformer',tatr)]:
        require(isinstance(data.get('regions'),list),'Missing external native regions')
        for index,node in enumerate(data['regions']):
            pointer='/regions/'+str(index)
            records.append(dict(id=prefix+model+':'+pointer,parser=model,
                native_type=node.get('type',node.get('native_label','unknown')),bbox=node.get('bbox'),native_bbox=node.get('bbox'),
                parent=None,role='segment',native=node,text='',score=node.get('score'),
                source=dict(**sources[model],pointer=pointer),transform=[1,0,0,1,0,0]))
    if any(not valid_box(r['bbox'],w,h) for r in records):incidents.append('invalid_geometry')
    return dict(identity=identity,records=records,adapter='canonical-v1',incidents=sorted(set(incidents)),
                parsers=statuses,missing_sources=[],render_path=str(render))


def prepare(archive,destination,sidecar=None):
    """Materialize verified raw sources and inputs only. Refuses any existing destination."""
    archive=Path(archive).resolve();destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('New destination required; existing inputs retained')
    sidecar=Path(sidecar) if sidecar is not None else archive.with_suffix('.sha256')
    archive_sha=file_digest(archive)
    require(archive_sha==sidecar.read_text(encoding='ascii').strip(),'Archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();require(len(names)==len(set(names)),'Duplicate ZIP members')
        for name in names:safe_member(name)
        file_manifest=json.loads(z.read('files-manifest.json'))
        require(file_manifest.get('schema')=='archive-member-sha256/1' and file_manifest.get('excludes_self') is True,'Unknown file manifest')
        files=file_manifest['files'];require(set(names)==set(files)|{'files-manifest.json'},'ZIP/member manifest mismatch')
        all_sources={};current_sources={}
        def asset(name,attempt=None):
            safe_member(name);require(name in files,'Missing manifest source '+name)
            raw=z.read(name);expected=files[name]
            require(len(raw)==expected['bytes'] and digest(raw)==expected['sha256'],'Source integrity: '+name)
            if attempt is not None:require((expected.get('source') or {}).get('attempt_id')==attempt,'Parser attempt mismatch: '+name)
            path=destination/'sources'/name
            if not path.exists():
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as stream:stream.write(raw)
            all_sources[str(path)]=expected['sha256'];current_sources[str(path)]=expected['sha256']
            return raw,dict(path=str(path),sha256=expected['sha256'])
        def load(name,attempt=None):
            raw,source=asset(name,attempt);return json.loads(raw),source
        header,_=load('manifest.json')
        require(header.get('schema')=='sic-native-archive-consolidation/1','Unsupported consolidated ZIP schema')
        selection=header['selection'];require(set(selection)==set(PARSERS),'Unexpected parser selection')
        require(all(re.fullmatch('[0-9a-f]{32}',str(x)) for x in selection.values()),'Invalid attempt ID')
        require(selection['layoutlmv3']==selection['table_transformer'] and selection['mineru']!=selection['layoutlmv3'],'Unsupported attempt selection')
        original='provenance/attempts/'+selection['layoutlmv3']+'/'
        config,_=load(original+'plan.json');profile,_=load(original+'execution-profile.json')
        for model,packages in SUPPORTED.items():
            actual=config['models'].get(model,{}).get('packages',{})
            require(all(actual.get(k)==v for k,v in packages.items()),'Unsupported parser configuration: '+model)
        index,_=load('index.json')
        require(len(index)==header['documents'] and len(index)>0,'Document count mismatch')
        require(sum(e['pages'] for e in index)==header['physical_pages'],'Page count mismatch')
        require(header['successful_page_parser_results']==header['physical_pages']*3,'Parser result count mismatch')
        keys=[e['document_sha256'] for e in index]
        require(len(keys)==len(set(keys)) and all(re.fullmatch('[0-9a-f]{64}',x) for x in keys),'Duplicate/invalid document SHA256')
        plans={e['key']:e['plan'] for e in config['documents']}
        require(set(keys)==set(plans),'Baseline document scope mismatch')
        global_sources=dict(current_sources);documents=[];output_hashes={};record_counts=Counter();page_total=0
        for entry in index:
            current_sources.clear();current_sources.update(global_sources)
            key=entry['document_sha256'];child,cs=load(original+'documents/'+key+'/plan.json')
            require(child==plans[key] and child['document_sha256']==key and child['document']==entry['document'],'Document plan mismatch')
            require(child['models']==config['models'] and child['page_count']==entry['pages'] and child['physical_pages']==list(range(1,entry['pages']+1)) and child['dpi']==200,'Unknown document configuration')
            pages=[]
            for number in child['physical_pages']:
                prefix=f'documents/{key}/pages/{number:04d}/'
                identity,_=load(prefix+'identity.json',selection['layoutlmv3'])
                require(identity.get('document_sha256')==key and identity.get('physical_page')==number and identity.get('dpi')==200,'Physical page identity mismatch')
                require(all(type(identity.get(k)) is int and identity[k]>0 for k in ('width_px','height_px')),'Invalid render size')
                require(identity.get('geometry',{}).get('coordinate_system')=={'unit':'pixel','origin':'top-left','bbox_format':'xyxy'},'Unknown render coordinate system')
                image,render_source=asset(prefix+'render.png',selection['layoutlmv3'])
                require(digest(image)==identity['render_sha256'] and image[:8]==b'\x89PNG\r\n\x1a\n' and
                        struct.unpack('>II',image[16:24])==(identity['width_px'],identity['height_px']),'Render integrity/size mismatch')
                statuses={}
                for model in PARSERS:
                    status,_=load(prefix+model+'/status.json',selection[model])
                    require(status.get('model')==model and status.get('page')==number and status.get('status')=='completed','Selected parser status contradiction')
                    statuses[model]=status['status']
                native,ns=load(prefix+'mineru/middle-native.json',selection['mineru'])
                derived,_=load(prefix+'mineru/regions.json',selection['mineru'])
                lm,ls=load(prefix+'layoutlmv3/regions.json',selection['layoutlmv3'])
                tatr,ts=load(prefix+'table_transformer/regions.json',selection['table_transformer'])
                page=canonical_page(identity,native,lm,tatr,derived,statuses,
                    dict(mineru=ns,layoutlmv3=ls,table_transformer=ts),render_source['path'])
                record_counts.update(r['parser'] for r in page['records']);pages.append(page);page_total+=1
            result=dict(adapter=VERSION,pages=pages,source_inputs=dict(current_sources),
                parser_configuration=config['models'],baseline_execution_profile=profile,
                input_archive=dict(path=str(archive),sha256=archive_sha),
                operation='input adaptation only; no reconciliation or human decisions consumed')
            relative='documents/'+key+'/input.json';raw=encoded(result);path=destination/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(raw)
            output_hashes[relative]=digest(raw)
            documents.append(dict(document=entry['document'],document_sha256=key,pages=len(pages),input=relative,
                records=len([r for p in pages for r in p['records']]),pages_with_incidents=sum(bool(p['incidents']) for p in pages)))
        require(file_digest(archive)==archive_sha,'Archive changed while adapting')
        report=dict(adapter=VERSION,source_archive=str(archive),source_archive_sha256=archive_sha,
            documents=documents,physical_pages=page_total,records_by_parser=dict(record_counts),
            outputs=output_hashes,source_inputs=all_sources,
            no_reconciliation_executed=True,no_models_executed=True,original_results_modified=False,
            reconciliation_rules_modified=False,compatibility='canonical-v1 input contract; not cross-paper scientific validation')
        with (destination/'adaptation-manifest.json').open('xb') as stream:stream.write(encoded(report))
        return report


def load_document(directory,document_sha256):
    """Return one verified document for engine.reconcile(page), without calling it."""
    root=Path(directory).resolve()
    require(bool(re.fullmatch('[0-9a-f]{64}',str(document_sha256))),'Invalid document identity')
    manifest=json.loads((root/'adaptation-manifest.json').read_bytes())
    require(manifest.get('adapter')==VERSION,'Unknown prepared input adapter')
    relative=f'documents/{document_sha256}/input.json'
    require(relative in manifest['outputs'],'Document not declared in prepared input')
    raw=(root/relative).read_bytes();require(digest(raw)==manifest['outputs'][relative],'Prepared input integrity mismatch')
    data=json.loads(raw)
    for name,expected in data['source_inputs'].items():
        path=Path(name).resolve();require(path.is_relative_to(root),'Prepared source escapes input directory')
        require(file_digest(path)==expected,'Prepared source integrity: '+name)
    require(data.get('adapter')==VERSION and all(p['adapter']=='canonical-v1' and p['identity']['document_sha256']==document_sha256 for p in data['pages']),'Prepared canonical identity mismatch')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive');parser.add_argument('destination');parser.add_argument('--sidecar')
    args=parser.parse_args();result=prepare(args.archive,args.destination,args.sidecar)
    print(json.dumps(dict(documents=len(result['documents']),pages=result['physical_pages'],records=result['records_by_parser'],reconciliation_executed=False)))
