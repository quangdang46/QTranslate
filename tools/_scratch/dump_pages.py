"""Dump each Options page's widget tree as text, for comparison with the
native DLGs. Text beats pixels for a structural audit."""
import os, sys, time
sys.path.insert(0, "/Users/tranquangdang21/Projects/QTranslate")
import tkinter as tk
from qtranslate import app as A

root = tk.Tk()
app = A.App(root)
root.update_idletasks(); root.update()
app.open_options()
root.update_idletasks(); root.update()

opts = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"][0]
lb = [c for c in opts.winfo_children() if c.winfo_class() == "Listbox"][0]
body = None
for c in opts.winfo_children():
    if c.winfo_class() != "Frame" or c is lb:
        continue
    if body is None or (c.winfo_width() * c.winfo_height() >
                        body.winfo_width() * body.winfo_height()):
        body = c

def walk(w, d=0):
    out = []
    for c in w.winfo_children():
        cls = c.winfo_class()
        txt = ""
        try: txt = str(c.cget("text"))
        except Exception: pass
        vals = ""
        try:
            v = c.get()
            vals = (" =" + str(v)[:40]) if isinstance(v, str) else ""
        except Exception: pass
        out.append("  "*d + f"{cls:<14} {txt!r}{vals}")
        out += walk(c, d+1)
    return out

for i in range(lb.size()):
    page = lb.get(i)
    lb.selection_clear(0, "end"); lb.selection_set(i)
    lb.event_generate("<<ListboxSelect>>")
    root.update_idletasks(); root.update()
    print("="*70)
    print("PAGE", page)
    print("="*70)
    print("\n".join(walk(body)))
root.destroy()
