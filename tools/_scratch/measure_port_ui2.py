import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import tkinter as tk
from qtranslate import app as A

root = tk.Tk()
root.geometry("595x376")
app = A.App(root)
root.update_idletasks(); root.update()
root.deiconify(); root.lift(); root.update_idletasks(); root.update()

def geo(w):
    if w is None: return None
    return (w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height(), w.winfo_reqwidth(), w.winfo_reqheight())

print("root:", root.winfo_width(), "x", root.winfo_height(), " geometry:", root.geometry())
panes = getattr(app, "_panes", {}) or {}
for name in ("src", "mid", "bar", "svc"):
    print(f"  pane {name:6s}", geo(panes.get(name)))
for attr in ("src", "out", "aux", "tgt", "src_lang", "suggest", "svc_link"):
    print(f"  attr {attr:10s}", geo(getattr(app, attr, None)))
print("  strip buttons:")
for n, b in (getattr(app, "svc_btns", {}) or {}).items():
    print(f"    {n:12s}", geo(b))
# absolute positions
print()
print("ABSOLUTE positions (root-relative):")
def abs_geo(w):
    if w is None: return None
    x, y = w.winfo_rootx() - root.winfo_rootx(), w.winfo_rooty() - root.winfo_rooty()
    return (x, y, w.winfo_width(), w.winfo_height())
for name in ("src", "out", "aux", "tgt", "src_lang", "suggest"):
    print(f"  {attr:10s}", abs_geo(getattr(app, attr, None)))
print("  svc strip  ", abs_geo(panes.get("svc")))
for n, b in list((getattr(app, "svc_btns", {}) or {}).items())[:3]:
    print(f"    btn {n:10s}", abs_geo(b))
root.destroy()
