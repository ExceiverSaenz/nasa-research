"""Tests of the folder pairs in Settings (each LLM results folder with its PDFs) and of loading papers
from them (OP-10, OP-12). Each pair keeps its own originals, drafts and versions."""
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.tests.test_ingest import make_pdf, result, sha  # noqa: E402
from value_review.domain.state import empty_state  # noqa: E402
from value_review.tests.test_service import Base  # noqa: E402

SETTINGS = '/api/v1/settings'
BASE = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5}


class Folders(Base):
    def setUp(self):
        super().setUp()
        # A second pair of folders: paper 7 unchanged plus a new paper 9.
        d = Path(self.tmp.name)
        self.run2, self.pdfs2 = d / 'run2', d / 'pdfs2'
        self.run2.mkdir()
        self.pdfs2.mkdir()
        shutil.copy(self.res, self.run2 / self.res.name)
        shutil.copy(self.pdf, self.pdfs2 / '7.pdf')
        make_pdf(self.pdfs2 / '9.pdf', [(612, 792)])
        data = result(sha(self.pdfs2 / '9.pdf'))
        data['paper']['paper_id'] = '9'
        data['paper']['title'] = 'A new paper'
        (self.run2 / '9-pdf_with_feature_guide.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.first = {'id': 'default', 'name': 'run', 'run_dir': str(self.run), 'pdf_dir': str(self.pdfs)}

    def put(self, sources, **extra):
        return self.client.put(SETTINGS, json={**BASE, 'sources': sources, **extra})

    def add_second(self, **pair):
        r = self.put([self.first, {'name': 'Second run', 'run_dir': str(self.run2), 'pdf_dir': str(self.pdfs2), **pair}])
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_default_pair(self):
        s = self.client.get(SETTINGS).json()
        self.assertEqual((s['sources'], s['active_source']), ([self.first], 'default'))

    def test_settings_saved_before_pairs_become_the_default_pair(self):
        self.write_json(self.store.settings_path, {**BASE, 'run_dir': str(self.run2), 'pdf_dir': str(self.pdfs2)})
        s = self.client.get(SETTINGS).json()
        self.assertEqual(s['sources'], [{'id': 'default', 'name': 'run2', 'run_dir': str(self.run2), 'pdf_dir': str(self.pdfs2)}])

    def test_folders_are_validated_per_field(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        r = self.put([self.first, {'name': 'run', 'run_dir': str(empty), 'pdf_dir': str(Path(self.tmp.name) / 'nope')}])
        self.assertEqual((r.status_code, r.json()['error']['code']), (422, 'invalid_folder'))
        self.assertEqual(r.json()['error']['details']['fields'], {
            'sources.1.name': 'Another pair has this name.',
            'sources.1.run_dir': 'No LLM results here (files named <paper>-pdf_with_feature_guide.json).',
            'sources.1.pdf_dir': 'This folder does not exist.'})
        r = self.put([{'name': ' ', 'run_dir': '', 'pdf_dir': str(self.pdfs2)}])
        self.assertEqual(set(r.json()['error']['details']['fields']), {'sources.0.name', 'sources.0.run_dir'})
        r = self.put([])
        self.assertEqual(r.json()['error']['details']['fields'], {'sources': 'Add at least one folder pair.'})
        self.assertFalse(self.store.settings_path.exists())

    # --- white-box cases (11-white-box-coverage-review.md) ------------------------------------
    def test_wb01_no_complete_paper_loads_nothing(self):  # WB-01: `complete == []` must not load every paper
        lone = Path(self.tmp.name) / 'lone pdfs'
        lone.mkdir()
        make_pdf(lone / '12.pdf', [(612, 792)])   # no result matches it; results 7 and 9 have no PDF here
        self.add_second(pdf_dir=str(lone))
        body = self.client.post('/api/v1/sources/second-run/ingest').json()
        self.assertEqual({k: body[k] for k in ('written', 'unchanged', 'changed', 'failed', 'papers')},
                         {'written': 0, 'unchanged': 0, 'changed': 0, 'failed': 0, 'papers': []})
        self.assertEqual((body['results_without_pdf'], body['pdfs_without_results']), (['7', '9'], ['12']))
        self.assertFalse((self.data / 'sources' / 'second-run' / 'originals').exists())

    def test_wb03_pdfs_without_results_in_numeric_then_name_order(self):  # WB-03: `order` key
        for name in ('notes.pdf', '10.pdf', '2.pdf'):
            make_pdf(self.pdfs2 / name, [(612, 792)])
        self.add_second()
        body = self.client.post('/api/v1/sources/second-run/ingest').json()
        self.assertEqual(body['pdfs_without_results'], ['2', '10', 'notes'])

    def test_wb05_changed_folders_of_an_existing_pair_are_checked_again(self):  # WB-05
        self.add_second()
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        s = self.client.get(SETTINGS).json()
        s['sources'][1]['run_dir'] = str(empty)
        r = self.client.put(SETTINGS, json={**BASE, 'sources': s['sources']})
        self.assertEqual((r.status_code, r.json()['error']['details']['fields']),
                         (422, {'sources.1.run_dir': 'No LLM results here (files named <paper>-pdf_with_feature_guide.json).'}))
        self.assertEqual(self.client.get(SETTINGS).json()['sources'][1]['run_dir'], str(self.run2))   # nothing saved

    def test_loading_after_a_saved_folder_disappeared(self):  # OP-12: 422 invalid_folder, nothing changed
        self.add_second()
        self.client.post('/api/v1/sources/second-run/ingest')
        originals = self.data / 'sources' / 'second-run' / 'originals'
        before = {p.name: sha(p) for p in originals.iterdir()}
        shutil.rmtree(self.run2)   # moved or deleted outside the app
        r = self.client.post('/api/v1/sources/second-run/ingest')
        self.assertEqual((r.status_code, r.json()['error']['code'], r.json()['error']['details']['fields']),
                         (422, 'invalid_folder', {'run_dir': 'This folder does not exist.'}))
        self.assertEqual({p.name: sha(p) for p in originals.iterdir()}, before)   # loaded papers kept
        rows = self.client.get('/api/v1/sources/second-run/papers').json()
        self.assertEqual({r['paper']: r['source_problems'] for r in rows}, {'7': ['result_missing'], '9': ['result_missing']})

    def test_wb10_pair_removed_while_in_use(self):  # WB-10: Source.folders after the pair is gone
        from value_review.service.errors import ApiError
        self.add_second()
        source = self.client.app.state.source('second-run')
        self.assertEqual(source.folders(), (self.run2, self.pdfs2))
        self.put([self.first])
        with self.assertRaises(ApiError) as caught:
            source.folders()
        self.assertEqual((caught.exception.status, caught.exception.code), (404, 'source_not_found'))
        self.assertEqual(self.client.get('/api/v1/sources/second-run/papers').status_code, 404)

    def test_unknown_or_repeated_id_is_refused(self):
        for sources in ([{**self.first, 'id': 'nope'}], [self.first, self.first]):
            self.assertEqual(self.put(sources).status_code, 400)

    def test_unchanged_folders_are_not_checked_again(self):
        self.add_second()
        shutil.rmtree(self.run2)   # the second pair's folder is gone, but saving other settings still works
        s = self.client.get(SETTINGS).json()
        r = self.client.put(SETTINGS, json={**BASE, 'reviewer_name': 'Dr. R', 'sources': s['sources']})
        self.assertEqual(r.status_code, 200, r.text)

    def test_quotes_and_spaces_are_cleaned_and_ids_made_from_names(self):
        s = self.add_second(run_dir=f'  "{self.run2}"  ', pdf_dir=f"'{self.pdfs2}'")
        self.assertEqual(s['sources'][1], {'id': 'second-run', 'name': 'Second run', 'run_dir': str(self.run2), 'pdf_dir': str(self.pdfs2)})
        self.assertEqual(s['active_source'], 'default')

    def test_each_pair_has_its_own_papers(self):
        self.add_second()
        r = self.client.post('/api/v1/sources/second-run/ingest')
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body['source'], body['written'], body['unchanged']), ('second-run', 2, 0))
        self.assertTrue((self.data / 'sources' / 'second-run' / 'originals' / '9.json').is_file())
        self.assertEqual([p['paper'] for p in self.client.get('/api/v1/papers').json()], ['7'])   # active: default
        self.assertEqual([p['paper'] for p in self.client.get('/api/v1/sources/second-run/papers').json()], ['7', '9'])
        self.assertEqual(self.client.get('/api/v1/sources/second-run/papers/9/pages/1/image').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/papers/9').status_code, 404)

    def test_papers_missing_a_file_are_reported_by_what_is_missing(self):
        for name in ('12.pdf', '3.pdf'):   # PDFs without an LLM result
            make_pdf(self.pdfs2 / name, [(612, 792)])
        shutil.copy(self.run2 / '9-pdf_with_feature_guide.json', self.run2 / '11-pdf_with_feature_guide.json')   # result without PDF
        self.add_second()
        body = self.client.post('/api/v1/sources/second-run/ingest').json()
        self.assertEqual((body['written'], body['failed']), (2, 0))
        self.assertEqual((body['results_without_pdf'], body['pdfs_without_results']), (['11'], ['3', '12']))
        self.assertEqual([p['paper'] for p in self.client.get('/api/v1/sources/second-run/papers').json()], ['7', '9'])
        body = self.client.post('/api/v1/ingest').json()   # default pair: both files for every paper
        self.assertEqual((body['results_without_pdf'], body['pdfs_without_results']), ([], []))

    def test_versions_are_kept_per_pair(self):
        self.add_second()
        self.client.post('/api/v1/sources/second-run/ingest')
        r = self.client.post('/api/v1/sources/second-run/papers/7/versions', json={'state': empty_state()}, headers={'If-Match': '0'})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.headers['Location'], '/api/v1/sources/second-run/papers/7/versions/1')
        self.assertTrue((self.data / 'sources' / 'second-run' / 'annotations' / 'versions' / '7' / 'v1.json').is_file())
        self.assertEqual(self.client.get('/api/v1/papers/7/versions').json(), [])   # default pair: none
        self.assertEqual(len(self.client.get('/api/v1/sources/second-run/papers/7/versions').json()), 1)

    def test_switching_the_active_pair(self):
        self.add_second()
        self.client.post('/api/v1/sources/second-run/ingest')
        r = self.client.put('/api/v1/active-source', json={'source': 'second-run'})
        self.assertEqual((r.status_code, r.json()['active_source']), (200, 'second-run'))
        self.assertEqual([p['paper'] for p in self.client.get('/api/v1/papers').json()], ['7', '9'])
        self.assertEqual(self.client.put('/api/v1/active-source', json={'source': 'nope'}).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/sources/nope/papers').json()['error']['code'], 'source_not_found')

    def test_removing_a_pair_keeps_its_data(self):
        self.add_second()
        self.client.post('/api/v1/sources/second-run/ingest')
        self.client.put('/api/v1/active-source', json={'source': 'second-run'})
        s = self.put([self.first]).json()
        self.assertEqual((len(s['sources']), s['active_source']), (1, 'default'))
        self.assertTrue((self.data / 'sources' / 'second-run' / 'originals' / '9.json').is_file())
        again = self.add_second()   # a new pair with the same name gets a fresh id: old data is not mixed in
        self.assertEqual(again['sources'][1]['id'], 'second-run-2')

    def test_a_changed_source_is_not_overwritten(self):
        (self.run2 / self.res.name).write_text(self.res.read_text(encoding='utf-8').replace('710', '711'), encoding='utf-8')
        self.put([{**self.first, 'run_dir': str(self.run2), 'pdf_dir': str(self.pdfs2)}])
        before = (self.data / 'originals' / '7.json').read_bytes()
        body = self.client.post('/api/v1/ingest').json()
        self.assertEqual({p['paper']: p['outcome'] for p in body['papers']}, {'7': 'changed', '9': 'written'})
        self.assertEqual((self.data / 'originals' / '7.json').read_bytes(), before)
        row = next(p for p in self.client.get('/api/v1/papers').json() if p['paper'] == '7')
        self.assertEqual((row['source_changed'], row['source_problems']), (True, ['result_changed']))

    def test_papers_missing_from_the_new_folders(self):
        only9 = Path(self.tmp.name) / 'only9'
        only9.mkdir()
        shutil.copy(self.run2 / '9-pdf_with_feature_guide.json', only9)
        self.put([{**self.first, 'run_dir': str(only9), 'pdf_dir': str(self.pdfs2)}])
        self.client.post('/api/v1/ingest')
        row = next(p for p in self.client.get('/api/v1/papers').json() if p['paper'] == '7')
        self.assertEqual(row['source_problems'], ['result_missing'])   # reviewed papers are never removed

    def test_sources_untouched(self):
        before = {p.name: sha(p) for p in list(self.run2.iterdir()) + list(self.pdfs2.iterdir())}
        self.add_second()
        self.client.post('/api/v1/sources/second-run/ingest')
        self.client.get('/api/v1/sources/second-run/papers/9/pages/1/image')
        self.assertEqual({p.name: sha(p) for p in list(self.run2.iterdir()) + list(self.pdfs2.iterdir())}, before)


if __name__ == '__main__':
    unittest.main()
