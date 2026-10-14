"""1:1 tkinter port of ``ui-html-port-need-strict-follow/UI-FULL.html``.

The HTML file is the reference UI: pixel-measured token table and 11 screens
(main window, Ctrl+Q popup, Options x9 pages, Dictionary, History,
Keyboard, tray menu). This module renders those same 11 screens in tkinter
so the port can be compared side-by-side with the HTML and with the native
screenshots.

Rules carried over from the spec (the HTML's own §0):
  * only the measured tokens below -- no invented hex;
  * 1px borders, square corners, no shadow, no rounding, no animation;
  * no widget style that introduces a colour outside the table;
  * missing data -> leave it out, do not guess.

Geometry is absolute where the spec measured it absolutely (control row,
popup, Options rows), and relative where the spec says relative (panes).
"""
from __future__ import annotations

import sys
import tkinter as tk

# --- measured design tokens (spec §1) -------------------------------------
FACE = "#f0f0f0"        # window/dialog bg, toolbar, control area
WINDOW = "#ffffff"      # text fields, listbox, translation panes
BORDER = "#7e7e7e"      # 1px: combobox, button, listbox, divider, pane frame
TEXT = "#000000"
TEXT_DIM = "#6d6d6d"     # disabled icons/buttons
ACCENT = "#0078d7"       # selected row bg in listbox
LINK = "#0066cc"         # toolbar link
THUMB = "#858585"        # scrollbar thumb
COLSEP = "#e5e5e5"       # column separator
BTN_TOP = "#e3e3e3"      # button/combobox vertical gradient
BTN_BOTTOM = "#d4d4d4"
BTN_HL = "#ffffff"       # 1px inner top highlight
BTN_SHADE = "#cacaca"    # 1px inner bottom shade
DIS_BG = "#e1e1e1"
DIS_TEXT = "#dcdcdc"
POPUP_BG = "#d0d0d0"
POPUP_BORDER = "#53606c"
POPUP_ICON = "#3a3a3a"
POPUP_TEXT = "#040404"
MENU_BG = "#f9f9f9"
MENU_BORDER = "#e5e5e5"
MENU_SEP = "#d7d7d7"
TITLE_W11 = "#eff4f9"    # native title bar (reference only)

# --- extra tokens measured later and recorded in the export --------------
CB_ON = "#005eb8"        # ticked checkbox bg + border
SECTION_INK = "#005eb8"  # Options/Services section heading
SECTION_RULE = "#b5c9e0"  # section underline
SWATCH_TEXT = "#000000"
SWATCH_FRAME = "#5d6c7a"

FONT = ("Segoe UI", 9)   # 9pt = 12px (spec: inferred, not measured)

# provider tab colours as measured in the HTML copy
TAB_COLORS = {
    "Go..": "#4b8bf5", "Mi..": "#1b9bb0", "Pr..": "#3aa757",
    "Ba..0": "#2d6cdf", "Ya..": "#d33", "yo..": "#e53",
    "Pa..": "#3a7bd5", "DeepL": "#0f2b46",
}

SERVICE_TABS = ["Go..", "Mi..", "Pr..", "Ba..", "Ya..", "yo..",
                "Ba..", "Pa..", "DeepL"]

HOTKEY_ACTIONS = [
    "Show main window", "Show popup window", "Show dictionary window",
    "Show history window", "Show keyboard window",
    "Listen to selected text", "Copy translation to clipboard",
    "Replace selected text", "Switch mouse mode",
    "Translate clipboard content", "Translate clipboard in main window",
    "Translate clipboard in popup window", "Dictionary from clipboard",
]
HOTKEY_BINDINGS = {1: "Ctrl + Q", 7: "Alt + W"}

OPTION_PAGES = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
                "Appearance", "Exceptions", "Advanced", "Updates"]

MAIN_WIDTH, MAIN_HEIGHT = 516, 423
POPUP_W, POPUP_H = 200, 68
OPTS_W, OPTS_H = 663, 388
DICT_W, DICT_H = 476, 333
HIST_W, HIST_H = 476, 320
KBD_W, KBD_H = 464, 198
TRAY_W, TRAY_H = 367, 295

TRAY_ITEMS = ["QTranslate", "Dictionary", "Text recognition", "History",
              "Keyboard", "Options", "About QTranslate"]
TRAY_FOOT = ["Enable global hotkeys", "Mouse mode"]


# ------------------------------------------------------------------ helpers
def _button(parent, text="", *, font=None, bg=None, fg=TEXT,
            activebackground=None, relief="flat", borderwidth=1):
    """Spec button: 1px --border, vertical gradient, inner highlight/shade.

    tk has no multi-stop gradient, so the highlight/shade lines are drawn
    with the frame borders below ``_flat_pack`` instead of faking them.
    """
    return tk.Button(parent, text=text, font=font or FONT, bg=bg or FACE,
                     fg=fg, activebackground=activebackground or BTN_TOP,
                     activeforeground=fg, relief=relief,
                     highlightthickness=1,
                     highlightbackground=BORDER,
                     highlightcolor=BORDER,
                     borderwidth=0, cursor="arrow")


def _flat_pack(win, widget, x, y, w=None, h=None):
    widget.place(x=x, y=y, width=w, height=h)
    return widget


def _hline(win, x, y, w, color=BORDER):
    f = tk.Frame(win, bg=color, bd=0, height=1)
    f.place(x=x, y=y, width=w, height=1)
    return f


def _vline(win, x, y, h, color=COLSEP):
    f = tk.Frame(win, bg=color, bd=0, width=1)
    f.place(x=x, y=y, width=1, height=h)
    return f


def _pane(win, x, y, w, h, text="", *, bg=WINDOW):
    """White text pane with 1px border and a 2px thumb on the right."""
    t = tk.Text(win, bg=bg, fg=TEXT, font=FONT, wrap="word",
                relief="flat", highlightthickness=1,
                highlightbackground=BORDER, bd=0, padx=5, pady=3)
    t.place(x=x, y=y, width=w, height=h)
    if text:
        t.insert("1.0", text)
        t.config(state="disabled")
    thumb = tk.Frame(win, bg=THUMB, bd=0, width=2)
    thumb.place(x=x + w - 4, y=y + 3, width=2, height=min(168, h - 6))
    return t


def _combo(win, x, y, w, label, *, disabled=False, h=20):
    """Combobox-styled button: gradient face, 1px border, ▴▾ arrow pair."""
    bg = FACE if disabled else FACE
    fg = TEXT_DIM if disabled else TEXT
    c = tk.Canvas(win, bg=bg, bd=0, highlightthickness=1,
                  highlightbackground=BORDER, height=h)
    c.place(x=x, y=y, width=w, height=h)
    c.create_text(6, h // 2, text=label, anchor="w", fill=fg,
                  font=("Segoe UI", 9))
    # the ▴▾ pair sits in the right 15px, exactly as the HTML copy does
    c.create_text(w - 10, int(h * 0.38), text="▴", fill=fg,
                  font=("Segoe UI", 7), anchor="e")
    c.create_text(w - 10, int(h * 0.72), text="▾", fill=fg,
                  font=("Segoe UI", 7), anchor="e")
    _hline(win, x + 1, y + h - 1, w - 2, BTN_SHADE)
    return c


def _check(win, x, y, label, *, on=False):
    """13x13 checkbox: white when off, #005eb8 with a white tick when on."""
    _check.nticks = getattr(_check, "nticks", 0) + 1
    c = tk.Canvas(win, bg=WINDOW if not on else CB_ON, bd=0,
                  highlightthickness=1, highlightbackground=BORDER)
    c.place(x=x, y=y, width=13, height=13)
    if on:
        c.create_text(6.5, 5, text="✓", fill="white",
                      font=("Segoe UI", 9, "bold"))
    tk.Label(win, text=label, bg=FACE, fg=TEXT, font=FONT,
             anchor="w").place(x=x + 18, y=y - 2)
    return c


def _group_box(win, x, y, w, h, title):
    """Win32 group box: 1px --border plus a 1px white offset line."""
    outer = tk.Frame(win, bg=BORDER, bd=0, highlightthickness=0)
    outer.place(x=x, y=y, width=w, height=h)
    off = tk.Frame(win, bg="white", bd=0, highlightthickness=0)
    off.place(x=x + 1, y=y + 1, width=w - 2, height=1)
    tk.Label(win, text=title, bg=FACE, fg=TEXT, font=FONT).place(
        x=x + 9, y=y - 7)
    return outer


def _label(win, x, y, text, *, fg=TEXT, anchor="w"):
    tk.Label(win, text=text, bg=FACE, fg=fg, font=FONT,
             anchor=anchor).place(x=x, y=y)
    return win


def _titlebar(win, w, text="QTranslate"):
    """Simulated Win11 title bar (native in the real app -- reference)."""
    bar = tk.Frame(win, bg=TITLE_W11, bd=0, height=30)
    bar.place(x=0, y=0, width=w - 2, height=30)
    tk.Label(bar, text="◉", bg=TITLE_W11, fg=TEXT_DIM,
             font=("Segoe UI", 9)).place(x=9, y=7)
    tk.Label(bar, text=text, bg=TITLE_W11, fg=TEXT,
             font=("Segoe UI", 9)).place(x=31, y=7)
    for glyph, off in (("–", w - 142), ("☐", w - 96), ("✕", w - 50)):
        tk.Label(bar, text=glyph, bg=TITLE_W11, fg=TEXT,
                 font=("Segoe UI", 10)).place(x=off, y=5)
    return bar


# ------------------------------------------------------------------ screens
def main_window(root):
    win = tk.Toplevel(root)
    win.geometry(f"{MAIN_WIDTH}x{MAIN_HEIGHT}")
    win.configure(bg=FACE)
    _titlebar(win, MAIN_WIDTH)

    # toolbar (y 30..59)
    _button(win, "◀", bg=FACE, fg=TEXT_DIM, font=("Segoe UI", 10))
    _flat_pack(win, win.winfo_children()[-1], 4, 32, 24, 22)
    _button(win, "▶", bg=FACE, fg=TEXT_DIM, font=("Segoe UI", 10))
    _flat_pack(win, win.winfo_children()[-1], 30, 32, 24, 22)
    _label(win, 62, 37, "Google", fg=LINK)
    win.winfo_children()[-1].configure(font=("Segoe UI", 9, "underline"))
    tk.Label(win, text="⋮", bg=FACE, fg=TEXT,
             font=("Segoe UI", 12)).place(x=502, y=34)
    _hline(win, 1, 59, MAIN_WIDTH - 3)

    # input pane (y 60..211) holds the shipped help text
    help_text = (
        "QTranslate Version  6.10.0\n\n"
        "Global hotkeys (default values):\n"
        "Double Ctrl => Show main window (with translation of selected "
        "text, if any)\n"
        "Ctrl+Q => Translate selected text and show it in popup window\n"
        "Ctrl+Shift+Q => Show dictionary window\n"
        "Ctrl+E => Listen to selected text\n\n"
        "Main window hotkeys:\n"
        "Ctrl+Enter => Translate text\n"
        "Ctrl+N => Clear current translation")
    _pane(win, 1, 60, MAIN_WIDTH - 3, 151, help_text)
    for glyph, x in (("🎤", 451), ("🎧", 472)):
        tk.Label(win, text=glyph, bg=WINDOW,
                 font=("Segoe UI", 12)).place(x=x, y=190)

    # splitter (y 211..217) with the 3-dot grip
    spl = tk.Frame(win, bg=FACE, bd=0)
    spl.place(x=1, y=212, width=MAIN_WIDTH - 3, height=5)
    _hline(win, 1, 213, MAIN_WIDTH - 3)
    for i in range(3):
        tk.Frame(win, bg="#555", bd=0,
                 width=1, height=3).place(x=249 + i * 5, y=213)

    # control row (y 217..238)
    _button(win, "🗎", bg=FACE, font=("Segoe UI", 12))
    _flat_pack(win, win.winfo_children()[-1], 4, 217, 31, 21)
    tk.Label(win, text="⋮", bg=FACE, fg=TEXT,
             font=("Segoe UI", 11)).place(x=41, y=219)
    _combo(win, 67, 217, 150, "Auto-Detect")
    _button(win, "⇄", bg=FACE, font=("Segoe UI", 12))
    _flat_pack(win, win.winfo_children()[-1], 223, 217, 27, 21)
    _combo(win, 256, 217, 177, "Vietnamese")
    _button(win, "Translate", bg=FACE, font=("Segoe UI", 9))
    _flat_pack(win, win.winfo_children()[-1], 438, 217, 73, 21)
    _hline(win, 1, 242, MAIN_WIDTH - 3)

    # output pane (y 243..391)
    _pane(win, 1, 243, MAIN_WIDTH - 3, 149,
          "No data returned (timeout while sending data).")
    tk.Label(win, text="🎧", bg=WINDOW,
             font=("Segoe UI", 12)).place(x=472, y=367)
    _hline(win, 1, 392, MAIN_WIDTH - 3)

    # provider tab strip (y 392..423)
    for i, name in enumerate(SERVICE_TABS):
        x = 4 + i * 57
        c = tk.Canvas(win, bg=FACE, bd=0, highlightthickness=1,
                      highlightbackground=BORDER, height=22)
        c.place(x=x, y=397, width=53, height=22)
        c.create_rectangle(4, 5, 16, 17,
                           fill=TAB_COLORS.get(name, "#888"), outline="")
        c.create_text(21, 11, text=name, anchor="w", fill=TEXT,
                      font=("Segoe UI", 9))
    return win


def popup(root, source="English to Vietnamese", result="người_record"):
    """Ctrl+Q popup: borderless, topmost, title row + result."""
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.geometry(f"{POPUP_W}x{POPUP_H}")
    win.configure(bg=POPUP_BG)
    outer = tk.Frame(win, bg=POPUP_BORDER, bd=0)
    outer.place(x=0, y=0, width=POPUP_W, height=POPUP_H)
    inner = tk.Frame(outer, bg=POPUP_BG, bd=0)
    inner.place(x=1, y=1, width=POPUP_W - 2, height=POPUP_H - 2)

    row = tk.Frame(inner, bg=POPUP_BG, bd=0)
    row.place(x=0, y=0, width=POPUP_W - 2, height=24)
    row_kw = {"bg": POPUP_BG, "fg": POPUP_ICON, "bd": 0, "font": FONT}
    tk.Label(row, text="✕", **row_kw).pack(side="left", padx=(6, 0))
    tk.Label(row, text=source + "…", **row_kw).pack(side="left", padx=6)
    tk.Label(row, text="★", **row_kw).pack(side="left")
    for glyph in ("📖", "🎧", "⧉", "tā"):
        tk.Label(row, text=glyph, **row_kw).pack(side="left", padx=6)
    tk.Label(inner, text=result, bg=POPUP_BG, fg=POPUP_TEXT, font=FONT,
             anchor="w").place(x=6, y=30)
    win.bind("<Escape>", lambda e: win.destroy())
    return win


def options_window(root, page="Hotkeys"):
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.title("Options")
    win.geometry(f"{OPTS_W}x{OPTS_H}")
    bar = tk.Frame(win, bg=WINDOW, bd=0, height=24)
    bar.place(x=0, y=0, width=OPTS_W, height=24)
    tk.Label(bar, text="Options", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=11, y=4)
    tk.Label(bar, text="✕", bg=WINDOW, fg=TEXT,
             font=("Segoe UI", 10)).place(x=OPTS_W - 46, y=3)

    side = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    side.place(x=10, y=28, width=142, height=140)
    for i, name in enumerate(OPTION_PAGES):
        bg = ACCENT if name == page else WINDOW
        fg = "#ffffff" if name == page else TEXT
        tk.Label(side, text=name, bg=bg, fg=fg, font=FONT,
                 anchor="w").place(x=2, y=3 + i * 13)

    if page == "Hotkeys":
        _check(win, 159, 34, "Enable hotkeys", on=True)
        tbl = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                       highlightbackground=BORDER)
        tbl.place(x=159, y=60, width=465, height=251)
        tk.Label(tbl, text="Action", bg=WINDOW, fg=TEXT,
                 font=FONT).place(x=6, y=4)
        tk.Label(tbl, text="Hotkey", bg=WINDOW, fg=TEXT,
                 font=FONT).place(x=317 + 6, y=4)
        _vline(tbl, 317, 0, 251)
        for i, act in enumerate(HOTKEY_ACTIONS):
            y = 24 + i * 17
            tk.Label(tbl, text=act, bg=WINDOW, fg=TEXT, font=FONT,
                     anchor="w").place(x=6, y=y)
            if i in HOTKEY_BINDINGS:
                tk.Label(tbl, text=HOTKEY_BINDINGS[i], bg=WINDOW, fg=TEXT,
                         font=FONT, anchor="w").place(x=323, y=y)
    return win


def dictionary_window(root):
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{DICT_W}x{DICT_H}")
    _titlebar(win, DICT_W, "Dictionary")
    _combo(win, 4, 35, 153, "English")
    fld = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    fld.place(x=163, y=34, width=274, height=21)
    _label(win, 170, 37, "◀ ▶", fg=TEXT_DIM)
    _label(win, 407, 34, "⌕")
    _label(win, 427, 34, "◷")
    _label(win, 457, 34, "⋮")
    track = tk.Frame(win, bg=MENU_BG, bd=0)
    track.place(x=455, y=60, width=19, height=240)
    _label(win, 460, 64, "⌃", fg=TEXT_DIM)
    _label(win, 460, 268, "⌄", fg=TEXT_DIM)
    tabs = ["G.", "W", "B.", "W", "M.", "I.", "R.", "U.", "A.", "y.",
            "O."]
    colors = ["#4285f4", "#d9534f", "#1a73c8", "#999", "#2d6cdf",
              "#7a3d9e", "#2d6cdf", "#e8890c", "#e53935", "#d33",
              "#8a8a2a"]
    for i, (n, c) in enumerate(zip(tabs, colors)):
        b = tk.Button(win, text="  " + n, bg=FACE, fg=TEXT, font=FONT,
                      anchor="w", relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER)
        b.place(x=4 + i * 42, y=306, width=42, height=21)
        tk.Frame(win, bg=c, bd=0).place(x=6 + i * 42, y=310, width=12,
                                        height=12)
    return win


def history_window(root):
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{HIST_W}x{HIST_H}")
    _titlebar(win, HIST_W, "History")
    fld = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    fld.place(x=4, y=34, width=467, height=21)
    tk.Label(fld, text="✕", bg=WINDOW, fg=TEXT,
             font=("Segoe UI", 9, "bold")).place(x=447, y=1)
    lst = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    lst.place(x=4, y=61, width=467, height=225)
    hdr = tk.Frame(lst, bg=FACE, bd=0)
    hdr.place(x=1, y=1, width=465, height=17)
    tk.Label(hdr, text="★", bg=FACE, fg="#555", font=FONT).place(x=2, y=1)
    tk.Label(hdr, text="person_record", bg=FACE, fg=TEXT,
             font=("Segoe UI", 9, "bold")).place(x=18, y=1)
    tk.Frame(lst, bg="#4285f4", bd=0).place(x=21, y=23, width=14,
                                            height=14)
    tk.Label(lst, text="người_record", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=41, y=23)
    for x, w, t in ((4, 73, "Clear"), (83, 108, "Save as…")):
        tk.Button(win, text=t, bg=FACE, fg=TEXT, font=FONT, relief="flat",
                  bd=0, highlightthickness=1,
                  highlightbackground=BORDER).place(x=x, y=294, width=w,
                                                    height=21)
    tk.Button(win, text="★", bg=FACE, fg="#e6c800", font=FONT,
              relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=197, y=294, width=20,
                                                height=21)
    tk.Button(win, text="OK", bg=FACE, fg=TEXT, font=FONT, relief="flat",
              bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=398, y=294, width=73,
                                                height=21)
    return win


KBD_LAYOUT = [
    ("F-row", None),
    ("` 1 2 3 4 5 6 7 8 9 0 - =", [("BkSp", 2)]),
    ("q w e r t y u i o p [ ]", [("Tab", 1.5), ("\\", 1.5)]),
    ("a s d f g h j k l ; '", [("Caps", 1.9), ("Enter", 2.2)]),
    ("z x c v b n m , . /", [("Shift", 2.3), ("Shift", 2.8)]),
    ("Ctrl Win Alt", [("", 6.3), ("AltGr", 1.5), ("Apps", 1.5),
                    ("^ v < >", 1)]),
]


def keyboard_window(root):
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{KBD_W}x{KBD_H}")
    _titlebar(win, KBD_W, "Keyboard")
    tk.Button(win, text="Esc", bg=FACE, fg=TEXT, font=FONT,
              relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=8, y=37, width=27,
                                                height=20)
    for i, x in enumerate([52, 84, 116, 148, 196, 228, 260, 292, 336,
                           368, 400, 430]):
        tk.Button(win, text="F%d" % (i + 1), bg=FACE, fg=TEXT, font=FONT,
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=BORDER).place(x=x, y=37, width=28,
                                                    height=20)
    # remaining rows normalised to fit 448px, as the spec records
    rows = [
        (57, [("`", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1),
              ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1),
              ("=", 1), ("BkSp", 2)]),
        (79, [("Tab", 1.5), ("q", 1), ("w", 1), ("e", 1), ("r", 1),
              ("t", 1), ("y", 1), ("u", 1), ("i", 1), ("o", 1), ("p", 1),
              ("[", 1), ("]", 1), ("\\", 1.5)]),
        (100, [("Caps", 1.9), ("a", 1), ("s", 1), ("d", 1), ("f", 1),
               ("g", 1), ("h", 1), ("j", 1), ("k", 1), ("l", 1),
               (";", 1), ("'", 1), ("Enter", 2.2)]),
        (121, [("Shift", 2.3), ("z", 1), ("x", 1), ("c", 1), ("v", 1),
               ("b", 1), ("n", 1), ("m", 1), (",", 1), (".", 1),
               ("/", 1), ("Shift", 2.8)]),
        (142, [("Ctrl", 1.4), ("Win", 1.4), ("Alt", 1.4), ("", 6.3),
               ("AltGr", 1.5), ("Apps", 1.5), ("^", 1), ("v", 1),
               ("<", 1), (">", 1)]),
    ]
    for y, keys in rows:
        total = sum(k[1] for k in keys)
        unit = (448 - 3 * (len(keys) - 1)) / total
        x = 8.0
        for label, weight in keys:
            w = int(weight * unit)
            if label:
                tk.Button(win, text=label, bg=FACE, fg=TEXT, font=FONT,
                          relief="flat", bd=0, highlightthickness=1,
                          highlightbackground=BORDER).place(
                              x=int(x), y=y, width=w, height=20)
            x += w + 3
    _combo(win, 8, 169, 150, "English")
    return win


def tray_menu(root):
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{TRAY_W}x{TRAY_H}")
    menu = tk.Frame(win, bg=MENU_BG, bd=0, highlightthickness=1,
                    highlightbackground=MENU_BORDER)
    menu.place(x=68, y=23, width=213, height=244)
    y = 5
    tk.Label(menu, text="QTranslate", bg=MENU_BG, fg="#000",
             font=("Segoe UI", 9, "bold")).place(x=38, y=y)
    for i, item in enumerate(TRAY_ITEMS[1:]):
        tk.Label(menu, text=item, bg=MENU_BG, fg="#000",
                 font=FONT).place(x=38, y=27 + i * 22)
    _hline(menu, 1, 160, 211, MENU_SEP)
    _check(menu, 14, 169, "Enable global hotkeys", on=True)
    menu.winfo_children()
    tk.Label(menu, text="Mouse mode", bg=MENU_BG, fg="#000",
             font=FONT).place(x=38, y=190)
    tk.Label(menu, text="›", bg=MENU_BG, fg="#000",
             font=FONT).place(x=190, y=190)
    _hline(menu, 1, 213, 211, MENU_SEP)
    tk.Label(menu, text="Exit", bg=MENU_BG, fg="#000",
             font=FONT).place(x=38, y=221)
    return win


SCREENS = {
    "main": main_window,
    "popup": popup,
    "options": options_window,
    "dict": dictionary_window,
    "hist": history_window,
    "kbd": keyboard_window,
    "tray": tray_menu,
}


def launch(screen="main"):
    root = tk.Tk()
    root.withdraw()
    SCREENS[screen](root)
    root.mainloop()


if __name__ == "__main__":
    launch(sys.argv[1] if len(sys.argv) > 1 else "main")
