"""Reversed from QTranslate 6.10.0 - Services/Google Translate/Service.js + Common.js.
Implements the same request pipeline: tk() token -> /translate_a/single?client=gtx.
"""
import json
import sys
import urllib.parse
import urllib.request

HOST = "https://translate.google.com"
MAX_URI_LEN = 1800


def _b(a: int, b: str) -> int:
    for d in range(0, len(b) - 2, 3):
        c = b[d + 2]
        c = (ord(c) - 87) if "a" <= c else int(c)
        c = (a >> c) if b[d + 1] == "+" else (a << c) & 0xFFFFFFFF
        a = (a + c) & 0xFFFFFFFF if b[d] == "+" else a ^ c
    return a


def tk(text: str, tkk: str = "0.0") -> str:
    """Port of tk(a) in Service.js. tkk = Options.GoogleTkk (seed from page)."""
    parts = tkk.split(".")
    h = int(parts[0]) if parts[0] else 0
    g = []
    e = 0
    while e < len(text):
        f = ord(text[e])
        if f < 128:
            g.append(f)
        elif f < 2048:
            g.append((f >> 6) | 192)
        else:
            if 55296 == (f & 64512) and e + 1 < len(text) and 56320 == (ord(text[e + 1]) & 64512):
                f = 65536 + ((f & 1023) << 10) + (ord(text[e + 1]) & 1023)
                e += 1
                g.append((f >> 18) | 240)
                g.append(((f >> 12) & 63) | 128)
            else:
                g.append((f >> 12) | 224)
            g.append(((f >> 6) & 63) | 128)
        g.append((f & 63) | 128)
        e += 1
    a = h
    for d in g:
        a += d
        a = _b(a, "+-a^+6")
    a = _b(a, "+-3^+b+-f")
    a ^= int(parts[1]) if len(parts) > 1 and parts[1] else 0
    if a < 0:
        a = (a & 2147483647) + 2147483648
    a %= 1_000_000
    return f"{a}.{a ^ h}"


def translate(text: str, sl: str = "auto", tl: str = "en", tkk: str = "0.0") -> str:
    """Port of serviceTranslateRequest + serviceTranslateResponse."""
    token = tk(text, tkk)
    q = urllib.parse.quote(text)
    get = len(q) <= MAX_URI_LEN
    path = ("/translate_a/single?client=gtx&sl={}&tl={}&hl=en&dt=t&dt=ld"
            "&ie=UTF-8&oe=UTF-8&tk={}").format(sl, tl, token)
    if get:
        path += "&q=" + q
        data = None
    else:
        data = ("q=" + q).encode()
    req = urllib.request.Request(
        HOST + path, data=data,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                 "Accept": "*/*", "Accept-Language": "en-US;q=0.8,en;q=0.6"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    out = ""
    if resp and resp[0]:
        for seg in resp[0]:
            if seg and len(seg):
                out += seg[0] or ""
    return out


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello world"
    tl = sys.argv[2] if len(sys.argv) > 2 else "vi"
    print("tk:", tk(text))
    print("translation:", translate(text, "auto", tl))
