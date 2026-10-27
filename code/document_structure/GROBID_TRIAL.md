# GROBID integration: offline implementation

## Current decision

**GROBID postponed due to size/cost.** No inference, variant C or real comparison.
Docker Linux did subsequently start; the pinned download began and was then
stopped. The old engine blockage in the historical section is not the latest
known state, but G0 remains incomplete. Do not resume services/downloads/models.
Current parsing works without GROBID on all 15 papers:
[document_pipeline](../document_pipeline/README.md).
The implementation checks/counts below are historical to that increment.

Plan: `analytics/analyses/paper/sic12-grobid-trial-v1-plan.md`.
Status: code/adapter/viewer verified with fixtures; **GROBID not run**.
There is no real C for 12.pdf or real comparison HTML. Fixtures are not presented as results.

## Components and contracts

- `grobid_adapter.parse_tei(raw,run)`: UTF-8 TEI with namespace; DTD/entities
  rejected. Text/attrs/coords/XML IDs/XPath and parents intact; accounting for
  all nodes, including unmapped nodes. Identity by TEI hash+XML position.

- `grobid_align.align_tei(evidence,B)`: existing native anchors, unique exact
  text/geometry matching, normalized-view offsets→source spans.
  Preserves multiple boxes and fragments, without new bbox. Partial text does not change a
  whole region. Repeated/fuzzy matches remain candidates; incompatible rotation/crop
  triggers abstention. Does not use parents to locate deferred children.

- `grobid_mapping.json`: versioned generic rules. Distinguishes the article's
  bibliographic description in teiHeader from cited bibliography; title,
  authors, affiliations, abstract, paragraphs, headings, captions/figDesc, notes,
  formulas, references and visual objects. Unknown labels are preserved.

- `grobid_reconcile.integrate_grobid(B,evidence,links,mapping)`: copies all of B,
  adds `grobid_proposals` per unit/dimension and candidate `grobid_structure`.
  Each decision saves B_decision, claims and C_decision. Only fills unknowns
  from unique, well-aligned whole-region claims. Disagreements retain B,
  alternatives and warnings. Agreement is not equivalent to independence/validation.
  No model claim becomes direct evidence. Does not concatenate paragraphs.

- `grobid_evaluation.compare_B_C`: validates inventory, order, sources, span refs,
  hierarchy and relationships; counts changes/abstentions/conflicts by page,
  category and dimension. Semantic quality `not_evaluated/null`. GT scoring
  requires a future independent annotation contract; rejects informally supplied
  references to avoid presenting B/C as truth.

- `grobid_export.export_saved_tei(B,raw,lock,destination)`: no network/models; verifies
  complete response200, hashes/run/lock/PDF/sources and B manifest. Exclusive destination;
  intact raw data, evidence, links, mapping, C, comparison, queue and manifest.

- `grobid_view.build_view(B,C,render_catalog,destination)`: B/C comparison, filters
  and independent flows. The render catalog is the original reconciliation,
  identified by hash in the B manifest. PNGs copied byte for byte; CSS zoom, no
  recompression. HTML is generated only after receiving valid real C.

## Runner and execution gate

`runners/grobid_trial.py` does not start Docker or download models. Import is inert.
`verify_lock` requires image0.9.1 by digest/platform, complete config/models,
hashes, verified consolidation parameters and resources4CPU/8GiB/heap4GiB.
The minimum component list does not replace the inventory of the entire cascade:
all effective components and transitive resources must be inventoried/configured
before marking the lock ready. The pending audit file
is deliberately invalid for execution; do not edit booleans without verification.

Before the real POST, the runner attests an already authorized service: container,
image, CPU/memory, absence of GPU/model mounts, official entrypoint/environment,
exclusive loopback, internal Docker network and version. It does not follow redirects when sending the PDF.
Consolidations0, one request, timeout900s, zero retries. Persistent reservation
before sending; an existing destination blocks repetition. HTTP/headers before body,
raw chunks persisted/flushed; read errors/timeouts preserve partials and unknown
status. Does not kill processes or resend after timeout. Timing included;
profiling of actual memory/resources still depends on the pending real runtime.

Available commands **for a future authorized run**, not run now:

```text
PYTHONPATH=code python -B -m document_structure.runners.grobid_trial PDF B_JSON LOCK ATTEMPT_NEW --authorized-execution
PYTHONPATH=code python -B -m document_structure.grobid_export B_JSON ATTEMPT_NEW/raw/response.tei.xml LOCK C_DEST_NEW
PYTHONPATH=code python -B -m document_structure.grobid_view B_JSON C_DEST_NEW/document.json RECONCILIATION_JSON VIEW_DEST_NEW
```

The flag is not authorization by itself; it requires the user's actual decision.
Do not include it in imports/tests/exporters. Do not automate startup while the
restriction against running models remains in force. No container created now.

## Tests and limitations

```text
PYTHONPATH=code python -B -m unittest discover -s code/document_structure -t code -p 'test_grobid_*.py'
node code/document_structure/test_grobid_view.js
```

Fixtures check contracts without inference or network calls; fixture PDFs/PNGs
are not study results. DOM checks interactions, not visual QA.
Actual compatibility/speed/coverage on 12.pdf has not yet been checked.
Conservative matching may abstain because of encoding, split lines,
omitted coordinates or mixed regions; evidence and candidates are preserved.
GROBID does not reconstruct reliable levels on its own. Docling order and parents/children
without coordinates remain intact; new visualizations appear only as candidate relationships.

Read-only check performed26Oct2026: Docker client exists, engine
`dockerDesktopLinuxEngine` unavailable. No attempt was made to start it or download an
image. G0, inference, C and real comparison remain pending. Review the audit
`analytics/results/sic12_document/grobid-trial-v1-audit/` before continuing.
