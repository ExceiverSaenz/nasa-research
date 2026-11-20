# Preserved comparison data; interactive viewer retired

The comparative viewer UI, server, prepared HTML/JavaScript/CSS copies, its own
tests, demo fixtures and the project-local Playwright browser dependency cache
were removed by explicit user request. The CLI no longer offers `serve` or
`build-viewer`, and future completed runs no longer render/build that UI
automatically.

The folders historically named `viewer/` and `viewer_source/` retain data only:
page/detection indexes (`viewer.json`), page backgrounds, original observations
(`reviews.json`) and supporting evidence. The analytical programs still use
these inputs; their exact bytes and scientific provenance are preserved.

- [Corrected collection index](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/viewer.json)
- [Corrected collection observations](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/viewer/reviews.json)
- [Historical collection index](../../../../raw_results/code/collection-20261101T015723Z/viewer_source/viewer.json)
- [Smoke index](../../../../raw_results/code/smoke-20261101T011229Z/viewer_source/viewer.json)

Graphs, annotated images and report examples are retained as analytical results.
Their source images are not interchangeable with UI code. Prior browser/HTTP
receipts describe historical checks, not a currently available viewer. Shared
background/index data still uses the [storage contract](storage.md).

Retired files and prior editable source/docs are independently backed up outside
the experiment under `history/viewer-retirement-20261102T003503Z/`.
