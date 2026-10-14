# Promt `/api/pageLoad` session call (FUN_0045f372)

Date: 2026-10-14
Target: `C:\Program Files (x86)\QTranslate\QTranslate.exe` (6.10.0),
recovered artifact `docs/review/artifacts/QTranslate.6.10.0.exe`
Tooling: REA 6.4.0 -> Ghidra 12.1.4 (`rea search` / `rea xrefs` /
`rea decompile`, snapshot `qt6`)

## Evidence

`https://www.online-translator.com/api/pageLoad` is a real string at
`0x52aa98`, referenced once, from `0x45f3c1` inside `FUN_0045f372`.
The decompiled body (address `0x45f3c1` resolves into that function):

```c
FUN_004023f1(&local_c,
  (uint *)L"Content-Type: application/x-www-form-urlencoded; charset=UTF-8\n"
          L"Accept: */*\nXSRF-TOKEN: %s\nCookie: %s");
FUN_00447132(&local_14, (uint *)"pageIx=0&v=1");
FUN_00401f21(&local_8,
  (uint *)L"https://www.online-translator.com/api/pageLoad");
FUN_00442d92(local_30, &local_8, &local_c, DAT_00549444,
             local_14, *(undefined4 *)(local_14 + -0xc), 0);
...
uVar3 = FUN_004a964f(local_d4, local_30);
if (((char)uVar3 != '\0') && /* status */ == (int *)0xc8) {   // 200 only
  FUN_00401f21(&local_8, (uint *)L"_ppup");
  bVar1 = FUN_0045451a((int)local_d4, &local_8, param_1);
  ...
}
```

### Facts read off the decompilation

1. **The request is `POST /api/pageLoad` with the literal body
   `pageIx=0&v=1`** -- `pageIx` is constant 0, `v` is constant 1
   (not the `v=2` the current web client sends for translations).
2. **Headers are exactly four**: the static `Content-Type`, `Accept: */*`,
   plus `XSRF-TOKEN` and `Cookie` interpolated from the current session.
3. **HTTP 200 is required** (`0xC8`); any other status fails the call.
4. **On success it extracts `_ppup`** (FUN_0045451a), the same field the
   port's new `ppup()` returns.
5. The call lives on the Promt EXTENSION's session path (i.e. order is
   scrape -> pageLoad -> translate), but a failure is non-fatal.

## Consequence for the port

* `qtranslate/services/promt.py` gains `page_load(paft, xsrf, cookie,
  opener)` reproducing 1-4 byte-for-byte (body, headers, URL, 200-only,
  `_ppup` extraction via `ppup()`), and `session()` now chains it after
  the scrape on the same opener, ignoring its result (rule 5).
* When the caller passed their own opener, the jar is invisible to us --
  an empty explicit Cookie is passed and the opener's own processor
  attaches the cookies (documented reason, not hidden).
* `tests/regress_promt_pageload.py` (11 assertions) pins the URL, body,
  headers, response parsing and the failure contract headlessly.
