# Yandex spell request builder FUN_0042c968 — verbatim strings + headers

Date: 2026-10-14
Target: `docs/review/artifacts/QTranslate.6.10.0.exe`
(sha256 f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227)
Tooling: REA 6.4.0 -> Ghidra 12.1.4 (`rea search` / `rea xrefs` /
`rea decompile`, snapshot `qt6`)

## Why revisit this row

`docs/review/SPELL_SERVICE_STRINGS_2026-10-14.md` (an earlier note from
this same day) and the docstring of `qtranslate/services/spell.py` both
claimed the spell host/path were "not present verbatim in the binary ...
assembled at runtime", classifying them INFERRED. That claim is
**disproven**, and the row is corrected here.

## Evidence

`rea search --pattern spellservice --kind strings`:

```
0x51f380  /services/spellservice.json/checkText
```

`rea xrefs --address 0x51f380`: a single reference at `0x42c9fd`.
Decompiling `0x42c9fd` resolves the function entry `FUN_0042c968`:

```c
bool FUN_0042c968(undefined4 *param_1, int *param_2)
{
  bVar1 = FUN_0045c2f4();
  if (bVar1) {
    ... text escaped into local_8 (FUN_0043b0be) ...
    cVar2 = FUN_0043356c(&param_1, 0x51f2a0);   // a constant consulted
    if (cVar2 == '\0') { FUN_004335a4((int *)&param_1); }
    FUN_004410bf(&local_c, &local_8, 0x522534, '\x01');  // separator join
    FUN_0043366e(&param_1, &local_c);
    FUN_00401f21(&local_14, (uint *)
      L"Accept-Encoding: gzip,deflate\r\nAccept-Charset: utf-8\r\n"
      L"Content-Type: application/x-www-form-urlencoded\r\n");
    FUN_00401f21(&local_10, (uint *)L"/services/spellservice.json/checkText");
    FUN_00401f21(&local_c,  (uint *)L"speller.yandex.net");
    bVar3 = FUN_0045bea3(&local_c, &local_10, &local_14, &param_1, param_2);
    ...
  }
  return bVar3;   // false when FUN_0045c2f4() gates it off
}
```

### Facts

1. **Both the path (`0x51f380`) and the host `speller.yandex.net` are
   verbatim strings in the image.** The "assembled at runtime" premise is
   retired.
2. **The header block is verbatim and exactly three headers**, in this
   order:
   `Accept-Encoding: gzip,deflate` /
   `Accept-Charset: utf-8` /
   `Content-Type: application/x-www-form-urlencoded`.
3. The request goes through the shared `FUN_0045bea3(host, path, headers,
   body, out)` wrapper, i.e. the same HTTP path as the other providers.
4. `FUN_0043356c` consults constant `0x51f2a0` and `FUN_004410bf` joins
   with string `0x522534`; both are **untraced** — not decoded here.
5. **Body shape not proven.** The `Content-Type` header is present, so a
   form body is possible; but the decompile does not show whether the
   text travels as a `?text=` GET query (the port's form) or as a POST
   body. Recorded as open, not guessed.

## Consequence for the port

* `qtranslate/services/spell.py` docstring: the "not present verbatim"
  note is **withdrawn**, replaced with this evidence and the open
  body-shape question.
* `yandex_spell()` now sends the verbatim three headers (plus its
  User-Agent), instead of UA only.
* The row stays `VERIFIED` for the strings/headers; the body shape is the
  one remaining honest unknown.
