# Shared local artifact storage

The local deduplication migration keeps result paths and file bytes unchanged.
Identical PNG/JPEG files and `viewer.json` indexes are interned by SHA256 under
`runtime/artifact-cache/objects/`. Their original paths become hardlinks to that
content: filesystem references, not independently stored copies. Distinct bytes
remain distinct even if filenames or PDF identities coincide.

Directory listings still show the original filenames and logical sizes. Count
unique `(device, file ID)` identities to measure storage, rather than adding
every path's size. Hardlinks require a filesystem that supports them and paths
on the same volume. Unsupported linking fails explicitly; it does not silently
copy data or change permissions.

## Existing consumers

The viewer, feedback API and analysis readers use the current paths. Historical
inventories and manifests retain their original provenance paths; `.layout.json`
translates legacy references without copying old directory trees. PDF SHA256, zero-based page index,
regions, detection IDs and human preferences are unchanged. Backgrounds are
local viewing assets; a reference to the PDF does not replace an annotated
example or analytical chart.

`build_viewer` now shares backgrounds and preserves the exact bytes of its
source index. JSON writes already use atomic replacement. Rendering now writes
to a new temporary file and atomically replaces its destination, so it cannot
write through a shared reference into another attempt. This migration itself
does not render PDFs or execute any scientific stages.

**Do not edit shared artifacts in place.** Hardlinks share writes. Use a new
file followed by atomic replacement, or produce a new output directory.
Arbitrary external editors and parser exporters are not made copy-on-write by
this tool. Original result bundles remain preserved.

## Inspect, apply, verify and recover

From `test_libs/bounding_boxes`, using the existing Python:

```powershell
python -B run.py storage inspect --root .
python -B run.py storage verify --root .
```

Inspection only reads candidate result assets. `apply` is a separate authorized
mutation and requires a new independent backup path. Before replacing any
artifact path, it writes a ZIP with one copy of each unique original content
and a manifest mapping all original paths to hashes, then rereads and verifies
the backup. The journal records `prepared` before replacements and `verified`
only after all alias hashes and physical identities pass.

The backup and migration records for this delivery live outside the experiment
at `history/bounding-boxes-storage-v1/` in the project root. The independent
backup consumes space and is accounted for separately from active storage saved.

For an explicitly authorized future migration/recovery, the command forms are:

```powershell
python -B run.py storage apply --root . --backup PATH_TO_NEW_BACKUP.zip
python -B run.py storage restore --root . --backup PATH_TO_EXISTING_BACKUP.zip
```

Restore prevalidates backup entries and all existing target bytes, refusing to
overwrite later edits. It reconstructs independent original files, records
recovery of the matching transaction and permits a new migration. An incomplete
transaction must be recovered before retrying. Corrupt cache objects are errors,
including when no new duplicate groups are found. Cache and backup deletion are
not automatic.

## Document references

[PDF reference catalog](../reference/pdf-sources.json) supplements the original
frozen inventory without rewriting it. It records the local PDF path, exact
SHA256, page count and page/region conventions. DOI URLs extracted from existing
first-page parser outputs are explicitly marked as candidates; they are not
verified source URLs. Missing verified URLs remain null rather than fabricated.
Existing region references retain their original coordinates and scope.

## Feedback retirement

The separate feedback API/application and its tests were subsequently removed
by user request. Earlier HTTP verification refers to the implementation at the
time of the storage/layout migrations. Preference results and analytical
snapshots remain preserved; this is not an available feedback service now.

## Comparative viewer retirement

The comparative viewer UI/server, its tests and local browser cache were later
removed by explicit user request. Earlier browser/HTTP verification is historical.
Only its page indexes, backgrounds, observations and analytical images remain;
see [preserved comparison data](viewer.md). The CLI has no serve/build-viewer
commands. Automatic remote completion no longer renders/builds a UI.
