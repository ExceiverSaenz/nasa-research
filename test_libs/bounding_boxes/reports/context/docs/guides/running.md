# Running existing commands

Purpose: document the existing CLI without initiating work. Run examples from the repository root with the existing Python. Consult [current status](../overview/current-status.md) before deciding whether any new operation is needed. Source: [run.py](../../../../code/run.py), the [decision record](../decisions/decision-record.md) and [implementation plan](../../../../../../history/bounding-boxes-cleanup-20261101T050218/preserved/docs/history/implementation-plan.md).

## Inspection and planning

```powershell
python -B test_libs/bounding_boxes/code/run.py --help
python -B test_libs/bounding_boxes/code/run.py inspect
python -B test_libs/bounding_boxes/code/run.py colab plan --attempt test_libs/bounding_boxes/runtime/attempt-future
```

`inspect` writes `runtime/local-preflight.json` by default (`--output` changes it); it does not install packages or allocate a session. Exit code 2 can indicate `NOT_RUN`, not overall success. Supplying `--r2-config PRIVATE_PATH` adds network HEAD/GET/hash probes. Existing credentials remain local; do not copy permanent keys into Colab. `colab plan` prints the proposed sequence with `session_will_start=false`; it creates no session and runs no inference.

## Local environment preparation

`prepare --environment a|b --python BASE_PYTHON --target NEW_ENV` checks the target. Installation requires explicit `--apply`; the CLI retains incompatible environments rather than patching them. A newly installed target requires reinspection. Environment candidates are [requirements inputs](../../../../code/config/requirements); use resolved lock identities and receipts, not a Windows environment copied to Linux. This action is separate from an inspection request.

## Remote phases require explicit authorization

These are command shapes for a separately authorized future operation, not instructions to resume a historical attempt:

```bash
python3 -B test_libs/bounding_boxes/code/run.py colab prepare --attempt test_libs/bounding_boxes/runtime/NEW_ATTEMPT --r2-config PRIVATE_PATH --allow-session
python3 -B test_libs/bounding_boxes/code/run.py colab smoke --attempt test_libs/bounding_boxes/runtime/NEW_ATTEMPT --r2-config PRIVATE_PATH --allow-inference
python3 -B test_libs/bounding_boxes/code/run.py colab execute --attempt test_libs/bounding_boxes/runtime/NEW_ATTEMPT --r2-config PRIVATE_PATH --allow-inference
```

The CLI requires WSL/Linux and the existing authenticated Colab CLI for these phases. Preparation can allocate a session, prepare environments and fetch missing verified artifacts. Smoke and execute run models. Required flags are authorization gates, not evidence that dependencies, GPU suitability or prior phases succeeded. Read attempt receipts, hashes, smoke results and phase state before continuing. Uncertain status requires `manual_review`; there is no automatic new session or retry. Historical closure receipts do not authorize remote operations now.

## Existing results and offline tools

`aggregate ATTEMPT --inventory INVENTORY --run-id ID` writes an aggregate; adding `--pdf-dir` enables rendering verified PDFs. The interactive viewer and its `build-viewer`/`serve` commands were retired. Aggregation produces data only; completed remote phases no longer automatically render/build a UI. See [preserved comparison data](viewer.md). Explicit aggregation/rendering still mutates outputs and requires a new destination.

Offline analysis is documented with each module: [automatic](../../../../analytics/automatic/README.md), [geometry](../../../../analytics/geometry/README.md) and [targets](../../../../analytics/targets/README.md). Generated outputs need a new destination and preserved inputs. Some target scripts and narrative generators are specific to this delivery; do not rerun them over existing evidence or treat their narratives as generic conclusions. Consult protocols and execution records from the [catalog](../INDEX.md#source-modules-and-execution-records). Examples describe the available entry points; the migration verification record identifies the offline checks actually performed.
