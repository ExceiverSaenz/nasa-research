import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from document_trial.common import ROOT,DOCUMENT,PAGE3,MODELS,read,save,sha,validate_bundle
from document_trial.offline import evaluate,reconcile

PACKAGE=ROOT/'code/packages/sic12-document-v5'
TEMP=ROOT/'analytics/results/sic12_document/trial-v1-preparation'

class PackageTests(unittest.TestCase):
    def test_document_and_original_environments_are_frozen(self):
        p=validate_bundle(PACKAGE/'upload.zip',PACKAGE/'upload.sha256')
        self.assertEqual(p['page_count'],13);self.assertEqual(p['physical_pages'],list(range(1,14)))
        self.assertEqual(p['document_sha256'],DOCUMENT)
        self.assertEqual([p['models'][m]['python'] for m in MODELS],['3.9.25','3.11.11','3.11.16'])
        self.assertFalse(p['automatic_recovery']);self.assertFalse(p['automatic_retries'])
        with zipfile.ZipFile(PACKAGE/'upload.zip') as z:
            # v5 is a frozen historical package, not the current editable source.
            manifest=json.loads(z.read('bundle-manifest.json'))
            for name,spec in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),spec['sha256'])

    def test_corrupt_bundle_and_unsafe_member_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            p=Path(folder);z=p/'upload.zip'
            with zipfile.ZipFile(z,'w') as archive:
                archive.writestr('../escape',b'x');archive.writestr('bundle-manifest.json',json.dumps({'files':{'../escape':{'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}}}))
            (p/'upload.sha256').write_text(sha(z))
            with self.assertRaises(ValueError):validate_bundle(z,p/'upload.sha256',p/'extracted')
            self.assertFalse((p/'extracted').exists())

    def test_historical_page3_boxes_and_native_content_stay_exact(self):
        with zipfile.ZipFile(PACKAGE/'upload.zip') as z:
            native=json.loads(z.read('regression/original-middle.json'))
            historical=json.loads(z.read('regression/historical-reconciled.json'))
        identity=dict(document_sha256=DOCUMENT,physical_page=3,render_sha256=PAGE3,width_px=1654,height_px=2205)
        candidate=reconcile(identity,native,{})
        by_id={x['local_id']:x for x in candidate['segments']}
        self.assertEqual(len(by_id),19)
        for original in historical['regions']:
            self.assertEqual(by_id[original['id']]['bbox'],original['bbox'])
            self.assertEqual(by_id[original['id']]['native_content'],original['native_content_evidence']['record'])
        self.assertEqual(len(candidate['containers']),4);self.assertEqual(len(candidate['relations']),8)

    def synthetic_archive(self,folder,changed=False):
        with zipfile.ZipFile(PACKAGE/'upload.zip') as upload:
            plan=upload.read('plan.json');native=json.loads(upload.read('regression/original-middle.json'));render=upload.read('regression/reference-render.png')
        archive=folder/'synthetic-not-inference.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('plan.json',plan);z.writestr('execution-status.json',json.dumps(dict(status='failed',error='synthetic missing page13 branch')))
            for page in range(1,14):
                prefix='pages/%04d/'%page
                for model in MODELS:z.writestr(prefix+model+'/status.json',json.dumps(dict(status='not_run' if page==13 else 'completed',model=model,page=page)))
                if page==13:continue
                identity=dict(document_sha256=DOCUMENT,physical_page=page,render_sha256=PAGE3,width_px=1654,height_px=2205)
                z.writestr(prefix+'identity.json',json.dumps(identity));z.writestr(prefix+'render.png',render)
                current=copy.deepcopy(native) if page==3 else dict(pages=[dict(page_idx=0,blocks=[dict(type='text',bbox=[.1,.1,.8,.2],content=[dict(type='text',content='Synthetic page')])])])
                if changed and page==3:current['pages'][0]['blocks'][0]['bbox'][0]+=.001
                z.writestr(prefix+'mineru/middle-native.json',json.dumps(current))
                for model in ('layoutlmv3','table_transformer'):z.writestr(prefix+model+'/regions.json',json.dumps(dict(regions=[])))
        sidecar=folder/'synthetic.sha256';sidecar.write_text(sha(archive));return archive,sidecar

    def test_full_offline_synthetic_document_preserves_regression_and_counts_failures(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            folder=Path(folder);archive,sidecar=self.synthetic_archive(folder)
            summary=evaluate(PACKAGE,archive,sidecar,folder/'analysis')
            self.assertEqual(len(summary),13);self.assertEqual(summary[-1]['status'],'not_evaluable_missing_render_or_native')
            self.assertTrue(read(folder/'analysis/page-0013/review-template.json')['not_evaluable_reason'])
            enrichment=read(folder/'analysis/page-0003/M1-enrichment.json')
            self.assertEqual(enrichment['table1'],'pending_warning');self.assertEqual(len(enrichment['accepted_components']),1)
            self.assertTrue(read(folder/'analysis/page-0003/regression.json')['selected_content_equal'])
            self.assertEqual(read(folder/'analysis/document-status.json')['status'],'pending_manual_evaluation_not_quality_accepted')
            with self.assertRaises(FileExistsError):evaluate(PACKAGE,archive,sidecar,folder/'analysis')

    def test_changed_page3_does_not_transplant_historical_table2_acceptance(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            folder=Path(folder);archive,sidecar=self.synthetic_archive(folder,changed=True)
            evaluate(PACKAGE,archive,sidecar,folder/'analysis')
            self.assertEqual(read(folder/'analysis/page-0003/M1-enrichment.json')['accepted_components'],[])
            self.assertTrue(read(folder/'analysis/page-0003/historical-table2-acceptance.json')['links_verified'])

if __name__=='__main__':unittest.main()
