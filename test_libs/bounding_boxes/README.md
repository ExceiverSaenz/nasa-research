# Bounding-box analysis â€” reader MVP

This delivery is for reading the final reports, locating their evidence and
inspecting the programs that generated and analyzed the data. It does not bundle
execution environments, model weights, cached wheels or generated test fixtures.

## Final reports

- [Targets](reports/final-target-analysis.md)
- [Bounding boxes](reports/final-bbox-analysis.md)
- [Integrated report](reports/final-integrated-report.md)

All embedded report images are in [reports/assets](reports/assets/). Supporting
methods and prior narratives are in [reports/context](reports/context/).

## Trace the evidence and code

| Question | Location |
| --- | --- |
| What did the parsers produce? | [raw_results/code](raw_results/code/) |
| What numerical/structured data supports the analyses? | [raw_results/analytics](raw_results/analytics/) |
| What human preferences were used? | [raw_results/feedback](raw_results/feedback/) |
| What inventory/receipts identify the executions? | [raw_results/provenance](raw_results/provenance/) |
| What generated the parser data? | [code/bbx](code/bbx/): adapters, worker, normalization, delivery and workflow |
| What analyzed it? | [analytics/automatic](analytics/automatic/), [analytics/geometry](analytics/geometry/), [analytics/targets](analytics/targets/) |
| What configurations and dependencies were used? | [code/config](code/config/) |
| What checks explain the implementation? | [tests/code](tests/code/), [tests/analytics](tests/analytics/) |

The chain is `code -> raw_results/code -> analytics -> raw_results/analytics ->
reportes`. The original human feedback is separate from predictions and is not
exhaustive ground truth. Preserved scientific results were not regenerated.

## Delivery boundaries

The five main folders are `reports`, `raw_results`, `analytics`, `code` and
`tests`. The small root `run.py` launcher and hidden `.layout.json` preserve the
entrypoint and translations of historical paths. Keep them with this folder.
Full environments/caches and generated test fixtures were archived outside the
delivery; reproducing remote inference or cache-dependent tests needs separately
prepared dependencies/resources. Source, locks and receipts remain inspectable.
The prior interactive viewer and feedback applications were retired.

Some supporting documents retain links to optional external history or project
bibliography; those archives are not required to open the three final reports
and their embedded images. Original scientific data is retained in full rather
than silently reduced to selected tables.

## GitHub selection

This PR includes reports/assets/context, source, configuration, test source,
computed analytical data, consumed human feedback and selected provenance.
`raw_results/code/` (original parser dumps) and `raw_results/tests/` (generated
test evidence/fixtures) stay local. Links to those inputs or external history
are local traceability references, not files supplied by this PR. Rerunning the
analytical pipeline requires the original parser inputs and separately prepared
dependencies; this is a reader/source/data delivery, not a bundled lab environment.
