# Tool category catalog

The canonical catalog is [tool-multipanel-categories.csv](../../../../code/config/tool-multipanel-categories.csv): four tools, eighteen English columns. The removed nine-column catalog was verified to equal its first nine columns exactly; consolidating it loses no row, value or source reference. Historical snapshots and the former base file are preserved in the [cleanup backup](../../../../../../history/bounding-boxes-cleanup-20261101T050218/README.md).

## Columns

| Group | Columns |
| --- | --- |
| Base vocabulary and provenance | `model`, `categories`, `scope`, `source`, `child_categories`, `inline_types`, `internal_detector_classes`, `format`, `version_reference` |
| Multipanel documentary assessment | `panel_separation`, `panel_identifiers`, `panel_figure_relationship`, `panel_shared_caption_relationship`, `multipanel_limitations`, `multipanel_method`, `multipanel_evidence`, `multipanel_sources`, `multipanel_review_date` |

The first nine columns provide the former base view without maintaining a second CSV. No executable consumer of the retired documentary catalog was found; native model labels, URLs, row order and all remaining values are retained.

Heron catalogs list the 17 published detector labels. A direct detector's boxes, labels and scores do not inherit all Docling pipeline capabilities. MinerU catalogs distinguish page block types, container children, inline types and internal detector classes. An `image_body` is a visual body, not proof of a panel; inline text without geometry is not an independently localized detection.

These records preserve documentary research context, including branch/version notes that predate pinned execution. Supported types are not an observed inventory or a guarantee that each tier emits each type. For executed identities use [experiment.json](../../../../code/config/experiment.json), [model manifests](../../../../code/config/model_manifests), [tool manifests](../../../../code/config/tool_manifests) and the corrected delivery's [provenance](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/tool-provenance.json). Do not turn naming similarity into an accepted figure–panel–caption association.

Observed frequencies and localized label assessments are in the [target census](../../../../raw_results/analytics/targets-20261101-v1/target_census.csv) and [target report](../../../final-target-analysis.md). The [target method](../methodology/targets.md) explains family, subtype and function; [conclusions](../findings/conclusions.md) state the provisional interpretation.
