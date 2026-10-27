"""Offline tests, no subprocess, network or model imports."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from .multipanel_candidates import generate
from .multipanel_candidates import export

BASE=Path(__file__).resolve().parents[2]/'analytics/results/sic12_document/evaluation-v1-20261025'


class CandidatesTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads((BASE/'page-0005/R-reconciled.json').read_bytes())

    def test_real_case_and_simple_contrast(self):
        before=copy.deepcopy(self.r)
        out=generate(self.r,self.r['identity'])
        self.assertEqual(self.r,before)
        self.assertTrue(any(len(c['members'])==2 for c in out['candidates']))
        self.assertTrue(any(c['status']=='single_body_no_group' for c in out['candidates']))
        self.assertTrue(all(c['accepted'] is False for c in out['candidates']))

    def test_identity_abstention(self):
        wrong=dict(self.r['identity'],physical_page=99)
        self.assertEqual(generate(self.r,wrong)['status'],'abstained')

    def test_invalid_geometry(self):
        self.r['segments'][0]['bbox']=[0,0,0,1]
        self.assertEqual(generate(self.r,self.r['identity'])['status'],'abstained')

    def test_caption_absent(self):
        self.r['segments']=[s for s in self.r['segments'] if s['type']!='caption']
        out=generate(self.r,self.r['identity'])
        self.assertTrue(all(c['status']=='abstained' for c in out['candidates'] if len(c['members'])>=2))

    def test_equivalent_anchor_deduplicated(self):
        anchor=next(e for e in self.r['evidence'] if e['native_record'].get('region_id','').endswith('p5-r8'))
        self.r['evidence'].append(copy.deepcopy(anchor))
        out=generate(self.r,self.r['identity'])
        two=[c for c in out['candidates'] if len(c['members'])==2]
        self.assertEqual(len(two),1)
        self.assertEqual(len(two[0]['anchors']),2)

    def test_multiple_captions(self):
        cap=copy.deepcopy(next(s for s in self.r['segments'] if s['local_id']=='p0-b12-c1'))
        cap['local_id']='p0-b11-c1';cap['id']=cap['id'].replace('p0-b12-c1','p0-b11-c1')
        cap['source_pointer']='/pages/0/blocks/11/content/1'
        self.r['segments'].append(cap)
        c=next(c for c in generate(self.r,self.r['identity'])['candidates'] if len(c['members'])==2)
        self.assertEqual(c['status'],'review_required');self.assertIn('multiple_captions',c['reasons'])

    def test_borderline(self):
        a=next(e for e in self.r['evidence'] if e['native_record'].get('region_id','').endswith('p5-r8'))
        a['native_record']['bbox'][0]=600
        out=generate(self.r,self.r['identity'])
        self.assertTrue(any(c['borderline_members'] and c['status']=='review_required' for c in out['candidates']))

    def test_mixed_context_and_shared_alternatives(self):
        a=next(e for e in self.r['evidence'] if e['native_record'].get('region_id','').endswith('p5-r8'))
        other=copy.deepcopy(a);other['id']+='-alternative';other['native_record']['bbox']=[0,0,1654,2205]
        self.r['evidence'].append(other)
        out=generate(self.r,self.r['identity'])
        self.assertTrue(any('shared_members_between_anchors' in c['reasons'] for c in out['candidates']))
        self.assertTrue(any('context_overlap' in c['reasons'] for c in out['candidates']))

    def test_export_determinism_and_protection(self):
        with tempfile.TemporaryDirectory(dir=BASE.parents[3]/'tmp') as folder:
            p=Path(folder)/'out.json';args=(BASE/'page-0005/R-reconciled.json',BASE/'page-0005/source-manifest.json',p)
            export(*args);first=p.read_bytes();export(*args);self.assertEqual(first,p.read_bytes())
            p.write_text('{}')
            with self.assertRaises(ValueError):export(*args)
