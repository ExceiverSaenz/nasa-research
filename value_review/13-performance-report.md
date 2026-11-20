# Performance Report · Tensile Value Review (2026-11-19)

> Where the tool spends CPU, memory and time, where it is slow or not smooth, and what to change. Measured, not assumed.
> **Status: all four fixes approved and applied (2026-11-19); before and after numbers in *Results after the fixes*.**

**Reference** · plan of the resource study (B1–B4); budgets in B2; tools: `value_review/perf/server_bench.py`,
`perf/stress_data.py`, `npm run perf` (`frontend/perf/`), Chrome DevTools Protocol CPU profiles.

## Environment and method

- **Machine** · this laptop: 12 logical CPUs, 31.6 GB RAM, Windows 11, Python 3.13.5, Microsoft Edge (Playwright 1.65.1).
- **Profiles** · *laptop* (1440×900, CPU as is) and *slow tablet* (834×1112, touch, browser CPU slowed 4× with
  `Emulation.setCPUThrottlingRate`), as decided.
- **Data** · a temporary copy of the real run `gpt-6.1-sol-low-pdf-only` (14 papers, 2,581 values; the largest is paper 10:
  414 values, 67 records, 14 pages) served by the real launcher; plus a synthetic stress set (see *Scale*). The user's data
  and the instance on port 8766 were not touched.
- **Server** · HTTP over a kept-alive connection (the full server stack), ≥ 30 runs per operation (p50, p95, max); CPU and
  memory of the server process sampled every 50 ms (`psutil`); `cProfile` and `tracemalloc` in process.
- **Browser** · Event Timing (key or tap → next paint), long tasks, layout shifts (CLS), frame times, CDP metrics (CPU time,
  layout, JS heap after GC, DOM nodes), network bytes; the page image's `src` changes and loads are logged to detect blank
  frames; a CDP CPU profile of 40 decisions on an unminified build to name the functions.

## Summary

| | Laptop | Slow tablet |
|---|---|---|
| Open the largest paper | **0.8 s**, no long task, CLS 0 | **3.7 s**, 10 long tasks (longest 551 ms), one **909 ms frozen frame**, CLS 0.012 |
| Decide a value (key or tap → paint) | p95 **32 ms**, max 64 ms, no long task | p95 **224 ms**, max **1.2 s**, 211 long tasks (longest 803 ms), 9 % of frames > 33 ms |
| Change page (cached / first visit) | 5 ms / 15–100 ms, **no blank frame** | 10–67 ms / 72–800 ms, no blank frame |
| Zoom | 100–110 ms (new image width) | 330–400 ms |
| Scroll values and page | smooth (worst frame 8 ms) | not measured (wheel ≠ touch) |
| JS heap after GC; growth over 10 papers | 3–11 MB; none (2.7 → 3.7 MB) | 3–8 MB; none |
| Server: Papers list (no versions / after 10 versions) | 50 ms / **580 ms** | (same server) |
| Server: version history | p50 **1.7 s**, p95 **5.2 s** | |
| Server: submit / save draft | 1.2–1.9 s / 0.37–0.47 s | |
| Server: load papers again | 2.9–4.4 s | |
| Server memory and CPU | RSS 56 MB idle, ≤ 139 MB peak, no growth over 1,000 requests; ≤ 1 core | |

**Verdict.** On this laptop the screens are smooth and within budget. The two real problems are (1) **the review screen is
CPU-heavy**: on a modest tablet it freezes for up to a second on opening and stutters while deciding, and (2) **the server
re-validates every stored version on every read**, which makes the version history, the Papers list (once versions exist),
submit, draft saves and exports slow, and gets worse with every version.

## Budgets (B2)

| Budget | Laptop | Slow tablet |
|---|---|---|
| Key or tap → paint p95 ≤ 100 / 200 ms | ✅ 32 ms | ❌ 224 ms (max 1.2 s) |
| No long task > 200 ms; ≤ 1 per 10 actions > 50 ms | ✅ none | ❌ 211 in 150 actions, up to 803 ms |
| Open largest paper ≤ 1.0 / 2.0 s | ✅ 0.8 s | ❌ 3.7 s |
| Page change (cached) ≤ 150 ms, no blank frame | ✅ 5 ms, none | ✅ ≤ 67 ms, none |
| CLS ≤ 0.05 | ✅ 0 | ✅ 0.012 |
| API Papers list / open paper p95 ≤ 150 ms | ❌ 713 ms after versions (91 ms before) / ❌ 224 ms | |
| Page image cached ≤ 30 ms; cold 1200 px ≤ 800 ms | ⚠️ p50 26 ms, p95 46 ms / ✅ p95 279 ms | |
| JS heap ≤ 100 MB, no growth | ✅ | ✅ |
| Server RSS ≤ 250 MB, no growth | ✅ ≤ 139 MB | |

## Hypotheses (B3): confirmed or rejected

| Hypothesis | Result |
|---|---|
| `signature(state)` on every render is costly | **Rejected**: 0.4 % of the decision profile |
| The page `<img>` swaps without preload → blank frame | **Rejected**: the element is never replaced (0 new `<img>`), the old page stays until the new one is drawn, CLS 0. First visits still wait 15–800 ms for the image (see B-4) |
| `/papers` reads and validates versions on every request | **Confirmed**, and it is the main server cost (B-2) |
| Settings read from disk several times per request | **Negligible**: the settings call takes 5 ms |
| One render lock serializes page images | **Confirmed**: 4 tabs × 5 cold pages take 5.5 s wall, p95 1.3 s per request |
| PNGs saved without compression | **Partly**: `optimize=True` saves nothing (438 vs 439 KB) and is slower; PNG encoding is **half** of a cold render |

## Bottlenecks, ranked by user impact, with proposed fixes

### B-1 · Review screen CPU on a modest tablet (freezes on open, stutter while deciding)

**Evidence** · slow tablet: open 3.7 s with a 909 ms frozen frame; decisions p95 224 ms, max 1.2 s, 211 long tasks. CPU
profile of 40 decisions (app code, inclusive): React re-rendering the whole review on every decision (~17 %), `browseRecords`
3.3 % (`lib/values.js`: for each of the 67 records it filters all 414 values, then filters again for the done count:
≈ 28,000 checks per decision, only to refresh the record picker's counts), `scrollToMain` 4.6 % (`PageViewer.jsx`: writes
`scrollTop` then reads `clientWidth`, forcing a synchronous layout of the page), `when` 1.3 % (`DetailPanel.jsx`: a new
`toLocaleString` formatter per call); the rest is browser layout and style of ~2,000 DOM nodes.

**Proposed fixes** (client only, no change to data or contract):
1. `browseRecords` / `browseFeatures`: one pass over the values that counts per record and column (linear instead of
   records × values).
2. Memoize the value rows (`React.memo` with stable callbacks) so a decision re-renders the changed row and the detail
   panel, not the whole list.
3. `scrollToMain`: read sizes first, then write; skip when the box is already in view.
4. One shared `Intl.DateTimeFormat` for `when`.

**Expected gain** · decisions on the slow tablet back under the 200 ms p95 budget and long tasks mostly gone; opening the
paper well under 2 s. **Risk** · low; each fix is covered by the existing unit and browser tests (decide, J/K, bulk accept,
moves), and the measurement is repeatable with `npm run perf`.

### B-2 · The server re-validates stored versions on every read

**Evidence** · cProfile: ~95 % of the time of Papers list, open paper, save draft and version history is `jsonschema`
validating version files (`storage/files.py` `_read` → `schemas.errors`). A version is a full snapshot (every value) and is
already validated when it is written, and it never changes. Times grow with the size and number of versions: Papers list
50 ms → 580 ms after 10 versions of one paper; version history 1.7 s p50, 5.2 s p95; submit 1.2–1.9 s; exports ~0.5 s;
save draft 0.37 s (autosave and closing the tab send it too).

**Proposed fix** · validate a version file once per process: cache the parsed, validated version by (path, size,
modification time), so a changed or new file is still validated; the version history reads only the header fields it lists.
Drafts keep being validated on write (they change), but `current()` uses the cache.

**Expected gain** · Papers list and open paper back to tens of ms; version history and exports under 100 ms; submit and
draft save roughly halved. **Risk** · low: same files, same checks on write; a file damaged on disk is still detected
because its size or time changes (test to add); covered by the existing version, draft, restore and export tests.

### B-3 · "Load papers again" rebuilds every original

**Evidence** · 2.9–4.4 s for 14 papers that are all already loaded and unchanged: each paper's result and PDF are hashed,
parsed and measured with pdfium before the build is compared with the stored original.

**Proposed fix** · skip a paper whose result and PDF have the same size and modification time as when its original was
built (remember them next to the originals); build only new or changed ones. **Expected gain** · well under 0.5 s when
nothing changed. **Risk** · low-medium: a source edited without changing size or time would be missed (rare; the source
hash check on open still flags it as *Source changed*).

### B-4 · Page images: first visits, zoom and parallel tabs

**Evidence** · cold render at 1200 px p50 185 ms (half of it PNG encoding, 487 KB per page), at 2400 px up to 1.1 s; first
visit of a page 15–100 ms on the laptop and 72–800 ms on the slow tablet; zoom fetches a new width (100–400 ms); one render
lock makes 4 tabs × 5 cold pages take 5.5 s.

**Proposed fixes** · (a) after the current page is drawn, preload the next and previous pages at the same width (cached
page changes take 5 ms); (b) encode PNG with a lower compression level (faster encode, somewhat larger files, still
lossless; to be measured before adopting). JPEG and WebP were measured but are **not** proposed: JPEG blurs small text and
WebP encodes 3× slower than PNG. **Expected gain** · page changes feel instant after the first page; cold renders ~30–40 %
faster. **Risk** · low; more server work in the background (bounded to two pages).

### Not a problem

Memory (server and browser), layout shifts, scrolling, the page change itself (no blank frames), the settings call and
`signature(state)`: all within budget, no action proposed.

## Results after the fixes

All four fixes (B-1 to B-4) were applied as proposed, with one refinement found by measuring: page preloading first
made zoom *slower*, because the service renders one page at a time and the zoomed page waited behind the preloads. The
preload now waits until the reviewer has stayed 400 ms on a page, asks only for the next page, and the service skips it
(`204`, nothing rendered) when it is busy or a reviewer's request is waiting (`prefetch=true`, `library.py`).

**Server, real data** (same benchmark, before → after, p50/p95 in ms):

| Operation | Before | After |
|---|---|---|
| Version history | 1,709 / 5,180 | **7 / 8** |
| Papers list after versions | 582 / 713 | **51 / 62** |
| Open the largest paper | 117 / 224 | **105 / 109** |
| Submit | 1,234 / 1,853 | **571 / 595** |
| Save draft | 374 / 466 | **96 / 106** |
| Export CSV / JSON / ZIP | 512 / 538 / 585 | **15 / 34 / 70** |
| Load papers again | 2,915 / 4,421 | **145 / 163** |
| Page image cached | 26 / 46 | **8 / 31** |
| Page image cold 1200 px | 185 / 279 | 184 / 250 (encode 22–42 % faster; render unchanged) |
| Whole benchmark | did not finish in 10 min | **1 min 13 s** |

**Browser** (before → after; the open time on the slow tablet was repeated 3 times: 0.75–0.87 s):

| | Laptop | Slow tablet |
|---|---|---|
| Open the largest paper | 0.80 → **0.73 s**, CPU −43 % | 3.7 → **0.8 s**, worst frame 909 → **195 ms**, long tasks 10 → **1** |
| Decide (p95 / max) | 32 / 64 → **24 / 88 ms**, CPU −23 % | 224 / 1,208 → **96 / 416 ms**, CPU −60 % |
| Long tasks while deciding (count / longest) | 0 → 0 | 211 / 803 → **51 / 139 ms** |
| First visit of a page | 15–102 → 15–110 ms | 72–800 → **28–137 ms** |
| Cached page | 4–7 → **1–7 ms** | 10–67 → **7–20 ms** |
| Zoom | 103–112 → 132–163 ms | 330–400 → **130–190 ms** |
| JS heap after 10 papers | 3.7 → 4.5 MB, no growth | 3.4 → 3.6 MB, no growth |

**Budgets now** · every B2 budget passes on both profiles, except *API Papers list ≤ 150 ms* at 50 papers (below).

## Scale (synthetic stress set, after the fixes)

50 papers, one with 2,000 values on 60 pages and 20 full versions (23 MB). Before the fixes this run did not finish in
16 minutes; after, it takes 3.5 minutes.

| Operation | p50 / p95 ms | Note |
|---|---|---|
| Papers list (50 papers) | 225 / 244 | linear, ~4.5 ms per paper: over the 150 ms budget from ~30 papers |
| Open the 2,000-value paper | 267 / 409 | |
| Save draft (2,000 decisions) | 462 / 498 | validation of the working copy, linear |
| Submit (2,000 values) | 2,425 / 2,532 | linear in values (414 values: 0.57 s) |
| Version history | 17 / 565 | first call after a start: 14,897 ms before the follow-up fix (below), 565 ms after; then 17 ms |
| Export CSV / ZIP | 29 / 137 | |
| Load papers again | 488 / 735 | |
| 4 tabs at once | wall 1.6 s | |
| Server memory | 181 MB, no growth over 1,000 requests | |

## Remaining (not part of the approved fixes)

1. ~~**First opening of the version history after a start, with very large versions**~~ · **Fixed (follow-up, approved)**:
   the list checks only each version's header (`AnnotationStore.version_header`); a version is validated in full when it
   is opened, restored or exported. 20 × 2,000 values: 14.9 s → 0.57 s (the rest is reading 23 MB of JSON); then 17 ms.
2. **Papers list over 150 ms from ~30 papers**: it still reads each paper's newest version and draft (now cached) and
   computes progress; a per-paper summary cache would make it constant.
3. **Submit time grows with the values** (validating and writing the full snapshot); fine at the real size.
4. **One render at a time** on the server: preloading hides it for page turns, not for several tabs rendering cold pages.

## Reproduce

```
python -B -m value_review.perf.server_bench --dataset real --profile --json server-real.json
python -B -m value_review.perf.server_bench --dataset stress --runs 8 --json server-stress.json   # slow until B-2 is fixed
cd value_review/frontend && npm run build && npm run perf     # results in perf-results/<profile>.json
```
