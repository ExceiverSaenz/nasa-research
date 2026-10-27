"""Contracts for offline preparation and fail-closed remote preflight."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from page_integration.workflow import prepare, unpack, collect_texts, evaluate
from page_integration.remote_labels import check_environment


class WorkflowTests(unittest.TestCase):
    def test_preparation_allowlist_excludes_reference_and_refuses_overwrite(self):
        import zipfile
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            out=Path(temp)/'bundle'
            plan=prepare(out)
            self.assertEqual(len(plan['targets']),2)
            self.assertTrue(all(t['status']=='ready' for t in plan['targets']))
            with zipfile.ZipFile(out/'upload.zip') as z:
                self.assertFalse(any('reference' in n for n in z.namelist()))
                self.assertNotIn('render.png',z.namelist())
            unpack(out/'upload.zip',out/'upload.sha256',Path(temp)/'unpacked')
            with self.assertRaises(FileExistsError):prepare(out)

    def test_unpacked_content_tampering_is_rejected(self):
        import zipfile,hashlib
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            out=Path(temp)/'bundle';prepare(out)
            with zipfile.ZipFile(out/'upload.zip','a') as z:z.writestr('../escape.txt','bad')
            (out/'upload.sha256').write_text(hashlib.sha256((out/'upload.zip').read_bytes()).hexdigest())
            with self.assertRaises(ValueError):unpack(out/'upload.zip',out/'upload.sha256',Path(temp)/'unpacked')
            self.assertFalse((Path(temp)/'unpacked').exists())

    def test_native_text_preserves_fragment_pointers_and_blocks(self):
        doc={'schema':'docvortex.middle','schema_version':'2.0','pages':[{'page_idx':0,'blocks':[
            {'type':'text','bbox':[.1,.1,.5,.2],'content':[{'type':'text','content':'Table '},{'type':'text','content':'1'}]}]}]}
        texts=collect_texts(doc,[0,0,200,200],'t','middle-native.json','a'*64)
        self.assertEqual(texts[0]['text'],'Table 1')
        self.assertEqual(texts[0]['fragments'][1]['source_pointer'],'/pages/0/blocks/0/content/1/content')
        self.assertEqual(texts[0]['bbox'],[20,20,100,40])
        bad=copy.deepcopy(doc);bad['pages'][0]['blocks'][0]['bbox']=[20,20,100,40]
        with self.assertRaises(ValueError):collect_texts(bad,[0,0,200,200],'t','x','a'*64)

    def test_returned_synthetic_run_evaluates_links_and_rejects_runtime_drift(self):
        """Synthetic native data only. No parser or model is called."""
        import zipfile,hashlib
        from page_integration.workflow import ROOT,REFERENCE,read
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            temp=Path(temp);prep=temp/'prep';plan=prepare(prep)
            labels=read(ROOT/REFERENCE)['labels']
            from page_integration.remote_labels import canonical
            with zipfile.ZipFile(prep/'upload.zip') as source:
                packages={canonical(line.split('==',1)[0]):line.split('==',1)[1]
                          for line in source.read('requirements-freeze.txt').decode().splitlines() if line.strip()}
            def write_run(path,drift=False,swapped=False,compact=False):
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr('plan.json',json.dumps(plan,ensure_ascii=False,indent=2))
                    z.writestr('execution-status.json',json.dumps({'status':'completed'}))
                    z.writestr('runtime.json',json.dumps({'verified':True,'observed':{
                        'python':'3.11.16','packages':packages,'gpu':'A100' if drift else 'Tesla T4','cuda':'12.6',
                        'device':'cuda','backend':'torch','config_matches':True,'weights_match':True,
                        'parse_options_match':True,'env_matches':True},'expected':{'python':'3.11.16','packages':{}}}))
                    for i,t in enumerate(plan['targets']):
                        label=next(l for l in labels if l['object_id']==t['object_id']);roi=t['bbox']
                        def norm(b):return [(b[0]-roi[0])/(roi[2]-roi[0]),(b[1]-roi[1])/(roi[3]-roi[1]),
                                            (b[2]-roi[0])/(roi[2]-roi[0]),(b[3]-roi[1])/(roi[3]-roi[1])]
                        b=label['bbox'];expanded=[b[0]-2,b[1]-2,b[2]+2,b[3]+2]
                        content=('Table 2' if i==0 else 'Table 1') if swapped else label['text']
                        if compact:content=content.replace(' ','')
                        blocks=[{'type':'text','bbox':norm(expanded),'content':[{'type':'text','content':content}]},
                                {'type':'text','bbox':norm(t['caption_bbox']),'content':[{'type':'text','content':t['description']}]}]
                        z.writestr('rois/'+t['roi_id']+'/middle-native.json',json.dumps({'schema':'docvortex.middle','schema_version':'2.0','pages':[{'page_idx':0,'blocks':blocks}]}))
                path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
            good=temp/'good.zip';write_run(good)
            result=evaluate(prep,good,temp/'evaluation')
            self.assertTrue(result['links_verified']);self.assertTrue(result['labels_recovered'])
            compact=temp/'compact.zip';write_run(compact,compact=True)
            self.assertTrue(evaluate(prep,compact,temp/'compact-eval')['links_verified'])
            bad=temp/'bad.zip';write_run(bad,swapped=True)
            self.assertFalse(evaluate(prep,bad,temp/'wrong-links')['links_verified'])
            drift=temp/'drift.zip';write_run(drift,drift=True)
            with self.assertRaises(ValueError):evaluate(prep,drift,temp/'drift-eval')

    def test_preflight_checks_full_freeze_config_gpu_and_weights_before_parser(self):
        versions={'python':'3.11.16','packages':{'mineru':'4.0.12'},'gpu':'Tesla T4','cuda':'12.6',
                  'device':'cuda','backend':'torch','config_matches':True,'weights_match':True,
                  'parse_options_match':True,'env_matches':True}
        expected={'python':'3.11.16','packages':{'mineru':'4.0.12'}}
        check_environment(versions,expected)
        for key,value in [('gpu','A100'),('cuda','12.4'),('weights_match',False),('config_matches',False),('env_matches',False)]:
            bad=copy.deepcopy(versions);bad[key]=value
            with self.assertRaises(ValueError):check_environment(bad,expected)
        bad=copy.deepcopy(versions);bad['packages']['extra']='1'
        with self.assertRaises(ValueError):check_environment(bad,expected)


if __name__=='__main__':unittest.main()
