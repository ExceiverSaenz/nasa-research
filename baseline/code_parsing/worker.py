"""Future Colab phases. Never invoked by --plan or package imports."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import time
import hashlib
import io
import urllib.request
import zipfile

from .common import ROOT, digest, file_manifest, IntegrityService, write_json

from .contracts import Downloader, Integrity, CommandRunner
from .parsing import CONFIG, DoclingConverterFactory, PaperParser
from .r2 import R2Client


class PlatformValidator:
    def __init__(self, root=ROOT, *, runner: CommandRunner | None = None):
        self.root = Path(root)
        self.runner = runner if runner is not None else subprocess.run

    def validate(self):
        if sys.platform != 'linux' or platform.machine() != 'x86_64' or platform.python_version() != '3.11.16':
            raise RuntimeError('Requires Linux x86_64 CPython 3.11.16; provide the pinned interpreter')
        import torch
        if torch.__version__ != '2.7.1+cu126' or torch.version.cuda != '12.6' or not torch.cuda.is_available():
            raise RuntimeError('Pinned CUDA Torch unavailable')
        gpu = torch.cuda.get_device_name(0)
        if 'A100' not in gpu: raise RuntimeError('A100 required')
        driver = self.runner(
            ['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],
            check=True, stdout=subprocess.PIPE, text=True,
        ).stdout.splitlines()[0].strip()
        if tuple(map(int, driver.split('.'))) < (560,28,3): raise RuntimeError('Driver below baseline policy')
        import onnxruntime
        if 'CPUExecutionProvider' not in onnxruntime.get_available_providers(): raise RuntimeError('OCR CPU provider missing')
        versions = {d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}
        for line in (self.root/'requirements.lock').read_text().splitlines():
            match = re.match(r'^([\w-]+)(?:\[[^]]+\])?==([^ ;\\]+)', line)
            if match and versions.get(match[1].lower()) != match[2]: raise RuntimeError('Installed pin mismatch: '+match[1])
        if versions.get('torchvision') != '0.22.1+cu126': raise RuntimeError('torchvision mismatch')
        if any(n in versions for n in ('opencv-python','opencv-contrib-python','opencv-contrib-python-headless','onnxruntime-gpu')):
            raise RuntimeError('Conflicting image/OCR distribution')
        self.runner([sys.executable,'-m','pip','check'], check=True)
        return dict(python=platform.python_version(), platform=platform.platform(), glibc=platform.libc_ver(),
                    gpu=gpu, vram_bytes=torch.cuda.get_device_properties(0).total_memory,
                    driver=driver, cuda=torch.version.cuda, packages=versions)

class PythonProvisioner:
    def __init__(self, root=ROOT, *, runner: CommandRunner | None = None, opener=None):
        self.root = Path(root)
        self.runner = runner if runner is not None else subprocess.run
        self.opener = opener if opener is not None else urllib.request.urlopen

    def bootstrap_uv(self, runtime):
        # Colab's system Python can lack ensurepip. uv's wheel is dependency-free;
        # install only its executable after enforcing the unchanged bootstrap lock.
        lock=(self.root/'bootstrap.lock').read_text()
        version=re.search(r'^uv==([^\s]+)',lock,re.M).group(1)
        allowed=set(re.findall(r'--hash=sha256:([a-f0-9]{64})',lock))
        with self.opener('https://pypi.org/pypi/uv/'+version+'/json',timeout=120) as stream:
            metadata=json.load(stream)
        files=[p for p in metadata['urls'] if p['digests']['sha256'] in allowed and p['filename'].endswith('.whl')]
        if len(files)!=1: raise ValueError('Bootstrap wheel not uniquely allowed by lock')
        with self.opener(files[0]['url'],timeout=120) as stream: data=stream.read()
        if hashlib.sha256(data).hexdigest() not in allowed: raise ValueError('Bootstrap uv SHA256 mismatch')
        bootstrap=runtime/'bootstrap'; bootstrap.mkdir()
        with zipfile.ZipFile(io.BytesIO(data)) as wheel:
            candidates=[n for n in wheel.namelist() if n.endswith('/uv')]
            if len(candidates)!=1: raise ValueError('Unexpected uv wheel layout')
            binary=bootstrap/'uv'; binary.write_bytes(wheel.read(candidates[0])); binary.chmod(0o755)
        write_json(runtime/'bootstrap-receipt.json',dict(version=version,wheel=files[0]['filename'],
            wheel_sha256=hashlib.sha256(data).hexdigest(),executable_sha256=digest(binary),
            bootstrap_lock_sha256=digest(self.root/'bootstrap.lock')))
        return binary

    def provision(self, runtime):
        uv=str(self.bootstrap_uv(runtime))
        env=dict(os.environ,UV_PYTHON_INSTALL_DIR=str(runtime/'python'),UV_CACHE_DIR=str(runtime/'uv-cache'))
        installed=self.runner([uv,'--no-config','python','install','3.11.16'],env=env,check=True,
                                 text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        result=self.runner([uv,'--no-config','python','find','--managed-python','3.11.16'],
                              env=env,check=True,text=True,stdout=subprocess.PIPE)
        python=Path(result.stdout.strip())
        if not python.is_file(): raise RuntimeError('Pinned Python was not provisioned')
        write_json(runtime/'python-provision.json',dict(version='3.11.16',installer='uv 0.12.21',
            source='uv managed CPython / astral-sh/python-build-standalone',
            bootstrap_lock_sha256=digest(self.root/'bootstrap.lock'),executable=str(python),
            executable_sha256=digest(python),installer_output=installed.stdout))
        return python

class EnvironmentPreparer:
    def __init__(self, root=ROOT, *, integrity=None, platform_validator=None, provisioner=None, runner=None):
        self.root = Path(root)
        self.runtime = self.root/'runtime'
        self.runner = runner if runner is not None else subprocess.run
        self.integrity = integrity if integrity is not None else IntegrityService(self.root)
        self.platform = platform_validator if platform_validator is not None else PlatformValidator(self.root, runner=self.runner)
        self.provisioner = provisioner if provisioner is not None else PythonProvisioner(self.root, runner=self.runner)

    def prepare(self):
        self.integrity.verify_lock()
        if sys.platform != 'linux' or platform.machine() != 'x86_64': raise RuntimeError('Requires Linux x86_64')
        self.runtime.mkdir(exist_ok=False)
        python=self.provisioner.provision(self.runtime)
        env = self.runtime/'environment'
        if env.exists(): raise FileExistsError('Environment already exists; inspect before retrying')
        self.runner([str(python),'-m','venv',str(env)], check=True)
        python = env/'bin/python'
        self.runner([str(python),'-m','pip','install','--require-hashes','--only-binary=:all:',
                        '--index-url','https://pypi.org/simple','-r',str(self.root/'requirements.lock')], check=True)
        self.runner([str(python),'-B','-m','baseline.code_parsing.worker','seal'], cwd=self.root.parent, check=True)

    def seal(self):
        from docling.utils.model_downloader import download_models
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        from docling.models.stages.ocr.rapid_ocr_model import _resolve_rapidocr_language
        from rapidocr.utils.typings import LangDet, LangRec, ModelType, OCRVersion
        if _resolve_rapidocr_language(['en']) != 'english': raise RuntimeError('OCR language API probe failed')
        environment = self.platform.validate(); start = time.perf_counter()
        # Persist diagnostics even when model acquisition fails.
        write_json(self.runtime/'platform-probe.json',environment)
        models = self.runtime/'models'
        print('Platform and OCR API validated; preparing layout, tables and formulas.',flush=True)
        download_models(output_dir=models, with_layout=True, with_tableformer=True,
                        with_code_formula=True, with_picture_classifier=False,
                        with_rapidocr=False, with_easyocr=False)
        # Docling 2.117.0 predates selective rapidocr_models on the bulk downloader.
        # Its OCR class supports selecting English/ONNX explicitly.
        print('Preparing English ONNX OCR models.',flush=True)
        RapidOcrModel.download_models(backend='onnxruntime',lang='english',
                                     local_dir=models/RapidOcrModel._model_repo_folder)
        write_json(self.runtime/'models.json', file_manifest(models))
        environment.update(lock_sha256=self.integrity.verify_lock()['lock_sha256'],
                           model_preparation_seconds=time.perf_counter()-start,
                           models_manifest_sha256=digest(self.runtime/'models.json'))
        environment['python_provision']=json.loads((self.runtime/'python-provision.json').read_text())
        write_json(self.runtime/'environment.json', environment)

class BatchProcessor:
    def __init__(self, root=ROOT, *, integrity: Integrity | None = None, platform_validator=None,
                 downloader: Downloader | None = None, converter_factory=None, parser_factory=None):
        self.root = Path(root)
        self.runtime = self.root/'runtime'
        self.integrity = integrity if integrity is not None else IntegrityService(self.root)
        self.platform = platform_validator if platform_validator is not None else PlatformValidator(self.root)
        self.downloader = downloader if downloader is not None else R2Client()
        self.converter_factory = converter_factory if converter_factory is not None else lambda models: DoclingConverterFactory(models).create()
        self.parser_factory = parser_factory if parser_factory is not None else lambda converter: PaperParser(converter, integrity=self.integrity)

    def parse(self, request_path):
        output=self.root/'results'; output.mkdir(exist_ok=False)
        status=dict(schema='baseline-batch/1', status='running', papers=[], configuration=CONFIG)
        try:
            self.integrity.verify_lock(); observed=self.platform.validate()
            environment=json.loads((self.runtime/'environment.json').read_text())
            if any(observed[k]!=environment[k] for k in ('python','packages','driver','gpu')):
                raise ValueError('Sealed environment changed')
            if environment['lock_sha256'] != self.integrity.verify_lock()['lock_sha256']: raise ValueError('Lock changed')
            model_manifest=json.loads((self.runtime/'models.json').read_text())
            if digest(self.runtime/'models.json') != environment['models_manifest_sha256'] or file_manifest(self.runtime/'models') != model_manifest:
                raise ValueError('Sealed models changed')
            write_json(output/'environment.json',environment)
            write_json(output/'models.json',model_manifest)
            request=json.loads(Path(request_path).read_text())
            try: papers=self.downloader.download(request,self.root/'inputs')
            finally: Path(request_path).unlink(missing_ok=True)
            write_json(output/'inputs.json',papers)
            os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
            converter=self.converter_factory(self.runtime/'models')
            parser = self.parser_factory(converter)
            for paper in papers:
                result=parser.parse(self.root/'inputs'/paper['name'],output/'papers',
                                   environment,environment['models_manifest_sha256'])
                status['papers'].append(dict(paper,status=result['status']))
            if file_manifest(self.runtime/'models') != model_manifest: raise ValueError('Model artifacts changed during parsing')
            status['status']='completed' if all(p['status']=='completed' for p in status['papers']) else 'partial'
        except Exception as exc:
            message=re.sub(r'https?://[^\s\x27\x22]+','<redacted-url>',str(exc))
            status.update(status='failed', error=type(exc).__name__+': '+message)
        finally:
            Path(request_path).unlink(missing_ok=True)
            write_json(output/'status.json',status)
            write_json(output/'files.json',file_manifest(output))
            archive=self.root.parent/'baseline-results.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                for path in sorted(output.rglob('*')):
                    if path.is_file(): tar.add(path,arcname=path.relative_to(output).as_posix(),recursive=False)
            (self.root.parent/'baseline-results.sha256').write_text(digest(archive))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','seal','parse'])
    parser.add_argument('--run-id',default='manual')
    parser.add_argument('--request',type=Path,default=Path('/content/baseline-request.json'))
    args=parser.parse_args(argv)
    if args.phase=='prepare': EnvironmentPreparer().prepare()
    elif args.phase=='seal': EnvironmentPreparer().seal()
    else: BatchProcessor().parse(args.request)
    print('BASELINE_COMPLETED:'+args.run_id+':'+args.phase,flush=True)

if __name__=='__main__': main()
