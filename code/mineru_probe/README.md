# MinerU Basic: single-page trial in Colab T4

Approved configuration: MinerU4.0.12, Basic, backendTorch, CUDA/T4; no VLM.
Python3.11.16, Torch2.7.1+cu126, torchvision0.22.1+cu126, Transformers5.10.1,
DocVortex0.6.0. requirements.lock pins135 packages and hashes for Linux x86_64.
Resolution and binary availability checked, except jieba0.42.1 (pure Python,
sdist explicitly allowed). No GPU installation/inference has yet been established.

## Run only on an existing authorized session

From the root in WSL:

```bash
bash code/mineru_probe/test_page.sh NOMBRE_SESION
```

Does not create or close sessions. Do not run twice in the same VM with these paths:
the lock and existing files prevent overwriting evidence. A CLI timeout does not
prove the process has ended; check before any retry.
The script prints status/balance near execution, not to recover context.

Only the verified original PNG of12.pdf,page3 and this trial's code/lock/
manifest are uploaded. Package `code/packages/mineru-page.zip`. MinerU internally converts the
PNG to PDF and may resize it for its models; we record that
transformation and return normalized boxes to the original1654×2205 frame.
No native text from the source PDF or regions from previous models are used.

Environment `/content/mineru-probe/env`, separate from the kernel and LayoutLMv3/TATR.
Bundle `opendatalab/MinerU-4_models_torch`, pinned revision
`2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`:12files,894881298bytes.
Each download is verified using size and Git/LFS digest from the pinned manifest,
and a SHA256 receipt is preserved. Already verified models are activated through
the official MinerU workflow with a local provider instead of downloading from main:
SHA256 values are revalidated, then the official workflow checks paths and marks completeness.
This adapter explicitly depends on code4.0.12; do not update it without review.

Layout/OCR/formulas use the requested Torch backend on CUDA. Table ONNX models
explicitly remain on CPU: do not claim that the whole pipeline uses
GPU. Initial checks validate T4/versions/backend/configuration; the complete
real runtime is established only after execution. The mandatory
mineru-llama-cpp dependency is installed by the package, but Basic does not load or download a VLM.
Auxiliary LLM functions are disabled and no API keys are required.

## Outputs and recovery

Local results `code/results/mineru-page/<fecha>/` with ZIP, sidecar and CLI log.
The ZIP includes configuration, input-manifest, lock/freeze, weight manifest and
download receipt, status/log even if installation or parsing fails.
Inside `page/`:

- `middle-native.json` and `model-native.json` (if available): saved before
  materializing images/Markdown, with the unreduced native contract.
- `native/`: official export of resources, MiddleJson, ModelJson and Markdown.
- `regions.json`: native labels, indices, JSON pointers and parent/child relationship;
  normalized bbox and XYXY in the original PNG. Score null if absent.
- `overlay.png` and `crops/`: review derivatives, without padding. Green for parents,
  blue for children. Parent and body may share exactly the same box:
  do not count them as independent detections.
- `run-manifest.json`, `page-status.json`, `error.log` on failure.

Missing boxes are recorded with bbox null and geometry_warnings, without inventing them.
A derivative failure allows local reexport from middle-native.json and
the original PNG, without loading models again. Preserve the original remote status.
Recover/verify the ZIP before stopping only your own session.

## Local verification

```bash
python3 -m unittest discover -s code/mineru_probe -p 'test_*.py' -v
bash -n code/mineru_probe/test_page.sh
```

Fixture/test-double tests: actual geometry and hierarchy of contract0.6.0,
JSON types, fixed input, native preservation on failure, package safety,
download integrity and evidence protection. These do not test real loading/inference.
Do not repeat them when starting another chat; consult `code/results/mineru-local-checks/`.

Visually compare heading3.1, paragraphs/list, captions, two figures, equation,
header/page and tables. No CER/WER, LaTeX accuracy, fusion or quality percentage.
