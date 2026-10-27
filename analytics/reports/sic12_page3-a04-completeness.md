# A04 Visible completeness of regions and crops

October 24, 2026. Stage executed after closing A03 and receiving two
explicit user decisions: caption with label and description in the same
crop, and table with complete content and structural borders. A05/A06 not yet
executed. No new inference, E03, GT or reconciliation.

## Question C01 and method

What content appears mixed or clipped and what requires review? The
21 existing original crops (2 TATR, 19 MinerU), extracted unchanged
from their verified ZIPs, were inspected. They were compared with the render and
A02/A03 evidence. The 23 LM records exported no crops: their previous visible scope
is preserved, but the usefulness of a nonexistent crop remains indeterminate. No
synthetic crops were generated to present as model exports.
The 4 MinerU containers remain contextual only, without double counting.

Observations concern visible content on this page, not OCR
accuracy, LaTeX, scientific content or paragraph completeness throughout the document.
Omissions are not decided without a reviewed reference. The review is by the assistant,
not independent human annotation. Indeterminacy is recorded without assuming
pixel tolerances or quality thresholds.

## Relevant results

| Evidence | Observation | Result against the agreed criterion |
| --- | --- | --- |
| TATR q5/q7 | Visible table content; outer rules outside the crops | Does not satisfy complete structural borders |
| MinerU p0-b2-c1, upper table | Content present; part of the lower rule stroke is outside | Does not satisfy complete border |
| MinerU p0-b4-c1, lower table | Dark lower stroke visible; one gray antialiased border row is outside | Strict border extent indeterminate, without invented tolerance |
| MinerU p0-b2-c0/p0-b4-c0 | Description visible without Table1/Table2 | Does not satisfy complete caption in the same crop |
| MinerU p0-b3-c1/p0-b9-c1 | Fig1/Fig2 and description in the same crop | Apparently satisfies the criterion at the inspected visual level |
| MinerU p0-b3-c0/p0-b9-c0 | Figures with axes or Fuel rod/Cladding, without unrelated table/caption | Visible content apparently preserved; not certified pixel by pixel |
| MinerU p0-b12 | Pressure paragraph with preceding direction. fragment at the top edge | Unrelated content observed; requires review |
| MinerU p0-b8/p0-b10 | Left ending commercial FE software and right beginning Abaqus... | Possible item2 continuity across columns; complete semantic unit not certified in crop p0-b8 |
| LM 23 records | No exported crops; A02 mixed/partial scopes preserved | Crop usefulness indeterminate; not zero or an inference failure |

Title, header, page, introduction, visible text and equation have individual
records in review.json, including apparently preserved cases and limitations
from page fragments. Apparent visual compliance does not equal transcription
accuracy or individual human approval. No quality percentage is calculated
from these statuses or the crop count.

## Fine border evidence and crop_clipped

The upper MinerU crop has integer bbox [114,231,1564,428], with exclusive lower
endpoint 428. In the render, the lower rule has RGB(189,189,189) samples
at y427, (15,15,15) at428 and (0,0,0) at429, verified at x300/700/1200. The crop
retains only the first of those rows: part of the dark stroke lies outside.

The lower one ends at exclusive y1526; it retains the dark stroke at1524/1525,
but gray row1526 RGB(203,203,203) is outside, verified at x300/500/700.
This is not resolved with an unagreed tolerance: indeterminacy is preserved
for the strict border. Values are image samples, not GT annotation or
an automatic rule to decide other tables' quality.

MinerU crop_clipped=false does not guarantee complete content: it indicates absence
of clipping to the frame, not preservation of labels, rules or unrelated text. The predicted
floating-point box and integer crop remain separate.

## Revision of a previous interpretation

Reading left item2 together with the right Abaqus... text suggests a
cross-column continuation. Therefore the previous A02/Q02 judgment describing
LM r12 list as incorrectly classified prose was too strong. A04
leaves it as possible list continuation, without validating reading order or
modifying the original label. The list/text difference remains descriptive;
it is not considered a confirmed class error. A03 geometry does not need recalculation.

A02/A03 records are preserved as historical evidence; this review has
interpretive priority when synthesizing C01. An initial A04 pass was preserved
as draft-first-pass files; the current output is review.json with its manifest.

## Evidence, verification and limitations

Directory analytics/results/sic12_page3/a04-20261024/: review.json,
review-manifest.json, review-status.json, crop-inventory.json, 21 original crops,
boundary-pixels.json, recipe and verifier, export-check.json.
48 exact references, 21 crops byte for byte against ZIPs, input/record/recipe
hashes and pixel samples against the render were checked. This is technical
verification of evidence; it does not automatically prove visual judgments.
Production code did not change: historical inference/analytics suites are not
repeated for this documentary review. Verification is specific to the increment.

A04 closes with these explicit limits: LM crops unavailable, lower
MinerU border strictly indeterminate, cross-column continuity as a
hypothesis, without a complete omission audit or geometric reference.
The persistent objective continues. A05 requires agreement on what counts as a useful
contribution: diagnostic advantage of separation/category versus strict usefulness
of the crop. Neither will be silently chosen and selection will not use score/IoU.
