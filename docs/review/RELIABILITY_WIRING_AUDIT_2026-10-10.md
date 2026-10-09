# Reliability Wiring Audit — where failures are lost today (2026-10-10)

> Read-only audit. **No code was changed.** Purpose: enumerate the app's live
> failure paths and mark, for each, whether `qtranslate/reliability.py`'s
> taxonomy already covers it, what is lost, and which phase the fix belongs to.
> This is the gap between "the reliability module exists" (§1 of `RELIABILITY.md`
> is about *classification*, which now exists) and "the app actually reports why
> it failed" (§7 diagnostics, which does not yet).
>
> Everything below was measured from `qtranslate/app.py` at commit `0b44311`.

## 1. The headline number

```
except Exception handlers in app.py            237
  of which swallow silently (`pass`, no return) 116
  of which surface something (return/print)       45
```

116 sites discard the exception **and** its type. A taxonomy cannot classify
what it never sees, so no amount of module quality fixes those paths. Most are
UI cosmetics and correctly ignored; the list below is only the subset that sits
on a user-visible **translation/TTS/history** path, which is what §7's
"the *mất kết nối* report must be answerable from logs" is about.

## 2. The translate path — the important one

`do_translate` (`app.py:545-586`) collapses **five** distinct failure sources
into one string:

| # | Failure source | Today | What is lost |
|---|----------------|-------|--------------|
| 1 | provider raised (network/timeout/auth/dead) | `except Exception:` → string 190 | the **kind** — a dead endpoint is reported identically to a hiccup |
| 2 | provider returned empty/falsy | `if not out:` → string 190 | same |
| 3 | `detect_language` — every provider failed | each provider's `except: pass`, then `"auto"` | that detection failed *at all*; a wrong `auto` is indistinguishable from a right one |
| 4 | RemoveLineBreaks read of Options.json | `except Exception: slow=False` | benign |
| 5 | back-translation raised | `except Exception: pass` | that the *back*-translation half silently never ran |

**#1 and #2 are the user's core complaint.** `"No data returned (timeout while
sending data)"` is the native string (string id 190, verified), so it is the
right *text* — but it asserts a **timeout** for every cause. A `PROVIDER_DEAD`
(404/SSL) and a `TIMEOUT` are different problems with different fixes
(`RELIABILITY.md` §1 table), and today they are one message.

**#3 is the quietest bug.** `detect_language` (`app.py:497-519`) tries six
providers in sequence, `except Exception: pass` on each, and returns `"auto"`.
If all six fail — network down, or all six token-walled — the caller receives
`"auto"` and proceeds to translate with auto-detect. There is no signal that
detection failed, so a user on a dead link gets "auto" rather than "your
network is down."

**#5 means the back-translation can vanish on its own.** The append is wrapped
in `except Exception: pass`, so a failed back-translation looks exactly like a
successful translation with no back-translation requested.

### Covered by the taxonomy now

`reliability.classify()` handles every one of #1/#2 (raises and empty-result →
`MALFORMED_RESPONSE`/`TRANSIENT_NETWORK`/`PROVIDER_DEAD`/…), and
`ProviderRouter.translate()` produces a `Result.note` naming the kind and the
providers tried. So the *information* is now available; the app just isn't
asking for it.

## 3. TTS (`speak`, `app.py:522-543`) — partly covered, partly not

```python
except Exception as e:
    print(f"TTS failed ({e}); trying SAPI")   # stdout only
    ...
    except Exception as e2:
        print(f"SAPI failed: {e2}")           # stdout only, and nothing more
```

This is a **two-level fallback with no contract**: online BASS mp3 → offline
SAPI. It is the only place in the app with a real fallback chain, and it behaves
correctly. Two problems:

1. **Both failures go to `print`, not the UI.** In a windowed app with no
   console, a completely silent TTS failure is indistinguishable from TTS
   working with no sound.
2. **A `CONFIG_ERROR` is misrouted.** If the proxy is misconfigured, SAPI will
   fail for the same underlying reason as BASS — so the "fallback" retries the
   same `CONFIG_ERROR` against a different engine and reports two failures
   instead of one diagnosis. `RELIABILITY.md` §5 is explicit that
   `CONFIG_ERROR` must not fall back.

## 4. Speech input (`on_mic`, `app.py:1411-1460`) — not covered, and shouldn't be

`except Exception as e: render(f"[speech error] {e}")` — the one place that
surfaces a **raw exception string to the UI**. It is honest but leaks internals
(dll names, HRESULTs) into a user-facing pane. Not a reliability gap: SAPI
offline recognition is `dead:native-unavailable` on this platform, and J5/J6
speech-in is genuinely unported. **Leave it**; chasing it is Phase 4 work
(`Dead:native-unavailable` is a port state, not a bug).

## 5. History (`push_hist`, `app.py:1751-1762`) — one silent

```python
try:
    if not bool(_CEH.load().get("General", {}).get("EnableHistory", True)):
        return
except Exception:
    pass
```

If the Options read fails, history is **enabled by default** and the entry is
saved. Defensible (fail-open is right for history), but it is the one place
where a config-read failure silently changes behavior rather than degrading it.
Low priority; noting for completeness.

## 6. What is already covered vs what needs a change

| Path | Taxonomised today? | Fix belongs to |
|------|--------------------|----------------|
| provider failure in `do_translate` | **no** — string 190 for all causes | **Phase 5** (engine cutover). The module is ready; the call site must ask for the `Failure.kind` instead of discarding it. |
| detect failure | **no** — returns `"auto"` | Phase 5, plus a decision: is `detect` failure `USER_NETWORK_DOWN` (stop) or a degrade-to-`auto`? The matrix's row B has an opinion. |
| TTS BASS→SAPI | **partially** — right shape, `CONFIG_ERROR` misrouted, both failures `print`-only | Phase 1-adjacent; small and independent. |
| speech input | intentionally uncovered | Phase 4 (platform capability honesty) |
| history config read | fail-open, not classified | none — correct as-is |
| the other ~100 silent `except`s | not classified | **none** — mostly widget cosmetics; auditing them all would be churn. |

## 7. The one thing worth doing before Phase 5

`RELIABILITY.md` §7 wants a *log line per classified failure* with
provider/kind/status/elapsed/attempts. The module already emits exactly that
(`Failure.log_line()`, and `on_event` hooks in `run_provider`/`route`). Nothing
writes it anywhere except stdout.

The minimal, no-architecture change: a tiny module-level log sink the app sets,
so every `Failure` recorded through the router lands in a file under the user's
data dir. **Not proposed as part of Phase 1** (which is complete and committed
at `0b44311`) — it is Phase 5 groundwork, and doing it now would be the exact
scope creep `IMPLEMENTATION_PLAN.md` warns about.

## 8. Reproduce the counts

```
grep -c "except Exception" qtranslate/app.py        # 237
grep -n "except Exception" qtranslate/app.py | wc -l # same
```

The 116/45 split came from a 3-line lookahead for `pass` vs `return`/`_T(`
(`_T(` is the native-string indirection used for the 190 error). Not exact
tooling — it is a *triage* count to size the problem, not a claim that every
one of the 116 is wrong.
