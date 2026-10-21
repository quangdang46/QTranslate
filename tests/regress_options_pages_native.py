"""Regression: the Options pages are native's nine dialogs, asserted on
the live widgets.

Native's Options window (DLG154) is a shell -- a nav list (1078) and
OK/Cancel/Apply -- hosting NINE page dialogs. The mapping is fixed by
the templates in the recovered image:

    Basics 171   Hotkeys 179   Internet 172
    Services 173 Languages 174  Appearance 175
    Exceptions 176  Advanced 185  Updates 205

and each page's controls are fixed too: a group box, a set of
ComboBoxes, a list view, and so on.

Six real defects were found by rendering the port's Options window and
comparing it with `docs/review/native_screens/2135..2141.png`:

1. **The English language pack was never loaded.** `_pack()` skipped
   the pack when the language was "English" (the comment claimed
   "English = built-in strings"). The hardcoded fallbacks are the
   DIALOG TEMPLATE's design-time strings, while the pack holds the
   RUNTIME strings native actually draws -- and they differ: DLG175's
   control 1159 is "Always activate" in the template and "Activate
   when opened" in the pack, 1145 is "Transparency (0-90):" in the
   template and "Transparency (0 - 90):" in the pack. So every label
   in the English UI was the template's text.
2. **The Services page drew two EMPTY lists.** The lists were filled
   from `ServicesOrder` alone, and that key is absent until the user
   reorders something, so on a fresh config both lists were empty.
3. **The Languages page was a page native does not have.** It showed
   "Default languages" with Translate from/to, Dictionary, Virtual
   keyboard, Always detect, Smart detection, Language pairs and a
   Disabled-languages list. Native's Languages page is DLG174: a
   four-column checklist of the 72 languages plus "Check / Uncheck
   all".
4. **The group boxes were bold Labels.** Every page's Win32 group box
   (1076, 1124, 1046, 1063, 1064, 1049, 1048, 1146, 1186, 1158) was
   drawn as a caption with no frame, and several ComboBoxes were
   Entries.
5. **The Advanced page drew duplicated labels** -- the same config key
   under two captions ("Preferred domain:" and "Google domain:" both
   wrote `PreferredDomain`) -- and overflowed the window, pushing the
   Apply button off the bottom edge.
6. **The Exceptions mode combo showed a raw Python list.** The pack
   stores a combo's ITEMS as `[[index, text], ...]`, and `_Cw` returns
   that list verbatim.

Every assertion here calls the real code and reads the real widget
tree; none of them grep source text.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail))


# --- 1. the language pack resolves (the `_pack()` fix) --------------------
from qtranslate.app import _Cw, _pack  # noqa: E402

ck("the English language pack loads", len(_pack()) > 0,
   "the pack is empty: every label falls back to the template text")
for _cid, _want in ((1159, "Activate when opened"),
                    (1145, "Transparency (0 - 90):"),
                    (1147, "Auto-hide delay:"),
                    (1137, "Icons:"),
                    (1124, "Popup window")):
    ck("Appearance control %d reads the pack" % _cid,
       _Cw(14, _cid, "<<FALLBACK>>") == _want,
       repr(_Cw(14, _cid, "<<FALLBACK>>")))
_v1162 = _Cw(15, 1162, "x")
ck("the Exceptions mode combo's ITEMS are a list of [index, text] pairs",
   isinstance(_v1162, list)
   and [x[1] for x in _v1162] == ["Enabled for these programs:",
                                  "Disabled for these programs:"],
   repr(_v1162))
ck("Basics group 1046 resolves", _Cw(10, 1046, "x") == "General",
   repr(_Cw(10, 1046, "x")))

# --- the live window ------------------------------------------------------
try:
    import tkinter as tk
except Exception as exc:                       # pragma: no cover
    print("SKIP: this host's python has no tkinter (%s)" % exc)
    raise SystemExit(0)

from qtranslate import app as A  # noqa: E402

root = tk.Tk()
app = A.App(root)
root.update_idletasks()
root.update()
app.open_options()
root.update_idletasks()
root.update()

opts = next((w for w in root.winfo_children()
             if w.winfo_class() == "Toplevel"), None)
ck("the Options window opened", opts is not None)
if opts is None:
    raise SystemExit(1)

lb = next((c for c in opts.winfo_children()
           if c.winfo_class() == "Listbox"), None)
ck("the Options window has a nav list", lb is not None)

PAGES = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
         "Appearance", "Exceptions", "Advanced", "Updates"]
ck("the nav lists native's nine pages in native's order",
   [lb.get(i) for i in range(lb.size())] == PAGES,
   repr([lb.get(i) for i in range(lb.size())]))


def body_frame():
    """The page body: the LARGEST frame in the window (the button row
    is a frame too, and it is created first)."""
    best = None
    for c in opts.winfo_children():
        if c.winfo_class() != "Frame" or c is lb:
            continue
        if best is None or (c.winfo_width() * c.winfo_height() >
                            best.winfo_width() * best.winfo_height()):
            best = c
    return best


def show(page):
    lb.selection_clear(0, "end")
    lb.selection_set(PAGES.index(page))
    lb.event_generate("<<ListboxSelect>>")
    root.update_idletasks()
    root.update()
    return body_frame()


def walk(w, d=0):
    """(depth, class, text) for every widget under w."""
    out = []
    for c in w.winfo_children():
        txt = ""
        try:
            txt = str(c.cget("text"))
        except Exception:
            pass
        out.append((d, c.winfo_class(), txt, c))
        out += walk(c, d + 1)
    return out


def texts(frame, cls=None):
    return [t for (_d, cl, t, _c) in walk(frame)
            if (cls is None or cl == cls) and t]


def classes(frame):
    return [cl for (_d, cl, _t, _c) in walk(frame)]


# --- 2. Basics (DLG171): three group boxes --------------------------------
b = show("Basics")
ck("Basics has three group boxes", classes(b).count("Labelframe") == 3,
   repr(classes(b)))
ck("Basics' groups are General / Auto-detect languages / History",
   [t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"] ==
   ["General", "Auto-detect languages", "History"],
   repr([t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"]))
ck("Basics keeps Start with Windows", "Start with Windows" in texts(b))
ck("Basics keeps the three history flags",
   all(x in texts(b) for x in ("Enable history", "Clear history on exit",
                               "Expand items")))

# --- 3. Internet (DLG172): two group boxes --------------------------------
b = show("Internet")
ck("Internet has two group boxes", classes(b).count("Labelframe") == 2,
   repr(classes(b)))
ck("Internet's groups are Connection / Proxy",
   [t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"] ==
   ["Connection", "Proxy"],
   repr([t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"]))

# --- 4. Services (DLG173): ONE list, two groups, real services ------------
b = show("Services")
_tree = [c for (_d, cl, _t, c) in walk(b) if cl == "Treeview"]
ck("Services draws a tree", len(_tree) == 1, repr(classes(b)))
if _tree:
    tv = _tree[0]
    _groups = [tv.item(i, "text") for i in tv.get_children("")]
    ck("Services has the two native group headers",
       _groups == ["Translation", "Dictionary"], repr(_groups))
    _rows = []
    for g in tv.get_children(""):
        for it in tv.get_children(g):
            _rows.append(tv.item(it, "text"))
    ck("Services lists the nine native translation services",
       all(any(n in r for r in _rows)
           for n in ("Google", "Microsoft", "Promt", "Babylon", "Yandex",
                     "youdao", "Baidu", "Papago", "DeepL")),
       repr(_rows))
    ck("Services lists the native dictionary services",
       all(any(n in r for r in _rows)
           for n in ("Google Search", "WordReference",
                     "Babylon Dictionary", "Wikipedia")),
       repr(_rows))
    ck("the Services lists are NOT empty on a fresh config",
       len(_rows) >= 13, "%d rows" % len(_rows))
ck("Services has the two native dictionary buttons",
   "Add dictionary..." in texts(b) and "Remove dictionary" in texts(b),
   repr(texts(b)))

# --- 5. Languages (DLG174): the checklist + Check / Uncheck all ------------
b = show("Languages")
ck("Languages has a Check / Uncheck all button",
   "Check / Uncheck all" in texts(b), repr(texts(b)))
_canvas = [c for (_d, cl, _t, c) in walk(b) if cl == "Canvas"]
ck("Languages draws the checklist on a canvas", len(_canvas) == 1,
   repr(classes(b)))
if _canvas:
    cv = _canvas[0]
    _items = cv.find_all()
    _names = [cv.itemcget(i, "text") for i in _items
              if cv.type(i) == "text"]
    ck("the checklist holds native's 72 languages", len(_names) == 72,
       "%d names" % len(_names))
    ck("the checklist is alphabetical", _names == sorted(_names),
       repr(_names[:6]))
    ck("the checklist starts with Afrikaans and ends with Vietnamese",
       _names and _names[0] == "Afrikaans"
       and _names[-1] == "Vietnamese",
       repr((_names[:1], _names[-1:])) if _names else "empty")
    ck("the checklist has the 4 columns native draws",
       "Afrikaans" in _names and "Estonian" in _names
       and "Kannada" in _names and "Russian" in _names,
       repr(_names[:4]))
ck("Languages has no leftover 'Default languages' page",
   "Default languages" not in texts(b)
   and "Translate from:" not in texts(b), repr(texts(b)))

# --- 6. Appearance (DLG175): two group boxes, native's controls ----------
b = show("Appearance")
ck("Appearance has two group boxes", classes(b).count("Labelframe") == 2,
   repr(classes(b)))
ck("Appearance's groups are General / Popup window",
   [t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"] ==
   ["General", "Popup window"],
   repr([t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"]))
ck("Appearance keeps Enable window style in the General group",
   "Enable window style" in texts(b), repr(texts(b)))
ck("Appearance labels the transparency field natively",
   "Transparency (0 - 90):" in texts(b), repr(texts(b)))
ck("Appearance shows the 'seconds' unit", "seconds" in texts(b))
ck("Appearance shows the native theme sentinel",
   any(c.get() == "--- Default ---" for (_d, cl, _t, c) in walk(b)
       if cl == "TCombobox"), repr(texts(b)))
ck("Appearance draws three colour swatches",
   len([c for (_d, cl, _t, c) in walk(b)
        if cl == "Frame" and c.winfo_class() == "Frame"
        and c.winfo_height() <= 20 and c.winfo_width() <= 60]) >= 3,
   "the colour fields are not swatches")
ck("Appearance has the four native icon buttons",
   sorted(t for (_d, cl, t, _c) in walk(b) if cl == "Button") ==
   sorted(["\u25a4", "", "\u29c9", "b\u2090"]),
   repr([(cl, t) for (_d, cl, t, _c) in walk(b) if cl == "Button"]))

# --- 7. Exceptions (DLG176): a mode combo and ONE list -------------------
b = show("Exceptions")
_cbs = [c for (_d, cl, _t, c) in walk(b) if cl == "TCombobox"]
ck("Exceptions has the mode combo", len(_cbs) == 1, repr(classes(b)))
if _cbs:
    _vals = list(_cbs[0].cget("values"))
    ck("the mode combo holds the two native modes",
       _vals == ["Enabled for these programs:",
                 "Disabled for these programs:"], repr(_vals))
ck("Exceptions has ONE list, not two",
   len([c for (_d, cl, _t, c) in walk(b) if cl == "Listbox"]) == 1,
   repr(classes(b)))
ck("Exceptions has Add / Modify / Delete",
   all(x in texts(b) for x in ("Add", "Modify", "Delete")), repr(texts(b)))
ck("Exceptions keeps Enable smart detection",
   "Enable smart detection" in texts(b), repr(texts(b)))

# --- 8. Advanced (DLG185): three group boxes, four combos -----------------
b = show("Advanced")
ck("Advanced has three group boxes", classes(b).count("Labelframe") == 3,
   repr(classes(b)))
ck("Advanced's groups are Advanced / Mouse mode / API keys",
   [t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"] ==
   ["Advanced", "Mouse mode", "API keys"],
   repr([t for (_d, cl, t, _c) in walk(b) if cl == "Labelframe"]))
ck("Advanced has the four native ComboBoxes",
   len([c for (_d, cl, _t, c) in walk(b) if cl == "TCombobox"]) == 4,
   repr(classes(b)))
ck("Advanced has the OCR API key field", "OCR API key:" in texts(b))
ck("Advanced has no duplicated label",
   len(texts(b)) == len(set(texts(b))), repr(texts(b)))
ck("Advanced keeps the native radio labels",
   all(x in texts(b) for x in ("Enable GUI translation",
                               "Remove line breaks")),
   repr(texts(b)))

# --- 9. Updates (DLG205): the changelog area and both buttons ------------
b = show("Updates")
ck("Updates has a changelog area",
   len([c for (_d, cl, _t, c) in walk(b) if cl == "Text"]) == 1,
   repr(classes(b)))
ck("Updates has Check now and Install",
   "Check now" in texts(b) and "Install" in texts(b), repr(texts(b)))
ck("Updates keeps the auto-check flag",
   "Automatically check for updates" in texts(b), repr(texts(b)))

# --- 10. the window's button row ------------------------------------------
_btns = texts(opts)
ck("the Options window has OK / Cancel / Apply",
   all(x in _btns for x in ("OK", "Cancel", "Apply")), repr(_btns))

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        try:
            print("  -", f)
        except UnicodeEncodeError:
            print("  -", f.encode("ascii", "replace").decode("ascii"))
    raise SystemExit(1)
print("regress_options_pages_native: all checks ok (%d assertions)" % n[0])
