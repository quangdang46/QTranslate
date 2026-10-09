# Test Strategy

> Status: **PLANNING.** How every compatibility and reliability claim is
> proven. A single "all green" run never constitutes proof of a claim
> (`PROJECT_VISION.md` §7).

## 1. Test layers

| Layer | Runs on | Proves |
|-------|---------|--------|
| **Contract** | any OS, no network | providers honor the SDK contract (same request → same shape) |
| **Compatibility** | Win + mac | matrix rows tagged `must-keep` behave like 6.10 |
| **Reliability** | any OS, mocked failures | classify/retry/fallback/timeout policy |
| **Platform** | Win, mac separately | adapters report honest capabilities; Core runs without OS imports |
| **Extension** | any OS | load, override, conflict, fail-open |
| **UI** | Win + mac | structure/strings **and** screenshot fidelity (separate tests) |
| **Live integration** | network | providers still reachable (optional, not a gate) |

## 2. Current suite inventory (what exists)

| File | Kind | Notes |
|------|------|-------|
| `tests/live_providers.py` | live integration | hits real endpoints; moved to *optional/nightly*, not a release gate |
| `tests/ui_match.py` | structural UI | asserts strings/order/defaults; **not** screenshots (`CURRENT_STATE.md` §2.2) |
| `tests/smoke_dict.py` | import/offline helpers | dictionary + config + hotkeys |
| `tests/live_bass.py` | live audio | playback smoke |

**Gap:** no mock-based reliability tests, no contract tests, no platform-absence
tests, no screenshot tests. These are added per phase below.

## 3. Required new tests (by phase)

- **Phase 1:** classification unit tests; fallback integration with a mock
  provider that always fails; `Retry-After` handling; total-budget enforcement.
- **Phase 2:** contract tests applied to every provider; golden-input
  equivalence (Google old path vs new contract → identical output).
- **Phase 3:** manifest validation matrix (missing/short/bad `sdk_version`,
  broken entrypoint, unimportable module); override conflict resolution.
- **Phase 4:** import-guard test — assert Core imports succeed with `win32gui`,
  `winreg`, `comtypes`, `ctypes.windll` patched to raise; per-adapter capability
  honesty (unsupported → reported, not faked).
- **Phase 5:** end-to-end engine tests with mock providers; the source-language
  consistency test for all capture paths (matrix row B).
- **Phase 6:** MVP demo tests — load a sample provider/theme/UI extension,
  assert effect; break it, assert fail-open.
- **Phase 7:** screenshot diff harness for main window + popup (Win first, mac
  after); UI extension slot tests.
- **Phase 8:** packaging smoke on each OS.

## 4. Rules

1. **Two-class suites.** *Deterministic* (mock, no network) gate every commit;
   *live* suites run on a schedule and are not a merge gate (endpoints flap —
   DeepL 429, WordReference Anubis, see `LIVE_RESULTS.md`).
2. **No compatibility claim from a structural test alone.** Structure ≠
   appearance ≠ behavior.
3. **Dead endpoints are recorded, not tested into green.** A test may assert
   "classified `PROVIDER_DEAD`", not "translate works".
4. **Cross-platform rows require both platforms** (both in `Test-on`) before `behaviour-verified`.
5. **Reproduce the baseline by running** — do not copy numbers from README.
6. **Every fixed reliability bug gets a regression test** that fails before and
   passes after.

## 5. Acceptance mapping

Each `COMPATIBILITY_MATRIX.md` row names a test in its "Test" column. A row is
`behaviour-verified` when that test exists and passes on the row's declared
platforms. The matrix — not a percentage — is the completion measure.

## 6. Tooling

- Test runner: `pytest` for deterministic suites (stdlib `unittest` acceptable);
  keep the existing script-style live suites as-is initially.
- Mocking: a shared `FakeProvider` fixture (configurable failure kind) for
  reliability and engine tests.
- Screenshots: platform screenshot capture + a tolerant diff (documented
  threshold), Windows baseline from the real QTranslate window where possible.
- CI: deterministic suites on Windows and macOS runners; live suites nightly.

## 7. What is explicitly not tested (v1)

- Untrusted-code isolation (no sandbox in v1).
- Realtime hot reload (not a feature).
- Marketplace/dependency resolver (not built).
