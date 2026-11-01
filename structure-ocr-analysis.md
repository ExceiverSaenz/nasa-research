# Integrated analysis of bounding boxes, targets and structural usefulness

<a id="scope"></a>

## 1. Scope, evidence populations and evaluation priorities

> **Document role: Provisional findings.** Original statements retain their stage-specific scope. See [current status](docs/overview/current-status.md) for current completion and pending validation.

**Date:** November 1, 2026.  
**Scope:** four tools —Heron, Heron-101, MinerU Basic and MinerU Standard— on 15 papers and 397 pages.  
**Nature:** synthesis of existing results and a provisional technical decision; does not constitute global semantic validation.

This ordered analysis combines **G** (geometry v2), **T** (targets v1) and **C** (comparative conclusions) by question. Source identifiers retain their original section meanings through the [reference crosswalk](#crosswalk). Bare artifact filenames are relative to the explicitly identified [evidence directories](#artifacts).

**Contents**

- [1. Scope and priorities](#scope)
- [2. Shared method and assessment states](#method)
- [3. Geometric agreement, levels and granularity](#geometry)
- [4. Target census and reviewed assessment](#targets)
- [5. Detailed target functions](#functions)
- [6. Structural relationships](#relationships)
- [7. Repeated patterns and asymmetric conditionals](#patterns)
- [8. Observed cost](#cost)
- [9. Provisional decision and residual work](#decision)
- [10. Limits, verification and stopping point](#limits)
- [11. Human selections and complete case evidence](#cases)
- [12. Cross-dimension evidence tables](#evidence-tables)
- [13. Artifacts, sources and reference crosswalk](#artifacts)

The geometric delivery is `deep-20261101-v2`: 15 papers, 397 pages, 1,588 tool/page outputs, 35,240 native records and 19,597 valid boxes. It reuses existing predictions, backgrounds and metrics. The census covers all native targets, separated by level and bbox presence. Its six human-selected examples are separate from the agent reference population below. The source analyses ran no parsers, OCR, Colab, models or PDF renders.

- Block-level correspondences from the previous in-depth analysis, internal IoU >= 0.9 and one box per tool in a cluster; granularity relationships and child captions are kept separate.
- 65 ROIs visually inspected on already existing PNG files, with labels hidden in reference sheets. 4 repetitions of the same object (T031/T016,T062/T056,T063/T021,T064/T022) and 2 additional cases without an unequivocal single class (T024,T065) were excluded: 59 eligible unique objects remain, 236 tool/case assessments.
- The sample targets discrepancies plus controls, is not random: 19 headings, 10 visuals, 6 authors/affiliations, 5 captions, 4 texts, 4 references, 3 tables, 3 equations, 2 notes, 1 list, 1 number, and 1 date. Twelve of the 19 headings come from 8.pdf. Cases are unique by object, not statistically independent.
- The observed class was assigned by the agent from the visual background, not by tool majority or text extracted from a parser. Selection does depend on predictions, and the agent knows the project's hypotheses: it is not a fully blind trial. It is not called human validation.

The decision responds to the user's priorities, preserved in the [analysis plan](docs/methodology/analysis-plan.md), section 1:

- Prioritize coverage and consistency, especially in titles, captions and body text.
- Accept several consecutive paragraphs in one box if they belong to the same column and section.
- Accept a combined figure as a useful base, even if its components have not been separated internally.
- Give greater importance to preserving the shared caption than to immediately obtaining individual boxes for all panels.
- Avoid mixing columns, sections, text and visualizations, and respect boundaries marked by titles.
- Value correct specific labels; a title lost as `text` requires more work than text marked as a title.
- Prefer reconstructing a capability uniformly when its results are irregular, rather than reviewing the entire document to find exceptions.
- Compare time, memory and failures without setting a budget or overall score that the user has not agreed to.

Therefore, a geometric difference is not automatically penalized. **Localization and relative coverage, granularity, target, subtype and structural relationship** are distinguished. A box may be useful even if its label is general; a correct label may coexist with an incorrect relationship. [G, §§5, 9 and 12; T, §§2 and 7]

<a id="method"></a>

## 2. Shared method, bibliographic foundation and assessment states

Bibliographic query through official CLI/Bases/Fileclass/gateway: 8efd92ca022a433096fe643338bce152, review accepted. Continuity and inventory: 6ffb384b75694bc9aaea699d8349142c, review accepted. Original chapters without a document class were preserved as bibliography, without reclassifying them.

- Chapter 2, Data: normalized attributes, missing values, proximities, and discretization. Boxes use relative page coordinates; a missing child box is not filled in with the parent's.
- Chapter 3, Exploring Data: histograms, quantiles, and OLAP by tool/paper/page/category/level. Micro by area, mean by page, and macro by paper are distinguished.
- Chapter 4, Classification: a table between tools expresses agreement. An accuracy confusion matrix needs verified actual classes. Parser voting is not used as a reference.
- Chapter 6, Association Analysis: support/confidence/lift describe output co-occurrence, with denominators and per-paper breakdowns to avoid misleading aggregate conclusions. They are not probabilities of correctness.
- Chapter 8, Cluster Analysis: complete-link agglomerative clustering to avoid chaining regions through a bridge, with internal evaluation separate from external evaluation. It is restricted to one box per tool per cluster; that limit does not remove duplicates, it leaves them explicit.
- Chapter 9: limitations of clustering algorithms and proximities. K-means on centers is not used: boxes with the same center may have very different extents, and partitioning requires incorporating area.

IoU/containment rules, bands, and thresholds are experimental adaptations, not values prescribed by the book. Method frozen before computation in [PROTOCOL](deep_analysis/PROTOCOL.md). Independent review detected and corrections were made to: three omitted empty pages, complete-link merge priority, shared geometry hash, and timing of the human snapshot. V 1 is preserved as diagnostic; it is not the current delivery.

Methodological source: Data Mining chapter 4 (confusion matrix with a reference) and chapter 5 §5.7 (imbalanced classes, precision/recall, and asymmetric cost). CLI/Bases/Fileclass query/review: faae4823e31543b5aa5d75bb594b34f4, status reviewed. The book supports the method; it does not establish geometric thresholds or user weights. No numerical weights, scores, or reference classes based on size heuristics were invented.

Spatially corresponding blocks support comparison of the same content; the blocks do not establish its true class. Native labels are preserved, agent visual reference is explicit, and heading→text has higher ordinal priority than text→heading. No numerical user weights are inferred.

| State | Interpretation |
| --- | --- |
| adequate | The label corresponds to the visually observed family; subtype is checked separately |
| coarse_usable | General but usable: text for author, list_item for reference, header for editorial logo; does not necessarily identify the specific target of interest to you |
| contradictory | Multiple families on the same object that are not resolved into a single function; the favorable one is not silently chosen, nor are all declared false |
| wrong | Dedicated correspondence with an incompatible label and unequivocal visual reference |
| no_own_correspondence | No box reaches the dedicated correspondence criteria; this is separated from tagging error and is not turned into an overall semantic omission |
| excluded_reference | Ambiguous crop, a set of several classes, or repetition of the same object |

Affiliations can simultaneously be list items and notes; footnote/list_item is not penalized as a contradiction in that subtype. Bibliographic reference and list item are also compatible properties. picture/image/chart are first compared as a visual family, but original vocabulary and specificity are preserved. section_header/paragraph_title belong to headings; document_title versus section_heading is recorded separately.

Dedicated correspondence uses IoU >= 0.5, or box containment in ROI >= 0.9 with ROI coverage >= 0.5. A large group covering ROI >= 0.9 but not comparable is distinguished as group_coverage; its bbox is not copied to a child, nor is a specific label imputed to each part. Intersections and alternatives are preserved by case to review boundary sensitivity.

<a id="geometry"></a>

## 3. Geometric agreement, levels and granularity

<a id="correspondences"></a>

### 3.1. Six pairwise comparisons and IoU distributions

Basic and Standard are nearly identical in the measured geometry: area Jaccard is **99.999102 %**, and block-level area Jaccard is **99.999296 %**. Heron/Heron-101 surface agreement is 97.315 %; Heron/MinerU comparisons span 92.644–93.327 %, while median individual-box IoU is about .859–.862. Boundary/partition differences must therefore be distinguished from large surface differences.

| Pair | Positive pairs | Median IoU | Reciprocal matches | Reciprocal median | Total area IoU |
| --- | --- | --- | --- | --- | --- |
| Heron / Heron-101 | 5824 | 0.9753 | 4455 | 0.9832 | 97.315 % |
| Heron / MinerU Basic | 5934 | 0.8589 | 3886 | 0.8969 | 93.327 % |
| Heron / MinerU Standard | 5933 | 0.8590 | 3886 | 0.8969 | 93.326 % |
| Heron-101 / MinerU Basic | 5890 | 0.8618 | 3831 | 0.8965 | 92.644 % |
| Heron-101 / MinerU Standard | 5888 | 0.8619 | 3831 | 0.8965 | 92.644 % |
| MinerU Basic / MinerU Standard | 6309 | 1.0000 | 4091 | 1.0000 | 99.999 % |

All positive pairs include small intersections between neighbors and coincident parent/body boxes. They are not one-to-one matches; a box may participate several times. Reciprocal matches choose the highest IoU in both directions and exclude ties. This is a selected population, also not a true reference. Unmatched boxes are not turned into IoU 0 pairs.

| IoU | heron/heron101 | heron/basic | heron/standard | heron101/basic | heron101/standard | basic/standard |
| --- | --- | --- | --- | --- | --- | --- |
| [0.0,0.1) | 14.44 % | 13.06 % | 13.05 % | 15.28 % | 15.25 % | 7.32 % |
| [0.1,0.2) | 0.82 % | 2.58 % | 2.58 % | 2.46 % | 2.46 % | 0.13 % |
| [0.2,0.3) | 0.48 % | 1.85 % | 1.85 % | 1.65 % | 1.65 % | 0.00 % |
| [0.3,0.4) | 1.08 % | 1.67 % | 1.67 % | 1.43 % | 1.43 % | 0.00 % |
| [0.4,0.5) | 2.09 % | 3.42 % | 3.42 % | 2.46 % | 2.46 % | 0.00 % |
| [0.5,0.6) | 0.64 % | 3.25 % | 3.25 % | 3.26 % | 3.26 % | 0.00 % |
| [0.6,0.7) | 0.82 % | 7.04 % | 7.05 % | 6.76 % | 6.76 % | 0.00 % |
| [0.7,0.8) | 0.89 % | 9.93 % | 9.91 % | 9.15 % | 9.15 % | 0.00 % |
| [0.8,0.9) | 2.78 % | 15.28 % | 15.30 % | 15.42 % | 15.42 % | 0.00 % |
| [0.9,1.0] | 75.94 % | 41.91 % | 41.92 % | 42.14 % | 42.15 % | 92.55 % |

Intervals are closed on the left and open on the right; the last includes 1. Denominators by column: 5,824; 5,934; 5,933; 5,890; 5,888; 6,309. All 35,778 pairs are preserved in full. Basic/Standard: 5,827 pairs have IoU exactly 1, and 5,839 are in [.9,1]; 470 pairs are below .2. These are not 470 errors: they contain secondary intersections of different records.

![IoU distribution](docs/findings/assets/integrated-analysis/iou_histogram_heatmap.png)

**Figure 1.** Positive-pair IoU distributions across six tool pairs. Small secondary intersections remain in this population; the histogram is not an error-rate plot. The [original source figure](analysis/deep-20261101-v2/iou_histogram_heatmap.png) remains available.

<a id="surface"></a>

### 3.2. Covered surface independent of box count

A sweep through all x/y boundaries produces disjoint geometric cells. Each cell preserves which tools and category sets cover it; areas are not counted twice. Area IoU is intersection of unions / union of unions. No enclosing rectangle is used, nor is blank content inferred.

![Surface agreement](docs/findings/assets/integrated-analysis/area_agreement.png)

**Figure 2.** Agreement between unions of predicted areas. This avoids double counting overlapping boxes, but does not establish true PDF coverage. The [original source figure](analysis/deep-20261101-v2/area_agreement.png) remains available.

Relative comparison does not identify who is right: area exclusive to a tool may be recovered content, padding, or mixing. There are 3 pages without boxes from any tool; they have Jaccard N/A, not 1 or 0. They are included in 397 pages and in association support. Mean Jaccard by page excludes those three N/A values and states this in its implicit denominator; it does not turn them into approval.

| Pair | Mean across papers | Minimum paper | Maximum paper |
| --- | --- | --- | --- |
| Heron / Heron-101 | 97.794 % | 92.892 % | 99.201 % |
| Heron / MinerU Basic | 93.427 % | 91.825 % | 95.497 % |
| Heron / MinerU Standard | 93.427 % | 91.825 % | 95.508 % |
| Heron-101 / MinerU Basic | 93.139 % | 87.071 % | 95.854 % |
| Heron-101 / MinerU Standard | 93.140 % | 87.071 % | 95.865 % |
| MinerU Basic / MinerU Standard | 99.998 % | 99.989 % | 100.000 % |

Pages with lowest Heron/Basic Jaccard for targeted inspection:

| Paper/page | Area IoU | Heron only (% page) | Basic only (% page) |
| --- | --- | --- | --- |
| 17.pdf / 58 | 0.0119 | 0.000 % | 42.646 % |
| 17.pdf / 3 | 0.3430 | 1.105 % | 0.115 % |
| 17.pdf / 2 | 0.3451 | 7.564 % | 1.116 % |
| 17.pdf / 5 | 0.4585 | 7.334 % | 0.735 % |
| 14.pdf / 2 | 0.4801 | 0.000 % | 18.109 % |
| 8.pdf / 1 | 0.5821 | 0.000 % | 10.001 % |
| 15.pdf / 7 | 0.6206 | 0.361 % | 0.507 % |
| 14.pdf / 3 | 0.6867 | 1.813 % | 0.836 % |
| 8.pdf / 4 | 0.6874 | 0.005 % | 0.123 % |
| 7.pdf / 6 | 0.6953 | 15.959 % | 1.794 % |

This is neither a random sample nor an error ranking. The “only” figures are divided by total page area. `comparison_by_paper.csv` and `page_metrics.csv` preserve all cases.

<a id="levels"></a>

### 3.3. Coincident geometries and native levels

| Tool | Records with a box | Unique geometries | Coincident groups |
| --- | --- | --- | --- |
| Heron | 4889 | 4806 | 83 |
| Heron-101 | 4777 | 4717 | 60 |
| MinerU Basic | 4966 | 4529 | 437 |
| MinerU Standard | 4965 | 4528 | 437 |

MinerU's 437 groups break down into 213 chart/chart_body, 162 image/image_body, and 62 table/table_body. They are a coincident parent/body representation; not 437 erroneously duplicated figures. Heron has 83 coincident groups; 35 are section_header/text, 16 footnote/list_item, and 12 page_footer/picture. Heron-101 has 60, including 19 section_header/text. Different labels on the same box must be preserved as alternatives/output ambiguity, without silently choosing one.

MinerU has 4,168 block-level boxes in each version; Basic adds 798 child boxes and Standard 797. Heron has 4,889 block and Heron-1014,777. Overall area counts per box mixed levels and categories. MinerU's overall median box is 2.40% of the page versus Heron's 1.28–1.31%, but that alone does not establish who groups more of the same content.

The [coincident-box summary](analysis/deep-20261101-v2/coincident_boxes_summary.csv) preserves the parent–body breakdown. Native count, box size and individual IoU alone cannot determine usefulness: content and meaningful boundaries must be preserved, while area may include whitespace or mix regions.

<a id="granularity"></a>

### 3.4. Block-level granularity candidates

Bipartite components are built with IoU >= 0.5 or containment >= 0.9. A 1:n/n: 1 group is a granularity candidate when union IoU >= 0.9, each small box has less than 0.98 of the large box's area, and the small boxes have redundancy <= 1%. This rejects large gaps, complete duplications, and n:m components. Small boxes may be panels or other kinds of parts: that meaning is not assigned automatically.

| Pair | 1:n | n:1 | Compatible granularity | 1:1 with different area | n:m | No strong link |
| --- | --- | --- | --- | --- | --- | --- |
| Heron / Heron-101 | 66 | 95 | 7 | 213 | 109 | 107 |
| Heron / MinerU Basic | 41 | 182 | 29 | 1649 | 37 | 343 |
| Heron / MinerU Standard | 41 | 182 | 29 | 1649 | 37 | 343 |
| Heron-101 / MinerU Basic | 41 | 139 | 29 | 1628 | 28 | 416 |
| Heron-101 / MinerU Standard | 41 | 139 | 29 | 1628 | 28 | 416 |
| MinerU Basic / MinerU Standard | 0 | 0 | 0 | 0 | 3 | 0 |

“No strong link” means no correspondence under this rule, not a confirmed omission. “1:1 with different area” does not distinguish padding, clipping, and different content: these are boundaries to review. The n:m cases are preserved; they are not flattened to force an answer.

In Heron/Basic, 26 of 29 candidates are one Heron box versus several Basic boxes; 3 are the reverse. The 26 include 24 visual/visual and 2 visual/header; they are not all called semantic equivalents. Of the 3 reverse cases, one includes caption/table versus table and another index/header versus index. Surface equivalence can coexist with a category or relationship difference. For visual/visual cases, granularity is a plausible and useful geometric explanation according to your priorities.

| Paper/page | Pair | Boxes A:B | Union IoU | Categories A/B |
| --- | --- | --- | --- | --- |
| 5.pdf / 1 | Heron / MinerU Basic | 1:2 | 0.9366 | ['visual'] / ['running_header'] |
| 9.pdf / 6 | Heron / MinerU Basic | 1:2 | 0.9183 | ['visual'] / ['visual'] |
| 9.pdf / 6 | Heron / MinerU Basic | 1:2 | 0.9469 | ['visual'] / ['visual'] |
| 15.pdf / 9 | Heron / MinerU Basic | 4:1 | 0.9071 | ['document_index', 'running_header'] / ['index'] |
| 15.pdf / 45 | Heron / MinerU Basic | 1:2 | 0.9181 | ['visual'] / ['visual'] |
| 6.pdf / 14 | Heron / MinerU Basic | 1:4 | 0.9645 | ['visual'] / ['visual'] |
| 6.pdf / 15 | Heron / MinerU Basic | 1:4 | 0.9641 | ['visual'] / ['visual'] |
| 6.pdf / 15 | Heron / MinerU Basic | 1:4 | 0.9672 | ['visual'] / ['visual'] |
| 6.pdf / 16 | Heron / MinerU Basic | 1:4 | 0.9716 | ['visual'] / ['visual'] |
| 6.pdf / 16 | Heron / MinerU Basic | 1:4 | 0.9699 | ['visual'] / ['visual'] |
| 6.pdf / 17 | Heron / MinerU Basic | 1:4 | 0.9703 | ['visual'] / ['visual'] |
| 6.pdf / 18 | Heron / MinerU Basic | 1:6 | 0.9005 | ['visual'] / ['visual'] |

![Located granularity example](docs/findings/assets/integrated-analysis/granularity_example.png)

**Figure 3.** The localized 6.pdf page 15 granularity example: one Heron visual region and four Basic blocks have similar union area; membership is a separate question. The [original source figure](analysis/deep-20261101-v2/granularity_example.png) remains available.

Reproducible example: 6.pdf, page 15. Heron has one visual box versus 4 Basic visual blocks; the union has IoU close to 0.96. Existing PNG backgrounds were reused without rendering the PDF again. At the geometric-comparison stage, membership of the parts and association of the shared caption had not been confirmed. This geometric example does not establish semantic membership; the later targeted diagnostic in [structural relationships](#relationships) finds an explicit Figure 8/Figure 9 caption-membership error on this page.

For the illustrated 6.pdf page 15 region, union IoU is approximately **0.9641**. The seven Heron/101 candidates and the four sets of 29 cross-family candidates overlap: they are not 123 independent cases. Basic/Standard has no compatible-granularity candidates under this rule. High geometric agreement does not establish semantic membership or shared-caption preservation.

<a id="sensitivity"></a>

### 3.5. Sensitivity across hierarchical levels

All 9 combinations of containment 0.85/0.9/0.95 and union 0.85/0.9/0.95 were tested across all localized levels:

| Pair | Minimum candidates | Maximum candidates |
| --- | --- | --- |
| Heron / Heron-101 | 2 | 9 |
| Heron / MinerU Basic | 0 | 6 |
| Heron / MinerU Standard | 0 | 6 |
| Heron-101 / MinerU Basic | 0 | 9 |
| Heron-101 / MinerU Standard | 0 | 9 |
| MinerU Basic / MinerU Standard | 0 | 0 |

This population includes parents/bodies. It therefore must not be compared as though it were the block table: in Heron/Basic the baseline value is 3 with all levels and 29 with block. The difference shows the effect of hierarchical representation. `granularity_sensitivity.csv` contains all numerators by page and threshold; the threshold maximizing agreement was not chosen. A case is not declared stable merely because it exists in one combination.

<a id="targets"></a>

## 4. Target census, spatial agreement and reviewed assessment

<a id="spatial-targets"></a>

### 4.1. Categories after spatial grouping

Clustering considers only coordinates through IoU and complete-link; each internal pair must reach 0.9, and there cannot be two boxes from the same tool in one cluster. Labels are read afterward. This is repeated at 0.8/0.9/0.95 in `cluster_sensitivity.csv`. Pages are not mixed to claim they contain the same object: cross-page patterns are repeated signatures, not content identity.

Across all levels there are 8,175 clusters, 7,219 with multiple tools and 820 with more than one descriptive category. Those 820 are not errors; they include different schemas and levels. At block level there are 6,453 multi-tool clusters. Conservative assessment uses the partial map already defined in the plan, with `unmapped` outside the evaluable denominator.

| Pair | Equivalent clusters | Comparable categories | Agree | Conditional agreement |
| --- | --- | --- | --- | --- |
| Heron / Heron-101 | 4271 | 3631 | 3594 | 98.981 % |
| Heron / MinerU Basic | 2093 | 1502 | 1384 | 92.144 % |
| Heron / MinerU Standard | 2093 | 1502 | 1384 | 92.144 % |
| Heron-101 / MinerU Basic | 2047 | 1469 | 1365 | 92.920 % |
| Heron-101 / MinerU Standard | 2047 | 1469 | 1365 | 92.920 % |
| MinerU Basic / MinerU Standard | 4168 | 2742 | 2742 | 100.000 % |

These percentages are agreement conditional on equivalent boxes, block level, and mapped categories. They do not measure all detections, heading recall, or accuracy. The first descriptive category layer across all levels must not be used as a winner: it includes child bodies without schema equivalence. The block table is the controlled comparison.

MinerU Basic and Standard agree on all 4,168 native labels in their equivalent block clusters, although only 2,742 enter the conservative analytical map. The other 1,426 are not discarded from the result: they are preserved as unmapped schema. They are not 1,426 errors.

| Heron | MinerU Basic | Equivalent cases | Comparison |
| --- | --- | --- | --- |
| text | text | 1070 | mapped |
| list_item | ref_text | 536 | partial schema/unmapped |
| picture | chart | 118 | mapped |
| list_item | text | 117 | mapped |
| picture | image | 103 | mapped |
| table | table | 57 | mapped |
| formula | equation | 19 | mapped |
| page_header | header | 15 | partial schema/unmapped |
| document_index | index | 14 | partial schema/unmapped |
| section_header | paragraph_title | 11 | mapped |
| picture | header | 7 | partial schema/unmapped |
| key_value_region | text | 6 | partial schema/unmapped |

The 536 Heron/Basic list_item/ref_text cases describe two ways to label nearly identical regions. Bibliographic reference and list item may be compatible properties, so that difference does not demonstrate tool failure. picture/chart and image express different schema resolution: chart is more specific, but not necessarily correct. formula/equation is vocabulary translation, not failure.

| Tool | Declared headings | Captions with dedicated box | Declared chart | Declared ref_text |
| --- | --- | --- | --- | --- |
| Heron | 563 | 271 | 0 | 0 |
| Heron-101 | 543 | 274 | 0 | 0 |
| MinerU Basic | 505 | 338 | 213 | 688 |
| MinerU Standard | 505 | 337 | 213 | 688 |

These counts are declared availability, not true frequency in the PDF. In particular, a dedicated MinerU caption may be a localized child; do not attribute children without boxes to caption or treat all spans as omitted elements.

<a id="census"></a>

### 4.2. Census and count bias

| Localized target | Heron | Heron-101 | Basic | Standard |
| --- | --- | --- | --- | --- |
| heading | 563 | 543 | 505 | 505 |
| text | 1815 | 1816 | 1730 | 1730 |
| caption | 271 | 274 | 338 | 337 |
| visual | 357 | 348 | 375 | 375 |
| table | 59 | 60 | 62 | 62 |
| equation | 71 | 71 | 70 | 70 |

These are declared localized records, not the actual number of PDF elements. Heron has 563 heading records but 557 unique geometries; Heron-101543 and 541; each MinerU 505. The heading targets appear on 262,255, and 259 pages respectively. It is not inferred that Heron recovers 58 additional correct headings: it may contain false headings and duplications.

MinerU's text records include many children without bbox: Basic 8,496 texts, 1,730 localized, and 6,766 without a box; Standard 8,440,1,730, and 6,710. Mixing them with Heron's blocks distorts distributions and micro accuracy. Children without boxes are not counted as omitted content or as millions of classification cases.

References: each MinerU declares 688 ref_text on 41 pages from 15 papers; Heron mainly uses list_item. The latter is not declared worse for not using the same name. `target_census.csv` also preserves targets outside the main families and child/inline categories without analytical equivalence.

- Heron: 35 heading/text geometries and 3 caption/text.
- Heron-101:19 heading/text and 3 caption/text.
- MinerU: 0 of these exact combinations at localized target level.

Do not confuse these with MinerU's 437 parent/body groups from the previous analysis:chart/chart_body orimage/image_body are not semantic target contradictions. A valid multilabel output may exist, but for a task needing a single function it requires an explicit subsequent policy. The output is not modified here.

<a id="sample"></a>

### 4.3. The 59-object agent sample

| Tool | Cases | Appropriate | Generally useful | Multitarget | Incorrect | No dedicated correspondence |
| --- | --- | --- | --- | --- | --- | --- |
| Heron | 59 | 31 | 10 | 14 | 1 | 3 |
| Heron-101 | 59 | 30 | 7 | 11 | 8 | 3 |
| MinerU Basic | 59 | 28 | 19 | 0 | 11 | 1 |
| MinerU Standard | 59 | 28 | 19 | 0 | 11 | 1 |

Columns separate specificity from error. Do not add generally useful to error, or count ambiguous cases as successes because one of their labels matches. Nor classify no correspondence as a false label. Differences reflect the chosen sample; do not publish “X% tool accuracy” across 397 pages from this table.

![Targeted sample by state](docs/findings/assets/integrated-analysis/target_audit_summary.png)

**Figure 4.** States of 236 tool/case assessments over 59 selected objects. This directed agent sample does not estimate collection-wide accuracy. The [original source figure](analysis/targets-20261101-v1/target_audit_summary.png) remains available.

Breakdown by reference: each cell expresses **appropriate / generally useful / multitarget / incorrect / no dedicated correspondence**.

| Reference | N | Heron | Heron-101 | Basic | Standard |
| --- | --- | --- | --- | --- | --- |
| heading | 19 | 10 / 0 / 9 / 0 / 0 | 8 / 0 / 9 / 2 / 0 | 9 / 0 / 0 / 10 / 0 | 9 / 0 / 0 / 10 / 0 |
| text | 4 | 1 / 0 / 2 / 1 / 0 | 2 / 0 / 1 / 1 / 0 | 3 / 0 / 0 / 0 / 1 | 3 / 0 / 0 / 0 / 1 |
| caption | 5 | 4 / 0 / 1 / 0 / 0 | 4 / 0 / 0 / 1 / 0 | 4 / 0 / 0 / 1 / 0 | 4 / 0 / 0 / 1 / 0 |
| visual | 10 | 9 / 0 / 0 / 0 / 1 | 9 / 0 / 0 / 0 / 1 | 1 / 9 / 0 / 0 / 0 | 1 / 9 / 0 / 0 / 0 |
| author | 6 | 0 / 5 / 1 / 0 / 0 | 0 / 3 / 1 / 2 / 0 | 0 / 6 / 0 / 0 / 0 | 0 / 6 / 0 / 0 / 0 |
| reference | 4 | 0 / 4 / 0 / 0 / 0 | 0 / 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 / 0 | 4 / 0 / 0 / 0 / 0 |
| list | 1 | 1 / 0 / 0 / 0 / 0 | 1 / 0 / 0 / 0 / 0 | 0 / 1 / 0 / 0 / 0 | 0 / 1 / 0 / 0 / 0 |
| table | 3 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 |
| equation | 3 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 | 3 / 0 / 0 / 0 / 0 |
| number | 1 | 0 / 1 / 0 / 0 / 0 | 0 / 0 / 0 / 1 / 0 | 1 / 0 / 0 / 0 / 0 | 1 / 0 / 0 / 0 / 0 |
| metadata | 1 | 0 / 0 / 1 / 0 / 0 | 0 / 0 / 0 / 1 / 0 | 0 / 1 / 0 / 0 / 0 | 0 / 1 / 0 / 0 / 0 |
| note | 2 | 0 / 0 / 0 / 0 / 2 | 0 / 0 / 0 / 0 / 2 | 0 / 2 / 0 / 0 / 0 | 0 / 2 / 0 / 0 / 0 |

The [audit verification](analysis/targets-20261101-v1/audit_verification.json) documents this directed sample. Native counts are neither true positives nor omissions; agreement, including agreement between dependent versions, cannot replace the observed reference.

<a id="functions"></a>

## 5. Detailed target functions and asymmetric errors

<a id="headings"></a>

### 5.1. Headings: signal, ambiguity and functional consistency

| Tool | Observed headings | Appropriate heading only | Heading + another class | Text only | Nonheadings with heading signal |
| --- | --- | --- | --- | --- | --- |
| Heron | 19 | 10 | 9 | 0 | 5 |
| Heron-101 | 19 | 8 | 9 | 2 | 5 |
| MinerU Basic | 19 | 9 | 0 | 10 | 0 |
| MinerU Standard | 19 | 9 | 0 | 10 | 0 |

In these 19 headings, Heron preserves a heading signal in all, but 9 are simultaneously text/section_header. That does not mean 19 clean correct decisions. Heron-101 offers 8 clean, 9 ambiguous, and 2 text only. MinerU offers 9 clean and 10 as text. The five nonheadings with a heading signal from each Heron include authors, notices, or metadata; some are multilabel and others single errors.

The practical consequence depends on your priority: a heading localized as text requires rediscovering its function; Heron at least offers a heading signal in many of those cases, although resolving conflicting candidates also has a cost. There is no complete dominance: greater signal availability and lower ambiguity are different dimensions.

In 8.pdf, 11 internal labels Baseline for Current Fuel-System Designs/New Baseline for Licensing were inspected, separate from Application/Assessment and body text (T004–T014):

| Tool | Single heading | Heading + text | Text only |
| --- | --- | --- | --- |
| Heron | 5 | 6 | 0 |
| Heron-101 | 3 | 6 | 2 |
| MinerU Basic | 4 | 0 | 7 |
| MinerU Standard | 4 | 0 | 7 |

Basic/Standard alternate between paragraph_title (4) and text (7) for the same template function. This is documented inconsistency, not just a naming difference between engines. Heron alternates single and double output; Heron-101 even loses the signal in 2. The pattern is not extrapolated to all headings: text, layout, and paper are preserved in each ROI.

Other examples: 12.pdf, page 4, T020 and 4.pdf, page 2, T027 are actual numbered subheadings preserved as text by both MinerU variants. 12.pdf, page 1, T019 is a document title: Basic/Standard declare it doc_title; Heron provides section_header (correct family, coarser hierarchy subtype); Heron-101 adds text.

Scores were recovered from original Heron JSON files by bbox/label equality, without creating MinerU scores or comparing them between engines. If, hypothetically, the highest-score label among dedicated correspondences were taken:

| Tool | Reviewed headings with score | Highest score preserves heading | Highest score chooses text |
| --- | --- | --- | --- |
| Heron | 19 | 13 | 6 |
| Heron-101 | 19 | 10 | 9 |

The heading signal available in 19 Heron cases would be reduced to 13 using highest score, because 6 favor text. This is a diagnostic, not a newly implemented policy or a calibrated correctness score. `native_score_alternatives.jsonl` preserves all alternatives.

Rates in `heading_sample_rates.csv` are operational measures of clean signal and bounds with conflicts within this targeted sample; they are not population estimates. Bounds are not statistical confidence intervals. The conventional strict matrix is limited to one predicted family; multilabels, group coverage, and lack of correspondence are presented outside it. Overall accuracy dominated by text is not used.

<a id="text-authors"></a>

### 5.2. Text, authors, affiliations, dates and false headings

- 1.pdf, page 1, T021: Tetsuji Noda is an author. Basic/Standard use text (generally useful). Heron provides text+section_header; Heron-101 section_header. Here the name is not a section heading.
- 2.pdf, page 1, T028: author list with superscripts; Heron-101 section_header is incompatible with the observed function.
- 8.pdf, pages 4 and 6, T002/T003: Page intentionally left blank is a notice, not a section. Heron returns heading as an alternative in one and as the sole category in another; MinerU preserves text.
- 8.pdf, page 1, T033: SEPTEMBER 2024 is an editorial date. text is generally usable; section_header does not describe the actual function. Not all large typography is a heading.
- Affiliations T034/T050: text/list_item/footnote may describe different aspects. Do not turn them into false errors due to schema differences.

Human feedback about the author said “not a section,” but the saved direction opposed Basic(text) to Heron(text+section_header). Visual observation clarifies the content's function without reversing or correcting original feedback. T063 was the same object as T021 and was excluded from the denominator.

<a id="captions"></a>

### 5.3. Captions: family, subtype and lexical markers

In five reviewed captions (five papers), Heron offers 4 with unequivocal caption family and 1 caption/text; Heron-101 and each MinerU offer 4 with unequivocal caption family and 1 incorrect text. Case 17.pdf, page 26, T026 is Figure 5 A:...B:...C:...: a multipanel caption preserved as text by 101 and both MinerU variants. This is a shared error: agreement does not imply truth.

There is also a subtype error: T018, 15.pdf, page 30, is Figure 6's caption about elastic properties. Basic and Standard label it table_caption. The caption family is appropriate but the table subtype does not correspond to the observed figure. It is recorded as figure_as_table_caption in agent_subtype_assessments.csv; it is not counted twice as a family failure. Heron uses generic caption. Therefore, 4/5 with correct family does not mean 4/5 correct specific labels.

The opposite case is in 14.pdf, page 24, T023: Figure 2.9 shows the layout... is a body paragraph, not the caption. Heron-101 labels it caption. Therefore, searching only for a Figure/Table prefix would not suffice to reconstruct accurate tagging; function and context must be considered, not just the initial word.

Already preserved texts of each MinerU caption were inspected, without OCR:

| Native text pattern | Basic | Standard |
| --- | --- | --- |
| Isolated marker(a)/(b)/letter |53|52|
| Figure/Fig prefix |207|207|
| Table prefix |46|46|
| Other caption texts |32|32|

The 338/337 records are not 338/337 complete captions. The specific difference is in 6.pdf, page 12: Basic includes `(b)` as image_caption; Standard does not. Both preserve the complete Figure 4 caption and Figure 5's. There is no evidence that Standard loses a complete shared caption there. Patterns are lexical descriptors, not an infallible text classification.

The [native-caption text summary](analysis/targets-20261101-v1/native_caption_text_summary.json) retains the marker breakdown. Caption family, complete-caption recovery, specific subtype and structural parent are separate assessments. In particular, **T018 is 15.pdf page 30, Figure 6**; it is not the Figure 8/Figure 9 membership case in 6.pdf page 15 discussed next.

<a id="visuals"></a>

### 5.4. Images, logos, headers and numeric subtype

Of 10 visuals reviewed in 8 papers, the Heron variants identify 9 with picture and lack a dedicated correspondence for 1 decorative illustration. Basic/Standard recognize that illustration as visual, but use header for 9 logos/editorial covers. These are useful boxes, and header describes a positional function; **it does not provide the specific image identification you prefer**.

Examples: Elsevier logos in 5.pdf/7.pdf, page 1; CrossMark in 1.pdf, page 1; journal covers in 5/7/12/2.pdf, page 1 and 11.pdf, page 2. This pattern is repeated, not an isolated case of the logo you pointed out. It is incorrect to add the 9 as omitted images or declare all header “wrong”: the deficit is content-target specificity.

For scientific charts, picture versus chart/image is a shared visual family and vocabulary of different resolution. chart is more specific but is not automatically considered more accurate without observing whether the region is actually a chart. This visual sample concentrates on logos and covers; it is not used to claim accuracy for all scientific figures.

The 17 in 1.pdf is a chapter number. Basic/Standard label it page_number: useful numeric family, imprecise subtype. Heron uses text and 101 picture. Do not claim that Basic correctly identified a page number: the observed reference is chapter_marker and is recorded as `chapter_as_page_number`.

<a id="other-targets"></a>

### 5.5. References, lists, tables and equations

Four reviewed bibliographic entries/fragments (three papers): MinerU uses ref_text, Heron list_item. Both can be useful, but ref_text better identifies the bibliographic function. The full pattern has 536 nearly equivalent list_item/ref_text correspondences between Heron and Basic in the collection; these are not 536 Heron errors.

The only reviewed nonbibliographic bullet, T051 (8.pdf, page 18), is list_item in Heron and text in MinerU. List signal available in Heron and usable general text in MinerU; one observation does not establish consistent lists throughout the document. List grouping and continuity were not assessed as part of the target.

Three reviewed tables and three equations were appropriately recognized by all four tools. Controls include cases where tools already agreed, so they establish neither universal accuracy nor a population tie. formula/equation are normalized as the equation family; table_body shares geometry with its parent and is not counted as a second correctly identified table.

<a id="relationships"></a>

## 6. Structural relationships and boundaries

The automatic screening produced these candidates before the targeted visual assessment. Their labels alone do not establish the actual function; the separate visual findings in sections 4 and 5 must be considered at their stated case scope.

- 28 equivalent block clusters show heading versus text, on 22 pages from 8 papers. They are high-interest candidates because of your asymmetric cost; this automatic evidence alone does not establish which side represents the actual heading.
- 3 show caption versus text, on 3 pages/3 papers.
- 1 shows visual versus text.
- 31 cross-edges in 20 text boxes almost completely contain a heading/visual/table from another tool and are more than 1.5 times larger. They are absorption/mixing candidates; not 31 confirmed mixtures. Another tool's labels are not an independent reference.

Complete examples are preserved in heading_vs_text_examples.jsonl, caption_vs_text_examples.jsonl, visual_vs_text_examples.jsonl, and structural_boundary_candidates.csv. Coordinate clustering detects discrepancies; deciding accuracy requires evidence of function, separating heading→text errors from body→heading errors. No heading classifier based on size is invented.

Inspection of the existing background of 6.pdf, page 15 shows Figure 8 (four strain/stress panels) above and Figure 9 (temperature/pressure/gas/oxide) below. In the Basic JSON, Figure 8's caption is a child of `/pages/14/blocks/4`, whose box is the first chart in Figure 9's lower group. The four upper charts are blocks 0–3. Therefore, in this case the output preserves the caption and images, but the declared membership does not represent Figure 8's group. This is an agent visual observation checked against original text/structure; not accumulated human review or a global rule.

This demonstrates why figure area agreement and the count of parents with captions are insufficient for your definition of accuracy. No association based on proximity is created, nor is the original changed. [caption_parent_diagnostics.json](analysis/deep-20261101-v2/caption_parent_diagnostics.json) preserves text, coordinates, pointers, and hash to review this case. `caption_parent_geometry.csv` describes all localized caption–parent relationships (above/below/overlapping), without declaring those above incorrect: table captions or particular layouts may be valid.

The Figure 8/Figure 9 observation illustrates a preserved image/caption with incorrect declared membership. Changing the caption family cannot repair that relationship. Good boxes, an appropriate caption class and an incorrect figure–panels–caption link can coexist; more declared links do not establish correct applicability or consistent shared-caption preservation.

| Dimension | Available automatic evidence | What is missing to decide according to your priorities |
| --- | --- | --- |
| Coverage, especially heading/caption/body | Union agreement, exclusive areas, selected human ROIs | Independent content inventory; omissions common to all are invisible here |
| Paragraphs, columns, sections |1:n/n:1, different boundaries and absorption candidates | Confirm whether it crosses columns/headings or only combines valid paragraphs |
| Combined figure/panels | Granularity candidates and preserved native relationships | Validate membership and shared caption; a large box may still be useful |
| Relationship consistency | MinerU reports251 visual parents with caption child in each version; Heron reports no edges in this projection | Correctness and applicability of those links; without inventing panels from geometry |
| Lists | Declared Heron items and MinerU references/text; recurring patterns | Check actual lists and grouping; isolated list_item is not a complete structure |
| Labels | Equivalent groups, vocabulary, conditional agreement, and human examples | Actual function of the region; heading→text priority separate from body→heading |
| Clipping | Different boundaries and exclusive areas | Evidence of clipped visible letters/words; no OCR was run, nor is automatic clipping claimed |
| Cost/failures | Preserved receipts and memory/time by scope | Comparable timing measurements and repetitions; do not add detector times to SDK parsing |

There is no aggregate score or semantic winner. Consistency is described by capability and context; a systematically incorrect output can also be consistent. Localized captions and relationships do not guarantee that the shared link is correct, and image_body nodes are not interpreted as panels.

<a id="patterns"></a>

## 7. Repeated patterns across pages and papers

236 recurring signatures were detected (at least 2 pages). Each signature includes labels by tool, vertical band, and width; it preserves cases/pages/papers, concentration in the dominant paper, and examples with IDs. Bands 0.2/0.8 and widths 0.35/0.7 are exploratory descriptors, not column or section boundaries.

| Declared labels | Zone/width | Cases | Pages | Papers |
| --- | --- | --- | --- | --- |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | middle/medium | 254 | 25 | 11 |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | bottom/medium | 33 | 11 | 8 |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | top/medium | 45 | 13 | 7 |
| basic:header; heron:picture; heron101:picture; standard:header | top/narrow | 7 | 7 | 7 |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | middle/wide | 145 | 20 | 6 |
| basic:text; heron:list_item; heron101:list_item; standard:text | middle/medium | 21 | 15 | 5 |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | bottom/wide | 21 | 12 | 5 |
| basic:index; heron:document_index; heron101:document_index; standard:index | middle/wide | 10 | 10 | 4 |
| basic:ref_text; heron:list_item; heron101:list_item; standard:ref_text | top/wide | 16 | 9 | 4 |
| heron:text; heron101:section_header | middle/narrow | 8 | 7 | 4 |
| basic:text; heron:list_item; heron101:list_item; standard:text | bottom/medium | 5 | 4 | 4 |
| basic:table_body; heron101:table; standard:table_body | middle/wide | 4 | 4 | 4 |

The reference/list pattern of medium width and middle zone appears 254 times on 25 pages/11 papers. It does not depend exclusively on one paper. Thepicture/header pattern in a narrow upper region appears on 7 pages/7 papers; it is especially relevant to your logo example. It is not automatically validated that all seven are logos, nor are their labels corrected.

`pattern_macro_and_loo.csv` calculates support by paper including zeros, macro mean, and descriptive range when excluding each paper. This checks how much the count depends on the observed collection; it is neither an external test nor a generalization confidence interval. Exact signatures include the tools present; if a box is missing, the signature may change, so patterns are not disjoint by actual function.

Page rules are in page_association_rules.csv: antecedent=declared presence of a category; consequent=disagreement, granularity, or area difference>0.5% of the page. Support/confidence/lift and per-paper breakdowns are published. Minimum thresholds of 10 antecedent pages and 5 joint pages only reduce accidental rarities. These are exploratory, without multiple-comparison correction or independent confirmation: do not select rules by lift and present them as document laws. High confidence may reflect a very frequent category or a schema; macro and micro are not interchangeable.

| Pair | Labels A/B | Cases | Pages | Papers |
| --- | --- | --- | --- | --- |
| Heron/MinerU Basic | list_item / ref_text | 536 | 40 | 15 |
| Heron/MinerU Basic | picture / chart | 118 | 75 | 14 |
| Heron/MinerU Basic | picture / image | 103 | 63 | 14 |
| Heron/MinerU Basic | list_item / text | 117 | 29 | 9 |
| Heron/MinerU Basic | picture / header | 7 | 7 | 7 |
| Heron/Heron-101 | text / section_header | 12 | 11 | 6 |
| Heron/MinerU Basic | formula / equation | 19 | 11 | 5 |
| Heron/MinerU Basic | document_index / index | 14 | 14 | 5 |
| Heron/Heron-101 | key_value_region / text | 5 | 5 | 5 |
| Heron/MinerU Basic | section_header / doc_title | 5 | 5 | 5 |
| Heron/Heron-101 | section_header / text | 14 | 13 | 4 |
| Heron/MinerU Basic | picture / footer | 4 | 4 | 4 |
| Heron/Heron-101 | list_item / footnote | 14 | 3 | 3 |
| Heron/Heron-101 | text / key_value_region | 6 | 6 | 3 |
| Heron/MinerU Basic | key_value_region / text | 6 | 4 | 3 |
| Heron/MinerU Basic | footnote / page_footnote | 3 | 3 | 3 |

These frequencies are based on nearly equivalent block clusters and preserve label text, pages, papers, concentration, and macro support. They indicate family equality/inequality, not accuracy: different classes may be compatible. Neither four votes nor two engine families constitute the reference; Basic/Standard and Heron/101 are dependent and share errors.

`target_pair_conditionals.csv` expresses, for example, which label B accompaniesheading from A over available correspondences. The denominator is the target declared by A that does have a correspondence: it is not the set of actual headings or recall. A→B andB→A asymmetry is preserved.

A pattern repeated across pages shows consistent output behavior, not correctness by itself. TheBaseline template documents functional inconsistency because the ROIs were reviewed; the reference/list pattern only shows schema alternatives until actual function is checked. No classifier was trained or threshold tuned to one paper's results.

<a id="cost"></a>

## 8. Observed cost, measurement scope and failures

| Recorded measurement | MinerU Basic | MinerU Standard |
| --- | ---: | ---: |
| Available time sum: SDK parsing, without export | 301.352 s | 321.891 s |
| Sampled stage peak RAM | 5,853 MiB | 9,707 MiB |
| Sampled device peak GPU | 2,862 MiB | 12,473 MiB |

Sources: G, §10; [stage costs](analysis/auto-20261101T080056Z-r2/cost_by_stage.csv) and [timing distributions](analysis/auto-20261101T080056Z-r2/timing_distributions.csv). RAM is rounded.

The table reports SDK parsing without export and sampled RAM/GPU peaks. These one-pass stage observations are not repetitions, model-exclusive memory measurements, variability estimates or universal hardware requirements. Within this scope no geometry/category gain explains Standard’s higher recorded cost.

Heron 12.598 s and Heron-101 16.685 s correspond only to the sum of detector inference; do not compare them directly with MinerU parsing. Corrected attempts completed 15 papers per tool without failures; the 11 previous failures of each MinerU with another version remain separate history. Nothing was rerun for this delivery.

<a id="decision"></a>

## 9. Provisional technical decision and residual work

**MinerU Basic is the preferred candidate as the segmentation base for this collection, but its tagging and structural relationships must not be assumed to be a complete and uniform solution.** This decision combines the visual preference expressed by the user, the observed equivalence between Basic and Standard and Basic's lower recorded resource usage. It does not imply that Basic has been shown to have the best true coverage or the highest global semantic accuracy. [G, §§1, 8 and 10; T, §§5 and 11]

**MinerU Standard showed no relevant improvement in boxes or block labels that would justify preferring it to Basic in this experiment.** Heron retains useful title and image signals that MinerU may generalize as `text` or `header`; however, its simultaneous labels and some false titles prevent considering it an unequivocally better substitute. Heron-101 also showed no consistent improvement over Heron in the reviewed cases. [G, §§3 and 10; T, §§4–11]

The operational conclusion is to retain the original outputs, use Basic as the base and later evaluate a uniform technique for the capabilities that proved unreliable: title identification, distinction of visual content within headers and preservation of figure–panels–caption relationships. **Neither that complementary technique nor an ensemble of tools has been implemented or validated.** [G, §§9–11; T, §11]

| Target/capability | Observed evidence | Bounded assessment |
| --- | --- | --- |
| Headings localized as headings | Heron preserves more signals in the sample; MinerU loses10/19 as text | Heron provides useful candidates, but9 are ambiguous. Do not use it as final tagging or extrapolate10/19 to the entire collection |
| Text without false headings | MinerU keeps authors/notices as text and returns no heading alternatives in those cases | Cleaner in these cases; may be too general for actual headings |
| Caption |4/5 clean per tool, with shared failure or alternative | No established winner; separate panel marker, complete caption, and shared relationship |
| Editorial image/logo | Heron picture in9 cases where MinerU uses header | Heron provides the specific content target you prefer; does not imply better overall segmentation |
| Bibliographic reference | MinerU ref_text in all4 cases; Heron list_item | Greater MinerU bibliographic specificity; list_item is not necessarily false |
| List | One bullet list_item versus text | Signal favoringHeron, sample insufficient for overall consistency |
| Table/equation | All appropriate in3+3 controls | No advantage detected in chosen controls; not a complete evaluation |
| Standard versusBasic | Same labels in 4,168 equivalent blocks; isolated caption difference(b) | No demonstrated Standard advantage in this collection's block targets |

A winning label by voting is not recommended, nor is an ensemble implemented. According to your preference for uniform reconstruction, **headings** and the **content class of logos/header** are tasks requiring a uniform policy if MinerU is adopted as the base. Heron can provide candidate evidence, but choosing it automatically here would reintroduce the inconsistency you want to avoid. This is diagnostic, not validation of a complementary technique.

| Decision or statement | Status and basis |
| --- | --- |
| Prioritize Basic as the base for this collection | Provisional decision supported by the user's visual preference, equivalence to Standard and lower observed cost. |
| Rule out Standard as a universal option | Unsupported. It showed no relevant advantage here; not all its possible use contexts were evaluated. |
| Replace Basic with Heron because of its labels | Not justified as a general decision: it provides useful signals, but also ambiguities and false titles. The total correction work for each alternative was not measured. |
| Treat every box difference as an error | Rejected: there are granularity and parent–body representation differences that are useful according to the agreed priorities. |
| Trust an engine's targets uniformly | Not established. Reviewed patterns show problems of function, specificity and consistency. |
| Use a uniform complementary technique | A reasonable direction to evaluate, especially for titles and relationships; which technique best reduces residual work has not yet been demonstrated. |
| Choose the label by voting among several parsers | Not validated. Consensus may share errors and versions of one family are not independent sources. |

The priority of a next evaluation would be to measure **residual work** on common cases: what content requires recovery, which titles must be rediscovered, which boundaries must be separated and which links must be reconstructed. Adding up correct labels or comparing how many boxes each engine produces is insufficient. This direction does not authorize or execute a new technique, reconstruction or model. [G, §§9–11; T, §11]

Operationally, the user’s tolerance for useful granularity supports concentrating subsequent review on exclusive regions, discrepant headings/captions, complex groups and shared relationships, rather than every small box difference. Coverage and structure should be used where consistency is demonstrated; capabilities that remain irregular require evaluation of a uniform reconstruction policy, without assuming that any such policy already works.

<a id="limits"></a>

## 10. Limits, verification and stopping point

1. **There is no exhaustive independent reference for the PDF.** Geometric agreement does not measure true coverage and does not necessarily reveal shared omissions.
2. **Target evaluation is directed and was performed by the agent.** Its 59 objects and 236 assessments do not constitute a representative human benchmark of the 397 pages.
3. **Consistency and adequacy are not equivalent.** A systematically general or incorrect label may be consistent; a useful function may appear irregularly.
4. **Semantically acceptable granularity still requires checking.** High union IoU does not by itself confirm membership, section boundaries or a shared caption.
5. **Resources were not measured through comparable end-to-end repetitions.** No universal performance advantages or joint time ranking of the four engines are inferred.
6. **The total human cost of correcting each output was not quantified.** Residual tasks and priorities were identified, but not correction minutes or an aggregate score.

These limits do not prevent a provisional working choice; they delimit what that choice can claim. The analyses recorded integrity checks of 2,452 original files, successful tests and technical invariants. That supports preservation and consistency of the calculations, not global semantic accuracy. [G, §11; T, §13; G and T verifications in the following section]

The finding is a matrix of strengths and problems by target, not a universal winner. Claiming precision/recall for the entire collection requires a representative reference and an inventory of actual elements, including those no tool detects. Agent review makes examples verifiable and distinguishes error from mere discrepancy; it does not replace human review or eliminate selection bias.

Stopping condition for this delivery: all six comparisons and strata are calculated, patterns have denominators and examples, originals are preserved, and semantic accuracy is not presented without a reference. True coverage, overall category accuracy, and which differences are exclusively granularity in the semantic sense remain explicitly undetermined. Specific geometric candidates and the work needed to confirm them are identified.

Historical checks support input preservation and internal consistency, not semantic validation. Target verification recorded **8/8 tests** and corrected the T016/T031 duplicate and false affiliation conflict; these are source-delivery facts. No aggregate semantic score, general winner, calibrated certainty, representative population precision/recall or independent reference inventory has been established.

<a id="cases"></a>

## 11. Human selections and complete agent case evidence

<a id="human-cases"></a>

### 11.1. Six selected human examples

| Page | Selection | Tool | Intersecting labels | ROI area with boxes | Human note |
| --- | --- | --- | --- | --- | --- |
| 1.pdf / 1 | negative | Heron | footnote, page_footer | 12.686 % | leaves text unsegmented |
| 1.pdf / 1 | preferred | MinerU Basic | footer | 92.504 % | leaves text unsegmented |
| 1.pdf / 1 | negative | Heron | footnote, page_footer | 20.196 % | leaves text unsegmented |
| 1.pdf / 1 | preferred | MinerU Basic | footer | 79.521 % | leaves text unsegmented |
| 1.pdf / 1 | negative | MinerU Basic | header | 25.098 % | that is not text, it counts more as an image since it is more like a logo |
| 1.pdf / 1 | preferred | Heron | picture | 24.126 % | that is not text, it counts more as an image since it is more like a logo |
| 1.pdf / 1 | negative | MinerU Basic | text | 24.408 % | it is an author, not a section |
| 1.pdf / 1 | preferred | Heron | section_header, text | 18.380 % | it is an author, not a section |
| 1.pdf / 1 | negative | Heron | text | 41.892 % | it is a number, not text |
| 1.pdf / 1 | preferred | MinerU Basic | page_number | 25.696 % | it is a number, not text |
| 12.pdf / 4 | negative | Heron | caption, table | 77.644 % | (no note) |
| 12.pdf / 4 | preferred | MinerU Basic | table, table_body, table_caption | 66.704 % | (no note) |

The two coverage preferences on 1.pdf, page 1 agree with a surface difference in those regions: Heron covers approximately 12.7% and 20.2% of your ROIs; Basic 92.5% and 79.5% of its preferred ROIs. ROIs on both sides have different boundaries, include blank space, and are not true boxes. Those percentages contextualize preference, not quantify text recall. The human note does express content you are missing; it is preserved as selected local evidence.

The logo example links Basic's header with Heron's picture and matches a recurring signature in 7 papers. The number links Heron's text with Basic's page_number: a local category preference, without extrapolating it to all numbers.

There is a discrepancy that should not be hidden: in the example “it is an author, not a section,” you selected Basic as nonpreferred, but its region intersects text; the Heron alternative intersects coincident text and section_header. The note and preference direction do not unambiguously determine which output you wanted to penalize. It remains pending, without reversing your record or using it as a training label.

On12.pdf, page 4 a Basic segmentation is preferred over Heron. The ROI includes a table and caption; Heron's box surface may even be larger without being your preferred option. This confirms that amount of area does not replace structural suitability. Six targeted examples, five on one page, do not allow training or evaluating generalization of a preference model; nor are they six exact reference boxes.

<a id="agent-cases"></a>

### 11.2. All 59 eligible agent objects

![Target examples](docs/findings/assets/integrated-analysis/target_examples.png)

**Figure 5.** Located target examples from existing backgrounds, connecting labels to observed function and preserved case identifiers. The [original source figure](analysis/targets-20261101-v1/target_examples.png) remains available.

| Case | Location | Observed | Heron | Heron-101 | Basic | Standard |
| --- | --- | --- | --- | --- | --- | --- |
| T001 | 8.pdf p3 | text | section_header,text → contradictory | section_header,text → contradictory |  → no_own_correspondence |  → no_own_correspondence |
| T002 | 8.pdf p4 | text | section_header,text → contradictory | text → adequate | text → adequate | text → adequate |
| T003 | 8.pdf p6 | text | section_header → wrong | text → adequate | text → adequate | text → adequate |
| T004 | 8.pdf p28 | heading | section_header → adequate | section_header → adequate | text → wrong | text → wrong |
| T005 | 8.pdf p29 | heading | section_header → adequate | text → wrong | text → wrong | text → wrong |
| T006 | 8.pdf p30 | heading | section_header,text → contradictory | section_header → adequate | paragraph_title → adequate | paragraph_title → adequate |
| T007 | 8.pdf p35 | heading | section_header,text → contradictory | section_header,text → contradictory | text → wrong | text → wrong |
| T008 | 8.pdf p36 | heading | section_header,text → contradictory | section_header → adequate | paragraph_title → adequate | paragraph_title → adequate |
| T009 | 8.pdf p37 | heading | section_header → adequate | section_header,text → contradictory | paragraph_title → adequate | paragraph_title → adequate |
| T010 | 8.pdf p37 | heading | section_header,text → contradictory | section_header,text → contradictory | text → wrong | text → wrong |
| T011 | 8.pdf p39 | heading | section_header,text → contradictory | section_header,text → contradictory | text → wrong | text → wrong |
| T012 | 8.pdf p44 | heading | section_header,text → contradictory | text → wrong | text → wrong | text → wrong |
| T013 | 8.pdf p45 | heading | section_header → adequate | section_header,text → contradictory | text → wrong | text → wrong |
| T014 | 8.pdf p49 | heading | section_header → adequate | section_header,text → contradictory | paragraph_title → adequate | paragraph_title → adequate |
| T015 | 7.pdf p1 | heading | section_header,text → contradictory | section_header → adequate | paragraph_title → adequate | paragraph_title → adequate |
| T016 | 7.pdf p1 | heading | section_header,text → contradictory | section_header → adequate | paragraph_title → adequate | paragraph_title → adequate |
| T017 | 15.pdf p1 | heading | section_header,text → contradictory | section_header → adequate | text → wrong | text → wrong |
| T018 | 15.pdf p30 | caption | caption,text → contradictory | caption → adequate | table_caption → adequate | table_caption → adequate |
| T019 | 12.pdf p1 | heading | section_header → adequate | section_header,text → contradictory | doc_title → adequate | doc_title → adequate |
| T020 | 12.pdf p4 | heading | section_header → adequate | section_header,text → contradictory | text → wrong | text → wrong |
| T021 | 1.pdf p1 | author | section_header,text → contradictory | section_header → wrong | text → coarse_usable | text → coarse_usable |
| T022 | 1.pdf p1 | number | text → coarse_usable | picture → wrong | page_number → adequate | page_number → adequate |
| T023 | 14.pdf p24 | text | text → adequate | caption → wrong | text → adequate | text → adequate |
| T025 | 17.pdf p2 | author | text → coarse_usable | section_header,text → contradictory | text → coarse_usable | text → coarse_usable |
| T026 | 17.pdf p26 | caption | caption → adequate | text → wrong | text → wrong | text → wrong |
| T027 | 4.pdf p2 | heading | section_header → adequate | section_header,text → contradictory | text → wrong | text → wrong |
| T028 | 2.pdf p1 | author | text → coarse_usable | section_header → wrong | text → coarse_usable | text → coarse_usable |
| T029 | 5.pdf p1 | heading | section_header → adequate | section_header → adequate | paragraph_title → adequate | paragraph_title → adequate |
| T030 | 8.pdf p1 | heading | section_header,title → adequate | section_header,title → adequate | doc_title → adequate | doc_title → adequate |
| T032 | 5.pdf p1 | author | text → coarse_usable | text → coarse_usable | text → coarse_usable | text → coarse_usable |
| T033 | 8.pdf p1 | metadata | section_header,text → contradictory | section_header → wrong | text → coarse_usable | text → coarse_usable |
| T034 | 7.pdf p1 | author | footnote,list_item → coarse_usable | footnote → coarse_usable | text → coarse_usable | text → coarse_usable |
| T035 | 5.pdf p3 | caption | caption → adequate | caption → adequate | chart_caption → adequate | chart_caption → adequate |
| T036 | 8.pdf p13 | caption | caption → adequate | caption → adequate | table_caption → adequate | table_caption → adequate |
| T037 | 7.pdf p3 | caption | caption → adequate | caption → adequate | table_caption → adequate | table_caption → adequate |
| T038 | 5.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T039 | 8.pdf p1 | visual |  → no_own_correspondence |  → no_own_correspondence | image → adequate | image → adequate |
| T040 | 7.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T041 | 5.pdf p3 | table | table → adequate | table → adequate | table → adequate | table → adequate |
| T042 | 8.pdf p13 | table | table → adequate | table → adequate | table → adequate | table → adequate |
| T043 | 7.pdf p3 | table | table → adequate | table → adequate | table → adequate | table → adequate |
| T044 | 5.pdf p4 | equation | formula → adequate | formula → adequate | equation → adequate | equation → adequate |
| T045 | 7.pdf p10 | equation | formula → adequate | formula → adequate | equation → adequate | equation → adequate |
| T046 | 9.pdf p4 | equation | formula → adequate | formula → adequate | equation → adequate | equation → adequate |
| T047 | 5.pdf p8 | reference | list_item → coarse_usable | list_item → coarse_usable | ref_text → adequate | ref_text → adequate |
| T048 | 8.pdf p26 | reference | list_item → coarse_usable | text → coarse_usable | ref_text → adequate | ref_text → adequate |
| T049 | 7.pdf p13 | reference | list_item → coarse_usable | list_item → coarse_usable | ref_text → adequate | ref_text → adequate |
| T050 | 5.pdf p1 | author | list_item → coarse_usable | footnote,list_item → coarse_usable | text → coarse_usable | text → coarse_usable |
| T051 | 8.pdf p18 | list | list_item → adequate | list_item → adequate | text → coarse_usable | text → coarse_usable |
| T052 | 7.pdf p14 | reference | list_item,text → coarse_usable | list_item → coarse_usable | ref_text → adequate | ref_text → adequate |
| T053 | 5.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T054 | 7.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T055 | 12.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T056 | 1.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T057 | 11.pdf p2 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T058 | 4.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T059 | 2.pdf p1 | visual | picture → adequate | picture → adequate | header → coarse_usable | header → coarse_usable |
| T060 | 1.pdf p1 | note |  → no_own_correspondence |  → no_own_correspondence | footer → coarse_usable | footer → coarse_usable |
| T061 | 1.pdf p1 | note |  → no_own_correspondence |  → no_own_correspondence | footer → coarse_usable | footer → coarse_usable |

Each case has ROI, paper/page, visual sheet, observed class/subtype, confidence, and note in `agent_reference_cases.jsonl`; each assessment saves all dedicated boxes and other intersections in `agent_assessments.jsonl`. Equivalent regions can be reviewed jointly without requesting piece-by-piece labeling from the user.

The family-level `adequate` states for T018 and T022 coexist with the explicit subtype problems described in [captions](#captions) and [numeric subtype](#visuals). They do not assert that `table_caption` is the correct figure subtype or that the chapter marker is actually a page number. Excluded IDs and duplicate links remain documented in the [scope](#scope) and source artifacts.

<a id="evidence-tables"></a>

## 12. Cross-dimension evidence tables

The following source summary tables join dimensions already developed above. They are retained in full for comparison and traceability; their repeated numbers are the same observations, not additional samples or independent evidence.

<a id="geometry-summary"></a>

### 12.1. Surface agreement alongside block granularity

| Comparison | IoU between box unions | Block-level granularity candidates |
| --- | ---: | ---: |
| Heron / Heron-101 | 97.315 % | 7 |
| Heron / MinerU Basic | 93.327 % | 29 |
| Heron / MinerU Standard | 93.326 % | 29 |
| Heron-101 / MinerU Basic | 92.644 % | 29 |
| Heron-101 / MinerU Standard | 92.644 % | 29 |
| MinerU Basic / MinerU Standard | **99.999102 %** | 0 |

Source: [geometric summary](analysis/deep-20261101-v2/summary.json) and [block comparison](analysis/deep-20261101-v2/block_pair_summary.csv). Area agreement is calculated over the union of rectangles, without double counting. Candidates may recur across pairs: they must not be added together as distinct cases. [G, §§3–5]

<a id="heading-summary"></a>

### 12.2. Heading signal summary

| Tool | Titles reviewed | Appropriate title family only | Title and another class simultaneously | Title only as text |
| --- | ---: | ---: | ---: | ---: |
| Heron | 19 | 10 | 9 | 0 |
| Heron-101 | 19 | 8 | 9 | 2 |
| MinerU Basic | 19 | 9 | 0 | 10 |
| MinerU Standard | 19 | 9 | 0 | 10 |

Source: [directional heading costs](analysis/targets-20261101-v1/heading_asymmetric_costs.csv) and T, §5. **Twelve of the 19 titles belong to `8.pdf`**; the table does not support claiming that MinerU loses that proportion of titles throughout the collection.

<a id="target-summary"></a>

### 12.3. Target-specific implications

| Target or function | Localized evidence | Interpretation for the decision |
| --- | --- | --- |
| Text and authors | MinerU retains the six reviewed authors/affiliations as `text`; Heron may add `section_header` and Heron-101 even uses it as the sole class for authors. | MinerU offers a useful general representation in these cases; Heron must not turn any title signal into an accepted section. |
| Editorial images and logos | Of ten reviewed visuals, Heron identifies nine as `picture`; MinerU uses `header` in nine and recognizes the remaining illustration as visual. | Heron provides greater content specificity in those logos/covers. `header` may describe their position, but does not by itself satisfy the image identification the user prefers. |
| Captions | Of five reviewed captions, each tool provides four with an unambiguous caption family; Heron has one multitarget case and the other three tools one as `text`. | No winner is established for this family. Subtype and relationship must also be checked. |
| Caption subtype | In T018, `15.pdf`, page 30, Basic and Standard label a figure caption as `table_caption`. | The caption family is appropriate, but the subtype is incorrect. Do not confuse the correct family with the correct specific label. |
| Bibliographic references | MinerU uses `ref_text` in four reviewed references; Heron uses `list_item`. | MinerU offers greater bibliographic specificity; both properties may be compatible, so the difference does not automatically imply an error. |
| Lists | One reviewed bullet appears as `list_item` in Heron and `text` in MinerU. | A signal favoring Heron in that case; the sample is insufficient to establish list consistency. |
| Tables and equations | All four tools classify three control tables and three control equations appropriately. | No advantage was observed in those controls; this does not amount to an exhaustive evaluation. |

Sources: T, §§4 and 6–11; [summary by target](analysis/targets-20261101-v1/agent_target_summary.csv) and [subtype assessment](analysis/targets-20261101-v1/agent_subtype_assessments.csv).

<a id="artifacts"></a>

## 13. Artifacts, provenance and source directories

**G evidence directory:** [`analysis/deep-20261101-v2/`](analysis/deep-20261101-v2/). Every bare G artifact filename below or in geometric discussion resolves here. **T evidence directory:** [`analysis/targets-20261101-v1/`](analysis/targets-20261101-v1/). Every bare T artifact filename below or in target discussion resolves here. `diagnostic-audit-v1` is the preserved intermediate diagnostic directory within T. Case records retain source page conventions: displayed paper pages are one-based; G JSONL pattern/example pages are base0. Artifact identifiers are preserved literally.

- Histograms and correspondences: iou_histograms.csv, pair_summary.csv, matched_boxes.csv.
- Relative coverage: atomic_area_signatures.jsonl, page_metrics.csv, comparison_by_paper.csv.
- Granularity: granularity_groups.jsonl (all levels), block_granularity_groups.jsonl, strict_granularity_examples.jsonl, granularity_sensitivity.csv.
- Categories: spatial_clusters.jsonl, block_spatial_clusters.jsonl, label_contingency.csv, block_label_contingency.csv, unlocalized_categories.csv, coincident_boxes.jsonl.
- Patterns: recurring_patterns.jsonl, pattern_macro_and_loo.csv, page_association_rules.csv; these JSONL files contain IDs and base0 pages.
- Feedback: human_feedback_snapshot.json, human_feedback_context.jsonl. Human originals were not modified.
- Subsequent review: review_examples.jsonl plus priority disagreement files; does not require reviewing all blocks one by one.
- Verification: verification.json, supplement_verification.json, report_verification.json, and final_checks.json. 2,452 original files were checked before/after, along with identity of inputs used and partitions. Independent review does not equal semantic review of the 397 pages across 15 PDFs. Editorial clarification: G §11 says “397 PDFs”; its stated population is 397 pages from 15 PDFs.

- Census: target_census.csv, target_profiles.csv, target_correspondences.csv, target_patterns.csv.
- Ambiguities: same_box_target_conflicts.jsonl and strict_same_box_target_alternatives.csv; do not confuse parent/body groups with class conflict.
- Agent reference: 65 ROIs, 59 scored objects, 4 duplicates excluded, 2 references without a single class; 236 eligible assessments. T062 is a partial ROI of the logo;T065 mixes table/caption.
- Assessment: agent_target_summary.csv, agent_tool_summary.csv, agent_confusion_counts.csv, heading_asymmetric_costs.csv, heading_sample_rates.csv, and agent_subtype_assessments.csv. Targeted rates and explicit abstentions, without overall accuracy.
- Original scores and text: native_score_alternatives.jsonl, native_caption_text.csv. No OCR or imputed scores; original JSON files preserved.
- Intermediate diagnostic audit results were preserved before correcting the ARTICLE INFO duplicate and affiliation compatibility. They are in diagnostic-audit-v1; they are not the current delivery. The family map did not change; code snapshots fix preparation and audit versions.
- Independent review: corrected the T016/T031 duplicate and false affiliation conflict. Does not constitute human semantic approval. Tests 8/8; final checks and hashes in final_checks.json.
- Originals, previous results, feedback, and viewer were not modified. No parsers, OCR, models, Colab, or PDF renders were run. Sheets are presentation crops of existing PNG files.

| Ref. | Source | Role in this conclusion |
| --- | --- | --- |
| **G** | [Full technical report: boxes, categories and granularity](analysis/deep-20261101-v2/report.md) | Area agreement, granularity, hierarchies, costs and shared-caption case. Current version v2; v1 is not used as the final result. |
| **T** | [Deep target analysis](analysis/targets-20261101-v1/report.md) | Labels per corresponding region, agent visual reference, directional errors, subtypes and inconsistencies per tool. |
| P | [Analysis plan](docs/methodology/analysis-plan.md) | Priorities P01–P12 and separation between coverage, segmentation, relationships, labels and costs. |
| G-D | [Geometric results summary](analysis/deep-20261101-v2/summary.json) and [block summary](analysis/deep-20261101-v2/block_pair_summary.csv) | Numerators and metrics supporting the geometric comparison. |
| T-D | [Assessment by target](analysis/targets-20261101-v1/agent_target_summary.csv), [titles](analysis/targets-20261101-v1/heading_asymmetric_costs.csv) and [subtypes](analysis/targets-20261101-v1/agent_subtype_assessments.csv) | Breakdown of the reviewed sample and distinction between correct family, specificity, ambiguity and error. |
| T-E | [Visual references per case](analysis/targets-20261101-v1/agent_reference_cases.jsonl) and [assessments with boxes and labels](analysis/targets-20261101-v1/agent_assessments.jsonl) | Localization and evidence of each agent observation. |
| V | [Geometric analysis verification](analysis/deep-20261101-v2/final_checks.json) and [target verification](analysis/targets-20261101-v1/final_checks.json) | Technical integrity and consistency; not human semantic validation. |

**C** is the unchanged [comparative conclusion](docs/findings/conclusions.md). It supplies the combined decision, priorities and limitation synthesis. This edition reorganizes existing documentary evidence; source predictions, original feedback and G/T/C reports retain their original scope and provenance.

<a id="crosswalk"></a>

### 13.1. Original-section reference crosswalk

References such as `[G, §5]` and `[T, §7]` always refer to the numbered sections in the original reports. The mapping below locates their material in this unified order. The machine-readable [coverage ledger](../../history/bounding-boxes-integrated-review-20261101T041555/coverage.json) accounts for all 206 inventoried source blocks, including reorganized headings and merged repetitions.

**G — Geometry v2**

- In-depth technical analysis of boxes, categories, and granularity → [unified location](#scope).

- 1. Useful conclusion for this experiment → [unified location](#correspondences).

- 2. Method and Data Mining foundation → [unified location](#method).

- 3. Six comparisons: histograms and correspondences → [unified location](#correspondences).

- 4. Covered surface without depending on the number of boxes → [unified location](#surface).

- 5. Geometric duplication, levels, and granularity → [unified location](#levels).

- Block-level comparison → [unified location](#granularity).

- Sensitivity: do not turn thresholds into truth → [unified location](#sensitivity).

- 6. Categories after spatial grouping → [unified location](#spatial-targets).

- Which disagreements dominate → [unified location](#spatial-targets).

- Disagreements that do merit your priority attention → [unified location](#relationships).

- 7. Patterns across pages and papers → [unified location](#patterns).

- 8. Your human examples: specific evidence and limits → [unified location](#human-cases).

- 9. Assessment matrix according to P01–P12 → [unified location](#relationships).

- 10. Cost and technical decision these data allow → [unified location](#cost).

- 11. Artifacts, reproducibility, and stopping point → [unified location](#artifacts).

- 12. Additional check of the shared caption: one specific case → [unified location](#relationships).

**T — Targets v1**

- Block targets: accuracy, specificity, and inconsistencies → [unified location](#decision).

- Main result → [unified location](#decision).

- 1. Scope and evidence → [unified location](#scope).

- 2. Vocabulary and states: what counts as an error → [unified location](#method).

- 3. Target census and count bias → [unified location](#census).

- Alternatives on exactly the same box → [unified location](#census).

- 4. Reviewed sample results: no overall ranking → [unified location](#sample).

- 5. Headings: the dimension with the highest cost for you → [unified location](#headings).

- Repeated pattern: same template, different results → [unified location](#headings).

- The native score does not automatically resolve inconsistency → [unified location](#headings).

- 6. Text, authors, dates, and false headings → [unified location](#text-authors).

- 7. Captions: correct class, markers, and relationship are three questions → [unified location](#captions).

- The apparent338 versus337 caption advantage is a marker → [unified location](#captions).

- 8. Image, logo, and header: content specificity versus position → [unified location](#visuals).

- 9. References, lists, tables, and equations → [unified location](#other-targets).

- 10. Complete patterns across tools and papers → [unified location](#patterns).

- 11. Which tool contributes more for your priorities → [unified location](#decision).

- 12. Evidence by case → [unified location](#agent-cases).

- 13. Verification, provenance, and limits → [unified location](#artifacts).

**C — Comparative conclusion**

- Comparative conclusion: bounding boxes, targets and structural usefulness → [unified location](#scope).

- 1. Conclusion and provisional decision → [unified location](#decision).

- 2. Agreed evaluation criterion → [unified location](#scope).

- 3. What the bounding box analysis demonstrates → [unified location](#geometry-summary).

- 3.1. Basic and Standard are practically equivalent in the measured geometry → [unified location](#geometry-summary).

- 3.2. Some discrepancies concern granularity or internal representation → [unified location](#levels).

- 4. What the deep target analysis adds → [unified location](#sample).

- 4.1. Titles: available signal, unambiguous label and inconsistency are different things → [unified location](#heading-summary).

- 4.2. Advantages and problems by target → [unified location](#target-summary).

- 4.3. More caption records do not mean more complete captions recovered → [unified location](#captions).

- 5. The relationship with the caption remains an independent limitation → [unified location](#relationships).

- 6. Observed cost and choice between Basic and Standard → [unified location](#cost).

- 7. What is decided and what remains open → [unified location](#decision).

- 8. Limits of the conclusion → [unified location](#limits).

- 9. Sources and traceability → [unified location](#artifacts).
