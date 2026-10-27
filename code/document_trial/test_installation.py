"""Offline command construction only; no installer, model or network calls."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from document_trial import remote

class InstallationTests(unittest.TestCase):
    def test_all_three_pinned_installations_use_explicit_index_strategy(self):
        calls=[]
        def capture(arguments,state,**kwargs):
            if kwargs.get('stage','').endswith(':probe'):raise RuntimeError('offline-stop-before-probe')
            calls.append(list(map(str,arguments)))
        plan=dict(execution_policy='USER_ONLY_COLAB_CLI_T4',automatic_recovery=False,automatic_retries=False,
                  models={m:dict(python=v) for m,v in zip(remote.MODELS,['3.9.25','3.11.11','3.11.16'])})
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            inputs=Path(folder)/'inputs';(inputs/'mineru').mkdir(parents=True);(inputs/'mineru/config.yaml').write_bytes(b'original-config')
            with patch.object(remote,'PREFIX',Path(folder)/'state'),patch.object(remote,'read',return_value=plan),patch.object(remote,'run_logged',side_effect=capture),patch.object(remote.shutil,'copytree'),patch.object(Path,'exists',return_value=False),patch.object(Path,'mkdir'),patch.object(Path,'write_bytes'):
                with self.assertRaisesRegex(RuntimeError,'offline-stop-before-probe'):remote.setup(inputs,Path(folder)/'state')
        installs=[a for a in calls if '--no-build-isolation' in a or '--require-hashes' in a]
        self.assertEqual(len(installs),3)
        for args in installs:
            self.assertEqual(args.count('--index-strategy'),1)
            self.assertEqual(args[args.index('--index-strategy')+1],'unsafe-best-match')
        for args in installs[:2]:
            self.assertIn('--no-deps',args);self.assertIn('--no-build-isolation',args)
            self.assertEqual(args[args.index('--extra-index-url')+1],'https://download.pytorch.org/whl/cu121')
        self.assertIn('--require-hashes',installs[2]);self.assertIn('--only-binary',installs[2])
        self.assertEqual(installs[2][installs[2].index('--extra-index-url')+1],'https://download.pytorch.org/whl/cu126')

if __name__=='__main__':unittest.main()
