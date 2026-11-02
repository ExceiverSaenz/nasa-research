# GitHub publication scope

This directory uses an allowlist in `.gitignore` to publish implementation,
offline tests, dependency inputs and locks, model/tool manifests, documentation,
and selected report evidence. Evidence paths are listed explicitly so future
execution outputs are not included automatically.

## Included report material

- The integrated report and all its documentation figures.
- Automatic analysis r2, geometry v2 and targets v1 reports, summary tables,
  charts, contact/review sheets used by the target examples, compact case
  records and verification/provenance files.
- Collection execution reports, including the earlier failed attempt, with
  their metrics, statuses and explicitly linked compact receipts.
- The smoke visual-review report with its eight annotated images, original
  background, findings, box catalog and verification records.
- The feedback implementation ledger and its screenshot/integrity evidence;
  selected workflow/inventory records explicitly referenced by documentation.

## Material kept local

The user chose to keep the page-review batches and the 397 full-page backgrounds
local (approximately 246 MiB). These are different from report charts and the
specific example sheets above. The link to `review/index.md` in the automatic
report and findings catalog therefore remains a local-only reference.

The following raw record tables remain local: `geometry_diagnostics.csv`,
`matched_boxes.csv` and `target_correspondences.csv`. Their aggregated results
are present in the reports and selected summary tables. Full detection/overlap/
clustering JSONL files, the large `source_map.json`, downloaded parser outputs,
ZIP bundles and complete interactive viewers also remain local. This selection
supports reading the reports; it does not reproduce every record-level analysis.

Original preferences under `feedback_data/` and copied human-feedback snapshots
are excluded. Empty review registries and compact review metadata do not imply
that the collection has been reviewed or approved.

Environments, caches and all other runtime files remain excluded. Ignoring a
path does not remove or alter the local file.

Documentation retains links to the original local evidence and to project
history outside this directory, including archived plans and bibliographic
chapter notes in the Obsidian vault. Those links require the corresponding local
artifacts; their contents are not copied into this selection. References to ZIP
bundles, raw outputs and full viewers likewise describe local evidence.
The GitHub selection alone is not a complete evidence archive.
The viewer and feedback application require their documented result inputs.
Publishing the source does not establish that this selection runs independently
of the rest of the project or provide new scientific validation.

Before pushing, review the exact selected files for credentials, private paths
and redistribution rights. The ignore rules filter filenames, not file contents.
From the repository root, inspect this selection with:

```powershell
git status --short --untracked-files=all -- test_libs/bounding_boxes
git ls-files --others --exclude-standard -- test_libs/bounding_boxes
```

When staging this delivery, specify `test_libs/bounding_boxes` explicitly.
The ignore rules here do not cover other directories of `nasa_research`.
