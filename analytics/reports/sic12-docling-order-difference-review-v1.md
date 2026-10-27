# Docling order differences against the baseline: 12.pdf

The user's observation—Docling looks much better visually—is supported
by several cross-column continuity corrections in the saved output. There are also
specific regressions and relations still lacking sufficient adjudication.
No rules were adjusted, Docling rerun, or OCR or neural models executed.

## Scope and evidence

The 168 content pairs whose precedence differs between the two outputs were reviewed,
across 13 pages and their routes. Reconciled boxes, text extracted directly
from the PDF with PyMuPDF and original renders were compared. Visual inspection of originals: pages
1, 2, 3, 4, 9; for the others, boxes and native region text. No new
browser interface inspection was performed and no renders/crops/boxes were created.

This is documentary adjudication by the agent, pending final human review;
not human GT or an evaluation of the entire sequence. Pairwise relations
overlap: one recovered continuity may correct several pairs simultaneously.
Do not interpret 129/168 as accuracy, precision or a general success rate.

| Assessment of changed precedence | Pairs |
| --- | ---: |
| Supported correction | 129 |
| Supported regression | 6 |
| Indeterminate | 33 |
| Total reviewed | 168 |

## Supported corrections

| Physical page | Evidence of correct order | What changes |
| --- | --- | --- |
| 1 | Introduction: heading and left fragment before the right continuation starting severe degradation | Corrects two local precedence relations; does not fix the entire page |
| 2 | Section2/2.1 and the left ending magnitude of the swelling precede strain has inverse temperature dependence on the right | Avoids reading constitutive relations/equations before the start of their section |
| 3 | Left item2 ends commercial FE software and continues on the right Abaqus, while BISON... | Table2,3.1 and the list precede that continuation; restores column flow |
| 4 | Left text ends axial void and continues on the right distribution..., before4.Results | Improves cross-column precedence; retains a local inversion described below |
| 5 | Left ending says ...the and right starts fuel rod-cladding gap decreases... | Places conclusions and left-side development before4.1.2/4.1.3 on the right |
| 6 | At at the left end continues this time on the right | Corrects column transition in4.1.4 |
| 7 | Left ending relation continues of hoop stress on the right, before equations6–8 | Avoids bringing equations and right-side explanation forward |
| 8 | Left ending decreases continues with increasing temperature on the right | Restores continuity of the swelling explanation |
| 9 | Left ending was not continues considered for the stress evaluation on the right | Corrects body order before4.1.5 and4.2 |
| 11 | azimuthal at the left end continues power variation on the right | Recovers the sentence introducing Fig.22 |
| 12 | possible at the left end continues impacts from such... on the right, before Summary | Avoids bringing conclusions ahead of the end of the development |

Continuities are described as analysis evidence; no paragraph_continues
links were added or text merged in results. Hyphens, line breaks or
ligatures may differ between native and reconciled text; OCR was not corrected.

## Specific introduced regressions

Five cases explain six reversed relations:

1. **Page1, abstract versus introduction —2 pairs.** Baseline: abstract body
   before1.Introduction and its first paragraph. Docling moves the heading and that
   paragraph ahead of the abstract body. The abstract box is approximately
   [564,904,1570,1360] and the introduction at [112,1521,296,1550] and
   [109,1579,822,1669], XYXY pixels of the1654×2205 render. The original shows a
   horizontal dividing band: the abstract ends before the introduction.
2. **Page1, notes —1 pair.** Reverses Corresponding author and E-mail address. The original
   and boxes show the label first and the email below. This is not an OCR failure.
3. **Page2, left column —1 pair.** Docling places The current work focuses...
   before Recent studies[19–21]..., although Recent studies occupies y≈556–1400 and
   The current work y≈1398–1810. Baseline correctly preserved this local order.
4. **Page2, resistivity definitions —1 pair.** Changes the order of K0 and Krd. The original
   shows Kirr, K0, Krd vertically; baseline respected it and Docling swaps
   the last two. These are independent blocks with slightly overlapping boxes.
5. **Page4, left column —1 pair.** Places A section of the3D FE model...
   before Fig.4 shows the axial power profile..., although the Fig.4 text is
   above (y≈514–747) and the3D model text below (y≈745–953). Baseline did this correctly.

In the four local note/paragraph/definition cases, the boxes touch or
overlap by approximately2–4px. This is a clue compatible with geometric sensitivity,
not demonstrated isolated causality: no box, tolerance or rule was changed.
The abstract regression affects a broader composition change.

## Indeterminate cases and inherited pending issues

33 pairs: 9 on page1 (Crossmark/metadata/copyright and parallel flows), 14 on page4
(relative position of Table3/Fig4 and text), 10 on page9 (figures versus body).
The reviewed evidence does not yield a single adjudicated precedence for those
relations among floating content. Having a linked caption does not fix its precedence relative
to all neighboring blocks. This conservative decision does not declare those
orders correct or automatically turn all elements into independent flows.

The classification problems of authors/affiliations/editorial in main are inherited:
Docling neither created nor corrected them. Nor did it change internal panel order, associations,
caption first or hierarchy. The Crossmark image on page1 remains a figure without
an appropriate document function. Do not attribute these limitations to a new parser error.

Pages10 and13: no content-order changes; that does not validate their order. The
bibliography,metadata and editorial_navigation routes do not change; in notes only the
identified pair on page1 changes. Not all unchanged pairs were reviewed as correct.

## Breakdown of the168 changed pairs

| Page | Corrections | Regressions | Indeterminate |
| --- | ---: | ---: | ---: |
| 1 | 2 | 3 | 9 |
| 2 | 56 | 2 | 0 |
| 3 | 20 | 0 | 0 |
| 4 | 5 | 1 | 14 |
| 5 | 8 | 0 | 0 |
| 6 | 3 | 0 | 0 |
| 7 | 13 | 0 | 0 |
| 8 | 3 | 0 | 0 |
| 9 | 14 | 0 | 10 |
| 11 | 2 | 0 | 0 |
| 12 | 3 | 0 | 0 |

## Traceability and stopping point

- [168 pair assessments with IDs and positions in both routes](../results/sic12_document/docling-order-difference-review-v1/changed-pairs-review.json).
- [Boxes and native text per region](../results/sic12_document/docling-order-difference-review-v1/native-region-evidence.json).
- [Summary](../results/sic12_document/docling-order-difference-review-v1/review-summary.json).
- [Verification](../results/sic12_document/docling-order-difference-review-v1/verification.json).
- [Unchanged original HTML comparison](../results/sic12_document/docling-order-trial-v1-view/index.html).

baseline_indices/docling_indices are local content positions per
page/route; route_step_positions are the global positions including structures shown
by the viewer. Text extraction uses the ROI of existing boxes and may
include parts of neighboring lines when they overlap; original pages
support the described definition/note cases. This is not OCR or a validated transcription.

Bounded conclusion: Docling provides verifiable precedence improvements in the reviewed
cases and deserves to remain a candidate; not yet the sole authority on
order. Regressions justify reconciliation with native anchors and structure,
not automatic tuning in this round. Stop here: results/code intact, without a new
export or scope extension. Formal human semantic review after_full_mvp.
