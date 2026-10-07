"""Scrape ephemeral session tokens the native QTranslate.exe obtains by
loading each provider's web page through its embedded Chakra/JS engine
before calling serviceTranslateRequest (see docs/NATIVE_ARCH.md, UtilsDispatch).
This module reproduces that bootstrap step with plain urllib + regex so the
Python ports of Microsoft/Promt/Baidu/Youdao can run standalone.
"""
import re
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def bing_session() -> dict:
    """Scrape IG + token + key + MUID cookie for Microsoft Translator.

    ttranslatev3 returns HTTP 401 without the MUID/_EDGE_* cookies Bing sets
    on the translator page response (verified live 2026-10-07) — anonymous
    (no-cookie) calls are rejected, unlike the gtx-era behaviour.
    """
    req = urllib.request.Request("https://www.bing.com/translator", headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
        set_cookie = r.headers.get_all("Set-Cookie") or []
    cookie = "; ".join(c.split(";")[0] for c in set_cookie)
    ig = re.search(r'IG:"(\w+)"', html)
    abuse = re.search(
        r'params_AbusePreventionHelper\s*=\s*\[(\d+),"([^"]+)",(\d+)', html)
    iid = re.search(r'data-iid="(translator\.\d+\.\d+)"', html)
    if not ig or not abuse:
        raise RuntimeError("Could not scrape Bing session (page layout changed?)")
    return {
        "IG": ig.group(1),
        "key": abuse.group(1),
        "token": abuse.group(2),
        "cookie": cookie,
        "iid": iid.group(1) if iid else "translator.5023.3",
    }


def promt_session() -> dict:
    """Scrape XSRF-TOKEN cookie + PromtPaft for online-translator.com."""
    req = urllib.request.Request(
        "https://www.online-translator.com", headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
        set_cookie = r.headers.get_all("Set-Cookie") or []
    xsrf = next((c.split(";")[0].split("=", 1)[1]
                 for c in set_cookie if c.startswith("XSRF-TOKEN=")), "")
    cookie = "; ".join(c.split(";")[0] for c in set_cookie)
    paft = re.search(r'name="aft"\s+value="([^"]+)"', html)
    return {"xsrf": xsrf, "cookie": cookie, "paft": paft.group(1) if paft else ""}


if __name__ == "__main__":
    import json
    print("bing:", json.dumps(bing_session()))
    try:
        print("promt:", json.dumps(promt_session()))
    except Exception as e:
        print("promt: ERROR", e)
