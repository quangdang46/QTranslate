# Dictionary response chains: all 19 recovered Service.js read — 2026-10-16

Scope: finish reading `PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md`'s
open work — *"the files are recovered and 2 providers are read; 14
dictionary providers and the translate providers are unread; that is the
remaining work, and it is reading, not recovery."*

## What was read

Every one of the 19 `Service.js` files in the recovered NSIS payload
(`0x13af4`, 2,263,053 B, md5 `f368eb6a7aa730dd7b0380a7242f1668`), by
cutting each one at the NEXT `new ServiceHeader(` — **not** by a fixed
window:

| cut | what it decides |
|-----|-----------------|
| `new ServiceHeader(` boundary | which service owns a `buildUri`, a host, a capability mask |

A first pass windowed 4000 bytes past each header and produced **three
false findings** (already pinned in `regress_dict_request_uri.py`:
Urban "owns" Wikipedia's `/wiki/`; ImTranslator "owns" Multitran's
`/m.exe`; Yandex/Baidu hosts mismatch). The same trap recurs twice more
while reading the chains, both pinned as notes:

* `function serviceDictionaryResponse(...) { ... }` bodies contain
  nested `{}`, so "up to `\n}`" truncates the chain mid-way. The body is
  brace-counted instead. Without it, service 26 (youdao) returned no
  match at all and 10 of 19 services looked like they had no response
  chain.
* The bundle pastes each service's JS next to a **locale string table**
  (`[180, "…"]` arrays in Arabic). An extractor taking "the last array
  in the window" reports Arabic UI strings where `removeAttributes`'s
  five attribute names belong. Anchoring on the literal `Capability.`
  (for the mask) and on the function body (for the chain) avoids it.

## Checks performed, and their result

`tests/regress_dict_response_chain.py` (50 assertions) — for the six
dictionary providers with non-trivial chains plus youdao:

* the slice marker, its inclusive/exclusive flags, and the JS's own
  quoting (`'…'` vs `"…"`, `\x3c` escapes) — the port has all 9 markers;
* `removeElements` / `removeAttributes` / `removeTags` argument lists;
* `updateHtmlLinks` placement, and each provider's style wrap;
* youdao's five-attribute strip and its `"https://" + host + buildUri`
  link.

`tests/regress_service_capabilities.py` (19 assertions) — the capability
mask of all 19 services.

## No port bug found

Every chain matches. One case is pinned because it *looks* like a bug
and is not:

`Google Search` calls `removeTags(a,["h[3-6]"])`. This is not a typo
for a list of heading names: `regExpRemove` builds
`</?({0})[^>]*>` and formats it with `b.join("|")`, so the single member
`h[3-6]` lands in the regex as a character class matching `<h3>`..`<h6>`.
The port keeps `["h[3-6]"]` verbatim (`dictionary.py:1062`). Expanding it
to `["h3","h4","h5","h6"]` is extensionally equivalent for this input —
verified — so the faithful form is a fidelity choice, not a bug fix.

The suite also pins the **11-vs-4 dictionary capability gap** as a
non-bug: 11 services declare `Capability.DICTIONARY`, but the
Options/Services screen shows 4 rows. The 4 rows are the screen's
measured UI contract (the spec pins them), and the other 7 are still
registered and still ported — the native list is user-mutable
(`Add dictionary` / `Remove dictionary` are native strings recovered
from the exe), not hardcoded to 4.

## Status

The "17/19 unread" open item is closed: **all 19 recovered `Service.js`
files are now read against the port**, and 10 real bugs were found
across the whole effort (Promt/DeepL `SupportedLanguages` shifts,
Baidu/Google ASCII branch, `unquoteHtml` `&#39`, `parseJSON`,
`regExpRemove` flags, DeepL payload, and the dictionary HTML helpers).
No new bug in this pass.

G9 remains `UNKNOWN`; the gate stays `BLOCKED (1 unresolved)`. Phase C
is still not started.
