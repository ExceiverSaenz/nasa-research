# Geometry and granularity method

Purpose: explain measured agreement without interpreting it as true coverage or accuracy. Current evidence: [geometry v2 report](../../../final-bbox-analysis.md). Full specification and execution: [protocol](geometry-protocol.md), [execution record](../../reports/execution/geometry-execution.md), [module README](../../../../analytics/geometry/README.md). User priorities remain in the [analysis plan](analysis-plan.md).

Six tool pairs are compared over all 397 pages, including three pages with empty detection sets. Empty union yields N/A; it does not prove absence of PDF content or perfect agreement. All overlaps, reciprocal maximum-IoU pairs, components and spatial clusters are different populations with separate denominators.

Strong correspondence edges use IoU ≥ 0.5 or containment ≥ 0.9 in either direction. Bipartite components retain isolated nodes and distinguish 1:1, 1:n, n:1, n:m and no strong correspondence. Exact rectangle unions avoid double counting; enclosing rectangles are not substituted for unions. Sensitivity tables retain alternative thresholds rather than selecting the most favorable result.

A one-to-many component can be geometrically compatible with granularity when its union matches, its small boxes are genuinely smaller and redundancy is limited. This candidate status does not confirm coherent content, section boundaries, caption membership or equivalent meaning. Parent/body coincidences and block-only comparisons are reported separately; a child without geometry never receives its parent's box.

Deterministic complete-link clustering groups nearly equivalent spatial regions without using labels, allows at most one box per tool and prevents bridge chaining. These clusters are comparison units, not document hierarchy or truth. Category agreement uses an explicit partial map while preserving native labels and excluded/unmapped counts. Exact geometric atoms integrate area and tool/category signatures without duplicate area.

Recurrence uses case/page/paper support, macro summaries, dominant-paper concentration and descriptive leave-one-paper-out checks. Page rules retain support/confidence/lift denominators. Regions and width bands are exploratory descriptors, not inferred columns or trained classes. The Data Mining foundation motivates descriptive methods; experiment thresholds are adaptations, not prescriptions from the book.

[Final checks](../../../../raw_results/analytics/deep-20261101-v2/final_checks.json) support technical invariants and input preservation. Specific agent observations, including a wrong native caption-parent assignment, retain their localized evidence and are not generalized to all relationships. V1 is preserved as a diagnostic before empty-page and clustering-priority corrections; use v2 for conclusions. See [target methodology](targets.md) for the separate label assessment and [findings](../findings/INDEX.md) for outputs.
