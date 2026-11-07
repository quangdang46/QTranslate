"""Pin the core secrets store + Proxy.Password migration (.tmp
NetworkConfigMappingTest: "the proxy password comes from the secret
store, not the config file").

Offline: everything runs against temp files; no network, no real
Options.json.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import secrets as SEC
from qtranslate import config as C
from qtranslate import session as S


def _tmpdir():
    return tempfile.mkdtemp(prefix="qtsec_")


# --- store basics ---------------------------------------------------------
d = _tmpdir()
sp = os.path.join(d, "secrets.json")
SEC.set("k", "v", path=sp)
ck("set/get round-trip", SEC.get("k", path=sp) == "v")
ck("missing key -> default", SEC.get("nope", "d", path=sp) == "d")
ck("file is owner-only", (os.stat(sp).st_mode & 0o777) == 0o600,
   oct(os.stat(sp).st_mode & 0o777))
SEC.delete("k", path=sp)
ck("delete removes", SEC.get("k", path=sp) is None)
try:
    SEC.set("k", 123, path=sp)
    ck("non-string value rejected", False)
except TypeError:
    ck("non-string value rejected", True)

# --- migrate_options ------------------------------------------------------
cfg = {"Proxy": {"ProxyType": 2, "Host": "h", "Port": 1,
                 "Username": "u", "Password": "s3cret"}}
ck("migration reports change", SEC.migrate_options(cfg, path=sp) is True)
ck("password popped from config", "Password" not in cfg["Proxy"],
   str(cfg["Proxy"]))
ck("password landed under upstream's key",
   SEC.get(SEC.PROXY_PASSWORD_KEY, path=sp) == "s3cret")
ck("empty password still drops the key",
   SEC.migrate_options({"Proxy": {"Password": ""}}, path=sp) is True)
ck("no Proxy section -> no change",
   SEC.migrate_options({}, path=sp) is False)
ck("no Password key -> no change",
   SEC.migrate_options({"Proxy": {"Host": "h"}}, path=sp) is False)

# --- config.load() migration (default path only) ---------------------------
d2 = _tmpdir()
opt = os.path.join(d2, "Options.json")
with open(opt, "w", encoding="utf-8") as f:
    json.dump({"Proxy": {"ProxyType": 2, "Host": "h", "Port": 1,
                         "Username": "u", "Password": "pw1"}}, f)
old = C.DEFAULT_PATH
C.DEFAULT_PATH = opt
try:
    cfg = C.load()
    ck("load returns config without Password",
       "Password" not in cfg.get("Proxy", {}), str(cfg.get("Proxy")))
    on_disk = json.load(open(opt, encoding="utf-8"))
    ck("Options.json scrubbed on disk",
       "Password" not in on_disk.get("Proxy", {}), str(on_disk.get("Proxy")))
    ck("secret stored beside THAT Options.json",
       SEC.get(SEC.PROXY_PASSWORD_KEY,
               path=SEC.path_for(opt)) == "pw1")
    # second load: nothing left to migrate, still clean
    cfg2 = C.load()
    ck("second load stays clean",
       "Password" not in cfg2.get("Proxy", {}))
finally:
    C.DEFAULT_PATH = old

# --- session.net_options uses the store ------------------------------------
d3 = _tmpdir()
opt3 = os.path.join(d3, "Options.json")
SEC.set(SEC.PROXY_PASSWORD_KEY, "s3cret",
        path=SEC.path_for(opt3))
old = C.DEFAULT_PATH
C.DEFAULT_PATH = opt3
_o_load = C.load
C.load = lambda: {"Internet": {},
                  "Proxy": {"ProxyType": 2, "Host": "proxy.local",
                            "Port": 8080, "Username": "alice"}}
try:
    o = S.net_options()
    ck("proxy URL carries the stored password",
       o["proxy"] == "http://alice:s3cret@proxy.local:8080",
       repr(o["proxy"]))
finally:
    C.load = _o_load
    C.DEFAULT_PATH = old

# legacy plaintext fallback still works (pre-migration file shape);
# point DEFAULT_PATH at an empty dir so no real secrets.json leaks in.
d4 = _tmpdir()
old = C.DEFAULT_PATH
C.DEFAULT_PATH = os.path.join(d4, "Options.json")
_o_load = C.load
C.load = lambda: {"Internet": {},
                  "Proxy": {"ProxyType": 2, "Host": "h", "Port": 9,
                            "Username": "u", "Password": "old"}}
try:
    o = S.net_options()
    ck("plaintext fallback for unmigrated configs",
       o["proxy"] == "http://u:old@h:9", repr(o["proxy"]))
finally:
    C.load = _o_load
    C.DEFAULT_PATH = old

# --- DEFAULT_PROXY no longer carries the key -------------------------------
ck("DEFAULT_PROXY has no Password",
   "Password" not in C.DEFAULT_PROXY, str(C.DEFAULT_PROXY))
ck("default_config Proxy has no Password",
   "Password" not in C.default_config().get("Proxy", {}))

if fails:
    print("FAIL %d" % len(fails))
    for f_ in fails:
        print("  -", f_)
    raise SystemExit(1)
print("regress_secrets: all checks ok (%d assertions)" % n[0])
