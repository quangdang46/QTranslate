# Current State — Audit of `qtranslate-re`

> Status: **PLANNING / READ-ONLY AUDIT.** Grounded in direct reads of the
> repository at commit `0cb0e78` (branch `main`) on 2026-10-09. No files were
> modified to produce this audit. Claims are tagged **[verified]** (read from
> code/tests now), **[doc-claimed]** (asserted by a repo doc, not re-run here),
> or **[assumed]** (inference, flagged as such).

## 1. Repository shape

| Path | Lines/Size | Role |
|------|-----------|------|
| `qtranslate/app.py` | ~4017 lines / 167 KB | Tkinter UI + hotkey + clipboard + orchestration (see §3) |
| `qtranslate/common.py` | 356 lines | 1:1 port of `Common.js` (RequestData/ResponseData, capability bitmask, helpers) |
| `qtranslate/config.py` | 161 lines | `Options.json` model, hotkey decode, service ids/order |
| `qtranslate/session.py` | 179 lines | Session/token scrape (Bing, Promt), net timeout/proxy |
| `qtranslate/services/` | 12 provider modules + `dictionary.py` + `ocr.py` + `spell.py` | provider ports |
| `qtranslate/win32app.py` | 203 lines | Native Win32 DLG129 re-creation (pywin32) |
| `qtranslate/{theme,locale,history,layout,xdxf,tts,player,sapi,headless,exclusions}.py` | small | feature modules |
| `docs/NATIVE_ARCH.md` | 1649 lines | native binary RE analysis |
| `tests/` | 4 files | `live_providers.py`, `ui_match.py`, `smoke_dict.py`, `live_bass.py` |

**[verified]** Language: Python, Tkinter UI, stdlib `urllib` for HTTP; optional
deps only (`keyboard`, `pyperclip` required; `pystray`, `Pillow`, `comtypes`,
`playwright` optional — `requirements.txt`).

**License [verified]:** MPL-2.0 (`README.md:69`). Clean-room RE for education.

## 2. What actually works today

### 2.1 Providers [doc-claimed, from `tests/LIVE_RESULTS.md` + README]
- **LIVE-OK (verified against real endpoints on 2026-10-07/08):** Google
  translate + TTS, DeepL detect/translate, Microsoft/Bing (via shared cookie
  jar), Yandex (android variant), Baidu detect+suggest, Naver/Papago
  (text/tts/dictionary), Youdao (translate_web + dictionary), Reverso
  translate, and dictionaries Oxford / Lingvo / Urban / Wikipedia / Multitran /
  WordReference (headless). `21/21 live OK` (`LIVE_RESULTS.md:27`).
- **Known dead / token-walled** (`LIVE_RESULTS.md:57-72`): Babylon translate
  (SSL dead), ImTranslator (ASMX retired), Google Search (JS+consent wall),
  Baidu `/transapi`, Youdao translate_o, Promt `paft`, plus Yandex TTS and
  Baidu TTS hosts.
- These results were **not re-run during this audit** — treat as doc-claimed.

### 2.2 Test suites [verified as files; results doc-claimed]
- `tests/live_providers.py` — hits real endpoints (network-dependent).
- `tests/ui_match.py` — **structural** checks of `app.py`: it constructs
  `A.App(root)` and asserts strings/order/defaults by inspecting objects and
  even the source text of `app.py` (`ui_match.py:57-59`). It is a
  *string/structural* match, **not** pixel or screenshot comparison.
- `tests/smoke_dict.py` — import + offline helper assertions.
- README claims `97/97 UI`, `21/21 live`, `9/9 smoke` (`README.md:28-34`) —
  counts differ across CHANGELOG entries (`82/82`, `40/40`, `46/46`…), a sign
  the suite grew over time; **not re-run here**.

> **Honesty note:** "97/97 UI match" does **not** mean the UI looks like the
> native window. The user's own assessment is that the UI "chả giống tý nào"
> (doesn't look alike at all). The test verifies *structure/strings/order*, not
> visual fidelity. Any future UI claim must distinguish these.

## 3. `app.py` — where boundaries blur [verified]

Full structural audit (delegated, line-cited):

- **`class App` owns everything** (`app.py:581-3335`): main window, popup,
  Options (`open_options` is one ~1073-line method, `app.py:1742-2815`),
  History, Dictionary, OCR, virtual keyboard.
- **Provider dispatch is dict-based but hardcoded:** `TRANSLATORS` (`:221`),
  `DICTS` (`:234`); detection is a **hardcoded tuple** (`:496-503`). A separate
  `services/__init__.py` `REGISTRY` registers only 5 providers — **three
  sources of truth**, none complete.
- **Orchestration interleaved with widgets:** `on_hotkey` (`:3337`) reads
  `app.current()` then writes `app.src`/render/history; same for the clipboard
  monitor (`:3407`) and `_replace` (`:3592`). `show_popup._to_main`
  (`:3999-4008`) builds a **second `tk.Tk()` + `App`** inside a popup callback.
- **Windows coupling:** `ctypes.windll.user32` (`:3419`, `:3790`), `winreg`
  autostart (`:1788`), `comtypes` SAPI (`:1251`), `keyboard` global hooks
  (`:3668`), `PIL.ImageGrab` (`:3277`), hardcoded `C:/Program Files (x86)/…`
  (`:1806`). Note: the **native cursor-hook / SendInput capture path is not
  ported** at all (no `win32gui` here).

## 4. Working tree — do not overwrite

**One uncommitted file: `qtranslate/app.py`** (`git diff --stat`: 2 insertions,
2 deletions). The change is in `on_hotkey` (`app.py:3356-3359`):

```python
svc, _, tgt, src = app.current()          # was: svc, _, tgt, _ = app.current()
res = do_translate(svc, text[:5000], tgt, src,   # was: ... tgt, "auto",
                   app.opt_detect.get(), app.opt_backtr.get())
```

So the popup hotkey now forwards the **selected source language** instead of
forcing `"auto"` (auto-detect). Rationale per the planning thread: respect the
user's chosen source.

**[verified] divergence to preserve awareness of:** the `"auto"` literal still
appears at `app.py:3449` (clipboard monitor), `:3593` (`_replace`), and
`on_listen_hotkey` `:3514` ignores `src`. This is inconsistent — the migration
must decide one behavior for all capture paths, and the compatibility matrix
records it. **Do not reset or overwrite this change.**

## 5. Native RE coverage [doc-claimed, from `docs/NATIVE_ARCH.md`]

`NATIVE_ARCH.md` (1649 lines) documents, with function addresses, RTTI classes
and dialog ids: startup/message-loop/hotkey, 3-mode capture, translate
orchestrator + provider executor, JS boundary (`IActiveScript` CLSIDs), render
(RichEdit/layout/popup), dictionaries/XDXF, TTS (BASS), speech-in
(BASS_RecordStart + FLAC), OCR, tray, Options/settings, history/export, crash
reporter, updater, spell, keyboard-layout convert, i18n, theme.

Ratio-style evidence it records (`NATIVE_ARCH.md`, doc-claimed): `123/124` live
Options.json keys matched (`:714`), `9/9` Options pages on real Options.json
(`:77`), `28/35` lang.json parse (`:1073`), 8 themes load (`:1527`), 17
providers (`:1648`).

## 6. Known gaps and dead ends

These are stated **where** they are true; several originate in `CHANGELOG.md` /
`README.md`, *not* in `NATIVE_ARCH.md` (verified by audit — do not misattribute).

| Gap | Where stated | Impact |
|-----|--------------|--------|
| Cursor-hook mouse icon not ported | `CHANGELOG.md` (Flags coverage) | mouse-mode hover UI |
| Drag-and-drop needs `tkinterdnd2` | `CHANGELOG.md` | file DnD |
| "Extended" feature absent in modern Options.json | `CHANGELOG.md` | legacy menu only (`NATIVE_ARCH.md:727` label) |
| TTS phonetic: no API | `CHANGELOG.md` | "Read phonetically" limited (`NATIVE_ARCH.md:736`) |
| Updater dead (server retired 2022) | `NATIVE_ARCH.md:1376` | update check is dead code |
| `tlookupv3` dictionary 401-walled | `NATIVE_ARCH.md:1454` | Bing standalone dict |
| `refresh_tkk()` not ported (defaults `"0.0"`) | `NATIVE_ARCH.md:1464` | Google token freshness |
| Speech endpoint needs key+FLAC | `NATIVE_ARCH.md:1638` | speech-input blocked |
| Native capture (mouse/mode 2, SendInput synth) not ported | `app.py` audit | core to native UX |
| UI visual fidelity low | user assessment | see §2.2 honesty note |

## 7. What is verified vs not — summary

- **[verified now]** file/module structure, dispatch tables, Windows couplings,
  the uncommitted diff, test files' existence and their *type*.
- **[doc-claimed]** all "N/ N green", "LIVE-OK", percentages, and native RE
  addresses — read from docs; not re-executed in this audit.
- **[assumed]** macOS behavior of adapters — never tested.

> **This audit is NOT an RE-completion artifact.** The `doc-claimed` bucket
> above is exactly the evidence that **cannot** be used to open the Gate
> (`PROJECT_VISION.md` §0). Structure and presence are not behavioral proof, and
> a line written in a document is not self-validating evidence. Native RE
> coverage lives in `RE_COVERAGE_CHECKLIST.md` and is tracked on its own axis;
> this file records the **Python-side** state only.

## 8. Implications for the redesign

1. The three-source-of-truth registry and hardcoded detect tuple **must** be
   unified (see `ARCHITECTURE.md` §3.2).
2. `app.py` cannot be the Core; it becomes UI host components.
3. The `"auto"` vs `src` inconsistency is a **real compatibility decision**,
   not just a diff to preserve.
4. Reliability is absent as a shared layer — the biggest user-facing gap.
5. Several providers are genuinely dead; the matrix must record dead-vs-fixable
   so the redesign doesn't promise to resurrect retired servers.
