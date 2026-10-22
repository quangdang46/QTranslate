"""Regression: the main window's fidelity fixes, asserted on the live widgets.

Three real defects were found by rendering the port's main window on
macOS and comparing it with `docs/review/native_screens/2131.png`:

1. **The service strip's buttons were 230 pixels wide.** Tk reads a
   button's `width`/`height` as CHARACTERS for a text button and as PIXELS
   for an image button. The strip's icons were only ever loaded from
   `C:/Program Files (x86)/QTranslate/...`, so off Windows no image was
   set, the buttons fell back to text, and `width=22` became 22
   characters. The strip then needed 2334px inside a 587px window and six
   of the nine services were pushed off-screen entirely.
2. **The Translate button was cut off.** The tool row was packed left to
   right, so it overflowed a 516px window (native puts Translate at
   x 438..510; the port drew it at 481..497).
3. **The main window opened with a three-line stub** instead of native's
   help text, because `default_source_text()` read
   `C:/Program Files (x86)/QTranslate/Locales/English/help.txt` and the
   native's own help.txt was never bundled.

Every assertion here calls the real code and reads the real widget
geometry; none of them greps source text.
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
        fail.append(f"{name} -- {detail}")


# --- the bundled assets exist and are the right size ------------------------
ASSETS = os.path.join(ROOT, "qtranslate", "assets")
STRIP_ICONS = os.path.join(ASSETS, "service_icons")
UI_ICONS = os.path.join(ASSETS, "ui_icons")

STRIP_SERVICES = ("google", "microsoft", "promt", "babylon", "yandex",
                  "youdao", "baidu", "naver", "deepl")

ck("the service strip icons are bundled",
   os.path.isdir(STRIP_ICONS), STRIP_ICONS)
for svc in STRIP_SERVICES:
    path = os.path.join(STRIP_ICONS, svc + ".png")
    ck(f"{svc}: strip icon is bundled", os.path.isfile(path), path)

ck("the mic/headphone icons are bundled",
   os.path.isfile(os.path.join(UI_ICONS, "mic.png"))
   and os.path.isfile(os.path.join(UI_ICONS, "headphone.png")), UI_ICONS)

ck("the English help.txt is bundled",
   os.path.isfile(os.path.join(ASSETS, "locales", "English", "help.txt")))

# --- the locale packs load off Windows --------------------------------------
from qtranslate import locale as L  # noqa: E402

packs = L.list_locales()
ck("35 locale packs load without a Windows install", len(packs) == 35,
   str(len(packs)))
try:
    vi = L.load_pack("Vietnamese")
    ck("the Vietnamese pack loads and reports its own code",
       vi.get("LanguageCode") == "vi", repr(vi.get("LanguageCode"))[:60])
except Exception as exc:
    ck("the Vietnamese pack loads", False, repr(exc))

# --- the default source text is native's whole help text --------------------
import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402

root = tk.Tk()
root.withdraw()
app = A.App(root)
root.update_idletasks()
root.update()

text = app.default_source_text()
for marker in ("Global hotkeys", "Main window hotkeys",
               "There are three modes of translation by mouse selection",
               "Actions:"):
    ck(f"the default source text contains {marker!r}", marker in text,
       repr(text[:120]))
ck("the default source text is native's full help, not the 3-line stub",
   len(text.splitlines()) > 20, str(len(text.splitlines())))

# --- the service strip: every service present and pixel-sized --------------
strip = (getattr(app, "_panes", {}) or {}).get("svc")
ck("the service strip exists", strip is not None)
buttons = getattr(app, "svc_btns", {}) or {}
ck("all nine services are in the strip", len(buttons) == 9, str(sorted(buttons)))

strip_w = strip.winfo_reqwidth() if strip is not None else 0
window_w = root.winfo_width()
ck("the strip fits inside the window",
   strip_w <= window_w, f"strip needs {strip_w}px, window is {window_w}px")
for name, btn in buttons.items():
    w = btn.winfo_reqwidth()
    ck(f"{name}: the strip button is pixel-sized, not character-sized",
       w <= 24, f"requested width {w}px (a character-sized one would be ~230)")
    ck(f"{name}: the strip button has an icon, not a text fallback",
       str(btn.cget("image")) not in ("", "none"), str(btn.cget("image"))[:40])

# --- the tool row: the Translate button is fully visible --------------------
go = None
for child in root.winfo_children():
    for sub in child.winfo_children():
        if sub.winfo_class() == "Button" and "Translate" in str(sub.cget("text")):
            go = sub
ck("the Translate button exists", go is not None)
if go is not None:
    root.update_idletasks()
    x = go.winfo_rootx() - root.winfo_rootx()
    right = x + go.winfo_width()
    ck("the Translate button is fully inside the window",
       right <= window_w, f"right edge {right} > window width {window_w}")

# --- the source pane overlays use native's icons ----------------------------
overlay = [c for c in root.winfo_children() if c.winfo_class() == "Frame"]
found_imgs = 0
for frame in root.winfo_children():
    for sub in frame.winfo_children():
        if sub.winfo_class() == "Button" and str(sub.cget("image")) not in ("", "none"):
            found_imgs += 1
ck("the source pane overlays carry images (mic + headphone)",
   found_imgs >= 2, f"{found_imgs} image buttons found")

# --- the band structure matches native's seven bands ------------------------
# Native's capture (2131) measures: nav row, source pane, separator, tool
# row, RESULT pane, separator, service strip -- with the third pane
# (DLG129's 1018) COLLAPSED to zero height and no suggestion band at all.
from qtranslate.windows import _src_pane_px  # noqa: E402

kids = list(root.winfo_children())
ck("the main window has no empty suggestion band",
   not any(k.winfo_class() == "Label" and str(k.cget("text")) == ""
           and k.winfo_manager() == "pack" for k in kids),
   "an empty suggestion label is packed")

src = (getattr(app, "_panes", {}) or {}).get("src")
ck("the source pane is reachable", src is not None)
if src is not None:
    # The root is WITHDRAWN (so the suite never puts a window on the
    # user's desktop), and a widget inside an unmapped toplevel is itself
    # unmapped -- so `winfo_height()` reports 1 for every child,
    # whatever the code did. The requested height is the value the pane
    # will occupy once the window is shown, and for a frame whose
    # propagation is switched off it IS the allocated height.
    ck("the source pane is native's height",
       src.winfo_reqheight() == _src_pane_px(),
       f"{src.winfo_reqheight()}px, native's is {_src_pane_px()}px "
       f"(10.5 lines of the app's font)")
    # ...and it is the REQUESTED height only because the frame does not
    # take the size of its children. With propagation on, the Text's own
    # request would decide the pane's height and the check above would
    # pass for the wrong reason.
    ck("the source pane does not take its children's height",
       not src.pack_propagate(),
       "pack_propagate is on: the pane's height is the Text's, not "
       "native's 10.5 lines")

aux = (getattr(app, "_panes", {}) or {}).get("aux")
ck("the third pane (1018) exists", aux is not None)
if aux is not None:
    ck("the third pane is COLLAPSED while it is empty, like native's",
       aux.winfo_manager() != "pack",
       f"the third pane is packed ({aux.winfo_height()}px)")

# --- the source pane scrolls, like native's RichEdit -----------------------
# Native grows a scrollbar when the content overflows: the capture shows
# one on the SOURCE pane (whose help text is clipped) and none on the
# RESULT pane (whose single line fits).
_sbar = getattr(app, "_src_scroll", None)
ck("the source pane has a scrollbar", _sbar is not None)
if _sbar is not None:
    ck("the source pane's scrollbar is SHOWN (the help text overflows)",
       bool(_sbar.grid_info()),
       "the scrollbar is hidden although the content does not fit")
    ck("the source pane's scrollbar scrolls the source",
       _sbar.cget("command") != "",
       repr(_sbar.cget("command")))

# --- the pane toggles actually toggle ---------------------------------------
# `toggle_pane` reads `_panes["src"]` / `_panes["mid"]`; the builder used
# to REPLACE the whole dict, so both were None and Ctrl+F1/F2 did nothing.
# The toggle also WRITES the settings file, so it is pointed at a
# throwaway path first -- the live one is the user's.
import tempfile  # noqa: E402
from qtranslate import config as _CFG  # noqa: E402

_saved_path = _CFG.DEFAULT_PATH
_cfg_dir = tempfile.mkdtemp(prefix="qtranslate-cfg-")
_CFG.DEFAULT_PATH = os.path.join(_cfg_dir, "Options.json")
try:
    ck("the source pane is registered for the pane toggles",
       (getattr(app, "_panes", {}) or {}).get("src") is not None)
    ck("the result pane is registered for the pane toggles",
       (getattr(app, "_panes", {}) or {}).get("mid") is not None)
    _before = src.winfo_manager() if src is not None else ""
    app.toggle_pane("ShowTopPane", "src")
    root.update_idletasks()
    _after = src.winfo_manager() if src is not None else ""
    ck("the ShowTopPane toggle changes the source pane",
       _before != _after, f"{_before!r} -> {_after!r}")
    app.toggle_pane("ShowTopPane", "src")
    root.update_idletasks()
    ck("...and puts it back",
       src.winfo_manager() == _before if src is not None else False,
       repr(src.winfo_manager()) if src is not None else "no source pane")
finally:
    _CFG.DEFAULT_PATH = _saved_path
    try:
        os.remove(_CFG.DEFAULT_PATH)
    except Exception:
        pass
    try:
        os.rmdir(_cfg_dir)
    except Exception:
        pass

# --- the third pane (1018) shows only when it has a back-translation --------
# Native's capture shows that pane COLLAPSED to zero height; the port's
# third pane must therefore be packed only while it carries something.
_main = app._main
ck("the main window has a render() that fills the panes",
   callable(getattr(_main, "render", None)))
if callable(getattr(_main, "render", None)):
    _main.render("result", "back-translation")
    root.update_idletasks()
    _aux = (getattr(app, "_panes", {}) or {}).get("aux")
    ck("a back-translation SHOWS the third pane",
       _aux is not None and _aux.winfo_manager() == "pack",
       f"manager={_aux.winfo_manager() if _aux else None}")
    _main.render("result only")
    root.update_idletasks()
    ck("without a back-translation the third pane is hidden again",
       _aux is not None and _aux.winfo_manager() != "pack",
       f"manager={_aux.winfo_manager() if _aux else None}")

# --- the sash moves the source pane -----------------------------------------
# The source pane's height is the FRAME's (the Text is gridded with a
# weighted row), so the drag handler has to move the frame -- a sash that
# only set the Text's `-height` would move nothing while still writing
# the value to Options.json.
if src is not None:
    _h0 = src.winfo_height()
    app._set_src_height(_h0 + 40)
    root.update_idletasks()
    ck("the source pane's height can be changed (the sash moves it)",
       src.winfo_height() >= _h0 + 30,
       f"{_h0} -> {src.winfo_height()}")
    app._set_src_height(_h0)
    root.update_idletasks()

# --- the nav arrows and the menu are native's icon buttons -------------------
# Native's back/forward, its ':' menu and its 'New' button are BS_ICON
# buttons. As text they were 47px wide on macOS, where native's are 20.
_nav_buttons = []
for frame in root.winfo_children():
    for sub in frame.winfo_children():
        if sub.winfo_class() == "Button":
            _nav_buttons.append(sub)
_icons = [b for b in _nav_buttons
          if str(b.cget("image")) not in ("", "none")]
_text_arrows = [b for b in _nav_buttons
                if str(b.cget("text")) in ("◀", "▶", "⋮")]
ck("the nav arrows and the kebab carry native's own icons, not text",
   len(_icons) >= 4 and not _text_arrows,
   f"{len(_icons)} icon buttons, {_text_arrows} text arrows")
for _b in _icons[:4]:
    ck("an icon button is pixel-sized, not character-sized",
       _b.winfo_reqwidth() <= 24, str(_b.winfo_reqwidth()))

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_main_window_fidelity: all checks ok (%d assertions)" % n[0])
