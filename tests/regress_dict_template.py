"""Pin the dictionary template bytes + card render (row E, headless).

The native RT_HTML resource id 192 is the dictionary card template; the
port ships `qtranslate/dict_template.html` and must stay byte-identical.
`dict_render.render_cards` fills it. This suite covers both WITHOUT the
GUI suite (ui_match) so the check runs in a no-tkinter session.

pefile is optional: when absent the byte-identity half is honestly
SKIPPED (the render half always runs).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]
skipped = []


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = "C:/Program Files (x86)/QTranslate/QTranslate.exe"
TPL = os.path.join(ROOT, "qtranslate", "dict_template.html")

from qtranslate import dict_render as DR

# --- the template file exists and is the native size --------------------
tpl = io.open(TPL, "rb").read()
ck("dict_template.html present", len(tpl) > 0, str(len(tpl)))
ck("template is 3062 bytes (native RT_HTML-192)",
   len(tpl) == 3062, "len=%d" % len(tpl))

# --- byte-identity vs the recovered resource (needs pefile) -------------
try:
    import pefile as _pe
    pexe = _pe.PE(EXE)
    native = b""
    for t in pexe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id != 23:  # RT_HTML
            continue
        for d in t.directory.entries:
            if d.id != 192:
                continue
            for lg in d.directory.entries:
                native = pexe.get_data(lg.data.struct.OffsetToData,
                                       lg.data.struct.Size)
    ck("template byte-identical to RT_HTML-192", native == tpl,
       "native=%d tpl=%d" % (len(native), len(tpl)))
except ImportError:
    skipped.append("dict-template-bytes (pefile missing)")
except Exception as e:
    ck("template byte-compare ran", False, repr(e))

# --- render_cards fills the template ------------------------------------
page = DR.render_cards([("1", "Google", "<b>hi</b>")])
ck("render_cards returns HTML", "<html" in page.lower(), page[:40])
ck("render_cards includes the card content", "<b>hi</b>" in page)
ck("render_cards includes the qt-content container",
   "qt-content" in page, "the native template's container class")
ck("empty result list still renders a page",
   "<html" in DR.render_cards([]).lower())

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_template: all checks ok (%d assertions%s)"
      % (n[0], (", %d skipped" % len(skipped)) if skipped else ""))
