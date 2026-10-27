import copy
import json
from pathlib import Path
import unittest
import tempfile
import shutil
from reconciliation.inputs import digest
from reconciliation.inputs import load_evaluation
from reconciliation.engine import reconcile

ROOT=Path(__file__).resolve().parents[2]
EVAL=ROOT/'analytics/results/sic12_document/evaluation-v1-20261025'


class InputTests(unittest.TestCase):
    def fixture(self, root):
        manifest=json.loads((EVAL/'evaluation-manifest.json').read_bytes())
        names=['manifest.json','document-status.json']+[f'page-{n:04d}/{s}' for n in (1,2) for s in ('M0-native.json','R-reconciled.json','source-manifest.json','render.png')]
        outputs={}
        for name in names:
            dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(EVAL/name,dest)
            outputs[name]=digest(dest.read_bytes())
        config=json.loads((root/'manifest.json').read_bytes());config['plan']['physical_pages']=[1,2]
        (root/'manifest.json').write_text(json.dumps(config),encoding='utf-8');outputs['manifest.json']=digest((root/'manifest.json').read_bytes())
        manifest['outputs']=outputs;(root/'evaluation-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        return manifest

    def test_missing_mineru_keeps_external_page(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            root=Path(temp);m=self.fixture(root)
            del m['outputs']['page-0001/M0-native.json']
            (root/'evaluation-manifest.json').write_text(json.dumps(m))
            data=load_evaluation(root);self.assertEqual(len(data['pages']),2)
            out=reconcile(data['pages'][0]);self.assertFalse(out['objects'])
            self.assertTrue(any(r['parser']=='layoutlmv3' for r in out['records']))

    def test_local_corruption_and_unknown_version(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            root=Path(temp);m=self.fixture(root)
            (root/'page-0001/M0-native.json').write_text('corrupted')
            results=[reconcile(p) for p in load_evaluation(root)['pages']]
            self.assertEqual(results[0]['status'],'blocked');self.assertEqual(results[1]['status'],'completed')
            self.fixture(root)
            config=json.loads((root/'manifest.json').read_bytes());config['plan']['models']['layoutlmv3']['packages']['transformers']='unknown'
            (root/'manifest.json').write_text(json.dumps(config));m['outputs']['manifest.json']=digest((root/'manifest.json').read_bytes())
            (root/'evaluation-manifest.json').write_text(json.dumps(m))
            self.assertTrue(all(reconcile(p)['status']=='blocked' for p in load_evaluation(root)['pages']))

    def test_existing_sources_and_known_regression(self):
        data=load_evaluation(EVAL)
        self.assertEqual(len(data['pages']),13)
        results=[reconcile(p) for p in data['pages']]
        self.assertEqual(sum(len(p['records']) for p in results),536)
        self.assertEqual(sum(len(p['objects']) for p in results),251)
        self.assertEqual(sum(len(p['containers']) for p in results),36)
        self.assertEqual(sum(len(p['groups']) for p in results),6)
        self.assertEqual([p['identity']['physical_page'] for p in results if p['groups']],[5,6,10,11])
        for p in results:
            baseline=json.loads((EVAL/f'page-{p["identity"]["physical_page"]:04d}/R-reconciled.json').read_bytes())
            selected={r['source_pointer']:r for r in baseline['segments']+baseline['containers']}
            if p['identity']['physical_page'] in (8,12):self.assertFalse(p['groups'])
            for r in p['records']:
                self.assertIn('pointer',r['source']);self.assertIn('sha256',r['source'])
                node=json.loads(Path(r['source']['path']).read_bytes())
                for part in r['source']['pointer'].strip('/').split('/'):
                    node=node[int(part)] if isinstance(node,list) else node[part]
                self.assertEqual(node,r['native'])
                if r['parser']=='mineru':self.assertEqual(r['bbox'],selected[r['source']['pointer']]['bbox'])
            self.assertFalse(any('human' in r for r in p))
        reference=json.loads((ROOT/'analytics/results/sic12_document/multipanel-candidates-v1-human-review/human-review.json').read_bytes())
        for case in reference['cases']:
            p=results[case['page']-1];byid={r['id']:r for r in p['records']}
            expected={m['source_pointer'] for m in case['members']}
            matches=[g for g in p['groups'] if {byid[m]['source']['pointer'] for m in g['members']}==expected]
            if case['decision']=='human_validated_composition':
                self.assertEqual(len(matches),1)
                self.assertEqual(byid[matches[0]['caption']]['source']['pointer'],case['captions'][0]['source_pointer'])
            else:self.assertFalse(matches)

    def test_no_human_or_enrichment_dependency(self):
        data=load_evaluation(EVAL)
        self.assertFalse(any('human' in p or 'final-reconciliation' in p or 'M1-' in p for p in data['source_inputs']))
        p=data['pages'][4];before=copy.deepcopy(p);reconcile(p);self.assertEqual(p,before)
        self.assertTrue(all(r['parser']!='historical' for r in p['records']))


if __name__=='__main__':unittest.main()
