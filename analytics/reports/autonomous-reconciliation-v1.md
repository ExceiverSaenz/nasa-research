# Autonomous reconciliation v1: implementation and regression

26oct2026. Design approved by the user; offline execution completed on saved
evidence. Reusable by document/page identity, without case IDs in rules.

## Delivery

- Code: `code/reconciliation/`; instructions in its README.
- Output: `analytics/results/sic12_document/autonomous-reconciliation-v1/`.
- View: `review.html`; automatic/MinerU/TATR/LayoutLMv3 with categories, groups,
  optional containers, inspector and decisions. The automatic output differs from the
  previous human output and does not incorporate historical Table2.
- Audit: `analytics/results/sic12_document/autonomous-reconciliation-v1-audit/`.

Result: 13 pages processed, 536 records preserved (251 segments and 36 MinerU
containers, 236 LM, 13 TATR), six automatic groups and 128 geometric
correspondences. The latter are not 128 validated semantic identities or a measure
of accuracy. All eight categories are implemented; Other may not appear in
a document and is tested with an unknown class.

Six groups match the saved human references in members and caption.
Fig5 and seven simple figures on p8/p12 do not produce improper groupings. Human
references are consulted only in tests, never to generate the output. Fig6
retains overlapping boxes and a warning; the geometry has not been repaired. TATR is
integrated into table correspondences/conflicts; it does not replace bodies or cells.

## Verification

21 tests pass: ontology, capabilities, identity, preservation, conflicts,
abstention, failed sources, unknown version, damaged page, nonfinite values,
group regression, HTML security and deterministic/non-overwriting export.
Exact comparison of MinerU boxes with R and of 536 records with native pointers.
55 hashed sources; 367 earlier files verified unchanged. Viewer JavaScript
passed syntax checking. No actual visual review or browser interaction
test was performed: the file: protocol was previously blocked for
the agent. Visual validation is not attributed to syntax checking.

Independent review found five boundary issues: use of a failed parser,
a page without MinerU, external versions, a local failure aborting the document and nonserializable
NaN. Fixed with regression tests observed to fail and then pass.
Failed sources are preserved without supporting decisions; the invalid page is
blocked while others continue. An unreadable/invalid global manifest prevents loading the batch.
Nonfinite values are preserved with an explicit JSON tag, not clipped.

## Limits and next decision

The engine automates normalization and conservative relations; it does not correct OCR,
object boundaries, content loss or semantic section hierarchy.
It preserves native classification and records conflicts, without a score-based winner.
The supplied adapter supports the existing evaluation format and declared
versions; new formats require adapters, not heuristics to guess scale.
No other papers have been processed or generality demonstrated. No new OCR,
inference, training, remote sessions or model changes.

The next useful step is to identify existing outputs from other papers and agree on the
held-out document-level evaluation set. Do not automatically expand the corpus or
repeat 12.pdf to tune thresholds. If suitable evidence is unavailable, record that
gap before requesting runs. A pilot requires new positives and function-specific
references; two held-out papers are a design minimum, not universal proof.

## Execution ledger

Plan: `analytics/analyses/paper/autonomous-reconciliation-plan.md`.
Ruling: T1–T3 were implemented in a shared pure core and verified by functional
suites, not as separate causal trials; do not attribute differences to a single
empirical variable or claim an accuracy improvement. Presentation is a separate layer.
Ruling: test temporary files within workspace tmp/, because the Windows sandbox
temporary directory rejected writes; no permission expansion was necessary.
Stopping point reached for implementation/regression; cross-paper pilot pending.
