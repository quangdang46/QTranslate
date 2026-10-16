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
4. Two operands resolved 2026-10-14 (follow-up decompile, no guesses):
   * `FUN_0043356c(this, 0x51f2a0)` is a **string-resource loader**: it
     requires `(param & 0xffff0000) == 0` (i.e. `0x51f2a0` is an id, not a
     pointer) and calls `FUN_004028a4(id & 0xffff)`, which loops
     `ATL::CAtlBaseModule::GetHInstanceAt` and calls
     `FindResourceExW(hModule, type 0x6 /* RT_STRING */, (id >> 4) + 1)`.
     So `0x51f2a0` is an RT_STRING id consulted before the request, and
     the sibling `(len, RVA)` table nearby (locale-pair strings
     `smn-fi`, `sms-fi`, `sq-al`, `sr-ba-cyrl`, `sr-ba-latn`, ...) is a
     **separate datum** — earlier session notes misread it as the lookup
     target; corrected here.
   * `FUN_004410bf(&local_c, &local_8, 0x522534, '\x01')` joins with a
     separator against the byte at `0x522534`; that byte is the tail of a
     longer native string whose head was not located (`wstr` from the
     guess point reads `Pane`). Recorded as unresolved, not decoded.
     **Resolved 2026-10-16 — it is NOT a string.** Resolving the RVA
     through the verified `0x401000` image base gives file offset
     `1185076`, whose bytes are `\xff\xff\xff\xff}\x98\x00\xfc\x01\x00\x00`
     — relocation/vtable filler. The nearby `Pane` strings are all
     Options-key names (`ShowTopPane`, `ShowMiddlePane`,
     `ShowServicesPane`) in the NULL-separated key table, which is what
     the guess point landed on; it is a **different datum**. So the third
     argument is a data slot (a length/offset), not a separator string,
     and the `'\x01'` fourth argument is the separator. Nothing here
     affects the port: the join is over RT_STRING ids, which the dictionary
     builder already reproduces.
5. **Body shape not proven.** The `Content-Type` header is present, so a
   form body is possible; but the decompile does not show whether the
   text travels as a `?text=` GET query (the port's form) or as a POST
   body. Recorded as open, not guessed.

> **CLOSED 2026-10-16 — by reading `.rdata`, not the decompile.**
> Native **POSTs a form body**. The image holds, in this order:
>
> ```
> text=                                              @1172340
> Accept-Encoding: gzip,deflate\r\nAccept-Charset: utf-8\r\n
> Content-Type: application/x-www-form-urlencoded\r\n
> /services/spellservice.json/checkText              @1172352
> speller.yandex.net
> pos  len  s
> ```
>
> Three facts settle it without tracing the body register: the literal
> `text=` sits immediately **before** (and apart from) the form-urlencoded
> header; the path carries **no `?`**; and `pos`/`len`/`s` — the response's
> suggestion fields — follow the host, confirming this is the spell block.
> A query-less path + a urlencoded header + a bare `text=` is a form body.
> `yandex_spell()` now POSTs `text=…&lang=…`; pinned by
> `tests/regress_spell_request.py` (15) and the rewritten
> `tests/regress_spell_headers.py` (11), which had been asserting the GET
> form this document left open.

## Consequence for the port

* `qtranslate/services/spell.py` docstring: the "not present verbatim"
  note is **withdrawn**, replaced with this evidence and the open
  body-shape question.
* `yandex_spell()` now sends the verbatim three headers (plus its
  User-Agent), instead of UA only.
* **2026-10-16:** the body shape is closed as POST — the port's GET was the
  one remaining unknown, so nothing is left open on this row.
* The row stays `VERIFIED` for the strings/headers.
