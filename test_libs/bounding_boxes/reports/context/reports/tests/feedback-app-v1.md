# Execution ledger — separate paired region feedback screen

User approved the separate screen, paired negative/preferred regions, optional reasons and sample-based review. Explicitly requested implementation with original results unchanged.

Ruling: keep new code in feedback_app and data in feedback_data; no worktree/commits or changes to original viewer/results. Cost: local uncommitted addition rather than branch integration.

Plan: tests first for data contract/storage, then loopback API, two-panel frontend, fixture browser tests, independent code review and visual verification. No parsing, OCR, models or Colab. Mining preference patterns is a subsequent task, not automatic ground-truth inference.

Scope of reference changes: latest user instruction replaces exhaustive manual review of397pages with selected examples; existing automatic outputs and pending review metadata remain frozen.

## Completed verification (2026-11-01)

- Backend: 8 unittest cases passed; geometry: 3 Node tests passed.
- Independent review found image readiness race and enabled alternative-removal buttons during save; both fixed. Revision validation now excludes booleans/floats.
- Browser fixture: reverse drag, 160% zoom, three alternatives across Basic/Standard, optional reason/note, save/reload/edit/remove alternative/withdraw/restore verified. Fixture data are isolated under runtime/feedback-browser-fixture-v1, not human preferences.
- Real browser: page1/page2 navigation and Heron/Basic boxes verified, 0 human examples saved. Screenshot: final.png. Separate app at http://127.0.0.1:8770/; PID in server.pid. Fixture server stopped.
- Original integrity: all2452 input-manifest files matched SHA256 (original-integrity.json). No parser, OCR, Colab or models executed.
- Gateway query e4898794d612477b938c2e87de4e4a1e reviewed successfully.
- Preference data will be created under feedback_data/session-v1 on the first save. Single server process is intended; do not run concurrent writers against that directory.
