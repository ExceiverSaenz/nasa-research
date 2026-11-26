# Tester Guide · Tensile Value Review (preliminary demo)

Thank you for testing. This tool shows each tensile value that an LLM extracted from a paper next to the PDF page it
came from, so an expert can accept, correct, reject or flag it, and save a reviewed version. This is an early demo:
please use it as you would in real work and tell us everything that is slow, confusing or broken.

Everything runs on your own computer. Nothing is sent anywhere, and the PDFs and LLM results are only read, never changed.

## 1. What you need

- **Docker Desktop** (Windows or macOS) or Docker Engine (Linux), running. Check with `docker version`.
- **Git**, to download the tool (or download the repository as a ZIP from GitHub).
- **Two folders you receive separately** from the project lead (they are not in the repository):
  - the **LLM results**: files named `<paper>-pdf_with_feature_guide.json`;
  - the **PDFs**: files named `<paper>.pdf` (the same paper numbers).
- About 1 GB of free disk space and a recent Chrome, Edge or Firefox.

## 2. Set it up (once)

1. Download the tool:

   ```
   git clone https://github.com/ExceiverSaenz/nasa-research.git
   cd nasa-research
   ```

2. Copy `value_review/.env.example` to `value_review/.env` and edit it with your name and the two folders, using full
   paths with forward slashes:

   ```
   REVIEW_NAME=Your Name
   REVIEW_LLM_RESULTS=C:/Users/you/Documents/llm_results
   REVIEW_PDFS=C:/Users/you/Documents/pdfs
   REVIEW_DATA=./review-data
   REVIEW_PORT=8766
   ```

   - `REVIEW_NAME` is required: it is written as the author of every decision and version you make.
   - Optional: `REVIEW_WORKSPACE=C:/Users/you/workspace`, a folder with `papers/<set>/` (PDFs) and
     `results/<set>/<run>/` (LLM results). Each run shows in Review and its papers load by themselves. The tool only
     reads this folder.
   - `REVIEW_DATA` is where **your reviews** are kept. Do not delete it while testing.
   - Change `REVIEW_PORT` only if port 8766 is already in use on your computer.

## 3. Start and stop

From the `nasa-research` folder:

```
docker compose -f value_review/compose.yaml up --build -d
```

The first start takes a few minutes: it builds the tool and runs its automatic tests. Then open
**http://127.0.0.1:8766/** in your browser.

- Check the start: `docker compose -f value_review/compose.yaml logs` should list how many LLM results and PDFs it
  found. A line starting with `WARNING: no LLM results` (or `no PDFs`) means a path in `.env` is wrong: fix it and run
  the `up` command again.
- Stop: `docker compose -f value_review/compose.yaml down`. Your reviews stay in `REVIEW_DATA`.
- Next time, the same `up` command starts it again in seconds.

## 4. What to try

Work on at least two papers, one of them a large one, and try each of these:

1. **Papers** · find a paper with the search box, sort the columns, open a paper.
2. **Review a value** · for each value, compare it with the highlighted box on the page, then:
   - **Accept** (key **F**) when it is right;
   - **Edit value** and save the correction when the number or unit is wrong;
   - **Reject** (key **S**) or **Unsure** (key **D**): both ask for a reason.
3. **Move around** · **J** / **K** next and previous value, **Shift+J** / **Shift+K** next and previous record, **?** shows
   every shortcut.
4. **Fix the structure** · move a value to another column or record ("Column and record"), add a record the model
   missed, add a value the model missed (**+ Add value**, then drag on the page to mark it).
5. **Highlights** · **+ Add highlight** and drag on the page; select a box on the page to **Redraw** or **Delete** it.
6. **Several at once** · **Accept N pending** accepts the rest of the list; **Undo** right after reverts it.
7. **Save and come back** · **Save draft** (Ctrl+S), close the tab, open the paper again and choose **Continue draft**.
8. **Finish** · **Finish paper**, read the summary, **Submit paper**; then **Download CSV** and look at it.
9. **Versions** · on Papers, the **⋯** menu of a paper: **Version history**, **Compare with current**, **Restore**.
10. If you have a tablet, open the same address from it only if it runs the tool itself; the demo is not reachable from
    other devices by design.

## 5. How to report

For each problem or suggestion, please send:

- **What you did** (the steps), **what you expected**, and **what happened**;
- the **paper number** and, if it is about a value, its column and record;
- a **screenshot** when it helps;
- how it felt: was anything **slow**, did the screen **freeze or flash**, was a label or message **unclear**?

Send them to the project lead, or open an issue in the GitHub repository. Your submitted versions (CSV or JSON from
**Download CSV** or the version history) are also useful to compare reviewers.

## 6. Known limits of this demo

- Each tester's reviews stay on their own computer; they are not combined automatically.
- Only papers with both files (LLM result and PDF) are loaded; the start log and **Settings → Load papers again** list
  any paper missing one of them.
- There are no accounts: anyone using your computer can use your demo. It is reachable only from your own computer.
- Your name can be changed later in **Settings** (the gear at the top of Papers).
