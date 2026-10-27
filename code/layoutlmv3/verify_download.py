"""Verify downloaded archive integrity and installer status without extracting."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def verify(archive):
    archive = Path(archive)
    expected = archive.with_suffix('.sha256').read_text(encoding='ascii').split()[0]
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('SHA-256 incorrecto; vuelve a descargar antes de detener la VM.')
    with zipfile.ZipFile(archive) as zipped:
        invalid = zipped.testzip()
        if invalid:
            raise ValueError('Miembro ZIP corrupto: ' + invalid)
        status = json.loads(zipped.read('job-status.json'))
    print('Integridad del respaldo verificada:', archive)
    if status['returncode'] != 0:
        raise RuntimeError('Instalacion fallida, codigo %s. Los diagnosticos estan respaldados.' % status['returncode'])
    print('Instalador completado. Alcance:', status.get('scope', 'consultar registros'))
    return status


if __name__ == '__main__':
    verify(sys.argv[1])
