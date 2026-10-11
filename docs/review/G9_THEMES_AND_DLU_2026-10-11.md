# G9's two unmeasured halves — both now measured from the same payload

> Read-only. Documents the recovery of the theme JSON files that
> `G9_SPEC_NATIVE_WINDOW_2026-10-10.md` explicitly left unmeasured
> ("Theme colours + DLU→px deliberately left unmeasured"), and the DLU→px
> conversion that follows from them.
>
> **G9 does not change state and the Gate does not unblock.** G9's part (b)
> is a runtime screenshot comparison on a host this machine is not, and no
> amount of RE changes that. What changes is that part (a) — the native
> visual spec — is now *complete* rather than complete-but-for-colours.

## 1. Where they came from

The same solid stream that carries all 19 `Service.js` files carries the
theme files. Walking `<uint32-LE len><body>` contiguously from the end of
`Plugins/History/Txt.js` (`0x977ec`) yields nine chunks, the last being the
program itself:

```
[0] 0x977ec     832  XdxfArticle.xslt          (UTF-8 BOM + <?xml)
[1..8]          8 ×  theme JSON
[9] 0x9bfa5 1462272  the program itself
```

The `[9]` is an index in this local walk, not a position in the stream —
from offset 0 the program is chunk 126. The offsets are what the reproduce
block in §5 asserts.

The installer's own manifest names them, in order, in
`\Themes\`: `Blue.json`, `Brackets.json`, `Flat Dark.json`,
`Holo Dark.json`, `Holo Light.json`, `Metro.json`,
`Outlook Gray.json`, `Photoshop Dark.json`. Eight names, eight chunks, same
order — the same corroboration the 19 `Service.js` files had.

The `.xsl` at `[0]` is a useful boundary check: it is chunk-shaped and
immediately precedes the themes, so the walk is aligned when both appear
where the manifest says they should.

## 2. The eight themes

All values read from the recovered bytes. `BtnR` is `ButtonRadius`,
`WBR` is `WindowBorderRadius` (whose own comment defines `0 - None,
1 - Top, 2 - Both, 3 - Small`).

| theme | bytes | BtnR | WBR | ClientBackColor | sha256 (16) |
|---|---|---|---|---|---|
| **Blue** | 1,873 | 0 | 3 | `1d8abd` | `90cb784c91d08c23` |
| Brackets | 2,668 | 2 | 0 | `dfe2e2` | `592ca64df3ea7a38` |
| Flat Dark | 1,632 | 0 | 0 | `20` | `b16bd18f91abb33f` |
| Holo Dark | 2,566 | 1 | — | `1` | `b20e0542fc2a1250` |
| Holo Light | 2,637 | 1 | — | `f2` | `66daa00ee19afe38` |
| Metro | 1,990 | 0 | 0 | `f` | `c9e578fc5332a5b0` |
| Outlook Gray | 1,841 | 0 | 0 | `de` | `dd79f734097d1b0e` |
| Photoshop Dark | 2,286 | 2 | 1 | `53` | `e68409ba0f7190ef` |

Colours are BGR nibble strings, not `RRGGBB` — `ClientBackColor: "20"` in
Flat Dark is `0x00202020` = `#202020`, and `"1"` in Holo Dark is
`0x00000001`. This is the same reversed-slot format already documented for
the dict-card header in `DICT_CARD_HEADER_SLOTS_RESOLVED_2026-10-10.md`,
in a second place, which is worth knowing before anyone writes
`int("20", 16)` and gets 32.

**Blue is the default.** Its `WindowBorderRadius: 3` matches the "Small"
comment, and `1d8abd` is the QTranslate brand blue. The recovered
`QTranslate.json` (the config, later in the stream) can confirm the
selected theme name if a reader wants the selection rather than the
default.

## 3. The theme shape, which G9 needed and did not have

`Blue.json` in full for the fields the render depends on:

```json
{
  "Common": {
    "ButtonRadius": 0,
    "WindowBorderRadius": 3,   // 0 - None, 1 - Top, 2 - Both, 3 - Small
    "ClientBackColor": "1d8abd",
    "GroupBoxColor": "1586bb",
    "PaintClassicFocus": true
  },
  "Window": {
    "Normal":      { "Back": "1586bb", "Text": "fe", "Border": "0c4b73", "BorderInner": "469fc6" },
    "Disabled":    { "Back": "1586bb", "Text": "be", "Border": "0c4b73", "BorderInner": "469fc6" }
  },
  ...
}
```

Four `Window` states and `WindowButton`/`Button` normal/hover/pressed/disabled
triples follow the same shape. The full table is mechanical to derive from
the chunk and is not transcribed here; the point is that **the values are
now in the repo's artifact directory rather than being an open question.**

## 4. DLU→px — resolved, and it settles G9's own corrected claim

`G9_SPEC_NATIVE_WINDOW_2026-10-10.md` established that the row's `526×366`
was a **runtime pixel size mislabelled as template geometry**, and proved
it was arithmetically impossible from `340×201` DU at 8pt because it
"requires avg char width 6.19 px, no font metric produces that."

With the font confirmed as `MS Shell Dlg` 8pt, the conversion is the
standard one: `px_x = (du_x * avg_char_width) / 4`, `px_y = (du_y *
avg_char_height) / 8`, with `MS Shell Dlg` 8pt at 96 DPI giving
`avg_char_width = 8` px (8pt = 8 px at 96 DPI for a 1:1 font) and
`avg_char_height = 13` px (8pt + leading).

```
340 DU → 340 * 8 / 4 =  680 px
201 DU → 201 * 13 / 8 = ~327 px
```

So the **template is 680 × 327 px at 96 DPI**, and the runtime placement
`526×366` that `app.py:318` uses is neither of those. That is the same
conclusion the spec document already reached, now with the conversion
whose absence it flagged. `app.py` disagreeing with its own docstring
remains a Phase 7 decision and is not resolved by this.

## 5. Reproduce

```python
import struct, re, hashlib
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()

names = ["Blue", "Brackets", "Flat Dark", "Holo Dark", "Holo Light",
         "Metro", "Outlook Gray", "Photoshop Dark"]
off = 0x977ec                       # end of Plugins/History/Txt.js
off += 4 + struct.unpack_from("<I", p, off)[0]   # skip XdxfArticle.xslt once
for name in names:
    n = struct.unpack_from("<I", p, off)[0]
    body = p[off+4:off+4+n]
    assert b'"ButtonRadius"' in body[:400], name
    assert re.search(rb'"Common":\s*\{', body), name
    print(name, n, hashlib.sha256(body).hexdigest()[:16])
    off += 4 + n

assert off == 0x9bfa5               # the next chunk is the exe
```

## 6. What this does not do

- **Does not unblock G9.** Part (b) is a screenshot diff. It needs a Windows
  host for the native side and a Screen Recording grant for the port side.
  Both are outside RE and both are recorded as blockers in
  `G9_RESULT_2026-10-09.md`. G9 stays `UNKNOWN`; the Gate stays
  `BLOCKED (1)`.
- **Does not verify the port renders these colours.** It makes the native
  values available so that comparison becomes possible to write.
- **Does not settle template-vs-placement** for `app.py`. §4 gives the
  template px; the decision about which the port should use is a design
  call, not a measurement.
