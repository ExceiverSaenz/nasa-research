# Preserved feedback results

The standalone feedback application and its tests were removed by explicit user
request. Its execution PID/log files and synthetic feedback fixtures were also
removed after checking that no listener was active on its documented port 8770.
The application is no longer available for collecting new preferences.

## Retained results

- [Original user preferences](../../../../raw_results/feedback/session-v1/feedback.json): retain IDs, revisions, history, PDF/page identity, regions and notes.
- [Geometry feedback snapshot](../../../../raw_results/analytics/deep-20261101-v2/human_feedback_snapshot.json) and [context](../../../../raw_results/analytics/deep-20261101-v2/human_feedback_context.jsonl): record the exact selected feedback used by that analysis.
- [Target-analysis snapshot](../../../../raw_results/analytics/targets-20261101-v1/feedback_snapshot.json): preserves that analysis's input.
- [Historical implementation ledger](../../reports/tests/feedback-app-v1.md), [screenshot](../../../../raw_results/tests/code/feedback-app-v1/final.png) and [integrity receipt](../../../../raw_results/tests/code/feedback-app-v1/original-integrity.json): retained verification evidence.

These are selected preferences, not exhaustive page ground truth or a trained
model. The [geometry report](../../../final-bbox-analysis.md)
and [targets report](../../../final-target-analysis.md) explain
their use and limits. Original analytical results were not changed by retirement.

An independent recovery ZIP and hashes of retired files are kept outside this
experiment under `history/feedback-retirement-20261102T003028Z/` in the project root.
