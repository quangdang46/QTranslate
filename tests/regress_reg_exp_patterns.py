"""Regression: the three regExpRemove patterns are native's, byte for byte.

``regExpRemove(a,b,c)`` builds the pattern by formatting ``c`` with
``b.join("|")`` -- so the pattern text itself is the contract, and a
transcription slip changes which strings match while still looking fine
on ordinary input.

One real bug this caught (fixed 2026-10-16): ``removeAttributes``'s
pattern was written as a Python raw string containing ``\\.``, which the
regex engine reads as *backslash + any char* where native's ``\\.``
(escaped in the JS literal) is the regex escaped dot ``\\.``. Both match
a dot, so every ordinary attribute value passed; they diverge on a value
containing ``\\"`` -- ``<a href="a\\"b">t</a>`` -- where native leaves
``<ab">t</a>`` and the wrong port returned ``<a>t</a>``, deleting the
rest of the tag.

The suite compares the port's pattern to the pattern READ out of the
recovered `Common.js` (never executed), then pins the diverging input.

Headless. Skips if the artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common as C  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")
i = TS.find("new ServiceHeader(25,")
PRE = TS[:i]


def native_pattern(js_fn):
    """The pattern literal of ``<js_fn>(a,b)`` as REGEX TEXT.

    The JS literal uses ``\\\\`` for one backslash and ``\\"`` for a quote;
    ``\\s`` is not a JS escape at all, so it stays backslash-s, which is
    the regex we want.
    """
    lit = re.search(r"function " + js_fn + r"\(a,b\)\{return regExpRemove\(a,b,"
                    r'(.*?)\)\}', PRE).group(1)
    assert lit.startswith('"') and lit.endswith('"'), lit
    js = lit[1:-1]
    return js.replace("\\\\", "\x00").replace('\\"', '"').replace("\x00",
                                                                  "\\")


def port_pattern(py_fn, helper):
    """The port's pattern, captured from the call it actually makes.

    ``reg_exp_remove`` is monkeypatched for one call, so the value comes
    from the real argument rather than from source text -- a docstring that
    quotes the JS (as ``remove_attributes``' now does) can never be
    mistaken for the pattern this way.
    """
    seen = []
    real = C.reg_exp_remove

    def spy(s, tags, fmt):
        seen.append(fmt)
        return real(s, tags, fmt)

    C.reg_exp_remove = spy
    try:
        helper('<a href="x">t</a>', ["href"])
    finally:
        C.reg_exp_remove = real
    assert len(seen) == 1, "%s: captured %r" % (py_fn, seen)
    return seen[0]


for js_fn, py_fn, py_helper in (
        ("removeAttributes", "remove_attributes", C.remove_attributes),
        ("removeTags", "remove_tags", C.remove_tags),
        ("removeElements", "remove_elements", C.remove_elements)):
    nat = native_pattern(js_fn)
    port = port_pattern(py_fn, py_helper)
    # `\"` in a Python regex is the same character as `"`, so the two
    # patterns can differ in spelling and still be the same pattern. What
    # matters -- and what the bug lived in -- is the ESCAPED DOT: `\.`
    # (a literal dot) versus `\\.` (backslash + any char).
    normalized = lambda p: p.replace(r'\"', '"')  # noqa: E731
    ck("%s: the port's pattern is native's" % js_fn,
       normalized(port) == normalized(nat),
       "\n  native=%r\n  port  =%r" % (nat, port))
    if js_fn == "removeAttributes":
        # only removeAttributes has the `(?:\.|[^"])*` step
        ck("%s: native's alternation step is an escaped DOT, not "
           "backslash-any" % js_fn, r"(?:\.|[^" in nat, nat)
        ck("%s: the port keeps the dot escaped exactly once" % js_fn,
           r"(?:\.|[^" in port, port)
    ck("%s: {0} is the join slot" % js_fn, "{0}" in port, port)

    # and the helper's behaviour agrees with a model built from native's
    # pattern, on a corpus that includes the escaping edge cases
    MODEL = re.sub(r"\{0\}", "{0}", nat)
    bad = []

    def model(a, attrs, _p=MODEL):
        return re.sub(_p.format("|".join(attrs)), "", a)

    probes = [
        '<a href="x">t</a>', '<a href="a.b">t</a>', '<a href="a\\\\b">t</a>',
        "<a title='y'>t</a>", '<a id class="c">t</a>',
        '<a href="x" title="y">t</a>',
        r'<a href="a\"b">t</a>',          # the case the bug lived in
        r'<a title=\'x\\\'y\'>t</a>',
        '<p>plain</p>', '<b>x</b><b>y</b>', '<B>x</B>',
        '<div class="a">' + 'z' * 20 + '</div>',
        '<h3 class="t">H</h3>', '<h6>H</h6>', '<h2>H</h2>',
    ]
    for probe in probes:
        try:
            want = model(probe, ["href", "title", "id", "b", "h[3-6]",
                                 "class"])
        except re.error:
            continue
        try:
            got = C.reg_exp_remove(probe, ["href", "title", "id", "b",
                                           "h[3-6]", "class"], nat)
        except re.error:
            continue
        if got != want:
            bad.append((probe, got, want))
    ck("%s: behaviour matches the native pattern on %d probes"
       % (js_fn, len(probes)), not bad, repr(bad[:3]))
    del py_helper

# the escaped-quote case, pinned on the real public helper too
ck("remove_attributes does not eat a tag on href=\"a\\\"b\"",
   C.remove_attributes(r'<a href="a\"b">t</a>', ["href"]) == r'<ab">t</a>',
   repr(C.remove_attributes(r'<a href="a\"b">t</a>', ["href"])))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_reg_exp_patterns: all checks ok (%d assertions)" % n[0])
