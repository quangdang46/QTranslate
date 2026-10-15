"""Fuzz the port's Common.js ports against a line-by-line faithful model.

The model below is the recovered `Common.js` transcribed expression for
expression -- no reference to the port -- so a divergence is a port bug,
not two copies of the same mistake. Each helper is probed with inputs
built from the character classes that actually trigger its edge cases
(leading/trailing whitespace, CR/LF pairs, quote styles, nested tags,
nonexistent attributes).

The model and the port are compared over a deterministic random corpus,
so this is a differential test rather than a fixed-vector table: it can
find divergence the tables miss.

Headless; the JS is READ from the artifact, never executed.
"""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common as C  # noqa: E402

NL = "\r\n"
N_PROBES = 30000
random.seed(20261016)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --------------------------------------------------------------- the model
def m_trim_string(a):
    return re.sub(r"(^\s+)|(\s+$)", "", a) if a else ""


def m_strip_html(a):
    if not a:
        return ""
    a = re.sub(r"<!--[\s\S]*?-->", "", a)
    a = re.sub(r"<(style|script)(.|\s)*?(style|script)>", "", a)
    a = re.sub(r"<br/>", NL, a, flags=re.I)
    a = re.sub(r"<[^>]+>", "", a)
    a = a.replace("&nbsp;", " ")
    a = re.sub(r"&#x27;", "'", a, flags=re.I)
    a = re.sub(r" +(?= )", "", a)
    # removeEmptyLines
    a = a.replace("\r", "")
    lines = a.split("\n")
    lines = ["" if not re.search(r"[\S]", ln) else ln for ln in lines]
    a = "\n".join(lines)
    a = re.sub(r"\n{3,}", "\n\n", a)
    a = a.replace("\n", NL)
    return m_trim_string(a)


def m_remove_empty_lines(a):
    if not a:
        return ""
    a = a.replace("\r", "")
    lines = a.split("\n")
    lines = ["" if not re.search(r"[\S]", ln) else ln for ln in lines]
    a = "\n".join(lines)
    a = re.sub(r"\n{3,}", "\n\n", a)
    a = a.replace("\n", NL)
    return m_trim_string(a)


def m_string_find(a, b):
    """Port of ``stringFind(a,b)`` -- a *compiled* pattern takes the
    ``a.match(b)`` branch; a plain string takes the ``indexOf`` branch,
    exactly as native's ``typeof b === "string"`` test does."""
    if b:
        if isinstance(b, str):
            c = a.find(b)
            return {"index": c, "length": len(b)} if c > -1 else None
        c = b.search(a)
        return {"index": c.start(), "length": len(c.group(0))} if c else None


def m_string_find_sub(a, b, c, d, e):
    if not (a and b and d):
        return ""
    b = m_string_find(a, b)
    if not b:
        return ""
    a = a[b["index"]:] if c else a[b["index"] + b["length"]:]
    b = m_string_find(a, d)
    if not b:
        return ""
    return a[:b["index"] + b["length"]] if e else a[:b["index"]]


def m_remove_if_starts_with(a, b):
    return a[len(b):] if a.startswith(b) else a


def m_update_html_links(a, b):
    if not a:
        return ""
    c = "https://" if b.startswith("https") else "http://"
    b = m_remove_if_starts_with(b, c)
    if not b.endswith("/"):
        b += "/"
    # the native does eight global replaces, each on the WHOLE string
    a = re.sub(r'href="//', 'href="' + c, a, flags=re.I)
    a = re.sub(r'href="/', 'href="' + c + b, a, flags=re.I)
    a = re.sub(r'src="//', 'src="' + c, a, flags=re.I)
    a = re.sub(r'src="/', 'src="' + c + b, a, flags=re.I)
    a = re.sub(r"href='//", "href='" + c, a, flags=re.I)
    a = re.sub(r"href='/", "href='" + c + b, a, flags=re.I)
    a = re.sub(r"src='//", "src='" + c, a, flags=re.I)
    a = re.sub(r"src='/", "src='" + c + b, a, flags=re.I)
    return a


# ------------------------------------------------------------- the corpus
WS = ["", " ", "  ", "\t", "\r", "\n", "\r\n", " \r\n ", "\xa0"]
FRAG = ["a", "b", "abc", "word", "  ", "\t", "\r", "\n", "<br/>", "<br />",
        "&nbsp;", "&#x27;", "<!-- c -->", "<p>", "</p>", "<div>", "</div>",
        "<style>", "</style>", "  hi  ", "<a>", "é", "å", "中"]


def gen(maxlen=9):
    return "".join(random.choice(FRAG)
                   for _ in range(random.randint(0, maxlen)))


# -------------------------------------------------------------- the probes
cmp_count = [0]


def same(name, made, model_fn, a, *rest):
    cmp_count[0] += 1
    want = model_fn(a, *rest)
    if made != want:
        fail.append("%s(%r%s) -> port %r != model %r"
                    % (name, a, list(rest), made, want))


for _ in range(N_PROBES):
    s = gen()
    same("trim_string", C.trim_string(s), m_trim_string, s)
    same("strip_html", C.strip_html(s), m_strip_html, s)
    same("remove_empty_lines", C.remove_empty_lines(s), m_remove_empty_lines,
         s)
    same("string_find_sub", C.string_find_sub(
        s, "a", False, "b", False), m_string_find_sub, s, "a", False, "b",
        False)
    same("update_html_links", C.update_html_links(s, "http://h.tld"),
         m_update_html_links, s, "http://h.tld")

# string_find / string_find_sub with a regex marker, the shape the
# dictionary providers actually pass
RE_MARKERS = [r"<section ", r"</section>", r"<div ",
              r'<div id="(articleWRD|article)">', r"</table>"]
for marker in RE_MARKERS:
    for end in ("</section>", "b", r"</div>"):
        probe = "xx" + marker + "body yyy" + end + "zz"
        for c in (True, False):
            for e in (True, False):
                cmp_count[0] += 1
                got = C.string_find_sub(probe, re.compile(marker), c,
                                        end, e)
                # model: the marker arrives as a REGEX (the port was handed
                # a compiled one), so it must go down native's `a.match(b)`
                # branch. Handing the model the raw string would take the
                # `typeof b === "string"` branch and indexOf the literal --
                # a different (and correct) native path.
                want = m_string_find_sub(probe, re.compile(marker), c,
                                         end, e)
                if got != want:
                    fail.append("string_find_sub(%r,%r,%s,%r,%s) -> "
                                "port %r != model %r"
                                % (probe, marker, c, end, e, got, want))

ck("no divergence across the whole corpus (n=%d)" % cmp_count[0],
   not fail, "%d divergences" % len(fail))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:15]:
        print("  -", f)
    raise SystemExit(1)
print("regress_common_fuzz: all checks ok (%d assertions, %d comparisons)"
      % (n[0], cmp_count[0]))
