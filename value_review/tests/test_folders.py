"""Tests of the source folders in Settings and of loading papers from them (OP-10, OP-12)."""
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.tests.test_ingest import make_pdf, result, sha  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

SETTINGS = '/api/v1/settings'
BASE = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5}


class Folders(Base):
    def setUp(self):
        super().setUp()
        # A second pair of folders: paper 7 unchanged plus a new paper 9.
        d = Path(self.tmp.name)
        self.run2, self.pdfs2 = d / 'run2', d / 'pdfs2'
        self.run2.mkdir(); self.pdfs2.mkdir()
        shutil.copy(self.res, self.run2 / self.res.name)
        shutil.copy(self.pdf, self.pdfs2 / '7.pdf')
        make_pdf(self.pdfs2 / '9.pdf', [(612, 792)])
        data = result(sha(self.pdfs2 / '9.pdf'))
        data['paper']['paper_id'] = '9'
        data['paper']['title'] = 'A new paper'
        (self.run2 / '9-pdf_with_feature_guide.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def put(self, **folders):
        return self.client.put(SETTINGS, json={**BASE, **folders})

    def test_folders_are_validated(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        r = self.put(run_dir=str(empty), pdf_dir=str(Path(self.tmp.name) / 'nope'))
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'invalid_folder'))
        self.assertEqual(set(r.json()['error']['details']['fields']), {'run_dir', 'pdf_dir'})
        r = self.put(run_dir=str(self.run2), pdf_dir=str(empty))
        self.assertEqual(list(r.json()['error']['details']['fields']), ['pdf_dir'])
        self.assertFalse(self.store.settings_path.exists())

    def test_quotes_and_spaces_are_cleaned(self):
        r = self.put(run_dir=f'  "{self.run2}"  ', pdf_dir=f"'{self.pdfs2}'")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()['run_dir'], r.json()['pdf_dir']), (str(self.run2), str(self.pdfs2)))

    def test_ingest_adds_new_papers_and_keeps_existing(self):
        self.assertEqual(self.put(run_dir=str(self.run2), pdf_dir=str(self.pdfs2)).status_code, 200)
        before = (self.data / 'originals' / '7.json').read_bytes()
        r = self.client.post('/api/v1/ingest')
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body['written'], body['unchanged'], body['changed'], body['failed']), (1, 1, 0, 0))
        self.assertEqual({p['paper']: p['outcome'] for p in body['papers']}, {'7': 'unchanged', '9': 'written'})
        self.assertEqual((self.data / 'originals' / '7.json').read_bytes(), before)
        rows = {p['paper']: p for p in self.client.get('/api/v1/papers').json()}
        self.assertEqual(set(rows), {'7', '9'})
        self.assertEqual((rows['9']['title'], rows['9']['source_changed']), ('A new paper', False))
        self.assertEqual(self.client.get('/api/v1/papers/9/pages/1/image').status_code, 200)   # PDF from the new folder

    def test_a_changed_source_is_not_overwritten(self):
        (self.run2 / self.res.name).write_text(self.res.read_text(encoding='utf-8').replace('710', '711'), encoding='utf-8')
        self.put(run_dir=str(self.run2), pdf_dir=str(self.pdfs2))
        body = self.client.post('/api/v1/ingest').json()
        self.assertEqual({p['paper']: p['outcome'] for p in body['papers']}, {'7': 'changed', '9': 'written'})
        row = next(p for p in self.client.get('/api/v1/papers').json() if p['paper'] == '7')
        self.assertEqual((row['source_changed'], row['source_problems']), (True, ['result_changed']))

    def test_papers_missing_from_the_new_folders(self):
        only9 = Path(self.tmp.name) / 'only9'
        only9.mkdir()
        shutil.copy(self.run2 / '9-pdf_with_feature_guide.json', only9)
        self.put(run_dir=str(only9), pdf_dir=str(self.pdfs2))
        self.client.post('/api/v1/ingest')
        row = next(p for p in self.client.get('/api/v1/papers').json() if p['paper'] == '7')
        self.assertEqual(row['source_problems'], ['result_missing'])   # reviewed papers are never removed

    def test_sources_untouched(self):
        before = {p.name: sha(p) for p in list(self.run2.iterdir()) + list(self.pdfs2.iterdir())}
        self.put(run_dir=str(self.run2), pdf_dir=str(self.pdfs2))
        self.client.post('/api/v1/ingest')
        self.assertEqual({p.name: sha(p) for p in list(self.run2.iterdir()) + list(self.pdfs2.iterdir())}, before)


if __name__ == '__main__':
    unittest.main()
