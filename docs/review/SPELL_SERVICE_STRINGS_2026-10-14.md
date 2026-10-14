# Native spell-service strings — REA hit at 0x51f380 (2026-10-14)

> Closes part of the Spell entry tension (matrix F row: "real spell entry not
> read"; port docstring says the hosts/paths "are not present verbatim in the
> binary"). That port claim is **wrong for Yandex**, and this note corrects it
> with a measured hit.

## Method + result

`rea search QTranslate.6.10.0.exe spellservice --provider ghidra`
against `docs/review/artifacts/QTranslate.6.10.0.exe`
(md5 `a7c1278d831b9dd8261b55b82eaaffc0`),
evidence `ev_3d52020eb4f441dacc1c54872f255731c079ba17815915d6f527aab8926daffb`:

```
[{"address": "0x51f380", "value": "/services/spellservice.json/checkText"}]
```

One hit. `0x51f380` is inside `.rdata` (`0x50d000..0x542200`), i.e. a
string constant in the image — **the path IS present verbatim in the binary**,
contrary to `qtranslate/services/spell.py`'s docstring.

## What this changes

| Item | State |
|------|-------|
| `spell.py` docstring: "the literal hosts/paths are not present verbatim in the binary (they are assembled at runtime)" | **partly false** — the Yandex *path* is verbatim at `0x51f380` |
| `spell.py` URL: `speller.yandex.net/services/spellservice.json/checkText` | **confirmed** as the native path string |
| yandex_spell() behaviour | `behaviour-verified` (port) unchanged — no code change made here |
| Matrix F spell row "real spell entry not read" | still open: this is a **string hit, not a decompile of the spell entry point** |

## What this does NOT establish

- The **host** prefix (`speller.yandex.net`), the query parameter names, and
  the response parsing are not proven by this hit. Only the path fragment is.
- No decompile of the spell function(s) was done. The port's spell entry
  remains INFERRED in the matrix sense, and the docstring's statement about
  how the URL is assembled is now known to be inaccurate for the path part
  and unmeasured for the rest.
- `GoogleSuggest`'s `/complete/search?client=firefox` was **not** searched
  here; do not assume it is present or absent without that search.
