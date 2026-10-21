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

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_main_window_fidelity: all checks ok (%d assertions)" % n[0])
