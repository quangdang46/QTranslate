# QTranslate port — agent notes

Python/PySide6 port of QTranslate 6.10. Reference implementation (read-only):
`.tmp/QTranslate` (Kotlin/Swing). Parity tracking: `docs/RE_COVERAGE_CHECKLIST.md`,
`docs/GAP_AUDIT_2.md`, `docs/GAP_AUDIT_3.md`.

## Workflow

- Tests: `QT_QPA_PLATFORM=offscreen .venv/bin/python tools/run_suites.py`
  (per-file: `.venv/bin/python tests/regress_*.py`). Judge by exit code.
- Tests must isolate `qtranslate.config.DEFAULT_PATH` to a temp file BEFORE
  any config load — pages write through, and `config.load()` auto-migrates
  the real Kotlin datastore only when `DEFAULT_PATH` is the builtin path.
- **Push to `origin main` after each completed wave** — user preference
  ("nhớ push thường xuyên"). Local commits alone are not enough.
- `br` beads track work (`br list`, `br close <id> --reason ...`).

## Conventions

- Options pages use screenshot coords via `put()` (ORIGIN=(1,26)); grown
  pages need matching `CHROME` offsets or footer overlaps.
- Popup stays button-less (structural test greps raw source — even comments
  mentioning the button class fail it).
- Secrets live in `qtranslate/secrets.py` (0600 JSON beside Options.json),
  never in Options.json.
- Platform backends dispatch on `sys.platform`, lazy imports, honest
  False/None fallback when binaries/modules are absent.
