import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from parsing.unified import environment_bundle as bundle


class BundleTests(unittest.TestCase):
    def test_relocates_only_verified_detectron2_url_and_preserves_hash(self):
        text='torch==2.7.1+cu126 \\\n    --hash=sha256:torch\ndetectron2 @ file:///old/detectron2.whl \\\n    --hash=sha256:abc\n'
        value=bundle.relocate_lock(text,'file:///old/detectron2.whl','file:///new/detectron2.whl','abc')
        self.assertEqual(value,text.replace('file:///old/detectron2.whl','file:///new/detectron2.whl'))

    def test_refuses_unrelated_file_url_or_wrong_wheel_hash(self):
        for text in ('detectron2 @ file:///old.whl --hash=sha256:bad\n',
                     'detectron2 @ file:///old.whl --hash=sha256:abc\nother @ file:///other.whl\n'):
            with self.assertRaises(ValueError):
                bundle.relocate_lock(text,'file:///old.whl','file:///new.whl','abc')

    def test_host_mismatch_rejected_in_each_dimension(self):
        expected={'system':'Linux','machine':'x86_64','python':'3.11.16',
                  'os':['ubuntu','24.04'],'libc':['glibc','2.39'],'compute_caps':['8.0']}
        bundle.require_compatible(expected,expected)
        for key in expected:
            with self.subTest(key=key),self.assertRaises(ValueError):
                bundle.require_compatible(expected,dict(expected,**{key:'changed'}))

    def test_receipt_build_identity_is_required(self):
        from parsing.unified import environment as env
        good={'commit':env.D2_COMMIT,'torch':env.CANDIDATE['torch'],'sha256':'abc','wheel':'d.whl'}
        bundle.require_build(good,'d.whl','abc')
        with self.assertRaises(ValueError):bundle.require_build(dict(good,commit='wrong'),'d.whl','abc')

    def test_changed_bundle_file_is_rejected(self):
        from parsing.unified import environment as env
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);(root/'file').write_bytes(b'original')
            data={'schema':'shared-environment-bundle/1','files':{'file':{
                'bytes':8,'sha256':env.sha256(root/'file')}}}
            (root/'bundle.json').write_text(json.dumps(data))
            self.assertEqual(bundle.read_bundle(root),data)
            (root/'file').write_bytes(b'changed!')
            with self.assertRaises(ValueError):bundle.read_bundle(root)

    def test_restore_installs_hashed_lock_once_without_resolver_or_build(self):
        from parsing.unified import environment as env
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);source=root/'source';source.mkdir()
            (source/'wheels').mkdir();wheel=source/'wheels/detectron2.whl';wheel.write_bytes(b'wheel')
            digest=env.sha256(wheel)
            for name in ('requirements.lock','requirements-candidate.in','source-environment.json','bundle.json'):
                (source/name).write_text('{}')
            (source/'requirements-complete.lock').write_text('detectron2 @ file:///old.whl --hash=sha256:'+digest+'\n')
            data={'wheel':'wheels/detectron2.whl','source_wheel_uri':'file:///old.whl'}
            build={'sha256':digest,'commit':env.D2_COMMIT,'compiler':'compiler','cuda_toolkit':'release 12.6'}
            dest=root/'restored';calls=[]
            with patch.object(bundle,'validate_bundle',return_value=(data,build)), \
                 patch.object(bundle.platform,'system',return_value='Linux'), \
                 patch.object(bundle.subprocess,'check_output',return_value=env.PYTHON_VERSION), \
                 patch.object(bundle.subprocess,'run',side_effect=lambda cmd,**kw:calls.append(cmd)), \
                 patch.object(env,'seal_environment',return_value=dest/'environment.json'):
                bundle.restore_bundle(dest,Path('python'),source)
            installs=[cmd for cmd in calls if 'install' in cmd]
            self.assertEqual(len(installs),1)
            self.assertIn('--require-hashes',installs[0]);self.assertIn('--no-deps',installs[0])
            self.assertFalse(any('git' in cmd or 'piptools' in cmd or 'wheel' in cmd for cmd in calls))
            self.assertIn((dest/'wheels/detectron2.whl').as_uri(),(dest/'requirements-complete.lock').read_text())
            self.assertTrue((dest/'reuse-receipt.json').is_file())

    def test_reexport_preserves_previous_source_receipt(self):
        from parsing.unified import environment as env
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);source=root/'installed';source.mkdir();(source/'wheels').mkdir()
            wheel=source/'wheels/detectron2-fixture.whl';wheel.write_bytes(b'wheel')
            (source/'source-environment.json').write_text('older-source-receipt')
            candidate=env.candidate_text(Path(env.__file__).resolve().parents[3]/'requirements.in')
            (source/'requirements-candidate.in').write_text(candidate,encoding='utf-8')
            (source/'requirements.lock').write_text('fixture')
            (source/'requirements-complete.lock').write_text('detectron2 @ '+wheel.as_uri()+' --hash=sha256:'+env.sha256(wheel)+'\n')
            build={'commit':env.D2_COMMIT,'torch':env.CANDIDATE['torch'],'wheel':wheel.name,'sha256':env.sha256(wheel)}
            (source/'detectron2-build-fixture.json').write_text(json.dumps(build))
            files={p.relative_to(source).as_posix():{'bytes':p.stat().st_size,'sha256':env.sha256(p)}
                   for p in source.rglob('*') if p.is_file()}
            (source/'environment.json').write_text(json.dumps({'status':'imports-validated','python':env.PYTHON_VERSION,'artifacts':files}))
            host={'system':'Linux','machine':'x86_64','python':env.PYTHON_VERSION,
                  'os':['ubuntu','24.04'],'libc':['glibc','2.39'],'compute_caps':['8.0']}
            with patch.object(env,'check_runtime'),patch.object(bundle,'host_fingerprint',return_value=host):
                archive=bundle.export_bundle(source,root/'export')
                bundle.validate_bundle(root/'export')
            self.assertTrue(archive.is_file())
            self.assertEqual((root/'export/source-environment.json').read_text(),'older-source-receipt')
            self.assertEqual((root/'export/bundle-source-environment.json').read_bytes(),(source/'environment.json').read_bytes())

    def test_preserves_only_wheels_with_locked_origin_and_seeds_without_overwrite(self):
        from parsing.unified import environment as env
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);cache=root/'cache';folder=cache/'wheels/aa/bb';folder.mkdir(parents=True)
            wheel=folder/'fixture-1.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel,'w') as archive:
                archive.writestr('fixture-1.0.dist-info/METADATA','Name: fixture\nVersion: 1.0\n')
            (folder/'origin.json').write_text(json.dumps({'archive_info':{'hashes':{'sha256':'a'*64}}}))
            output=root/'bundle';output.mkdir()
            source={'versions':{'fixture':'1.0'}}
            with self.assertRaises(ValueError):bundle.preserve_built_wheels(cache,output,source,'fixture==1.0 --hash=sha256:wrong\n')
            names=bundle.preserve_built_wheels(cache,output,source,'fixture==1.0 --hash=sha256:'+'a'*64+'\n')
            data={'cache_files':names,'files':{name:{'bytes':(output/name).stat().st_size,'sha256':env.sha256(output/name)} for name in names}}
            target=root/'new-cache';bundle.seed_wheel_cache(output,data,target)
            bundle.seed_wheel_cache(output,data,target)
            restored=target/'wheels/aa/bb'/wheel.name
            self.assertEqual(restored.read_bytes(),wheel.read_bytes())
            restored.write_bytes(b'changed')
            with self.assertRaises(ValueError):bundle.seed_wheel_cache(output,data,target)


if __name__=='__main__':unittest.main()
