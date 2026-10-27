"""Bridge consolidated canonical-v1 inputs to the existing classification v2 API."""
from collections import Counter
from pathlib import Path, PurePosixPath

from reconciliation.consolidated_inputs import load_document
from reconciliation.engine import reconcile, VERSION, THRESHOLD
from reconciliation.export import encoded
from .common import digest, read_json, write_json


def export_collection(prepared, pdf_directory, destination):
    prepared, pdf_directory, destination = (Path(p).resolve() for p in (prepared, pdf_directory, destination))
    if destination.exists():
        raise FileExistsError(destination)
    for source in (prepared, pdf_directory):
        if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ValueError('Separate output required')
    adaptation = read_json(prepared / 'adaptation-manifest.json')
    entries = adaptation['documents']
    seen_papers, seen_hashes, inputs = set(), set(), []
    for entry in entries:
        name = PurePosixPath(entry['document'])
        if len(name.parts) != 2 or name.parts[0] != 'SiC_papers' or name.suffix != '.pdf' or not name.stem.isdigit():
            raise ValueError('Unexpected PDF name')
        paper = int(name.stem)
        key = entry['document_sha256']
        if paper < 1 or paper in seen_papers or key in seen_hashes:
            raise ValueError('Duplicate/invalid paper identity')
        seen_papers.add(paper)
        seen_hashes.add(key)
        pdf = pdf_directory / name.name
        if digest(pdf) != key:
            raise ValueError('PDF identity mismatch: ' + name.name)
        data = load_document(prepared, key)
        if len(data['pages']) != entry['pages'] or [p['identity']['physical_page'] for p in data['pages']] != list(range(1, entry['pages'] + 1)):
            raise ValueError('Physical page scope mismatch')
        inputs.append((paper, entry, pdf, data))
    destination.mkdir(parents=True, exist_ok=False)
    documents, totals, statuses, protected = [], Counter(), Counter(), {}
    for paper, entry, pdf, data in sorted(inputs, key=lambda row: row[0]):
        print(f'Conciliación: {paper}.pdf ({len(data["pages"])} páginas)', flush=True)
        pages = [reconcile(p) for p in data['pages']]
        # The engine adds classifications/relations; all native records must survive.
        for original, result in zip(data['pages'], pages):
            before = {r['id']: r for r in original['records']}
            after = {r['id']: r for r in result['records']}
            if set(before) != set(after) or any(any(after[id].get(k) != v for k, v in r.items()) for id, r in before.items()):
                raise ValueError('Native record mutation or loss')
        doc = dict(schema_version='autonomous-document/1', rule_version=VERSION,
                   document=str(pdf), document_sha256=entry['document_sha256'], pages=pages,
                   parser_configuration=data['parser_configuration'], validation='technical_only_semantic_pending')
        rel = f'papers/{paper}/document.json'
        path = destination / rel
        path.parent.mkdir(parents=True)
        with path.open('xb') as stream:
            stream.write(encoded(doc))
        counts = dict(pages=len(pages), records=sum(len(p['records']) for p in pages),
                      groups=sum(len(p['groups']) for p in pages),
                      correspondences=sum(len(p['correspondences']) for p in pages))
        totals.update(counts)
        page_statuses = Counter(p['status'] for p in pages)
        statuses.update(page_statuses)
        documents.append(dict(paper=paper, document=str(pdf), document_sha256=entry['document_sha256'],
                              data=rel, counts=counts, page_statuses=dict(page_statuses)))
        protected.update(data['source_inputs'])
        protected[str(pdf)] = entry['document_sha256']
        prepared_path = prepared / 'documents' / entry['document_sha256'] / 'input.json'
        protected[str(prepared_path)] = digest(prepared_path)
    if any(digest(p) != h for p, h in protected.items()):
        raise ValueError('Input changed during reconciliation')
    summary = dict(schema_version='autonomous-reconciliation-collection/1', documents=documents,
                   physical_pages=totals['pages'], records=totals['records'], groups=totals['groups'],
                   correspondences=totals['correspondences'], page_statuses=dict(statuses),
                   rule_version=VERSION, threshold=THRESHOLD, models_executed=False,
                   semantic_validation='pending_after_full_mvp')
    write_json(destination / 'summary.json', summary)
    write_json(destination / 'manifest.json', dict(protected_inputs=protected,
               outputs={p.relative_to(destination).as_posix(): digest(p) for p in destination.rglob('*.json')},
               rule_version=VERSION, threshold=THRESHOLD, original_inputs_unchanged=True))
    return summary
