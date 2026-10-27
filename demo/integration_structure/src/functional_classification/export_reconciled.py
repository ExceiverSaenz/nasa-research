"""Verified append-only collection export. Standard library only, no inference."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from .reconciled import classify_reconciled_document, VERSION, CONFIG


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')


def export_collection(source,destination):
    source=Path(source).resolve(); destination=Path(destination).resolve()
    if destination.exists(): raise FileExistsError(destination)
    if source==destination or source in destination.parents or destination in source.parents:
        raise ValueError('output must be separate from original collection')
    summary=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    protected={str(p):digest(p) for p in source.rglob('*') if p.is_file()}
    documents=[]; identities=set(); papers=set()
    for item in summary['documents']:
        paper=item['paper']
        if not isinstance(paper,int) or isinstance(paper,bool) or paper<1 or paper in papers:
            raise ValueError('paper ids must be unique positive integers')
        papers.add(paper)
        path=(source/item['data']).resolve()
        if source not in path.parents: raise ValueError('document outside collection')
        d=json.loads(path.read_text(encoding='utf-8'))
        if d['document_sha256'] in identities: raise ValueError('duplicate paper identity')
        identities.add(d['document_sha256'])
        for page in d['pages']:
            if page.get('identity',{}).get('document_sha256',d['document_sha256'])!=d['document_sha256']:
                raise ValueError('page document mismatch')
            for r in page['records']:
                s=r.get('source',{}); p=Path(s.get('path',''))
                if not p.is_file() or not s.get('sha256') or not s.get('pointer'):
                    raise ValueError('missing native source provenance')
                if str(p) not in protected: protected[str(p)]=digest(p)
                if protected[str(p)]!=s['sha256']: raise ValueError('native source hash mismatch')
        documents.append((item,d,path))
    # Verify all inputs before creating output; failures leave originals untouched.
    destination.mkdir(parents=True)
    stats=Counter(); categories=Counter(); functions=Counter(); statuses=Counter(); warnings=Counter(); groups=defaultdict(list); outputs=[]
    for item,d,path in documents:
        result=classify_reconciled_document(d)
        originals={r['id']:r for page in d['pages'] for r in page['records'] if r['id'] in set(page['objects']+page['containers'])}
        if len(result['regions'])!=len(originals) or any(r['original_record']!=originals[r['id']] for r in result['regions']):
            raise ValueError('record conservation failed')
        result['source']={'path':str(path),'sha256':protected[str(path)],'pointer':'/'}
        result['validation']['technical_contract']='record_conservation_verified'
        rel=Path('papers')/str(item['paper'])/'document.json'; write(destination/rel,result)
        stats.update(papers=1,pages=len(d['pages']),classified_regions=len(result['regions']),logical_groups=len(result['logical_units']),parser_evidence_records=len(result['evidence_records']),segments=sum(len(p['objects']) for p in d['pages']),containers=sum(len(p['containers']) for p in d['pages']))
        reviewed=0
        for r in result['regions']+result['logical_units']:
            c=r['classification']; categories[c['category']['value'] or 'unresolved']+=1
            functions[c['function']['value'] or 'unresolved']+=1; statuses[c['function']['status']]+=1
            if c['requires_human_validation']: reviewed+=1
            for w in c['warnings']:
                warnings[w['code']]+=1
                groups[w['code']].append(dict(paper_id=result['paper_id'],paper=item['paper'],page=r['page'],region_ref=r['id'],document=str(rel).replace('\\','/')))
        stats['units_with_review_warning']+=reviewed
        outputs.append(dict(paper=item['paper'],paper_id=result['paper_id'],data=rel.as_posix(),classified_regions=len(result['regions']),logical_groups=len(result['logical_units']),parser_evidence_records=len(result['evidence_records']),pages=len(d['pages']),units_with_review_warning=reviewed))
    changed=[p for p,h in protected.items() if digest(p)!=h]
    if changed: raise ValueError('protected inputs changed during export')
    result=dict(schema_version=VERSION,**dict(stats),category_values=dict(categories),function_values=dict(functions),
                function_statuses=dict(statuses),warnings=dict(warnings),documents=outputs,
                semantic_validation='pending_after_full_mvp',reading_order='not_computed',
                human_review_required_now=False,all_reconciled_units_retained=True,classification_scope='reconciled_units_only')
    write(destination/'summary.json',result)
    write(destination/'review-queue.json',dict(message='Requiere validación humana',review_stage='after_full_mvp',groups=dict(groups)))
    write(destination/'manifest.json',dict(version=VERSION,config=CONFIG,source=str(source),protected_inputs=protected,
         verification=dict(protected_files=len(protected),unchanged=True,record_conservation=True),
         outputs={str(p.relative_to(destination)).replace('\\','/'):digest(p) for p in destination.rglob('*.json')}))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination'); args=parser.parse_args()
    result=export_collection(args.source,args.destination)
    print(json.dumps({k:v for k,v in result.items() if k not in ('documents',)},ensure_ascii=False,indent=2))
