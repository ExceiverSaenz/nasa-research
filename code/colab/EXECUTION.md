# Single Colab CLI execution workflow

This is the common operational entry point for any remote run. The guides
in `code/colab/`, `code/document_trial/` and `code/page_integration/` describe
specific trials, but do not replace this state control.

## Before running

1. Consult `AGENTS.md`, `docs/continuidad/session-handoff.md` and the
   canonical state.
2. Consult [`analytics/config/remote_runs.json`](../../analytics/config/remote_runs.json).
3. Confirm that no other run with the same scope remains unresolved in `running`,
   `timeout_manual_review` or `backup_verified`.
4. Identify the package, version, configuration, weights, document, pages and
   authorized session.
5. Create a record with status `prepared` using the template in this folder.

## Controlled workflow

```text
prepared
  → uploaded
  → running
  → backup_verified
  → accepted / failed / timeout_manual_review
  → closed
```

Each transition must preserve the command, terminal output, run ID, ZIP,
sidecar, SHA/CRC and decision. A client timeout does not prove that the remote
process ended; use `timeout_manual_review` and do not retry automatically.

## Closure criteria

Mark `backup_verified` only when the downloaded backup, its hash/CRC,
manifest and package identity match. Mark `accepted` only
after the authorized baseline comparison. Mark `closed` only when
the session and record have confirmed status.

## Do not repeat

- Do not repeat preflight, upload or download for an already backed-up run.
- Do not create another session to recover context.
- Do not change the package, configuration, weights or hardware within the same run.
- Do not close a potentially active process after a timeout without confirmation.
- Do not execute this workflow merely to read documentation.
