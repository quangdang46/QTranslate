"""Regression: the recovered Service.js sources, and the port against them.

Why this suite exists
--------------------
`Service.js` content is absent from `QTranslate.6.10.0.exe`. That is true, and
three separate checks built on it reached the false conclusion that the
dictionary rows could not be re-verified from this repo -- because all three
searched only the exe. The sources are in
`docs/review/artifacts/nsis_payload_unpacked.bin`, the NSIS solid stream
`ARTIFACT_RECOVERY_2026-10-10.md` 2 already recovered and 6 already listed.

A filename present in the image with no path prefix means the file is loaded at
runtime from somewhere; it is a pointer to where the file lives, not evidence
that it is gone. This suite pins the extraction so the blind spot cannot recur
silently: it walks the stream, asserts the counts, and asserts a set of
serviceHost values against the port.

Docs: docs/review/PLUGIN_JS_RECOVERED_2026-10-11.md (recovery),
     docs/review/PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md (this check).
     docs/review/REA_AS_INTERFACE_2026-10-11.md records the retraction.
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
EXE = os.path.join(ROOT, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")
DICT = os.path.join(ROOT, "qtranslate", "services", "dictionary.py")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


def extract_services(blob: bytes) -> list:
    """Every length-prefixed `Service.js` body in the NSIS stream.

    The framing is `<uint32-LE length><body>` with the length field
    IMMEDIATELY before the body. A constant back-offset is wrong: the offset
    varies, and guessing it silently computes hashes over the wrong bytes.
    """
    out = []
    i = blob.find(b"function serviceHeader")
    while i != -1:
        ln = int.from_bytes(blob[i - 4:i], "little")
        if 0 < ln < 100000 and blob[i:i + 20].startswith(b"function"):
            body = blob[i:i + ln]
            m = re.search(rb'new ServiceHeader\((\d+),"([^"]+)"', body[:200])
            if m:
                out.append((int(m.group(1)), m.group(2).decode("utf-8"),
                            ln, hashlib.sha256(body).hexdigest(), body))
        i = blob.find(b"function serviceHeader", i + 1)
    return out


if not os.path.exists(PAYLOAD):
    ck("NSIS payload present (run from the repo root)", False, PAYLOAD)
else:
    blob = open(PAYLOAD, "rb").read()
    svc = extract_services(blob)

    # --- the extraction itself -------------------------------------------------
    ck("all 19 Service.js files are recovered", len(svc) == 19,
       "got %d" % len(svc))
    ck("the sources total 49,889 bytes",
       sum(s[2] for s in svc) == 49889, "got %d" % sum(s[2] for s in svc))
    # ids are the checklist's row ids; each file declares its own
    ids = [s[0] for s in svc]
    ck("every file declares a unique service id", len(set(ids)) == 19)
    # every body is a real JS file, not a fragment
    ck("every body starts as a JS function",
       all(s[4].startswith(b"function serviceHeader") for s in svc))
    ck("every body ends inside JS (no truncation)",
       all(s[4].rstrip().endswith((b"}", b";", b"]", b")")) or len(s[4]) < 600
           for s in svc))

    # --- the exe lives in the SAME stream, so this is one artifact -----------
    exe = open(EXE, "rb").read()
    ck("the committed exe is a chunk of this same stream", exe in blob,
       "the two artifacts are not the same recovery")
    ck("exe digest pins the artifact",
       hashlib.sha256(exe).hexdigest().startswith("f35a3bc8e09e"),
       hashlib.sha256(exe).hexdigest()[:16])

    # --- every serviceHost the rows cite is in the port ----------------------
    # Dictionary providers live in dictionary.py; DeepL / Papago / Promt are
    # TRANSLATE providers and live in their own modules -- checking only
    # dictionary.py would report them missing and that would be a false gap.
    sources = {s[1]: s[4].decode("utf-8", errors="replace") for s in svc}
    port = open(DICT, encoding="utf-8").read()
    # Kept per module, not concatenated: an operative host is a CONSTANT
    # ASSIGNMENT (`OXFORD_HOST = "https://..."`), and the module it lives in is
    # part of the claim. Concatenating would let any host satisfy any row.
    MODULES = {"dictionary": port}
    for mod in ("deepl", "naver", "promt"):
        p = os.path.join(ROOT, "qtranslate", "services", mod + ".py")
        if os.path.exists(p):
            MODULES[mod] = open(p, encoding="utf-8", errors="replace").read()
    MODULES["session"] = open(os.path.join(ROOT, "qtranslate", "session.py"),
                              encoding="utf-8", errors="replace").read()

    HOSTS = {
        "ABBYY Lingvo Live": "lingvolive.com",
        "Babylon": "translation.babylon-software.com",
        "Babylon Dictionary": "dictionary.babylon-software.com",
        "DeepL": "www2.deepl.com",
        "Google Search": "www.google.com",
        "ImTranslator": "imtranslator.net",
        "Multitran": "www.multitran.com",
        "Oxford Learner Dictionary": "oxfordlearnersdictionaries.com",
        "Papago": "papago.naver.com",
        "Promt": "online-translator.com",
        "Reverso": "dictionary.reverso.net",
        "Urban Dictionary": "urbandictionary.com",
        "WordReference": "www.wordreference.com",
    }
    # `NAME = "https://...host"` at line start. A bare substring test is NOT
    # enough and was measured to be too weak: the host appears inside
    # oxford_lookup's docstring and inside a link-rewriting regex, so changing
    # the one operative `OXFORD_HOST` constant still passed the substring check.
    # A fact about a string in a file is not a fact about the string the code
    # runs on.
    def _operative_host(hay: str, host: str):
        return re.search(r'^[A-Za-z_]\w*\s*=\s*["\']https?://(?:www\.)?'
                         + re.escape(host) + r'(?:[/"\'])', hay, re.M)

    for name, host in sorted(HOSTS.items()):
        src = sources.get(name, "")
        ck(f"{name}: host is in the recovered source",
           host in src, "host not found in %s.js" % name)
        where = [m for m, txt in MODULES.items() if _operative_host(txt, host)]
        ck(f"{name}: the port assigns an operative host constant",
           bool(where),
           "no module assigns NAME = \"https://...%s\"; host found only in prose "
           "or a regex" % host)

    # and each of those constants is actually USED, not shipped dead
    for name, host in sorted(HOSTS.items()):
        for mod, txt in MODULES.items():
            m = _operative_host(txt, host)
            if not m:
                continue
            const = m.group(0).split("=")[0].strip()
            without_def = re.sub(r'^\s*' + re.escape(const) + r'\s*=.*$',
                                 "", txt, flags=re.M)
            ck(f"{name}: {const} is referenced outside its own definition",
               re.search(r'\b' + re.escape(const) + r'\b', without_def)
               is not None,
               "%s is assigned but never used -- the host would be dead code"
               % const)

    # --- the ones that are NOT in dictionary.py, and why ---------------------
    for name, mod in (("DeepL", "deepl.py"), ("Papago", "naver.py"),
                      ("Promt", "promt.py")):
        ck(f"{name} is a translate provider, not a dictionary one",
           name in sources and os.path.exists(
               os.path.join(ROOT, "qtranslate", "services", mod)),
           "%s must live in %s" % (name, mod))

    # --- two line-for-line reads, pinned so a port edit cannot drift silently
    wr = sources.get("WordReference", "")
    ck("WordReference: the port's slice markers are native's",
       '<div id="(articleWRD|article)">' in wr
       and 'postArticle' in wr
       and re.search(r'_sub\(page,\s*re\.compile\(r\'<div id="\(articleWRD\|'
                     r'article\)">\'\)', port) is not None,
       "either the JS markers moved or the port drifted")
    ck("WordReference: buildUri is host + /{sl}{tl}/{q}",
       'format("/{0}{1}/{2}"' in wr and "wordreference_build_uri" in port)

    ox = sources.get("Oxford Learner Dictionary", "")
    # Asserted against the OPERATIVE regex, not the file text: the markers also
    # appear in oxford_lookup's docstring, so a plain `in port` passes while the
    # executed slice has drifted. That is exactly the mutant that survived the
    # first version of this check.
    ox_re = re.search(r'_sub\(page,\s*[\'"](<div id="ox-wrapper)[\'"]', port)
    rc_re = re.search(r'_sub\(\s*page,[^)]*?[\'"](<div id="rightcolumn)[\'"]',
                      port, re.S)
    ck("Oxford: the port's operative slice markers are native's",
       ox_re is not None and rc_re is not None,
       "the executed _sub() no longer slices on the native markers "
       "(start=%r, end=%r)" % (ox_re.groups() if ox_re else None,
                              rc_re.groups() if rc_re else None))
    ck("Oxford: the port slices on the START marker before the END one",
       ox_re is not None and rc_re is not None
       and port.find(ox_re.group(1)) < port.find(rc_re.group(1)),
       "native's stringFindSub(start, end) order must be preserved")
    ck("Oxford: the qtdp: rewrite is native's",
       'qtdp:' in ox and 'qtdp:' in port)

    # Reverso's attribute list is the other easy drift: native passes a
    # space-split list of SEVEN attributes,
    # `removeAttributes(a,"id name class href onclick onmouseover onmouseout"
    # .split(" "))`. All SEVEN must be pinned, not merely the leading five --
    # the first version of this check matched only up to "onclick", and a mutant
    # that dropped `onmouseout` alone survived it. Five-of-seven present is not
    # a test of "native's seven".
    rv = sources.get("Reverso", "")
    ck("Reverso: the port's attribute list is native's seven",
       'removeAttributes(a,"id name class href onclick onmouseover '
       'onmouseout".split(" "))' in rv
       and re.search(r'_remove_attributes\(\s*frag,\s*\[\s*"id"\s*,'
                     r'\s*"name"\s*,\s*"class"\s*,\s*"href"\s*,\s*"onclick"'
                     r'\s*,\s*"onmouseover"\s*,\s*"onmouseout"\s*\]', port)
       is not None,
       "either the JS attribute list moved or the port drifted")


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_plugin_js_recovered: all checks ok (%d assertions%s)"
      % (n[0], ", payload used" if os.path.exists(PAYLOAD) else ", NO PAYLOAD"))
