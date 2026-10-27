# Docling ordering trial on 12.pdf

Docling's rule-based ordering component was run once over the
existing reconciled units. DocumentConverter, OCR, neural
models, classifier and native/GROBID integration were not run. Scope: 13 pages of 12.pdf.

## Consult

- [Responsive HTML comparison](../results/sic12_document/docling-order-trial-v1-view/index.html).
- [Candidate JSON](../results/sic12_document/docling-order-trial-v1/document.json).
- [Summary per page and route](../results/sic12_document/docling-order-trial-v1/summary.json).
- [Warnings](../results/sic12_document/docling-order-trial-v1/review-queue.json).
- [Audit](../results/sic12_document/docling-order-trial-v1-audit/verification.json).
- [Frozen plan](../analyses/paper/sic12-docling-order-trial-v1-plan.md) and [code](../../code/document_structure/DOCLING_TRIAL.md).

The view allows choosing page/route, synchronizing selection or keeping it independent,
viewing both versions or only one, zoom/boxes/arrows and a differences table. It shares
13 original hash-identical PNGs, without reduction or recompression; CSS fits their
presentation to width. Panels stack on mobile. These are not parser layers.

## Descriptive result

293 units preserved (251 segments, 36 containers, 6 groups), 251 content
occurrences and 279 route steps, including structures/references. 99 content
positions changed; 168 pairs changed precedence relative to the baseline.
The denominator of compared pairs is 2006: pairs within the same page and route; it does not mix different routes.

These numbers measure disagreement, not errors or improvement. There is no adjudicated reading GT.
All 29 processed page/route combinations completed without execution fallback.
This only demonstrates that the component works, not correct reading.

| Page | Content | Distinct positions | Reversed / compared pairs |
| --- | ---: | ---: | ---: |
| 1 | 27 | 10 | 14 / 103 |
| 2 | 25 | 20 | 58 / 254 |
| 3 | 19 | 11 | 20 / 137 |
| 4 | 19 | 13 | 20 / 137 |
| 5 | 15 | 7 | 8 / 79 |
| 6 | 14 | 4 | 3 / 67 |
| 7 | 18 | 9 | 13 / 121 |
| 8 | 15 | 4 | 3 / 79 |
| 9 | 16 | 14 | 24 / 92 |
| 10 | 11 | 0 | 0 / 37 |
| 11 | 12 | 3 | 2 / 46 |
| 12 | 14 | 4 | 3 / 67 |
| 13 | 46 | 0 | 0 / 787 |

## What changed and what remained fixed

Single variable: order among existing blocks/groups within each route and page.
Docling2.123.1, docling-core2.92.0, rtree1.4.1, pydantic2.12.5, Python3.13.5; defaults
intact and predictive module pinned by hash. Neutral inputs sorted by geometry
before invoking the component, without using the baseline sequence as a semantic signal.
Group anchors use the same existing body boxes; their enclosing extents are
derived ordering inputs, not new reconciled boxes.

Geometric adaptation to BOTTOMLEFT was necessary because the dependency's
TOPLEFT origin conversion returns BoundingBox and loses cid. Detected through tests,
it was resolved by correctly creating the input PageElement; Docling was not modified.

Classification, routing, associations, members and internal
group/panel order were not modified. Caption first and shared content without duplication
are preserved. If shared references require a capsule to appear earlier,
that constraint is recorded in the trace. Known problems with
authors/affiliations/metadata were not corrected: they continue to affect routes.

Original relations remain in baseline_evidence_relations. next_in_route
was regenerated. Old continuities were not reused as new ones: continuity NLP
was not run. Previous warnings remain present in every step and
unit, alongside this trial's warning of an unvalidated proposal.

## Verification and limitations

145 previous protected files hash-intact; identical inventory and page context.
No duplication, reference loss or operational cycles. Nine Python tests
pass; one expectedFailure documents a quality failure of the component itself:
a wide heading followed by two columns in a fixture produces row-wise
interleaving. Parameters were not tuned to hide it. Independent technical review
completed; it corrected resetting the other panel's selection when synchronization was disabled.
A test with literal script-closing text confirms preservation when embedding JSON.

DOM simulation of the actual HTML: 156 page/route combinations across both views,
navigation, synchronization without echoes and independent selection; parent tests for
synchronization/height/showing panels pass. Visual browser review could not
be performed: its security policy rejects file://. No workaround was attempted.
This limitation is not presented as passed visual QA.

The trial does not demonstrate superiority over the baseline or replace semantic
structure. Differences are available for inspection; formal human review
remains after_full_mvp. Stopping point reached for this bounded export; no tuning,
automatic repetition or extension to other papers through this delivery.
