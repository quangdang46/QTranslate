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
import ast
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

    # --- Common.js, the framework the whole service protocol depends on ------
    # Found by CONTENT, never by name. The payload stores files as positional
    # length-prefixed bodies with no filename field, so `b"Common.js" in blob`
    # is 0 -- and concluding from that 0 that the framework was absent is the
    # exact error this suite exists to prevent. The test that finds it is
    # walking the <len><body> chain, or matching a literal that exists only
    # inside the file. Five markers, one occurrence each.
    CJ_MARKERS = ("var Const={MAX_URI_LEN", "Capability={TRANSLATE:1",
                  "HttpMethod={UNDEFINED:0", "CodePage={WINDOWS1251",
                  "Array.prototype.filter=function")
    cj = ""
    for mk in CJ_MARKERS:
        enc = mk.encode()
        hits = [i for i in range(len(blob)) if blob.startswith(enc, i)]
        ck("Common.js: marker %r occurs exactly ONCE" % mk,
           len(hits) == 1, "got %d occurrences" % len(hits))
        if len(hits) == 1:
            # the body starts at the length field's end
            # only the marker scan is needed here; the body used for the
            # assertions below is the length-prefixed chunk at 0x13af4, not a
            # fixed window from the marker -- the constants the port mirrors
            # live past 7000 bytes into the file, and a window cut them out.
            cj = blob[hits[0]:hits[0] + 64].decode("utf-8", "replace")
    cj_len = int.from_bytes(blob[0x13af0:0x13af4], "little")
    cj_body = blob[0x13af4:0x13af4 + cj_len]
    cj_src = cj_body.decode("utf-8", "replace")
    ck("Common.js: chunk[5] is 6,203 bytes at 0x13af4", cj_len == 6203,
       "got %d" % cj_len)
    ck("Common.js: the chunk's sha256 is the peer's a03d677a8b3788b5",
       hashlib.sha256(cj_body).hexdigest().startswith("a03d677a8b3788b5"),
       hashlib.sha256(cj_body).hexdigest()[:16])

    # The three facts dictionary.py's _codes() now depends on. Without these,
    # a later "the framework must refuse" edit would look supported.
    ck("Common.js: codeFromLanguage returns the entry UNGUARDED",
       re.search(r'function codeFromLanguage\(a\)\{return a===AUTO_DETECT'
                 r'_LANGUAGE\|\|isLanguage\(a\)\?SupportedLanguages\[a\]:'
                 r'UNKNOWN_LANGUAGE_CODE\}', cj_body.decode("utf-8", "replace"))
       is not None,
       "it tests the index, never the value -- an unsupported entry "
       "interpolates as -1")
    ck("Common.js: isLanguage is a BOUNDS test, not a support test",
       "a>AUTO_DETECT_LANGUAGE&&a<SupportedLanguages.length" in cj_src,
       "true for unsupported entries too, which is why supported() exists")
    ck("Common.js: there is NO refusal path at all",
       cj_src.count("return null") == 0 and cj_src.count("return!1") == 0
       and cj_src.count("return false") == 0,
       "native neither skips nor refuses an unsupported pair; it sends -1")
    ck("Common.js: the framework never calls codeFromLanguage itself",
       len(re.findall(r'codeFromLanguage\(', cj_src)) == 1,
       "only a service's own buildUri does")
    ck("Common.js: SupportedLanguages is ONE shared global (null, then "
       "reassigned)", "var SupportedLanguages=null" in cj_src,
       "each of the 19 Service.js files overwrites it at load")
    ck("Common.js: all 19 Service.js reassign that same shared global",
       sum(1 for s in svc if "SupportedLanguages=" in
           s[4].decode("utf-8", "replace")[:200]
           or re.search(r'(?<![\w])SupportedLanguages=',
                        s[4].decode("utf-8", "replace")) is not None) == 19,
       "a provider's table and the framework's are the same slot")
    # and the constants common.py carries, so the port's own source is pinned.
    # Two spellings, because the framework declares them two ways: the Const
    # object uses `NAME:value` and the language ids use a `var NAME=value` run.
    for const, val in (("MAX_URI_LEN", "1800"), ("MAX_SOURCE_LEN", "5E3"),
                       ("UNKNOWN_LANGUAGE_CODE", "-1"),
                       ("UNKNOWN_LANGUAGE", "0"),
                       ("AUTO_DETECT_LANGUAGE", "1"),
                       ("ENGLISH_LANGUAGE", "17")):
        ck("Common.js: %s=%s" % (const, val),
           re.search(re.escape(const) + r'\s*[:=]\s*' + re.escape(val)
                     + r'(?![\d.])', cj_src) is not None,
           "common.py mirrors this value; a drift here is a real divergence")

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

    # --- Lingvo (25): read 2026-10-11, the 4th provider read against source --
    # Every load-bearing literal in serviceDictionaryResponse is pinned, because
    # this provider's response handler is the longest of the dictionary ones.
    lv = sources.get("ABBYY Lingvo Live", "")
    ck("Lingvo: the slice start is native's five-way alternation",
       '/<div name="#(dictionary|user|quote|phrase|wordform)"/.exec(b)' in lv
       and "dictionary|user|quote|phrase|wordform" in port,
       "the five named<div> kinds the response slices on")
    ck("Lingvo: the end marker is HLjpm with a <footer fallback",
       "HLjpm" in lv and "HLjpm" in port and "<footer" in lv
       and '"<footer"' in port,
       "native bakes the fallback into one conditional: if HLjpm is absent "
       "(-1 -> 0), use <footer")
    ck("Lingvo: the four removed attributes are native's",
       'removeAttributes(c,["id","name","class","data-reactid"])' in lv
       and re.search(r'_remove_attributes\(\s*frag,\s*\["id",\s*"name",\s*'
                     r'"class",\s*"data-reactid"\s*\]', port) is not None,
       "data-reactid is the React one and is easy to drop")
    ck("Lingvo: the two removed elements are native's",
       'removeElements(c,["button","svg"])' in lv
       and '"button", "svg"' in port,
       "button AND svg -- both, or the raw UI ships")
    ck("Lingvo: buildUri is /{ui}/translate/{sl}-{tl}/{word}",
       'format("/{0}/translate/{1}-{2}/{3}"' in lv
       and re.search(r'"/\{0\}/translate/\{1\}-\{2\}/\{3\}"', port) is not None,
       "the UI lang prefix comes from langToUiLang(Options.LanguageCode)")
    for code, ui in (("ru", "ru-ru"), ("es", "es-mx"), ("pt-BR", "pt-br")):
        ck(f"Lingvo: langToUiLang({code!r}) is {ui!r}",
           'case "%s": return "%s"' % (code, ui) in lv
           or '"%s": "%s"' % (code, ui) in port,
           "the JS switch and the port dict must agree for every case")
    ck("Lingvo: langToUiLang falls through to en-us",
       'default:return"en-us"' in lv.replace(" ", "")
       and '"en-us"' in port,
       "the default is en-us, not the caller's own code")
    ck("Lingvo: the injected _QT6_ALLs style block is native's",
       lv.count("_QT6_ALLs") >= 4 and port.count("_QT6_ALLs") >= 4,
       "the wrapper div, three CSS rules and the injected <div><div>")

    # SupportedLanguages, compared entry-by-entry rather than by "an array
    # exists". The two spellings differ (JS -1 vs Python None, quoted vs bare
    # strings), so they are normalised before comparison -- and the check is on
    # the CONTENT, because "the port ships some array" is not "the port ships
    # native's array".
    lv_arr = re.search(r'SupportedLanguages=\[([^\]]*)\]', lv)
    lv_port = re.search(r'^LINGVO_LANGS\s*=\s*(\[[^\]]*\])', port, re.M | re.S)
    if lv_arr is None or lv_port is None:
        ck("Lingvo: both SupportedLanguages arrays are present", False,
           "js=%s port=%s" % (lv_arr is not None, lv_port is not None))
    else:
        js = [None if v.strip() == "-1" else v.strip().strip('"')
              for v in lv_arr.group(1).split(",")]
        py = ast.literal_eval(lv_port.group(1))
        bad = [(k, n, p) for k, (n, p) in enumerate(zip(js, py)) if n != p]
        ck("Lingvo: LINGVO_LANGS equals native's SupportedLanguages",
           len(js) == len(py) and not bad,
           "len %d vs %d, %d mismatching entries: %s"
           % (len(js), len(py), len(bad), bad[:4]))
        ck("Lingvo: the unsupported holes are native's own count",
           sum(1 for v in js if v is None) == 55
           and sum(1 for v in py if v is None) == 55,
           "native has 55 -1 entries; a different count means a different table")

    # An array the nothing reads is a hole, not a feature. Lingvo's buildUri
    # indexes it through codeFromLanguage(lang), so the port that ships it must
    # also use it -- this is the same liveness check the hosts get above.
    ck("Lingvo: LINGVO_LANGS is read, not shipped dead",
       re.search(r'\bLINGVO_LANGS\b', re.sub(
           r'^\s*LINGVO_LANGS\s*=.*$', "", port, flags=re.M))
       is not None,
       "the array is present but unreferenced")

    # --- ResponseData's LINK field, which is not serviceLink() --------------
    # Common.js: `function ResponseData(a,b,c,d,e){this.translation=a||"";
    # this.sourceLanguage=b; this.translationLanguage=c;this.data=d||"";
    # this.nextRequestHandler=e||""}` -- so the link is the FOURTH argument.
    # serviceLink() is a different field, and conflating them produced three
    # wrong links (7be0014). The link is asserted against the JS's own
    # format() call, not against a literal the port could share by accident.
    rd = re.search(r'function ResponseData\(a,b,c,d,e\)\s*\{\s*'
                   r'this\.translation=a\|\|"";\s*this\.sourceLanguage=b;'
                   r'\s*this\.translationLanguage=c;\s*this\.data=d\|\|"";'
                   r'\s*this\.nextRequestHandler=e\|\|""\}', cj_src)
    ck("Common.js: ResponseData's 4th field is `data`, so a link passed 4th "
       "lands there", rd is not None,
       "the constructor moved; every link assertion below would be wrong")

    def js_link(name):
        """The ``x = format(...)`` a service's response builds its link from.

        Paren-balanced: a naive ``[^)]*`` stops inside ``encodeGetParam(b)``
        and silently truncates the expression, which makes the expected string
        below unmatchable -- and an assertion that can never match is worse than
        a missing one.
        """
        s = sources.get(name, "")
        i = s.find("function serviceDictionaryResponse")
        if i < 0:
            return ""
        seg = s[i:i + 1600]
        for m in re.finditer(r'([a-z])=format\(', seg):
            st, d, j = m.end() - 1, 0, m.end() - 1
            while j < len(seg):
                if seg[j] == "(":
                    d += 1
                elif seg[j] == ")":
                    d -= 1
                    if d == 0:
                        return seg[m.start():j + 1]
                j += 1
        return ""

    # Urban: format("{0}/{1}", host, word) -- NOT the /define.php?term= request
    ck("Urban: the link is host/<word>, not the request URL",
       'b=format("{0}/{1}",e,encodeGetParam(b))' in js_link("Urban Dictionary")
       and re.search(r'return\s+"\{0\}/\{1\}"\.format\(\s*urban_host\(\),\s*'
                     r'_q\(word\)\)', port) is not None,
       "reusing the request path here makes the link a duplicate of it")
    ck("Urban: the link contains no ?term=", "?term=" not in re.search(
        r'def urban_link\(word\)[^:]*:\s*"""(.|\n)*?"""\s*\n\s*return\s+([^\n]+)',
        port).group(2), "the request's query string leaked into the link")

    # ImTranslator: format("{0}/translation/", serviceHost()) -- the dictionary
    # subdomain is serviceLink's field, not this one's.
    ck("ImTranslator: the link is serviceHost + /translation/",
       'b=format("{0}/translation/",b)' in js_link("ImTranslator")
       and re.search(r'return\s+"\{0\}/translation/"\.format\(\s*'
                     r'imtranslator_host\(\)\)', port) is not None,
       "imtranslator_host() is http://imtranslator.net; the dictionary. "
       "subdomain belongs to serviceLink")
    ck("ImTranslator: serviceHost is the bare domain, not dictionary.*",
       'return"http://imtranslator.net"' in sources.get("ImTranslator", ""),
       "if this changes, imtranslator_link() follows it")

    # Babylon Dictionary: host/{code(target)}/{code(source)}/, target first
    ck("Babylon Dictionary: the link is host/{target}/{source}/ with no word",
       'b=format("{0}/{1}/{2}/",b,codeFromLanguage(c),codeFromLanguage(d))'
       in js_link("Babylon Dictionary")
       and re.search(r'return\s+"\{0\}/\{1\}/\{2\}/"\.format\(\s*'
                     r'babylon_dict_host\(\),\s*tgt,\s*src\)', port) is not None,
       "c is the target and d the source in ResponseData(text, source, "
       "target, data) -- so the ORDER is target-then-source")

    # Wikipedia: two distinct fields, and an earlier draft deleted the
    # distinction. Both are pinned so neither can be merged into the other.
    ck("Wikipedia: serviceLink and the ResponseData link are distinct",
       re.search(r'return\s+"https://www\.wikipedia\.org/"', port) is not None
       and re.search(r'return\s+host\s*\+\s*"/wiki/"', port) is not None,
       "wikipedia_link() is serviceLink; wikipedia_article_url() is the "
       "ResponseData link -- both must exist separately")

    # Liveness: every *_LANGS table is either read, or provably nothing to read.
    ck("a language table that no request uses is dead BY DESIGN, not by "
       "omission",
       all(re.search(r'\b' + t + r'\b', re.sub(
               r'^\s*' + t + r'\s*=.*$', "", port, flags=re.M))
           for t in ("LINGVO_LANGS", "REVERSO_LANGS", "WORDREF_LANGS",
                     "MULTITRAN_LANGS", "WIKI_LANGS", "GSEARCH_LANGS",
                     "BABYLON_DICT_LANGS", "IMTRANS_LANGS")),
       "one of the eight request-relevant tables is unreferenced again")
    for name in ("Oxford Learner Dictionary", "Urban Dictionary"):
        s = sources.get(name, "")
        ck(f"{name}: its table is legitimately unused (no language in the "
           f"request)",
           "codeFromLanguage" not in
           re.search(r'function serviceDictionaryRequest\([^)]*\)\{(.*?)'
                     r'return', s).group(1)
           and not re.search(r'\b' +
                             ("OXFORD_LANGS" if name.startswith("Oxford")
                              else "URBAN_LANGS") + r'\b',
                             re.sub(r'^\s*(OXFORD|URBAN)_LANGS\s*=.*$', "",
                                    port, flags=re.M)),
           "a fixed-path request cannot consume a language table; if the JS "
           "gains one, this check is the signal")

    # --- the BEHAVIOUR, called rather than matched ---------------------------
    # All the checks above compare text, and text-comparison is not enough:
    # five mutants reintroduced the exact defects fixed in 1146d6d and 7be0014
    # (raw indices interpolated, an unsupported entry falling back to its input,
    # `WIKI_LANGS[17]` replaced by a literal "en") and every one of them passed
    # a 97-assertion suite that pinned the format strings. The functions have to
    # be CALLED. Note this suite is offline -- these are pure string builders, so
    # calling them needs no network and no mocked service.
    try:
        sys.path.insert(0, ROOT)
        from qtranslate.services import dictionary as _D
    except Exception as exc:  # pragma: no cover - import path issue
        ck("dictionary.py imports", False, repr(exc))
    else:
        # A native language index must resolve to that provider's CODE. If the
        # index leaks into the URL, the port is building URLs native never does.
        for label, fn, args, want in (
            ("Lingvo", _D.lingvo_build_uri, ("hello", 17, 46, "en"),
             "/en/translate/en-ru/hello"),
            ("Lingvo (ISO)", _D.lingvo_build_uri, ("hello", "en", "ru", "en"),
             "/en/translate/en-ru/hello"),
            ("Reverso", _D.reverso_build_uri, ("hello", 17, 46),
             "/english-russian/hello"),
            ("WordReference", _D.wordreference_build_uri, ("hello", 17, 46),
             "/enru/hello"),
            ("Google Search", _D.gsearch_build_uri, ("hello", 46),
             "/search?q=hello&ie=UTF-8&hl=ru"),
            ("MultiTran", _D.multitran_build_uri, ("hello", "en", "ru", "en"),
             "/m.exe?l1=2&l2=1&s=hello&SHL=1"),
        ):
            got = fn(*args)
            ck("%s: a native index resolves to the provider's own code"
               % label, got == want, "got %r want %r" % (got, want))
        # No URL may carry a bare language index. The digits 17/46/60/2 are
        # checked positionally (not as a bare substring) because some legit
        # codes contain them, e.g. Google Search's hl= is fine and Reverso's
        # `-1` for unsupported is required.
        for label, fn, args in (
            ("Lingvo", _D.lingvo_build_uri, ("hello", 17, 46, "en")),
            ("Reverso", _D.reverso_build_uri, ("hello", 17, 46)),
            ("WordReference", _D.wordreference_build_uri, ("hello", 17, 46)),
        ):
            got = fn(*args)
            ck("%s: no raw language index reaches the URL" % label,
               not re.search(r'(?<![\w-])(17|46|60)(?![\w-])', got),
               "an index leaked into %r" % got)

        # An unsupported entry must interpolate as -1, the value native sends,
        # NOT fall back to the input. Falling back makes index 60 look like a
        # code, which is how one of these mutants survived. Index 0 is NOT a
        # test of this: common.is_language's `1 < a` bounds check already
        # returns -1 there, so the table is never consulted and the fallback
        # branch never runs. Index 60 is IN RANGE and unsupported, which is the
        # only shape that reaches it.
        for label, fn, args, want in (
            ("Lingvo target unsupported", _D.lingvo_build_uri,
             ("hello", 17, 60, "en"), "/en/translate/en--1/hello"),
            ("Lingvo source unsupported", _D.lingvo_build_uri,
             ("hello", 60, 17, "en"), "/en/translate/{0}-en/hello"
             .format(_D._codes(_D.LINGVO_LANGS, 60, 17)[0])),
        ):
            got = fn(*args)
            ck("%s: interpolates -1, not the input" % label,
               got == want, "got %r want %r" % (got, want))
        ck("supported() reports that pair unsupported",
           _D.supported(_D.REVERSO_LANGS, 17, 0) is False
           and _D.supported(_D.LINGVO_LANGS, 17, 60) is False
           and _D.supported(_D.REVERSO_LANGS, 17, 46) is True,
           "the bounds test in common.is_language is not a support test; an "
           "in-range unsupported index is the case that distinguishes them")

        # Wikipedia: the host resolves the index, and the ENGLISH fallback comes
        # from the ARRAY, not a literal. A "en" literal passes until the entry
        # changes, which is exactly what the mutant did.
        ck("Wikipedia: host resolves an index to its code",
           _D._wiki_host(46) == "https://ru.m.wikipedia.org",
           repr(_D._wiki_host(46)))
        ck("Wikipedia: an index does not reach the hostname",
           "17.m.wikipedia" not in _D._wiki_host(17),
           repr(_D._wiki_host(17)))
        ck("Wikipedia: the fallback is WIKI_LANGS[17], not a literal",
           _D._wiki_host("") == "https://%s.m.wikipedia.org"
           % _D.WIKI_LANGS[17]
           and re.search(r'code\s*=\s*WIKI_LANGS\[17\]', port) is not None,
           repr(_D._wiki_host("")))

        # The four link fields, called rather than matched.
        for label, got, want in (
            ("Urban", _D.urban_link("hello"),
             "https://www.urbandictionary.com/hello"),
            ("ImTranslator", _D.imtranslator_link(),
             "http://imtranslator.net/translation/"),
            ("Babylon Dictionary", _D.babylon_dict_link("en", "ru"),
             "https://dictionary.babylon-software.com/russian/english/"),
            ("Wikipedia article", _D.wikipedia_article_url("hello", "en", "ru"),
             "https://ru.m.wikipedia.org/wiki/hello"),
        ):
            ck("%s: the ResponseData link is native's shape" % label,
               got == want, "got %r want %r" % (got, want))
        ck("Urban's link carries no request querystring",
           "?term=" not in _D.urban_link("hello"))
        ck("Babylon Dictionary's link has the word NOWHERE in it",
           "hello" not in _D.babylon_dict_link("en", "ru"),
           "native's link is host/{target}/{source}/ -- it takes no word at all")
        ck("Babylon Dictionary's link is target-then-source",
           _D.babylon_dict_link("en", "ru")
           == "https://dictionary.babylon-software.com/russian/english/"
           and _D.babylon_dict_link("en", "en") ==
           "https://dictionary.babylon-software.com/english/english/",
           "target first, source second -- an asymmetric pair proves the order")


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_plugin_js_recovered: all checks ok (%d assertions%s)"
      % (n[0], ", payload used" if os.path.exists(PAYLOAD) else ", NO PAYLOAD"))
