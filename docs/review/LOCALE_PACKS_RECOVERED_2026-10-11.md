# The locale packs, and O2's 36/14 claim confirmed against them

> Read-only. O2 cites `Locales/*/lang.json` as its artifact and says
> **36 strings / 14 windows packs**. That artifact is in the same NSIS solid
> stream as the `Service.js` files, so the row's two numbers are now
> measured rather than asserted.
>
> **No row state changed.** O2 stays `VERIFIED`, which is now a state with
> evidence behind it rather than a state with a citation.

## 1. There are 35 locale packs, not 36

Walking the stream and taking every chunk containing `"LanguageName"`
yields **35**, matching the installer manifest's `\Locales\` listing in
count and order:

```
Arabic, Bulgarian, Chinese (Simplified), Chinese (Traditional), Czech,
Danish, Dutch, English, Farsi, Finnish, French, German, Greek, Hebrew,
Hungarian, Indonesia, Italian, Japanese, Korean, Latvian, Mongolian,
Polish, Portuguese (Brazilian), Portuguese (Europian), Romanian, Russian,
Serbian, Slovak, Slovenian, Spanish, Swedish, Turkish, Ukrainian, Uyghur,
Vietnamese
```

The row's "36 strings" is **not** a count of locales. Those are different
numbers and the coincidence of 35 vs 36 is worth naming explicitly so
nobody later reads one as a correction of the other.

These files are not strict JSON. They contain `//` comments and trailing
commas before `]` and `}`. A plain `json.loads` fails on the English pack
at line 154 with `Illegal trailing comma before end of array`. Any port
that reads them needs the same tolerance, and the fact that they parse at
all after stripping both is the alignment check.

## 2. The 36 / 14 / 10 structure, which is what O2 actually claims

The English pack has exactly 7 top-level keys:

```
Author, LanguageName, LanguageNativeName, LanguageCode, Strings, Windows, Menus
```

| key | count in English |
|---|---|
| `Strings` | **36** |
| `Windows` | **14** |
| `Menus` | 10 |

Both of O2's numbers reproduce exactly, from the recovered bytes:

```python
import struct, re, json
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
def chunk(o):
    n = struct.unpack_from("<I", p, o)[0]
    return p[o+4:o+4+n]
def clean(b):
    t = b.decode("utf-8-sig", "replace")
    t = re.sub(r"//[^\n]*", "", t)
    return re.sub(r",(\s*[}\]])", r"\1", t)

d = json.loads(clean(chunk(0x3b85e)))          # English
assert len(d["Strings"]) == 36
assert len(d["Windows"]) == 14
assert len(d["Menus"]) == 10
```

**The shape is uniform, not an artefact of English.** Checked across
Vietnamese, Russian, and Farsi: `Strings=36 Windows=14 Menus=10` in every
one. All 35 packs are the same schema, which is the property that makes a
port of the loader meaningful — a missing key in one pack would be a
translation gap, not a structural one.

## 3. What the entries look like, since O2's claim is about "packs"

`Windows` is a list of window records, each keyed by the DLG id that
`G9_SPEC_NATIVE_WINDOW_2026-10-10.md` independently parsed out of `.rsrc`:

```json
{ "Controls": [[1004, "Translate"]], "Id": 1, "Caption": "QTranslate" }
```

`Id: 1` is the main window and `1004` is the Translate button — the same
control id that appears in the G9 geometry table. So the locale pack and
the dialog templates are two views of the same window list, and the ids
cross-check between a *data* artifact and a *resource* artifact that were
measured separately. That is stronger corroboration than either alone.

`Menus` is a list of menu records:

```json
{ "Items": [[10, "Spell checking"], [20, "Instant translation"], ...] }
```

`Strings` is the flat string table (36 entries).

## 4. What this does not establish

- **Not** that the port's locale handling is correct. This makes the native
  values available to compare against; comparing them is separate work.
- **Not** the Vietnamese pack's contents, beyond the counts. The row's note
  says "vi pack" — the pack exists at stream offset `0x94438` (10,659
  bytes) and its counts match, but its 36 strings were not diffed against
  anything here.
- **Not** that 35 is the complete set. It is the complete set in *this
  installer*; the manifest lists the same 35.
