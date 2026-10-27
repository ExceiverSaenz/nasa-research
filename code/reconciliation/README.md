# Autonomous offline reconciliation v1

Approved design: ../../analytics/analyses/paper/autonomous-reconciliation-design.md.
Generic engine `engine.reconcile(page)`; adapter `inputs.load_evaluation(directory)`
for document_trial exports with MinerU 4.0.12 and original LM/TATR contracts.
Does not import models, run OCR or access the network. Does not consume human acceptance.

From the root in PowerShell:

```powershell
$env:PYTHONPATH='code'
python -m unittest discover -s code/reconciliation -t code -v
python -m reconciliation.export RUTA_EVALUACION DIRECTORIO_NUEVO
```

The adapter discovers pages declared in the manifest, not thirteen fixed
pages. Verifies hashes, identity, render and versions of packages defining the
external contracts. MinerU normalized→pixel transformation; LM/TATR are already
in pixels under this export contract. Another format/configuration requires
a versioned adapter: do not guess scales or accept unknown versions.

Common API `canonical-v1`: identity(document_sha256,physical_page,render_sha256,
width_px,height_px); parsers(model→status); records(id,parser,native_type,bbox,
native,parent,role,source(path,sha256,pointer),transform,text); incidents. `bbox`
is already in XYXY pixels, top-left origin; `transform` documents the
affine transformation [a,b,c,d,e,f] from the native box. Anyone creating an adapter must
verify that transformation against its source before providing records.
The core is an internally trusted API; it does not open source files or apply
a transformation a second time. The supplied exporter verifies sources.

Outputs: document.json, manifest.json, review.html. Four views: automatic,
MinerU, TATR and LM; page/category selection, containers, groups and inspector.
The automatic view preserves MinerU boxes/text and adds relationships. Previous human
results remain separate. Does not correct edges or recover historical labels.

Rules: explicit normalization of eight classes; mutual correspondence >=0.90,
unique per parser pair; multipanel with LM support and MinerU structure/caption,
without comparable internal or external conflicts. Scores do not select winners.
Failed sources are preserved without supporting decisions. Local integrity failure
blocks a page, not the entire document; an invalid global manifest prevents loading it.
Invalid geometry blocks page relationships. Nonfinite numbers are exported
as `{"$nonfinite":"nan"}` (or inf/-inf), without clipping or deleting them.

Limit: regression-tested on 12.pdf and contract fixtures. Generality on
other papers has not been evaluated; neither has OCR/reading accuracy. Geometric
correspondences are not validated semantic identity. Unsupported new configuration
is blocked; this is an explicit limitation, not a parser failure.

## Consolidated native ZIP input v1

`consolidated_inputs.py` adapts `sic-native-archive-consolidation/1` to
`canonical-v1` pages, separated by document SHA256. Does not run the engine, models,
OCR or new renders; does not modify `inputs.py`, `engine.py` or rules/thresholds.
MinerU is read from `middle-native.json`, with normalized→pixel transformation
verified against its export; LM/TATR from their pixel-based `regions.json`.
Complete native records, hierarchy, scores, unknown classes
and invalid geometry are preserved. No box is clipped and no score is used to filter.

Offline preparation, once only and with a new destination:

```powershell
$env:PYTHONPATH='code'
python -B -m reconciliation.consolidated_inputs ARCHIVO.zip DESTINO_NUEVO
```

Requires the `.sha256` sidecar, supported formats/versions and matching
document/page/render/status. Copies only necessary sources to `sources/`, with
intact bytes, and writes `documents/<SHA256>/input.json` and
`adaptation-manifest.json`. If preparation fails, preserve the partial
directory for review; do not overwrite it or retry automatically.

Verified loading API, without automatic reconciliation:

```python
from reconciliation.consolidated_inputs import load_document
data = load_document("DESTINO_PREPARADO", "SHA256_DEL_DOCUMENTO")
# data['pages'] contains the input contract for engine.reconcile(page).
```

The historical `reconciliation.export` CLI still accepts old evaluations;
do not pass this ZIP or the prepared collection directly to it. Each document must
be consumed separately to avoid confusing physical pages with the same number.
Provenance paths in prepared inputs are absolute: moving the folder
requires new traceable preparation, not manual pointer/hash edits.
Preparing the input does not validate reconciler generality across papers.

Tests: `python -B -m unittest reconciliation.test_consolidated_inputs -v`.
