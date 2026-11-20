"""Real offline pip-tools resolution over local wheels; no installed packages changed."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from parsing.unified import environment as env


def wheel(directory, name, *, requires=()):
    normalized = name.replace('-', '_')
    filename = directory/(normalized+'-1.0-py3-none-any.whl')
    dist = normalized+'-1.0.dist-info/'
    metadata = 'Metadata-Version: 2.1\nName: '+name+'\nVersion: 1.0\nRequires-Python: >=3.10\n'
    metadata += ''.join('Requires-Dist: '+item+'\n' for item in requires)
    with zipfile.ZipFile(filename,'x') as stream:
        stream.writestr(dist+'METADATA',metadata+'\n')
        stream.writestr(dist+'WHEEL','Wheel-Version: 1.0\nGenerator: offline-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        stream.writestr(dist+'RECORD','')
    return filename


class ResolverTests(unittest.TestCase):
    def test_resolution_uses_requested_interpreter_and_hashes_complete_local_closure(self):
        if importlib.util.find_spec('piptools') is None:
            self.skipTest('pip-tools unavailable locally; real resolution must run on the target host')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root=Path(temporary);wheels=root/'wheels';wheels.mkdir()
            child=wheel(wheels,'hybrid-fixture-child')
            parent=wheel(wheels,'hybrid-fixture-parent',requires=['hybrid-fixture-child==1.0'])
            candidate=root/'candidate.in';output=root/'resolved.lock'
            candidate.write_text('--extra-index-url https://download.pytorch.org/whl/cu126\n'
                                 '--find-links '+wheels.as_uri()+'\nhybrid-fixture-parent==1.0\n',encoding='utf-8')
            commands=[]
            def run(command):
                commands.append(command)
                self.assertEqual(Path(command[0]).resolve(),Path(sys.executable).resolve())
                self.assertEqual(command[1:3],['-m','piptools'])
                environment=dict(os.environ,PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',
                                 TEMP=str(root),TMP=str(root),TMPDIR=str(root))
                result=subprocess.run(list(map(str,command)),env=environment,text=True,
                                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode,0,result.stdout)
            env.resolve_lock(Path(sys.executable),candidate,output,run)
            locked=output.read_text(encoding='utf-8')
            self.assertIn('hybrid-fixture-parent==1.0',locked)
            self.assertIn('hybrid-fixture-child==1.0',locked)
            for path in (parent,child):
                self.assertIn('--hash=sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),locked)
            self.assertIn('--extra-index-url https://download.pytorch.org/whl/cu126',locked)
            self.assertEqual(len(commands),1)
            with self.assertRaises(FileNotFoundError):
                env.resolve_lock(root/'missing-target-python',candidate,root/'wrong.lock',
                                 lambda command: subprocess.run(list(map(str,command)),check=True))
            self.assertFalse((root/'wrong.lock').exists())


if __name__=='__main__':
    unittest.main()
