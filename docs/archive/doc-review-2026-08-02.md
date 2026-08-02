# Documentation Review — 2026-08-02

**Method:** single-model review (no MCR — per request). All 12 markdown files
(README + docs/, including the new archive) assessed for accuracy vs code,
freshness, links, duplication, coverage, and audience fit. Auto-checks:
internal-link resolution (12/12 resolve), external URL health (all 200),
repo-wide stale-reference scan (clean), spot-checks against the live code.

## Verdict

**PASS after 2 fixes.** The docs were in good shape (the architecture refactor
had kept pace with the code); the main gap was organizational — five historical
issue-draft/review docs sat among the active docs as if current.

## Per-file findings

| File | Status | Findings |
|---|---|---|
| `README.md` | ✅ Good (updated) | Pipeline section corrected in Phase 4 (own-sites were "fallback only" — the opposite of reality); added a Documentation index |
| `docs/architecture.md` | ✅ New (this review) | System map + data model + invariants; cross-refs the other docs |
| `docs/development.md` | ✅ New, 1 fix | Setup, tasks, testing, PR conventions. Fix: `node --check a.js b.js` only checks the first file — split with `&&` |
| `docs/data-flow.md` | ✅ Good | Pipeline mechanics; matches code (writers, fallbacks, manuals) |
| `docs/architecture-refactor-plan.md` | 1 fix | **Internal contradiction (MCR-flagged):** line 99 still said Phases 1/3/4 are "independently shippable" while the MCR-deltas header says Phase 3 depends on the Phase-1 parser. Corrected. |
| `docs/making-cows.md` | ✅ Good | Verified: 30 rotating cows (`cow-0..29`; the other 5 files are `cow-base.png` + 4 `cow-pending-*` spares), Gemini 3 Pro Image, prompt template current |
| `docs/archive/README.md` | ✅ New | Explains what the archived docs are and why (provenance only) |
| `docs/archive/{5 issue docs}` | ✅ Archived | Historical issue drafts + MCR report; no inbound links; issues closed |

## Checks performed

- **Links:** all 12 internal links resolve (including the archive move — no
  inbound references broke); external URLs verified live (bigsoundbank 200,
  issue links 200, DeepSeek API endpoint correct).
- **Stale references:** repo-wide scan for old paths/claims
  (`data/removed_venues.json` outside `data/state/`, "fallback only",
  "Phases 1–2 done", old cache paths) — clean; the only hits are legitimate
  (a historical "why" sentence in the plan, and the real constant).
- **Accuracy vs code:** hours.js loaded before app.js ✓ (index.html), 22
  distinct hours strings ✓ (live data), requirements.txt deps ✓, validator
  commands ✓, remove_venue/tombstone path ✓, closure flags ✓.
- **Coverage:** no audience gap left — architecture (map), development
  (how-to), data-flow (pipeline), making-cows (assets), archive (provenance).

## Non-issues (checked, no action)

- Cow count 35 files vs "30 rotating cows" — correct: the 5 extra files are
  base/pending spares, not rotation cows.
- Minor duplication of the invariants in `architecture.md` and `data-flow.md`
  — intentional (map vs mechanics contexts); both now point at the schema.

## Actions taken

1. Created `docs/architecture.md` (system overview) + `docs/development.md` (dev guide).
2. Archived 5 historical docs under `docs/archive/` with an index README.
3. Fixed the refactor-plan shippability contradiction.
4. Fixed the `node --check` multi-file misuse in the dev guide.
5. Added the Documentation index to the README.
