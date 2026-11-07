"""regress_ext_secrets_i18n -- SecretStore + localization port pins.

Round-3 bead qt-t00: the portable subset of .tmp's ``SecretStore``
(``ScopedSecretStore``) and plugin localization (``PluginLocalization`` /
``DisplayText``) landed on ``ExtensionAPI``. This suite pins, against
isolated fake registries, temp data dirs and a temp Options.json:

  * ``api.secrets_set/get/delete/contains`` round-trip through
    ``<data_dir>/<ext id>/secrets.json`` -- persisted, per-extension
    isolated, owner-only (0600) where the platform honours modes;
  * secrets never appear in ``get_config`` output or Options.json;
  * ``api.tr(key, fallback, *args)`` resolves the extension's own
    ``localization/<tag>.toml`` bundles along the active-language chain
    (written tag -> base language -> en) with fallback + printf args.
"""
import io
import json
import os
import stat
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
from qtranslate import ext_i18n  # noqa: E402
import qtranslate.config as _config  # noqa: E402


class FakeReg:
    """Isolated stand-in for qtranslate.registry (same as the sibling
    suites): own TRANSLATORS + dispatch tables, no globals."""

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


def manifest(ext_id):
    return {"id": ext_id, "name": ext_id + " display",
            "version": "0.1.0", "sdk_version": "1.0",
            "entrypoint": "__init__:register",
            "capabilities": ["provider"]}


def write_ext(root, name, man, source, localization=None):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    with io.open(os.path.join(folder, "manifest.json"), "w",
                 encoding="utf-8") as fh:
        fh.write(json.dumps(man))
    with io.open(os.path.join(folder, "__init__.py"), "w",
                 encoding="utf-8") as fh:
        fh.write(source)
    for tag, body in (localization or {}).items():
        ldir = os.path.join(folder, "localization")
        os.makedirs(ldir, exist_ok=True)
        with io.open(os.path.join(ldir, tag + ".toml"), "w",
                     encoding="utf-8") as fh:
            fh.write(body)
    return folder


SRC = "def register(api):\n    pass\n"

root = tempfile.mkdtemp(prefix="qt_extsec_")
cfg = os.path.join(root, "Options.json")
data_base = os.path.join(root, "extensions_data")
saved_default = _config.DEFAULT_PATH
_config.DEFAULT_PATH = cfg
try:
    ext_root = os.path.join(root, "extensions")
    os.makedirs(ext_root)

    # ext.a ships en + vi + zh bundles; ext.b ships none (fallback path).
    write_ext(ext_root, "ext_a", manifest("ext.a"), SRC,
              localization={
                  "en": '[mine]\n'
                        'greet = "Hello %s"\n'
                        'only_en = "English only"\n',
                  "vi": '[mine]\n'
                        'greet = "Xin chao %s"\n',
                  "zh": '[mine]\n'
                        'only_en = "Chinese only"\n',
              })
    write_ext(ext_root, "ext_b", manifest("ext.b"), SRC)

    # UI language: Vietnamese (tag "vi").
    _config.save({"General": {"LocaleFoderName": "Vietnamese"}})

    m = ExtensionManager(FakeReg(), data_dir=data_base)
    report = m.load_dir(ext_root)
    by_id = {r["id"]: r for r in report}
    ck("both extensions load",
       by_id.get("ext.a", {}).get("status") == "loaded"
       and by_id.get("ext.b", {}).get("status") == "loaded",
       str(report))
    api_a = m._ext_apis["ext.a"]
    api_b = m._ext_apis["ext.b"]

    # ---- secrets round-trip -------------------------------------------
    ck("secrets_get unset -> default",
       api_a.secrets_get("api_key", "dflt") == "dflt")
    ck("secrets_contains unset -> False",
       api_a.secrets_contains("api_key") is False)
    api_a.secrets_set("api_key", "s3cr3t-value")
    ck("secrets_get returns the value",
       api_a.secrets_get("api_key") == "s3cr3t-value")
    ck("secrets_contains set -> True",
       api_a.secrets_contains("api_key") is True)
    api_a.secrets_set("api_key", "s3cr3t-value")   # idempotent rewrite
    ck("second set keeps one entry",
       api_a.secrets_get("api_key") == "s3cr3t-value")

    sec_file = os.path.join(data_base, "ext_a", "secrets.json")
    ck("secrets file lives in the extension data_dir",
       os.path.isfile(sec_file), sec_file)
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(sec_file).st_mode)
        ck("secrets file is owner-only (0600)",
           mode & 0o077 == 0, oct(mode))

    # isolation: ext.b cannot see ext.a's secret
    ck("secrets are per-extension",
       api_b.secrets_get("api_key") is None
       and api_b.secrets_contains("api_key") is False)
    ck("no secrets file for an extension that set none",
       not os.path.exists(os.path.join(data_base, "ext_b",
                                       "secrets.json")))

    # type discipline (upstream SecretStore is string-only)
    try:
        api_a.secrets_set("bad", {"not": "a string"})
        ck("non-string secret value raises", False)
    except TypeError:
        ck("non-string secret value raises", True)
    try:
        api_a.secrets_get("")
        ck("empty secret key raises", False)
    except ValueError:
        ck("empty secret key raises", True)

    # never leak: not in get_config, not in Options.json
    cfg_dump = json.dumps(api_a.get_config())
    ck("secret absent from get_config",
       "s3cr3t-value" not in cfg_dump, cfg_dump[:200])
    ck("secret absent from Options.json",
       "s3cr3t-value" not in
       (open(cfg, encoding="utf-8").read()
        if os.path.exists(cfg) else ""))
    ck("secrets.json is not inside Options.json dir confusion",
       os.path.dirname(sec_file) == os.path.join(data_base, "ext_a"))

    # persistence across manager instances (same data base)
    m2 = ExtensionManager(FakeReg(), data_dir=data_base)
    m2.load_dir(ext_root)
    api_a2 = m2._ext_apis["ext.a"]
    ck("secrets persist across reload",
       api_a2.secrets_get("api_key") == "s3cr3t-value")
    ck("perms still tight after reload-read",
       os.name != "posix"
       or stat.S_IMODE(os.stat(sec_file).st_mode) & 0o077 == 0)

    # delete
    api_a.secrets_delete("api_key")
    ck("secrets_delete removes the value",
       api_a.secrets_get("api_key") is None
       and api_a.secrets_contains("api_key") is False)
    api_a.secrets_delete("api_key")          # no-op when absent
    ck("secrets_delete absent is a no-op", True)

    # ---- tr() localization ---------------------------------------------
    # Vietnamese active: vi bundle wins for greet; only_en falls to en.
    ck("tr uses the active language bundle",
       api_a.tr("mine.greet", "fb", "World") == "Xin chao World")
    ck("tr falls back to en bundle for missing vi key",
       api_a.tr("mine.only_en") == "English only")
    ck("tr returns fallback for unknown key",
       api_a.tr("mine.nope", "Fallback Text") == "Fallback Text")
    ck("tr returns key when fallback empty and key unknown",
       api_a.tr("mine.nope2") == "mine.nope2")
    ck("tr formats fallback args",
       api_a.tr("mine.nope", "Hi %s", "Bo") == "Hi Bo")
    ck("tr with no bundle returns fallback",
       api_b.tr("mine.greet", "Plain") == "Plain")

    # base-language fallback: zh-CN -> zh bundle (only_en = Chinese only)
    _config.save({"General": {"LocaleFoderName":
                              "Chinese (Simplified)"}})
    ext_i18n.clear_cache()
    ck("tr tries base language before en (zh-CN -> zh)",
       api_a.tr("mine.only_en") == "Chinese only",
       api_a.tr("mine.only_en"))
    ck("zh has no greet -> en bundle still answers",
       api_a.tr("mine.greet", "fb", "W") == "Hello W")

    # a language with no bundle at all -> en terminal candidate
    _config.save({"General": {"LocaleFoderName": "Danish"}})
    ext_i18n.clear_cache()
    ck("tr terminal fallback is en (da -> en)",
       api_a.tr("mine.greet", "fb", "W") == "Hello W")

    # broken config -> en
    _config.save({"General": {"LocaleFoderName": "No Such Language"}})
    ext_i18n.clear_cache()
    ck("unreadable locale setting degrades to en",
       api_a.tr("mine.only_en") == "English only")
finally:
    _config.DEFAULT_PATH = saved_default
    ext_i18n.clear_cache()
    import shutil
    shutil.rmtree(root, ignore_errors=True)

if fails:
    print("FAIL %d/%d" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_ext_secrets_i18n: all checks ok (%d assertions)" % n[0])
