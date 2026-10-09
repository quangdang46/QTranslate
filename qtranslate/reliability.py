"""Reliability layer — classification, bounded retry, fallback, provider health.

Phase 1 of docs/IMPLEMENTATION_PLAN.md. Reliability is a Core concern (D15):
providers stay dumb, this module holds the policy. It imports neither tkinter
nor any Win32 binding, so Phase 4's platform-absence tests run it unchanged.

Design source: docs/RELIABILITY.md.

  §2 taxonomy  -> ErrorKind + classify()
  §3 retries   -> RetryPolicy + run_provider() (one shared budget, Retry-After
                  honored, never past the budget)
  §5 fallback  -> FallbackRouter (preserves the request, transparent about who
                  answered, follows ServicesOrder, skips dead providers)
  §6 health    -> HealthTracker (healthy/degraded/unavailable/unsupported)
  §7 logs      -> Failure.log_line() + the on_event callbacks

No network I/O happens here: the call, the sleep and the clock are injected,
so tests run offline and deterministically.
"""
from __future__ import annotations

import dataclasses
import datetime
import email.utils
import enum
import errno
import socket
import time


class ErrorKind(enum.Enum):
    """The nine kinds of RELIABILITY.md §2, and nothing else."""

    TRANSIENT_NETWORK = "transient-network"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate-limited"
    AUTH_EXPIRED = "auth-expired"
    UNSUPPORTED_PAIR = "unsupported-pair"
    MALFORMED_RESPONSE = "malformed-response"
    PROVIDER_DEAD = "provider-dead"
    CONFIG_ERROR = "config-error"
    USER_NETWORK_DOWN = "user-network-down"


# §2: kinds that justify another attempt on the same provider.
RETRYABLE = frozenset({
    ErrorKind.TRANSIENT_NETWORK,
    ErrorKind.TIMEOUT,
    ErrorKind.RATE_LIMITED,
    ErrorKind.AUTH_EXPIRED,
})

# §5: no useful fallback target exists — surface to the user instead.
NO_FALLBACK = frozenset({ErrorKind.CONFIG_ERROR, ErrorKind.USER_NETWORK_DOWN})

# Kinds whose repetition across providers means the user's own link is down.
NETWORK_LEVEL = frozenset({ErrorKind.TRANSIENT_NETWORK, ErrorKind.TIMEOUT})

_STATUS_KINDS = {
    400: ErrorKind.MALFORMED_RESPONSE,
    401: ErrorKind.AUTH_EXPIRED,
    403: ErrorKind.AUTH_EXPIRED,
    404: ErrorKind.PROVIDER_DEAD,
    410: ErrorKind.PROVIDER_DEAD,
    422: ErrorKind.MALFORMED_RESPONSE,
    429: ErrorKind.RATE_LIMITED,
}
_RETRYABLE_STATUS_KINDS = frozenset({
    ErrorKind.TRANSIENT_NETWORK, ErrorKind.RATE_LIMITED,
    ErrorKind.AUTH_EXPIRED,
})


def _status_kind(code: int) -> ErrorKind | None:
    if code in _STATUS_KINDS:
        return _STATUS_KINDS[code]
    if 500 <= code <= 599:
        # A 502/503/504 is usually transient; a bare 500 means the endpoint
        # exists but is broken, which still deserves one retry, not death.
        return ErrorKind.TRANSIENT_NETWORK
    return None


_REASON_KINDS = (
    # TLS/cert failures are an endpoint that is gone, not a flaky connection.
    ("certificate", ErrorKind.PROVIDER_DEAD),
    ("ssl", ErrorKind.PROVIDER_DEAD),
    ("timed out", ErrorKind.TIMEOUT),
    ("timeout", ErrorKind.TIMEOUT),
    ("network is down", ErrorKind.USER_NETWORK_DOWN),
    ("getaddrinfo", ErrorKind.TRANSIENT_NETWORK),
    ("name or service not known", ErrorKind.TRANSIENT_NETWORK),
    ("nodename nor servname", ErrorKind.TRANSIENT_NETWORK),
    ("temporary failure in name resolution", ErrorKind.TRANSIENT_NETWORK),
    ("connection reset", ErrorKind.TRANSIENT_NETWORK),
    ("connection refused", ErrorKind.TRANSIENT_NETWORK),
    ("connection aborted", ErrorKind.TRANSIENT_NETWORK),
    ("broken pipe", ErrorKind.TRANSIENT_NETWORK),
    ("no route to host", ErrorKind.TRANSIENT_NETWORK),
    ("network is unreachable", ErrorKind.TRANSIENT_NETWORK),
    ("proxy", ErrorKind.CONFIG_ERROR),
)

# OSError errno -> kind, for stdlib-level failures that carry no HTTP status.
# ``*_KINDS`` lookups use .get() so a platform that lacks a member still works.
_ERRNO_KINDS = {
    errno.ECONNRESET: ErrorKind.TRANSIENT_NETWORK,
    errno.ECONNABORTED: ErrorKind.TRANSIENT_NETWORK,
    errno.EPIPE: ErrorKind.TRANSIENT_NETWORK,
    errno.EHOSTUNREACH: ErrorKind.TRANSIENT_NETWORK,
    errno.ENETUNREACH: ErrorKind.TRANSIENT_NETWORK,
    errno.ENETDOWN: ErrorKind.USER_NETWORK_DOWN,
    errno.ETIMEDOUT: ErrorKind.TIMEOUT,
}


def _exception_status(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if not isinstance(code, int) or isinstance(code, bool):
        return None
    return code


def _retry_after_seconds(exc: BaseException) -> float | None:
    headers = getattr(exc, "headers", None)
    get = getattr(headers, "get", None)
    if get is None:
        return None
    return parse_retry_after(get("Retry-After"))


def classify(exc: BaseException | None, *, status: int | None = None) -> ErrorKind:
    """Put a provider failure into exactly one kind from §2.

    Total and raise-free: an unrecognized exception becomes MALFORMED_RESPONSE
    rather than a bucket the router cannot act on.

    Message text is consulted before ``errno`` because urllib surfaces the
    failure as ``URLError.reason`` (an OSError whose ``strerror`` names the
    cause), and errno values for the same condition differ per platform.
    """
    if status is None:
        status = _exception_status(exc if exc is not None else None)
    if status is not None:
        kind = _status_kind(status)
        if kind is not None:
            return kind

    if exc is None:
        return ErrorKind.MALFORMED_RESPONSE
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ErrorKind.TIMEOUT
    if isinstance(exc, ValueError):
        return ErrorKind.MALFORMED_RESPONSE

    reason = getattr(exc, "reason", None)
    text = str(reason if reason is not None else exc).lower()
    for needle, kind in _REASON_KINDS:
        if needle in text:
            return kind

    if isinstance(exc, socket.gaierror):
        return ErrorKind.TRANSIENT_NETWORK
    if isinstance(exc, OSError):
        return _ERRNO_KINDS.get(exc.errno, ErrorKind.TRANSIENT_NETWORK)
    return ErrorKind.MALFORMED_RESPONSE


def parse_retry_after(value) -> float | None:
    """Seconds from a Retry-After header: delta-seconds or an HTTP-date (§3)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    text = str(value).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        pass
    else:
        return seconds if seconds >= 0 else None
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    return max(0.0, (when - now).total_seconds())


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry inside one wall-clock budget shared by every provider.

    ``total_budget`` is the whole allowance for a translate attempt — §3: the
    user waits once, not once per provider.
    """

    total_budget: float = 10.0
    max_attempts: int = 3
    base_delay: float = 0.2
    max_delay: float = 0.8
    honor_retry_after: bool = True

    def delay_for(self, attempt: int) -> float:
        """Exponential backoff, capped. ``attempt`` is 1-based."""
        if attempt < 1:
            return 0.0
        return min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)


class Budget:
    """One shared deadline: every provider's retries draw from the same clock."""

    def __init__(self, total: float, clock=time.monotonic):
        self.total = float(total)
        self._clock = clock
        self._start = clock()

    @classmethod
    def start(cls, total: float, clock=time.monotonic) -> "Budget":
        return cls(total, clock)

    def consumed(self) -> float:
        return self._clock() - self._start

    def remaining(self) -> float:
        return max(0.0, self.total - self.consumed())

    def expired(self) -> bool:
        return self.remaining() <= 0


@dataclasses.dataclass(frozen=True)
class Failure:
    """One classified provider failure, as §7 diagnostics require."""

    provider: str
    kind: ErrorKind
    status: int | None = None
    detail: str = ""
    attempts: int = 1
    elapsed: float = 0.0

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE

    def log_line(self) -> str:
        parts = [f"provider={self.provider}", f"kind={self.kind.value}",
                 f"attempts={self.attempts}", f"elapsed={self.elapsed:.3f}s"]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " ".join(parts)


@dataclasses.dataclass(frozen=True)
class Success:
    provider: str
    value: object
    attempts: int = 1
    elapsed: float = 0.0


class _HttpLike(Exception):
    """Test double shaped like urllib.error.HTTPError (code + headers)."""

    def __init__(self, code, message="", headers=None):
        super().__init__(message or f"HTTP {code}")
        self.code = code
        self.headers = headers if headers is not None else {}


def _header_value(exc: BaseException, name: str):
    headers = getattr(exc, "headers", None)
    get = getattr(headers, "get", None)
    if get is None:
        return None
    try:
        return get(name)
    except Exception:
        return None


def run_provider(fn, provider: str, *, policy: RetryPolicy | None = None,
                 budget: Budget | None = None, sleep=time.sleep,
                 clock=time.monotonic, on_event=None):
    """Call ``fn()`` under the retry policy. Returns Success or Failure.

    The loop stops early when the shared budget can no longer cover the next
    backoff plus a call, so one provider cannot starve the rest.
    """
    policy = policy or RetryPolicy()
    budget = budget or Budget.start(policy.total_budget, clock)
    started = clock()
    attempt = 0
    kind = None
    status = None
    detail = ""
    retry_after = None

    while True:
        attempt += 1
        try:
            value = fn()
        except Exception as exc:
            kind = classify(exc)
            status = _exception_status(exc)
            detail = str(exc)[:200]
            retry_after = (_retry_after_seconds(exc)
                           if policy.honor_retry_after else None)
            if on_event is not None:
                on_event(f"{provider} attempt {attempt} failed "
                         f"kind={kind.value}")
        else:
            if isinstance(value, str) and not value.strip():
                # An empty body is a parse-level fault, not a translation.
                kind = ErrorKind.MALFORMED_RESPONSE
                status, detail, retry_after = None, "empty result", None
            else:
                if on_event is not None and attempt > 1:
                    on_event(f"{provider} ok on attempt {attempt}")
                return Success(provider, value, attempt, clock() - started)

        if kind not in RETRYABLE or attempt >= policy.max_attempts:
            break
        if budget.expired():
            break
        if retry_after is not None:
            if retry_after > budget.remaining():
                # §3: a Retry-After longer than the budget means fall back now.
                break
            delay = retry_after
        else:
            delay = min(policy.delay_for(attempt), budget.remaining())
            if policy.delay_for(attempt) > budget.remaining():
                break
        if delay:
            sleep(delay)

    return Failure(provider, kind, status, detail, attempt, clock() - started)


class HealthState(enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


@dataclasses.dataclass(frozen=True)
class Health:
    state: HealthState = HealthState.HEALTHY
    kind: ErrorKind | None = None
    since: str = ""
    note: str = ""

    @property
    def skippable(self) -> bool:
        """Unavailable/unsupported providers are not worth budget (§5.3)."""
        return self.state in (HealthState.UNAVAILABLE, HealthState.UNSUPPORTED)


class HealthTracker:
    """Per-provider health for the current session (§6), in memory only."""

    UNAVAILABLE_AFTER = 3   # consecutive PROVIDER_DEAD
    DEGRADED_AFTER = 2      # consecutive timeout / rate-limit / transient

    def __init__(self):
        self._entries: dict[str, Health] = {}
        self._streak: dict[str, int] = {}

    def get(self, provider: str) -> Health:
        return self._entries.setdefault(provider, Health())

    def record_failure(self, provider: str, kind: ErrorKind,
                       now: str | None = None) -> Health:
        streak = self._streak.get(provider, 0) + 1
        self._streak[provider] = streak
        if kind is ErrorKind.UNSUPPORTED_PAIR:
            state = HealthState.UNSUPPORTED
        elif kind is ErrorKind.PROVIDER_DEAD and streak >= self.UNAVAILABLE_AFTER:
            state = HealthState.UNAVAILABLE
        elif kind in (ErrorKind.TRANSIENT_NETWORK, ErrorKind.TIMEOUT,
                      ErrorKind.RATE_LIMITED) and streak >= self.DEGRADED_AFTER:
            state = HealthState.DEGRADED
        elif streak == 1:
            state = HealthState.HEALTHY
        else:
            state = HealthState.DEGRADED
        entry = Health(state, kind, now or _today(), kind.value)
        self._entries[provider] = entry
        return entry

    def record_success(self, provider: str, now: str | None = None) -> Health:
        self._streak[provider] = 0
        entry = Health(HealthState.HEALTHY, None, now or _today(), "")
        self._entries[provider] = entry
        return entry

    def mark_unavailable(self, providers, note: str = "dead:host-retired") -> None:
        """Record known-dead providers before any budget is spent on them."""
        for name in providers:
            self._streak[name] = 0
            self._entries[name] = Health(
                HealthState.UNAVAILABLE, ErrorKind.PROVIDER_DEAD, _today(), note)

    def as_dict(self) -> dict:
        return {name: {"state": h.state.value,
                       "kind": h.kind.value if h.kind else None,
                       "since": h.since, "note": h.note}
                for name, h in self._entries.items()}


def _today() -> str:
    return datetime.date.today().isoformat()


@dataclasses.dataclass(frozen=True)
class RouteResult:
    ok: bool
    text: str = ""
    provider_used: str | None = None
    requested: str = ""
    failures: tuple = ()
    attempts: int = 0
    note: str = ""

    @property
    def tried(self) -> list:
        return [f.provider for f in self.failures]


class FallbackRouter:
    """Try the requested provider, then the ordered fallbacks (D12).

    Guarantees from RELIABILITY.md §5: the request is rebuilt identically for
    every provider, the provider that answered is named, dead providers are
    skipped before budget is spent, and one budget covers the whole route.
    """

    # Two consecutive network-level failures across providers means the user's
    # own link is down; further attempts only burn the budget (§1).
    NETWORK_DOWN_AFTER = 2

    def __init__(self, callables: dict, *, order=None, health=None,
                 policy: RetryPolicy | None = None, result_is_valid=None):
        self.callables = dict(callables)
        self.order = list(order) if order is not None else list(self.callables)
        self.health = health if health is not None else HealthTracker()
        self.policy = policy or RetryPolicy()
        self.result_is_valid = result_is_valid

    def _usable(self, value) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if self.result_is_valid is not None:
            return bool(self.result_is_valid(value))
        return True

    def _alive(self, name: str) -> bool:
        """A provider worth spending budget on: registered and not skippable."""
        return name in self.callables and not self.health.get(name).skippable

    def _sequence(self, requested: str | None) -> list:
        if requested is None:
            return [n for n in self.order if self._alive(n)]
        # A provider already marked dead is skipped even when the user picked
        # it explicitly — §5.3 exists precisely to avoid burning the budget on
        # a retired host. An unknown request degrades to the ordered list.
        head = [requested] if self._alive(requested) else []
        return head + [n for n in self.order
                       if n != requested and self._alive(n)]

    def route(self, text, src, tgt, requested: str | None = None, *,
              on_event=None, budget: Budget | None = None) -> RouteResult:
        budget = budget or Budget.start(self.policy.total_budget)
        failures: list[Failure] = []
        network_streak = 0
        attempts = 0

        for name in self._sequence(requested):
            if failures and budget.expired():
                if on_event is not None:
                    on_event(f"budget exhausted before {name}")
                break
            fn = self.callables[name]

            def _call(_fn=fn):
                return _fn(text, src, tgt)

            outcome = run_provider(_call, name, policy=self.policy,
                                   budget=budget, clock=budget._clock,
                                   on_event=on_event)
            if isinstance(outcome, Success) and self._usable(outcome.value):
                self.health.record_success(name)
                attempts += outcome.attempts
                note = ""
                if requested is not None and name != requested:
                    note = f"{name} answered (fallback from {requested})"
                return RouteResult(True, _as_text(outcome.value), name,
                                   requested or name, tuple(failures), attempts,
                                   note)

            if isinstance(outcome, Success):
                outcome = Failure(name, ErrorKind.MALFORMED_RESPONSE, None,
                                  "invalid result", outcome.attempts,
                                  outcome.elapsed)
            attempts += outcome.attempts
            failures.append(outcome)
            self.health.record_failure(name, outcome.kind)

            if outcome.kind in NO_FALLBACK:
                if on_event is not None:
                    on_event(f"{name}: {outcome.kind.value} -> no fallback")
                break

            if outcome.kind in NETWORK_LEVEL:
                network_streak += 1
                if network_streak >= self.NETWORK_DOWN_AFTER:
                    # Re-label the consecutive network-level failures as the
                    # user's link being down: the honest reason to stop here.
                    for index, prior in enumerate(failures):
                        if prior.kind in NETWORK_LEVEL:
                            failures[index] = dataclasses.replace(
                                prior, kind=ErrorKind.USER_NETWORK_DOWN)
                    if on_event is not None:
                        on_event("network appears down; stopping fallback")
                    break
            else:
                network_streak = 0

        return RouteResult(False, "", None, requested or "",
                           tuple(failures), attempts, _failure_note(failures))


def _as_text(value) -> str:
    return value if isinstance(value, str) else str(value)


def _failure_note(failures) -> str:
    if not failures:
        return "no provider available"
    if all(f.kind is ErrorKind.PROVIDER_DEAD for f in failures):
        return "providers unavailable: " + ", ".join(f.provider for f in failures)
    kinds = sorted({f.kind.value for f in failures})
    return ("no provider answered (" + ", ".join(kinds) + "): "
            + ", ".join(f.provider for f in failures))


# --------------------------------------------------------------------------
# Adapter: the port's service callables behind the reliability policy.
#
# This is Phase 1's seam into app.py. It deliberately does NOT replace
# do_translate(): the live-path cutover is Phase 5. What it does is make the
# existing per-service callables reachable under one bounded, falling-back
# route, so Phase 1 has a testable guarantee, and Phase 5 has something to
# move rather than to invent.
#
# Two invariants the adapter exists to hold:
#   1. Request-shaping (RemoveLineBreaks, the 5000-char cut) happens ONCE,
#      before the first attempt — never once per provider.
#   2. The detect shortcut and the back-translation append stay OUTSIDE.
#      The detect shortcut changes the src that providers see, so running it
#      per-attempt could hand a retry a different source language; the
#      back-translation append post-processes a final answer, so running it
#      per-attempt would append once per failed provider. Both belong after the
#      loop, exactly once, on the returned provider_used.
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Result:
    provider_used: str
    text: str
    requested: str = ""
    failures: tuple = ()
    attempts: int = 0
    note: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.provider_used)


def normalize_request(text, src, tgt, *, remove_line_breaks=False,
                       max_chars=5000) -> tuple:
    """Apply the shaping transforms the live path applies, exactly once.

    Order mirrors do_translate(): RemoveLineBreaks first (it collapses
    newlines), then the length cap. Applied here so no provider sees a
    differently-shaped request than its neighbour.
    """
    text = (text or "").strip()
    if not text:
        return "", src, tgt
    if remove_line_breaks:
        import re

        text = re.sub(r"\s*\n\s*", " ", text)
    if max_chars:
        text = text[:max_chars]
    return text, src, tgt


class ProviderRouter:
    """Route a translate request across app.py's service callables.

    ``callables`` maps a service id to ``fn(text, src, tgt)`` — the same
    signature app.py's ``_t_*`` adapters already have. ``order`` is the
    fallback order (ServicesOrder ids as names); ``requested`` is the user's
    explicit choice and always runs first unless already marked dead.
    """

    def __init__(self, callables: dict, *, order=None, health=None,
                 policy: RetryPolicy | None = None, remove_line_breaks=False,
                 max_chars=5000, logger=None):
        self.router = FallbackRouter(callables, order=order, health=health,
                                     policy=policy)
        self.remove_line_breaks = remove_line_breaks
        self.max_chars = max_chars
        self.logger = logger

    @property
    def health(self) -> HealthTracker:
        return self.router.health

    def mark_dead(self, providers, note="dead:host-retired") -> None:
        self.router.health.mark_unavailable(providers, note)

    def translate(self, service, text, src, tgt, *, config=None,
                  on_event=None) -> Result:
        """Translate with bounded retry + ServicesOrder fallback.

        ``config`` is read only for the shaping flags this class owns
        (``Advanced.RemoveLineBreaks``); nothing else is consumed, so a caller
        can pass a real Options.json dict or None.
        """
        cfg = config if config is not None else {}
        remove_line_breaks = bool(
            cfg.get("Advanced", {}).get("RemoveLineBreaks",
                                        self.remove_line_breaks))

        text, src, tgt = normalize_request(
            text, src, tgt, remove_line_breaks=remove_line_breaks,
            max_chars=self.max_chars)
        if not text:
            return Result("", "", service or "", attempts=0,
                          note="empty request")

        route = self.router.route(text, src, tgt, service or None,
                                  on_event=on_event)
        if route.ok:
            return Result(route.provider_used, route.text,
                          route.requested, route.failures, route.attempts,
                          route.note)
        # A failed route carries its own diagnostic note; the UI surfaces the
        # native "no data" string for the text and this note for the reason.
        return Result("", "", route.requested, route.failures, route.attempts,
                      route.note)

    def translate_with_backtranslation(self, service, text, src, tgt, *,
                                       back_translate=False, config=None,
                                       on_event=None) -> Result:
        """Same route, then append the back-translation ONCE, after the loop.

        The back-translation uses the provider that actually answered — not
        the one the user picked — because that is the provider whose output is
        being back-translated. The appended segment is marked so the caller can
        split it back apart for persistence (see app.py's EditBackTranslation).
        """
        primary = self.translate(service, text, src, tgt, config=config,
                                 on_event=on_event)
        if not primary.ok or not back_translate:
            return primary
        try:
            back_fn = self.router.callables.get(primary.provider_used)
            if back_fn is None:
                return primary
            back = back_fn(primary.text[:self.max_chars or 5000], tgt, src)
            if back and not back.startswith("No data"):
                combined = (primary.text + "\n\n--- back-translation ---\n"
                            + back)
                return dataclasses.replace(primary, text=combined)
        except Exception as exc:
            if self.logger is not None:
                self.logger("back-translation failed: %r" % (exc,))
        return primary


BACKTRANSLATION_MARKER = "\n\n--- back-translation ---\n"


def split_backtranslation(text: str) -> tuple:
    """Split a combined result into (main, back) for separate persistence.

    Inverse of the append in translate_with_backtranslation(), so the value
    saved to Contents.EditBackTranslation is exactly the segment that was
    appended. NOTE: this marker is a port convention — the native binary has no
    `back-translation` string (see docs/review/D10_SPOTCHECK_Contents_2026-10-10.md
    §4a), so this split is about our own round-trip, not native fidelity.
    """
    if BACKTRANSLATION_MARKER in text:
        main, back = text.split(BACKTRANSLATION_MARKER, 1)
        return main.rstrip(), back.strip()
    return text, ""

