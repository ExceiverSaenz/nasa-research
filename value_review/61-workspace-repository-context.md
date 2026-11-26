# Repository Context · Workspace

**Reference** · [60-workspace-specification.md](60-workspace-specification.md)

## Entry point and relevant files

| Path or symbol | What to review |
|---|---|
| `service/workspace.py` | Scan, ids, `source.json` records, loading, `GET /workspace`, `POST /workspace/scan` |
| `service/app.py` `find_pair`, `find_source`, `Source`, `ctx`, `ingest_lock` | Workspace runs served like folder pairs; one load at a time |
| `config.py` `default_workspace`, `service/config.py` `Config.workspace`, `__main__.py` `--workspace` | The root at startup |
| `ingest/` `find_papers`, `ingest_run` | Reused as they are |
| `frontend/src/lib/reviewView.js` `sourceList`, `data/review.js`, `components/ReviewRuns.jsx` | Review lists pairs and runs, loading on open |
| `frontend/src/components/WorkspaceTab.jsx` | Settings › Workspace |
| `compose.yaml`, `Dockerfile`, `.env.example`, `docker_check.py` | `REVIEW_WORKSPACE`, mounted read only |
| `tests/test_workspace.py`, `tests/e2e_server.py` `--with-workspace`, `frontend/e2e/workspace.spec.js` | Tests |

## Conventions and constraints

- [02-repository-context.md](02-repository-context.md): atomic writes, `python -B`, the build is committed.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s value_review/tests -p "test_*.py"` (repository root) | Scan, ids, loading, reviewing a run, problems, nothing written in the workspace |
| `npm test`, `npm run build`, `npm run e2e` (in `value_review/frontend`) | The list of extractions and Settings, with and without a workspace |
| `docker compose -f value_review/compose.yaml config` with and without `REVIEW_WORKSPACE` | The mount and the environment |
