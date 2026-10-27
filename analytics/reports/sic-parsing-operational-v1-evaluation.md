# Documentary evaluation of the 15 papers

Synthesis of the saved result, without new processing, tuning or adjudication.
[Technical report](sic-parsing-operational-v1.md), [consolidated metrics](../analyses/collection/parsing-operational-v1-evaluation.json),
[order comparison](../results/sic_collection/parsing-operational-v1-audit/comparison.json)
and [views/JSON](../results/sic_collection/parsing-operational-v1/index.html).

## Assessment

Useful automated technical MVP, more integrated than the geometric Docling component
used as baseline. Uneven semantic quality and still no global accuracy measurement.
It was not compared against the full Docling neural pipeline, which was not run.
Same configuration across 15 papers / 397 pages; originals, 5,374 units and 4,512
occurrences preserved. No manual document-specific adjustments or GROBID.

## Contributions relative to the baseline

- Structure and route connected through IDs, sources, statuses and alternatives: 478 proposed nodes, 185 with parent and 3,298 units with section context.
- 24 capsules move to the metadata flow as traceable proposals, without duplicating captions or content.
- 174 of 23,563 comparable pairs reverse direction (0.74%). These are not 174 corrected errors. The 1,139 distinct positions include shifts from separating metadata.
- In the agent's previous review of 12.pdf, the 129 relations considered Docling improvements are retained; four of six regressions reverse direction and the other two remain in separate flows. This covers only previously reviewed cases, not human GT or global accuracy.
- All outputs have JSON/comparative viewer and verifiable provenance. Technical automation on 15 documents does not demonstrate universal precision.

## Per paper

Pending function counts only content occurrences, excluding containers and
deferred children. Changed pairs exclude elements moved to another flow; these are not
confirmed errors. Section nodes may contain unreconciled hypotheses.

| Paper | Changed pairs vs Docling | Pending function / content | Unknown level / nodes | Deferred children |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0 | 32 / 284 | 27 / 27 | 20 |
| 2 | 7 | 40 / 256 | 1 / 21 | 20 |
| 3 | 0 | 1 / 80 | 4 / 11 | 0 |
| 4 | 9 | 0 / 86 | 4 / 12 | 0 |
| 5 | 22 | 1 / 185 | 1 / 17 | 0 |
| 6 | 84 | 4 / 321 | 5 / 29 | 0 |
| 7 | 27 | 3 / 269 | 3 / 25 | 0 |
| 8 | 0 | 41 / 567 | 30 / 66 | 24 |
| 9 | 4 | 0 / 153 | 0 / 9 | 0 |
| 10 | 0 | 2 / 64 | 1 / 8 | 0 |
| 11 | 1 | 24 / 336 | 25 / 29 | 0 |
| 12 | 8 | 1 / 251 | 4 / 21 | 0 |
| 14 | 2 | 14 / 580 | 12 / 61 | 100 |
| 15 | 1 | 22 / 503 | 9 / 68 | 135 |
| 17 | 9 | 111 / 577 | 72 / 74 | 75 |

The hierarchy is especially incomplete in 1, 11 and 17. Papers 6, 7 and 5 account for
133 of 174 pair changes: a verification priority, not adjudicated errors.
Paper 17 accounts for 111 of 296 pending content functions. Paper 9 has no
proposed subsections; zero parent does not by itself imply failure in a flat paper.

## Uncertainty and review: different denominators

| Measure | Cases | Interpretation |
| --- | ---: | --- |
| Final review by policy | 5,374 units | Not all are errors or ambiguous |
| Any inherited warning | 2,471 units | Previous warnings preserved |
| Unknown category or function, deduplicated union | 1,292 units | 24.0% of inventory; includes deferred structures |
| Unknown category | 209 units | Does not equal lost text |
| Unknown function | 1,127 units | 374 children + 457 containers + 296 content occurrences |
| Unknown function in content | 296 / 4,512 | 6.6%; previous category may be resolved |
| Explicit semantic contradiction | 25 units | Alternatives per dimension preserved |
| Unknown section level | 198 / 478 nodes | 41.4%; do not treat an absent parent as synonymous with error |
| Ambiguous numbering | 10 nodes | Hypotheses preserved |
| Unlocated heading | 10 nodes | Do not force identity by proximity |
| No section context in main flow | 123 units | The 1,536 outside the main flow are not counted as this failure |
| Ambiguous continuity | 102 relations | Do not accept based on consecutiveness or topic |
| Blocked continuity | 16 relations | Abstention/insufficient native alignment; not all are children without bbox |
| Supported continuity | 127 relations | Still a candidate, not validated |
| Suspended precedence | 4 relations | Hierarchy/geometry contradiction; zero operational cycles |

Do not sum rows: units, nodes and relations have different granularities and
overlaps. 4,878 units do not receive a more specific document role; they retain
their previous category/function. That unknown auxiliary field does not mean 4,878
completely unclassified units.

## Limitations still open

103 nodes have unique native alignment; 235 are unresolved heading candidates,
120 heading proposals, 10 ambiguous numberings and 10 unlocated. Outlines
and headings with encoding differences may represent duplicate hypotheses.
Native levels and marker depth have different origins; the contract explains
how to interpret them. Physical membership depends on the route; it does not demonstrate thematic
membership of figures/tables. Mixed metadata and independent columns/flows may still
remain provisional. The 374 children without boxes and their 19 parents are retained;
the 17 abstained pages are not forced into individual reading.

13 offline tests and 4,764 DOM cases support integrity/interaction, not comprehension.
Real visual QA and an independent semantic reference remain pending. No
precision/recall/F1 is calculated or global improvement claimed without adjudication at the end of the MVP.
GROBID remains postponed. This report does not authorize corrections or another export.
