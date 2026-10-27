"""Read native PDF evidence only. No OCR, rendering, models or source writes."""
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import fitz


def inspect_pdf(path):
    path=Path(path).resolve();before=hashlib.sha256(path.read_bytes()).hexdigest();d=fitz.open(path)
    evidence=[];pages=[];missing=[]
    def add(id,kind,page,data,**source):
        evidence.append(dict(id=id,kind=kind,page=page,data=data,source=dict(pdf_sha256=before,**source)))
    for i,p in enumerate(d):
        n=i+1;pages.append(dict(page=n,width_pt=p.rect.width,height_pt=p.rect.height,rotation=p.rotation,crop_box=list(p.cropbox),media_box=list(p.mediabox)))
        blocks=p.get_text('dict',flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES,sort=False)['blocks']
        for j,b in enumerate(blocks):
            if b['type']!=0:continue
            add(f'native:p{n}:b{j}','text_block',n,dict(bbox=list(b['bbox']),text='\n'.join(''.join(s['text'] for s in l['spans']) for l in b['lines']),lines=b['lines']),api='PyMuPDF.Page.get_text(dict,sort=False)',pointer=f'/pages/{i}/blocks/{j}')
        for j,l in enumerate(p.get_links()):
            data={k:(list(v) if isinstance(v,(fitz.Rect,fitz.Point)) else v) for k,v in l.items()}
            add(f'native:p{n}:link{j}','annotation_link',n,data,api='PyMuPDF.Page.get_links',pointer=f'/pages/{i}/links/{j}',xref=l.get('xref'))
        for j,image in enumerate(p.get_images(full=True)):
            add(f'native:p{n}:image{j}','image_resource',n,dict(xref=image[0],width=image[2],height=image[3],resource_name=image[7]),api='PyMuPDF.Page.get_images',pointer=f'/pages/{i}/images/{j}')
    stack=[];toc=d.get_toc(simple=False)
    for i,(level,title,page,detail) in enumerate(toc):
        while stack and stack[-1][0]>=level:stack.pop()
        id=f'native:outline:{i}';parent=stack[-1][1] if stack else None
        add(id,'outline',page if page>0 else None,dict(title=title,level=level,parent_ref=parent,destination={k:(list(v) if isinstance(v,(fitz.Rect,fitz.Point)) else v) for k,v in detail.items()}),api='PyMuPDF.Document.get_toc',pointer=f'/outlines/{i}',xref=detail.get('xref'));stack.append((level,id))
    if not toc:missing.append('outlines')
    xmp=d.get_xml_metadata();prefix={'http://purl.org/dc/elements/1.1/':'dc','http://prismstandard.org/namespaces/basic/3.0/':'prism'}
    if xmp:
        try:
            root=ET.fromstring(xmp)
            for i,desc in enumerate(root.findall('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')):
                for j,e in enumerate(desc):
                    uri,tag=e.tag[1:].split('}',1) if e.tag.startswith('{') else ('',e.tag)
                    field=prefix.get(uri,uri)+':'+tag
                    values=[x.text or '' for x in e.findall('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li')] or [''.join(e.itertext()).strip()]
                    add(f'native:xmp:{i}:{j}','xmp',None,dict(field=field,values=values),api='PyMuPDF.Document.get_xml_metadata + ElementTree',pointer=f'/rdf/Description/{i}/{j}')
        except ET.ParseError as e:missing.append('xmp_parse_error:'+str(e))
    else:missing.append('xmp')
    for k,v in d.metadata.items():
        if v:add('native:metadata:'+k,'pdf_metadata',None,dict(field=k,values=[v]),api='PyMuPDF.Document.metadata',pointer='/metadata/'+k)
    pageof={p.xref:i+1 for i,p in enumerate(d)}
    def ref(obj,key):
        val=d.xref_get_key(obj,key)[1];return int(val.split()[0]) if val.endswith(' R') else None
    sr=ref(d.pdf_catalog(),'StructTreeRoot');seen=set();pending=[sr] if sr else [];attribute_refs=[]
    while pending and len(seen)<5000:
        x=pending.pop(0)
        if x in seen:continue
        seen.add(x);k=d.xref_get_key(x,'K')[1];pending.extend(int(a) for a in re.findall(r'(\d+)\s+0\s+R',k))
        typ=d.xref_get_key(x,'S')[1]
        if typ=='null':continue
        pg=ref(x,'Pg');ar=ref(x,'A');attribute_refs.append(ar)
        add(f'native:struct:{x}','structure_element',pageof.get(pg),dict(tag=typ,title=d.xref_get_key(x,'T')[1],alt=d.xref_get_key(x,'Alt')[1],attribute_ref=ar,attributes=d.xref_object(ar) if ar else None,geometry_use='not_used_for_region_localization'),api='PyMuPDF.xref_get_key',xref=x,pointer=f'/xref/{x}')
    if pending:missing.append('structure_traversal_limit')
    if not sr:missing.append('structure_tree')
    for e in evidence:
        if e['kind']=='structure_element' and e['data']['attribute_ref'] and attribute_refs.count(e['data']['attribute_ref'])>1:e['data']['warning']='shared_attributes_geometry_requires_validation'
    threads=d.xref_get_key(d.pdf_catalog(),'Threads')[1];thread_refs=[int(x) for x in re.findall(r'(\d+)\s+0\s+R',threads)]
    for t in thread_refs:
        x=ref(t,'F');visited=set()
        while x and x not in visited and len(visited)<5000:
            visited.add(x);pg=ref(x,'P');add(f'native:thread:{t}:{x}','article_thread_area',pageof.get(pg),dict(thread_xref=t,rectangle_literal=d.xref_get_key(x,'R')[1],next_xref=ref(x,'N'),order_use='candidate_only_unvalidated',coordinate_origin='PDF_bottom_left'),api='PyMuPDF.xref_get_key',xref=x,pointer=f'/xref/{x}');x=ref(x,'N')
    if not thread_refs:missing.append('article_threads')
    metadata=d.metadata.copy();d.close()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=before:raise ValueError('PDF mutated')
    return dict(pdf_path=str(path),pdf_sha256=before,extractor='PyMuPDF',extractor_version=fitz.VersionBind,metadata=metadata,raw_xmp=xmp,pages=pages,evidence=evidence,missing_information=missing,counts=dict(Counter(e['kind'] for e in evidence)))
