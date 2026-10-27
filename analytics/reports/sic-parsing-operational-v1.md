# Operational collection parsing — results

26oct2026. Authorized increment without GROBID: automated operational structure,
route connection and canonical integration. 15 papers/397 pages were processed with the same
code/configuration, without per-paper adjustments or manual intervention. Source: reconciled
version/classificationv2 and readingv1; geometric Docling as baseline. Approved
12.pdf caches reused by identity, without repeating its previous trial.

[Index and views of all papers](../results/sic_collection/parsing-operational-v1/index.html),
[metrics](../results/sic_collection/parsing-operational-v1/summary.json),
[final queue](../results/sic_collection/parsing-operational-v1/review-queue.json),
[manifest](../results/sic_collection/parsing-operational-v1/manifest.json),
[audit](../results/sic_collection/parsing-operational-v1-audit/verification.json),
[order comparison](../results/sic_collection/parsing-operational-v1-audit/comparison.json).
Contract/methods: [README](../../code/document_pipeline/README.md).

## Technical result

5374/5374 units and 4512 content occurrences preserved. 374 children without bbox,
19 parents and 17 pages with abstention intact: no imputed boxes or lifted
abstentions. 478 section nodes proposed, 185 with parent and 198 with unknown level;
they are not 478 confirmed sections. 3298 units have proposed section context;
1622 paragraph fragments without concatenation. 24 capsules move to the metadata flow.
4595 local precedence constraints proposed, 4 suspended; zero operational cycles.
All sources, original classifications, boxes, texts and previous associations
remain verifiable. No OCR, new inference, GROBID, renders or Colab.

|Paper|Pages|Units|Proposed sections|With parent|Unknown level|Deferred children|Route changes|
|---|---:|---:|---:|---:|---:|---:|---:|
|1|26|331|27|0|27|20|0|
|2|12|303|21|9|1|20|0|
|3|4|89|11|3|4|0|0|
|4|4|94|12|4|4|0|0|
|5|9|204|17|8|1|0|3|
|6|26|390|29|19|5|0|0|
|7|14|299|25|12|3|0|5|
|8|49|607|66|27|30|24|8|
|9|12|187|9|0|0|0|2|
|10|9|69|8|0|1|0|1|
|11|21|365|29|0|25|0|0|
|12|13|293|21|10|4|0|5|
|14|68|740|61|40|12|100|0|
|15|59|694|68|53|9|135|0|
|17|71|709|74|0|72|75|0|

## Connection and comparison

Structure contributes parent→subsection precedence when geometry and hierarchy are
compatible. Zones/capsules delimit local relations; metadata migrate only if
all capsule content has front-matter support. Cycles/conflicts suspend
the new proposal and preserve alternatives; internal caption-first order remains intact.
Containers and shared references are retained; no region is removed.

1139 content positions differ from Docling, including index changes
from moving metadata: not 1139 corrected errors. Among 23563 comparable pairs within the
same page/flow, 174 reverse direction; pairs across different flows are not scored.
The audit records readingv1→Docling→operational differences per paper.

Bounded comparison with the agent's previous review of 12.pdf: 129/129 relations
that had been considered Docling corrections retain their direction. Of 6 previous regressions,
4 reverse direction and 2 remain across separate flows. This does not imply global accuracy:
the earlier review is not human GT and covered only 168 pairs. 33 indeterminate cases
remain unadjudicated (25 same direction, 3 changed, 5 different flows).

## Validation and limitations

13 offline tests pass, including automatic export of two fixtures, identity,
no-overwrite, capsules, abstained pages, hierarchy and absence of dependency on
section names. Independent review found no reproducible P1/P2 issues. Freeze of
new code and reused dependencies/templates verified before/after.
4764 DOM cases in the 15 HTML files/397 pages, 10748 step selections and section
navigation; no real visual QA. Previous file:// policy prevents automating that review;
no attempt was made to bypass it. Original PNGs copied byte for byte, without recompression.

Structure remains partial. Unlocated outlines and headings with encoding
differences may remain distinct hypotheses with ambiguous numbering.
Native levels and marker depth have different origins and are preserved
separately. Semantic classification, visual thematic membership and continuity
require final evaluation; geometric agreement does not demonstrate the same section.
Without sufficient native text, the parser source and per-dimension abstention are preserved.
No weights were learned and no training used 12.pdf; only frozen generic heuristics.

The 5374 units retain a warning under after_full_mvp policy, not 5374 errors.
An unknown new role does not invalidate its physical category or previous function.
Ambiguous metadata or mixed capsules may remain in the previous flow with a warning;
perfect semantic separation is not guaranteed. Two columns are insufficient to decide
independence: provisional Docling presentation and explicit alternatives.

The canonical integration of this stage has a single entry point and per-paper results;
it does not change parsers/ZIPs or invent a validated ensemble. Semantic quality, visual QA
and V&V with an independent reference remain pending. Do not claim universal improvement because
the 15 papers completed technically. Human review accumulates at the end, without blocking.
GROBID remains postponed by user decision; its download was stopped, without deleting
caches or changing the preserved code. Do not resume it automatically.

Frozen export: do not repeat or adjust rules per document. New errors
are documented for a separate increment, without modifying these results.

Candidate continuity by status: {"candidate_ambiguous": 102, "candidate_supported": 127, "blocked_deferred": 16}.
Section statuses: {"aligned_unique": 103, "ambiguous_numbering": 10, "heading_proposal": 120, "unresolved_heading_candidate": 235, "unlocated": 10}.
Papers with preserved native extraction failure: [].
