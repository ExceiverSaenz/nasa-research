# Functional layout

The approved migration separates the following roles. Location does not imply
scientific authority, semantic validation or human approval.

| Location | Contents |
| --- | --- |
| `code/` | Application/backend code, parser adapters and storage |
| `analytics/` | Automatic, geometric and target-analysis programs |
| `tests/code/` | Product, storage, transport and contract controls |
| `tests/analytics/` | Analytical calculations and analytical layout controls |
| `tests/fixtures/` | Shared synthetic test inputs |
| `raw_results/code/` | Preserved execution attempts, native outputs, receipts and viewers |
| `raw_results/analytics/` | Calculated tables, JSON/JSONL, charts and evidence snapshots |
| `raw_results/tests/code/`, `raw_results/tests/analytics/` | Machine test reports and generated fixtures |
| `reports/` | Integrated, execution, analytical and test narratives |
| `docs/` | Instructions, scope, methods, decisions and reference contracts |
| `config/` | Experiment inputs, dependency locks and pinned manifests |
| `feedback_data/` | Original human preferences, retaining their identities and scope |
| `runtime/` | Environments, dependencies, caches, diagnostic environments and operational state |

Native parser Markdown, historical code snapshots and diagnostic scripts remain
inside their preserved evidence directories. They are not promoted to active
application code or to authored reports merely because of their extension.

## Entrypoints

From the project root:

```powershell
python -B test_libs/bounding_boxes/run.py --help
python -B test_libs/bounding_boxes/run.py colab plan --attempt unused
python -B -m pytest test_libs/bounding_boxes/tests/code
python -B -m pytest test_libs/bounding_boxes/tests/analytics
```

Planning does not allocate sessions. Native ABI tests keep their opt-in flag; browser tests were retired. Skipped
cases are reported explicitly. A passing suite
is not a measurement of semantic extraction accuracy.

The root launcher delegates to `code/run.py`; no second application copy exists.
Analytical scripts retain direct-file entrypoints under `analytics/` and use
package-qualified imports. Their real execution still requires new output
destinations and separate authorization according to the experiment guides.
For canonical analytical output directories, authored Markdown goes to
`reports/analytics/<run>/`, while figures and tables remain in
`raw_results/analytics/<run>/`. Existing report guards cover the report location
before any figure regeneration.

## Historical paths and shared data

`.layout.json` is a small old/new path map. Active readers resolve historical
local references through `code/bbx/layout.py`. Frozen manifests, input hashes,
native outputs and remote `/content/...` provenance strings remain unchanged.
Old source/data directory trees are not recreated as compatibility copies.

The remote input ZIP is assembled from the current local folders using its
existing flat `bbx/`, `requirements/`, manifests and entrypoint contract. This
was tested offline; no remote session or inference was launched.

Same-volume renames preserve hardlink sharing. The cache journal has current
alias paths and layout revision 2; its exact previous bytes are backed up.
Storage restoration translates original backup paths through the layout map,
rather than recreating obsolete result directories. Shared artifacts still
require atomic replacement instead of in-place edits.

The [migration ledger](../../../../../../history/bounding-boxes-reorganization-v1/plan.md)
and the adjacent move manifest record old paths, new paths, SHA256 and physical
file identities. Exact editable source/document bytes are preserved in the
independent before ZIP. No result data tree was copied during migration.

The separate feedback application and its own tests were subsequently retired
by user request. Their historical test receipts remain evidence of the earlier
implementation, while original feedback results and analytical snapshots remain.

## Comparative viewer retirement

The comparative viewer UI/server, its tests and local browser cache were later
removed by explicit user request. Earlier browser/HTTP verification is historical.
Only its page indexes, backgrounds, observations and analytical images remain;
see [preserved comparison data](viewer.md). The CLI has no serve/build-viewer
commands. Automatic remote completion no longer renders/builds a UI.
