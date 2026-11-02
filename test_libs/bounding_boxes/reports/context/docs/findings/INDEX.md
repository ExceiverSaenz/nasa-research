# Findings and evidence catalog

Use [current status](../overview/current-status.md) for present state and [conclusions](conclusions.md) for the provisional choice. Reports and data remain beside the evidence that produced them. This catalog does not recalculate or newly verify their results.

## Current deliveries

| Delivery | Entry and supporting artifacts | Meaning |
| --- | --- | --- |
| Unified technical analysis | [Complete report](../../../final-integrated-report.md) | One thematic analysis with all source technical content, tables, cases and references mapped; includes English presentation figures. |
| Corrected collection | [Report](../../reports/execution/mineru-nativefix-20261101T034122Z/report.md), [final status](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/final-status.json), [verification](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/verification.json), [provenance](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/tool-provenance.json) | Completed technical comparison; reused Heron and newly executed Basic/Standard remain distinct. |
| Automatic analysis r2 | [Report](../../reports/analytics/auto-20261101T080056Z-r2/report.md), [verification](../../../../raw_results/analytics/auto-20261101T080056Z-r2/analysis_verification.json), [agreement](../../../../raw_results/analytics/auto-20261101T080056Z-r2/agreement_summary.csv), [costs](../../../../raw_results/analytics/auto-20261101T080056Z-r2/cost_by_stage.csv), [attempt failures](../../../../raw_results/analytics/auto-20261101T080056Z-r2/attempt_failure_summary.csv) | Descriptive predictions and costs, preserving configurations and denominators. |
| Geometry v2 | [Report](../../../final-bbox-analysis.md), [summary](../../../../raw_results/analytics/deep-20261101-v2/summary.json), [block pairs](../../../../raw_results/analytics/deep-20261101-v2/block_pair_summary.csv), [sensitivity](../../../../raw_results/analytics/deep-20261101-v2/granularity_sensitivity.csv), [checks](../../../../raw_results/analytics/deep-20261101-v2/final_checks.json) | Union agreement, granularity candidates, category patterns and structural diagnostics; not accuracy. |
| Targets v1 | [Report](../../../final-target-analysis.md), [census](../../../../raw_results/analytics/targets-20261101-v1/target_census.csv), [target assessments](../../../../raw_results/analytics/targets-20261101-v1/agent_target_summary.csv), [heading costs](../../../../raw_results/analytics/targets-20261101-v1/heading_asymmetric_costs.csv), [subtypes](../../../../raw_results/analytics/targets-20261101-v1/agent_subtype_assessments.csv), [checks](../../../../raw_results/analytics/targets-20261101-v1/final_checks.json) | Full output census plus targeted agent assessment; no representative human benchmark. |
| Review preparation | [Review index](../../reports/analytics/auto-20261101T080056Z-r2/review/index.md), [review status](../../../../raw_results/analytics/auto-20261101T080056Z-r2/review_status.json) | All-page review batches; preparation does not mean review completed. |

The geometric [caption-parent diagnostic](../../../../raw_results/analytics/deep-20261101-v2/caption_parent_diagnostics.json) and target [caption text summary](../../../../raw_results/analytics/targets-20261101-v1/native_caption_text_summary.json) explain why relationships and isolated caption markers require separate interpretation. [Methods](../methodology/geometry.md) and [target methods](../methodology/targets.md) define populations and limits.

## Historical and diagnostic evidence

| Preserved evidence | Status and use |
| --- | --- |
| [Smoke report](../../reports/execution/smoke-20261101T011229Z/smoke_report.md), [agent visual review](../../reports/execution/smoke-20261101T011229Z/visual-review/report.md) | One-page historical execution; observations pending human validation, not collection review. |
| [Earlier collection report](../../reports/execution/collection-20261101T015723Z/collection_report.md) | Heron completed; MinerU failed on 11 papers under the earlier native dependency. Retain failures separately from the corrected delivery. |

Superseded automatic/deep/target diagnostics and implementation history were removed from this active tree. Their [verified external backup](../../../../../../history/bounding-boxes-cleanup-20261101T050218/README.md) retains the correction history and exact original artifacts; the current deliveries above remain the working evidence.
