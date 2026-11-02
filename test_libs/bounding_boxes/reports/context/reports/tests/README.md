# Test evidence

## Functional-layout migration

| Suite | Passed | Skipped | Failed/errors | Machine evidence |
| --- | ---: | ---: | ---: | --- |
| Application code | 89 | 9 | 0 | [JUnit](../../../../raw_results/tests/code/migration-v2/junit.xml) |
| Analytical code | 36 | 0 | 0 | [JUnit](../../../../raw_results/tests/analytics/migration-v2/junit.xml) |
| Feedback coordinates (Node) | 3 | 0 | 0 | [Observed result](../../../../raw_results/tests/code/migration-v2/node-summary.json) |

The six layout controls were rechecked after adding flat-bundle execution and
legacy-backup restoration assertions; all six passed. [Recheck JUnit](../../../../raw_results/tests/code/migration-v2/layout-recheck.xml). These are the same six cases, not six additional distinct tests.

The nine skipped cases are the existing optional browser/native ABI checks.
They were not activated by this organization task. Fixture servers were only
loopback compatibility checks. No remote inference, PDF rendering or scientific
analysis was run to regenerate preserved results. Passing calculations/contracts
does not establish semantic accuracy of the extracted collection.

## Preserved earlier evidence

- [Historical browser JUnit](../../../../raw_results/tests/code/history/tests-with-browser.xml): 59 cases, no failures/errors/skips, timestamp 2026-10-31T19:08:20.599943-06:00. It is historical, not this migration's run.
- [Earlier shared-storage verification](../../../../../../history/bounding-boxes-storage-v1/README.md): 69 focused tests were summarized there; a full per-case JUnit was not captured at that time.
- [Feedback implementation ledger](feedback-app-v1.md), with preserved fixtures/screenshots under [test results](../../../../raw_results/tests/code/feedback-app-v1).

Source tests live in `tests/code/` and `tests/analytics/`. Persisted fixtures,
logs and machine reports live under `raw_results/tests/`; they are not scientific
reference labels or human review of the collection.

## Later feedback retirement

The standalone feedback application and its own tests were removed by explicit
user request after the runs above. Those test receipts remain historical
evidence and do not describe the current set of available tests or a running
feedback application. Human preferences and analytical snapshots are preserved.

## Later comparative viewer retirement

The comparative viewer UI, browser tests and their demo were subsequently
retired. The remaining suites passed 113 tests, with 6 optional native ABI
cases skipped. [Retirement JUnit](../../../../raw_results/tests/code/viewer-retirement/junit.xml). Earlier browser/Node/HTTP receipts are retained historical results, not available applications or the current test inventory.
