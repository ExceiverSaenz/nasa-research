# Real A100 bounding box smoke test

Data, tables and original assets: [data directory](../../../../../raw_results/code/smoke-20261101T011229Z). Artifact filenames in the report refer to that directory.


The smoke test completed successfully with all four tools on **the first page of 1.pdf**. **A single 40 GB NVIDIA A100-SXM4 session** was used, with two isolated environments and sequential execution. The session was closed after downloading and verifying the results, in accordance with the user's choice. **The collection was not run.**

Attempt: `smoke-20261101T011229Z`. Session: `bbx-8456b0df1ca4487f9df41dc433ab3544`. Identifiers and records use UTC; the test corresponds to October 31, 2026 in the user's time zone.

## Checks performed

| Check | Result |
| --- | --- |
| Sessions created | One; a single actual creation record |
| Environment A | Isolation, lock, pip check and imports passed |
| Environment B | Isolation, lock, pip check, imports and vLLM passed |
| CUDA A | Torch 2.7.1+cu126, CUDA 12.6; matmul and torchvision NMS on GPU correct |
| CUDA B | Torch 2.10.0+cu128, CUDA 12.8; matmul and torchvision NMS on GPU correct |
| vLLM | 0.19.1; effective engine vllm, weight loading on CUDA and FlashAttention established by the Standard log |
| Local R2 | Successful HEAD for all 15 PDFs and GET/hash of 12.pdf as preflight |
| R2 from Colab | GET of 1.pdf; size and SHA256 match the local inventory |
| Outputs | Four tools, one page per tool; original files, projections and receipts retained |
| Download | ZIP of 4,829,399 bytes; 49 files and manifest verified |
| Closure | Confirmed; subsequent Colab query with no active sessions |

R2 source: `1.pdf`, 50,705,515 bytes, SHA256 `a56254c77fd86f0a4045c7eb14aea84595e931794100dcc0895eb7e346908c80`. A one-page PDF was derived for each worker; the other pages and papers were not processed in the smoke test. Permanent keys remained in WSL and temporary requests were not included in the results archive.

## Configurations and reuse

- A: Torch 2.7.1+cu126, torchvision 0.22.1+cu126, Transformers 5.10.1, MinerU 4.0.12. Ran Heron, Heron-101 and Basic.
- B: Torch 2.10.0, torchvision 0.25.0, Transformers 5.10.1, MinerU 4.0.12, vLLM 0.19.1. Ran Standard.
- Hashed locks and the jieba wheel retained from a100-v2 were reused, verified before transfer. The venvs and snapshots were absent on the new VM and were prepared before use; environments were reinspected after installation.
- Manifests pin revisions and hashes of both Heron variants, the small MinerU models and the VLM. Models, engines and thresholds were not changed to obtain a favorable result.

## Results and observed resources

| Tool | Status | Recorded time | Sampled device peak GPU |
| --- | --- | --- | --- |
| Heron | PASS, one page | Load 0.79 s; inference 1.34 s | 866 MiB |
| Heron-101 | PASS, one page | Load 1.00 s; inference 0.60 s | 954 MiB |
| MinerU Basic | PASS, one page | Parsing 8.06 s | 986 MiB |
| MinerU Standard | PASS, one page | Parsing 86.76 s | 7,015 MiB |

These times **are not directly equivalent**: Heron reports detector inference; MinerU reports parsing, including internal initialization, without a complete breakdown of loading and inference. Standard initialized and compiled its vLLM engine; the log records 19.73 s of torch.compile. Environment preparation, weight download and transport are kept separate from these values.

Memory was sampled every second and is device memory, not exclusive attribution or a guaranteed continuous peak. Process-tree RAM and all samples are in the receipts. This page does not allow choosing a winning tool, establishing 6 GB capability or validating the entire collection.

## Retained evidence

- [Final status](../../../../../raw_results/code/smoke-20261101T011229Z/final-status.json): closure, scope and final checks.
- [Verification and summary](../../../../../raw_results/code/smoke-20261101T011229Z/verification.json): hashes, hardware and vLLM engine evidence.
- [Complete package](../../../../../raw_results/code/smoke-20261101T011229Z/smoke-results.zip): 49 files with manifest.
- [Remote summary](../../../../../raw_results/code/smoke-20261101T011229Z/download/runtime/smoke-summary.json).
- [Installed environments](../../../../../raw_results/code/smoke-20261101T011229Z/download/runtime/environment-receipt.json).
- [Standard log](../../../../../raw_results/code/smoke-20261101T011229Z/download/results/smoke/standard.log): V1 LLM engine 0.19.1 initialization, CUDA, weights, BF16 and FlashAttention.
- [Heron output](../../../../../raw_results/code/smoke-20261101T011229Z/download/results/smoke/heron/receipt.json), [Heron-101](../../../../../raw_results/code/smoke-20261101T011229Z/download/results/smoke/heron101/receipt.json), [Basic](../../../../../raw_results/code/smoke-20261101T011229Z/download/results/smoke/basic/receipt.json) and [Standard](../../../../../raw_results/code/smoke-20261101T011229Z/download/results/smoke/standard/receipt.json).
- Code snapshot, transfer logs and controller status: `../../runtime/attempts/smoke-20261101T011229Z/`.

ZIP SHA256: `206d284ae767646c291c2b7f625cd69a925a660ac420a1a02b834ef30ca20d5b`.

## Incidents and limits

The first local check did not find Colab CLI in the WSL process PATH without a login shell; it failed before allocating resources. The same attempt was continued with the absolute path of the existing CLI. No other session was created and the CLI was not reinstalled.

A CUDA probe sent during preparation exhausted the client's wait. It was not interpreted as GPU failure or cancellation of remote work. Afterwards A's result was reused and B was verified; both probes passed. Inference of the four models was not repeated because of this incident.

The smoke test establishes technical operation on this page and in these environments. It does not establish box or label accuracy, panel separation, caption relationships, semantic quality or generalization. Visual review and evaluation of all pages remain pending; they were neither authorized nor run here.

Subsequent local-only update: an [agent visual review of this page](visual-review/report.md) was completed, with annotated images and 15 traceable observations. Human validation and evaluation of the remaining pages remain pending. This review did not run inference, another A100 or the collection.

