"""Pin the recovered plugin JS against the URL shapes the port builds.

Read-only. Recovers the plugin JS files from the NSIS solid stream that
ships in docs/review/artifacts/, then asserts the hosts and paths the port
hard-codes are the ones the native JS builds. Exits non-zero on any
mismatch, so this fails loudly if either side moves.

Usage:  python3 -I tools/verify_plugin_js.py
"""

import lzma
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "docs/review/artifacts"
STUB = Path.home() / "Downloads/QTranslate.6.10.0.exe"
STREAM = ART / "nsis_payload_unpacked.bin"
EXE = ART / "QTranslate.6.10.0.exe"

STREAM_LEN = 2263053          # measured; also asserted in the review doc §7
IMAGE_OFF = 0x9bfa9           # where the program begins inside the stream
IMAGE_LEN = 0x165000


def load_stream() -> bytes:
    if STREAM.exists():
        return STREAM.read_bytes()
    raw = STUB.read_bytes()
    props = {"id": lzma.FILTER_LZMA1, "dict_size": 0x800000,
             "lc": 3, "lp": 0, "pb": 2}
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[props])
    out = b""
    while True:
        chunk = dec.decompress(raw[0xF621:], max_length=1 << 22)
        out += chunk
        if len(chunk) < (1 << 22):
            break
    if not dec.eof:
        sys.exit("stream decompressed without reaching EOF")
    if len(out) != STREAM_LEN:
        sys.exit("stream is %d bytes, expected %d" % (len(out), STREAM_LEN))
    return out


def chunk_at(blob: bytes, off: int) -> bytes:
    n = int.from_bytes(blob[off:off + 4], "little")
    body = blob[off + 4:off + 4 + n]
    if len(body) != n:
        raise ValueError("truncated chunk at 0x%x" % off)
    return body


def chunk_before(blob: bytes, end: int) -> bytes:
    """The chunk whose body ends exactly at `end`.

    The stream has no index, so the length field is the only way in: walk
    back far enough to cover any chunk here (the largest is 49 KB) and take
    the candidate whose arithmetic lands on `end` exactly.
    """
    for start in range(end - 4, max(0, end - 0x20000), -1):
        n = int.from_bytes(blob[start:start + 4], "little")
        if 0 < n and start + 4 + n == end:
            return blob[start + 4:end]
    raise ValueError("no length field ends at 0x%x" % end)


def services(blob: bytes) -> dict:
    """Every chunk starting with the serviceHeader hook, keyed by service name."""
    found = {}
    for m in re.finditer(rb"function serviceHeader", blob):
        off = m.start() - 4
        if off < 0:
            continue
        try:
            body = chunk_at(blob, off)
        except ValueError:
            continue
        if not body.startswith(b"function serviceHeader"):
            continue
        name = re.search(rb'new ServiceHeader\(\s*\d+\s*,\s*"([^"]+)"', body)
        found[name.group(1).decode()] = body.decode("utf-8")
    return found


# (port module, marker, Service.js it must also appear in)
HOSTS = [
    ("qtranslate/services/dictionary.py",
     "https://translation.babylon-software.com", "Babylon"),
    ("qtranslate/services/dictionary.py",
     "https://dictionary.babylon-software.com", "Babylon Dictionary"),
    ("qtranslate/services/dictionary.py",
     "https://www.lingvolive.com", "ABBYY Lingvo Live"),
    ("qtranslate/services/dictionary.py",
     "http://dictionary.reverso.net", "Reverso"),
    ("qtranslate/services/google_translate.py",
     "https://translate.google.", "Google"),
    ("qtranslate/services/microsoft.py", "www.bing.com", "Microsoft"),
    ("qtranslate/services/deepl.py", "www2.deepl.com", "DeepL"),
    ("qtranslate/services/baidu.py", "fanyi.baidu.com", "Baidu"),
    ("qtranslate/services/yandex.py", "translate.yandex.net", "Yandex"),
    ("qtranslate/services/naver.py", "papago.naver.com", "Papago"),
    ("qtranslate/services/promt.py", "online-translator.com", "Promt"),
]

# Path literals that must be byte-identical on both sides.
PATHS = [
    ("qtranslate/services/dictionary.py",
     "/translate/babylon.php?v=1.0&q={0}", "Babylon"),
    ("qtranslate/services/dictionary.py", "/ajax.php/", "Babylon Dictionary"),
    ("qtranslate/services/dictionary.py",
     "/{0}/translate/{1}-{2}/{3}", "ABBYY Lingvo Live"),
    ("qtranslate/services/google_translate.py",
     "/translate_a/single?client=gtx&sl={0}&tl={1}&hl={2}", "Google"),
    ("qtranslate/services/microsoft.py", "/ttranslatev3?isVertical=1&IG=", "Microsoft"),
    ("qtranslate/services/yandex.py", "/api/v1/tr.json/translate", "Yandex"),
    ("qtranslate/services/youdao.py", "/translate_o?smartresult=dict", "youdao"),
]

HISTORY = [
    ("csv", "return[escapeValue(a),escapeValue(c),escapeValue(b),"
            "escapeValue(e),escapeValue(d)].join()"),
    ("html", 'function quoteHtml(a){return a?a.replace(/&/g,"&amp;")'),
    ("json", 'var escMap={\'"\':\'\\\\"\',"\\\\":"\\\\\\\\"'),
    ("txt", 'function historyItemEnd(a,b){return"======='),
]


def main() -> int:
    blob = load_stream()
    if EXE.exists():
        embedded = chunk_at(blob, IMAGE_OFF - 4)
        if embedded != EXE.read_bytes():
            sys.exit("embedded image differs from the committed extracted exe")

    svc = services(blob)
    needed = {s for _, _, s in HOSTS} | {s for _, _, s in PATHS}
    absent = sorted(needed - set(svc))
    if absent:
        sys.exit("no recovered Service.js for: %s" % ", ".join(absent))

    cache = {m: (ROOT / m).read_text(encoding="utf-8") for m in
             {m for m, _, _ in HOSTS} | {m for m, _, _ in PATHS}}

    def slots(s: str) -> str:
        """Collapse a format placeholder to a bare slot.

        JS numbers them {0},{1}; Python's str.format writes {} and lets the
        order carry the position. Without this, a two-slot path compares as
        equal only by accident of numbering.
        """
        return re.sub(r"\{(\d+)?\}", "{}", s)

    fails = []
    for kind, table in (("host", HOSTS), ("path", PATHS)):
        for mod, needle, svc_name in table:
            # JS numbers its placeholders {0},{1}; Python's str.format writes {}
            # and lets argument order carry the position. Normalise both sides
            # or a two-slot path reports unequal purely from the numbering.
            want = slots(needle)
            in_port = want in slots(cache[mod])
            in_js = want in slots(svc[svc_name])
            if not (in_port and in_js):
                fails.append("%s %s: %r port=%s native=%s"
                             % (kind, mod, needle, in_port, in_js))

    for fname, marker in HISTORY:
        tail = b'historyFileExtension(){return"%s"};\n' % fname.encode()
        end = blob.find(tail)
        if end < 0:
            fails.append("history %s.js: terminator literal not found" % fname)
            continue
        try:
            body = chunk_before(blob, end + len(tail))
        except ValueError as e:
            fails.append("history %s.js: %s" % (fname, e))
            continue
        text = body.decode("utf-8")
        if marker not in text:
            fails.append("history %s.js: marker drifted" % fname)
        if ('historyFileExtension(){return"%s"}' % fname) not in text:
            fails.append("history %s.js: chunk on the other side of the marker" % fname)

    print("recovered %d Service.js (%d bytes), %d History exporters"
          % (len(svc), sum(len(v) for v in svc.values()), len(HISTORY)))
    print("checks: %d, failures: %d" % (len(HOSTS) + len(PATHS) + len(HISTORY), len(fails)))
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
