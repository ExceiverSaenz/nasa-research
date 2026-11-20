# Comparative conclusion: bounding boxes, targets and structural usefulness

> **Document role: Provisional findings.** Original statements retain their stage-specific scope. See [current status](../overview/current-status.md) for current completion and pending validation.

**Date:** November 1, 2026.  
**Scope:** four tools —Heron, Heron-101, MinerU Basic and MinerU Standard— on 15 papers and 397 pages.  
**Nature:** synthesis of existing results and a provisional technical decision; does not constitute global semantic validation.

## 1. Conclusion and provisional decision

**MinerU Basic is the preferred candidate as the segmentation base for this collection, but its tagging and structural relationships must not be assumed to be a complete and uniform solution.** This decision combines the visual preference expressed by the user, the observed equivalence between Basic and Standard and Basic's lower recorded resource usage. It does not imply that Basic has been shown to have the best true coverage or the highest global semantic accuracy. [G, §§1, 8 and 10; T, §§5 and 11]

**MinerU Standard showed no relevant improvement in boxes or block labels that would justify preferring it to Basic in this experiment.** Heron retains useful title and image signals that MinerU may generalize as `text` or `header`; however, its simultaneous labels and some false titles prevent considering it an unequivocally better substitute. Heron-101 also showed no consistent improvement over Heron in the reviewed cases. [G, §§3 and 10; T, §§4–11]

The operational conclusion is to retain the original outputs, use Basic as the base and later evaluate a uniform technique for the capabilities that proved unreliable: title identification, distinction of visual content within headers and preservation of figure–panels–caption relationships. **Neither that complementary technique nor an ensemble of tools has been implemented or validated.** [G, §§9–11; T, §11]

## 2. Agreed evaluation criterion

The decision responds to the user's priorities, preserved in the [analysis plan](../methodology/analysis-plan.md), section 1:

- Prioritize coverage and consistency, especially in titles, captions and body text.
- Accept several consecutive paragraphs in one box if they belong to the same column and section.
- Accept a combined figure as a useful base, even if its components have not been separated internally.
- Give greater importance to preserving the shared caption than to immediately obtaining individual boxes for all panels.
- Avoid mixing columns, sections, text and visualizations, and respect boundaries marked by titles.
- Value correct specific labels; a title lost as `text` requires more work than text marked as a title.
- Prefer reconstructing a capability uniformly when its results are irregular, rather than reviewing the entire document to find exceptions.
- Compare time, memory and failures without setting a budget or overall score that the user has not agreed to.

Therefore, a geometric difference is not automatically penalized. **Localization and relative coverage, granularity, target, subtype and structural relationship** are distinguished. A box may be useful even if its label is general; a correct label may coexist with an incorrect relationship. [G, §§5, 9 and 12; T, §§2 and 7]

## 3. What the bounding box analysis demonstrates

### 3.1. Basic and Standard are practically equivalent in the measured geometry

| Comparison | IoU between box unions | Block-level granularity candidates |
| --- | ---: | ---: |
| Heron / Heron-101 | 97.315 % | 7 |
| Heron / MinerU Basic | 93.327 % | 29 |
| Heron / MinerU Standard | 93.326 % | 29 |
| Heron-101 / MinerU Basic | 92.644 % | 29 |
| Heron-101 / MinerU Standard | 92.644 % | 29 |
| MinerU Basic / MinerU Standard | **99.999102 %** | 0 |

Source: [geometric summary](../../../../raw_results/analytics/deep-20261101-v2/summary.json) and [block comparison](../../../../raw_results/analytics/deep-20261101-v2/block_pair_summary.csv). Area agreement is calculated over the union of rectangles, without double counting. Candidates may recur across pairs: they must not be added together as distinct cases. [G, §§3–5]

Basic and Standard each have 4,168 blocks that enter spatial correspondences with IoU ≥ 0.9 and agree in their native labels. The almost total agreement supports choosing between them on cost and observed usefulness, without attributing an advantage to Standard that the results do not show. **99.999102 % is geometric agreement between predictions, not accuracy against the PDF.** [G, §§1 and 6; T, §11]

### 3.2. Some discrepancies concern granularity or internal representation

Each MinerU retains 437 groups of coincident parent–body boxes: 213 `chart/chart_body`, 162 `image/image_body` and 62 `table/table_body`. They do not automatically represent erroneously duplicated figures. Mixing those levels with independent blocks may inflate apparent differences in count, size and labels. [G, §5; [coincident boxes](../../../../raw_results/analytics/deep-20261101-v2/coincident_boxes_summary.csv) table]

In `6.pdf`, page 15, a visual region appears as one box in Heron and four blocks in MinerU. For the example presented, the IoU of their unions is approximately 0.9641. This is evidence of a different partition with a very similar area, compatible with the user's tolerance for granularity differences. It does not by itself demonstrate that the membership of the parts or the caption is correctly resolved. [G, §5; [visual example](../../../assets/bbox/granularity_example.png)]

**Consequence:** box count and individual IoU are insufficient to decide which tool is most useful. It is necessary to observe whether content is preserved and relevant boundaries are respected. Area alone is also insufficient: a large box could include whitespace or mix regions that should remain separate. [G, §§4–5]

## 4. What the deep target analysis adds

The census covers all 35,240 records in the collection. The localized semantic evaluation inspected 65 ROIs and, after excluding repetitions and references without a single class, scored **59 unique objects and 236 tool/case assessments**. The visual reference was assigned by the agent on the existing backgrounds; it is not human validation. The sample targeted discrepancies and controls, so its rates do not estimate accuracy across the entire collection. [T, §1; [audit verification](../../../../raw_results/analytics/targets-20261101-v1/audit_verification.json)]

### 4.1. Titles: available signal, unambiguous label and inconsistency are different things

| Tool | Titles reviewed | Appropriate title family only | Title and another class simultaneously | Title only as text |
| --- | ---: | ---: | ---: | ---: |
| Heron | 19 | 10 | 9 | 0 |
| Heron-101 | 19 | 8 | 9 | 2 |
| MinerU Basic | 19 | 9 | 0 | 10 |
| MinerU Standard | 19 | 9 | 0 | 10 |

Source: [directional heading costs](../../../../raw_results/analytics/targets-20261101-v1/heading_asymmetric_costs.csv) and T, §5. **Twelve of the 19 titles belong to `8.pdf`**; the table does not support claiming that MinerU loses that proportion of titles throughout the collection.

Heron retains more candidate signals in this sample, but nine cases require resolving simultaneous labels. MinerU provides less ambiguous decisions, although ten reviewed titles remain `text`, the error the user considers more costly. Therefore, neither counting all Heron signals as clean successes nor interpreting MinerU's absence of ambiguity as sufficient accuracy would be correct. [T, §§4–5]

There is a specific functional inconsistency: in 11 headings from the same template in `8.pdf` —*Baseline for Current Fuel-System Designs* and *New Baseline for Licensing*— Basic and Standard alternate between `paragraph_title` in four cases and `text` in seven. Heron alternates between a title alone and a title plus text. This pattern supports the need for a uniform title strategy, without extrapolating the behavior to any document. [T, §5]

### 4.2. Advantages and problems by target

| Target or function | Localized evidence | Interpretation for the decision |
| --- | --- | --- |
| Text and authors | MinerU retains the six reviewed authors/affiliations as `text`; Heron may add `section_header` and Heron-101 even uses it as the sole class for authors. | MinerU offers a useful general representation in these cases; Heron must not turn any title signal into an accepted section. |
| Editorial images and logos | Of ten reviewed visuals, Heron identifies nine as `picture`; MinerU uses `header` in nine and recognizes the remaining illustration as visual. | Heron provides greater content specificity in those logos/covers. `header` may describe their position, but does not by itself satisfy the image identification the user prefers. |
| Captions | Of five reviewed captions, each tool provides four with an unambiguous caption family; Heron has one multitarget case and the other three tools one as `text`. | No winner is established for this family. Subtype and relationship must also be checked. |
| Caption subtype | In T018, `15.pdf`, page 30, Basic and Standard label a figure caption as `table_caption`. | The caption family is appropriate, but the subtype is incorrect. Do not confuse the correct family with the correct specific label. |
| Bibliographic references | MinerU uses `ref_text` in four reviewed references; Heron uses `list_item`. | MinerU offers greater bibliographic specificity; both properties may be compatible, so the difference does not automatically imply an error. |
| Lists | One reviewed bullet appears as `list_item` in Heron and `text` in MinerU. | A signal favoring Heron in that case; the sample is insufficient to establish list consistency. |
| Tables and equations | All four tools classify three control tables and three control equations appropriately. | No advantage was observed in those controls; this does not amount to an exhaustive evaluation. |

Sources: T, §§4 and 6–11; [summary by target](../../../../raw_results/analytics/targets-20261101-v1/agent_target_summary.csv) and [subtype assessment](../../../../raw_results/analytics/targets-20261101-v1/agent_subtype_assessments.csv).

### 4.3. More caption records do not mean more complete captions recovered

Basic declares 338 captions and Standard 337, but those counts include 53 and 52 isolated markers, respectively. The specific difference in `6.pdf`, page 12, is a `(b)` labeled `image_caption`; both retain the complete captions of Figure 4 and Figure 5. Therefore, that additional record does not prove a complete-caption coverage advantage for Basic. [T, §7; [caption text profile](../../../../raw_results/analytics/targets-20261101-v1/native_caption_text_summary.json)]

The same principle applies to all categories: native counts describe how each engine represents its output; they are not directly true positives, omissions or errors. Agreement between engines also cannot replace a reviewed reference, especially between versions of the same family. [T, §§2–3 and 10]

## 5. The relationship with the caption remains an independent limitation

In `6.pdf`, page 15, Basic's JSON retains the caption of Figure 8, but declares it a child of the first lower chart belonging to Figure 9. The case was checked by the agent against the original background and structure; its pointers, coordinates and text are preserved. It is not generalized to all relationships or presented as human review. [G, §12; [caption and parent diagnostic](../../../../raw_results/analytics/deep-20261101-v2/caption_parent_diagnostics.json)]

This case is decisive when interpreting the two analyses together: **good boxes, a correct caption label and incorrect structural membership can coexist**. Therefore, figure–panels–caption links must be evaluated separately. Having more declared relationships does not demonstrate that they are correct or that they consistently preserve a shared caption. [G, §§9 and 12; T, §7]

## 6. Observed cost and choice between Basic and Standard

| Recorded measurement | MinerU Basic | MinerU Standard |
| --- | ---: | ---: |
| Available time sum: SDK parsing, without export | 301.352 s | 321.891 s |
| Sampled stage peak RAM | 5,853 MiB | 9,707 MiB |
| Sampled device peak GPU | 2,862 MiB | 12,473 MiB |

Sources: G, §10; [stage costs](../../../../raw_results/analytics/auto-20261101T080056Z-r2/cost_by_stage.csv) and [timing distributions](../../../../raw_results/analytics/auto-20261101T080056Z-r2/timing_distributions.csv). RAM is rounded.

These are observations from one pass and stage samples; they do not estimate variability, memory exclusive to the model or universal hardware requirements. Heron timings correspond to detector inference and are not directly comparable with MinerU SDK parsing. Within the available scope, Basic records lower resource usage without a relevant disadvantage in boxes or block labels compared with Standard. This combination supports the provisional preference for Basic. [G, §10]

## 7. What is decided and what remains open

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

## 8. Limits of the conclusion

1. **There is no exhaustive independent reference for the PDF.** Geometric agreement does not measure true coverage and does not necessarily reveal shared omissions.
2. **Target evaluation is directed and was performed by the agent.** Its 59 objects and 236 assessments do not constitute a representative human benchmark of the 397 pages.
3. **Consistency and adequacy are not equivalent.** A systematically general or incorrect label may be consistent; a useful function may appear irregularly.
4. **Semantically acceptable granularity still requires checking.** High union IoU does not by itself confirm membership, section boundaries or a shared caption.
5. **Resources were not measured through comparable end-to-end repetitions.** No universal performance advantages or joint time ranking of the four engines are inferred.
6. **The total human cost of correcting each output was not quantified.** Residual tasks and priorities were identified, but not correction minutes or an aggregate score.

These limits do not prevent a provisional working choice; they delimit what that choice can claim. The analyses recorded integrity checks of 2,452 original files, successful tests and technical invariants. That supports preservation and consistency of the calculations, not global semantic accuracy. [G, §11; T, §13; G and T verifications in the following section]

## 9. Sources and traceability

The references **G** and **T** used in the document correspond to the two main reports:

| Ref. | Source | Role in this conclusion |
| --- | --- | --- |
| **G** | [Full technical report: boxes, categories and granularity](../../../final-bbox-analysis.md) | Area agreement, granularity, hierarchies, costs and shared-caption case. Current version v2; v1 is not used as the final result. |
| **T** | [Deep target analysis](../../../final-target-analysis.md) | Labels per corresponding region, agent visual reference, directional errors, subtypes and inconsistencies per tool. |
| P | [Analysis plan](../methodology/analysis-plan.md) | Priorities P01–P12 and separation between coverage, segmentation, relationships, labels and costs. |
| G-D | [Geometric results summary](../../../../raw_results/analytics/deep-20261101-v2/summary.json) and [block summary](../../../../raw_results/analytics/deep-20261101-v2/block_pair_summary.csv) | Numerators and metrics supporting the geometric comparison. |
| T-D | [Assessment by target](../../../../raw_results/analytics/targets-20261101-v1/agent_target_summary.csv), [titles](../../../../raw_results/analytics/targets-20261101-v1/heading_asymmetric_costs.csv) and [subtypes](../../../../raw_results/analytics/targets-20261101-v1/agent_subtype_assessments.csv) | Breakdown of the reviewed sample and distinction between correct family, specificity, ambiguity and error. |
| T-E | [Visual references per case](../../../../raw_results/analytics/targets-20261101-v1/agent_reference_cases.jsonl) and [assessments with boxes and labels](../../../../raw_results/analytics/targets-20261101-v1/agent_assessments.jsonl) | Localization and evidence of each agent observation. |
| V | [Geometric analysis verification](../../../../raw_results/analytics/deep-20261101-v2/final_checks.json) and [target verification](../../../../raw_results/analytics/targets-20261101-v1/final_checks.json) | Technical integrity and consistency; not human semantic validation. |

The Data Mining basis —proximities, histograms, clustering, agreements, matrices with a reference and asymmetric costs— is documented in G, section 2, and T, sections 1–2. Priorities come from the user; the geometric adaptations and experiment thresholds are not presented as prescriptions from the book.

This Markdown synthesizes evidence already generated. Its creation does not execute additional analyses, parsers, OCR, models, Colab or modifications to predictions, feedback or source reports.

