"""Port of C:/Program Files (x86)/QTranslate/Services/Naver/Service.js (SERVICE_ID=30).

Papago N2MT/SMT API. Auth: HmacMD5(deviceId + "\\n" + url + "\\n" + timestamp,
key "v1.6.5_956d74858f"), header "PPG deviceId:base64(hmac)", Timestamp header.
Endpoints: POST /apis/n2mt/translate or /apis/nsmt/translate, POST
/apis/langs/dect for detection. pt/hi fall back to en.
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import uuid

SERVICE_ID = 30
SERVICE_NAME = "Papago"
HOST = "https://papago.naver.com"
_AUTH_KEY = "v1.6.5_956d74858f"

SUPPORTED_LANGS = [-1, "auto", -1, -1, -1, -1, -1, -1, -1, -1, -1, "zh-CN",
                   "zh-TW", -1, -1, -1, -1, "en", -1, -1, -1, "fr", -1, "de",
                   -1, -1, -1, "hi", -1, -1, "id", "it", -1, "ja", -1, "ko",
                   -1, -1, -1, -1, -1, -1, -1, -1, "pt", -1, "ru", -1, -1, -1,
                   "es", -1, -1, "th", -1, -1, -1, "vi", -1, -1, -1, -1, -1,
                   -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]

_N2MT_PAIRS = {"enhi", "enpt", "hien", "pten"}


def _auth(url: str):
    ts = str(int(time.time() * 1000) - 19555)
    dev = str(uuid.uuid4())
    sig = hmac.new(_AUTH_KEY.encode(), f"{dev}\n{url}\n{ts}".encode(),
                   hashlib.md5).digest()
    header = (f"Authorization:PPG {dev}:{base64.b64encode(sig).decode()}\r\n"
              f"Timestamp:{ts}")
    return header, dev


def _post(path: str, body: str, extra_headers: str = "") -> dict:
    url = HOST + path
    _, dev = _auth(url)  # deviceId also goes in body for translate
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*",
                 "Accept-Language": "en-US;q=0.8",
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    # auth headers are per-request; rebuild for this exact url
    header, _ = _auth(url)
    for line in (header + "\r\n" + extra_headers).split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            req.add_header(k.strip(), v.strip())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def detect(text: str) -> str:
    body = "query=" + urllib.parse.quote(text[:5000])
    resp = _post("/apis/langs/dect", body)
    return resp.get("langCode", "")


def translate(text: str, sl: str = "auto", tl: str = "en") -> tuple:
    if sl in ("pt", "hi"):
        sl = "en"
    if tl in ("pt", "hi"):
        tl = "en"
    mode = "nsmt" if (sl + tl) in _N2MT_PAIRS else "n2mt"
    # note: original uses n2mt unless pair in enhi|enpt|hien|pten list
    mode = "n2mt" if (sl + tl) not in _N2MT_PAIRS else "nsmt"
    url = HOST + f"/apis/{mode}/translate"
    header, dev = _auth(url)
    body = ("deviceId={}&source={}&target={}&text={}".format(
        dev, sl, tl, urllib.parse.quote(text[:5000])))
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"User-Agent": "Mozilla/5.0",
                 "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    for line in header.split("\r\n"):
        k, v = line.split(":", 1)
        req.add_header(k.strip(), v.strip())
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("translatedText", ""), resp.get("srcLangType", sl)
