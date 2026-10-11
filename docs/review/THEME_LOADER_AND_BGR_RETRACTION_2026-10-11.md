# The theme loader, and a correction to my own "BGR nibble strings" claim

> Read-only. Two things: a **recoverable** fact G9's part (a) did not have
> (how native *selects* and *parses* a theme), and a retraction of a claim I
> made in `G9_THEMES_AND_DLU_2026-10-11.md` §2 that this work disproved.
>
> **G9 still stays `UNKNOWN` and the Gate stays `BLOCKED (1)`.** Part (b) is a
> screenshot diff. Nothing here changes a row's RE state or the tally.
>
> Measured with **Ghidra 12.1.4 headless, via REA 6.4.0**, on
> `docs/review/artifacts/QTranslate.6.10.0.exe`, SHA-256
> `f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227`.

## 1. Retraction: theme colours are **not** BGR nibble strings

`G9_THEMES_AND_DLU_2026-10-11.md` §2 says:

> Colours are BGR nibble strings, not `RRGGBB` — `ClientBackColor: "20"` in
> Flat Dark is `0x00202020` = `#202020`, and `"1"` in Holo Dark is
> `0x00000001`. This is the same reversed-slot format already documented for
> the dict-card header … before anyone writes `int("20", 16)` and gets 32.

**That is wrong, and it was never warranted by the evidence I had.** I
inferred byte order from short values, and every short value in every theme
is *grayscale* — so the two readings are indistinguishable for exactly the
data I looked at. The claim that survived was the one I wanted (a second
instance of a reversal pattern already found elsewhere) rather than one I had
shown.

The parser that decides it is `FUN_0046457a`, reached from the theme loader:

```
theme loader FUN_00464c2f
  └─ FUN_00464724   colour-string getter  (key absent -> 0xffffffff)
       └─ FUN_0046457a   string -> COLORREF
```

`FUN_0046457a` is hand-rolled and the decompiler's `CONCAT11(...)<<8 | ...>>8`
chain is easy to mis-read. So rather than trust my transcription twice, I
settled byte order from **outside the instruction stream**: a colour palette
must be a *designed* hue family, and one reading preserves that family while
the other destroys it.

Blue theme — its ten 6-digit values, which the same document calls the
QTranslate brand blue:

```
value      as literal #RRGGBB          through the COLORREF construction
1d8abd     #1d8abd   hue 199.1         #b0babd   hue 193.8
1586bb     #1586bb   hue 199.2         #b0b6bb   hue 207.3
0c4b73     #0c4b73   hue 203.3         #707b73   hue 136.4
469fc6     #469fc6   hue 198.3         #c0cfc6   hue 144.0
429fca     #429fca   hue 199.0         #c0cfca   hue 160.0
61add1     #61add1   hue 199.3         #d0ddd1   hue 124.6
...

literal hue spread:     5.0 degrees   (one blue palette)
COLORREF hue spread:   70.9 degrees  (cyan through grey-green)
```

The reversed reading also gives every Blue value `R = 0` and `G ≥ B`, i.e. it
turns a coherent blue palette into a family of desaturated cyan-greys. **The
strings are `RRGGBB`.** The `20` → `#202020` case in §2 happens to be right
for the wrong reason, and the `"1"` → `0x00000001` claim beside it is where
the error shows: native parses `1` as `#111111`, not as `0x00000001`.

### What the parser really does, and the port already matches it

`FUN_0046457a` accepts a leading `#`, skips leading whitespace, and accepts
**1, 2, 3 or 6** hex digits (anything else → `0xffffffff`):

| length | rule | native | port |
|---|---|---|---|
| 1 | duplicate the nibble three times | `b` → `#bbbbbb` | same |
| 2 | duplicate the byte three times | `20` → `#202020` | same |
| 3 | CSS expansion, per-channel | `09c` → `#0099cc` | same |
| 6 | as-is | `1d8abd` → `#1d8abd` | same |

Verified against the **real** `qtranslate/theme.py:_hex`, on **all 123
distinct colour strings in all 8 recovered themes**:

```
checked 123 distinct colour strings ... mismatches: 0
```

The port's `_hex` is correct, and the `len(set(v)) == 1` guard in it is a
clever route to the same place. The one thing native does that the port does
not is reject a *malformed* value; `_hex("")` returns `#000000` where native
returns `0xffffffff`, and there is no check at all for a string with illegal
hex or an unsupported length — `_hex("xyz")` silently produces `#`.

## 2. The theme loader, which G9's part (a) did not have

`FUN_00464c2f` (`this`, `param_1`) is the whole loader. Its structure:

```c
local_1c = <base dir>;                              // FUN_00402cbd
if (!FUN_0045b7b3((uint *)*param_1, &local_1c))     // "<base>\<ThemeName>.json"
    return 0;
if (GetFileAttributesW(local_1c) == 0xffffffff)     // INVALID_FILE_ATTRIBUTES
    return 0;                                       // <-- NO FALLBACK
if (!FUN_0043df32(local_1c, &local_24))  return 0;  // parse the JSON
piVar4 = FUN_0043f71a(&local_38, &local_24);        // -> JSON object
cVar3 = (**(code **)(*piVar4 + 0x20))(&local_18);
```

and `FUN_0045b7b3`, the path builder, is three appends:

```c
FUN_0045b1cf(L"Themes", param_2);        // <base>\Themes
FUN_00401f21(&local_8, param_1);         // + <ThemeName>
FUN_00402366(&local_8, L".json");        // + ".json"
FUN_0045b9d9(param_2, &local_8);         // join
```

**`FUN_0045b7b3` has exactly one caller** (`0x464c53`, inside `FUN_00464c2f`),
so this is the only way a theme file is named.

Four facts the port does not currently have:

1. **A missing theme file is a failure — but *not* a fallback to nothing,
   which is what I originally wrote here and had to correct.**
   `GetFileAttributesW(...) == 0xffffffff` → `return 0`, and the JSON-parse
   failure path is also `return 0`. The loader itself substitutes nothing.

   My first version said "so native has no built-in default to fall back *to*
   and its behaviour on a bad `ThemeName` is to render without theme values."
   **That second sentence is false, and §3a below shows why.** The default is
   not a *file*, so searching the image for a theme *name* cannot find it —
   `theme::DefaultColorTheme` is a **C++ class with a hardcoded
   `GetSysColor`-based initialiser**. See §3a.

2. **`Common` is optional.** Every `Common` key is read inside
   `if ((char)uVar6 != '\0')` after `FUN_004409c6(... L"Common" ...)`, so a
   theme file with no `Common` section is valid and simply leaves those
   fields untouched. Same guard shape for `Window`, `WindowButton`,
   `Button`.
3. **`ClientBackColor` and the `GroupBox*` colours use a dedicated getter**
   (`FUN_00464724`), while `ButtonRadius`/`PaintClassicFocus` use the int and
   bool getters. Absent colour key → `0xffffffff`, which is *distinct* from
   `0` — so the port storing `#000000` for a missing colour is not native.
4. **`Disabled` inherits `Normal`, `Hover` inherits `Normal`, `Pressed`
   inherits `Normal`** — and only if the child key is absent. The copy is a
   five-word struct copy (`for (iVar9 = 5; iVar9 != 0; iVar9--)`), i.e. a
   colour record is five dwords wide, not one. `window_colors()` in
   `theme.py` read `Window`/`<state>` directly and did not implement this
   inheritance, so an omitted state got zeros instead of `Normal`'s values.
   **This is a live path, not a defensive branch:** 20 section/state pairs are
   genuinely absent across the seven themes — `Window` × `Hover` in all
   seven, `Window` × `Pressed` in all seven, `Button` × `Hover` in four, and
   `WindowButton` × `Hover` in two (Holo Dark, Holo Light). `Disabled` is
   present everywhere, so the rule never fires for it on the shipped themes.

### 3a. The config's colour ints are `#RRGGBB` too — measured, not assumed

`ColorBack`/`ColorText`/`ColorFrame` arrive as **plain ints** through
`FUN_00440942`, which is a generic int getter returning the stored value
unmodified — no byte swapping at parse time. So the byte order was decided
by whoever *wrote* the file, and that is measurable from the defaults:

| key | default int | hex | as `#RRGGBB` | as `COLORREF 0x00BBGGRR` |
|---|---|---|---|---|
| `ColorBack` | 15790320 | `0x00f0f0f0` | `#f0f0f0` | `#f0f0f0` (symmetric) |
| `ColorText` | 0 | — | black | black |
| `ColorFrame` | 8023133 | `0x007a6c5d` | `#7a6c5d` | `#5d6c7a` |

Only `ColorFrame` can discriminate, and it settles it: **`0x7a6c5d` is exactly
`int("7a6c5d", 16)`**, which is what a writer produces from the string
`#7a6c5d`. A `COLORREF` writer would have emitted `0x005d6c7a` = 6122618
instead. The config therefore stores `#RRGGBB` as a plain int, and
`config.py`'s `"#%06x" % v` is correct.

Worth recording because it is the same class of error as §1's retraction —
reaching for a byte-reversal reading — arriving in a second place in the
same file family. Here the data settles it before anyone has to guess: the
two symmetric defaults cannot decide anything, and the one asymmetric value
decides it in the port's favour.

### 3b. The default theme is a **C++ class**, not a file — correcting §2 again

My §2 said native "has no built-in default to fall back *to*" on a bad
`ThemeName`. That reasoning came from searching the image for a theme
**name** and finding none. The absence is real; the conclusion drawn from it
was not, and this is the third instance of the same mistake in one document —
inferring a behaviour from the absence of a string rather than from the code.

`FUN_00464c2f` has exactly one caller, `FUN_004654ca`, which is a **factory**:

```c
int *FUN_004654ca(int *param_1) {
  if (*(int *)(*param_1 + -0xc) != 0) {            // ThemeName non-empty
    _Dst = (int *)FUN_004b3df0(0x1d0);             // alloc
    FUN_0044c0de(_Dst);                            // base ctor
    *_Dst = (int)common::ColorThemeFile::vftable;  // RTTI
    cVar1 = FUN_00464c2f(_Dst, param_1);           // load the JSON
    if (cVar1 != '\0') return _Dst;                // success -> the object
    (**(code **)(*_Dst + 8))(1);                   // release it
  }
  return (int *)0x0;                               // NULL on any failure
}
```

and its result is installed by `FUN_0044b44f`, which **does** substitute:

```c
void FUN_0044b44f(undefined4 *param_1, undefined1 param_2) {
  … release the current DAT_005491e8 …
  if (param_1 == (undefined4 *)0x0) {              // no theme loaded
    param_1 = (undefined4 *)FUN_004b3df0(0x1d0);
    FUN_0044c0de(param_1);
    *param_1 = (int *)theme::DefaultColorTheme::vftable;   // <-- the default
    FUN_0044c9a6(param_1);                                  //     populate it
  }
  *(undefined1 *)(param_1 + 0x71) = param_2;
  DAT_005491e8 = param_1;                          // install as active theme
}
```

So the chain is: **JSON theme if it loads, `theme::DefaultColorTheme`
otherwise** — never "no values." `DefaultColorTheme::FUN_0044c9a6` populates
the same `0x1d0`-byte layout the JSON loader fills:

```c
param_1[1] = 2;  param_1[2] = 1;                   // radii
DVar1 = GetSysColor(0xf);   …  param_1[7] = DVar1;   // COLOR_BTNFACE
DVar2 = GetSysColor(0x14);  …  param_1[9] = DVar2;   // COLOR_BTNHIGHLIGHT
CVar3 = FUN_0044a163(GetSysColor(0x15), 0x14); …      // 3DDKSHAD, brightened
param_1[0xb] = 0xffffffff;  …  param_1[10] = GetSysColor(8);   // WINDOWTEXT
DVar1 = GetSysColor(0x11);  …                              // COLOR_GRAYTEXT
… GetSysColor(5) …                                          // COLOR_WINDOW
param_1[0x11]=0x191919; [0x12]=0x5e5e5e; [0x13]=0xf9f9f9; [0x16]=0x393939;
param_1[0x17]=0x7e7e7e; [0x18]=0xffffff; [0x1b]=0x111111; [0x1c]=0x383838;
[0x1d]=0xc1c1c1; 0x65..0x6d the same eight greys again
```

**The default theme is the user's Windows system colours**, with the
remaining slots taken from eight hardcoded greys and derived through
`FUN_0044a163` — the very function the port already implements as
`adjust_brightness()`. All eight hardcoded values are achromatic
(`#191919`, `#5e5e5e`, `#f9f9f9`, `#393939`, `#7e7e7e`, `#ffffff`, `#111111`,
`#383838`, `#c1c1c1`).

Two consequences:

- **A sorry-default-theme port is not correct, and neither is unthemed.**
  `load_theme_native()` returning `None` is right about the *file* load and
  wrong about the *result*: the caller must then build the system-colour
  palette. My doc's "renders without theme values" would have shipped a black
  or default-faced popup where native paints the user's Windows theme.
- **Those values are not measurable on this host.** `GetSysColor` reads the
  Windows theme, and this machine is macOS — so the default palette's exact
  RGB is genuinely unmeasurable here while its *structure* is fully measured.
  What a port can do is use the platform's equivalent (Tk's own system
  colours, which is exactly what `tk_colors` already maps to).

This also explains §2's observation without it meaning what I said: the
default is a class, so **no theme filename exists in the image for a search
to find** — the absence I measured was real and the inference from it was
not.

## 3. Where `ThemeName` comes from — `Options.json`, under `Appearance`

`ThemeName` is a persistent config key, not a runtime constant. Its UTF-16LE
literal is at file offset `0x122014` / **VA `0x523014`**, in the same block
as the other config keys, and it has exactly two referencing sites in
`.text`: `0x45792d` (in `FUN_004561f0`, the `Options.json` **writer**) and
`0x459875` (in the **reader**).

Read via REA, the reader loads it with the **string** getter, where every
neighbouring key uses the int getter:

```c
FUN_00401f21(&stack0xffffff50, L"Appearance");
uVar6 = FUN_004409c6(root, &stack0xffffff50, &appearance);
if ((char)uVar6 != '\0') {
    FUN_00401f21(&stack0xffffff50, L"EnableWindowStyle");
    FUN_00440921(appearance, &stack0xffffff50, p + 0x1d8);   // bool
    FUN_00401f21(&stack0xffffff50, L"ThemeName");
    FUN_00440984(appearance, &stack0xffffff50, p + 0x1dc);   // string
    FUN_00401f21(&stack0xffffff50, L"PopupAutoSize");
    FUN_00440921(appearance, &stack0xffffff50, p + 0x1e0);   // bool
    FUN_00401f21(&stack0xffffff50, L"PopupAutoPos");         // bool
    FUN_00401f21(&stack0xffffff50, L"PopupAutoFocus");       // bool
    FUN_00401f21(&stack0xffffff50, L"PopupTimeout");         // int
    FUN_00401f21(&stack0xffffff50, L"ColorBack");            // int
    FUN_00401f21(&stack0xffffff50, L"ColorText");            // int
    FUN_00401f21(&stack0xffffff50, L"ColorFrame");           // int
    FUN_00401f21(&stack0xffffff50, L"Transparency");         // int
    FUN_00401f21(&stack0xffffff50, L"PopupWindowFrameThickness");
    FUN_00401f21(&stack0xffffff50, L"PopupIcons");
}
```

Two consequences worth recording:

- **`Options.json`, not `QTranslate.json`, is the settings file.** The
  writer's first act is `FUN_0045b3d7(base, L"Options.json", '\0')`. My
  G9 doc said "the recovered `QTranslate.json` (the config, later in the
  stream) can confirm the selected theme name" — **there is no
  `QTranslate.json` in this payload**, and the string does not occur in the
  exe in either encoding. That pointer was wrong.
- **`ColorBack`/`ColorText`/`ColorFrame` are separate config keys that sit
  in the same section as `ThemeName`.**

  **Correction, because my first version of this bullet over-claimed.** I
  wrote that "the two must be resolved rather than one replacing the other."
  I had not measured any resolution, and there is **none**. `StructRefs` (the
  one-pass offset scan) finds 19 functions touching these four keys, and the
  ones that touch several are the **Options dialog**, not a resolver:
  `FUN_004866f0` is a control-ID switch (`0x4eae` → `ThemeName`,
  `0x4f4d` → `ColorBack`, `0x4f4f` → `ColorFrame`, `0x283e` → `ColorText`)
  that stores each into its own field of the settings object;
  `FUN_00410c70` is the `OptionsWindow` constructor with a `PageAppearance`
  and three `windows::ColorButton` sub-objects — the colour pickers
  themselves.

  What the measurements actually support: the theme file owns
  `theme::ColorThemeFile`'s own fields, and `Appearance` holds four
  independent settings. The native main window is documented as using
  `Appearance` colours (`app.py`'s own `_default_colors` says the popup uses
  the theme); **which one wins where is still unmeasured**, and I am
  recording that rather than asserting a precedence the code has not shown
  me. This is the fourth time in this document that a tidy two-subsystem
  story outran the evidence.

## 4. Reproduce

```python
import struct, re
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()

# the loader's path builder and the Appearance keys, read from the image
exe = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
e = struct.unpack_from("<I", exe, 0x3c)[0]
assert exe[e:e+4] == b"PE\0\0" and e == 0x120       # PE32, i386
assert struct.unpack_from("<H", exe, e+4)[0] == 0x14c
assert "ThemeName".encode("utf-16-le") in exe
assert "Themes".encode("utf-16-le") in exe
for name in ("Blue", "Brackets", "Flat Dark", "Holo Dark",
             "Holo Light", "Metro", "Outlook Gray", "Photoshop Dark"):
    assert name.encode("ascii") not in exe and name.encode("utf-16-le") not in exe
assert b"QTranslate.json" not in exe
assert "QTranslate.json".encode("utf-16-le") not in exe
assert "Options.json".encode("utf-16-le") in exe          # the config file
assert b"Options.json" not in exe                         # wide only
```

The byte-order claim is reproducible without any decompilation, which is the
point — it should never have needed one:

```python
# Blue theme, hue spread under each reading
import math
vals = ["1d8abd", "1586bb", "0c4b73", "469fc6", "429fca", "61add1",
        "16688e", "1b7fad", "1b82b3", "0d7aad"]
def hue(rgb):
    r, g, b = (int(rgb[i:i+2], 16)/255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn: return None
    d = mx - mn
    h = ((g-b)/d) % 6 if mx == r else ((b-r)/d + 2 if mx == g else (r-g)/d + 4)
    return h*60
hs = [hue(v) for v in vals if hue(v) is not None]
assert max(hs) - min(hs) < 10          # one blue palette as written
```

The §3a config-int claim, and the 20 absent pairs, both offline:

```python
# ColorFrame is the only asymmetric default, so it is the only one that can
# decide the config's byte order.
assert 8023133 == int("7a6c5d", 16)          # exactly a #RRGGBB writer's output
assert 8023133 != 0x005d6c7a                 # not a COLORREF writer's
assert 15790320 == int("f0f0f0", 16)         # symmetric: uninformative either way

p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
import json, re
off = 0x97b30
absent = []
for _ in range(7):
    ln = int.from_bytes(p[off:off+4], "little")
    d = json.loads(re.sub(r"//[^\n]*", "", p[off+4:off+4+ln].decode("utf-8")))
    for sec in ("Window", "WindowButton", "Button"):
        for st in ("Hover", "Pressed", "Disabled"):
            if st not in d.get(sec, {}):
                absent.append((sec, st))
    off += 4 + ln
assert len(absent) == 20
assert absent.count(("Window", "Hover")) == 7
assert absent.count(("Window", "Pressed")) == 7
assert absent.count(("Button", "Hover")) == 4
assert absent.count(("WindowButton", "Hover")) == 2
```

The parser model, checked against the real port on all 8 themes:

```python
from qtranslate.theme import _hex

U8 = lambda v: v & 0xff
C11 = lambda hi, lo: (U8(hi) << 8) | U8(lo)

def native(s):                          # FUN_0046457a, len<=6 path
    n = [int(c, 16) for c in s]
    if len(n) == 1:
        bVar7 = U8((n[0] << 4) | n[0]); uVar10 = U8(bVar7) << 8; bVar6 = bVar7
    elif len(n) == 2:
        bVar7 = U8(n[1] | (n[0] << 4)); uVar10 = U8(bVar7) << 8; bVar6 = bVar7
    elif len(n) == 3:
        bVar7 = U8((n[0] << 4) | n[0]); uVar10 = U8(bVar7) << 8
        bVar6 = U8((n[1] << 4) | n[1]); bVar7 = U8((n[2] << 4) | n[2])
    else:
        return None
    cr = ((C11(bVar7, bVar6) << 8) | (uVar10 >> 8)) & 0xffffffff
    return "#%02x%02x%02x" % (cr & 0xff, (cr >> 8) & 0xff, (cr >> 16) & 0xff)

assert native("20") == _hex("20") == "#202020"
assert native("09c") == _hex("09c") == "#0099cc"
```

## 5. What this does not establish

- **Not** that the port's theme *rendering* is correct. `window_colors()`
  reads `Window/<state>` without the native inheritance rule and without the
  `#RRGGBB`-vs-`0xffffffff` distinction for absent colours, both of §2.
- **Not** a change to `G9_THEMES_AND_DLU_2026-10-11.md`. §2 of that document
  carries the false claim; this one is the correction, and the fix to that
  document is its owner's call, not mine.
- **Not** that `Options.json` contains a theme at all in a default install.
  It is the *only* place the key is read from, but no `Options.json` is in
  this payload, so the shipped default value is not measured here — only that
  no theme name is compiled in.
- **Not** G9's part (b). Still a Windows host plus a Screen Recording grant.
