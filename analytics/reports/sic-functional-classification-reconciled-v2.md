# Functional classification of the reconciled version — v2

26oct2026. Explicitly authorized correction of the previous MVP's scope.
[Design/plan](../analyses/collection/functional-classification-reconciled-v2-plan.md).

## Problem and decision

V1 classified all parser records instead of reconciled units.
Its results are preserved as a historical attempt, but do not represent the requested
MVP. Do not directly compare its coverage counts with those of v2.
V2 takes exactly the objects/containers/groups declared in the saved reconciliation.
It does not redo reconciliation or determine selection by parser or score.

The category, status and reason preserved in reconciliation are explicit initial
evidence. Geometric/NLP analysis uses reconciled neighbors; native
labels, comparable external detections and previous decisions only contribute
evidence, coarse support or contradiction. Differences are neither erased nor resolved
by majority vote. Caption relations and group members provide functional context;
they retain authority and warnings, without new human acceptance.

## Output

`analytics/results/sic_collection/functional-classification-reconciled-v2/`:
summary, manifest, review-queue and document.json per paper.

- 15 papers / 397 pages.
- **5343 reconciled regions:** 4886 segments +457 containers.
- **31 logical groups**, referencing existing members, without new boxes.
- 6124 alternative records separated as evidence_records; they receive no
  functional classification and do not become additional objects.
- All 11467 original source records remain preserved in their corresponding
  layer and intact sources; IDs and provenance without replacement.
- 4219 automatically proposed functions and 1155 abstentions over **5374
  structural units** (regions+groups, not disjoint semantic objects).
- 2471 units with some warning, about function/category/subtype/geometry or
  inherited status. “Requires human validation” warning, after_full_mvp review.
  Coverage does not represent accuracy or request immediate human review.

374 children without bbox, parents and full-page abstention are preserved on the
17 affected pages. Original relations, groups, decisions, correspondences and statuses
preserved; reconciled categories not silently replaced.
Reading order remains unresolved. Semantic validation at the end of the full MVP.

## Website for 12.pdf

[Open local responsive website](../results/sic12_document/functional-classification-reconciled-v2-view/index.html).
13 pages, 251 segments +36 containers and 6 reconciled groups. A single layer,
without a parser selector. Color by category or function, navigation, zoom and containers.
Preserved category, proposals, alternatives and evidence accessible in the inspector.
Groups select their members' original boxes, without a new enclosing box.

Original PNGs copied byte for byte and hash-verified; no resizing/recompression.
Initial width fit through CSS, optional zoom. Reading+inspector grid on
desktop, inspector below on mobile; no fixed height or mandatory internal scrolling
for the fitted page. No external publication or paper uploads.

## Verification and limitations

15 offline Python tests pass; 52 page/color/container combinations and
group selection/zoom verified with a simulated DOM. Node verifies JS syntax.
Independent review confirmed eligibility, abstentions and static presentation.
A selected failed source's ability to influence another was fixed with a
red→green regression; explicit group abstention is also preserved.

Baseline: 63 outputs and four historical modules verified before export.
1164 protected input files and 25 previous classification/view files
intact. Single semantic export; audit verifies exact sets,
complete original_record/evidence, seed categories and abstentions/relations.
13 PNGs and final HTML verified by hash.

**Real visual QA pending:** the test browser did not reach localhost
(ERR_CONNECTION_TIMED_OUT). Do not claim browser-validated responsiveness because
simulated tests pass. The local website and its automated verification are delivered.

[Audit](../results/sic_collection/functional-classification-reconciled-v2-audit/verification.json).
No OCR, models, Colab, new renders or changes to previous results.
Frozen geometric/NLP rules, without tuning on results. Canonical pipeline
and V&V pending. Stop the correction after delivery; next stage: designing
document order over reconciliation, not automatic execution.

## Descriptive metrics per paper and category (documentation expansion)

This section aggregates only data from the saved v2 output. It does not run the
classifier or modify labels, statuses, warnings, boxes or links. The
counts describe system decisions; they are not precision, recall, F1 or an error
rate. Human semantic review remains at the end of the full MVP.

### Definitions, denominators and criteria

For each dimension d (category, function and subtype):

- **Coverage C_d = units with non-null value / N.** Includes preserved categories;
  does not mean a new correction, certainty or human validation.
- **Abstention A_d = units with status=abstained / N.** In this output C_d+A_d=1
  in each stratum. It may result from multiple candidates, no candidate or blocking
  of a single proposal by page restrictions; it is not always ambiguity.
- **Warnings W = unique units with one or more warnings / N.** Do not sum
  reasons: one unit may appear under several. Having a proposal does not remove warnings.
- **Joint coverage = units with non-null category and function / N**; full coverage
  also requires a non-null subtype. Neither certifies accuracy.
- N includes declared segments, containers and groups. Groups reference
  members and containers contain children; these are not disjoint semantic objects
  or independent samples. The 6124 external records provide evidence only.
- Grouped by **effective proposed category**; value=null appears under Ambiguous.
  The original retained category remains in input JSONs. Ambiguous is not GT.
- An N=0 stratum is displayed as **— (not applicable)**, not 0 % coverage/abstention.
  All percentages in each row use that row's N and are rounded to
  two decimals; counts are exact. Reasons do not change the denominator.

Complete reusable data: [metrics.json](../results/sic_collection/functional-classification-reconciled-v2-metrics/metrics.json).

### Global summary

| Dimension (N=5374) | With a single proposal: n (%) | Abstention: n (%) |
| --- | --- | --- |
| Category | 5 165 (96,11 %) | 209 (3,89 %) |
| Function | 4 219 (78,51 %) | 1 155 (21,49 %) |
| Subtype | 3 680 (68,48 %) | 1 694 (31,52 %) |

Warnings: **2 471 (45,98 %)**. Joint category+function coverage: **4 060 (75,55 %)**. All three dimensions: **2 934 (54,60 %)**.

### Separation by unit type

| Unit | N | Category C / A | Function C / A | Subtype C / A | With warning n (%) |
| --- | --- | --- | --- | --- | --- |
| Segment | 4 886 | 4 677 / 209 | 4 188 / 698 | 3 649 / 1 237 | 1 983 (40,59 %) |
| Container | 457 | 457 / 0 | 0 / 457 | 0 / 457 | 457 (100,00 %) |
| Logical group | 31 | 31 / 0 | 31 / 0 | 31 / 0 | 31 (100,00 %) |

C / A expresses counts with a single proposal / abstention. The 31 groups have all three dimensions proposed, but inherit member or group warnings. The 457 containers retain their category and have no effective function/subtype assigned.

### Breakdown per paper

Each coverage is accompanied by the corresponding abstention, with the same denominator.

| Paper | N | Cat. C / A | Func. C / A | Func. C % / A % | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.pdf | 331 | 307 / 24 | 252 / 79 | 76,13 % / 23,87 % | 243 / 88 | 144 (43,50 %) |
| 2.pdf | 303 | 302 / 1 | 218 / 85 | 71,95 % / 28,05 % | 227 / 76 | 139 (45,87 %) |
| 3.pdf | 89 | 86 / 3 | 79 / 10 | 88,76 % / 11,24 % | 57 / 32 | 34 (38,20 %) |
| 4.pdf | 94 | 93 / 1 | 86 / 8 | 91,49 % / 8,51 % | 69 / 25 | 25 (26,60 %) |
| 5.pdf | 204 | 203 / 1 | 185 / 19 | 90,69 % / 9,31 % | 144 / 60 | 65 (31,86 %) |
| 6.pdf | 390 | 382 / 8 | 319 / 71 | 81,79 % / 18,21 % | 210 / 180 | 193 (49,49 %) |
| 7.pdf | 299 | 293 / 6 | 264 / 35 | 88,29 % / 11,71 % | 189 / 110 | 122 (40,80 %) |
| 8.pdf | 607 | 557 / 50 | 504 / 103 | 83,03 % / 16,97 % | 521 / 86 | 193 (31,80 %) |
| 9.pdf | 187 | 186 / 1 | 156 / 31 | 83,42 % / 16,58 % | 87 / 100 | 104 (55,62 %) |
| 10.pdf | 69 | 68 / 1 | 62 / 7 | 89,86 % / 10,14 % | 55 / 14 | 16 (23,19 %) |
| 11.pdf | 365 | 356 / 9 | 314 / 51 | 86,03 % / 13,97 % | 223 / 142 | 168 (46,03 %) |
| 12.pdf | 293 | 291 / 2 | 255 / 38 | 87,03 % / 12,97 % | 172 / 121 | 130 (44,37 %) |
| 14.pdf | 740 | 730 / 10 | 571 / 169 | 77,16 % / 22,84 % | 540 / 200 | 328 (44,32 %) |
| 15.pdf | 694 | 663 / 31 | 486 / 208 | 70,03 % / 29,97 % | 467 / 227 | 405 (58,36 %) |
| 17.pdf | 709 | 648 / 61 | 468 / 241 | 66,01 % / 33,99 % | 476 / 233 | 405 (57,12 %) |

Micro functional coverage (all units): **78,51 %**; macro per paper (equal weight per document): **82,11 %**. Micro warnings: **45,98 %**; macro: **42,48 %**. Observed functional range: **66,01 %–91,49 %**. These are statistics for this collection, without confidence intervals or population generalization.

### Global breakdown by category

Because grouping uses the effective category, category coverage is 100 % in
resolved categories and 0 % in Ambiguous by construction; this is not per-class
performance or a confusion matrix. Function/subtype coverage does show
which other decisions remain pending within each proposed category.

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 2 752 | 2 752 / 0 | 2 331 (84,70 %) | 421 (15,30 %) | 2 728 / 24 | 421 (15,30 %) |
| Title | 469 | 469 / 0 | 256 (54,58 %) | 213 (45,42 %) | 469 / 0 | 213 (45,42 %) |
| Figure | 781 | 781 / 0 | 404 (51,73 %) | 377 (48,27 %) | 31 / 750 | 781 (100,00 %) |
| Table | 119 | 119 / 0 | 57 (47,90 %) | 62 (52,10 %) | 0 / 119 | 119 (100,00 %) |
| Caption | 337 | 337 / 0 | 337 (100,00 %) | 0 (0,00 %) | 95 / 242 | 242 (71,81 %) |
| Equation | 67 | 67 / 0 | 67 (100,00 %) | 0 (0,00 %) | 67 / 0 | 0 (0,00 %) |
| Margin | 640 | 640 / 0 | 608 (95,00 %) | 32 (5,00 %) | 186 / 454 | 486 (75,94 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 209 | 0 / 209 | 159 (76,08 %) | 50 (23,92 %) | 104 / 105 | 209 (100,00 %) |

### Paper × category cross-tabulation

The nine categories are retained in each paper, even if N=0. C / A are counts; function and warning rates have a local denominator. Category/subtype rates are also calculated in metrics.json.

#### 1.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 151 | 151 / 0 | 128 (84,77 %) | 23 (15,23 %) | 150 / 1 | 23 (15,23 %) |
| Title | 27 | 27 / 0 | 2 (7,41 %) | 25 (92,59 %) | 27 / 0 | 25 (92,59 %) |
| Figure | 44 | 44 / 0 | 22 (50,00 %) | 22 (50,00 %) | 0 / 44 | 44 (100,00 %) |
| Table | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 21 | 21 / 0 | 21 (100,00 %) | 0 (0,00 %) | 6 / 15 | 15 (71,43 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 56 | 56 / 0 | 51 (91,07 %) | 5 (8,93 %) | 56 / 0 | 5 (8,93 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 24 | 0 / 24 | 24 (100,00 %) | 0 (0,00 %) | 4 / 20 | 24 (100,00 %) |

#### 2.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 188 | 188 / 0 | 145 (77,13 %) | 43 (22,87 %) | 186 / 2 | 43 (22,87 %) |
| Title | 24 | 24 / 0 | 15 (62,50 %) | 9 (37,50 %) | 24 / 0 | 9 (37,50 %) |
| Figure | 45 | 45 / 0 | 23 (51,11 %) | 22 (48,89 %) | 3 / 42 | 45 (100,00 %) |
| Table | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 13 | 13 / 0 | 13 (100,00 %) | 0 (0,00 %) | 4 / 9 | 9 (69,23 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 30 | 30 / 0 | 20 (66,67 %) | 10 (33,33 %) | 10 / 20 | 30 (100,00 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 3.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 36 | 36 / 0 | 36 (100,00 %) | 0 (0,00 %) | 36 / 0 | 0 (0,00 %) |
| Title | 11 | 11 / 0 | 10 (90,91 %) | 1 (9,09 %) | 11 / 0 | 1 (9,09 %) |
| Figure | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Table | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 10 | 10 / 0 | 10 (100,00 %) | 0 (0,00 %) | 1 / 9 | 9 (90,00 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 8 / 3 | 3 (27,27 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 3 | 0 / 3 | 3 (100,00 %) | 0 (0,00 %) | 1 / 2 | 3 (100,00 %) |

#### 4.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 46 | 46 / 0 | 46 (100,00 %) | 0 (0,00 %) | 46 / 0 | 0 (0,00 %) |
| Title | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 11 / 0 | 0 (0,00 %) |
| Figure | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Table | 0 | — | — | — | — | — |
| Caption | 9 | 9 / 0 | 9 (100,00 %) | 0 (0,00 %) | 4 / 5 | 5 (55,56 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 8 / 3 | 3 (27,27 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 5.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 102 | 102 / 0 | 102 (100,00 %) | 0 (0,00 %) | 102 / 0 | 0 (0,00 %) |
| Title | 19 | 19 / 0 | 17 (89,47 %) | 2 (10,53 %) | 19 / 0 | 2 (10,53 %) |
| Figure | 32 | 32 / 0 | 17 (53,12 %) | 15 (46,88 %) | 2 / 30 | 32 (100,00 %) |
| Table | 4 | 4 / 0 | 2 (50,00 %) | 2 (50,00 %) | 0 / 4 | 4 (100,00 %) |
| Caption | 16 | 16 / 0 | 16 (100,00 %) | 0 (0,00 %) | 6 / 10 | 10 (62,50 %) |
| Equation | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Margin | 24 | 24 / 0 | 24 (100,00 %) | 0 (0,00 %) | 8 / 16 | 16 (66,67 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 1 (100,00 %) |

#### 6.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 106 | 106 / 0 | 106 (100,00 %) | 0 (0,00 %) | 106 / 0 | 0 (0,00 %) |
| Title | 25 | 25 / 0 | 22 (88,00 %) | 3 (12,00 %) | 25 / 0 | 3 (12,00 %) |
| Figure | 128 | 128 / 0 | 65 (50,78 %) | 63 (49,22 %) | 2 / 126 | 128 (100,00 %) |
| Table | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 59 | 59 / 0 | 59 (100,00 %) | 0 (0,00 %) | 39 / 20 | 20 (33,90 %) |
| Equation | 30 | 30 / 0 | 30 (100,00 %) | 0 (0,00 %) | 30 / 0 | 0 (0,00 %) |
| Margin | 26 | 26 / 0 | 26 (100,00 %) | 0 (0,00 %) | 0 / 26 | 26 (100,00 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 8 | 0 / 8 | 7 (87,50 %) | 1 (12,50 %) | 8 / 0 | 8 (100,00 %) |

#### 7.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 140 | 140 / 0 | 140 (100,00 %) | 0 (0,00 %) | 140 / 0 | 0 (0,00 %) |
| Title | 26 | 26 / 0 | 21 (80,77 %) | 5 (19,23 %) | 26 / 0 | 5 (19,23 %) |
| Figure | 53 | 53 / 0 | 27 (50,94 %) | 26 (49,06 %) | 1 / 52 | 53 (100,00 %) |
| Table | 6 | 6 / 0 | 3 (50,00 %) | 3 (50,00 %) | 0 / 6 | 6 (100,00 %) |
| Caption | 20 | 20 / 0 | 20 (100,00 %) | 0 (0,00 %) | 7 / 13 | 13 (65,00 %) |
| Equation | 1 | 1 / 0 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 0 (0,00 %) |
| Margin | 47 | 47 / 0 | 47 (100,00 %) | 0 (0,00 %) | 8 / 39 | 39 (82,98 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 6 | 0 / 6 | 5 (83,33 %) | 1 (16,67 %) | 6 / 0 | 6 (100,00 %) |

#### 8.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 414 | 414 / 0 | 387 (93,48 %) | 27 (6,52 %) | 411 / 3 | 27 (6,52 %) |
| Title | 65 | 65 / 0 | 20 (30,77 %) | 45 (69,23 %) | 65 / 0 | 45 (69,23 %) |
| Figure | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Table | 14 | 14 / 0 | 5 (35,71 %) | 9 (64,29 %) | 0 / 14 | 14 (100,00 %) |
| Caption | 8 | 8 / 0 | 8 (100,00 %) | 0 (0,00 %) | 0 / 8 | 8 (100,00 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 48 | 48 / 0 | 47 (97,92 %) | 1 (2,08 %) | 8 / 40 | 41 (85,42 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 50 | 0 / 50 | 33 (66,00 %) | 17 (34,00 %) | 37 / 13 | 50 (100,00 %) |

#### 9.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 69 | 69 / 0 | 69 (100,00 %) | 0 (0,00 %) | 69 / 0 | 0 (0,00 %) |
| Title | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Figure | 65 | 65 / 0 | 34 (52,31 %) | 31 (47,69 %) | 3 / 62 | 65 (100,00 %) |
| Table | 0 | — | — | — | — | — |
| Caption | 17 | 17 / 0 | 17 (100,00 %) | 0 (0,00 %) | 0 / 17 | 17 (100,00 %) |
| Equation | 2 | 2 / 0 | 2 (100,00 %) | 0 (0,00 %) | 2 / 0 | 0 (0,00 %) |
| Margin | 27 | 27 / 0 | 27 (100,00 %) | 0 (0,00 %) | 6 / 21 | 21 (77,78 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 1 (100,00 %) |

#### 10.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 47 | 47 / 0 | 47 (100,00 %) | 0 (0,00 %) | 47 / 0 | 0 (0,00 %) |
| Title | 8 | 8 / 0 | 6 (75,00 %) | 2 (25,00 %) | 8 / 0 | 2 (25,00 %) |
| Figure | 7 | 7 / 0 | 3 (42,86 %) | 4 (57,14 %) | 0 / 7 | 7 (100,00 %) |
| Table | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 4 | 4 / 0 | 4 (100,00 %) | 0 (0,00 %) | 0 / 4 | 4 (100,00 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 0 | — | — | — | — | — |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 11.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 166 | 166 / 0 | 166 (100,00 %) | 0 (0,00 %) | 166 / 0 | 0 (0,00 %) |
| Title | 29 | 29 / 0 | 5 (17,24 %) | 24 (82,76 %) | 29 / 0 | 24 (82,76 %) |
| Figure | 50 | 50 / 0 | 26 (52,00 %) | 24 (48,00 %) | 2 / 48 | 50 (100,00 %) |
| Table | 6 | 6 / 0 | 3 (50,00 %) | 3 (50,00 %) | 0 / 6 | 6 (100,00 %) |
| Caption | 23 | 23 / 0 | 23 (100,00 %) | 0 (0,00 %) | 8 / 15 | 15 (65,22 %) |
| Equation | 0 | — | — | — | — | — |
| Margin | 82 | 82 / 0 | 82 (100,00 %) | 0 (0,00 %) | 18 / 64 | 64 (78,05 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 9 | 0 / 9 | 9 (100,00 %) | 0 (0,00 %) | 0 / 9 | 9 (100,00 %) |

#### 12.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 126 | 126 / 0 | 126 (100,00 %) | 0 (0,00 %) | 126 / 0 | 0 (0,00 %) |
| Title | 19 | 19 / 0 | 17 (89,47 %) | 2 (10,53 %) | 19 / 0 | 2 (10,53 %) |
| Figure | 70 | 70 / 0 | 38 (54,29 %) | 32 (45,71 %) | 6 / 64 | 70 (100,00 %) |
| Table | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 28 | 28 / 0 | 28 (100,00 %) | 0 (0,00 %) | 4 / 24 | 24 (85,71 %) |
| Equation | 8 | 8 / 0 | 8 (100,00 %) | 0 (0,00 %) | 8 / 0 | 0 (0,00 %) |
| Margin | 32 | 32 / 0 | 32 (100,00 %) | 0 (0,00 %) | 8 / 24 | 24 (75,00 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 2 | 0 / 2 | 2 (100,00 %) | 0 (0,00 %) | 1 / 1 | 2 (100,00 %) |

#### 14.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 446 | 446 / 0 | 343 (76,91 %) | 103 (23,09 %) | 443 / 3 | 103 (23,09 %) |
| Title | 58 | 58 / 0 | 47 (81,03 %) | 11 (18,97 %) | 58 / 0 | 11 (18,97 %) |
| Figure | 93 | 93 / 0 | 49 (52,69 %) | 44 (47,31 %) | 5 / 88 | 93 (100,00 %) |
| Table | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Caption | 45 | 45 / 0 | 45 (100,00 %) | 0 (0,00 %) | 6 / 39 | 39 (86,67 %) |
| Equation | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Margin | 66 | 66 / 0 | 63 (95,45 %) | 3 (4,55 %) | 13 / 53 | 56 (84,85 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 10 | 0 / 10 | 10 (100,00 %) | 0 (0,00 %) | 9 / 1 | 10 (100,00 %) |

#### 15.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 348 | 348 / 0 | 208 (59,77 %) | 140 (40,23 %) | 343 / 5 | 140 (40,23 %) |
| Title | 66 | 66 / 0 | 52 (78,79 %) | 14 (21,21 %) | 66 / 0 | 14 (21,21 %) |
| Figure | 66 | 66 / 0 | 35 (53,03 %) | 31 (46,97 %) | 5 / 61 | 66 (100,00 %) |
| Table | 29 | 29 / 0 | 14 (48,28 %) | 15 (51,72 %) | 0 / 29 | 29 (100,00 %) |
| Caption | 35 | 35 / 0 | 35 (100,00 %) | 0 (0,00 %) | 5 / 30 | 30 (85,71 %) |
| Equation | 9 | 9 / 0 | 9 (100,00 %) | 0 (0,00 %) | 9 / 0 | 0 (0,00 %) |
| Margin | 110 | 110 / 0 | 102 (92,73 %) | 8 (7,27 %) | 23 / 87 | 95 (86,36 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 31 | 0 / 31 | 31 (100,00 %) | 0 (0,00 %) | 16 / 15 | 31 (100,00 %) |

#### 17.pdf

| Category | N | Cat. C / A | Function C n (%) | Function A n (%) | Subtype C / A | Warnings n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Text | 367 | 367 / 0 | 282 (76,84 %) | 85 (23,16 %) | 357 / 10 | 85 (23,16 %) |
| Title | 75 | 75 / 0 | 5 (6,67 %) | 70 (93,33 %) | 75 / 0 | 70 (93,33 %) |
| Figure | 88 | 88 / 0 | 45 (51,14 %) | 43 (48,86 %) | 2 / 86 | 88 (100,00 %) |
| Table | 14 | 14 / 0 | 7 (50,00 %) | 7 (50,00 %) | 0 / 14 | 14 (100,00 %) |
| Caption | 29 | 29 / 0 | 29 (100,00 %) | 0 (0,00 %) | 5 / 24 | 24 (82,76 %) |
| Equation | 5 | 5 / 0 | 5 (100,00 %) | 0 (0,00 %) | 5 / 0 | 0 (0,00 %) |
| Margin | 70 | 70 / 0 | 65 (92,86 %) | 5 (7,14 %) | 12 / 58 | 63 (90,00 %) |
| Other | 0 | — | — | — | — | — |
| Ambiguous | 61 | 0 / 61 | 30 (49,18 %) | 31 (50,82 %) | 20 / 41 | 61 (100,00 %) |

### Pending structural issues and deferred decisions: do not confuse with errors

The example of a parent with bbox and child with text but bbox=null represents
preserved content with pending geometry, not text loss or a proven semantic error.
The current output has **374 textual children without boxes and 19 index parent containers**
with preserved boxes. This is a decision explicitly deferred by the user.
Do not impute the parent's box to the child, delete records or lift abstentions.

Three related levels are distinguished and must not be summed:

1. **Children without boxes: 374.** Preserved individual pending geometry.
2. **Inherited page abstention: 473 units on 17 pages.** Includes children,
   parents and other records affected by the conservative full-page rule.
   This does not imply that all those records have invalid geometry.
3. **Pending container function: 457 containers.** A general pending issue in the
   current design; only 19 are the index parents of these children. Do not attribute all
   457 to the incident involving children without coordinates or to a new human decision.

The union of pending-container and page-geometric-abstention flags has
**910 units**, all with abstained function: 457+473−20=910. The 374 flags for
children without boxes are included in page abstention. The overlap of 20
containers on abstained pages does not equal the 19 index parents: there is also
another affected container. **910 of the 1155 abstentions (78,79 %) have at least
one of those structural flags**; 245 have neither. This association of reasons
does not demonstrate exclusive causality or allow pending cases to be declared correct.

These units are not excluded from official denominators and artificially higher
coverage is not recalculated. Nor do they automatically become 910
individual human reviews: design/policy decisions could
resolve families of cases in the future, if a separate increment is agreed.

| Paper | Abstained pages | Children without boxes | Index parents with boxes | Pending containers (all) | Units with page abstention | Structural union |
| --- | --- | --- | --- | --- | --- | --- |
| 1.pdf | 1 | 20 | 1 | 27 | 31 | 57 |
| 2.pdf | 2 | 20 | 2 | 24 | 63 | 84 |
| 3.pdf | 0 | 0 | 0 | 9 | 0 | 9 |
| 4.pdf | 0 | 0 | 0 | 8 | 0 | 8 |
| 5.pdf | 0 | 0 | 0 | 17 | 0 | 17 |
| 6.pdf | 0 | 0 | 0 | 67 | 0 | 67 |
| 7.pdf | 0 | 0 | 0 | 29 | 0 | 29 |
| 8.pdf | 1 | 24 | 3 | 16 | 31 | 44 |
| 9.pdf | 0 | 0 | 0 | 31 | 0 | 31 |
| 10.pdf | 0 | 0 | 0 | 5 | 0 | 5 |
| 11.pdf | 0 | 0 | 0 | 27 | 0 | 27 |
| 12.pdf | 0 | 0 | 0 | 36 | 0 | 36 |
| 14.pdf | 3 | 100 | 3 | 55 | 109 | 161 |
| 15.pdf | 5 | 135 | 5 | 51 | 151 | 197 |
| 17.pdf | 5 | 75 | 5 | 55 | 88 | 138 |

**Form of functional abstentions:** 694 without a candidate; 432 with one candidate but a blocked decision; 29 with several candidates. These are mutually exclusive partitions and sum to 1155. This distinguishes lack of evidence, restrictions and competing proposals.

**Pending subtypes:** 895 without a candidate and 799 with several candidates, total 1694. Several subtypes may be compatible (for example heading and recurring margin); do not interpret this count as 1694 actual semantic conflicts. The rules were not changed to correct this in this expansion.

### Interpretation limits and documentation verification

Warnings are not confirmed errors or an estimate of human time.
Decisions without warnings are not validated either. Precision, recall,
macro-F1, confusion matrix and error among issued decisions require an
independent human reference; they remain pending until the end of the MVP.
Future review must include automatic proposals and abstentions, separated
by paper/format and without treating development cases as independent validation.

Sums by paper, category and unit type were verified; C+A=N for every dimension
and stratum; equality with summary.json; N=0 as not applicable; preserved
children/parents/statuses and original-output hashes before/after. The classifier was neither
imported nor invoked. The viewer was not modified and models/OCR/Colab were not run.
[Verification of this expansion](../results/sic_collection/functional-classification-reconciled-v2-metrics/verification.json).
The complete previous report is preserved in
`docs/history/20261026-functional-classification-v2-metrics/before/analytics/reports/`.
