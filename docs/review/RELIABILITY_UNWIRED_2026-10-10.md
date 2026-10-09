# The reliability layer is implemented and has no production caller

> Read-only verification. `COMPATIBILITY_MATRIX.md` says the reliability layer is
> `not-started` / "design only". That is correct for the **product**, but the
> reason is not the one the matrix gives: `qtranslate/reliability.py` is **28KB
> of finished logic with zero callers outside the tests**. It is not design-only;
> it is unwired.
>
> No code changed by this document.

## 1. What was measured

`qtranslate/app.py` imports the module **nowhere**. Every reference to
`reliability` in the repo is a test file:

```
tests/regress_result_shape.py:30     from qtranslate import reliability as R
tests/regress_reliability.py:11      (the reliability suite)
```

And `do_translate` — the single entry point every capture path funnels into —
contains none of it. Confirmed by AST, not by grep, because a substring search
over `app.py` returns the whole file's worth of false hits:

```
do_translate: 66 lines
   'retry'       False
   'classify'    False
   'reliability' False
   '_t_google'   True        # it calls the bare function directly
```

So the flow is `app.py -> services/*.py()` with a `try/except Exception` around
it, and the classification, bounded-retry, and fallback machinery in
`reliability.py` never runs.

## 2. Why this matters more than the "not-started" label suggests

The matrix row reads as "this is a design." It is not a design — it is working
code, which is the more misleading of the two:

- **A reader planning Phase C would budget build time for something already
  built.** 28KB, with `ErrorKind`, `classify()`, `FallbackRouter`, and
  `ProviderHealth` present.
- **The failure surface is worse than `not-started` implies.** With no
  classifier in the loop, every provider exception is swallowed by
  `except Exception` and `do_translate` returns the id-190 string unconditionally
  ("No data returned (timeout while sending data.)"). A 429, a Cloudflare wall,
  and a genuine timeout are indistinguishable to the user — which is exactly what
  `RELIABILITY.md` §2 exists to fix.
- **`tests/regress_reliability.py` therefore passes against nothing.** It
  exercises the module directly. That is legitimate unit coverage and it is not
  product coverage, and the two are easy to conflate when the tests are green.

## 3. What this does *not* establish

- **It does not establish that the reliability layer is correct.** Nothing has
  run it against a live provider.
- **It does not establish that wiring it is trivial.** `do_translate` currently
  calls `fn(text[:5000], src, target)` and gets a `str` back;
  `reliability.run_provider` wants a request object and returns a `Result`. The
  `CORE_RESULT_SHAPE_2026-10-10.md` proposal exists precisely because those two
  contracts do not meet, so the wiring and the type change are one piece of work,
  not two.
- **It does not establish which behavior native exposes to the user.** That is a
  §F RE question and it is separate.

## 4. The cheap fix, and why I am not doing it here

The matrix row should say what is true: **implemented, unwired** — a different
state from both `not-started` and `ported`, and one this matrix's vocabulary does
not yet have. That is a row-owner decision.

The wiring itself is deliberately not attempted in this session: it requires the
`core.Result` field-order decision (`CORE_RESULT_SHAPE_2026-10-10.md` §2) to be
settled first, since `do_translate`'s return type is what the change pivots on.
Doing the wiring under the current `str` contract would mean wiring it twice.
