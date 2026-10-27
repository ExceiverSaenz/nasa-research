"""Offline contracts for one user-executed Table 1 header experiment."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from page_integration.header_roi import header_roi,prepare_header,unpack_header
from page_integration.workflow import ROOT


class HeaderTests(unittest.TestCase):
    def target(self):
        return dict(object_id='t',bbox=[112,154,1564,428],caption_bbox=[112.472,202.86,942.78,229.32],
                    body_bbox=[114.126,231.525,1563.03,427.77],status='ready',
                    transform={'operation':'crop_only'})

    def test_header_is_derived_from_caption_and_existing_barrier_not_reference(self):
        target=self.target();before=copy.deepcopy(target)
        result=header_roi(target,1654,2205)
        self.assertEqual(result['bbox'],[112,154,943,230])
        self.assertEqual(result['transform']['size_px'],[831,76])
        self.assertEqual(target,before)
        target['caption_bbox'][2]=800.1
        self.assertEqual(header_roi(target,1654,2205)['bbox'][2],801)

    def test_invalid_context_or_overlap_with_body_is_rejected(self):
        for mutate in [lambda t:t.update(status='roi_ambiguous'),
                       lambda t:t['bbox'].__setitem__(1,210),
                       lambda t:t['body_bbox'].__setitem__(1,220)]:
            target=self.target();mutate(target)
            with self.assertRaises(ValueError):header_roi(target,1654,2205)

    def test_package_is_one_crop_with_original_settings_and_no_reference(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            dest=Path(temp)/'package';plan=prepare_header(dest)
            self.assertEqual(len(plan['targets']),1)
            self.assertEqual(plan['targets'][0]['object_id'],'p0-b2')
            self.assertEqual(plan['targets'][0]['bbox'],[112,154,943,230])
            with zipfile.ZipFile(dest/'upload.zip') as z,zipfile.ZipFile(ROOT/'code/results/mineru-page/20261023T202636Z/result.zip') as original:
                self.assertEqual(z.read('plan.json'),(dest/'plan.json').read_bytes())
                self.assertEqual([n for n in z.namelist() if n.endswith('.png')],['inputs/p0-b2.png'])
                self.assertFalse(any('reference' in n for n in z.namelist()))
                for n in ['config.yaml','requirements.lock','requirements-freeze.txt','model-manifest.json','model-download-receipt.json']:
                    self.assertEqual(z.read(n),original.read(n))
            unpack_header(dest/'upload.zip',dest/'upload.sha256',Path(temp)/'unpacked')
            with self.assertRaises(FileExistsError):prepare_header(dest)
            with self.assertRaises(FileExistsError):unpack_header(dest/'upload.zip',dest/'upload.sha256',Path(temp)/'unpacked')

    def test_tampered_or_extra_member_never_extracts(self):
        import hashlib
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            dest=Path(temp)/'package';prepare_header(dest)
            with zipfile.ZipFile(dest/'upload.zip','a') as z:z.writestr('../bad','x')
            (dest/'upload.sha256').write_text(hashlib.sha256((dest/'upload.zip').read_bytes()).hexdigest())
            with self.assertRaises(ValueError):unpack_header(dest/'upload.zip',dest/'upload.sha256',Path(temp)/'unpacked')
            self.assertFalse((Path(temp)/'unpacked').exists())


if __name__=='__main__':unittest.main()
