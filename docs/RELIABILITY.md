# Reliability Layer

> Status: **PLANNING.** Design for the "QTranslate keeps losing connection"
> problem. Reliability is a **Core** responsibility (D15) — providers stay
> dumb, Core owns retry / fallback / classification.

## 1. The problem, stated precisely

Today a failed translation surfaces as a raw error string and the user is
stuck. The native error text is `"No data returned (timeout while sending
data)."` (see `qtranslate/win32app.py:169`). The current Python app has
timeout + proxy support in `session.py` but **no shared classification, no
bounded budget, no automatic fallback** across providers.

Before writing retry logic we must separate **where** the failure happened,
because the fix differs per layer:

| Layer | Symptom | Correct fix |
|-------|---------|-------------|
| User's network down | every provider fails at once | tell the user, do not burn retries |
| Provider API changed | one provider 404/400 always | disable / update that provider's logic |
| Endpoint retired | one provider dead forever | mark `unsupported`, do not retry |
| Session/token stale | 401/403 until page re-scraped | refresh session (see §4) |
| Rate limit | HTTP 429 | honor `Retry-After`, back off |
| Slow/hung request | no response | per-request timeout (already in `session.py`) |
| UI thread blocked | app freezes, then errors | move work off the UI thread |

**Rule:** a retry that does not know which layer failed is a placebo. Every
retry/fallback decision below keys off a classified error.

## 2. Error taxonomy

Core classifies every provider failure into exactly one kind:

| Kind | Examples | Retry? | Fallback? |
|------|----------|--------|-----------|
| `TRANSIENT_NETWORK` | connection reset, DNS hiccup | yes, bounded | yes |
| `TIMEOUT` | exceeded `Internet.Timeout` | yes, bounded | yes |
| `RATE_LIMITED` | HTTP 429 | yes, honor `Retry-After` | yes |
| `AUTH_EXPIRED` | 401/403 token/session | refresh once, then | yes |
| `UNSUPPORTED_PAIR` | provider can't do `xx→yy` | no | yes |
| `MALFORMED_RESPONSE` | parse failed / empty body | no (usually) | yes |
| `PROVIDER_DEAD` | 404 / endpoint retired / SSL fail | **no** | yes |
| `CONFIG_ERROR` | bad API key, bad proxy | no | no — surface to user |
| `USER_NETWORK_DOWN` | all providers failed at once | no | no — surface to user |

`PROVIDER_DEAD` and `CONFIG_ERROR` must **not** be retried — retrying a dead
endpoint is what makes QTranslate feel like it "hangs then fails".

## 3. Retry policy

- **Bounded budget, not bounded count alone.** Total wall-clock budget for a
  translate attempt (default from `Internet.Timeout`, e.g. 10 s) — the user
  waits once, not once per provider.
- Per-request timeout already flows from `Options.json` via
  `session.net_options()` (`session.py:13`). Keep that as the source of truth.
- Exponential backoff with a small cap (e.g. 200 ms → 400 ms → 800 ms),
  and **never** retry past the total budget.
- **429:** if `Retry-After` is present, respect it; if it exceeds the budget,
  do not retry — fall back immediately.
- **AUTH_EXPIRED:** one session refresh attempt, then fall back.

## 4. Session / token lifecycle

Some providers need an ephemeral token scraped from a page before the real
call (native did this via its Chakra engine + `UtilsDispatch`; see
`docs/NATIVE_ARCH.md`). This is reproduced today in `qtranslate/session.py`:

- `bing_session()` / `bing_translate()` — shared cookie jar so engine-set
  cookies persist between scrape and translate (`session.py:94`, `:128`).
- `promt_session()` — XSRF + `paft` scrape (`session.py:157`).

Rules for the Core session manager:

- Session objects are **per-provider**, cached, and refreshable on
  `AUTH_EXPIRED` exactly once per request.
- A session refresh failure is `AUTH_EXPIRED` (→ fallback), not a retry loop.
- Do not treat "endpoint needs a token we cannot scrape" as transient. Several
  such cases are already documented as dead ends in `tests/LIVE_RESULTS.md`.

## 5. Fallback routing (decision D12)

When the user explicitly picks **Google** and it fails:

```
Google  ──retry (bounded)──►  still failing?
   │                              │
   │  classify                    ▼
   │                        next provider in ServicesOrder
   ▼                              │
 CONFIG_ERROR / USER_NETWORK_DOWN  │  (skip providers marked PROVIDER_DEAD)
   → surface to user, no fallback  ▼
                            Microsoft ── … ──►
                              all exhausted → clear error + log
```

Guarantees the fallback path **must** hold:

1. **Preserve the request.** Source text, source/target language, and options
   are identical across providers — only the provider changes. (This is the
   `do_translate(svc, text, tgt, src, detect, backtr)` contract; the
   source-language argument is exactly what the uncommitted hotkey change
   touches — see `CURRENT_STATE.md`.)
2. **Be transparent.** The UI must show **which provider produced the
   result**, so a silent provider swap never masquerades as the chosen one.
3. **Respect the order.** Fallback follows `Options.json` `ServicesOrder`
   (default `[1,5,12,13,11,26,28,30,31]`, `config.py:16`), skipping any
   provider already classified `PROVIDER_DEAD` for this run.
4. **One budget.** Retries across all providers share the total time budget.

## 6. Provider health

A lightweight per-provider status kept in Core (in-memory, persisted
optionally):

| State | Meaning |
|-------|---------|
| `healthy` | last call succeeded |
| `degraded` | recent timeout / rate-limit |
| `unavailable` | repeated `PROVIDER_DEAD` this session |
| `unsupported` | cannot serve this language pair |

Health is shown in the Services list and used to skip hopeless providers
before spending the budget on them.

## 7. Diagnostics

- Every classified failure logs: provider, kind, HTTP status, elapsed, attempt
  number, and whether it fell back.
- The "mất kết nối" report must be answerable from logs: **which layer**
  failed, **which provider**, **what Core did**.
- A dead endpoint discovered by the matrix or live tests is recorded as
  `PROVIDER_DEAD` with a date — not silently retried forever.

## 8. What this layer must NOT do

- Do not add retry to providers individually — that recreates the current
  inconsistency. Keep `sock`/`session` primitives; put policy in Core.
- Do not retry `PROVIDER_DEAD` / `CONFIG_ERROR`.
- Do not block the UI thread while retrying (see the reliability workstream
  in `IMPLEMENTATION_PLAN.md`).
- Do not claim "fixed" from a retry that masks a dead endpoint.
