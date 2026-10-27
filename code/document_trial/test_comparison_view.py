"""Offline fidelity and export tests; no parser/model/browser execution."""
import copy
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import comparison_view as viewer

ROOT = Path(__file__).resolve().parents[2]


class ViewerTests(unittest.TestCase):
    def test_all_pages_and_regions_match_sources(self):
        data = viewer.build(ROOT)
        self.assertEqual(len(data['pages']), 13)
        for page in data['pages']:
            baseline = json.loads((ROOT/page['baseline']).read_bytes())
            self.assertEqual(page['views']['mineru'], page['views']['reconciled'])
            selected = [x for x in page['views']['reconciled'] if x['layer']=='segment']
            self.assertEqual([x['bbox'] for x in selected], [x['bbox'] for x in baseline['segments']])
            self.assertEqual([x['id'] for x in selected], [x['id'] for x in baseline['segments']])
            for model,key in [('layoutlmv3','lm'),('table_transformer','tatr')]:
                evidence = [x for x in baseline['evidence'] if x['model']==model]
                self.assertEqual([x['bbox'] for x in page['views'][key]], [x['native_record']['bbox'] for x in evidence])
                self.assertEqual([x['id'] for x in page['views'][key]], [x['id'] for x in evidence])
        self.assertEqual(sum(len(p['groups']) for p in data['pages']),6)
        self.assertEqual(sum(len(p['historical']) for p in data['pages']),1)
        title=next(x for x in data['pages'][3]['outline'] if x['local_id']=='p0-b9')
        self.assertEqual(title['level'],2)
        self.assertEqual(title['text'],'4. Results')
        self.assertTrue(all(not p['paragraph_section_membership_validated'] for p in data['pages']))

    def test_identity_and_native_pointer_corruption_rejected(self):
        original=viewer.read_json
        for mutate in [lambda r:r['identity'].update(physical_page=99),
                       lambda r:r['segments'][0].update(source_pointer='/bad')]:
            def altered(path):
                value=original(path)
                if str(path).replace('\\','/').endswith('page-0004/R-reconciled.json'):
                    value=copy.deepcopy(value);mutate(value)
                return value
            with self.subTest(mutate=mutate),patch.object(viewer,'read_json',side_effect=altered):
                with self.assertRaises(ValueError):viewer.build(ROOT)

    def test_export_deterministic_protected_and_safe_html(self):
        before=viewer.protected_hashes(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            dest=Path(folder)/'view'
            viewer.export(ROOT,dest)
            original=(dest/'index.html').read_bytes()
            viewer.export(ROOT,dest)
            self.assertEqual(original,(dest/'index.html').read_bytes())
            self.assertIn(b'application/json',original)
            self.assertIn(b'comparison_view.js',original)
            class Resources(HTMLParser):
                def __init__(self): super().__init__(); self.urls=[]
                def handle_starttag(self,tag,attrs):
                    attrs=dict(attrs)
                    if tag=='script' and 'src' in attrs:self.urls.append(attrs['src'])
                    if tag=='link' and 'href' in attrs:self.urls.append(attrs['href'])
            resources=Resources();resources.feed(original.decode('utf-8'))
            self.assertFalse(any(x.startswith(('http:','https:')) for x in resources.urls))
            (dest/'comparison_view.js').write_text('incompatible')
            with self.assertRaises(ValueError):viewer.export(ROOT,dest)
            self.assertEqual(original,(dest/'index.html').read_bytes())
        self.assertEqual(before,viewer.protected_hashes(ROOT))
        self.assertNotIn('</script',viewer.safe_json({'native_text':'</script><img src=x>'}))

    def test_protected_destination_rejected(self):
        with self.assertRaises(ValueError):viewer.export(ROOT,ROOT/viewer.EVAL/'new-output')
