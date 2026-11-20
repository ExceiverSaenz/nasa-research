# Bounding box experiment documentation

Start with [current status](overview/current-status.md), the authority for the present state. Read [experiment design](overview/experiment-design.md) for scope and [conclusions](findings/conclusions.md) for the provisional choice and its evidence. Preserved plans and execution records describe their own dates; their pending statements do not override current status.

## Read by purpose

| Purpose | Entry |
| --- | --- |
| Read all three analyses in one complete document | [Integrated technical report](../../final-integrated-report.md) |
| Understand the comparison | [Design](overview/experiment-design.md), [analysis plan and P01Ã¢â‚¬â€œP12](methodology/analysis-plan.md) |
| Use existing commands | [Running guide](guides/running.md) |
| Read preserved comparison data | [Viewer guide](guides/viewer.md) |
| Read preserved preferences | [Feedback guide](guides/feedback.md) |
| Interpret geometric agreement | [Geometry method](methodology/geometry.md) |
| Interpret labels and target assessments | [Target method](methodology/targets.md) |
| Locate reports and data | [Findings catalog](findings/INDEX.md) |
| Understand schema catalogs | [Tool categories](reference/tool-categories.md) |
| Read structured formats and retained technical identifiers | [CSV/JSON and other formats](reference/structured-formats.md) |
| Trace specification decisions | [Decision record](decisions/decision-record.md) |

## Source modules and execution records

Source READMEs provide implementation detail; methods are in docs/methodology and execution ledgers in reports/execution. Current state is consolidated in the overview.

| Module | Purpose and documentation |
| --- | --- |
| `code/bbx/`, `code/run.py` | Orchestration, contracts, normalization, transfer and storage; [running](guides/running.md), [viewer](guides/viewer.md) |
| `analytics/automatic/` | [Automatic analysis README](../../../analytics/automatic/README.md); [analysis deliveries](../../../raw_results/analytics/README.md) |
| `analytics/geometry/` | [README](../../../analytics/geometry/README.md), [protocol](methodology/geometry-protocol.md), [execution and rulings](../reports/execution/geometry-execution.md) |
| `analytics/targets/` | [README](../../../analytics/targets/README.md), [protocol](methodology/targets-protocol.md), [execution and rulings](../reports/execution/targets-execution.md) |
| Preserved feedback | [Results and retirement](guides/feedback.md); [historical implementation evidence](../reports/tests/feedback-app-v1.md) |

Configuration and provenance remain in [experiment.json](../../../code/config/experiment.json), [requirements](../../../code/config/requirements), [model manifests](../../../code/config/model_manifests), [tool manifests](../../../code/config/tool_manifests) and [runtime](../../../../../history/bounding-boxes-reader-mvp-20261102T010950Z/archive/runtime). Their current roles and legacy-path resolution are described in the [layout guide](guides/organization.md).

## Preserved provenance

Superseded plans, ledgers, conversations, snapshots and diagnostic attempts were removed from the active experiment under the user-authorized cleanup. The [cleanup record](../../../../../history/bounding-boxes-cleanup-20261101T050218/README.md) preserves their original paths, hashes and external copies. Current evidence remains in the [findings catalog](findings/INDEX.md).
