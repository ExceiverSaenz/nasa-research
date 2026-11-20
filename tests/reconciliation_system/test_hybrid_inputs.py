"""Hybrid native adapter contract tests; synthetic data, no inference."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
import zipfile
import warnings

from integration.hybrid_inputs import load_run


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def seal_run(run):
    """Fixture-only sealing of intentionally constructed native parser outputs."""
    archive = run.with_name(run.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as saved:
        for path in sorted(run.rglob('*')):
            if path.is_file(): saved.write(path, path.relative_to(run).as_posix())
    archive.with_suffix('.zip.sha256').write_text(digest(archive) + '  ' + archive.name + '\n', encoding='ascii')
    return archive


def png(width=200, height=100):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff' * width * 3) * height)) + chunk(b'IEND', b''))


def fixture(root, *, count=1, missing_child=False):
    run = root / 'parser-attempt'
    inputs, tuples = [], []
    for n in range(count):
        pdf = root / ('Research paper ' + str(n) + '.pdf')
        pdf.write_bytes(b'%PDF-1.4\nsynthetic fixture ' + str(n).encode())
        sha = digest(pdf)
        pid = 'Research-paper-' + str(n) + '-' + sha
        inputs.append(dict(id=pid, path=str(pdf), sha256=sha, page_count=1))
        folder = run / 'renders' / pid / '1'
        folder.mkdir(parents=True)
        render = folder / 'render.png'
        render.write_bytes(png())
        geometry = dict(dpi=200, width_px=200, height_px=100, color='RGB',
                        crop_box_pt=[0, 0, 72, 36], rotation_deg=0,
                        coordinate_system=dict(unit='pixel', origin='top-left', bbox_format='xyxy'),
                        pdf_to_render_matrix=[[200/72, 0, 0], [0, -100/36, 100], [0, 0, 1]],
                        render_to_pdf_matrix=[[72/200, 0, 0], [0, -36/100, 36], [0, 0, 1]])
        identity = dict(document_sha256=sha, physical_page=1, render_sha256=digest(render),
                        width_px=200, height_px=100, dpi=200, geometry=geometry)
        write(folder / 'identity.json', identity)
        blocks = [dict(type='text', bbox=[0.1, 0.1, 0.9, 0.3], content='Research text')]
        derived = [dict(source_pointer='/pages/0/blocks/0', bbox_normalized=blocks[0]['bbox'], bbox=[20., 10., 180., 30.])]
        if missing_child:
            blocks = [dict(type='image', bbox=[0.1, 0.1, 0.9, 0.9], content=[dict(type='image_body', bbox=None)])]
            derived = [dict(source_pointer='/pages/0/blocks/0', bbox_normalized=blocks[0]['bbox'], bbox=[20., 10., 180., 90.]),
                       dict(source_pointer='/pages/0/blocks/0/content/0', bbox_normalized=None, bbox=None)]
        native = dict(schema='docvortex.middle', schema_version='2.0', metadata=dict(producer=dict(name='mineru', version='4.0.12')),
                      pages=[dict(page_idx=0, blocks=blocks)])
        for engine in ('layoutlmv3', 'table_transformer', 'mineru'):
            out = run / 'results' / pid / '1' / engine
            write(out / 'identity.json', identity)
            tuples.append(dict(paper_id=pid, page=1, model=engine, status='completed',
                               result=dict(status='completed', model=engine, identity=identity)))
            if engine == 'layoutlmv3':
                write(out / 'regions.json', dict(document_id=sha, page=1, coordinate_system=geometry,
                                                regions=[dict(type='text', bbox=[20, 10, 180, 30], score=0.9)]))
            elif engine == 'table_transformer':
                write(out / 'regions.json', dict(coordinate_system=identity, regions=[]))
            else:
                write(out / 'middle-native.json', native)
                write(out / 'regions.json', dict(coordinate_system=dict(width_px=200, height_px=100, unit='pixel', origin='top-left',
                                                                      bbox_format='xyxy', native_bbox='normalized [0,1]'), regions=derived))
    write(run / 'inputs.json', inputs)
    write(run / 'status.json', dict(status='completed', error=None, tuples=tuples,
                                   runtime_fingerprint='a'*64, package_fingerprint='b'*64, env_manifest_sha256='c'*64))
    seal_run(run)
    return run


class HybridInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_multiple_named_papers_native_provenance_and_read_only(self):
        run = fixture(self.root, count=2)
        before = {str(p): digest(p) for p in self.root.rglob('*') if p.is_file()}
        collection = load_run(run)
        self.assertEqual(len(collection['documents']), 2)
        self.assertEqual(collection['adapter'], 'hybrid-parser-input/1')
        for document in collection['documents']:
            self.assertEqual(document['id'], document['paper_id'])
            self.assertEqual(len(document['pages'][0]['records']), 2)
            self.assertTrue(all(digest(p) == sha for p, sha in document['source_inputs'].items()))
            self.assertEqual(document['pages'][0]['adapter'], 'canonical-v1')
        self.assertEqual(before, {str(p): digest(p) for p in self.root.rglob('*') if p.is_file()})

    def test_partial_run_and_missing_tuple_are_rejected(self):
        run = fixture(self.root)
        path = run / 'status.json'; status = json.loads(path.read_bytes())
        status['status'] = 'failed'; write(path, status)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Only completed'): load_run(run)
        status['status'] = 'completed'; status['tuples'].pop(); write(path, status)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Missing page/engine'): load_run(run)

    def test_duplicate_and_cross_paper_tuples_are_rejected(self):
        run = fixture(self.root)
        path = run / 'status.json'; status = json.loads(path.read_bytes())
        status['tuples'].append(copy.deepcopy(status['tuples'][0])); write(path, status)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Duplicate or out-of-scope'): load_run(run)
        status['tuples'].pop(); status['tuples'][0]['paper_id'] = 'other-paper'; write(path, status)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Duplicate or out-of-scope'): load_run(run)

    def test_pdf_and_render_hash_corruption_rejected(self):
        run = fixture(self.root)
        pdf = Path(json.loads((run/'inputs.json').read_bytes())[0]['path'])
        original = pdf.read_bytes(); pdf.write_bytes(original+b'changed')
        with self.assertRaises(ValueError): load_run(run)
        pdf.write_bytes(original)
        render = next((run/'renders').rglob('render.png')); render.write_bytes(png(10, 10))
        with self.assertRaises(ValueError): load_run(run)

    def test_engine_identity_and_native_transform_mismatch_rejected(self):
        run = fixture(self.root)
        path = next((run/'results').glob('*/1/layoutlmv3/identity.json'))
        identity = json.loads(path.read_bytes()); original = copy.deepcopy(identity)
        identity['physical_page'] = 2; write(path, identity)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Engine result identity'): load_run(run)
        write(path, original)
        path = next((run/'results').glob('*/1/mineru/regions.json'))
        derived = json.loads(path.read_bytes()); derived['regions'][0]['bbox'][0] = 1; write(path, derived)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'MinerU transform differs'): load_run(run)

    def test_unsafe_id_and_duplicate_pdf_rejected(self):
        run = fixture(self.root)
        path = run/'inputs.json'; inputs = json.loads(path.read_bytes())
        inputs[0]['id'] = '../escape'; write(path, inputs)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Unsafe paper id'): load_run(run)
        inputs[0]['id'] = 'safe'; inputs.append(dict(inputs[0], id='other')); write(path, inputs)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Duplicate/invalid paper identity'): load_run(run)

    def test_missing_child_box_preserved_without_parent_imputation(self):
        run = fixture(self.root, missing_child=True)
        page = load_run(run)['documents'][0]['pages'][0]
        child = next(r for r in page['records'] if r['parent'] is not None)
        self.assertIsNone(child['bbox'])
        self.assertIsNone(child['native_bbox'])
        self.assertIn('invalid_geometry', page['incidents'])

    def test_invalid_geometry_rejected(self):
        run = fixture(self.root)
        path = next((run/'renders').rglob('identity.json'))
        identity = json.loads(path.read_bytes()); identity['geometry']['rotation_deg'] = 45; write(path, identity)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Invalid PDF crop box/rotation'): load_run(run)

    def test_missing_native_file_and_duplicate_json_keys_rejected(self):
        run = fixture(self.root)
        native = next((run/'results').glob('*/1/mineru/middle-native.json'))
        raw = native.read_bytes(); native.unlink()
        with self.assertRaises(FileNotFoundError): load_run(run)
        native.write_bytes(raw)
        path = run/'status.json'
        path.write_text('{"status":"failed","status":"completed"}', encoding='utf-8')
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'): load_run(run)

    def test_two_pages_accounted_with_distinct_physical_identity(self):
        import shutil
        run = fixture(self.root)
        inputs = json.loads((run/'inputs.json').read_bytes()); inputs[0]['page_count'] = 2
        pid = inputs[0]['id']; write(run/'inputs.json', inputs)
        shutil.copytree(run/'renders'/pid/'1', run/'renders'/pid/'2')
        shutil.copytree(run/'results'/pid/'1', run/'results'/pid/'2')
        identity = json.loads((run/'renders'/pid/'2/identity.json').read_bytes())
        identity['physical_page'] = 2
        write(run/'renders'/pid/'2/identity.json', identity)
        status = json.loads((run/'status.json').read_bytes())
        for engine in ('layoutlmv3', 'table_transformer', 'mineru'):
            branch = run/'results'/pid/'2'/engine
            write(branch/'identity.json', identity)
            if engine != 'mineru':
                regions = json.loads((branch/'regions.json').read_bytes())
                if engine == 'layoutlmv3': regions['page'] = 2
                else: regions['coordinate_system'] = identity
                write(branch/'regions.json', regions)
            status['tuples'].append(dict(paper_id=pid, page=2, model=engine, status='completed',
                                        result=dict(status='completed', model=engine, identity=identity)))
        write(run/'status.json', status)
        seal_run(run)
        result = load_run(run)
        pages = result['documents'][0]['pages']
        self.assertEqual([p['identity']['physical_page'] for p in pages], [1, 2])
        self.assertTrue(set(r['id'] for r in pages[0]['records']).isdisjoint(r['id'] for r in pages[1]['records']))

    def test_consistent_but_wrong_render_dimensions_rejected(self):
        run = fixture(self.root)
        render = next((run/'renders').rglob('render.png'))
        render.write_bytes(png(10, 10))
        # Even a hash edited together with all identities cannot hide a size mismatch.
        identity = json.loads(render.with_name('identity.json').read_bytes())
        identity['render_sha256'] = digest(render)
        write(render.with_name('identity.json'), identity)
        for path in (run/'results').rglob('identity.json'): write(path, identity)
        status = json.loads((run/'status.json').read_bytes())
        for item in status['tuples']: item['result']['identity'] = identity
        write(run/'status.json', status)
        seal_run(run)
        with self.assertRaisesRegex(ValueError, 'declared dimensions'): load_run(run)

    def test_native_edit_preserving_identity_is_rejected_against_archive(self):
        run = fixture(self.root)
        path = next((run/'results').glob('*/1/mineru/middle-native.json'))
        data = json.loads(path.read_bytes()); data['pages'][0]['blocks'][0]['content'] = 'tampered text'
        write(path, data)
        with self.assertRaisesRegex(ValueError, 'Archived source differs'): load_run(run)

    def test_missing_archive_and_corrupt_archive_are_rejected(self):
        run = fixture(self.root)
        archive = run.with_name(run.name + '.zip'); raw = archive.read_bytes(); archive.unlink()
        with self.assertRaises(FileNotFoundError): load_run(run)
        archive.write_bytes(raw + b'corruption')
        with self.assertRaisesRegex(ValueError, 'Archive SHA256 mismatch'): load_run(run)

    def test_archive_sidecar_is_protected_and_required(self):
        run = fixture(self.root)
        result = load_run(run)
        archive = run.with_name(run.name + '.zip')
        sidecar = archive.with_suffix('.zip.sha256')
        for document in result['documents']:
            self.assertEqual(document['source_inputs'][str(archive)], digest(archive))
            self.assertEqual(document['source_inputs'][str(sidecar)], digest(sidecar))
        sidecar.unlink()
        with self.assertRaises(FileNotFoundError): load_run(run)

    def test_unsafe_and_duplicate_archive_members_rejected(self):
        run = fixture(self.root)
        archive = run.with_name(run.name + '.zip')
        for bad_name in ('../escape', 'inputs.json'):
            seal_run(run)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(archive, 'a') as saved: saved.writestr(bad_name, b'bad')
            archive.with_suffix('.zip.sha256').write_text(digest(archive) + '  ' + archive.name + '\n', encoding='ascii')
            with self.assertRaisesRegex(ValueError, 'Unsafe archive member|Duplicate archive member'): load_run(run)


if __name__ == '__main__': unittest.main()
