# RE Progress Log (durable)

> Running record of the reverse-engineering effort (Phase A). Append-only.
> Machine tally: `python -I tools/coverage_tally.py` (regenerates the block in
> `RE_COVERAGE_CHECKLIST.md`; exit 0=Gate OPEN, 1=structure invalid, 2=BLOCKED).

## Constraints (standing)

- Do **not** modify `docs/NATIVE_ARCH.md` without explicit user authorization.
  Record discrepancies in this log / `RE_COVERAGE_CHECKLIST.md` as *tensions*.
- Preserve the uncommitted `qtranslate/app.py` change (on_hotkey `"auto"`→`src`).
- Two independent axes: native **RE** (`VERIFIED/INFERRED/UNKNOWN/UNRECOVERABLE`)
  vs **port** (`not-started/ported/behaviour-verified/dead:<slug>`). A doc
  statement is never self-validating evidence.
- Do not start Phase C (implementation) without explicit Gate approval.

## Session log

### 2026-10-09 — Groups D–R sweep

| Group | Result | Notes |
|-------|--------|-------|
| D Orchestration | D1–D9,D11 VERIFIED; D10 INFERRED | struct + loop resolved (pass 3) |
| E Providers | partial | E1–E3,E8 VERIFIED; E4–E22 still INFERRED |
| F JS boundary | F1–F10 VERIFIED; F13 UNKNOWN | CLSID_JScript via CoCreateInstance; arity-based interface ID |
| G Rendering | G1–G8 VERIFIED; G9 UNKNOWN | layout::LayoutRatioRule, RichEdit subclass, rounded rgn |
| H Dictionary | H2,H3,H5,H6,H8 VERIFIED; H1,H7 INFERRED | chain data→MSXML/XSLT→HTML→UI closed |
| I History | I1,I3,I4a–d,I5,I6 VERIFIED; I2 INFERRED | two-way flow; save=`FUN_00463B04` |
| J TTS/audio | J1,J2,J4,J5 VERIFIED; J3 UNKNOWN; J6,J7 INFERRED | BASS 1:1; **J3 SAPI absent in native** |
| K OCR | K1,K3,K4 VERIFIED; K2 INFERRED | OCR chain screen→PNG→ocr.space→ParsedText |
| L Tray | L1–L4 VERIFIED | Shell_NotifyIconW; states 199/0x84/0x8A |
| M Options | M1–M21 VERIFIED; M22,M23 INFERRED | loader `FUN_0045869F` maps all sections |
| N Theme | N1,N3,N4 VERIFIED | GDI+ fill; state selector `FUN_0044C51C` |
| O i18n | O1,O3 VERIFIED; O4 INFERRED | `FUN_0042F2CC` default source |
| P Layout | P2,P3 VERIFIED; P1 INFERRED | exact EN↔RU pairs |
| Q Crash | Q1–Q3 VERIFIED | fail-fast codes |
| R Updater | R1,R2 VERIFIED; R3 INFERRED | host retired |

Tally after sweep: **140 VERIFIED / 9 INFERRED / 3 UNKNOWN** (152 items),
Gate **BLOCKED (12)**.

### 2026-10-09 — continued pass (A/B/C/L/M/N/O/P/Q/R + E providers)

- **A** startup: WinMain `FUN_00435005`, single-instance `FUN_00435175`
  (`L"allow-multiple-instances"` switch), msg loop `FUN_00455061`,
  filter registrar `FUN_004551D6`, palette ctor `FUN_00416470` → A1–A9 VERIFIED.
- **B** hotkey: `RegisterHotKey` `FUN_00405A17`; dispatch `FUN_0041786B` → task
  objects; display `FUN_00403B48`; HotKeyCtrl `FUN_00408456`/`FUN_0040AA88`
  (double-press bit15) → B1–B5 VERIFIED; B6 INFERRED.
- **C** capture: dispatcher `FUN_004052E4`, OLEACC `FUN_00404901`, clipboard
  viewer `FUN_0043EBE0`, write-back `FUN_0043BE56`, exclusions `FUN_004631DE`,
  RawInput `FUN_00417E4E`, click `FUN_004193F6` → C1–C9 VERIFIED; C10 INFERRED.
- **E** providers: read all 19 `Services/*/Service.js` (subagent) → E4–E20,
  E22 VERIFIED with exact IDs/capabilities/endpoints; E21 (tkk parse) INFERRED.
- **L** tray, **M** options (loader `FUN_0045869F` maps all 20 sections),
  **N** theme, **O** i18n, **P** layout pairs, **Q** crash, **R** updater →
  all VERIFIED except O4/P1.
- **B4/B5 correction:** double-press is in the HotKeyCtrl (`FUN_0040AA88`),
  not only the global registrar.

### Remaining 12 unresolved (all evidence-limited, none forced)

INFERRED (9): B6 in-window keys · C10 cursor-icon · E21/F12 Google tkk parse ·
F11 cookie jar · I2 DLG164 dialog link · J6 FLAC encoder call-site ·
J7 phonetic effect · K2 region-select→bitmap.

UNKNOWN (3): F13 JS backend (OS-decided) · G9 visual fidelity (measurement
task) · J3 native SAPI (absent in binary).

> Supersedes an earlier "15 unresolved / INFERRED (12)" list in this same
> section: F12/H7/O4/P1 were later promoted to `VERIFIED` and D10 is now
> `VERIFIED` (loop), leaving 9 INFERRED + 3 UNKNOWN. The machine tally
> (`coverage_tally.py`, 140/9/3, BLOCKED 12) is authoritative.

### Tensions recorded (not edited into NATIVE_ARCH.md)

1. `NATIVE_ARCH.md:1592` labels `FUN_0045F6C1` "task executor" — decompile shows
   option/token seeding; request loop is `FUN_00460354`. (D)
2. `NATIVE_ARCH.md:463` "detect-retry loop" for `FUN_00460354` — it is a
   build→fetch→parse loop, no detect. (D10)
3. `NATIVE_ARCH.md:982` attributes spell to `FUN_0042C909` — it is a destructor. (H)
4. `NATIVE_ARCH.md:32` labels `FUN_004638D8` "History save" — it is the loader;
   writer is `FUN_00463B04`. (I)
5. `NATIVE_ARCH.md:1622` labels `FUN_00448BEC` = SpVoice `{29333BF9-…}` — the
   address is the MSXML DOMDocument engine `{2933BF90-…}`; SpVoice CLSID is
   absent; **no native SAPI TTS found**. (J3)
6. `NATIVE_ARCH.md:105` groups `EVENT_STOP_CAPTURE` with OCR — it is a
   speech-recognizer FSM event. (K)

### Blockers / limits

- **J3** native offline SAPI: no evidence in binary (may not exist). Port-side
  `sapi.py` kept as our fallback only.
- **F13** JS engine backend (JScript5.8 vs Chakra): OS-decided, not answerable
  from the binary.
- **G9** visual fidelity: a measurement task (screenshot diff), not RE.
- **A9** argv parse: strings present, xref unresolved (MFC thunk), low impact.

### Coverage completeness audit (performed)

Independent enumeration against the 152-row inventory:

| Source enumerated | Count | Mapped to | Status |
|-------------------|-------|-----------|--------|
| `Services/*/` | 19 (+ Common.js) | E1–E22 | all present |
| `Plugins/History/*.js` | 4 | I4a–I4d | all present |
| `Themes/*.json` | 8 | N2 (group) | present |
| `Locales/*/` | 35 | O2 (group) | present |
| `Options.json` sections | 20 | M3–M21 | all present |
| `.rsrc` RT_DIALOG | 19 | dialogs | History=164 confirmed |
| RTTI windows | App/Main/Popup/Keyboard/History/Dictionary/Options/HotKey/Languages/Info/About/ScreenCapture/LayoutIndicator/SpeechLevel/Progress | A/G/K/J | represented |
| RTTI tasks | ShowMainWindow/ShowPopupWindow/Dictionary/ListenText/ConvertTextLayout/CopyTranslation/ReplaceSelection/TranslateClipboard/Ocr | A–D/J/K | represented |

No in-scope feature enumeration was found unrepresented. The inventory is **not
claimed exhaustive**; passing `coverage_tally.py` is a structure check only.

## Gate report (2026-10-09) — RE incomplete, Gate BLOCKED, approval pending

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Every row has a justified RE state | **12 rows still INFERRED/UNKNOWN → not yet** |
| 2 | Every VERIFIED cites a concrete artifact | yes (address/JS/asset/test) |
| 3 | Critical call chains traced | yes (D/E/F/H/I/J/K) |
| 4 | Native vs port vs hypothesis distinguished | yes (two-axis model) |
| 5 | Contradictions reconciled/documented | yes (6 tensions) |
| 6 | Validator passes intended checks | `exit=2` (expected while BLOCKED) |
| 7 | Working-tree preservation | app.py change intact |
| 8 | Coverage completeness audit | done |

### The 12 unresolved rows

**INFERRED (9):** B6 in-window keys · C10 cursor-icon · E21/F12 Google tkk
*parse* · F11 cookie jar · I2 DLG164 dialog-run link · J6 FLAC encoder
call-site · J7 phonetic effect · K2 region-select→bitmap.

**UNKNOWN (3):** F13 JS backend (OS-decided) · G9 visual fidelity
(measurement) · J3 native SAPI (absent in binary).

**F13 and G9 are not answerable by RE at all** — they need a product decision,
not more decompilation. J3 likewise appears genuinely absent. The remainder need
targeted call-site work.

### Phase B.3 — J6/J7 deep trace + F13/G9/J3 resolution (2026-10-09)

- **J6 CLOSED → VERIFIED.** FLAC encoder init `FUN_00466509` writes the `"fLaC"`
  magic (`0x664C6143`) via `FUN_0046CBCE`, installs callbacks
  (`FUN_00472AE1`/`0046A316`/`0046A672`/`0046AD6E` at struct+0x1C30..), read
  callback `FUN_00445803` at +0x1C64, returns FLAC init-status codes 1..0xd. The
  **call site is `FUN_00445716`** (init once, then PCM int16→int32 +
  `FUN_00467437(encoder, samples, n)`), reached from the speech loop
  `FUN_004437F3`/`FUN_004439E6`. Feeds the `audio/x-flac` upload (J5).
- **J7 CLOSED → VERIFIED (+ relabel).** Full chain: key `ReadPhonetically` ↔
  `DAT_00549414` (loader `FUN_0045869F`, saver `FUN_004561F0`); menu `0x802d`
  "Read phonetically" (`FUN_0042DF28`), toggled in `FUN_00430C52`; **consumer
  `FUN_0042ED3F`** appends `"\r\r"`+string-resource `0xBA`+phonetics to the
  result pane when the flag is on and `entry[5]` is non-empty. It is **phonetics
  display**, NOT TTS modulation — the old label was wrong.
- **F13 RESOLVED → VERIFIED.** Binary requests `CLSID_JScript {F414C260-…}`
  (present) and does **not** reference Chakra/JScript9 `{16D51579-…}` (absent,
  no engine strings). No engine *version* claimed (OS/registry decides).
- **J3 → VERIFIED (proven negative; reclassified from UNRECOVERABLE 2026-10-09
  by user decision).** SpVoice CLSID bytes and
  `SAPI.SpVoice`/`SpVoice`/`ISpVoice`/`sapi` strings absent from the exe; only
  `"SAPI"` hit is `atlTraceISAPI`; all `"Speech"` strings are input-side. Reason:
  the feature does not exist in the binary. Impact: `sapi.py` is a non-native
  port addition.
- **G9 split.** Native window spec is RE-recovered (geometry/ids/fonts/theme);
  the *fidelity comparison* is a runtime screenshot-diff = product-acceptance
  task, left `UNKNOWN` (not relabelled).

Result: **151 VERIFIED / 0 INFERRED / 1 UNKNOWN (G9) / 0 UNRECOVERABLE**, Gate
**BLOCKED (1)**. (J3 reclassified to `VERIFIED` as a proven negative on
2026-10-09 — see its bullet above; `UNRECOVERABLE` count is now 0.)

### Phase B.1 targeted closure (2026-10-09)

Closed by targeted decompile this pass:

- **B6** (in-window keys): `FUN_0042DC18` binds menu `0x8051` "Reset" with
  `L"Shift+Esc"`; RT_ACCELERATOR id 3 confirmed → VERIFIED.
- **C10** (cursor icon): mouse path fully enumerated (RawInput→click→OLEACC);
  **no cursor-icon hook exists** → VERIFIED (absence logged, not forced).
- **I2** (DLG164): template bytes read (`00554E98`, WS_CHILD child dialog,
  1st control BUTTON id 0x20); kept VERIFIED with the ATL-indirect caveat.
- **E21/F12** (tkk): `FUN_0040FEC9` fetches the translate page and `Find`-slices
  the tkk → VERIFIED; F12 closes the `GoogleTkk` seed chain.
- **F11** (cookie engine): recast to the curl fetch wrappers + proxy options
  (the "shared jar" was our port's inference, not native) → VERIFIED.
- **K2** (region select): overlay key handler `FUN_004377CB` + DC→HBITMAP→PNG
  → OCR → VERIFIED.
- **J7 tightened**: the "loaded by loader" line was imprecise — flag is in the
  **saver** only; cons-path untraced → stays INFERRED (honest correction).

Final: **147 VERIFIED / 2 INFERRED (J6 FLAC encoder call-site, J7 phonetic
effect) / 3 UNKNOWN (F13, G9, J3)** — 152 items, Gate **BLOCKED (5)**.

### Phase B cross-doc audit (2026-10-09)

Audited all 12 docs + README + CHANGELOG against the 140/9/3, BLOCKED(12)
tally (plus a delegated full-contradiction scan). Fixed:

1. **RE_PROGRESS self-contradiction**: "Remaining 15 / INFERRED (12)"
   (leftover from the 137-sweep) → "12 / INFERRED (9)".
2. **D10 stale notes**: checklist evidence said "D10 stays `INFERRED`"; row is
   `VERIFIED` as "request/response loop".
3. **Matrix provisional counts** (`~45/~8/~10`) → reconciled
   (`ported 121 / dead 9 / not-started 11`).
4. **Tension citations** in the matrix: History save/loader, spell/destructor,
   SAPI/MSXML. `PIPELINE.md` carries a tension banner + fixed diagram labels +
   19 providers + NO screenshot claim.
5. **README "all green"** → dated snapshot with test-count-churn note.
6. **CHANGELOG naver** → LIVE-OK (new API).
7. **Gate-report title** softened: "incomplete, BLOCKED" (no implication that
   implementation may start).

Still intentionally frozen: `NATIVE_ARCH.md` (6 tensions stay as tensions), the
`app.py` 4-line change, and the rule that Phase C requires explicit approval.

## Gate review package (Phase B.2, 2026-10-09)

> **⚠️ SUPERSEDED by §B.3 (2026-10-09).** This package (below) reflects the
> state **before** the final J6/J7/F13/J3 trace. Left as history per the
> append-only rule. Current authoritative state: **151 VERIFIED / 0 INFERRED /
> 1 UNKNOWN (G9) / 0 UNRECOVERABLE**, Gate **BLOCKED (1)**. In particular,
> this package's "5 exception items" (J6,J7,F13,G9,J3) is **stale**: J6/J7 are
> now VERIFIED, F13 is VERIFIED, J3 is VERIFIED (proven negative), and only G9
> remains. The
> validator **does** now have a waiver mechanism (see below), still unused.

### Why the validator returns exit 2 (exact)

> **[HISTORICAL — NOT CURRENT STATE]** At the time of this package the validator
> had no waiver mechanism and 5 rows were unresolved. The current validator
> **does** support waivers (`--selftest`), and only `G9` is unresolved. The
> arithmetic below (`147/2/3`, `return 2`) is the *old* state; see §B.3.

`tools/coverage_tally.py:152`:
`unresolved = sum(1 for r in rows if r[1] not in GATE_OK_RE)` where
`GATE_OK_RE = ("VERIFIED", "UNRECOVERABLE")` (line ~85). Non-`GATE_OK` RE states
are `INFERRED` and `UNKNOWN`. Current: **2 INFERRED + 3 UNKNOWN = 5** →
`return 2` (line 158). It is **all-or-nothing**: the validator has **no
exception/waiver mechanism**. Exit codes: `0`=open, `1`=structure invalid,
`2`=blocked. So exit 2 with 147/2/3 is **correct and expected**, not a bug.

### The 5 exception items — **[HISTORICAL — NOT CURRENT STATE; SUPERSEDED by §B.3]**

> The table below is the **pre-trace** snapshot. Current: J6/J7 `VERIFIED`,
> F13 `VERIFIED`, J3 `VERIFIED` (proven negative), G9 `UNKNOWN`; only G9 unresolved.

| Item | RE state | Evidence held | Missing | Type | Impact on implementation | Acceptance condition |
|------|----------|---------------|---------|------|--------------------------|----------------------|
| **J6** FLAC encoder | INFERRED | `audio/x-flac` stream string, libFLAC `FLAC__STREAM_ENCODER_*` strings, Xiph banner | concrete encoder call site | RE incomplete | Low — output format is known; only the exact encode entry unfound. Port uses our own encoder | Accept as RE-incomplete: preserve `audio/x-flac` contract + rate; no native byte-fidelity claim |
| **J7** phonetic TTS | INFERRED | `ReadPhonetically` key (saver ref) + label | loader read + runtime effect path | RE incomplete | Low — feature is optional; behavior unproven | Accept: implement per product decision; mark "native effect unverified" |
| **F13** JS backend | UNKNOWN | CLSID_JScript creation proven | which engine (JScript5.8/Chakra) | **environment-dependent** | None — we don't bundle a JS engine (use urllib+regex) | Accept: do **not** claim a specific engine |
| **G9** visual fidelity | UNKNOWN | native window geometry/classes | screenshot diff | **runtime/measurement task** | Medium — UI fidelity goal unmet | Accept: separate test task; no fidelity claim until measured |
| **J3** native SAPI | UNKNOWN | SpVoice CLSID absent, no sapi import | any native SAPI evidence | **RE-incomplete (likely absent)** | Low — `sapi.py` is our fallback | Accept: do not claim native SAPI; keep port fallback labeled as ours |

### Risk classification (three distinct kinds)

> **[HISTORICAL — NOT CURRENT STATE]** Below reflects the pre-trace view (J6/J7
> listed as incomplete). Kept for record; see §B.3 for current states.

1. **RE evidence incomplete** (J6, J7, J3-likely-absent): more decompile *might*
   close J6/J7; J3 appears genuinely absent. → risk of a wrong "equivalent" claim
   if not honestly labeled. Mitigation: keep labels; no native-fidelity claims.
2. **Environment/measurement-bound** (F13, G9): **cannot** be closed by RE.
   → Mitigation: F13 "no engine claim"; G9 becomes a UI test task.
3. **Product/runtime testing** (G9, and the J6/J7 behaviors): require runtime
   or product decision. → Mitigation: acceptance tests in Phase C, not RE.

### Validator change — WAIVER mechanism (IMPLEMENTED, tool-only)

> **[HISTORICAL — NOT CURRENT STATE]** The "0 waivers / BLOCKED (5)" line at the
> end of this subsection is the pre-trace figure. Current: **0 waivers** still,
> but only **`G9` is unresolved** → `BLOCKED (1)`, `exit=2` (see §B.3). The
> mechanism itself is current; only the count in that closing line is stale.

Approved tool change (not a Gate opening). `tools/coverage_tally.py` now
supports an explicit per-row `WAIVER: <reason>` token:

- reason mandatory; empty reason → structural error (exit 1)
- valid only on `INFERRED`/`UNKNOWN` (waiving `VERIFIED`/`UNRECOVERABLE` → error)
- waived rows reported **separately** in the tally block, never counted as
  `VERIFIED`
- validator **never** auto-assigns a waiver; default stays **BLOCKED** unless
  every INFERRED/UNKNOWN row is VERIFIED/UNRECOVERABLE or validly waived
- `--selftest` covers: unwaived INFERRED, waiver-with-reason (INFERRED+UNKNOWN),
  empty-reason error, waiver-on-VERIFIED error, and all-resolved-open (6 cases,
  PASS)

**Current state: 0 waivers assigned.** Real doc still reports
~~`BLOCKED (5 unresolved)`~~ → **[HISTORICAL — NOT CURRENT STATE] it now reports
`BLOCKED (1 unresolved)` (only `G9`), `exit=2`.** Gate not opened.
`app.py`/`NATIVE_ARCH.md` untouched.

#### Proposed waiver record format (to be filled ONLY on user approval)

Each accepted exception will get an explicit, auditable record. Proposed:

```
WAIVER: approved <YYYY-MM-DD> by <approver> | scope: Gate open only, not RE-complete | limit: <one-line>
```

and the same exception listed in the checklist's Gate section with: item id,
original RE state (unchanged), reason, approver, date, acceptance scope, and the
mitigation/test that covers its risk. **A waiver is not RE evidence and does not
change the item's RE state.** Verified end-to-end on a throwaway copy: adding a
valid `WAIVER:` to the 5 open rows flips `BLOCKED(5)` → `OPEN(0)`; an empty
reason yields a structural error (exit 1). The real document is unchanged (no
waiver assigned).

### Proposed Gate-approval conditions (for the user to sign off)

> **[HISTORICAL — NOT CURRENT STATE; SUPERSEDED by §B.3]** The conditions below
> were written for the pre-trace 5-exception state and are **void as a package**
> (their numbering no longer maps to reality). Current: J6/J7/F13 **VERIFIED**,
> J3 **VERIFIED** (proven negative — decided 2026-10-09, no longer "pending a
> semantic decision"), only **G9** unresolved. Do not act on the list below.

Gate may open if the user explicitly approves **all** of:

1. J6, J7 stay `INFERRED` with the limits above (no `dead`/`UNRECOVERABLE`
   relabel — not finding a call site ≠ the feature is absent).
2. F13 stays `UNKNOWN`; no specific JS engine is claimed.
3. G9 is accepted as a **separate UI test task**, not an RE gate item.
4. J3 stays `UNKNOWN`; `sapi.py` remains our fallback only, no native claim.
5. These 5 are recorded as **approved exceptions** in the Gate record.

Once approved, the RE Goal is "complete with 5 documented exceptions", and
Phase C may begin. **Until the user approves, Phase C does not start.**

## Backlog

| State | Task |
|-------|------|
| ready | Fix dead links + ADR table; remove stale model/count claims |
| ready | Verify observed UI structure vs native at implementation time |
| blocked | **Gate approval (user)** — required before Phase C (**only `G9` remains**, not the 5 exceptions above) |
| blocked | Phase C implementation — do not start without approval |
