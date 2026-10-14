"""Regression: Yandex.Disk public-key href resolver (FUN_0046185d).

Native formats
  https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=%s&fields=href
fetches it, and returns the ``href`` member of the JSON root -- "" when
the fetch fails, the JSON is not a dict, or there is no href. Pinned
headless with stub openers; no network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import yandex as Y  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


class _Resp:
    headers = {}

    def __init__(self, payload):
        self._b = payload.encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


seen = {}


class _Opener:
    def __init__(self, payload):
        self.payload = payload

    def open(self, req, timeout=None):
        seen["url"] = req.full_url
        return _Resp(self.payload)


ck("formatter matches native's template",
   Y.DISK_PUBLIC_URL % "K" == ("https://cloud-api.yandex.net/v1/disk/"
                               "public/resources/download"
                               "?public_key=K&fields=href"))
ck("returns href on success",
   Y.resolve_public_href("K", _Opener('{"href": "https://dl/h", "x":1}'))
   == "https://dl/h")
ck("requested url carries the key + fields=href",
   "public_key=K" in seen["url"] and "fields=href" in seen["url"],
   repr(seen.get("url")))
ck("empty key short-circuits without a fetch",
   Y.resolve_public_href("", _Opener('{"href": "x"}')) == "")
ck("missing href returns ''",
   Y.resolve_public_href("K", _Opener('{"nope": 1}')) == "")
ck("non-dict json returns ''",
   Y.resolve_public_href("K", _Opener('[1,2]')) == "")
ck("garbage body returns ''",
   Y.resolve_public_href("K", _Opener('not json{{')) == "")


class _Boom:
    def open(self, req, timeout=None):
        raise OSError("offline")


ck("transport failure returns ''",
   Y.resolve_public_href("K", _Boom()) == "")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_yandex_disk: all checks ok (%d assertions)" % n[0])
