"""Regression: General.EnableHistory gates push_hist (was unconditional)."""
import sys
import json
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

import qtranslate.config as C  # noqa: E402

fail = []


def ck(n, c, d=""):
    if not c:
        fail.append(n + (" -- " + d if d else ""))


# Point DEFAULT_PATH at a throwaway file so we never touch the real config.
fd, path = tempfile.mkstemp(suffix=".json")
os.close(fd)
orig_load = C.load

try:
    import qtranslate.app as app

    class _Stub:
        def __init__(self):
            self.history = []
            self._hist_pos = -1
        push_hist = app.App.push_hist

    def _load_from(path_arg=None):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    C.load = _load_from

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"General": {"EnableHistory": False}}, f)
    s = _Stub()
    s.push_hist("google", "hello", "xin chao")
    ck("EnableHistory=False blocks recording", s.history == [], str(s.history))

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"General": {"EnableHistory": True}}, f)
    s2 = _Stub()
    s2.push_hist("google", "hello", "xin chao")
    ck("EnableHistory=True records", len(s2.history) == 1, str(s2.history))
finally:
    C.load = orig_load
    os.remove(path)

if fail:
    raise SystemExit("FAIL:\n  " + "\n  ".join(fail))
print("OK: EnableHistory gates push_hist")
