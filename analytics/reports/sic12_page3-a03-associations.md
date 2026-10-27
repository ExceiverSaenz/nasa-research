# A03 Correspondences and disagreements between predictions

October 24, 2026. Method approved by the user through the selection
“Approve A03 as proposed (recommended)”. Stage A03 executed alone;
A04/A05/A06 not yet executed. Proposal preserved in sic12_page3-a03-proposal.md.

## Question C01 and scope

Where do parsers agree and differ in delimiting and classifying regions?
The 18 A02 cases were organized as explicit visual associations and cross-model
pairs were measured within each case, without filtering by class, score,
area or intersection. D05 supplies 44 segments; the 4 MinerU containers are
preserved only as context. TATR is compared on the two tables, without penalizing it
for unsupported categories. There is no automatic matching or reference objects.

## What was done

exploration/proximity.py was created for S01, associations.py for references,
roles, cardinalities and pair enumeration, and run_associations.py for
verification/export. Command analytics/associate_regions.py --output CARPETA_NUEVA.
Roles and ambiguities are attributed to A02 visual judgment, not a decision by the
measures. Cardinality and ambiguity remain separate; several candidates may mean
redundancy or mixed scope, not necessarily one-to-many granularity.

The A/B pair follows LM,TATR,MinerU order. Each pair is saved once with all
its related cases; Q02 is not recalculated within each model. Boxes,
labels and selection are not altered. No union boxes are formed to measure groups.

## Results

- 18 association records: 16 with cross-model candidates and 2 without a cross-model pair
  (header/page), with availability explained.
- 48 traced records: 44 selected and 4 contextual containers.
- 44 unique cross-model pairs; all 132 S01 measures are computable on these data.
  Do not confuse 44 pairs with 44 selected segments: they are different units.
- 9 cases retain an ambiguity flag for partial, redundant
  or mixed-scope alternatives. These are not 9 confirmed independent errors.
- 19 pairs have different analysis_label values. This includes legitimate
  taxonomy differences and mixed boxes: not a count of 19 classification errors.

| Pair (A→B) | IoU | Containment of A in B | Containment of B in A |
| --- | ---: | ---: | ---: |
| LM r20 → TATR q5, upper table | 0.899373 | 0.899373 | 1.000000 |
| LM r20 → MinerU p0-b2-c1 | 0.959481 | 0.990824 | 0.968083 |
| TATR q5 → MinerU p0-b2-c1 | 0.878731 | 1.000000 | 0.878731 |
| TATR q7 → MinerU p0-b4-c1 | 0.878187 | 1.000000 | 0.878187 |
| LM r5 → MinerU p0-b7, first item | 0.366384 | 0.368067 | 0.987673 |
| LM r5 → MinerU p0-b8, second item | 0.624496 | 0.634970 | 0.974265 |
| LM r21 → MinerU p0-b13, equation | 0.042074 | 0.042104 | 0.983336 |

Rounding for presentation only. Full analytical values and complete IDs
are in associations.json. No thresholds are used to interpret these examples.

## Interpretation and evidence type

Geometric fact: TATR q5/q7 boxes are contained in MinerU table
bodies, with smaller area. This is compatible with the visual observation of
very tight borders; it does not prove which crop is complete or correct.

Preserved A02 visual judgment: r20 is an upper-table candidate; it is not discarded
for low confidence. Its agreement with the MinerU table does not make it GT.
Mixed LM boxes remain ambiguous-scope candidates even if they contain
much of another box.

The list has cardinality 1:2, retaining list versus text classes without
forcing one-to-one agreement. For captions, the LM label and description are recorded
as components relative to the MinerU caption, without assuming equal recovered content.

The equation is almost contained in r21, but occupies a small part of that
box. It illustrates why high containment does not imply good delimitation
or the same semantic object. r21 is linked to several right-hand blocks; it is not split
or counted as new detections for each case.

Technically checked results: integrity, pair scope, typed provenance
and S01 arithmetic. No validated detection accuracy. Complementarity
and usefulness are hypotheses/cases for evaluation in A04/A05, not automatic consequences
of geometric agreement. Header/page without a cross-model candidate are not declared
omissions or false negatives.

## Evidence and verification

Derivatives in analytics/results/sic12_page3/a03-20261024/: associations.json,
association-manifest.json, association-status.json, local-tests.txt,
inspect_export.py and export-check.json. A02 overlays/crops are linked without repeating
their historical review. Manifest: hashes of A02,P03,P04,S01, approved proposal and
code. The distinction between method approval and independent human
validation of each judgment is preserved.

9 new tests plus 35 previous ones: identical/disjoint/touching geometry, inclusion,
containment swapping, invalid/different frame, nonfinite values,
cardinality/ambiguity, references, absent categories, deduplication and actual
execution path. Independent Decimal audit of 132 measures with tolerance 1e-12 and
independent enumeration of pairs/cases, coverage and input hashes.
No new inference, E03, confidence-based selection, GT, reconciliation or GPU.

## Limitations and A04 gate

A03 closes as a traceable descriptive comparison; explained ambiguity is a
result and no winner is forced. The page does not represent the collection and
cases are not independent replicates. Pairs without intersection are retained:
they may correspond to different components of the same described caption.

Executing A04 requires methodological decisions: whether a usable caption
requires label+description together and whether a usable table must include
outer rules. Options and a recommendation will be requested before evaluating
completeness/usefulness under either criterion. A crop without a label
or outer rule is not silently assumed correct or incorrect.
The A03–A06 objective remains active; A04 awaits those decisions, not a generic
“let's continue” message. A05/A06 are not yet executed.
