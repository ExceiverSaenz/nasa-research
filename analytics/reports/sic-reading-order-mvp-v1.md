# Reading order MVP v1: results

Authorized implementation over classification of the reconciled version, without reclassification or running OCR, models or Colab. Single export of 15 papers / 397 pages. Proposals remain pending semantic validation after the MVP of all stages.

## Where to consult

- [Responsive view of 12.pdf](../results/sic12_document/reading-order-mvp-v1-view/index.html): 13 pages, intact original PNGs, synchronized boxes/list/arrows, route switching and zoom.
- [12.pdf JSON](../results/sic_collection/reading-order-mvp-v1/papers/12/document.json).
- [Summary and links to each paper](../results/sic_collection/reading-order-mvp-v1/summary.json), [warning queue](../results/sic_collection/reading-order-mvp-v1/review-queue.json).
- [Design](../analyses/collection/reading-order-reconciled-mvp-v1-design.md), [plan with parameters](../analyses/collection/reading-order-reconciled-mvp-v1-plan.md), [code and techniques](../../code/reading_order/README.md).
- [Audit](../results/sic_collection/reading-order-mvp-v1-audit/verification.json).

## Contract and techniques

`inventory` preserves each original unit and its classification unchanged; `steps` contains visits by reference; `routes` separates body, notes, bibliography, metadata and editorial navigation. Fragments are not concatenated. `original_page_context`, `layouts`, `decisions` and `suspended_constraints` preserve evidence, alternatives and provenance. The viewer presents text/warnings and the JSON retains complete details of alternatives.

Recursive XY-cut proposes zones/columns from existing boxes (vertical gap .025 width; horizontal .012 height). A precedence graph preserves usable constraints; conflicts are suspended with a warning. Without a clear cut, y,x fallback and an x,y alternative are offered. LTR direction is an explicit hypothesis. Order crosses pages within each paper.

Caption first applies only within existing usable associations: native_preserved, automatic_rule, human_accepted or accepted. Automatic_rule does not mean human acceptance. Candidate links are not accepted by proximity. Shared captions and bodies have one content occurrence and later visits by reference. The set's position uses its bodies as anchors, without exporting new boxes.

`precedes` expresses constraints; `next_in_route` the consecutive visit; `paragraph_continues` a hypothesis of membership in the same paragraph. Page/column transition geometry, a final hyphen or an open clause/lowercase start support continuity candidates. Text is not merged and that relation is not considered validated.

## Coverage, abstention and warnings

5 374 units accounted for = 5 343 regions + 31 groups: 100 % inventory coverage. This does not equal individually ordering all text. There are 4 512 content occurrences: 1 835 rule-proposed positions (40.67 %) and 2 677 fallback (59.33 %). The 79 content occurrences with abstained geometric evidence are included in fallback, not added separately.

There are 4 158 steps with some warning and 2 838 fallback steps, including structures/references in addition to content. These counts may overlap and their denominator is steps, different from the inventory. Original classification warnings remain in each unit; the additional queue belongs to this stage. No figure measures accuracy, precision, recall or F1: no validated order GT exists.

The 374 children without coordinates remain deferred in 19 parent placeholders, with references without individual sequence; 17 pages retain abstention. All original boxes and texts are preserved. Human review does not block export and remains at the end, including automatic decisions.

Continuity: 108 rule-supported candidates, 374 ambiguous and 14 blocked by geometry/deferred units. All require final human validation. There is no duplicate content or operational cycles. Conservative heuristics produce many fallbacks for geometry without clear separation; thresholds were not adjusted to improve these figures.

| Paper | Inventory | Content occurrences | Proposed position | Content fallback | Deferred children |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 331 | 284 | 133 | 151 | 20 |
| 2 | 303 | 256 | 50 | 206 | 20 |
| 3 | 89 | 80 | 45 | 35 | 0 |
| 4 | 94 | 86 | 38 | 48 | 0 |
| 5 | 204 | 185 | 59 | 126 | 0 |
| 6 | 390 | 321 | 76 | 245 | 0 |
| 7 | 299 | 269 | 97 | 172 | 0 |
| 8 | 607 | 567 | 82 | 485 | 24 |
| 9 | 187 | 153 | 75 | 78 | 0 |
| 10 | 69 | 64 | 23 | 41 | 0 |
| 11 | 365 | 336 | 129 | 207 | 0 |
| 12 | 293 | 251 | 87 | 164 | 0 |
| 14 | 740 | 580 | 375 | 205 | 100 |
| 15 | 694 | 503 | 196 | 307 | 135 |
| 17 | 709 | 577 | 370 | 207 | 75 |

## Technical acceptance and limitations

23 offline tests pass: columns/wide blocks, caption first, shared relations, routes, cycles, scale, RTL, abstained pages, deferred children, hashes and invalid references. DOM simulation: 78 page×route combinations and 199 navigation transitions for 12.pdf, without errors. The 13 copied images retain their hashes, without reduction or recompression. Independent export audit confirms exact equality of units and original context, unique references and captions before bodies in applicable capsules.

111 previous protected files remain hash-identical, in addition to input manifest checks. Independent technical review found and enabled correction of serialization conflicts, fallback propagation, false continuity evidence and insufficient reference validation before final export. It does not validate the papers' semantic order.

Visual browser inspection was not completed in this session; interface verification consists of DOM simulation and code review. Opening the local HTML allows reviewing the route. Canonical integration and V&V remain pending; do not repeat the export or automatically refine rules.
