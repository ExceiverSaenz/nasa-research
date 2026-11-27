"""What each API key spent per month (annotations/spending.json; ADR-029).

``{"schema": "value-review-spending/1", "keys": {"<key id>": {"YYYY-MM": usd}}}``. Runs add their actual cost after
each paper; Settings and the run checks read it. A file that cannot be read counts as nothing spent and is left as it is.
"""
import json
import threading
from pathlib import Path

from .atomic import atomic_write_bytes

FORMAT = 'value-review-spending/1'


class SpendingStore:
    def __init__(self, folder):
        self.path = Path(folder) / 'spending.json'
        self.lock = threading.Lock()

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'schema': FORMAT, 'keys': {}}
        keys = data.get('keys') if isinstance(data, dict) else None
        return {'schema': FORMAT, 'keys': keys if isinstance(keys, dict) else {}}

    def spent(self, key_id, month):
        """Dollars ``key_id`` spent in ``month`` ("YYYY-MM")."""
        value = self._read()['keys'].get(key_id, {})
        value = value.get(month, 0) if isinstance(value, dict) else 0
        return float(value) if isinstance(value, (int, float)) else 0.0

    def add(self, key_id, month, usd):
        if not usd:
            return
        with self.lock:
            data = self._read()
            months = data['keys'].setdefault(key_id, {})
            months[month] = round(float(months.get(month, 0)) + float(usd), 6)
            atomic_write_bytes(self.path, (json.dumps(data, indent=1) + '\n').encode('utf-8'))
