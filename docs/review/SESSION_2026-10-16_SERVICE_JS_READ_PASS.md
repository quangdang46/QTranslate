# 2026-10-16 — the reading pass over all 19 `Service.js` + `Common.js`

Scope: the open item the checklist named — *the files are recovered and 2
providers are read; the remaining work is reading the 17 unread `Service.js`
files* — plus the shared `Common.js` that every one of them calls into.

Method throughout: the JS is **read from the artifact, never executed**.
Every comparison uses an independent reference written inside the test, so a
mistake in the port and a mistake in the reference cannot agree.

## The windowing trap, three more times

The first pass found three false findings by windowing a fixed byte range
after each `new ServiceHeader(`. This pass hit the same class of error three
more times, and all three are pinned so they are not repeated:

1. **`serviceDictionaryResponse` bodies contain nested `{}`**, so
   "up to `\n}`" truncates the chain. Extracted by brace counting instead —
   with the window, 10 of 19 services looked like they had *no* response
   chain at all.
2. **The bundle pastes an Arabic locale table after each service's JS**, so
   "the last array in the window" reports `[180, "…"]` UI strings where
   `removeAttributes`' five attribute names belong.
3. **Native `stringFind` branches on `typeof b === "string"`** — a plain
   string takes `indexOf`, a compiled regex takes `match`. A harness that
   hands the model a raw string while handing the port a compiled pattern
   compares two different native paths and reports 11 phantom divergences.

Rule: **cut at the next header; count braces; match native's own branch.**

## Four real port bugs found

| # | where | what was wrong | divergence |
|---|-------|----------------|------------|
| 1 | `common.remove_attributes` | pattern had `\\.` where native's regex is `\.` | `<a href="a\"b">t</a>` → native `<ab">t</a>`, port `<a>t</a>` |
| 2 | `yandex._use_dictionary` | `str.split()` where native splits on `/\s+/` | `"   a b c"` has 4 JS members (rejected); `.split()` saw 3 (accepted) |
| 3 | `google_translate.tk` | `int(seg)` where native is `Number(seg)\|\|0` | `tk('hello','abc.def')` raised `ValueError`; native signs with a 0 seed |
| 4 | `baidu.sign` | identical coercion | `sign('hello','abc.def')` raised; native signs with a 0 seed |

1 survived every earlier vector test because it needs a backslash-quote
inside a quoted attribute value. 3 and 4 were latent crashes on a
plausible scraped-token shape. 2 changed which providers were consulted for
leading-whitespace text.

Bugs 3 and 4 were the same native rule spelled twice, so the coercion moved to
`common.js_number` and both providers now share it.

## Two documented divergences re-checked (and kept)

* **Google's romanization slot.** Native reads `e[2]` (guard `2 < e.length`);
  the port reads `e[3]` because the live shape puts the value there and
  native's own slot is `null`. Pinned as a *recorded divergence* — the
  suite refuses to let the docstring's explanation be deleted.
* **Microsoft's `tryFetchingGenderDebiasedTranslations=true`**, absent from
  the recovered body, a live fix for post-6.10 Bing. Was in the port's
  docstring but **not** in the checklist; now recorded in E3 and pinned so
  both facts stay true at once.

## Verification added

| suite | assertions / comparisons | what it pins |
|-------|--------------------------|--------------|
| `regress_dict_response_chain` | 50 | 6 dictionary chains + youdao: markers, inclusive flags, `remove*` lists, style wraps |
| `regress_translate_response_chain` | 45 | all 9 translate chains: `ResponseData` arity, `getSourceLanguage` shapes, dt set |
| `regress_service_capabilities` | 19 | all 19 capability masks; the 11-vs-4 DICTIONARY gap as a non-bug |
| `regress_common_fuzz` | 150,060 | differential fuzz of 5 `Common.js` helpers against a model transcribed from the JS |
| `regress_reg_exp_patterns` | 12 | the three `regExpRemove` patterns vs the literal read out of the artifact |
| `regress_js_number` | 44 | the shared seed coercion, in both providers |
| `regress_microsoft_request` | 21 | the request body and its one documented divergence |

`tools/gate_artifact_audit.py` is new: it enforces the Gate's
"concrete artifact" clause, which nothing tooled before. 147 of 147 VERIFIED
rows now pass.

## Status

95 regression suites + the UI-spec audit, all green. Full suite: 95/95
passing.

**The 19-`Service.js` reading pass is closed** and `Common.js` is fully
compared. Four port bugs found and fixed; three windowing-class false
findings pinned; two divergences re-confirmed as deliberate and documented.

**G9 remains `UNKNOWN`, so the Gate remains `BLOCKED (1 unresolved)`.** The
Gate's concrete-artifact clause now holds, but G9 is not affected by this
pass — it is a runtime screenshot-diff that RE cannot provide and this
machine cannot run. Phase C is still not started and still needs explicit
approval.

## Local commits, not pushed

Commits are on `main`, ahead of `origin/main`. The push token from earlier
had been revoked by the time it was used, and tokens do not survive turns,
so **nothing has been pushed**; a fresh token is needed for
`git push <remote> main`.
