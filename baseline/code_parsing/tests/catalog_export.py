"""Test-only preserved CSV regression helper; not part of the MVP pipeline."""
import csv
import json
from pathlib import Path


class CatalogExporter:
    def export(self, source, destination):
        records = json.loads(Path(source).read_text(encoding='utf8'))['records']
        with Path(destination).open('w', encoding='utf8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['paper','reused','pages','elements','pictures','tables','formulas','result_directory'])
            for record in records:
                metrics = record['metrics']; types = metrics['by_type']
                writer.writerow([record['name'],record['reused'],metrics['pages'],metrics['elements'],
                    types.get('picture',0),types.get('table',0),types.get('formula',0),record['result_directory']])

