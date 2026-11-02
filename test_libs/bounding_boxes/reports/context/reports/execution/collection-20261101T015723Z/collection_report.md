# SiC collection: execution of all four tools

Data, tables and original assets: [data directory](../../../../../raw_results/code/collection-20261101T015723Z). Artifact filenames in the report refer to that directory.


**All 15 PDFs and their 397 pages were attempted with all four tools** on a single A100, with two isolated environments and sequential execution. **The result of both MinerU variants is incomplete:** each completed 4 papers and failed on 11. Heron and Heron-101 completed all 15. The A100 was closed after downloading and verifying the outputs; the subsequent Colab query confirmed that no active sessions remain.

Attempt: `collection-20261101T015723Z`. Session: `bbx-7000c89813c1406c937e8a396496c281`. IDs use UTC; execution started on October 31, 2026 in the user's time zone. It does not replace the historical artifact or mix its results with the previous smoke test.

## Actual coverage

| Tool | Papers attempted | Papers completed | Pages with complete parsing | Failed papers | Boxes on completed pages |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heron | 15 | 15 | 397 / 397 | 0 | 4889 |
| Heron-101 | 15 | 15 | 397 / 397 | 0 | 4777 |
| MinerU Basic | 15 | 4 | 60 / 397 | 11 | 881 |
| MinerU Standard | 15 | 4 | 60 / 397 | 11 | 880 |

**60 pages allow comparing all four complete outputs:** papers `1.pdf`, `3.pdf`, `4.pdf` and `6.pdf`. On the other **337 pages**, both Heron variants have complete output, but both MinerU variants failed for their paper. This adds up to 914 complete page/tool results out of 1,588 expected. The remaining 674 slots correspond to failures; they are not valid empty detections.

Box counts have different coverage and are not a quality measure. Basic's 980 rows without bbox and Standard's 1,177 are retained as unknown geometry; they do not receive their parents' boxes or count as omissions.

## Observed MinerU failure

Both MinerU variants failed on the same 11 papers: `2.pdf`, `5.pdf`, `7.pdf`, `8.pdf`, `9.pdf`, `10.pdf`, `11.pdf`, `12.pdf`, `14.pdf`, `15.pdf` and `17.pdf`. Their tracebacks end in native text extraction, the `owner.prepare_span_texts` call, with:

```text
TypeError: argument 'private_ranges': 'int' object is not an instance of 'tuple'
```

The individual continuation errors and Basic's original log for `10.pdf` were verified. The error occurs inside MinerU; the underlying cause of the argument incompatibility remains pending diagnosis. It is not presented as a CUDA failure or poor box delineation. Versions were not updated, packages were not patched, models or parameters were not changed, and alternative engines were not enabled to obtain favorable results.

## Continuity and a single pass per paper

The original sequence completed both Heron variants and Basic's `1.pdf`; the worker stopped when Basic failed on `10.pdf`. After reviewing the traceback and preserving the state, execution continued on the same A100 with the **13 papers not yet attempted by Basic and all 15 for Standard**. Each subsequent failure was recorded and execution moved to the next independent paper. Completed or failed papers were not repeated.

Original outputs are in `download/results/execute`; subsequent outputs in `download/results/continuation-v1`. `download/results/assembled-v1` brings together verified copies to build the viewer; it contains no new inference. Assembled receipts preserve the original resource segments. Basic is divided into two execution processes because of the initial failure, so it must not be treated as a continuous stage when comparing costs.

Before environment preparation there was a wait by the local Colab client without the kernel receiving the phase. History and the absence of installations were checked, only that client was terminated and preparation continued in the same session. The failed state, decision and subsequent explicit confirmation were retained; a second A100 was not allocated.

## Preparation and checks

- Local inventory: 15 PDFs, 397 pages and 109,402,087 bytes; identities identical to those of the previous smoke test. R2: HEAD for all 15 and test GET/hash; on the VM, PDFs were downloaded or reused only after checking their identities. Local originals served for identity and rendering, not as a replacement for R2.
- Local tests: 57 passed and 3 skipped. Hashed locks, candidate and manifests checked; compatible wheels reused. Both environments were inspected before installation and afterwards passed isolation, lock, pip check and imports.
- A: Torch 2.7.1+cu126, torchvision 0.22.1+cu126, Transformers 5.10.1 and MinerU 4.0.12. B: Torch 2.10.0+cu128, torchvision 0.25.0, Transformers 5.10.1, MinerU 4.0.12 and vLLM 0.19.1.
- Real CUDA operations: matmul and torchvision NMS passed in both environments on NVIDIA A100-SXM4-40GB. B selected local vLLM; its log records loading V1 LLM engine 0.19.1 on CUDA and FlashAttention 2.
- Smoke test of the new session completed with all four tools before the collection. Its one-page technical success did not prevent the subsequent native text failure.
- ZIP of 65,383,460 bytes and 2415 files, plus manifest: SHA256 and per-file hashes/sizes verified. SHA256: `bfc617688f642ab4829478b7ced5961f18b3d306925eea6042bcc0c11d98b6a7`.
- Native coverage and file hashes for each completed paper, continuation worker identities, configuration, locks and local PDFs for the viewer were verified. Failures remain explicit.

## Resources and comparison limits

| Tool | Sampled device peak GPU (MiB) | Resource segments |
| --- | ---: | ---: |
| Heron | 920 | 1 |
| Heron-101 | 1054 | 1 |
| MinerU Basic | 2796 | 2 |
| MinerU Standard | 12473 | 1 |

Receipts retain per-paper/page timings, RAM and GPU samples. [metrics.json](../../../../../raw_results/code/collection-20261101T015723Z/metrics.json) exposes the summary and all 60 tool/paper attempts. Heron measures detector inference; MinerU reports parsing without fully isolating loading and inference. Their published time sums include only successful papers and have different coverage. Unexposed failure times remain unknown, not zero. No speed ranking is calculated from those totals. GPU memory is device memory and was sampled every second; it is not memory attributed exclusively to each model or a guaranteed continuous peak. Process-tree RSS may count shared memory more than once.

## Viewer and evidence

- [preserved data index; UI retired](../../../../../raw_results/code/collection-20261101T015723Z/viewer/viewer.json), served through HTTP by the existing command. Presents all 397 pages and retains `tool_status` per page/tool; a warning lists the failed MinerU papers.
- [preserved data index; UI retired](../../../../../raw_results/code/collection-20261101T015723Z/viewer/viewer.json): distinguishes completion from failure before interpreting layers without boxes.
- [Download verification](../../../../../raw_results/code/collection-20261101T015723Z/verification.json), [viewer verification](../../../../../raw_results/code/collection-20261101T015723Z/viewer-verification.json), [remote summary](../../../../../raw_results/code/collection-20261101T015723Z/remote-summary.json) and [original package](../../../../../raw_results/code/collection-20261101T015723Z/collection-results.zip).
- [Heron receipt](../../../../../raw_results/code/collection-20261101T015723Z/download/results/assembled-v1/heron/receipt.json), [Heron-101](../../../../../raw_results/code/collection-20261101T015723Z/download/results/assembled-v1/heron101/receipt.json), [Basic](../../../../../raw_results/code/collection-20261101T015723Z/download/results/assembled-v1/basic/receipt.json) and [Standard](../../../../../raw_results/code/collection-20261101T015723Z/download/results/assembled-v1/standard/receipt.json).
- [Original Basic failure](../../../../../raw_results/code/collection-20261101T015723Z/download/results/execute/basic.log), [errors and outputs of its continuation](../../../../../raw_results/code/collection-20261101T015723Z/download/results/continuation-v1/basic), [Standard errors and outputs](../../../../../raw_results/code/collection-20261101T015723Z/download/results/continuation-v1/standard).
- [Controller status and reviewed continuations](../../../../../raw_results/provenance/attempts/collection-20261101T015723Z/workflow.json).

The viewer preserves original boxes and labels. Its 397 backgrounds are generated locally with PDFium at 200 DPI from PDFs whose identity was verified. Downloaded scientific results remain intact. No smoke test reviews were imported or human marks added.

**Pending:** diagnose and resolve the MinerU native text failure in a separate increment if that is decided; visual and human review of the collection; evaluation of panels, identifiers and caption relationships on pages with usable outputs; validation with an independent reference. Technically completing both Heron variants does not demonstrate accuracy, hierarchy or semantic quality. This delivery does not establish that all four tools correctly parsed the entire collection.

