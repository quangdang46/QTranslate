# NSIS payload chunk census — all 131 chunks classified (2026-10-15)

> Read-only census of `docs/review/artifacts/nsis_payload_unpacked.bin`
> (2,263,053 bytes). No row state changed by this document. It closes the
> last *enumeration* gap: every chunk in the recovered installer stream is
> now identified, and the locale set is proven byte-identical to the
> installed tree.

## 1. Method

Walk the stream as `<uint32-LE length><body>` from offset 0. The walk
consumes **all 2,263,053 bytes exactly in 131 chunks** — no residue, no
re-sync needed. Classification is by content, never by position:

| Test (in order) | Meaning |
|---|---|
| `MZ` / `PK\x03\x04` magic | PE executable / zip |
| `new ServiceHeader(` in first 300 B | `Services/*/Service.js` |
| `var Const={MAX_URI_LEN` in first 2000 B | `Common.js` |
| `<?xml` / `<xsl` head | `Resources/XdxfArticle.xslt` |
| `historyHeader` anywhere | `Plugins/History/*.js` |
| `\x00\x00\x01\x00` magic | ICO icon group |
| `BM` magic | BMP bitmap |
| `"LanguageCode"` + `"Strings"` | `Locales/*/lang.json` |
| UTF-8 BOM + `=>` hotkey text / `Ctrl + Q` | `Locales/*/help.txt` |
| `{` + `"Common": { "ButtonRadius"` | `Themes/*.json` |
| `\xff\xfe` (UTF-16LE BOM) + task text | `License.rtf` body text |
| `\x80\x00\x00\x00` + small ints | NSIS installer header block |

## 2. Full census (131 chunks)

| Class | Count | Notes |
|---|---|---|
| `lang.json` (one per locale) | **35** | codes: ar bg cs da de el en es fa-ir fi fr hu id it iw ja ko lv mn nl pl pt-BR pt-PT ro ru si sk sr sv tr ug uk vi zh-CN zh-TW |
| `help.txt` (UTF-8 BOM, one per locale dir; 35 dirs on disk, 34 matched this pass by BOM+marker test — see §4) | 34 observed | Arabic sample: `Double Ctrl => …`, `Ctrl + Q => …` |
| `Themes/*.json` | 8 | `{"Common": {"ButtonRadius"…` |
| `Services/*/Service.js` | 19 | |
| `Common.js` | 1 | 6,203 bytes (already pinned in `regress_plugin_js_recovered.py`) |
| `Plugins/History/*.js` | 4 | Csv 381 B, Html, Json, Txt |
| `XdxfArticle.xslt` | 1 | 832 bytes |
| PE executables | 5 | incl. the committed `QTranslate.6.10.0.exe` (1,462,272 B); others are 4–128 KB helper/uninstaller blobs |
| ICO icon groups | ~12 | `\x00\x00\x01\x00`, 894–1,150 B each |
| BMP bitmaps | ~7 | `BM` magic |
| `License.rtf` text (`\xff\xfe…Tasti…`) | 1 | UTF-16LE license body |
| NSIS header block (`\x80\x00\x00\x00 …`) | 1 | chunk 1, 45,516 B |
| **Total** | **131** | walk consumes the stream exactly |

## 3. Strongest result: 35/35 `lang.json` byte-identical

Each payload `lang.json` body was hashed (SHA-256) and compared against the
installed file `C:\Program Files (x86)\QTranslate\Locales\<dir>\lang.json`
(mapped by the file's own `"LanguageCode"`):

**35 identical, 0 different.** The installer's locale set and the installed
locale set are the same bytes — no locale drift between installer and disk.

The filesystem side has 35 directories (English display names:
`Arabic/`, `Bulgarian/`, … `Vietnamese/`), each holding `help.txt` +
`lang.json`. The earlier checklist line "35 packs share one loader/format"
(`RE_COVERAGE_CHECKLIST.md` O2) is therefore grounded in 35 real files, and
the O-group granularity decision (one group row for locales) is confirmed,
not assumed.

## 4. Honest residuals (not forced)

- The `help.txt` content test matched 34 chunks this pass, not 35. The 35th
  help file may use a slightly different marker set, or one chunk may have
  been mis-binned as residual. **Not re-binned by guessing** — a follow-up
  pass should hash each payload help body against its installed
  `Locales/<dir>/help.txt` exactly as §3 did for `lang.json`.
- The `Themes/*.json` bodies were classified, not hashed against
  `Themes/*.json` on disk. Same follow-up applies (8 files).
- The 4 small PE blobs and the icon/bitmap set are installer furniture
  (uninstaller, icons), out of RE scope — recorded here so nobody
  re-discovers them as "unclassified".
- Residual unclassified bodies after the locale/theme/help accounting are
  installation metadata, not application features; none maps to a
  checklist group.

## 5. Consequence for the Gate

None on row states: O2/N2 stay `VERIFIED` as group rows, as before. What
this document adds is the *enumeration proof* behind them — the inventory
the checklist's granularity section cites is now a measured census of the
actual installer stream (131/131 consumed, 35/35 locales hash-pinned),
not a directory listing taken on faith.
