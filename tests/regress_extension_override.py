"""F1/F2 pin: override consistency across aliases + runtime-fallback policy.

F1 — a declared override of ``microsoft`` or ``bing`` updates **every** name
that shared the replaced callable, so ``TRANSLATORS``, ``router_order()`` and
``ExtensionManager.active()`` agree whichever alias was named. An alias
conflict (two extensions claiming aliases of one provider) applies **no**
override and keeps the built-in, and the outcome does not depend on discovery
order.

F2 (PA-B) — a runtime failure of an overriding extension falls through to the
next provider; the replaced built-in is **not** revived. The failure stays
traceable through ``Result.failures``/``provider_used``.

Offline, no window, no network (temp folders + fake providers only). Mutates
the live ``registry.TRANSLATORS`` table on purpose and restores it at the end.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import engine
from qtranslate import registry as RG
from qtranslate.extensions import ExtensionManager, load_user_extensions

_TABLE = RG.TRANSLATORS
_ORIGINAL = dict(RG.TRANSLATORS)
_builtin_bing = _ORIGINAL["microsoft"]


def restore():
    """Put the live dispatch table back to its pre-suite state."""
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIGINAL)
    RG.reset_router()


def write_ext(root, folder_name, ext_id, source, replaces=None):
    folder = os.path.join(root, folder_name)
    os.makedirs(folder)
    man = {"id": ext_id, "name": ext_id, "version": "0.1.0",
           "sdk_version": "1.0", "entrypoint": "__init__:register",
           "capabilities": ["provider"]}
    if replaces:
        man["replaces"] = replaces
    with io.open(os.path.join(folder, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    return folder


def replaces_ext(provider, text, target):
    return ("def register(api):\n"
            "    api.register_provider(%r,\n"
            "                          lambda t, s, g: %r + t,\n"
            "                          replaces=%r)\n"
            % (provider, text, target))


root = tempfile.mkdtemp(prefix="qt_ovr_")
try:
    ck("alias precondition: built-in microsoft and bing are one callable",
       _ORIGINAL["microsoft"] is _ORIGINAL["bing"])

    # --- F1: an override of microsoft reaches the alias bing ------------
    restore()
    ms_dir = os.path.join(root, "ms")
    os.makedirs(ms_dir)
    write_ext(ms_dir, "ext_ms", "ext.ms",
              replaces_ext("ext.ms", "MS:", "microsoft"),
              replaces=["microsoft"])
    rep = load_user_extensions(extensions_dir=ms_dir)
    ck("the microsoft override loads", rep and rep[0]["status"] == "loaded",
       str(rep))
    ck("overriding microsoft updates the alias bing (one callable)",
       RG.TRANSLATORS["microsoft"] is RG.TRANSLATORS["bing"]
       and RG.TRANSLATORS["microsoft"] is not _builtin_bing,
       repr(RG.TRANSLATORS["microsoft"]))
    ck("the alias is not a second fallback entry (rule b)",
       "microsoft" in RG.router_order() and "bing" not in RG.router_order(),
       str(RG.router_order()))
    m_after = ExtensionManager()
    ck("active() agrees for microsoft and bing",
       m_after.active("microsoft") is RG.TRANSLATORS["microsoft"]
       and m_after.active("bing") is RG.TRANSLATORS["microsoft"],
       repr((m_after.active("microsoft"), m_after.active("bing"))))
    res = engine.translate("microsoft", "hi", "vi", src="en")
    ck("translating through microsoft calls the extension",
       res.ok and res.text == "MS:hi", repr(res))
    res = engine.translate("bing", "hi", "vi", src="en")
    ck("translating through the alias calls the same extension",
       res.ok and res.text == "MS:hi", repr(res))

    # --- F1: the reverse direction (override bing updates microsoft) -----
    restore()
    bing_dir = os.path.join(root, "bing")
    os.makedirs(bing_dir)
    write_ext(bing_dir, "ext_bing", "ext.bing",
              replaces_ext("ext.bing", "BING:", "bing"),
              replaces=["bing"])
    load_user_extensions(extensions_dir=bing_dir)
    ck("overriding bing updates the alias microsoft (reverse)",
       RG.TRANSLATORS["microsoft"] is RG.TRANSLATORS["bing"]
       and RG.TRANSLATORS["microsoft"] is not _builtin_bing,
       repr(RG.TRANSLATORS["bing"]))
    ck("the manager's own alias view is updated too",
       ExtensionManager().active("microsoft") is ExtensionManager().active("bing"))
    ck("the reverse override is deduped from the fallback chain",
       "bing" not in RG.router_order(), str(RG.router_order()))

    # --- F1: a direct register()+commit() is protected too ---------------
    restore()

    def _fake_ms(t, s, g):
        return "FAKE"

    m_direct = ExtensionManager()
    m_direct.register("ext.fake_ms", _fake_ms, replaces="microsoft")
    m_direct.commit()
    ck("commit updates the manager's OWN alias view (both directions)",
       m_direct.active("microsoft") is _fake_ms
       and m_direct.active("bing") is _fake_ms,
       repr((m_direct.active("microsoft"), m_direct.active("bing"))))
    ck("the table agrees with a direct commit",
       RG.TRANSLATORS["microsoft"] is _fake_ms
       and RG.TRANSLATORS["bing"] is _fake_ms)

    restore()

    def _claim_a(t, s, g):
        return "A"

    def _claim_b(t, s, g):
        return "B"

    m_dc = ExtensionManager()
    m_dc.register("ext.dc_a", _claim_a, replaces="microsoft")
    m_dc.register("ext.dc_b", _claim_b, replaces="bing")  # alias: no raise here
    ck("a direct register keeps both alias claims for the user to resolve",
       m_dc.conflicts() == {"microsoft": "ext.dc_a", "bing": "ext.dc_b"},
       str(m_dc.conflicts()))
    m_dc.commit()
    ck("commit fails safe on a direct-register alias conflict",
       m_dc.conflicts() == {}
       and RG.TRANSLATORS["microsoft"] is _builtin_bing
       and RG.TRANSLATORS["bing"] is _builtin_bing
       and "ext.dc_a" not in RG.TRANSLATORS
       and "ext.dc_b" not in RG.TRANSLATORS,
       repr((m_dc.conflicts(), RG.TRANSLATORS["microsoft"])))

    # --- F1: alias conflict applies no override, keeps the built-in -----
    restore()
    conflict = os.path.join(root, "conflict")
    os.makedirs(conflict)
    write_ext(conflict, "a_ms", "ext.ms",
              replaces_ext("ext.ms", "MS:", "microsoft"),
              replaces=["microsoft"])
    write_ext(conflict, "b_bing", "ext.bing",
              replaces_ext("ext.bing", "BING:", "bing"),
              replaces=["bing"])
    m_conf = ExtensionManager()
    crep = m_conf.load_dir(conflict)
    by_id = {r["id"]: r for r in crep}
    ck("both alias-conflicting extensions are disabled",
       by_id["ext.ms"]["status"] == "disabled"
       and by_id["ext.bing"]["status"] == "disabled", str(crep))
    ck("the alias conflict is reported (the user must pick the winner)",
       "pick the winner" in by_id["ext.ms"]["reason"]
       and "pick the winner" in by_id["ext.bing"]["reason"], str(by_id))
    ck("no winner was selected, so no override remains",
       m_conf.conflicts() == {}, str(m_conf.conflicts()))
    ck("the conflicting providers are not registered",
       "ext.ms" not in m_conf.providers()
       and "ext.bing" not in m_conf.providers())
    ck("the built-in is intact under both alias names",
       RG.TRANSLATORS["microsoft"] is _builtin_bing
       and RG.TRANSLATORS["bing"] is _builtin_bing)
    rep = load_user_extensions(extensions_dir=conflict)
    ck("load_user_extensions commits nothing when the only claims conflict",
       all(r["status"] == "disabled" for r in rep)
       and RG.TRANSLATORS["microsoft"] is _builtin_bing, str(rep))

    # --- F1: outcome does not depend on discovery order ------------------
    conflict2 = os.path.join(root, "conflict2")
    os.makedirs(conflict2)
    write_ext(conflict2, "a_bing", "ext.bing",
              replaces_ext("ext.bing", "BING:", "bing"),
              replaces=["bing"])
    write_ext(conflict2, "b_ms", "ext.ms",
              replaces_ext("ext.ms", "MS:", "microsoft"),
              replaces=["microsoft"])
    crep2 = ExtensionManager().load_dir(conflict2)
    ck("the alias conflict disables both regardless of folder order",
       all(r["status"] == "disabled" for r in crep2), str(crep2))
    ck("the built-in is still intact after the reversed discovery order",
       RG.TRANSLATORS["microsoft"] is _builtin_bing
       and RG.TRANSLATORS["bing"] is _builtin_bing)

    # --- F1: repeated load/commit is idempotent --------------------------
    restore()
    idem = os.path.join(root, "idem")
    os.makedirs(idem)
    write_ext(idem, "ext_idem", "ext.idem",
              replaces_ext("ext.idem", "IDEM:", "microsoft"),
              replaces=["microsoft"])
    load_user_extensions(extensions_dir=idem)
    len1, order1 = len(RG.TRANSLATORS), list(RG.router_order())
    load_user_extensions(extensions_dir=idem)
    len2, order2 = len(RG.TRANSLATORS), list(RG.router_order())
    ck("a repeated load does not accumulate registrations",
       len1 == len2, "%d -> %d" % (len1, len2))
    ck("a repeated load does not change the router order",
       order1 == order2, "%r vs %r" % (order1, order2))
    ck("a repeated load keeps the alias identity",
       RG.TRANSLATORS["microsoft"] is RG.TRANSLATORS["bing"])
    ck("the extension still serves after a repeated load",
       engine.translate("microsoft", "z", "vi", src="en").text == "IDEM:z")

    # --- F2 (PA-B): a runtime failure of an override falls through -------
    # A controlled two-provider table keeps the fallback offline and lets us
    # observe whether the replaced built-in is revived.
    calls = []

    def builtin_good(t, s, g):
        calls.append("good")
        return "BUILTIN:" + t

    def alt(t, s, g):
        return "ALT:" + t

    restore()
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update({"good": builtin_good, "alt": alt})
    RG.reset_router()

    fail_dir = os.path.join(root, "fail")
    os.makedirs(fail_dir)
    write_ext(fail_dir, "ext_fail", "ext.fail",
              "def _boom(t, s, g):\n"
              "    raise ValueError('boom')\n"
              "def register(api):\n"
              "    api.register_provider('ext.fail', _boom,\n"
              "                          replaces='good')\n",
              replaces=["good"])
    frep = load_user_extensions(extensions_dir=fail_dir)
    ck("the failing override is a runtime failure, not a load failure",
       frep and frep[0]["status"] == "loaded", str(frep))
    ck("the override replaced the built-in under its id",
       RG.TRANSLATORS["good"] is not builtin_good)
    res = engine.translate("good", "x", "vi", src="en")
    ck("a runtime failure of an override falls through (PA-B)",
       res.ok and res.text == "ALT:x", repr(res))
    ck("provider_used names the provider that answered",
       res.provider_used == "alt", repr(res.provider_used))
    ck("the replaced built-in is NOT revived", calls == [], str(calls))
    ck("the failure is traceable in Result.failures",
       [f.provider for f in res.failures] == ["good"]
       and res.failures[0].kind.value == "malformed-response",
       repr([(f.provider, f.kind.value) for f in res.failures]))
    ck("Result.requested still records the originally requested provider",
       res.requested == "good", repr(res.requested))

    # --- F2 (PA-B): an empty result is invalid and also falls through ----
    restore()
    calls[:] = []
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update({"good": builtin_good, "alt": alt})
    RG.reset_router()

    mal_dir = os.path.join(root, "mal")
    os.makedirs(mal_dir)
    write_ext(mal_dir, "ext_mal", "ext.mal",
              "def register(api):\n"
              "    api.register_provider('ext.mal',\n"
              "                          lambda t, s, g: '',\n"
              "                          replaces='good')\n",
              replaces=["good"])
    load_user_extensions(extensions_dir=mal_dir)
    res = engine.translate("good", "x", "vi", src="en")
    ck("an empty-result override is not usable and falls through (PA-B)",
       res.ok and res.text == "ALT:x", repr(res))
    ck("the empty override is reported as malformed",
       any(f.provider == "good" and f.kind.value == "malformed-response"
           for f in res.failures),
       repr([(f.provider, f.kind.value) for f in res.failures]))
    ck("the replaced built-in is not revived for a malformed override",
       calls == [], str(calls))

    # --- tkinter-free ----------------------------------------------------
    src = io.open("qtranslate/extensions.py", encoding="utf-8").read()
    ck("extensions module imports no tkinter",
       re.search(r"^\s*(import|from)\s+tkinter", src, re.M) is None)
finally:
    restore()
    shutil.rmtree(root, ignore_errors=True)

print("regress_extension_override: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
