"""USER ONLY controller: one padded header, original parser, passive traces."""
import hashlib
from pathlib import Path
import platform
import sys
import traceback
import zipfile

PREFIX='/content/nasa-table1-square-v1'


def main():
    if platform.system()!='Linux' or not Path('/content').is_dir():raise RuntimeError('Colab Linux only; local OCR forbidden')
    bundle=Path(PREFIX+'-upload.zip');sidecar=Path(PREFIX+'-upload.sha256')
    inputs=Path(PREFIX+'-inputs');state=Path(PREFIX);archive=Path(PREFIX+'.zip')
    for p in (inputs,state,archive,archive.with_suffix('.sha256')):
        if p.exists():raise FileExistsError('Previous evidence exists; no automatic retry: '+str(p))
    if hashlib.sha256(bundle.read_bytes()).hexdigest()!=sidecar.read_text().strip():raise ValueError('Square bundle mismatch')
    from page_integration.square_roi import unpack_square
    from page_integration.workflow import save,file_hash
    from page_integration.remote_labels import setup_and_run
    unpack_square(bundle,sidecar,inputs)
    sys.path.insert(0,str(inputs));state.mkdir(exist_ok=False)
    status=dict(status='failed',ocr_scope='single_table1_square_header_ROI',initiator='human_colab_cli',error=None)
    try:
        setup_and_run(inputs,state,experiment='table1-square-v1')
        status['status']='completed'
    except Exception:
        status['error']=traceback.format_exc();(state/'error.log').write_text(status['error'],encoding='utf-8')
        print(status['error'],file=sys.stderr)
    finally:
        save(state/'execution-status.json',status)
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for path in sorted(state.rglob('*')):
                if path.is_file() and not path.is_symlink():z.write(path,path.relative_to(state).as_posix())
        archive.with_suffix('.sha256').write_text(file_hash(archive)+'\n',encoding='ascii')
        print('SQUARE_ARCHIVE_READY',status['status'],flush=True)
    if status['status']!='completed':raise SystemExit(1)


if __name__=='__main__':main()
