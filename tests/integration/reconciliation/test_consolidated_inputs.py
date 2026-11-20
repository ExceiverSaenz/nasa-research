"""Synthetic archive contracts only; no models, renders or reconciliation runs."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

from integration.reconciliation.consolidated_inputs import prepare, load_document


def raw(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def sha(value):return hashlib.sha256(value).hexdigest()


class ConsolidatedInputTests(unittest.TestCase):
    def fixture(self,root,mutate=None,corrupt=None,unsafe=False):
        members={};original='a'*32;corrected='b'*32
        models={
            'layoutlmv3':{'packages':{'torch':'1.10.0+cu111','transformers':'4.12.5','detectron2':'0.6+cu111'}},
            'table_transformer':{'packages':{'torch':'2.5.1+cu121','transformers':'4.49.0'}},
            'mineru':{'packages':{'mineru':'4.0.12','docvortex':'0.6.0','torch':'2.7.1+cu126'}}}
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
        image=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',100,200,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*300)*200))+chunk(b'IEND',b'')
        selection={'layoutlmv3':original,'table_transformer':original,'mineru':corrected}
        index=[];entries=[]
        for number in (1,2):
            key=sha(str(number).encode());prefix=f'documents/{key}/pages/0001/'
            identity={'document_sha256':key,'physical_page':1,'render_sha256':sha(image),'width_px':100,'height_px':200,'dpi':200,
                'geometry':{'coordinate_system':{'unit':'pixel','origin':'top-left','bbox_format':'xyxy'}}}
            native={'schema':'docvortex.middle','schema_version':'2.0','metadata':{'producer':{'name':'mineru','version':'4.0.12'}},'pages':[
                {'page_idx':0,'blocks':[{'type':'image','bbox':[.1,.2,.9,.8],'content':[
                    {'type':'image_body','bbox':[.1,.2,.9,.7],'content':'asset'},
                    {'type':'image_caption','bbox':[.1,.7,.9,.8],'content':[{'type':'text','content':'Fig. 1'}]}]},
                    {'type':'new_unknown_kind','bbox':None,'content':'keep me'}]}]}
            lm={'document_id':key,'page':1,'coordinate_system':identity['geometry'],'regions':[{'type':'figure','bbox':[10,40,90,140],'score':.8}]}
            tatr={'coordinate_system':identity,'regions':[{'native_label':'table rotated','bbox':[-1,10,30,50],'score':.1}]}
            derived=[]
            def visit(n,p):
                box=n.get('bbox');derived.append({'source_pointer':p,'bbox_normalized':box,'bbox':None if box is None else [v*s for v,s in zip(box,[100,200,100,200])]})
                if n['type']=='image':
                    for i,c in enumerate(n['content']):visit(c,p+'/content/'+str(i))
            for i,n in enumerate(native['pages'][0]['blocks']):visit(n,'/pages/0/blocks/'+str(i))
            for path,obj in [('identity.json',identity),('mineru/middle-native.json',native),('layoutlmv3/regions.json',lm),('table_transformer/regions.json',tatr),
                ('mineru/regions.json',{'coordinate_system':{'width_px':100,'height_px':200,'unit':'pixel','origin':'top-left','bbox_format':'xyxy','native_bbox':'normalized [0,1]'},'regions':derived})]:members[prefix+path]=raw(obj)
            members[prefix+'render.png']=image
            for model in selection:members[prefix+model+'/status.json']=raw({'status':'completed','model':model,'page':1,'inference_calls':1})
            child={'document':f'SiC_papers/{number}.pdf','document_sha256':key,'page_count':1,'physical_pages':[1],'models':models,'dpi':200}
            entries.append({'key':key,'plan':child})
            members[f'provenance/attempts/{original}/documents/{key}/plan.json']=raw(child)
            index.append({'document':child['document'],'document_sha256':key,'pages':1,'path':f'documents/{key}/'})
        members['manifest.json']=raw({'schema':'sic-native-archive-consolidation/1','selection':selection,'documents':2,'physical_pages':2,'successful_page_parser_results':6,
            'input_archives':[{'attempt_id':original,'inner_sha256':'c'*64},{'attempt_id':corrected,'inner_sha256':'d'*64}]})
        members['index.json']=raw(index)
        members[f'provenance/attempts/{original}/plan.json']=raw({'models':models,'documents':entries})
        members[f'provenance/attempts/{original}/execution-profile.json']=raw({'actual_execution_policy':'USER_ONLY_COLAB_WEB_A100_PIPELINE'})
        if mutate:mutate(members)
        manifest={'schema':'archive-member-sha256/1','excludes_self':True,'files':{n:{'bytes':len(b),'sha256':sha(b),
            'source':None if '/pages/' not in n else {'attempt_id':corrected if '/mineru/' in n else original,'member':n}} for n,b in members.items()}}
        if corrupt:
            name=next(n for n in members if n.endswith(corrupt));members[name]+=b' '
        if unsafe:members['../escape.txt']=b'unsafe';manifest['files']['../escape.txt']={'bytes':6,'sha256':sha(b'unsafe')}
        archive=root/'native.zip'
        with zipfile.ZipFile(archive,'x') as z:
            for n,b in members.items():z.writestr(n,b)
            z.writestr('files-manifest.json',raw(manifest))
        archive.with_suffix('.sha256').write_text(sha(archive.read_bytes()))
        return archive,index

    def test_two_documents_canonical_contract_and_native_pointers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive,index=self.fixture(root);dest=root/'adapted'
            report=prepare(archive,dest)
            self.assertEqual(report['physical_pages'],2)
            ids=[]
            for entry in index:
                data=load_document(dest,entry['document_sha256']);page=data['pages'][0]
                self.assertEqual(page['adapter'],'canonical-v1');self.assertEqual(len(page['records']),6)
                self.assertEqual(set(page['parsers'].values()),{'completed'})
                body=next(r for r in page['records'] if r['native_type']=='image_body')
                self.assertEqual(body['bbox'],[10,40,90,140]);self.assertEqual(body['transform'],[100,0,0,200,0,0])
                self.assertIsNotNone(body['parent'])
                tatr=next(r for r in page['records'] if r['parser']=='table_transformer')
                self.assertEqual(tatr['native_type'],'table rotated');self.assertEqual(tatr['bbox'],[-1,10,30,50]);self.assertEqual(tatr['score'],.1)
                self.assertIn('invalid_geometry',page['incidents'])
                self.assertTrue(any(r['native_type']=='new_unknown_kind' and r['bbox'] is None for r in page['records']))
                self.assertFalse(any(k in page for k in ('groups','correspondences','decisions')))
                for record in page['records']:
                    value=json.loads(Path(record['source']['path']).read_bytes())
                    for part in record['source']['pointer'].strip('/').split('/'):
                        value=value[int(part)] if isinstance(value,list) else value[part]
                    self.assertEqual(value,record['native'])
                ids.extend(r['id'] for r in page['records'])
            self.assertEqual(len(ids),len(set(ids)))
            with self.assertRaises(FileExistsError):prepare(archive,dest)

    def test_hash_corruption_and_traversal_are_rejected(self):
        for opts in ({'corrupt':'middle-native.json'},{'unsafe':True}):
            with self.subTest(opts=opts),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);archive,_=self.fixture(root,**opts)
                with self.assertRaises(ValueError):prepare(archive,root/'adapted')
                self.assertFalse((root/'escape.txt').exists())

    def test_unknown_version_and_document_identity_are_rejected(self):
        def unknown(m):
            name=next(n for n in m if n.endswith('/plan.json') and '/documents/' not in n)
            obj=json.loads(m[name]);obj['models']['mineru']['packages']['mineru']='unknown';m[name]=raw(obj)
        def identity(m):
            name=next(n for n in m if n.endswith('identity.json'));obj=json.loads(m[name]);obj['physical_page']=2;m[name]=raw(obj)
        for change in (unknown,identity):
            with self.subTest(change=change.__name__),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);archive,_=self.fixture(root,mutate=change)
                with self.assertRaises(ValueError):prepare(archive,root/'adapted')

    def test_prepared_source_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive,index=self.fixture(root);dest=root/'adapted';prepare(archive,dest)
            data=load_document(dest,index[0]['document_sha256'])
            source=Path(data['pages'][0]['records'][0]['source']['path']);source.write_text('{}')
            with self.assertRaises(ValueError):load_document(dest,index[0]['document_sha256'])

    def test_wrong_transform_status_or_attempt_is_rejected(self):
        def transform(m):
            name=next(n for n in m if n.endswith('mineru/regions.json'))
            obj=json.loads(m[name]);obj['regions'][0]['bbox'][0]*=2;m[name]=raw(obj)
        def status(m):
            name=next(n for n in m if n.endswith('mineru/status.json'))
            obj=json.loads(m[name]);obj['status']='failed';m[name]=raw(obj)
        def attempt(m):
            obj=json.loads(m['manifest.json']);obj['selection']['mineru']='e'*32;m['manifest.json']=raw(obj)
        for change in (transform,status,attempt):
            with self.subTest(change=change.__name__),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);archive,_=self.fixture(root,mutate=change)
                with self.assertRaises(ValueError):prepare(archive,root/'adapted')


if __name__=='__main__':unittest.main()
