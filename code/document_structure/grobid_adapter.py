"""Decode saved TEI only. No network, model imports or source writes."""
import hashlib
import math
import xml.etree.ElementTree as ET
from collections import Counter

NS='http://www.tei-c.org/ns/1.0'
LABELS={'title','persName','affiliation','head','p','ref','figure','figDesc','label','graphic','formula','note','biblStruct','abstract','keywords','div','author','funder'}


def parse_tei(raw: bytes,run: dict) -> dict:
    try:text=raw.decode('utf-8-sig')
    except UnicodeError as exc:raise ValueError('TEI must be UTF-8; unsupported encoding') from exc
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('DTD/entities forbidden')
    try:root=ET.fromstring(text)
    except ET.ParseError as exc:raise ValueError('Invalid TEI XML') from exc
    if root.tag!='{'+NS+'}TEI':raise ValueError('Unexpected TEI namespace/root')
    sha=hashlib.sha256(raw).hexdigest();nodes=[];unmapped=[];pages=[];allpaths=[]
    for s in root.iter('{'+NS+'}surface'):
        try:
            p=dict(page=int(s.attrib['n']),width=float(s.attrib['lrx'])-float(s.attrib.get('ulx',0)),height=float(s.attrib['lry'])-float(s.attrib.get('uly',0)),origin=[float(s.attrib.get('ulx',0)),float(s.attrib.get('uly',0))])
            if p['page']<1 or not all(math.isfinite(v) and v>0 for v in (p['width'],p['height'])):raise ValueError()
            pages.append(p)
        except (KeyError,ValueError):pages.append(dict(status='invalid_surface',attributes=dict(s.attrib)))
    def walk(e,path,ancestors,parent_ref=None):
        tag=e.tag.rsplit('}',1)[-1];id='grobid:'+sha+':'+str(len(allpaths));allpaths.append(path)
        selected=tag in LABELS and e.tag.startswith('{'+NS+'}')
        if selected:
            coords=[];errors=[]
            for c in e.attrib.get('coords','').split(';'):
                if not c.strip():continue
                try:
                    vals=[float(x) for x in c.split(',')]
                    if len(vals)!=5 or not all(math.isfinite(v) for v in vals):raise ValueError()
                    page,x,y,w,h=vals
                    if page!=int(page) or page<1 or x<0 or y<0 or w<=0 or h<=0:raise ValueError()
                    coords.append(dict(page=int(page),bbox=[x,y,x+w,y+h],original=c))
                except ValueError:errors.append(c)
            nodes.append(dict(id=id,tag=tag,xpath=path,xml_id=e.attrib.get('{http://www.w3.org/XML/1998/namespace}id'),attributes=dict(e.attrib),text=''.join(e.itertext()),parent_ref=parent_ref,ancestors=ancestors,coords=coords,coordinate_errors=errors,target=e.attrib.get('target'),
                source=dict(tei_sha256=sha,run_ref=run.get('run_id'),models_ref=run.get('models_ref'),config_ref=run.get('config_ref'),source_family='grobid',derived_from_pdf_sha256=run.get('pdf_sha256')),strength='model_inferred'))
            parent_ref=id
        else:unmapped.append(dict(id=id,tag=tag,xpath=path,text=''.join(e.itertext()),attributes=dict(e.attrib),reason='container_or_unmapped_model_label'))
        counts=Counter()
        for child in e:
            counts[child.tag]+=1;walk(child,path+'/'+child.tag+f'[{counts[child.tag]}]',ancestors+[dict(tag=tag,type=e.attrib.get('type'))],parent_ref)
    walk(root,'/'+root.tag+'[1]',[])
    return dict(schema_version='grobid-evidence/1',tei_sha256=sha,run=run,pages=pages,nodes=nodes,unmapped_nodes=unmapped,accounting=dict(xml_nodes=len(allpaths),selected_nodes=len(nodes),other_nodes=len(unmapped)),source_family='grobid',semantic_validation='pending_after_full_mvp')
