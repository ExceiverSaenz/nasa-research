"""API keys in annotations/secrets.json (52-models-keys-interface-contract.md; ADR-020).

The file is apart from settings.json so it never travels with settings or exports. It is written atomically, with
owner-only permissions where the system has them (0600 on Linux and in Docker; on Windows the file inherits the user
profile's permissions). A key is never returned by the service, logged or put in an error message: only its last 4
characters leave this module through ``public``.
"""
import json
import os
import secrets as _random
import threading
from pathlib import Path

from .. import schemas
from .atomic import StorageError, reason

FORMAT = 'value-review-secrets/1'


def _empty():
    return {'schema': FORMAT, 'keys': []}


def public(entry):
    """A key's entry as the API shows it: everything but the key itself."""
    return {'id': entry['id'], 'provider': entry['provider'], 'name': entry['name'], 'last4': entry['key'][-4:],
            'url': entry.get('url', ''), 'monthly_limit_usd': entry.get('monthly_limit_usd'), 'spent_usd': 0,
            'default': entry['default'], 'added_at': entry['added_at'], 'tested_at': entry['tested_at'],
            'models_found': len(entry.get('models', []))}


class SecretStore:
    def __init__(self, folder):
        self.path = Path(folder) / 'secrets.json'
        self.lock = threading.RLock()   # every read-modify-write of the file holds it

    def read(self):
        """The file's content ({keys: []} when missing). A damaged file is reported, never repaired or replaced."""
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return _empty()
        except (OSError, ValueError) as error:
            raise StorageError(f'secrets.json cannot be read: {type(error).__name__}') from None
        errs = schemas.errors('secrets', data)
        if errs:
            raise StorageError(f'secrets.json does not match its schema at {errs[0][0] or "/"}') from None
        return data

    def write(self, data):
        """Replace the file atomically; the temporary file is created owner-only, so the key is never readable by
        others, not even for a moment."""
        errs = schemas.errors('secrets', data)
        if errs:   # a bug, not a client error
            raise RuntimeError(f'secrets would not validate at {errs[0][0]}')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f'{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
        body = (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_BINARY', 0), 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
            if os.name == 'posix':
                os.chmod(self.path, 0o600)
        except OSError as error:
            try:
                temp.unlink()
            except OSError:
                pass
            raise StorageError(f'Could not write secrets.json: {reason(error)}') from None

    @staticmethod
    def new_id(data):
        taken = {k['id'] for k in data['keys']}
        while True:
            kid = 'k_' + _random.token_hex(4)
            if kid not in taken:
                return kid
