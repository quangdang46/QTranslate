"""Behaviour pins for the reliability audit's four open items (2026-10-21).

Closes, behaviourally, the items left open in
``docs/review/RELIABILITY_WIRING_AUDIT_2026-10-10.md``:

  §2 (3)  detect failure returned "auto" with no signal
  §2 (1)(2)(5)  the classified failures never reached the caller
  §3     TTS failures went to ``print``, and a CONFIG_ERROR was misrouted
  §7     ``Failure.log_line()`` was composed but never written anywhere

Every assertion here CALLS the real function and reads a real return value
or a real captured line — the log sink's own output, a real file on disk.
There are no source-text greps: this repo already shipped a 97-assertion
suite that pinned strings and let five real defects through.

Offline and deterministic: the provider table is replaced with recording
doubles, so no request leaves the machine and nothing sleeps.
"""
import errno
import os
import shutil
import sys
import tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import engine as E            # noqa: E402
from qtranslate import registry as RG         # noqa: E402
from qtranslate import reliability as R       # noqa: E402

# --------------------------------------------------------------------------
# harness: a sink that captures what was written, and provider doubles
# --------------------------------------------------------------------------
LINES = []


def _capture(line):
    LINES.append(line)


def _parse(line):
    """key=value pairs of one log line (detail may contain spaces)."""
    out = {}
    for part in line.split(" "):
        if "=" in part:
            key, _, value = part.partition("=")
            out.setdefault(key, value)
    return out


_orig_table = dict(RG.TRANSLATORS)
_orig_singleton = getattr(RG, "_ROUTER_SINGLETON", None)
_orig_detect = RG.detect_language


def _install(table):
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(table)
    RG._ROUTER_SINGLETON = None


def _restore():
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_orig_table)
    RG._ROUTER_SINGLETON = _orig_singleton
    RG.detect_language = _orig_detect


def _ok_provider(name, calls):
    def _f(t, s, g, **_kw):
        calls.append((name, t, s, g))
        return "%s:%s" % (name, t)
    return _f


def _dead_provider(name, calls, exc=None):
    def _f(t, s, g, **_kw):
        calls.append((name, t, s, g))
        raise exc if exc is not None else ValueError("boom")
    return _f


# --------------------------------------------------------------------------
# §7 — the log sink: a failure must actually be WRITTEN
# --------------------------------------------------------------------------
LINES.clear()
R.set_log_sink(_capture)
ck("a sink can be installed and read back",
   R.get_log_sink() is _capture, repr(R.get_log_sink()))

# 1. A classified failure reaches the sink, with the §7 fields.
_install({"alpha": _dead_provider("alpha", [])})
try:
    router = R.ProviderRouter({"alpha": _dead_provider("alpha", [])},
                               order=["alpha"], policy=R.RetryPolicy())
    res = router.translate("alpha", "hello", "en", "vi")
finally:
    _restore()
ck("the route failed", not res.ok, repr(res.note))
ck("the sink received a line for the failed provider",
   len(LINES) == 1, repr(LINES))
_fields = _parse(LINES[0]) if LINES else {}
ck("the logged line names the provider",
   _fields.get("provider") == "alpha", repr(LINES))
ck("the logged line names the kind",
   _fields.get("kind") == "malformed-response", repr(LINES))
ck("the logged line carries the attempt count",
   _fields.get("attempts") == "1", repr(LINES))
ck("the logged line carries the elapsed time",
   "elapsed" in _fields, repr(LINES))
ck("the logged line says whether the route fell back",
   _fields.get("fell_back") == "0", repr(LINES))
ck("the failure is also on the result",
   len(res.failures) == 1 and res.failures[0].provider == "alpha",
   repr(res.failures))

# 2. Every provider of a multi-provider route is accounted for — once each.
LINES.clear()
_calls = []
_install({"alpha": _dead_provider("alpha", _calls),
          "beta": _dead_provider("beta", _calls)})
try:
    router = R.ProviderRouter(
        {"alpha": _dead_provider("alpha", _calls),
         "beta": _dead_provider("beta", _calls)},
        order=["alpha", "beta"], policy=R.RetryPolicy())
    res2 = router.translate("alpha", "hello", "en", "vi")
finally:
    _restore()
ck("two failing providers produce two failures",
   len(res2.failures) == 2, repr(res2.failures))
ck("two failing providers produce two log lines",
   len(LINES) == 2, repr(LINES))
ck("each provider is logged once",
   sorted(_parse(line).get("provider") for line in LINES) == ["alpha", "beta"],
   repr(LINES))
ck("a failure that was followed by another provider is marked as fallen back",
   _parse(LINES[0]).get("fell_back") == "1", repr(LINES))
ck("the last failure is not marked as fallen back — nothing followed it",
   _parse(LINES[-1]).get("fell_back") == "0", repr(LINES))

# 2b. A kind that must not fall back (the user's own link is down) stops
#     the route, and the log says which kind it was.
LINES.clear()
_calls = []


def _link_down(t, s, g, **_kw):
    _calls.append(t)
    raise OSError(errno.ENETDOWN, "Network is down")


_install({"alpha": _link_down})
try:
    router = R.ProviderRouter({"alpha": _link_down, "beta": _ok_provider("beta", [])},
                               order=["alpha", "beta"],
                               policy=R.RetryPolicy())
    res_down = router.translate("alpha", "hello", "en", "vi")
finally:
    _restore()
ck("a dead link stops the route — no fallback provider is tried",
   len(_calls) == 1, repr(_calls))
ck("the dead link is classified user-network-down",
   res_down.failures and res_down.failures[0].kind
   is R.ErrorKind.USER_NETWORK_DOWN, repr(res_down.failures))
ck("the log names the dead-link kind",
   LINES and _parse(LINES[0]).get("kind") == "user-network-down", repr(LINES))
ck("the log says the route did not fall back",
   LINES and _parse(LINES[0]).get("fell_back") == "0", repr(LINES))

# 3. A file sink writes to a real file (the audit's "one thing worth doing").
_tmpdir = tempfile.mkdtemp(prefix="qt-rel-audit-")
try:
    _logfile = os.path.join(_tmpdir, "reliability.log")
    _sink = R.FileLogSink(_logfile)
    ck("the file sink writes what it is given", _sink("provider=x kind=y") is True)
    with open(_logfile, encoding="utf-8") as _fh:
        _content = _fh.read()
    ck("the line really is in the file",
       _content.strip() == "provider=x kind=y", repr(_content))
    ck("the sink is not installed by merely being constructed",
       R.get_log_sink() is _capture, repr(R.get_log_sink()))

    # 4. The engine wires the file sink: a failed translation writes a file.
    _env_path = os.path.join(_tmpdir, "engine.log")
    _old_env = os.environ.get(R.LOG_PATH_ENV)
    os.environ[R.LOG_PATH_ENV] = _env_path
    R.set_log_sink(None)          # let the engine install the file sink
    _calls = []
    _install({"alpha": _dead_provider("alpha", _calls)})
    try:
        _eng = E.translate("alpha", "hello", "vi", src="en")
    finally:
        _restore()
        R.set_log_sink(_capture)
        if _old_env is None:
            os.environ.pop(R.LOG_PATH_ENV, None)
        else:
            os.environ[R.LOG_PATH_ENV] = _old_env
    ck("the engine installed a file sink", R.get_log_sink() is not None,
       repr(R.get_log_sink()))
    ck("the failed translation wrote a log file",
       os.path.exists(_env_path), _env_path)
    if os.path.exists(_env_path):
        with open(_env_path, encoding="utf-8") as _fh:
            _engine_log = _fh.read()
        ck("the engine's log file names the provider that failed",
           "provider=alpha" in _engine_log, repr(_engine_log))
        ck("the engine's log file names the kind",
           "kind=malformed-response" in _engine_log, repr(_engine_log))

    # 4b. End to end: the "which layer failed" report is answerable from
    #     the file — a dead link shows the detection failure AND the
    #     provider failure, in the order they happened.
    _env_path2 = os.path.join(_tmpdir, "engine2.log")
    _old_env = os.environ.get(R.LOG_PATH_ENV)
    os.environ[R.LOG_PATH_ENV] = _env_path2
    R.set_log_sink(None)
    _calls = []
    _install({"alpha": _dead_provider("alpha", _calls)})
    RG.detect_language = lambda t: "auto"
    try:
        E.translate("alpha", "hello", "vi", src="auto")
    finally:
        _restore()
        R.set_log_sink(_capture)
        if _old_env is None:
            os.environ.pop(R.LOG_PATH_ENV, None)
        else:
            os.environ[R.LOG_PATH_ENV] = _old_env
    ck("the dead link produced a log file", os.path.exists(_env_path2),
       _env_path2)
    if os.path.exists(_env_path2):
        with open(_env_path2, encoding="utf-8") as _fh:
            _both = _fh.read()
        ck("the file shows the detection failure",
           "provider=detect" in _both, repr(_both))
        ck("the file shows the provider failure",
           "provider=alpha" in _both, repr(_both))
        ck("the detection failure comes first — it happened first",
           _both.find("provider=detect") < _both.find("provider=alpha"),
           repr(_both))
finally:
    shutil.rmtree(_tmpdir, ignore_errors=True)

# 5. A sink that raises must not break the caller.
def _boom_sink(line):
    raise IOError("disk on fire")


R.set_log_sink(_boom_sink)
ck("a broken sink does not propagate",
   R.log_failure(R.Failure("alpha", R.ErrorKind.TIMEOUT)) is False)
R.set_log_sink(_capture)

# 6. An installed sink is never replaced by the default one.
_before = R.get_log_sink()
ck("ensure_log_sink keeps an installed sink",
   R.ensure_log_sink() is _before, repr(R.get_log_sink()))

# --------------------------------------------------------------------------
# §2 — the classified failures must reach the caller
# --------------------------------------------------------------------------
LINES.clear()
_calls = []
_install({"alpha": _dead_provider("alpha", _calls)})
try:
    _res = E.translate("alpha", "hello", "vi", src="en")
finally:
    _restore()
ck("a failed translation still shows the native error string",
   "No data returned" in _res.text, repr(_res.text))
ck("a failed translation now carries the classified failures",
   len(_res.failures) == 1, repr(_res.failures))
ck("the failure carries a reliability kind",
   _res.failures and isinstance(_res.failures[0].kind, R.ErrorKind),
   repr(_res.failures))
ck("the failure names the provider that failed",
   _res.failures and _res.failures[0].provider == "alpha",
   repr(_res.failures))
ck("the note names the kind instead of asserting a timeout",
   "malformed-response" in _res.note, repr(_res.note))
ck("the attempt count survives the round trip",
   _res.attempts >= 1, repr(_res.attempts))

# 7. A back-translation that dies is recorded, not swallowed.
LINES.clear()
_calls = []


def _back_call(t, s, g, **_kw):
    _calls.append((t, s, g))
    if len(_calls) == 1:
        return "primary"
    raise ValueError("back-translation exploded")


_install({"alpha": _back_call})
try:
    _res2 = E.translate("alpha", "hello", "vi", src="en", back_translate=True)
finally:
    _restore()
ck("the translation itself still succeeded", _res2.ok, repr(_res2.note))
ck("the missing back-translation is recorded",
   any("back-translation" in (f.detail or "") for f in _res2.failures),
   repr(_res2.failures))
ck("the note says the back-translation failed",
   "back-translation failed" in _res2.note, repr(_res2.note))
ck("the missing back-translation was logged",
   any("back-translation" in line for line in LINES), repr(LINES))

# --------------------------------------------------------------------------
# §2 (3) — a detection that names no source: degrade, record, never silent
# --------------------------------------------------------------------------
LINES.clear()
_calls = []
_install({"alpha": _ok_provider("alpha", _calls)})
RG.detect_language = lambda t: "auto"          # the chain-exhausted sentinel
try:
    _det = E.translate("alpha", "hello", "vi", src="auto")
finally:
    _restore()
ck("a failed detection does not stop the translation", _det.ok, repr(_det.note))
ck("the provider was still called", len(_calls) == 1, repr(_calls))
ck("the request degraded to the auto source",
   _calls and _calls[0][2] == "auto", repr(_calls))
ck("the detection failure is on the result",
   any(f.provider == "detect" for f in _det.failures), repr(_det.failures))
ck("the detection failure is classified",
   any(f.provider == "detect"
       and f.kind is R.ErrorKind.USER_NETWORK_DOWN for f in _det.failures),
   repr(_det.failures))
ck("the detection failure was logged",
   any(line.startswith("provider=detect ") for line in LINES), repr(LINES))
ck("the logged detection failure names its kind",
   any(_parse(line).get("kind") == "user-network-down"
       for line in LINES if line.startswith("provider=detect ")),
   repr(LINES))

# 8. A detection that fails while the source is already concrete keeps the
#    concrete source (the request is not degraded) but is still recorded.
LINES.clear()
_calls = []
_install({"alpha": _ok_provider("alpha", _calls)})
RG.detect_language = lambda t: "auto"
try:
    _det2 = E.translate("alpha", "hello", "vi", src="en", auto_detect=True)
finally:
    _restore()
ck("a concrete source survives a failed detection",
   _calls and _calls[0][2] == "en", repr(_calls))
ck("the failed detection is still recorded",
   any(f.provider == "detect" for f in _det2.failures), repr(_det2.failures))
ck("the failed detection was still logged",
   any(line.startswith("provider=detect ") for line in LINES), repr(LINES))

# 9. No false positive: a detection that names a source records nothing.
LINES.clear()
_calls = []
_install({"alpha": _ok_provider("alpha", _calls)})
RG.detect_language = lambda t: "en"
try:
    _det3 = E.translate("alpha", "hello", "vi", src="auto")
finally:
    _restore()
ck("a successful detection records no detection failure",
   not any(f.provider == "detect" for f in _det3.failures),
   repr(_det3.failures))
ck("a successful detection logs no detection line",
   not any(line.startswith("provider=detect ") for line in LINES),
   repr(LINES))
ck("a successful detection gives the provider the detected source",
   _calls and _calls[0][2] == "en", repr(_calls))

# 10. The chain-level classification is the documented one.
_ck_failure = R.detect_failure()
ck("a detection failure is classified user-network-down",
   _ck_failure.kind is R.ErrorKind.USER_NETWORK_DOWN, repr(_ck_failure))
ck("a detection failure is recorded under the detect provider",
   _ck_failure.provider == "detect", repr(_ck_failure))
ck("a detection failure says what it does not know",
   "auto sentinel" in _ck_failure.detail, repr(_ck_failure.detail))

# --------------------------------------------------------------------------
# §3 — the TTS fallback policy: CONFIG_ERROR must not fall back
# --------------------------------------------------------------------------
_proxy = urllib.error.URLError("proxy error: cannot reach the proxy")
_action, _tts_fail = R.tts_failure_plan(_proxy)
ck("a proxy misconfiguration is classified config-error",
   _tts_fail.kind is R.ErrorKind.CONFIG_ERROR, repr(_tts_fail))
ck("a config error does not fall back to the other engine",
   _action == "surface", _action)
ck("the tts failure carries the kind for the log",
   "kind=config-error" in _tts_fail.log_line(), repr(_tts_fail.log_line()))

_timeout = TimeoutError("timed out")
_action2, _tts_fail2 = R.tts_failure_plan(_timeout)
ck("a timeout is classified timeout",
   _tts_fail2.kind is R.ErrorKind.TIMEOUT, repr(_tts_fail2))
ck("a timeout falls back to the offline engine",
   _action2 == "fallback", _action2)

_down = OSError(errno.ENETDOWN, "Network is down")
_action3, _tts_fail3 = R.tts_failure_plan(_down)
ck("a dead link is classified user-network-down",
   _tts_fail3.kind is R.ErrorKind.USER_NETWORK_DOWN, repr(_tts_fail3))
ck("a dead link still falls back — the offline voice is local",
   _action3 == "fallback", _action3)

# The premise of the audit's §3 complaint: the misconfiguration IS what the
# classifier calls CONFIG_ERROR, and CONFIG_ERROR is in the no-fallback set.
ck("config-error is in the no-fallback set",
   R.ErrorKind.CONFIG_ERROR in R.NO_FALLBACK, repr(R.NO_FALLBACK))

R.set_log_sink(None)

print("regress_reliability_audit: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
