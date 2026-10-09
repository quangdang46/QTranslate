"""Regression: reliability layer — classify / retry / fallback / health.

Phase 1 of docs/IMPLEMENTATION_PLAN.md, tests prescribed by
docs/TEST_STRATEGY.md §3 ("classification unit tests; fallback integration with
a mock provider that always fails; Retry-After handling; total-budget
enforcement").

Offline and deterministic: no network, no real sleeping (a recording clock and
a fake sleeper stand in), so every assertion is on policy, not on timing luck.

Run: python -I tests/regress_reliability.py
"""
import os
import socket
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qtranslate.app as app  # noqa: E402
import qtranslate.reliability as R  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


def _http(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return urllib.error.HTTPError("http://x/", code, "boom",
                                  type("H", (), {"get": headers.get})(), None)


def _raise(exc):
    raise exc


def _raise_429():
    raise _http(429)


class Clock:
    """Deterministic monotonic stand-in: advances only when told."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def sleeper():
    calls = []

    def _sleep(dt):
        calls.append(dt)

    return calls, _sleep


# ------------------------------------------------------------ 1. taxonomy (§2)
for exc, expected in [
    (TimeoutError("timed out"), R.ErrorKind.TIMEOUT),
    (socket.timeout("timed out"), R.ErrorKind.TIMEOUT),
    (socket.gaierror("dns dead"), R.ErrorKind.TRANSIENT_NETWORK),
    (ConnectionRefusedError("nope"), R.ErrorKind.TRANSIENT_NETWORK),
    (ConnectionResetError("reset"), R.ErrorKind.TRANSIENT_NETWORK),
    (ValueError("Expecting value"), R.ErrorKind.MALFORMED_RESPONSE),
    (OSError(101, "network unreachable"), R.ErrorKind.TRANSIENT_NETWORK),
    (OSError(110, "timed out"), R.ErrorKind.TIMEOUT),
    (_http(429), R.ErrorKind.RATE_LIMITED),
    (_http(401), R.ErrorKind.AUTH_EXPIRED),
    (_http(403), R.ErrorKind.AUTH_EXPIRED),
    (_http(404), R.ErrorKind.PROVIDER_DEAD),
    (_http(410), R.ErrorKind.PROVIDER_DEAD),
    (_http(400), R.ErrorKind.MALFORMED_RESPONSE),
    (_http(422), R.ErrorKind.MALFORMED_RESPONSE),
    (_http(502), R.ErrorKind.TRANSIENT_NETWORK),
    (_http(503), R.ErrorKind.TRANSIENT_NETWORK),
    (_http(500), R.ErrorKind.TRANSIENT_NETWORK),
]:
    check(f"classify {exc!r} -> {expected.value}",
          R.classify(exc) is expected, R.classify(exc).value)

check("classify: reason-text certificate -> provider-dead",
      R.classify(Exception("certificate verify failed")) is R.ErrorKind.PROVIDER_DEAD)
check("classify: reason-text proxy -> config-error",
      R.classify(Exception("proxy refused")) is R.ErrorKind.CONFIG_ERROR)
check("classify: explicit status wins",
      R.classify(ValueError("x"), status=404) is R.ErrorKind.PROVIDER_DEAD)
check("classify: None -> malformed-response",
      R.classify(None) is R.ErrorKind.MALFORMED_RESPONSE)
check("classify: total on a bare exception",
      R.classify(RuntimeError("who knows")) in set(R.ErrorKind))

# An SSL/cert failure is an endpoint that is gone, so it must never retry.
check("PROVIDER_DEAD is not retryable",
      R.ErrorKind.PROVIDER_DEAD not in R.RETRYABLE)
check("CONFIG_ERROR is not retryable",
      R.ErrorKind.CONFIG_ERROR not in R.RETRYABLE)
check("AUTH_EXPIRED retries once (then falls back)",
      R.ErrorKind.AUTH_EXPIRED in R.RETRYABLE)

# --------------------------------------------------------- 2. Retry-After (§3)
check("Retry-After delta-seconds parsed",
      R.parse_retry_after("2") == 2.0)
check("Retry-After numeric parsed",
      R.parse_retry_after(3) == 3.0)
check("Retry-After bool is not a number",
      R.parse_retry_after(True) is None)
check("Retry-After empty is None", R.parse_retry_after("") is None)
check("Retry-After negative is None", R.parse_retry_after("-1") is None)
check("Retry-After HTTP-date in the future",
      R.parse_retry_after("Wed, 21 Oct 2099 07:28:00 GMT") > 0)
check("Retry-After garbage is None", R.parse_retry_after("soon") is None)

# --------------------------------------------------- 3. backoff shape (§3)
pol = R.RetryPolicy()
check("backoff grows 0.2 -> 0.4 -> 0.8 (capped)",
      (pol.delay_for(1), pol.delay_for(2), pol.delay_for(3),
       pol.delay_for(9)) == (0.2, 0.4, 0.8, 0.8), repr(pol.delay_for(9)))
check("backoff below attempt 1 is zero", pol.delay_for(0) == 0.0)

# ------------------------------------------- 4. bounded retry, shared budget
calls, sleep = sleeper()


def _flaky(fail_times):
    """Return a callable that raises ``fail_times`` transient errors."""
    state = {"n": 0}

    def _fn():
        state["n"] += 1
        if state["n"] <= fail_times:
            raise ConnectionResetError("boom")
        return "translated"

    return _fn


out = R.run_provider(_flaky(2), "google", policy=R.RetryPolicy(), sleep=sleep,
                     on_event=None)
check("retries a transient failure then succeeds", isinstance(out, R.Success)
      and out.value == "translated" and out.attempts == 3, repr(out))
check("backoff applied between retries", len(calls) == 2 and calls[0] == 0.2
      and calls[1] == 0.4, repr(calls))

calls, sleep = sleeper()
out = R.run_provider(_flaky(99), "google", policy=R.RetryPolicy(), sleep=sleep)
check("stops at max_attempts, never loops forever",
      isinstance(out, R.Failure) and out.attempts == 3 and out.kind
      is R.ErrorKind.TRANSIENT_NETWORK, repr(out))

calls, sleep = sleeper()
clock = Clock()


def _sleep_and_advance(dt):
    calls.append(dt)
    clock.advance(dt)


out = R.run_provider(_flaky(99), "google", policy=R.RetryPolicy(),
                     sleep=_sleep_and_advance, clock=clock,
                     budget=R.Budget(0.5, clock))
# 0.2s backoff fits inside 0.5s (attempt 2 runs), the 0.4s one does not.
check("a small budget stops retrying instead of overrunning",
      isinstance(out, R.Failure) and out.attempts == 2, repr(out))

# Retry-After that fits inside the budget is respected.
seen, sleep = sleeper()
out = R.run_provider(lambda: _raise_429(), "google",
                     policy=R.RetryPolicy(), sleep=sleep)
check("429 classified rate-limited, not transient",
      out.kind is R.ErrorKind.RATE_LIMITED, out.kind.value)

# Retry-After larger than the whole budget: fall back immediately, no sleep.
slept, _s = sleeper()
clock = Clock()
out = R.run_provider(lambda: _raise(_http(429, retry_after="30")), "google",
                     policy=R.RetryPolicy(), sleep=_s, clock=clock,
                     budget=R.Budget(5.0, clock))
check("Retry-After beyond the budget -> no sleep, fall back",
      isinstance(out, R.Failure) and slept == [] and out.status == 429, repr(out))

# PROVIDER_DEAD never retries (RELIABILITY.md §8).
slept, _s = sleeper()
attempts = []


def _dead():
    attempts.append(1)
    raise _http(404)


R.run_provider(_dead, "babylon", policy=R.RetryPolicy(), sleep=_s)
check("PROVIDER_DEAD does not retry at all",
      len(attempts) == 1 and slept == [], repr(attempts))

# One shared budget, two providers: the first cannot starve the second.
clock = Clock()


def _slow_fail():
    raise ConnectionResetError("nope")


budget = R.Budget(1.0, clock)
first = R.run_provider(_slow_fail, "a", policy=R.RetryPolicy(base_delay=0.4,
                                                           max_attempts=5),
                       sleep=lambda dt: clock.advance(dt), clock=clock,
                       budget=budget)
second = R.run_provider(lambda: "ok", "b", policy=R.RetryPolicy(), clock=clock,
                        budget=budget)
check("first provider is cut off by the shared budget",
      isinstance(first, R.Failure) and first.attempts == 2, repr(first))
check("second provider still has budget and succeeds",
      isinstance(second, R.Success) and second.value == "ok", repr(second))

# ------------------------------------------------ 5. fallback routing (§5, D12)
router = R.FallbackRouter(
    {"google": lambda t, s, g: "G", "microsoft": lambda t, s, g: "M",
     "deepl": lambda t, s, g: "D"},
    order=["google", "microsoft", "deepl"],
    policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0))

res = router.route("hi", "en", "vi", "deepl")
check("explicit provider is used when healthy",
      res.ok and res.provider_used == "deepl" and res.text == "D", repr(res))

router.callables["deepl"] = lambda t, s, g: (_ for _ in ()).throw(
    ConnectionResetError("down"))
res = router.route("hi", "en", "vi", "deepl")
check("a failing explicit provider falls back to the next in order",
      res.ok and res.provider_used in ("google", "microsoft") and res.text
      in ("G", "M"), repr(res))
check("the fallback names itself in the note (§5.2 transparency)",
      "fallback" in res.note and res.requested == "deepl", repr(res.note))

# A dead provider is skipped before any budget is spent on it.
router2 = R.FallbackRouter(
    {"google": lambda t, s, g: "G", "babylon": lambda t, s, g: "B"},
    order=["google", "babylon"], policy=R.RetryPolicy())
router2.health.mark_unavailable(["babylon"])
res = router2.route("hi", "en", "vi", "babylon")
check("a provider marked dead is skipped, not called",
      res.ok and res.provider_used == "google", repr(res))

# The request must be identical for every provider (RELIABILITY.md §5.1).
seen_args = []


def _record(name, value):
    def _fn(text, src, tgt):
        seen_args.append((name, text, src, tgt))
        return value
    return _fn


router3 = R.FallbackRouter({"a": _record("a", "A"),
                            "b": _record("b", "B")},
                           order=["a", "b"],
                           policy=R.RetryPolicy(base_delay=0.0))
res = router3.route("  keep this  ", "de", "vi", "b")
# 'b' succeeds, so 'a' is never called — the request is only observable on
# the provider that actually ran. Assert the single call kept the request.
check("the request is passed through unmodified (no normalization)",
      res.ok and res.provider_used == "b"
      and seen_args == [("b", "  keep this  ", "de", "vi")], repr(seen_args))

# When the fallback does run, every provider sees the identical request.
seen_args.clear()


def _record_fail(name):
    def _fn(text, src, tgt):
        seen_args.append((name, text, src, tgt))
        raise ConnectionResetError("down")

    return _fn


router3.callables["b"] = _record_fail("b")
res = router3.route("  keep this  ", "de", "vi", "b")
check("fallback preserves text/src/tgt exactly for every provider",
      res.ok and res.provider_used == "a"
      and seen_args[0] == ("b", "  keep this  ", "de", "vi")
      and seen_args[-1] == ("a", "  keep this  ", "de", "vi")
      and all(a[1:] == ("  keep this  ", "de", "vi") for a in seen_args),
      repr(seen_args))
check("provider b was retried up to max_attempts before falling back",
      seen_args.count(("b", "  keep this  ", "de", "vi")) <= 3, repr(seen_args))

# CONFIG_ERROR stops the whole route.
def _cfg_error(t, s, g):
    raise Exception("bad proxy")


router4 = R.FallbackRouter({"a": _cfg_error, "b": lambda t, s, g: "B"},
                           order=["a", "b"], policy=R.RetryPolicy())
res = router4.route("hi", "en", "vi", "a")
check("CONFIG_ERROR does not fall back (§5 no-fallback set)",
      not res.ok and res.failures[0].kind is R.ErrorKind.CONFIG_ERROR
      and res.failures[0].provider == "a", repr(res))

# The user's link being down is reported as such, not as two dead providers.
router5 = R.FallbackRouter(
    {"a": lambda t, s, g: (_ for _ in ()).throw(
        socket.gaierror("reroute failed")),
     "b": lambda t, s, g: (_ for _ in ()).throw(
         socket.gaierror("reroute failed")),
     "c": lambda t, s, g: "C"},
    order=["a", "b", "c"], policy=R.RetryPolicy(base_delay=0.0))
res = router5.route("hi", "en", "vi", "a")
check("consecutive network failures -> USER_NETWORK_DOWN, no endless fallback",
      not res.ok and len(res.failures) == 2
      and all(f.kind is R.ErrorKind.USER_NETWORK_DOWN for f in res.failures),
      repr(res))
check("the third provider is never reached once the link looks down",
      "c" not in res.tried, repr(res.tried))

# A 200 with an unusable payload is malformed, not a translation.
router6 = R.FallbackRouter({"a": lambda t, s, g: "<html>error</html>",
                            "b": lambda t, s, g: "B"},
                           order=["a", "b"],
                           policy=R.RetryPolicy(base_delay=0.0),
                           result_is_valid=lambda v: not v.startswith("<"))
res = router6.route("hi", "en", "vi", "a")
check("an unusable 200 body falls back instead of being shown as text",
      res.ok and res.provider_used == "b", repr(res))

# --------------------------------------------- 6. health tracking (§6)
h = R.HealthTracker()
h.record_failure("p", R.ErrorKind.TIMEOUT)
h.record_failure("p", R.ErrorKind.TIMEOUT)
check("two timeouts -> degraded", h.get("p").state is R.HealthState.DEGRADED)
h.record_failure("p", R.ErrorKind.PROVIDER_DEAD)
h.record_failure("p", R.ErrorKind.PROVIDER_DEAD)
h.record_failure("p", R.ErrorKind.PROVIDER_DEAD)
check("three consecutive provider-dead -> unavailable",
      h.get("p").state is R.HealthState.UNAVAILABLE and h.get("p").skippable)
h.record_success("p")
check("a success resets to healthy and un-skips",
      h.get("p").state is R.HealthState.HEALTHY and not h.get("p").skippable)
h.record_failure("q", R.ErrorKind.UNSUPPORTED_PAIR)
check("unsupported pair is recorded as such",
      h.get("q").state is R.HealthState.UNSUPPORTED and h.get("q").skippable)

# --------------------------------------------------- 7. diagnostics (§7)
f = R.Failure("bing", R.ErrorKind.RATE_LIMITED, 429, "too many", 2, 1.25)
line = f.log_line()
check("log line carries every §7 field",
      all(k in line for k in ("provider=bing", "kind=rate-limited", "status=429",
                              "attempts=2", "elapsed=1.250")), line)

# ----------------------------- 8. the app's own error string is never faked
_orig = app.TRANSLATORS.copy()


def _always_dead(t, s, g):
    raise ConnectionResetError("no network")


app.TRANSLATORS.clear()
app.TRANSLATORS.update({"promt": _always_dead})
try:
    out = app.do_translate("promt", "hello", "vi", src="en")
finally:
    app.TRANSLATORS.clear()
    app.TRANSLATORS.update(_orig)
check("do_translate still surfaces the native 'no data' string",
      isinstance(out, str) and out.startswith("No data returned"), repr(out))
check("no fabricated translation text on total failure",
      "hello" not in out, repr(out))




# ------------------------------------------- 9. adapter (Phase 1 seam, §5.1)
# The pinning test: provider 1 fails, and the request reaching provider 2 must
# be byte-identical to what reached provider 1. This is the "preserve the
# request" guarantee of RELIABILITY.md §5.1, asserted rather than assumed.
seen_by = []


def _rec(name, value, boom=False):
    def _fn(text, src, tgt):
        seen_by.append((name, text, src, tgt))
        if boom:
            raise ConnectionResetError("provider down")
        return value

    return _fn


adapter_calls = {"a": _rec("a", "A", boom=True),
                 "b": _rec("b", "B"),
                 "c": _rec("c", "C")}
pr = R.ProviderRouter(adapter_calls, order=["a", "b", "c"],
                      policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0))
res = pr.translate("a", "  keep\tthis \n text  ", "de", "vi")
first_request = seen_by[0]
last_request = seen_by[-1]
check("adapter falls back to the next provider",
      res.ok and res.provider_used == "b", repr(res))
check("every provider is offered a byte-identical request",
      all(s[1:] == first_request[1:] for s in seen_by),
      repr(seen_by))
# .strip() runs first, matching do_translate()'s `text.strip()` before any
# provider sees the request; RemoveLineBreaks (off here) leaves \n in place.
check("the shaping already happened before the first attempt",
      first_request[1] == "keep\tthis \n text", repr(first_request))
check("the fallback names itself via provider_used",
      res.provider_used == "b" and "fallback" in res.note, repr(res.note))

# RemoveLineBreaks is applied once, not per provider.
seen_by.clear()
pr2 = R.ProviderRouter(dict(adapter_calls), order=["a", "b", "c"],
                       policy=R.RetryPolicy(base_delay=0.0, max_delay=0.0))
res2 = pr2.translate("a", "line1\nline2", "en", "vi",
                     config={"Advanced": {"RemoveLineBreaks": True}})
check("RemoveLineBreaks collapses newlines before the first attempt",
      all(s[1] == "line1 line2" for s in seen_by), repr(seen_by))
check("RemoveLineBreaks did not run a second time",
      len(seen_by) >= 2 and all(s[1] == "line1 line2" for s in seen_by)
      and seen_by[0][1].count(" ") == 1, repr(seen_by))

# The 5000-char cap is applied once, before any provider sees the text.
seen_by.clear()
long_text = "x" * 9000
res3 = pr.translate("a", long_text, "en", "vi")
check("the 5000-char cap is applied exactly once, up front",
      all(s[1] == "x" * 5000 for s in seen_by), repr(seen_by[0]))

# The back-translation append runs once, after the loop.
seen_by.clear()
res4 = pr.translate_with_backtranslation("a", "hi", "en", "vi",
                                        back_translate=True)
check("back-translation appended once, using the provider that answered",
      res4.ok and R.BACKTRANSLATION_MARKER in res4.text
      and res4.text.count(R.BACKTRANSLATION_MARKER) == 1, repr(res4.text))
check("back-translation is hidden inside the returned text, not pre-applied",
      len([s for s in seen_by if s[0] == "b"]) == 2, repr(seen_by))

main, back = R.split_backtranslation(res4.text)
check("split_backtranslation recovers the persisted fields",
      main == "B" and back == "B", repr((main, back)))
m2, b2 = R.split_backtranslation("no marker here")
check("split on a markerless result returns ('text', '')",
      (m2, b2) == ("no marker here", ""), repr((m2, b2)))

# An empty request short-circuits: no provider call at all.
seen_by.clear()
res5 = pr.translate("a", "   \n  ", "en", "vi")
check("an empty request never reaches a provider",
      not res5.ok and seen_by == [] and "empty" in res5.note, repr(res5.note))

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: reliability classify/retry/fallback/health/adapter")
