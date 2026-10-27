import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from document_trial.inventory import collect, package_map, clean_inventory
from document_trial.common import check_runtime

class InventoryTests(unittest.TestCase):
    def entry(self,version='26.3',path='/env/packaging.dist-info'):
        return dict(name='packaging',version=version,metadata_path=path,root_path='/env')

    def test_duplicates_preserved_and_conflicting_locations_rejected(self):
        entries=[self.entry(),self.entry('24.2','/env/setuptools/_vendor/packaging.dist-info')]
        snapshot=dict(distributions=entries)
        with self.assertRaisesRegex(ValueError,'Ambiguous'):package_map(snapshot)
        self.assertEqual(len(snapshot['distributions']),2)

    def test_same_version_at_different_locations_is_preserved(self):
        snapshot=dict(distributions=[self.entry(),self.entry(path='/other/packaging.dist-info')])
        self.assertEqual(package_map(snapshot),{'packaging':'26.3'})
        self.assertEqual(len(snapshot['distributions']),2)

    def test_repeated_same_location_kept_but_not_false_conflict(self):
        snapshot=dict(distributions=[self.entry(),self.entry()])
        self.assertEqual(package_map(snapshot),{'packaging':'26.3'})
        self.assertEqual(len(snapshot['distributions']),2)

    def test_real_version_drift_and_extra_package_still_fail(self):
        spec=dict(python='3.9.25',cuda='11.1',packages={'packaging':'26.3'})
        for packages in [{'packaging':'24.2'},{'packaging':'26.3','unexpected':'1'}]:
            with self.assertRaises(ValueError):check_runtime(dict(python='3.9.25',cuda='11.1',gpu='Tesla T4',packages=packages),spec)

    def test_missing_provenance_is_rejected(self):
        entry=self.entry();entry['metadata_path']=None
        with self.assertRaises(ValueError):package_map(dict(distributions=[entry]))

    def test_probe_compares_clean_inventory_and_preserves_post_import_duplicates(self):
        from document_trial import worker
        clean=dict(distributions=[self.entry()])
        after=dict(distributions=[self.entry(),self.entry('24.2','/env/setuptools/_vendor/packaging.dist-info')])
        spec=dict(python='3.9.25',cuda='11.1',packages={'packaging':'26.3'})
        fake_torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True,get_device_name=lambda n:'Tesla T4'),version=SimpleNamespace(cuda='11.1'))
        with patch.dict(sys.modules,{'torch':fake_torch}),patch.object(worker,'clean_inventory',return_value=clean),patch.object(worker,'collect',return_value=after),patch.object(worker,'read',return_value={'models':{'layoutlmv3':spec}}),patch.object(worker.platform,'python_version',return_value='3.9.25'),patch.object(worker,'save') as saved:
            result=worker.probe('layoutlmv3',Path('/inputs'),Path('/state'))
            self.assertEqual(result['packages'],{'packaging':'26.3'})
            self.assertEqual(saved.call_args_list[0].args[1],after)
            clean['distributions'][0]['version']='24.2'
            with self.assertRaisesRegex(ValueError,'INCOMPATIBLE'):worker.probe('layoutlmv3',Path('/inputs'),Path('/state'))

    def test_actual_clean_child_does_not_inherit_parent_vendor_path(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root=Path(folder);vendor=root/'vendor';meta=vendor/'nasa_inventory_fixture-1.dist-info';meta.mkdir(parents=True)
            (meta/'METADATA').write_text('Metadata-Version: 2.1\nName: nasa-inventory-fixture\nVersion: 1\n',encoding='utf-8')
            with patch.object(sys,'path',sys.path+[str(vendor)]):
                parent=collect()
                self.assertTrue(any(d['name']=='nasa-inventory-fixture' for d in parent['distributions']))
                child=clean_inventory(root,'fixture')
            self.assertFalse(any(d['name']=='nasa-inventory-fixture' for d in child['distributions']))
            self.assertNotEqual(child['pid'],os.getpid())
            self.assertFalse(child['torch_imported'])
            self.assertTrue(all(d['metadata_path'] and d['root_path'] for d in child['distributions']))
            self.assertTrue((root/'inventory-fixture-preflight-clean.json').is_file())

if __name__=='__main__':unittest.main()
