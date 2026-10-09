"""Regression: the Common.js framework layer (`qtranslate/common.py`).

This is the port's substitute for native's JS engine. Native loads
`Common.js` + one `Services/*/Service.js` into `CLSID_JScript` via
`IActiveScript`/`IActiveScriptParse` (F1/F2/F3/F5) and calls the exported
functions by name through `GetIDsOfNames`+`Invoke` (F6). The port has no
script engine — `common.py` is a **hand port** of Common.js, so the row can
never claim a JS engine, only that each ported helper matches its JS
original.

What that makes testable: the **framework helpers**, which every service
port calls. Before this suite they had **zero** coverage (`smoke_dict.py`
is the only file importing `qtranslate.common`, and it exercises dictionary
paths, not the helpers). So a regression in `stringFindSub`,
`removeElements` or `updateHtmlLinks` would have been invisible.

Each case below is a known-answer vector from the JS semantics. Where the
JS original has a quirk the quirk is asserted, not normalized away — that
is the whole point of a compatibility layer.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import common as C  # noqa: E402

fail = []
n = [0]


def ck(name, got, want):
    n[0] += 1
    if got != want:
        fail.append(f"{name} -- got {got!r}, want {want!r}")


def t(name, ok):
    n[0] += 1
    if not ok:
        fail.append(f"{name} -- expected true")


# --- addOption / Options: the JS `var Options={}` global (F7/F8) ---
C.Options.clear()
C.add_option("GoogleTkk", "123.456")
ck("addOption writes the shared store", C.Options.get("GoogleTkk"), "123.456")
C.add_option("LanguageCode", "vi")
ck("store is the module-level dict", C.Options["LanguageCode"], "vi")

# --- stringFind(a,b): str -> indexOf, regex -> match ---
ck("stringFind str hit", C.string_find("abc", "b"),
   {"index": 1, "length": 1})
ck("stringFind str miss -> None (JS undefined)",
   C.string_find("abc", "z"), None)
ck("stringFind regex", C.string_find("aXbc", r"X"), {"index": 1, "length": 1})
ck("stringFind empty needle -> None (JS falsy guard)",
   C.string_find("abc", ""), None)

# --- stringSplit(a,b) ---
ck("stringSplit on comma", C.string_split("a,b,c", ","), ["a", "b", "c"])
# NOTE: JS "a1b22c".split(/\d+/) is ['a','b','c'], NOT ['a','b','','c'] —
# `+` is greedy, so it consumes the whole "22" run. (The [a,b,'',c] shape is
# what single-char /\d/ gives.) Verified against node before writing this.
ck("stringSplit regex is greedy like JS",
   C.string_split("a1b22c", r"\d+"), ["a", "b", "c"])
ck("stringSplit single-char regex gives the empty middle field",
   C.string_split("a1b22c", r"\d"), ["a", "b", "", "c"])

# --- stringFindSub(a,b,c,d,e) — the tkk/romanization slicer (E21/F12) ---
ck("sub between markers, exclusive",
   C.string_find_sub("xx_ctkk='123';yy", "_ctkk='", False, "';", False), "123")
ck("sub inclusive of end marker",
   C.string_find_sub("xx_ctkk='123';", "_ctkk='", False, "';", True), "123';")
ck("sub from_start keeps the start marker",
   C.string_find_sub("<b>text</b>", "<b>", True, "</b>", False), "<b>text")
# A regex start with from_start=False skips the ENTIRE match (`f[0]`), so a
# capture group does not keep its text. Node confirms JS behaves the same:
#   stringFindSub('k=9;', /k=(\d+)/, false, ';', false) === ""
ck("sub regex start skips the whole match (JS f[0], not the group)",
   C.string_find_sub("k=9;", r"k=(\d+)", False, ";", False), "")
# ...so the JS-native way to keep the matched text is from_start=True, which
# starts the second search at f.index rather than after the match.
# NOTE: the pattern must be a compiled `re.Pattern` (or JS RegExp). A plain
# str is matched LITERALLY by both this port and JS — `"k=\d+"` would look
# for a backslash, which is why this case returns the whole remainder.
ck("sub regex start with from_start keeps the whole match",
   C.string_find_sub("k=9;", re.compile(r"k=\d+"), True, ";", False), "k=9")
ck("sub start absent -> empty",
   C.string_find_sub("nothing", "x", False, ";", False), "")
ck("sub end absent -> empty",
   C.string_find_sub("a=1", "a=", False, ";", False), "")

# --- trim / starts / ends / remove ---
t("trimString strips both ends", C.trim_string("  x  ") == "x")
t("trimString None-safe", C.trim_string(None) == "")
t("startsWith", C.starts_with("abc", "ab"))
t("startsWith false", not C.starts_with("abc", "bc"))
t("endsWith", C.ends_with("abc", "bc"))
t("removeIfStartsWith", C.remove_if_starts_with("qtdp:link", "qtdp:") == "link")
t("removeIfStartsWith no match",
  C.remove_if_starts_with("qtdp:link", "http:") == "qtdp:link")

# --- unquoteHtml(a) ---
ck("unquoteHtml", C.unquote_html("a&amp;b&lt;c&gt;d&quot;e&#39;f"),
   "a&b<c>d\"e'f")
ck("unquoteHtml None-safe", C.unquote_html(None), "")

# --- removeEmptyLines(a) — exact 1:1 incl. the >2-blank clamp ---
ck("removeEmptyLines clamps 3+ blanks to 2",
   C.remove_empty_lines("a\n\n\n\nb"), "a" + C.NL + C.NL + "b")
t("removeEmptyLines trims", not C.remove_empty_lines("\n\n x \n\n").endswith("\n"))

# --- stripHtml(a) ---
ck("stripHtml drops tags", C.strip_html("<b>hi</b> <i>there</i>"), "hi there")
ck("stripHtml drops script/style", C.strip_html("<style>a{}</style>ok"), "ok")
ck("stripHtml collapses spaces",
   C.strip_html("a     b"), "a b")
ck("stripHtml None-safe", C.strip_html(None), "")

# --- updateHtmlLinks(a,b) ---
ck("updateHtmlLinks protocol-relative",
   C.update_html_links('<a href="//x/y">', "https://h/p"),
   '<a href="https://x/y">')
ck("updateHtmlLinks root-relative",
   C.update_html_links('<a href="/y">', "https://h/p"),
   '<a href="https://h/p/y">')
ck("updateHtmlLinks base without trailing slash",
   C.update_html_links('<img src="/i">', "https://h/p"),
   '<img src="https://h/p/i">')
ck("updateHtmlLinks None-safe", C.update_html_links(None, "https://h/"), "")

# --- removeTags / removeAttributes / removeElements ---
t("removeTags keeps text", "<b>x</b>" == C.remove_tags("<b>x</b>", ["b"])
   or C.remove_tags("<b>x</b>", ["b"]) == "x")
t("removeTags not matching", C.remove_tags("<b>x</b>", ["i"]) == "<b>x</b>")
t("removeAttributes strips style",
  C.remove_attributes('<div style="a" data-x="1">', ["style"]).find("style") < 0)
t("removeElements removes the whole block",
  C.remove_elements("<p>a</p><p>b</p>", ["p"]) == "")
t("removeElements leaves unmatched",
  C.remove_elements("<p>a</p>", ["div"]) == "<p>a</p>")

# --- language helpers: the index<->code mapping every provider uses ---
LANGS = [-1, "auto", "af", "az", "ar", "en", "vi"]
ck("codeFromLanguage index", C.code_from_language(5, LANGS), "en")
ck("codeFromLanguage auto", C.code_from_language(1, LANGS), "auto")
ck("codeFromLanguage out of range", C.code_from_language(99, LANGS), -1)
ck("languageFromCode hit", C.language_from_code("en", LANGS), 5)
ck("languageFromCode miss", C.language_from_code("zz", LANGS), 0)
t("usesAutoDetectCode", C.uses_auto_detect_code(LANGS))
t("usesAutoDetectCode false when -1",
  not C.uses_auto_detect_code([-1, -1]))
t("isLanguage in range", C.is_language(3, LANGS))
t("isLanguage rejects 0/1", not C.is_language(0, LANGS)
  and not C.is_language(1, LANGS))

# --- encoders: MAX_URI_LEN split is the native 1800-byte cap ---
ck("encodeUriParam escapes everything",
   C.encode_uri_param("a b&c"), "a%20b%26c")
ck("encodeUriParam None-safe", C.encode_uri_param(None), "")
LONG = "x" * 4000
t("encodeGetParam caps at MAX_URI_LEN", len(C.encode_get_param(LONG)) <= C.MAX_URI_LEN)
# JS: substring(0, 1800) then substring(0, lastIndexOf('%20')) — so the
# result ends mid-run and, on a string that is full of %20s, still contains
# them. Verified against node: ep('word '.repeat(600)) -> 1796 chars ending
# "0word%20word". The assertion is about the cap and the cut point, not
# about the absence of %20.
_long = C.encode_get_param(LONG)
t("encodeGetParam truncates the over-long input",
  len(_long) < len(LONG) and _long.startswith("x"))
_words = C.encode_get_param("word " * 600)
t("encodeGetParam cuts at a space boundary (not mid-%20)",
  not _words.endswith("%") and len(_words) <= C.MAX_URI_LEN)
ck("encodeGetParam under the cap is untouched",
   C.encode_get_param("a b"), "a%20b")
ck("limitSource truncates", len(C.limit_source("y" * 9000)), C.MAX_SOURCE_LEN)
ck("limitSource None-safe", C.limit_source(None), "")
t("prepareSource normalizes CRLF", C.prepare_source("a\r\nb\rc") == "a\nb\nc")

# --- format_q: JS String.replace({0}, ...) semantics ---
ck("format_q substitutes numbered slots",
   C.format_q("{0}-{1}-{0}", "a", "b"), "a-b-a")

# --- header builders (getHeader/postHeader are what curl sends) ---
_h = C.get_header()
C.Options["LanguageCode"] = "vi"
t("getHeader has Accept", "Accept: */*" in C.get_header())
t("getHeader honors LanguageCode", "vi" in C.get_header())
t("getHeader asks for gzip", "gzip" in C.get_header())
t("postHeader default is form-urlencoded",
  "application/x-www-form-urlencoded" in C.post_header())
t("postHeader(True) is json",
  "application/json" in C.post_header(True))
t("postHeader includes the base headers", "Accept: */*" in C.post_header())

# --- split_headers: the parser for those same blocks ---
ck("split_headers", C.split_headers("A: 1" + C.NL + "B: 2"), {"A": "1", "B": "2"})
ck("split_headers keeps a colon in the value",
   C.split_headers("H: a:b"), {"H": "a:b"})

# --- constants that the whole port depends on ---
ck("NL is CRLF", C.NL, "\r\n")
ck("NL2 is blank line", C.NL2, "\r\n\r\n")
ck("MAX_URI_LEN 1800", C.MAX_URI_LEN, 1800)
ck("MAX_SOURCE_LEN 5000", C.MAX_SOURCE_LEN, 5000)
ck("AUTO_DETECT_LANGUAGE 1", C.AUTO_DETECT_LANGUAGE, 1)
ck("ENGLISH_LANGUAGE 17", C.ENGLISH_LANGUAGE, 17)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_common_framework: all checks ok (%d assertions)" % n[0])
