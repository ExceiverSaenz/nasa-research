# SiC bounding box comparative analysis plan

> **Document role: Preserved experimental method.** Original statements retain their stage-specific scope. See [current status](../overview/current-status.md) for current completion and pending validation.

> **For agentic workers:** when executing this plan in a future request, use `superpowers:executing-plans` and proceed through the phases with checkboxes. This document does not authorize its execution or the creation of infrastructure.

**Status:** documentary plan, November 1, 2026. Analysis not started.

**Goal:** compare the four tools through coverage, structural separation, granularity, nested relationships, labeling, geometry and cost, preserving original outputs and distinguishing automatic signals from reviewed findings.

**Architecture:** consume the corrected delivery as read-only input; build analytical tables and derived graphs with provenance per tool; organize an accumulated review against the PDF to confirm meaning, omissions and clipping. Publish results by dimension, paper and content type, with explicit pending items and without automatic overall scoring.

**Tech Stack:** for future execution, Python and standard libraries for JSON/CSV, descriptive statistics and small graphs; reuse existing normalized coordinates and backgrounds. Training, embeddings, OCR, new dependencies or another parser run are not initially required.

**Spec:** [consolidated report](../../../../../../history/bounding-boxes-cleanup-20261101T050218/preserved/docs/history/conversation-report.md), contracts from the [original plan](../../../../../../history/bounding-boxes-cleanup-20261101T050218/preserved/docs/history/implementation-plan.md) and priorities clarified by the user in this chat, transcribed in section 1. These clarifications take precedence for assessment; the original plan retains its historical and technical role.

## Global Constraints

- This delivery creates only this plan. All analysis phases remain pending.
- Use existing Heron, Heron-101, MinerU Basic and MinerU Standard results on the same 15 PDFs and 397 pages. These are 1,588 expected tool/page outputs, not 1,588 semantic verifications.
- Do not start Colab, GPU, R2, Docker, services, parsers, models, OCR or renders. Do not correct, regenerate or replace predictions to improve the comparison.
- Do not modify `new_code`, the vault, experiment configurations, locks, originals, receipts, backgrounds or previous reviews. Do not create a repository, worktree or commits for this documentary task.
- Preserve native labels, boxes, relationships and scores. Missing values remain missing; do not assign a parent's bbox to a child or generate associations by proximity.
- Apply the same procedure to all papers. Freeze analytical decisions before calculating results; no adjustments specific to title, author, page or paper ID.
- Separate agreement between predictions, geometric signals, confirmed findings and pending items. Without an independent reference, do not present overall accuracy, recall or mAP.
- Do not evaluate reading order or extend the hierarchy to cells, lines or paragraphs by default. Lists may be described as a capability, without reconstructing them at this stage.
- Do not set numerical weights, a resource budget, a quality threshold or a winner that the user has not agreed to. A failure in one box does not automatically imply discarding the entire tool.

## Review Focus

1. A caption inside a combined box is covered even if it has no box of its own; do not count it as an omission or invent geometry for it. Check F3/V1.
2. Zero records or relationships may mean an unreported function, a transport failure or actual absence of the element; keep these states separate. Check F1/V2 and F4/V5.
3. A box covering an entire region may mix columns, sections or text with visualizations; area agreement does not establish usefulness. Check F4/V4.
4. Numerous text rows and children without bbox may hide titles/captions or duplicate their counts; use common reviewed units. Check F3/V4 and F4/V6.
5. Reused Heron and corrected MinerU have different provenance and timing scopes; do not add copies together or impute per-paper times or memory. Check F1/V3 and F5/V9.

## 1. Agreed priorities and consequences for assessment

| ID | User priority | Analysis rule |
| --- | --- | --- |
| P01 | Cover all content; know what is omitted and how often. | Break down all categories; highlight titles, captions and body. The absence of a type in the output does not prove it does not exist in the PDF. |
| P02 | Accept figures, panels and caption inside a combined box as a useful basis. | Separate coverage, own boxes, internal segmentation and reported relationships. |
| P03 | Consistently preserving the relationship with the shared caption matters more than separating all panels. | Evaluate that relationship separately from the number of panels detected and boundary precision. |
| P04 | If a structural task is irregular, the user prefers to solve it uniformly with another technique; lists were also given as an example. | Describe which capability can be used and which would require uniform reconstruction; measure list availability and consistency when verifiable, without reconstructing them. |
| P05 | Accept one or several consecutive paragraphs per box in the same column and section; tolerate variability. | Do not automatically penalize differences in paragraph count, length or partitioning. |
| P06 | Mixing columns or text from different sections, or running text with visualizations, is unacceptable for the block. | Record such mixtures as high-impact issues. Their frequency and scope are reported before deciding on the entire tool. |
| P07 | Crossing a separation marked by a header or title is less tolerable. | Examine structural boundaries; distinguish title from body even though both are text. |
| P08 | For visualizations, the user tolerates broader grouping if consistent and if it does not merge widely separated groups. | Measure dispersion as a signal and check membership; distance alone does not prove an incorrect merge. |
| P09 | Values precise text labels; losing a title inside “text” requires more work than a paragraph marked as a title. | Keep both errors separate, with higher ordinal priority for title→text; without inventing a numerical cost ratio. Size is an inspection clue, not a validated correction rule. |
| P10 | Irregular tagging may be replaced by another uniform technique, but its precision does add value. | Evaluate labeling and geometry separately; a good box with a bad label may still be usable. |
| P11 | Clipping letters or words is annoying; the latest clarification withdrew absolute rejection. | Record extent and frequency of clipping; do not establish zero tolerance or automatic rejection. |
| P12 | No fixed time or memory limit; compare whether the improvement justifies the cost. | Present quality and resources together, preserving each measurement's scope and failures per attempt. |

Consistency is examined between comparable cases and by capability. It does not mean requiring identical box counts, equal paragraph sizes or uniform labels for elements with different functions. A systematically incorrect result may be consistent; consistency and adequacy remain separate.

## 2. Existing inputs and provenance to preserve

Paths in this section are relative to `test_libs/bounding_boxes/`. Their presence and some fields were inspected to draft the plan; collection hashes, metrics or agreements were not recalculated here.

| Input | Future use |
| --- | --- |
| [Corrected final status](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/final-status.json) | Declared technical scope: 15 papers, 397 pages, four tools; complete human review is false. |
| [Provenance per tool](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/tool-provenance.json) | Heron/Heron-101 from `collection-20261101T015723Z`; Basic/Standard from `mineru-nativefix-20261101T034122Z`. |
| [Preserved verification](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/verification.json) | Package identity, native coverage and historical verifications; does not replace an identity check when running the analysis. |
| [PDF inventory](../../../../raw_results/provenance/attempts/mineru-nativefix-20261101T034122Z/inventory.json) | Names, SHA256 and expected pages. Resolve local PDFs by identity, not only by name. |
| `results/mineru-nativefix-20261101T034122Z/assembled/{tool}/{paper_stem}/normalized.json` | Main analytical input, one array of detections per paper/tool. Tools: `heron`, `heron101`, `basic`, `standard`. |
| `results/mineru-nativefix-20261101T034122Z/assembled/{tool}/receipt.json` | Results, files/hashes per paper and resource samples per stage. |
| [Existing metrics](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/metrics.json) | Already calculated summary and timing fields; reference for checking future aggregations, without treating counts as quality. |
| [preserved data index; UI retired](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/viewer/viewer.json) and its `viewer.json` | Existing presentation and backgrounds. Do not start a server or modify `reviews.json` in this delivery. |
| [Original configuration](../../../../code/config/experiment.json) | Exploratory IoU 0.5, resource interval 1 s and one measured pass. `ready=false` does not invalidate later receipts or authorize new runs. |
| [Previous collection report](../../reports/execution/collection-20261101T015723Z/collection_report.md) | History of failures with another dependency; do not mix it into the failure rate of the corrected dependency closure. |
| [Smoke review](../../reports/execution/smoke-20261101T011229Z/visual-review/report.md) | Agent findings on one page, pending human validation; do not import them as reviews of the corrected collection. |

Do not count `assembled`, `viewer_source`, `viewer` and `download` as different runs. `assembled` provides the analytical projection; `original_ref` and `original_sha256` allow the local original to be resolved within its source attempt. The `/content/...` paths saved in JSONs are remote provenance, not active paths or permission to access another session.

The preserved ZIP has declared SHA256 `41626b5653343a117ca60cd6afec154dacbea5b5bc20c90ce19b6d8bc3e30744`. Its receipt does not imply that it has been verified again in this task.

## 3. Analytical representation and states

### 3.1 Two different units

**Native detection:** preserve `id`, `tool`, `paper_sha256`, `page_idx` (zero-based), `raw_label`, `bbox_raw`, `bbox_normalized`, `coordinate_system`, `page_dimensions`, `original_ref`, `original_sha256`, `relations`, `geometry_error` and `native_parent_ref` when present. The analytical key includes source attempt, tool, SHA256, page and ID; do not deduplicate distinct elements because they share text or a box.

**Review case:** element or group identifiable in the PDF with a tool-independent `case_id`. Contains paper/page, observed type, locator, review status and evidence; references zero, one or several detections for each tool. This case allows comparing one box with several without turning a parser's granularity into truth.

Review units: complete visible title; shared caption only once; visual body paragraph; table; equation; composite figure; verifiable panel and the other categories present. For body continuing in another column/page, record linkable physical fragments, without evaluating order or concatenating text. If paragraph boundaries or type cannot be distinguished, mark that uncertainty and do not impute a paragraph count.

The candidate inventory derived from predictions is not the complete PDF inventory. Only explicit review of the entire page, including regions without detections, allows setting `page_case_inventory_complete=true`.

### 3.2 Independent axes per case/tool

| Axis | Values and meaning |
| --- | --- |
| `coverage_status` | `full`, `partial`, `absent`, `undetermined`, `not_reviewed`. Refers to the case's visible content, not to having a child record. |
| `coverage_support` | List of `own_bbox`, `several_boxes`, `group_bbox`, `none`, `unknown`, with evidence IDs. A group box retains its identity; it is not copied to children. |
| `segmentation_status` | `coherent`, `needs_internal_split`, `structural_mixing`, `undetermined`, `not_reviewed`; specific issues separately. |
| `relation_status` | `reported_pending`, `reported_validated`, `reported_incorrect`, `not_reported`, `not_applicable`, `undetermined`. `relations=null` in normalization requires checking whether the original provides relationships before stating `not_reported`. |
| `tag_status` | `not_reviewed`, `adequate`, `inadequate`, `coarse_but_usable`, `not_evaluable`, `undetermined`. A group box does not amount to a specific label for all its components. |
| Evidence | `signal`, `agent_observation`, `human_reviewed`; preserve author/date, references and contradictory decisions as “Requires human validation”. An observation or test does not mark human review. |

Normative example of the agreed criterion: two images and their caption fully included in a combined box → `coverage_status=full`, support `group_bbox`; `needs_internal_split` if own boxes are missing. The semantic relationship still depends on what is reported and reviewed: geometric containment alone does not create figure–panel–caption edges.

Each case may have several problems. Issue counts are accompanied by unique affected cases; do not add clipping, mixing and label issues as if they were three omitted elements.

### 3.3 Analytical labels

Build a separate mapping table, with native label, its schema definition, level (block/body/child/inline), candidate analytical category, source and status (`documented`, `partial`, `unmapped`). Freeze it before summarizing semantic comparisons.

Schema candidates: `section_header`/`paragraph_title` for section heading; `caption` versus `image_caption`, `chart_caption`, `table_caption`; `picture` versus `image`/`chart`; `formula` versus `equation`. Preserve differences and subtypes. `header` is not equivalent by name to section title; `image_body` is not a panel; `equation_inline` without bbox is not an independently located equation.

This mapping describes what the schema declares, not the actual function of each region. The reviewed type comes from the PDF, even when the parser labels it incorrectly. A doubtful mapping remains pending; do not change originals to make categories match.

## 4. Techniques and metrics by dimension

### 4.1 Coverage: frequencies and multidimensional analysis

**Technique:** frequencies and cross-tabulations/OLAP by tool × paper × type × status; chapters 2 and 3 [B2, B3].

**Automatic:** count expected/produced/failed pages and records with valid bbox, without bbox or with geometric error. These counts describe the output, not how many real elements there are. Never interpret `rows_without_bbox` as the number of omissions.

**Reviewed:** for type `t`, tool `h` and reviewed case set `S`, define `F`=complete content, `P`=partial, `A`=absent, `U`=undetermined and `R`=not reviewed. All come from the same case inventory for the four tools.

- `N_evaluable = F + P + A`.
- `cobertura_completa_observada = F / N_evaluable`.
- `omision_observada = A / N_evaluable`; also report `parcial_observada = P / N_evaluable`.
- Always publish `F,P,A,U,R`, number of pages with complete inventory and own/group/several-box support. If the denominator is zero, result `N/A`, not 0%.
- Publish by paper and type; case aggregation (micro) and the mean across papers with evaluable cases of that type (macro) are different views. Do not collapse titles, captions and body into a single main rate.

These are review frequencies for the delimited set, not validated overall recall. A review targeted at suspicions does not automatically represent the collection. Omissions shared by the four tools can only be discovered by checking against the PDF or appropriate external evidence.

**Assessment:** lower confirmed incidence of absences and partial coverage, with particular visibility for titles/captions/body. With equal coverage, separating components provides an additional capability; it does not turn a covered group into an omission.

For inline equations, keep two different questions: content covered inside text and availability of an own box for independent location. The first can hold without the second; record both results without inventing geometry.

### 4.2 Structural separation: spatial similarity and verifiable boundaries

**Technique:** attributes and proximities from chapter 2 [B2], adapted to spatial relationships. Use verifiable positions, alignment and separations to generate candidates, preserving their source.

Record `cross_column`, `cross_section_boundary`, `cross_heading_boundary`, `body_visual_mix`, `independent_block_intrusion` and `distant_visual_merge`. Confirm boundaries in the PDF or in existing reviewable evidence; do not infer a correct section solely from the evaluated parser's tagging.

**Metrics:** unique cases with each issue / evaluable reviewed cases where separation is applicable; affected pages / reviewed pages; distribution of affected regions and references. Report both numerator and denominator, and coexisting issues.

**Assessment:** mixing columns, sections or body with visualizations has high impact; crossing a title is less tolerable than grouping paragraphs from the same section. The terms “high impact” are ordinal priorities, not weights. Proximity, box width or overlap alone do not certify the failure.

### 4.3 Granularity: Jaccard and many-to-many correspondences

**Technique:** set/Jaccard similarity [B2], adapted to geometric area, and bipartite graphs per tool pair, paper and page.

For valid boxes `a,b`, record intersection `I`, `IoU = I / (area(a)+area(b)-I)` and directional containments `I/area(a)`, `I/area(b)`. Keep the original IoU 0.5 as an exploratory descriptor, not a correctness threshold. Preserve all positive overlaps: filtering by 0.5 would lose a large box versus several small ones.

In each candidate component, record box count per side (1:1, 1:n, n:1, n:m) and compare, where applicable, the exact union of rectangles on each side. Do not replace the union with its enclosing rectangle. A component connected by minimal overlap is a correspondence hypothesis, not an accepted semantic unit.

**Metrics:** IoU/containment distributions; frequencies of correspondence types; union area differences. Separate geometric agreement from label agreement. Page area coverage may include whitespace and mixtures; do not use it as a percentage of actual content recovered.

**Assessment:** one box versus several paragraphs may be equally usable if it covers content and respects boundaries. Penalize only confirmed content or separation problems, preserving granularity differences as description.

### 4.4 Nested groupings and consistency: graphs and templates

**Technique:** labeled graphs and substructure patterns [B7], with support and conditional frequencies [B6]. This is an adaptation to directed document relationships; the book's main example studies undirected graphs.

Build the graph only with explicit relationships from the original (`relations`, parent/child references or other verified links). Preserve relationship type: a generic container does not demonstrate a multipanel figure; `image_body` does not demonstrate a panel. Do not create edges with IoU, proximity or similar labels.

Predefined templates: (G1) figure/group with linked shared caption; (G2) figure with differentiated panels; (G3) components within the same group and relationship with the shared caption; (G4) linked panel marker, only if the PDF shows markers. G2/G3 require the case's visible panels, not exactly two; the image provided by the user is an example, not a universal rule.

As an additional descriptor (G5), for visible lists record whether there is a list group, differentiated items and explicit membership of those items. An isolated `list_item` label reports item recognition, not complete grouping; absence of list structure does not imply that its text is omitted. Compare these capabilities on the same reviewed lists and show frequency of availability, partiality and correct membership, with pending items separate. Do not extend G5 to general hierarchies of lines or paragraphs.

**Automatic:** count templates reported by the schema, dangling links, relationships without sufficient type and missing own bbox. Use applicable records declared by each tool as denominator and label it as output availability, without comparing it as accuracy.

**Reviewed:** for the same applicable visual groups, publish frequencies of valid complete, partial, incorrect, unreported and undetermined structure; for G1, `observed_compliance = cases with a valid link / evaluable applicable cases`. Undetermined and pending cases are shown separately. Report by paper and comparable context, including panel count and layout type when verifiable.

**Assessment:** G1 takes priority over separation detail. A complete combined box may still be a useful basis even if G2 is missing. A function never reported is not “correct consistency”; its availability and the quality of the relationships it does produce are different results. Describe whether use requires uniform reconstruction, without performing it or setting an acceptance percentage yet. Do not extrapolate “always” from a finite collection.

Limit analysis to these templates; do not launch exhaustive subgraph or association mining. Do not interpret a rule's confidence as the probability that a relationship is correct. Co-occurrence of figure and caption does not demonstrate a link between them. Apply the same criterion to list-item co-occurrence.

### 4.5 Labeling: agreements, review and asymmetric costs

**Technique:** contingency/agreement tables between tools; confusion matrices only for cases with a reviewed reference [B4]; cost-sensitive assessment [B5].

**Automatic:** counts by native label and level; label sets of corresponding candidate regions, without arbitrarily choosing a winning label in many-to-many correspondences. A parser A × parser B table is agreement, not confusion against truth.

**Reviewed:** compare observed function and declared label when a unit attributable to the case exists. Separate title→text, body→title, caption→body, other errors, usable general label and non-evaluable cases. A combined box without specific labels for its children does not become many tagging errors; it lacks internal resolution. A completely omitted block is evaluated under coverage, without imputing an incorrect label to it.

**Metrics:** counts and proportions of each confusion over evaluable cases of its type; transition table; number of affected papers and pending cases. Keep semantic error, granularity and schema mapping separate.

For tagging consistency, publish the distribution of labels for the same function and context reviewed in the PDF, for example section titles of comparable level. As a descriptor, `predominance = max_l N(label=l, function, context) / N_evaluable_labels_for_that_function_and_context`. Also report the predominant label and its reviewed adequacy: predominance 1 may describe a uniform error and is not considered success on its own. The denominator's function cannot be derived solely from the label being evaluated. Preserve small strata and cases without an evaluable label as such, without claiming universal regularity.

**Assessment:** ordinal cost `title→text > body→title`, without an invented numerical relationship. Describe residual work: directly usable, needs localized correction, or a candidate for uniform reconstruction. A paragraph's size may guide inspection; it does not permit automatically discarding a title label. Do not correct native labels or train a classifier in this phase.

### 4.6 Geometry: robust statistics and anomaly candidates

**Technique:** median, percentiles, MAD and IQR [B3]; anomalies as a complement [B10]. Attributes: width and height relative to page, relative area, directional containments and horizontal/vertical distances between already identified components. A physical aspect ratio requires verified actual dimensions; `[1,1]` from a normalized output does not provide the PDF's physical size.

Publish `n`, missing values, minimum, P05, median, P95, maximum, IQR and MAD by tool and documented stratum. Define percentiles through linear interpolation over ordered values with index `r=(n-1)p`, `p` in `[0,1]`; `Q1=P25`, `Q3=P75`, `IQR=Q3-Q1` and `MAD=mediana(abs(x-mediana(x)))`, without a scaling factor. As a proposed exploratory signal, use values outside `[Q1-1,5 IQR; Q3+1,5 IQR]` when there are at least 20 comparable observations and positive IQR. This is a technical prioritization decision, not a user tolerance or an error rule. For smaller groups or zero dispersion, publish data/distribution without imputing a score. Do not adjust the rule after seeing which tool it favors.

**Reviewed:** record clipping of strokes/characters/words, visible extent, intrusion into an independent block, excess margin and merging of distant visuals; separate edge contact from actual clipping. Use existing backgrounds/PDF; if their resolution does not allow a decision, leave undetermined. Native character evidence may only support analysis if it already exists and can be verified; this plan does not add extraction or OCR to obtain it.

**Metrics:** cases affected by defect class / evaluable reviewed cases; affected pages; doubtful cases; descriptive severity and references. An unusual area may be a valid figure. A repeated error may not be anomalous. Do not delete, correct or stop reviewing cases because of their score.

**Assessment:** clipping is assessed by frequency and scope, with the annoyance indicated by the user; structural intrusions have greater impact than a white margin that does not incorporate other content. Keep that comparison as qualitative interpretation, without weights or automatic rejection.

### 4.7 Cost and failures: descriptive statistics with declared scope

**Technique:** multidimensional tables, percentiles and distribution/cost charts against reviewed findings [B3].

Existing fields: Heron has `result.load_s` and `result.timings[].inference_s`; MinerU has `result.total_parse_export_excluded_s`, with possibly null `inference_s` and `load_s` and `unknown_timing_reason`. Preserve those names and scopes. Check when `load_s` represents actual loading before adding it across papers.

Publish times per paper where they exist; `recorded_time / completed pages` with an explicit scope label; distribution per paper and, only for Heron when applicable, per page. Do not fabricate per-page MinerU times by dividing the total and presenting them as individual observations. Total stage time is published only if an explicit measurement exists; the last sampled `elapsed_s` is not the exact stage duration.

Samples `resources[].ram_bytes` and `resources[].gpu[].used_mib` correspond to the tool stage. Publish sampled maximum, median/P95 of valid samples, sample count, interval and monitor failures. Do not attribute that memory to each paper without verifiable timestamps. GPU is device memory, not exclusive attribution to the model; tree RSS may count shared memory repeatedly. Do not convert missing values into zero or claim that an actual peak was captured between 1 s samples.

For failures, separate attempt, versions, phase, paper, cause and final status. Denominator: paper/tool tasks attempted in that attempt, showing unattempted tasks separately. The smoke, native validation of 10.pdf and failed attempt are not interchangeable repetitions of the same measurement. Do not average historical failures with the corrected closure or count reused Heron twice.

**Assessment:** compare verified improvements against observed cost, with common reviewed cases. Without a fixed budget or weights, deliver tables of advantages and costs; detector time and parsing time are described separately. One pass does not estimate between-run variability, future stability or capability in 6 GB. Do not estimate monetary cost without documented prices and billable duration.

## 5. Efficiency and limits of automatic analysis

1. Read each `normalized.json` once and process by paper/page; keep IDs and references instead of duplicating images or loading all copies of `viewer.json`.
2. Start with counts, cross-tabulations, distributions and small templates. Do not run Apriori, FP-Growth or exhaustive subgraph mining to count already defined relationships.
3. The existing [comparison](../../../../code/bbx/compare.py) implementation iterates over pairs before filtering paper/page. In a future run, do not pass the entire collection to it at once. Partition first; pair cost remains tied to `sum(n_pagina^2)`, preserving relevant overlaps within each page. If this is still expensive, evaluate a spatial index without losing containments or large boxes.
4. Sparse/local graphs [B9] serve geometric candidates. Preserve all native relationships even if long; do not prune them through a neighbor threshold. Record the candidate policy so it can be checked for loss of relevant pairs.
5. MAD/IQR and templates will be the first prioritization layer. Only consider neighbor distance or local density [B10] if there is a question unresolved by that layer, sufficient comparable attributes and a demonstrable review benefit. Do not make LOF a mandatory dependency or copy its score as native confidence.
6. Clustering [B8] remains an optional exploration of case families. A dendrogram does not establish document hierarchy and good silhouette/cohesion does not prove that a caption belongs to a figure. Do not reconstruct parser results with clustering during their evaluation.
7. Measure the analysis's own time/memory when it runs and save them separately from inference resources. This efficiency proposal does not yet have a local benchmark.

## 6. Accumulated review and denominators

Semantic review is organized after completing the set's automatic outputs, in batches per paper; it does not require labeling cases one by one to unblock each calculation or turn ambiguous cases into obstacles to producing preliminary results.

- Final objective: review the 397 pages with the four outputs, keeping names visible as in the original protocol.
- Review order may alternate flagged cases, representative pages and cases without alerts. Initial strata are paper and verifiable layouts; rare classes are not selected solely through the label produced by the parser being evaluated.
- Stratified sampling [B2] may organize initial batches and ensure variety. It does not replace final scope or by itself provide an overall estimate. Publish targeted review and any probability sample separately; the latter would need its own design and weighting before inferring to the whole set.
- On each page, also review regions not covered by any tool. Do not limit review to agreement-graph components: that would leave shared omissions invisible.
- Inventory PDF elements as common cases before counting failures per tool. Preserve the visual reference and its authorship; do not call it a validated independent benchmark.
- Record `page_case_inventory_complete` and review of each case/tool/axis separately. A page with a complete inventory may still have pending tagging or relationships.
- Agent observations accumulate with their provenance; human approval is explicitly recorded and is not inferred from absence of comments, file imports or viewer tests.
- If only part was reviewed, the report presents that part's frequencies and the remaining pending scope. Do not assign zero failures to the remainder or extrapolate from the smoke.

## 7. Planned files for future execution

Create a new destination `test_libs/bounding_boxes/raw_results/analytics/<analysis_id>/` only when execution is authorized. `analysis_id` identifies this analysis, while each record preserves its `source_run_id`. A rerun or protocol modification produces another destination; it does not overwrite previous evidence.

| Future file | Responsibility and minimum fields |
| --- | --- |
| `analysis_manifest.json` | Version/hash of this plan, frozen analytical configuration, tools, inputs/hashes, provenance, date and phase states. |
| `source_map.json` | Mapping between `original_ref`, JSON fragment, local file, expected/checked SHA256 and resolution status. |
| `page_inventory.csv` | SHA256, PDF name, zero-based page, tool, technical status, source and review status. |
| `detections.jsonl` | Read projection with analytical key, native fields and clearly separated derived diagnostics. |
| `label_map.csv` | Documented analytical mapping, level, source and status of each label; preserves original label. |
| `descriptive_tables.csv` | Tool/paper/type/level/status, counts, denominators and amount of pending data. |
| `agreement_edges.jsonl` | Detection pairs from the same page, intersection, IoU, containments and label agreements with explicit scope. |
| `geometry_diagnostics.csv` | Attributes, stratum, n, statistic/rule, candidate signal and evidence; no signal is automatically marked as a human error. |
| `native_patterns.jsonl` | Graph/template, native references, applicability, output completeness and review status. |
| `case_registry.jsonl` | Tool-independent PDF cases, observed type, locator, reviewed expected relationships, author and page-inventory status. |
| `case_assessments.jsonl` | Case/tool, support detections, section 3.2 axes, issues, evidence, author, date and separate human approval. |
| `review_batches.json` | Batches per paper, selection rationale, planned/completed coverage and pending items; without importing smoke reviews as new acceptances. |
| `reviewed_metrics.csv` | Metric, tool, paper/type/context, numerator, denominator, uncertainties, scope and supporting cases. |
| `cost_by_paper.csv` | Available times, original field, scope, completed pages and missing data. |
| `cost_by_stage.csv` | Documented stage memory and times, provenance, interval and monitor failures; without fictitious per-paper attribution. |
| `failures.csv` | Attempt, version, phase, task, cause, status and appropriate denominator, with separate history. |
| `analysis_verification.json` | Technical analysis checks, input identity before/after, control cases, limits and errors. Does not equal scientific validation. |
| `report.md` | Comparison by dimension and type, traceable examples, advantages/costs, usable functions and pending items. |

The JSON/CSVs are future-result contracts, not files created by this plan. Do not modify the original viewer's format or reviews to accommodate them; any interface adaptation would require its own scope. Future report links will point to existing originals and backgrounds by identity.

## 8. Future execution phases and stopping criteria

All the following checkboxes are deliberately pending. Reading an input to draft the plan does not complete an analysis phase.

### F0. Freeze analytical protocol

**Question:** what will be calculated and how will it be interpreted before observing its results?

**Inputs:** this plan, current decisions and original configuration. **Outputs:** `analysis_manifest.json` and initial `label_map.csv`.

- [ ] Record the plan version/hash and a configuration with exploratory IoU 0.5, all positive overlaps, the IQR rule from section 4.6 and states/denominators from section 3.
- [ ] Document schema mappings; keep doubtful ones as `unmapped` or `partial`.
- [ ] Fix templates G1–G5, attribute scope and separation between signals and verdicts. Record these technical specifications as plan proposals, not numerical preferences expressed by the user.

**Stop/acceptance:** protocol recorded before calculation; no weight, doubtful mapping or missing data is silently filled in. A contradiction with recent instructions is resolved before executing the affected part.

### F1. Verify input and resolve provenance

**Question:** do the four sets correspond to the same PDFs and the declared runs?

**Inputs:** section 2. **Outputs:** `source_map.json`, `page_inventory.csv` and input identity in the manifest.

- [ ] Verify inventory, identities, normalized/native files and technical coverage against receipts. Expected: 15 PDFs/397 pages per tool; do not infer quality from this.
- [ ] Resolve remote references to preserved local files, checking SHA256 before using them; separate file path and JSON fragment.
- [ ] Check all required fields, null states, coordinates and resource origin; no copy is counted as a new run.

**Controls:** V2 (absence/unavailability), V3 (provenance) and V8 (invalid geometry), section 9.

**Stop/acceptance:** every input used has verifiable identity. A discrepancy blocks its use, is recorded and does not trigger automatic restoration, download or new inference. Unaffected tables may continue with explicit scope.

### F2. Produce descriptors and automatic candidates

**Question:** where do outputs differ and which cases should be reviewed together?

**Inputs:** verified inputs, protocol and label map. **Outputs:** `detections.jsonl`, `descriptive_tables.csv`, `agreement_edges.jsonl`, `geometry_diagnostics.csv` and `native_patterns.jsonl`.

- [ ] Generate counts by label/level/bbox and page without counting child records as additional boxes.
- [ ] Calculate overlaps by page and tool pairs, preserving many-to-many relationships and exact unions when applicable.
- [ ] Describe geometric attributes and IQR signals according to the protocol; do not remove extremes or impute scores or geometry.
- [ ] Inspect native graphs and count G1–G5 as output availability. Distinguish reference-resolution errors from unreported links.
- [ ] Check technical counts against already preserved metrics and investigate projection differences before publishing them.

**Controls:** V1, V3, V5, V6 and V8.

**Stop/acceptance:** every derived row refers to the original; no automatic signal asserts an omission, semantic mixture or incorrect label without review. If meaning cannot be resolved, the preliminary result remains available with pending status.

### F3. Prepare common inventory and accumulated review

**Question:** what elements exist in the PDF, including those absent from predictions?

**Inputs:** automatic candidates, existing PDFs/backgrounds and four outputs. **Outputs:** `review_batches.json`, `case_registry.jsonl` and page states.

- [ ] Create batches per paper that include pages without alerts, regions without predictions and priority types; preserve the full objective of 397 pages.
- [ ] Inventory common cases with the unit defined in section 3.1 and without imposing a parser's granularity.
- [ ] Explicitly record inventory completeness and visibility/resolution limits; do not generate new images to resolve them without further authorization.
- [ ] Keep ambiguous cases and agent observations for accumulated human review, without stopping automatic outputs or asking for human labeling at every processing step.

**Controls:** V1, V2 and V4.

**Stop/acceptance:** each paper/page is present in the registry, even if still pending; a complete review phase is declared only with an explicit record of the 397 pages. A sample or partial batch retains its scope.

### F4. Evaluate cases and calculate reviewed frequencies

**Question:** which differences imply losses or subsequent work according to the user's priorities?

**Inputs:** common inventory and evidence. **Outputs:** `case_assessments.jsonl` and `reviewed_metrics.csv`.

- [ ] Evaluate coverage and support without confusing absence of an own box with absence of content; record partial and undetermined cases.
- [ ] Evaluate boundaries, accepted granularity and clipping; preserve several issues per case without multiplying the number of affected cases.
- [ ] Review G1–G5 relationships and tagging in evaluable units. Check shared captions only once, relationship types and title→text priority.
- [ ] Calculate metrics by type/paper/context, numerators, denominators and pending items. Keep signals, agent observations and human reviews separate.

**Controls:** V1, V2, V4, V5, V6 and V7.

**Stop/acceptance:** no proportion lacks supporting cases or a denominator; unknown coverage remains unknown. If review is missing, deliver partial results without extrapolating them or declaring the capability resolved.

### F5. Compare quality and resources

**Question:** what improvement does each tool provide and what observed cost or residual task does it imply?

**Inputs:** reviewed metrics, receipts and preserved metrics from each attempt. **Outputs:** `cost_by_paper.csv`, `cost_by_stage.csv`, `failures.csv` and report comparisons.

- [ ] Extract times with their field/scope and summarize resources in their actual unit; preserve nulls and monitor failures.
- [ ] Present failures from each attempt with their versions and denominators; distinguish sessions, validations and reused results.
- [ ] Compare tools on the same reviewed cases. If review scope differs, show it without fabricating a comparable quality difference.
- [ ] Describe by capability: directly useful, useful as a basis pending separation, requires corrections or candidate for uniform reconstruction. These are interpretations with examples, not validated scientific labels or an automatic replacement decision.

**Controls:** V3, V7 and V9.

**Stop/acceptance:** provenance and scope allow interpretation of each comparison. Do not declare a winner by summed counts, overall average, isolated speed or unagreed weights.

### F6. Verify and deliver

**Question:** is the report reproducible, does it preserve inputs and express its limits?

**Inputs:** all derivatives. **Outputs:** `analysis_verification.json` and `report.md`.

- [ ] Check source identity before/after, resolvable references and control cases from section 9.
- [ ] Review coverage of P01–P12 in the report and publish pending items, human review achieved and limits of each metric.
- [ ] Deliver tables by dimension and examples of the same cases across tools, accompanied by cost and residual task; preserve contradictory alternatives.

**Stop/acceptance:** technical closure with intact sources and traceable results; complete semantic evaluation is declared only if review supports it. Do not turn this closure into authorization for new parsers, OCR or reconstruction techniques.

## 9. Control cases for a future implementation

These verify analytical logic; they are not paper results. No fixtures have been created or tests run while drafting the plan.

| ID | Control case | Expected result |
| --- | --- | --- |
| V1 | Two images and caption inside a combined box, without components' own boxes. | Content covered; separation pending; no omission or imputed boxes. A semantic relationship exists only if it has its own evidence. |
| V2 | Child without bbox, unresolved reference, unproduced page and valid page without detections. | Four distinguishable states; no absence automatically becomes zero errors, semantic omission or actual lack of content. |
| V3 | Heron repeated in `assembled` and `viewer_source`; remote `original_ref` and resources from the previous attempt. | One single run/input per identity, preserved provenance and local resolution with hash. |
| V4 | One box with three paragraphs from the same column/section; another crossing two columns or a title. | First granularity admissible; second a candidate mixture and, after review, a structural issue. |
| V5 | Overlapping parent/children, caption detected nearby without a link, `image_body` without panel information and list items without a reported group. | Possible legitimate overlap; proximity without relationship; `image_body` is not transformed into a panel; items recognized without inferred list hierarchy. |
| V6 | One large box versus three small ones with individual IoU below 0.5; shared caption repeated in references. | Overlaps/candidate correspondence preserved; exact union without double counting; one caption case with several references. |
| V7 | Located title labeled as text, body labeled as title and entirely absent title. | Two different confusions with asymmetric ordinal cost; absence assessed under coverage, without an imputed incorrect label. |
| V8 | Degenerate/out-of-range box, normalized dimensions `[1,1]`, missing values and stratum with zero MAD/IQR. | Invalid geometry recorded without correction; no invented physical dimension, invalid division or imputed score. |
| V9 | MinerU parsing time with null inference; GPU sampled per stage; old failure with another lock. | Separate scopes, preserved nulls, memory without fictitious per-paper attribution and historical failure outside the corrected attempt's rate. |

## 10. Form of the final decision

The report must allow assessment of four questions for each tool:

1. What content does it cover and what does it lose, especially titles, captions and body?
2. What boundaries, relationships and labels can be used with verified consistency and adequacy?
3. What part would remain for a subsequent uniform technique and what residual corrections does the utilized part require?
4. How much observed time, memory and failures accompany those advantages and limits?

Maintain a matrix of capabilities, issues and costs; not an aggregate score. Ordinal priorities guide interpretation, but do not yet set a minimum consistency percentage, a tolerable number of omissions, a cost per minute of correction or a universal boundary for “widely separated regions”. Exploratory geometric thresholds do not replace those decisions.

The preference for uniform reconstruction expresses the user's strategy for an irregular capability; it does not demonstrate that a specific complementary technique is better or authorize implementing it. The final choice may draw on useful parts of each output, preserving the fact that the experiment compares direct tools and does not validate an ensemble.

## 11. Foundations and traceability

| Ref. | Source consulted | Use in this plan |
| --- | --- | --- |
| B2 | [Chapter 2: Data](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_02_Data.md), §§2.2, 2.3.2, 2.4 | Quality/missing values, sampling, similarity, attributes and scales. |
| B3 | [Chapter 3: Exploring Data](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_03_Exploring_Data.md), §§3.2–3.4 | Frequencies, median, MAD/IQR, percentiles, visualization and OLAP. |
| B4 | [Chapter 4: Classification](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_04_Classification_Basic_Concepts.md), §§4.1–4.2 | Confusion matrices and need for reference classes. |
| B5 | [Chapter 5: Classification: Alternative Techniques](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_05_Classification_Alternative_Techniques.md), §5.7 | Rare classes and asymmetric costs. |
| B6 | [Chapter 6: Association Analysis](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_06_Association_Analysis_Basic_Concepts.md), §§6.1, 6.7 | Support/conditional frequencies, templates and limits of aggregation/confidence; Simpson's paradox. |
| B7 | [Chapter 7: Advanced Concepts](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_07_Association_Analysis_Advanced_Concepts.md), §7.5 | Graphs and substructure patterns; exhaustive mining cost. |
| B8 | [Chapter 8: Cluster Analysis](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_08_Cluster_Analysis_Basic_Concepts.md), §§8.3, 8.5 | Limits of hierarchies obtained by clustering and internal indices. |
| B9 | [Chapter 9: Additional Issues](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_09_Cluster_Analysis_Additional_Issues.md), §9.4.1 | Sparse graphs and comparison reduction. |
| B10 | [Chapter 10: Anomaly Detection](../../../../../../entregas/boveda-obsidian-v1/docs/analysis/referencia-bibliografica/data_mining/Capitulo_10_Anomaly_Detection.md), §§10.1, 10.3–10.5 | Rarity, systematic errors, neighbors/density and their limits. |

The chapters support general techniques; they do not prescribe box metrics for this experiment. Geometric adaptations, G1–G5 templates, the exploratory IQR rule, contracts and the F0–F6 sequence are concrete technical proposals of this plan. P01–P12 come from the user's decisions, not the book.

The bibliographic consultation used the official CLI, Bases, Fileclass and the local intermediary; chapter sources without the Documento class were preserved as bibliography. Accepted query/review packages: `859e440321024868b118aac7c3bfbc1a` and `f03b3f1900664f8bbcda110210cfb286`. That status establishes citations and structural rereading, not the scientific validity of the design.

The technical fields of this proposal were checked by reading [normalization](../../../../code/bbx/normalize.py), [comparison](../../../../code/bbx/compare.py), [resources](../../../../code/bbx/resources.py), receipts and existing JSON samples. Those modules were not imported or executed. The general script inventory guided reading; this experiment's scope is determined by its physical files and receipts, not absent historical paths.

## 12. Scope of the documentary delivery

`plan_analisis.md` is created as a new document; it does not replace `implementation-plan.md` or modify the consolidated report. The clarifications from this chat are preserved here to execute the plan without reconstructing them from memory.

Verification of this delivery is limited to rereading the plan, coverage of P01–P12, existence of cited links/inputs and consistency of states, formulas and phases. It does not mean having executed F0–F6, recalculated results, visually reviewed pages or validated efficiency or semantic quality.

