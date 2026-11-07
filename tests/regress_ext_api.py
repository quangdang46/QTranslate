"""regress_ext_api -- PluginContext-parity surface on ExtensionAPI.

GAP_AUDIT_2 item 5: the .tmp ``PluginContext`` gives every plugin a
scoped data directory, ``notify``, a host-configured HTTP client and
lifecycle hooks. This suite pins the port's mapping, against isolated
fake registries and temp dirs:

  * ``api.data_dir`` is ``<tmp>/extensions_data/<sanitised id>/``,
    created lazily on access and isolated per extension;
  * ``api.notify`` reaches a host-registered hook (and honestly
    no-ops without one -- ``qtranslate.notify`` may not exist yet);
  * ``api.on_load`` / ``api.on_unload`` / ``api.on_settings_changed``
    fire on the load/disable/set_setting paths, and a raising
    ``on_load`` fails the load fail-open;
  * ``api.http_get`` / ``api.http_post`` go through
    ``session._net_open`` (proxy/timeout/retry are the user's) with
    JSON body support -- pinned with a stubbed opener, no network.
"""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.extensions import ExtensionManager  # noqa: E402
from qtranslate import registry as real_registry  # noqa: E402
import qtranslate.config as _config  # noqa: E402
import qtranslate.session as _session  # noqa: E402


class FakeReg:
    """Isolated stand-in for qtranslate.registry (same as the
    lifecycle suite): own TRANSLATORS + dispatch tables, no globals."""

    def __init__(self):
        self._google = lambda *a: "google"
        self.TRANSLATORS = {"google": self._google}
        self.DICT_EXT = {}
        self.TTS_EXT = {}
        self.OCR_EXT = {}
        self.SPELL_EXT = {}
        self.WORKFLOW_EXT = {}

    def reset_router(self):
        pass


def manifest(ext_id, caps, **overrides):
    base = {"id": ext_id, "name": ext_id + " display", "version": "0.1.0",
            "sdk_version": "1.0", "entrypoint": "__init__:register",
            "capabilities": caps}
    base.update(overrides)
    return base


def write_ext(root, name, man, source):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    with io.open(os.path.join(folder, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    return folder


class FakeResp:
    status = 201

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


root = tempfile.mkdtemp(prefix="qt_extapi_")
cfg = os.path.join(root, "Options.json")
saved_default = _config.DEFAULT_PATH
_config.DEFAULT_PATH = cfg
try:
    events = os.path.join(root, "events.log")

    # ext_a exercises every capability; ext_b proves data-dir isolation.
    SRC_A = (
        "import os\n"
        "EVENTS = %r\n"
        "def _log(msg):\n"
        "    with open(EVENTS, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(msg + '\\n')\n"
        "def register(api):\n"
        "    d = api.data_dir\n"
        "    with open(os.path.join(d, 'mark.txt'), 'w') as fh:\n"
        "        fh.write('a')\n"
        "    api.notify('warning', 'Hello', 'Body text')\n"
        "    api.on_load(lambda a: _log('load'))\n"
        "    api.on_unload(lambda a: _log('unload'))\n"
        "    api.on_settings_changed(\n"
        "        lambda k, v: _log('settings:%%s=%%s' %% (k, v)))\n"
    ) % events
    SRC_B = (
        "import os\n"
        "def register(api):\n"
        "    d = api.data_dir\n"
        "    with open(os.path.join(d, 'mark.txt'), 'w') as fh:\n"
        "        fh.write('b')\n"
    )
    ext_root = os.path.join(root, "extensions")
    os.makedirs(ext_root)
    write_ext(ext_root, "ext_a",
              manifest("ext.a", ["provider"]), SRC_A)
    write_ext(ext_root, "ext_b",
              manifest("ext.b", ["provider"]), SRC_B)

    m = ExtensionManager(FakeReg())
    sent = []
    m.set_notify_hook(
        lambda eid, sev, title, msg: sent.append(
            (eid, sev, title, msg)))
    report = m.load_dir(ext_root)
    by_id = {r["id"]: r for r in report}
    ck("both extensions load",
       by_id.get("ext.a", {}).get("status") == "loaded"
       and by_id.get("ext.b", {}).get("status") == "loaded",
       str(report))

    # ---- data dir -------------------------------------------------------
    base = os.path.join(root, "extensions_data")
    dir_a = os.path.join(base, "ext_a")       # '.' sanitised to '_'
    dir_b = os.path.join(base, "ext_b")
    ck("data dir created under extensions_data",
       os.path.isdir(dir_a) and os.path.isdir(dir_b),
       "a=%r b=%r" % (dir_a, dir_b))
    ck("data dirs are per-extension",
       dir_a != dir_b
       and open(os.path.join(dir_a, "mark.txt")).read() == "a"
       and open(os.path.join(dir_b, "mark.txt")).read() == "b")
    ck("data_dir is a str path on the api",
       isinstance(m._ext_apis["ext.a"].data_dir, str)
       and os.path.isdir(m._ext_apis["ext.a"].data_dir))
    weird = m.data_dir_for("../escape")
    ck("manifest id cannot traverse the data root",
       os.path.dirname(weird) == os.path.abspath(base)
       and ".." not in weird)

    # ---- notify ----------------------------------------------------------
    ck("notify reached the host hook",
       ("ext.a", "warning", "Hello", "Body text") in sent, str(sent))
    api_a = m._ext_apis["ext.a"]
    ck("notify returns True with a hook",
       api_a.notify("error", "T", "M") is True)
    ck("bogus severity coerces to info",
       api_a.notify("bogus", "T", "M") is True
       and sent[-1][1] == "info", str(sent[-1:]))
    m.set_notify_hook(None)
    # The fallback is the optional qtranslate.notify module (the
    # NotificationBus port, sibling bead). When it exists the call must
    # deliver a real Notification tagged with the extension id; when it
    # does not, the call is an honest no-op -- never an exception.
    try:
        from qtranslate import notify as _N
    except Exception:                   # noqa: BLE001
        _N = None
    if _N is not None:
        got = []
        bus = _N.default_bus()
        bus.subscribe(got.append)
        try:
            ck("notify without a hook posts to the app bus",
               api_a.notify("error", "BusTitle", "BusBody") is True)
            hit = [x for x in got
                   if getattr(x, "title", "") == "BusTitle"]
            ck("bus notification carries severity+source",
               hit and hit[0].severity == _N.Severity.ERROR
               and hit[0].source == "ext.a"
               and hit[0].body == "BusBody",
               repr(hit[:1]))
        finally:
            bus.unsubscribe(got.append)
    else:
        ck("notify without a surface is a safe no-op",
           api_a.notify("info", "T", "M") in (True, False))
    m.set_notify_hook(
        lambda eid, sev, title, msg: sent.append(
            (eid, sev, title, msg)))

    # ---- lifecycle hooks -------------------------------------------------
    def _events():
        if not os.path.exists(events):
            return []
        with io.open(events, encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if ln.strip()]

    ck("on_load fired during load", "load" in _events(), str(_events()))

    # on_settings_changed via the real set_setting path (temp config).
    api_a.set_setting("greeting", "hi")
    ck("on_settings_changed fired with key+value",
       "settings:greeting=hi" in _events(), str(_events()))
    ck("the setting itself persisted",
       m.get_setting("ext.a", "greeting") == "hi")

    # on_unload on disable, then on_load again on enable.
    ck("disable known id", m.disable("ext.a") is True)
    ck("on_unload fired", "unload" in _events(), str(_events()))
    out = m.enable("ext.a", saved={}, disabled=set())
    ck("enable re-loads", out is not None
       and out.get("status") == "loaded", str(out))
    ck("on_load fired again after re-enable",
       _events().count("load") == 2, str(_events()))

    # A raising on_load fails the whole load, fail-open.
    write_ext(ext_root, "ext_bad",
              manifest("ext.bad", ["provider"]),
              "def register(api):\n"
              "    api.on_load(lambda a: 1 / 0)\n")
    m3 = ExtensionManager(FakeReg())
    rep3 = m3.load_dir(ext_root)
    bad = [r for r in rep3 if r.get("id") == "ext.bad"]
    ck("raising on_load disables the extension",
       bad and bad[0]["status"] == "disabled"
       and "ZeroDivisionError" in (bad[0].get("reason") or ""),
       str(bad))
    ck("failing on_load left no hooks behind",
       "ext.bad" not in m3._hooks)

    # ---- scoped HTTP (stubbed opener, no network) ------------------------
    calls = []

    class _StubResp(FakeResp):
        pass

    def fake_net_open(req, opener=None, data=None, timeout=None):
        calls.append({"url": req.full_url, "data": req.data,
                      "method": req.get_method(),
                      "headers": dict(req.header_items()),
                      "timeout": timeout})
        return _StubResp(b"payload")

    saved_net_open = _session._net_open
    _session._net_open = fake_net_open
    try:
        body = api_a.http_get("http://example.test/x",
                              headers={"X-Test": "1"})
        ck("http_get returns the decoded body", body == "payload",
           repr(body))
        ck("http_get is a GET", calls[-1]["method"] == "GET")
        ck("http_get forwards headers",
           calls[-1]["headers"].get("X-test") == "1",
           str(calls[-1]["headers"]))

        body = api_a.http_post("http://example.test/y",
                               json={"a": 1})
        ck("http_post returns the decoded body", body == "payload")
        last = calls[-1]
        ck("http_post sends JSON with the right content type",
           last["method"] == "POST"
           and json.loads(last["data"].decode("utf-8")) == {"a": 1}
           and last["headers"].get("Content-type", "")
           .startswith("application/json"),
           str(last))
        status, text = m.http_request("PUT", "http://example.test/z",
                                      data="raw", timeout=7)
        ck("http_request returns (status, text)",
           status == 201 and text == "payload", "%r %r" % (status, text))
        ck("timeout override reaches the opener",
           calls[-1]["timeout"] == 7, str(calls[-1]))
    finally:
        _session._net_open = saved_net_open
finally:
    _config.DEFAULT_PATH = saved_default
    import shutil
    shutil.rmtree(root, ignore_errors=True)

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_ext_api: all checks ok (%d assertions)" % n[0])
