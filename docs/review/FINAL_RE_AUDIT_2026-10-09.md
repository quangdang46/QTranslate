# FINAL RE AUDIT — qtranslate-re (QTranslate 6.10.0)

> Consolidated hand-off. Produced under the MASTER LOOP prompt (RE completion &
> audit). **No Phase C, no commit, no waiver assigned.** Read-only on the binary
> (Ghidra) + `QTranslate.exe` byte/string/`.rsrc` inspection.

## 1. Executive summary

Native reverse engineering of QTranslate 6.10.0 is **effectively complete**:
**151 / 152** checklist items are `VERIFIED` by direct artifact (incl. **J3**,
a *proven negative*: no native SAPI TTS), and **1** (`G9`, visual fidelity) is a
**runtime measurement task**, not an RE question. **No item remains `INFERRED`
or `UNRECOVERABLE`.** The Gate reads **BLOCKED (1)** because the validator is
all-or-nothing and `G9` is not VERIFIED — not because of an unknown native
behavior.

Two large closures this session: the **FLAC encoder call site (J6)** and the
**read-phonetically chain (J7)**. Three corrections to `NATIVE_ARCH.md` labels
were confirmed by evidence and recorded as tensions (file left frozen).

## 2. Baseline

- Branch `main`, HEAD `0cb0e78`, no commits made by this work.
- **Preserved user change:** `qtranslate/app.py` `on_hotkey` uses `src` from
  `app.current()` instead of `"auto"` — **diff = 4 lines, untouched**.
- `docs/NATIVE_ARCH.md` — **frozen, diff empty**.

## 3. RE tally (from `tools/coverage_tally.py`)

| Axis | Value |
|------|-------|
| Total items | **152** |
| `VERIFIED` | **151** |
| `INFERRED` | **0** |
| `UNKNOWN` | **1** (G9) |
| `UNRECOVERABLE` | **0** |
| `WAIVED` | **0** |

Port axis: `ported 121 · not-started 11 · behaviour-verified 11 · dead:* 9`.

## 4. Gate

```
$ python -I tools/coverage_tally.py --check
items=152 re={'VERIFIED':151,'UNKNOWN':1} port={...}
gate=BLOCKED (1 unresolved)
exit=2
```
Validator logic: `unresolved = rows where RE-state not in {VERIFIED,UNRECOVERABLE}
and not waived`. Only `G9` (UNKNOWN) matches → **BLOCKED (1)**, `exit=2`.

## 5. Resolved items this session

| Item | New evidence (file / symbol / address) | Why status changed |
|------|----------------------------------------|--------------------|
| **B6** in-window keys | `FUN_0042DC18` binds menu `0x8051` "Reset" + `L"Shift+Esc"`; RT_ACCELERATOR id 3 in `.rsrc` type 9 | menu-accelerator wiring directly observed |
| **C10** cursor icon | full mouse path `FUN_00417E4E`→`FUN_004193F6`→`FUN_00404901` (text only); no `SetCursor`/icon hook | absence proven within enumerated path |
| **I2** DLG164 | RT_DIALOG id `0xA4`=164 → template @`0x00554E98` (WS_CHILD, BUTTON id 0x20) | dialog resource bytes read |
| **E21/F12** tkk | `FUN_0040FEC9` GETs the translate page + `CString::Find` slice = tkk parse | parse site found |
| **F11** cookie | curl fetch wrappers `FUN_0045BCED`/`FUN_0045BF7D` + proxy options | recast to observed evidence |
| **K2** region select | `FUN_004377CB` overlay keys + DC→HBITMAP→PNG `FUN_0044B269` → OCR | glue traced |
| **J6** FLAC | init `FUN_00466509` (`"fLaC"` `0x664C6143`, callbacks +0x1C30, read cb `FUN_00445803`), call site `FUN_00445716` (PCM int16→int32 + `FUN_00467437`) | encoder init **and** call site both found |
| **J7** read-phonetically | flag `DAT_00549414`; menu `0x802d`; consumer `FUN_0042ED3F` (appends phonetics to result) | consumer/effect found; **relabelled display, not TTS** |
| **F13** engine | `CLSID_JScript {F414C260-…}` present, Chakra/JScript9 `{16D51579-…}` absent, no engine strings | binary behavior resolved; no version claimed |
| **J3** SAPI | SpVoice CLSID + `SAPI.SpVoice`/`SpVoice`/`ISpVoice`/`sapi` all absent; only `atlTraceISAPI` | **VERIFIED (proven negative)** — no native SAPI TTS |

## 6. Unresolved items

### G9 — Visual fidelity to native (`UNKNOWN`)
- **Tried:** enumerated native window spec (DLG129 geometry `526×366`, control
  ids, RichEdit50W, Tahoma 9, theme colours, tray icons) from `.rsrc`/RTTI.
- **Result:** the native *spec* is recovered; the *comparison* (our Tk render vs
  native) is not an RE question.
- **Missing evidence:** a screenshot-diff of native vs port.
- **Why stop:** RE/decompilation cannot produce it.
- **Next step:** runtime test harness — capture both, diff with tolerance.
  **Classification: product-acceptance**, not RE. Left `UNKNOWN` so the Gate is
  honest.

### J3 — native SAPI TTS (`VERIFIED`, proven negative)
- **Reason:** positive exclusion — CLSID bytes and all SAPI strings absent.
- **Impact:** `sapi.py` is a non-native port addition; must not be presented as
  reconstructed native behavior. (Recorded as tension vs `NATIVE_ARCH.md:1622`.)

## 7. J6 / J7 deep trace (call/data flow)

**J6 FLAC encoder (closed):** mic → `BASS_RecordStart` (`FUN_0044555D`, cb
`FUN_00445606`) → frame `FUN_00444D94` → queue `FUN_00445659`; the speech loop
`FUN_004437F3`/`FUN_004439E6` calls `FUN_00445716`, which (once) runs encoder
init `FUN_00466509` — writes `"fLaC"` magic via `FUN_0046CBCE`, installs FLAC
callbacks (`FUN_00472AE1`/`0046A316`/`0046A672`/`0046AD6E` at +0x1C30..),
read callback `FUN_00445803` at +0x1C64, returns FLAC init-status codes — then
converts PCM int16→int32 and calls `FUN_00467437(encoder, samples, n)`. Output
is uploaded as `audio/x-flac` (J5).

**J7 read-phonetically (closed):** key `ReadPhonetically`↔`DAT_00549414` via
loader `FUN_0045869F` and saver `FUN_004561F0`; toggled by menu `0x802d` in
`FUN_00430C52`; **consumed in `FUN_0042ED3F`** — when the flag is set and the
phonetics field `entry[5]` is non-empty, it appends `"\r\r"` + string-resource
`0xBA` + the phonetics text to the result pane. **Display feature, not TTS.**

## 8. Independent feature inventory (coverage)

| Source | Count | Checklist | Gap |
|--------|-------|-----------|-----|
| `Services/*/` | 19 (+Common.js) | E1–E22 | none |
| `Plugins/History/*.js` | 4 | I4a–d | none |
| `Themes/*.json` | 8 | N2 | none |
| `Locales/*/` | 35 | O2 | none |
| `Options.json` sections | 20 | M3–M21 | none |
| `.rsrc` RT_DIALOG | 19 | dialogs | none |
| RTTI windows/tasks/services | ApplicationWindow…, TaskShowMainWindow…, services::Script/UtilsDispatch | A/G/K/J/D/F | none |

No in-scope feature enumeration was found without a checklist row. The
inventory is **not claimed exhaustive**; `coverage_tally.py` is a structure
check, not a completeness proof.

## 9. Cross-document audit

Fixed this session: matrix counts reconciled to the tally; matrix tension
citations (history loader/saver, spell destructor, SAPI); `PIPELINE.md` tension
banner + fixed executor/detect-retry labels + 19 services + no screenshot claim;
README test numbers marked as a dated snapshot; CHANGELOG naver → LIVE-OK;
matrix phonetic row → display. Remaining known-by-design: `NATIVE_ARCH.md`'s six
mislabeled claims stay as recorded tensions (file frozen).

## 10. Test evidence

```
$ python -I tools/coverage_tally.py --selftest   ->  PASS (all 6 cases ok)  exit 0
$ python -I tools/coverage_tally.py --check       ->  BLOCKED (1)          exit 2
```

## 11. Git diff audit

- Modified: `CHANGELOG.md`, `README.md`, `docs/PIPELINE.md`, `qtranslate/app.py`.
- Untracked: **10** docs in `docs/` (`ARCHITECTURE`, `COMPATIBILITY_MATRIX`,
  `CURRENT_STATE`, `EXTENSION_SDK`, `IMPLEMENTATION_PLAN`, `PROJECT_VISION`,
  `RELIABILITY`, `RE_COVERAGE_CHECKLIST`, `RE_PROGRESS`, `TEST_STRATEGY`) +
  `tools/coverage_tally.py` + `docs/review/`.
- **Invariants held:** `NATIVE_ARCH.md` diff empty; `app.py` diff = 4 lines; no
  runtime/schema/dependency change; **0 row-level waivers**; no commit/push.

## 12. Readiness assessment (three separate axes)

| Axis | Status |
|------|--------|
| **RE coverage** | ~99% — 151/152 VERIFIED (J3 = proven negative), 0 INFERRED, 1 runtime-test (G9). Effectively complete. |
| **Refactor readiness** | High — Core/Extension boundaries designed (`ARCHITECTURE.md`); providers/settings/history mapped; 6 native labels to carry as caveats. |
| **Implementation completeness** | 0% — Phase C not started (awaiting Gate approval). |
| **Product acceptance** | 0% — no acceptance run; G9 fidelity unproven. |

## 13. Decisions (user-resolved 2026-10-09)

1. **J3** — decided: reclassified to `VERIFIED` (proven negative); resolved.
2. **G9** — decided: **keep the Gate BLOCKED** and build a **runtime
   screenshot-diff harness** before any G9 waiver. Rationale: fidelity is an
   unmeasured product-acceptance criterion, not missing RE; waiving it would
   shift risk into implementation.
3. **Phase C** — not started; will be considered only after the G9 decision is
   informed by harness results.

## 14. Next steps (not yet executed)

Per §13, the G9 decision is **already made** (keep the Gate BLOCKED, build the
harness first) — the next step is to *execute* it, not to re-decide it:

1. **Build and run the G9 runtime screenshot-diff harness** (product test, not
   RE): capture native + port at identical window size / UI state / input; diff
   with a clearly configurable tolerance; save original, port, and diff images
   plus a results report; if no native-runnable environment or identical state
   exists, report **BLOCKED** with a specific reason — never fabricate a PASS.
   Only after harness results exist may G9's disposition (waiver or fix-first)
   be revisited.
2. **Gate** stays **BLOCKED (1)** throughout. No waiver is assigned by this
   step; opening the Gate remains a separate, explicit user act (§13.2).
3. **Phase C** — not started; considered only once G9 is informed by harness
   results and the user approves the Gate (§13.3).

No commit, no push, no waiver, no runtime/product implementation as part of the
harness-tooling step itself.
