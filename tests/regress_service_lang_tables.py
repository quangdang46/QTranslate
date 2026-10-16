"""Regression: every ``SupportedLanguages`` matches the recovered Service.js.

The NSIS payload carries 19 complete ``Service.js`` sources with hashes
(`docs/review/PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md`), and each
one declares its own ``SupportedLanguages`` array. These arrays decide the
language code sent to that provider, so an off-by-one silently routes the
wrong language.

Two real bugs this caught (fixed 2026-10-16):
  * Promt -- the table was 75 entries, two short of native's 76, so index
    74 resolved to ``"tt"`` where native returns ``-1`` and index 75
    (native's ``"tt"``) resolved to ``-1``;
  * DeepL -- carrying two extra trailing ``-1`` (78 vs 76).

Only the 10 services whose Python module exposes a table are compared
here; the remaining 9 are dictionary providers with tables verified in
`docs/review/PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md` §3
(entry-by-entry for Lingvo).

Native writes ``-1`` for "unsupported"; the port's tables may spell that
either ``-1`` or ``None`` -- both mean the same thing to
``code_from_language``, so the comparison normalises them rather than
failing on a representation choice.

Headless: the JS is read straight from the artifact, never executed.

youdao (id 26) was added 2026-10-16 when checking that every
DICTIONARY-capable service is reachable: it is the only
TRANSLATE|DICTIONARY service, and its table carried **77** entries where
native has **76** — one extra trailing unsupported. The length mattered
even though every present entry matched: `is_language(76)` answered True
in the port and false in native, so a language index one past the end was
accepted. Byte-equal now.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import (baidu, deepl, dictionary, microsoft,  # noqa: E402
                                  naver, promt, yandex)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


PAYLOAD = os.path.join(ROOT := os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "review", "artifacts",
    "nsis_payload_unpacked.bin")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

_ts = open(PAYLOAD, "rb").read().decode("utf-8", "replace")


def native_table(service_id):
    """The ``SupportedLanguages`` array from that service's own JS."""
    import re
    i = _ts.find("new ServiceHeader(%d," % service_id)
    assert i >= 0, "no ServiceHeader(%d)" % service_id
    m = re.search(r"SupportedLanguages=\[(.*?)\];", _ts[i:i + 12000],
                  re.S)
    assert m, "no SupportedLanguages after ServiceHeader(%d)" % service_id
    return eval("[" + m.group(1) + "]")


def norm(table):
    return [None if v == -1 else v for v in table]


# service id -> (label, the port's table)
TABLES = [
    (1, "Google", __import__(
        "qtranslate.services.google_translate",
        fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS),
    (5, "Microsoft", microsoft.SUPPORTED_LANGS),
    (11, "Yandex", yandex.SUPPORTED_LANGS),
    (12, "Promt", promt.SUPPORTED_LANGS),
    (13, "Babylon", __import__(
        "qtranslate.services.babylon", fromlist=["SUPPORTED_LANGS"]
    ).SUPPORTED_LANGS),
    (20, "Babylon Dictionary", dictionary.BABYLON_DICT_LANGS),
    (22, "Reverso", dictionary.REVERSO_LANGS),
    (28, "Baidu", baidu.SUPPORTED_LANGS),
    (30, "Papago", naver.SUPPORTED_LANGS),
    (31, "DeepL", deepl.SUPPORTED_LANGS),
    (26, "youdao", __import__(
        "qtranslate.services.youdao", fromlist=["SUPPORTED_LANGS"]
    ).SUPPORTED_LANGS),
]

for sid, label, port in TABLES:
    nat = native_table(sid)
    ck("%s: 76 entries (native count)" % label, len(nat) == 76,
       str(len(nat)))
    ck("%s: port has the same length" % label, len(port) == len(nat),
       "port=%d native=%d" % (len(port), len(nat)))
    diff = [(i, a, b) for i, (a, b)
            in enumerate(zip(norm(nat), norm(port))) if a != b]
    ck("%s: every entry matches" % label, not diff,
       "idx %d native=%r port=%r" % diff[0] if diff else "")

# the two fixed bugs, pinned so they cannot come back
_promt = native_table(12)
ck("Promt index 74 is unsupported natively (the port had 'tt' there)",
   _promt[74] == -1, repr(_promt[74]))
ck("Promt index 75 is 'tt' (the port had -1 there)",
   _promt[75] == "tt", repr(_promt[75]))
ck("Promt's last two entries are the shift that was wrong",
   norm(promt.SUPPORTED_LANGS)[74:] == norm(_promt)[74:],
   "%r vs %r" % (promt.SUPPORTED_LANGS[74:], _promt[74:]))

_deepl = native_table(31)
ck("DeepL is exactly 76 (the port carried 78)",
   len(deepl.SUPPORTED_LANGS) == len(_deepl) == 76)
ck("DeepL's tail is native's tail",
   norm(deepl.SUPPORTED_LANGS)[70:] == norm(_deepl)[70:])

# a spot check that the codes really are that provider's own
# (WordReference uses cz/gr; Promt's Chinese codes are lowercase)
ck("Promt uses its own lowercase 'zhcn'", promt.SUPPORTED_LANGS[11]
   == "zhcn", repr(promt.SUPPORTED_LANGS[11]))
ck("DeepL uses uppercase ISO codes", deepl.SUPPORTED_LANGS[9] == "BG",
   repr(deepl.SUPPORTED_LANGS[9]))
_wr = dictionary.WORDREF_LANGS
ck("WordReference keeps its non-ISO codes (cz for Czech, gr for Greek)",
   "cz" in _wr and "gr" in _wr, repr([v for v in _wr
                                      if v in ("cz", "gr")]))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_service_lang_tables: all checks ok (%d assertions)" % n[0])
