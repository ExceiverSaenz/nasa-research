# Current parsing architecture

The Parse stage has an operational MVP technically executed on 15 papers/397 pages.
It is an automated layer over existing parser results, preserving uncertainty and
provenance. [Status](../continuidad/13-estado-y-ciclo-experimental.md),
[JSON contract](parsing-operativo-contrato.md) and [code](../../code/document_pipeline/README.md).

## Layers and responsibilities

| Layer | Implementation / input | Output and limitation |
| --- | --- | --- |
| Original detection/OCR | LayoutLMv3, Table Transformer, MinerU; historical outputs preserved | Not rerun in the current integration; no validated global winner |
| Reconciliation | autonomous-reconciliation-v1 | Units per paper; sources/parsers as evidence, not new primary units per parser |
| Functional classification | functional-classification-reconciled-v2 | Category/subtype/function and warnings over reconciliation; source-based v1 is historical |
| Geometric order | Docling ReadingOrderPredictor, a rule-based component | Capsule baseline; the full Docling neural pipeline was not run |
| Native evidence | PyMuPDF: text/spans/styles, XMP, outlines, links and resources | Supplements, does not replace previous OCR or provide GT |
| Operational structure | document_pipeline/structure.py | Headings, partial hierarchy, memberships and candidate fragments |
| Structure/route connection | document_pipeline/order.py | Capsule routing, zones, local precedence; conflicts suspended |
| Canonical integration | document_pipeline/pipeline.py | JSON/queue/manifest and per-paper view, collection index/metrics |
| Final evaluation | Existing technical audit; semantic/visual QA pending | Integrity and DOM are not accuracy; human review after_full_mvp |

## Implemented flow

1. Verify manifests for readingv1, reconciled classification, reconciliation and PDF.
2. Reuse approved caches by identity/hash or apply the same geometric Docling and native method to each document.
3. Preserve the original inventory and generate separate operational semantics; do not replace original labels/boxes.
4. Build a partial structure with outlines, preserved headings, auxiliary numbering and relative typography.
5. Operate on whole capsules: caption first within usable associations, supported metadata in its own flow and acyclic precedence; Docling preserves an alternative and tie-breaks.
6. Assign section/fragment context through references, without concatenating or accepting new associations solely by proximity.
7. Export to a new destination, validate hashes/contracts and generate views with original PNGs. Freeze identical code/configuration across the 15 papers.

## Relations and geometry

`precedes`, `next_in_route`, `paragraph_continues`, membership and associations are
different concepts. Physical order does not prove thematic membership. Two columns
do not prove independence or continuity. Ambiguity remains with alternatives and
“Requires human validation”, without blocking outputs.

Original boxes retain their system/origin/transformations. Derived zones/extents
are not new region bboxes. 374 children without bbox/19 parents/17 abstained pages
are preserved; the parent's box is not inherited and native text does not lift abstention.
Do not merge predictions, average scores across models or impute confidence.

## What is excluded or postponed

GROBID: offline code preserved, without a trial or real C; postponed due to size/cost.
Do not add it as a mandatory dependency or silently change engines.
Legacy LayoutReader remained a compatibility investigation; do not repair/run it
routinely. Documentation does not authorize new models, OCR, Colab/GCE or GPU selection.
Cell/table representation, full semantics and the Extract/Curate/Discover stages
are not considered implemented merely because this Parse integration is technically complete.

Earlier details of models/checkpoints, proposals and specific trials are preserved
in full in [the snapshot of this architecture](../history/parsing-operational-documentation-consolidation-v1/before/docs/arquitectura/02-arquitectura-del-parsing.md).
Do not interpret them as current authorization or as pending current execution.
