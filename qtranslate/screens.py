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

# Native font, resolved by measurement against the spec + RE:
#   * the spec CSS says `font:12px/15px "Segoe UI"` (.win) and
#     `.pane.top{line-height:14px}`;
#   * the 11-line help block in the 151px .pane.top does NOT fit at a 15px
#     advance (11 x 15 = 165 > 151) -- tk's Text reports exactly that 15px
#     height for Segoe UI **9**, which is why the port clipped the last
#     line. It fits at a 13px advance (11 x 13 = 143 <= 151), which is
#     what "Segoe UI 8" / "MS Shell Dlg 8" measure.
#   * this matches the RE finding for G9 in docs/RE_COVERAGE_CHECKLIST.md:
#     native DLG129 carries `MS Shell Dlg` **8pt** (an earlier "Tahoma 9"
#     claim was withdrawn there).
# The old `("Segoe UI", 9)` was the spec's "9pt = 12px (inferred, NOT
# measured)" guess -- the guess is now disproven by the clip it caused.
FONT = ("Segoe UI", 8)

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

# Options/Services page rows (measured from the reference copy)
SERVICES_TRANSLATE = [
    ("Google", "#4285f4"), ("Microsoft", "#f5a623"),
    ("Promt", "#2bb673"), ("Babylon", "#1a73c8"),
    ("Yandex", "#e53935"), ("youdao", "#d32f2f"),
    ("Baidu", "#2d6cdf"), ("Papago", "#1dc078"),
    ("DeepL", "#0f2b46"),
]
SERVICES_DICTIONARY = [
    ("Google Search", "#4285f4"), ("WordReference", "#d9534f"),
    ("Babylon Dictionary", "#1a73c8"), ("Wikipedia", "#fff"),
]

# Options/Languages page: 4 columns x 18 rows, all ticked (measured)
# Native's Options -> Languages checklist. The DATA lives in
# `qtranslate/config.py` now, because the live Options window (DLG174)
# needs it too; `screens.py` stays the standalone reference module and
# must not be depended on by production code.
from qtranslate.config import LANGUAGE_COLUMNS  # noqa: E402,F401

# Options/Exceptions page rows (measured)
EXCEPTIONS_ROWS = [
    ("* All Programs *", "SysListView32"),
    ("* All Programs *", "SysTreeView32"),
    ("* All Programs *", "ListBox"),
    ("* All Programs *", "ScrollBar"),
    ("* All Programs *", "ComboBox"),
    ("* All Programs *", "msctls_hotkey32"),
    ("* All Programs *", "ConsoleWindowClass"),
    ("mstsc.exe", "* All Windows *"),
]

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
def _btn(win, x, y, w, text, *, h=21, bg=FACE, fg=TEXT, font=None,
         disabled=False):
    """Spec button as a bordered face: outer 1px --border, inner face with
    the 1px highlight on top and shade at the bottom, as measured."""
    face = DIS_BG if disabled else bg
    outer = tk.Frame(win, bg=BORDER, bd=0, highlightthickness=0)
    outer.place(x=x, y=y, width=w, height=h)
    inner = tk.Frame(outer, bg=face, bd=0, highlightthickness=0)
    inner.place(x=1, y=1, width=max(1, w - 2), height=max(1, h - 2))
    hl = tk.Frame(inner, bg=BTN_HL, bd=0, highlightthickness=0)
    hl.place(x=0, y=0, width=w - 2, height=1)
    sh = tk.Frame(inner, bg=BTN_SHADE, bd=0, highlightthickness=0)
    sh.place(x=0, y=h - 3, width=w - 2, height=1)
    b = tk.Button(inner, text=text, font=font or FONT,
                  bg=face, fg=DIS_TEXT if disabled else fg,
                  activebackground=BTN_TOP, activeforeground=fg,
                  relief="flat", bd=0, highlightthickness=0,
                  cursor="arrow")
    b.place(x=0, y=1, width=w - 2, height=h - 4)
    return b


def _bordered(win, x, y, w, h, *, inner_bg=WINDOW, outer_bg=BORDER):
    """The 1px border the spec measures, drawn the way tk can actually
    render it: an outer frame filled with --border and an inner frame
    over it, inset 1px. ``highlightthickness`` on a bd=0 widget does not
    paint reliably here (the user's "where's the border?" report).

    Returns the inner frame to pack children into.
    """
    outer = tk.Frame(win, bg=outer_bg, bd=0, highlightthickness=0)
    outer.place(x=x, y=y, width=w, height=h)
    inner = tk.Frame(outer, bg=inner_bg, bd=0, highlightthickness=0)
    inner.place(x=1, y=1, width=max(1, w - 2), height=max(1, h - 2))
    return inner


def _hline(win, x, y, w, color=BORDER):
    f = tk.Frame(win, bg=color, bd=0, height=1)
    f.place(x=x, y=y, width=w, height=1)
    return f


def _vline(win, x, y, h, color=COLSEP):
    f = tk.Frame(win, bg=color, bd=0, width=1)
    f.place(x=x, y=y, width=1, height=h)
    return f


def _pane(win, x, y, w, h, text="", *, bg=WINDOW):
    """White text pane with a real 1px border and a 2px thumb on the right.

    Line-height comes from ``FONT`` (8pt, 13px advance) -- see the note
    there: the module used to claim Segoe UI 9, whose 15px advance
    overflowed the spec's 151px pane and clipped the last help line.
    """
    inner = _bordered(win, x, y, w, h, inner_bg=bg)
    t = tk.Text(inner, bg=bg, fg=TEXT, font=FONT, wrap="word",
                relief="flat", highlightthickness=0, bd=0, padx=5, pady=3)
    t.place(x=0, y=0, width=w - 2, height=h - 2)
    if text:
        t.insert("1.0", text)
        t.config(state="disabled")
    thumb = tk.Frame(inner, bg=THUMB, bd=0, width=2, highlightthickness=0)
    thumb.place(x=w - 6, y=3, width=2, height=min(168, h - 6))
    return t


def _combo(win, x, y, w, label, *, disabled=False, h=20):
    """Combobox-styled button: real 1px border, face, ▴▾ arrow pair."""
    face = FACE
    fg = TEXT_DIM if disabled else TEXT
    outer = tk.Frame(win, bg=TEXT_DIM if disabled else BORDER, bd=0,
                     highlightthickness=0)
    outer.place(x=x, y=y, width=w, height=h)
    inner = tk.Frame(outer, bg=face, bd=0, highlightthickness=0)
    inner.place(x=1, y=1, width=max(1, w - 2), height=max(1, h - 2))
    hl = tk.Frame(inner, bg=BTN_HL, bd=0, highlightthickness=0)
    hl.place(x=0, y=0, width=w - 2, height=1)
    sh = tk.Frame(inner, bg=BTN_SHADE, bd=0, highlightthickness=0)
    sh.place(x=0, y=h - 3, width=w - 2, height=1)
    tk.Label(inner, text=label, bg=face, fg=fg, font=FONT,
             anchor="w").place(x=5, y=(h - 4) // 2)
    # the ▴▾ pair sits in the right 15px, exactly as the HTML copy does
    tk.Label(inner, text="▴", bg=face, fg=fg,
             font=("Segoe UI", 7)).place(x=w - 15, y=1)
    tk.Label(inner, text="▾", bg=face, fg=fg,
             font=("Segoe UI", 7)).place(x=w - 15, y=(h - 4) // 2 + 1)
    return inner


def _check(win, x, y, label, *, on=False):
    """13x13 checkbox: white when off, #005eb8 with a white tick when on."""
    outer = tk.Frame(win, bg=CB_ON if on else BORDER, bd=0,
                     highlightthickness=0)
    outer.place(x=x, y=y, width=13, height=13)
    inner = tk.Frame(outer, bg=CB_ON if on else WINDOW, bd=0,
                     highlightthickness=0)
    inner.place(x=1, y=1, width=11, height=11)
    if on:
        tk.Label(inner, text="✓", bg=CB_ON, fg="#ffffff",
                 font=("Segoe UI", 9, "bold")).place(x=1, y=-3)
    tk.Label(win, text=label, bg=FACE, fg=TEXT, font=FONT,
             anchor="w").place(x=x + 18, y=y - 2)
    return inner


def _group_box(win, x, y, w, h, title):
    """Fixed."""
    for _ex, _ey, _ew, _eh in ((x, y, w, 1), (x, y + h - 1, w, 1),
                               (x, y, 1, h), (x + w - 1, y, 1, h)):
        tk.Frame(win, bg=BORDER, bd=0, highlightthickness=0).place(
            x=_ex, y=_ey, width=_ew, height=_eh)
    tk.Label(win, text=title, bg=FACE, fg=TEXT, font=FONT).place(
        x=x + 9, y=y - 7)
    return None

def _label(win, x, y, text, *, fg=TEXT, anchor="w"):
    tk.Label(win, text=text, bg=FACE, fg=fg, font=FONT,
             anchor=anchor).place(x=x, y=y)
    return win


def _titlebar(win, w, text="QTranslate"):
    """Sets the window title and lets tkinter draw its OWN native Win11
    title bar -- do NOT also paint one here. An earlier version drew a
    fake bar (icon + text + min/max/close glyphs) inside the client area
    on top of the real OS-drawn one, producing two title bars stacked
    (the user's "bạn copy cả header ... duplicate giao diện" report).
    The real app never draws its own title bar either.
    """
    win.title(text)
    return None


# ------------------------------------------------------------------ screens
def main_window(root):
    # The spec's 516x423 is the FULL window including the native title
    # bar. tkinter's geometry/place origin is the client area only (the
    # title bar is OS chrome tkinter doesn't draw), so the client area is
    # 30px shorter than the spec figure -- there is no fake title bar
    # here any more (see _titlebar), just win.title().
    h = MAIN_HEIGHT - 30
    win = tk.Toplevel(root)
    win.geometry(f"{MAIN_WIDTH}x{h}")
    win.configure(bg=FACE)
    _titlebar(win, MAIN_WIDTH)

    # toolbar (y 0..29) -- native 2131.png: the back/forward glyphs sit
    # flush against the toolbar face with NO button border (only the
    # service tabs at the bottom and the combo/Translate controls get
    # the bordered-button treatment).
    tk.Button(win, text="◀", bg=FACE, fg=TEXT_DIM, font=("Segoe UI", 10),
              relief="flat", bd=0, highlightthickness=0,
              activebackground=FACE, cursor="arrow").place(
                  x=4, y=2, width=24, height=22)
    tk.Button(win, text="▶", bg=FACE, fg=TEXT_DIM, font=("Segoe UI", 10),
              relief="flat", bd=0, highlightthickness=0,
              activebackground=FACE, cursor="arrow").place(
                  x=30, y=2, width=24, height=22)
    _label(win, 62, 7, "Google", fg=LINK)
    win.winfo_children()[-1].configure(font=("Segoe UI", 9, "underline"))
    tk.Label(win, text="⋮", bg=FACE, fg=TEXT,
             font=("Segoe UI", 12)).place(x=502, y=4)
    _hline(win, 1, 29, MAIN_WIDTH - 3)

    # input pane (spec .pane.top: top 60px, height 151px) holds the
    # shipped help text
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
    _pane(win, 1, 30, MAIN_WIDTH - 3, 151, help_text)
    for glyph, x in (("🎤", 451), ("🎧", 472)):
        tk.Label(win, text=glyph, bg=WINDOW,
                 font=("Segoe UI", 12)).place(x=x, y=160)

    # splitter (spec .spl: y 212..217) -- TWO stacked 1px --border lines
    # (::before top:1px, ::after top:2px) plus the 3-dot grip at x249.
    # A native low-res screenshot suggests one plain line, but the spec is
    # the authority here and it measures the double line + dots, so this
    # restores them.
    spl = tk.Frame(win, bg=FACE, bd=0)
    spl.place(x=1, y=212, width=MAIN_WIDTH - 3, height=5)
    _hline(win, 1, 213, MAIN_WIDTH - 3)
    _hline(win, 1, 214, MAIN_WIDTH - 3)
    for i in range(3):
        tk.Frame(win, bg="#555", bd=0,
                 width=1, height=3).place(x=249 + i * 5, y=213)

    # control row (spec .ctl: top 217px)
    _btn(win, 4, 217, 31, "🗎", font=("Segoe UI", 12))
    tk.Label(win, text="⋮", bg=FACE, fg=TEXT,
             font=("Segoe UI", 11)).place(x=41, y=219)
    _combo(win, 67, 217, 150, "Auto-Detect")
    _btn(win, 223, 217, 27, "⇄", font=("Segoe UI", 12))
    _combo(win, 256, 217, 177, "Vietnamese")
    _btn(win, 438, 217, 73, "Translate", font=("Segoe UI", 9))
    _hline(win, 1, 242, MAIN_WIDTH - 3)

    # output pane (spec .pane.bot: top 243px, height 149px)
    _pane(win, 1, 243, MAIN_WIDTH - 3, 149,
          "No data returned (timeout while sending data).")
    tk.Label(win, text="🎧", bg=WINDOW,
             font=("Segoe UI", 12)).place(x=472, y=367)
    _hline(win, 1, 392, MAIN_WIDTH - 3)

    # provider tab strip (spec #main .tabs: top 392px, .tab top:5px)
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
    # spec #opt .title: 0..24 white strip, "Options" at left 11/top 4,
    # close at right (the shell's own ✕ at 46px from the right edge).
    bar = tk.Frame(win, bg=WINDOW, bd=0, height=24)
    bar.place(x=0, y=0, width=OPTS_W, height=24)
    tk.Label(bar, text="Options", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=11, y=4)
    tk.Label(bar, text="✕", bg=WINDOW, fg=TEXT,
             font=("Segoe UI", 10)).place(x=OPTS_W - 46, y=3)

    # spec #opt .side (the static, authoritative one for this screen):
    # left:10px top:28px width:142px height:323px, entries at
    # top:3+i*13. NOTE the spec carries a SECOND, different shell: the
    # JS-generated FR() used by the 7 extra Options pages uses
    # P(5,30,141,323) + i*13+1 in a 646x389 window. Those are the
    # spec's own inconsistency; `options_window` is the #opt screen
    # (default page "Hotkeys"), so it follows #opt and records the
    # divergence here rather than silently picking one.
    side = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                    highlightbackground=BORDER)
    side.place(x=10, y=28, width=142, height=323)
    for i, name in enumerate(OPTION_PAGES):
        bg = ACCENT if name == page else WINDOW
        fg = "#ffffff" if name == page else TEXT
        tk.Label(side, text=name, bg=bg, fg=fg, font=FONT,
                 anchor="w").place(x=2, y=3 + i * 13)

    # --- page bodies (all 9, ported from UI-FULL.html) --------------------
    PAGE_BODIES[page](win)
    # spec FR(): BTN(404,364,73,'OK') / BTN(484,364,73,'Cancel') /
    #            BTN(565,364,73,'Apply','dis')  (.btn.bt top:361 in #opt)
    _btn(win, 404, 364, 73, "OK")
    _btn(win, 484, 364, 73, "Cancel")
    _btn(win, 565, 364, 73, "Apply", disabled=True)
    return win


def _page_basics(win):
    _group_box(win, 152, 35, 484, 84, "General")
    for i, label in enumerate(("Start with Windows",
                               "Load at system startup (startup parameter)",
                               "Show on load")):
        _check(win, 160, 55 + i * 20, label, on=not i)
    _group_box(win, 152, 128, 484, 55, "Language")
    _label(win, 157, 152, "Interface language:")
    _combo(win, 397, 143, 233, "English")
    _label(win, 157, 176, "Font:")
    _combo(win, 397, 167, 233, "Tahoma, 9 pt")


def _page_hotkeys(win):
    _check(win, 159, 34, "Enable hotkeys", on=True)
    tbl = _bordered(win, 159, 60, 465, 251)
    tk.Label(tbl, text="Action", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=6, y=4)
    tk.Label(tbl, text="Hotkey", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=323, y=4)
    _vline(tbl, 317, 0, 251)
    for i, act in enumerate(HOTKEY_ACTIONS):
        y = 24 + i * 17
        tk.Label(tbl, text=act, bg=WINDOW, fg=TEXT, font=FONT,
                 anchor="w").place(x=6, y=y)
        if i in HOTKEY_BINDINGS:
            tk.Label(tbl, text=HOTKEY_BINDINGS[i], bg=WINDOW, fg=TEXT,
                     font=FONT, anchor="w").place(x=323, y=y)


def _page_internet(win):
    _group_box(win, 152, 35, 484, 45, "Connection")
    _label(win, 157, 59, "Timeout, sec:")
    _combo(win, 375, 50, 255, "10")
    _group_box(win, 152, 91, 484, 101, "Proxy")
    _combo(win, 157, 105, 470, "Use system proxy settings")
    _combo(win, 162, 134, 78, "HTTP", disabled=True)
    for x, y, w, txt in ((248, 134, 277, ""), (532, 134, 95, "0"),
                         (248, 160, 186, ""), (441, 160, 186, "")):
        f = _bordered(win, x, y, w, 20, outer_bg=TEXT_DIM, inner_bg=FACE)
        if txt:
            tk.Label(f, text=txt, bg=FACE, fg=TEXT_DIM,
                     font=FONT).place(x=5, y=1)


def _page_services(win):
    """The Services page: enabled-service checkboxes + a dictionary preview.

    COORDINATE ORIGIN. The x values below are the spec's FR()-shell numbers,
    which are relative to the page-list frame the spec draws at
    ``P(5,30,141,323)``. `options_window` draws its page list on the WINDOW
    at ``x=10..152`` instead, so using those numbers here put this page's
    whole left column UNDER the page list -- the lists overlapped the
    "Basics/Hotkeys/..." labels and the rest of the window showed bare
    background, reading as large gray blocks. Every other page in this file
    already starts at x=152 (past the list); this one now does too, shifted
    by the same offset. The preview pane at x=155 was already absolute and
    is unchanged.
    """
    X = 152                      # the offset that reconciles the two shells
    _label(win, X + 5, 5, "Translation", fg=SECTION_INK)
    _hline(win, X + 5, 12, 376, SECTION_RULE)
    for i, (name, color) in enumerate(SERVICES_TRANSLATE):
        _check(win, X + 5, 25 + i * 18, "", on=True)
        tk.Frame(win, bg=color, bd=0,
                 highlightthickness=0).place(x=X + 21, y=24 + i * 18,
                                             width=14, height=14)
        tk.Label(win, text=name, bg=FACE, fg=TEXT, font=FONT,
                 anchor="w").place(x=X + 38, y=23 + i * 18)
    _label(win, X + 5, 191, "Dictionary", fg=SECTION_INK)
    _hline(win, X + 5, 198, 376, SECTION_RULE)
    for i, (name, color) in enumerate(SERVICES_DICTIONARY):
        _check(win, X + 5, 212 + i * 18, "", on=True)
        tk.Frame(win, bg=color, bd=0,
                 highlightthickness=0).place(x=X + 21, y=211 + i * 18,
                                             width=14, height=14)
        tk.Label(win, text=name, bg=FACE, fg=TEXT, font=FONT,
                 anchor="w").place(x=X + 38, y=210 + i * 18)
    tk.Frame(win, bg=THUMB, bd=0, highlightthickness=0).place(
        x=471, y=17, width=2, height=157)
    fld = _bordered(win, 155, 31, 481, 272)
    for x, w, t in ((157, 24, "▲"), (187, 24, "▼"),
                    (219, 117, "Add dictionary…"),
                    (342, 118, "Remove dictionary")):
        _btn(win, x, 309, w, t, fg=TEXT_DIM if t in ("▲", "▼",
                                                     "Remove dictionary")
             else TEXT)


def _page_languages(win):
    """The Languages page: three checkbox columns inside one bordered pane.

    COORDINATE ORIGIN, same defect as `_page_services`: the checkboxes were
    laid out at x=3..16, which the spec means relative to the page-list frame
    (`P(5,30,141,323)`), so they landed UNDER the page list. `options_window`
    puts the list on the window at x=10..152, so the columns are shifted by
    the same 152 offset and now live inside the bounded pane at x=155.
    """
    X = 152
    # The returned inner frame is the pane's white interior; children are
    # placed on `win` (absolute), so the frame only supplies the bg/border.
    _bordered(win, X + 3, 31, 481, 272)
    col_w, per_col = 126.5, 18
    for ci, col in enumerate(LANGUAGE_COLUMNS):
        for i, name in enumerate(col.split(" ")):
            x = 3 + ci * col_w
            _check(win, X + int(x), int(31 + i * 14), "", on=True)
            tk.Label(win, text=name, bg=WINDOW, fg=TEXT, font=FONT,
                     anchor="w").place(x=X + int(x) + 16,
                                       y=int(31 + i * 14))
    tk.Frame(win, bg=THUMB, bd=0, highlightthickness=0).place(
        x=X + 18, y=262, width=238, height=2)
    _btn(win, X + 3, 308, 481, "Check / Uncheck all")


def _page_appearance(win):
    _group_box(win, 152, 35, 484, 56, "General")
    _check(win, 160, 55, "Enable window style")
    _label(win, 157, 77, "Theme:")
    _combo(win, 397, 68, 233, "--- Default ---")
    _group_box(win, 152, 98, 484, 226, "Popup window")
    for i, (label, on) in enumerate((("Enable auto size", True),
                                     ("Enable auto position", True),
                                     ("Activate when opened", False),
                                     ("Pin when dragging", True))):
        _check(win, 160, 122 + i * 23, label, on=on)
    _label(win, 157, 213, "Auto-hide delay:")
    _combo(win, 397, 204, 115, "5")
    _label(win, 523, 206, "seconds")
    _label(win, 157, 237, "Transparency (0 - 90):")
    f = _bordered(win, 397, 227, 233, 20)
    tk.Label(f, text="15", bg=WINDOW, fg=TEXT, font=FONT).place(x=5, y=1)
    _label(win, 157, 261, "Frame thickness:")
    _combo(win, 397, 252, 233, "2")
    _label(win, 157, 286, "Icons:")
    for i, g in enumerate(("📖", "🎧", "⧉")):
        _btn(win, 398 + i * 23, 275, 22, g, h=22)
    _btn(win, 467, 275, 22, "tā", h=22)
    _label(win, 157, 313, "Background color:")
    _label(win, 320, 313, "Text color:")
    tk.Frame(win, bg=SWATCH_TEXT, bd=0, highlightthickness=0).place(
        x=378, y=305, width=87, height=17)
    _label(win, 482, 313, "Frame color:")
    tk.Frame(win, bg=SWATCH_FRAME, bd=0, highlightthickness=0).place(
        x=549, y=305, width=78, height=17)


def _page_exceptions(win):
    _combo(win, 155, 33, 481, "Disabled for these programs:")
    tbl = _bordered(win, 153, 60, 483, 221)
    tk.Label(tbl, text="Program Name", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=7, y=5)
    tk.Label(tbl, text="Window Class Name", bg=WINDOW, fg=TEXT,
             font=FONT).place(x=246, y=5)
    _vline(tbl, 240, 2, 18)
    for i, (prog, cls) in enumerate(EXCEPTIONS_ROWS):
        y = 25 + i * 17
        tk.Label(tbl, text=prog, bg=WINDOW, fg=TEXT, font=FONT,
                 anchor="w").place(x=7, y=y)
        tk.Label(tbl, text=cls, bg=WINDOW, fg=TEXT, font=FONT,
                 anchor="w").place(x=246, y=y)
    _btn(win, 155, 288, 71, "Add")
    _btn(win, 234, 288, 72, "Modify")
    _btn(win, 314, 288, 72, "Delete")
    _check(win, 154, 321, "Enable smart detection", on=True)


def _page_advanced(win):
    _group_box(win, 152, 35, 484, 178, "Advanced")
    for y, label, value in ((56, "Default browser:", "Internet Explorer"),
                            (80, "Copy action:", "Ctrl + C"),
                            (104, "Keyboard layout indicator:", "None"),
                            (128, "Preferred domain:", "com")):
        _label(win, 157, y, label)
        _combo(win, 455, y - 10, 175, value)
    for i, (label, on) in enumerate((("Enable GUI translation", False),
                                     ("Enable listening to the same text at "
                                      "a slower speed", True),
                                     ("Remove line breaks", False))):
        _check(win, 160, 154 + i * 23, label, on=on)
    _group_box(win, 152, 224, 484, 66, "Mouse mode")
    _check(win, 160, 244,
           "Enable mouse mode only when Ctrl is pressed")
    _check(win, 160, 268,
           "Click on system tray icon switches mouse mode", on=True)
    _group_box(win, 152, 296, 484, 54, "API keys")
    _label(win, 157, 315, "OCR API key:")
    _bordered(win, 387, 304, 243, 22)
    _label(win, 157, 331, "Register here for free OCR API key", fg=LINK)


def _page_updates(win):
    _check(win, 161, 44, "Automatically check for updates")
    _bordered(win, 153, 63, 481, 230)
    _btn(win, 524, 300, 110, "Check now")


PAGE_BODIES = {
    "Basics": _page_basics,
    "Hotkeys": _page_hotkeys,
    "Internet": _page_internet,
    "Services": _page_services,
    "Languages": _page_languages,
    "Appearance": _page_appearance,
    "Exceptions": _page_exceptions,
    "Advanced": _page_advanced,
    "Updates": _page_updates,
}


def dictionary_window(root):
    # see main_window: spec height includes the native title bar, the
    # client area tkinter actually places into is 30px shorter.
    h = DICT_H - 30
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{DICT_W}x{h}")
    _titlebar(win, DICT_W, "Dictionary")
    _combo(win, 4, 5, 153, "English")
    fld = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    fld.place(x=163, y=4, width=274, height=21)
    _label(win, 170, 7, "◀ ▶", fg=TEXT_DIM)
    _label(win, 407, 4, "⌕")
    _label(win, 427, 4, "◷")
    _label(win, 457, 4, "⋮")
    track = tk.Frame(win, bg=MENU_BG, bd=0)
    track.place(x=455, y=30, width=19, height=240)
    _label(win, 460, 34, "⌃", fg=TEXT_DIM)
    _label(win, 460, 238, "⌄", fg=TEXT_DIM)
    tabs = ["G.", "W", "B.", "W", "M.", "I.", "R.", "U.", "A.", "y.",
            "O."]
    colors = ["#4285f4", "#d9534f", "#1a73c8", "#999", "#2d6cdf",
              "#7a3d9e", "#2d6cdf", "#e8890c", "#e53935", "#d33",
              "#8a8a2a"]
    for i, (n, c) in enumerate(zip(tabs, colors)):
        b = tk.Button(win, text="  " + n, bg=FACE, fg=TEXT, font=FONT,
                      anchor="w", relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=BORDER)
        b.place(x=4 + i * 42, y=276, width=42, height=21)
        tk.Frame(win, bg=c, bd=0).place(x=6 + i * 42, y=280, width=12,
                                        height=12)
    return win


def history_window(root):
    h = HIST_H - 30
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{HIST_W}x{h}")
    _titlebar(win, HIST_W, "History")
    fld = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    fld.place(x=4, y=4, width=467, height=21)
    tk.Label(fld, text="✕", bg=WINDOW, fg=TEXT,
             font=("Segoe UI", 9, "bold")).place(x=447, y=1)
    lst = tk.Frame(win, bg=WINDOW, bd=0, highlightthickness=1,
                   highlightbackground=BORDER)
    lst.place(x=4, y=31, width=467, height=225)
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
                  highlightbackground=BORDER).place(x=x, y=264, width=w,
                                                    height=21)
    tk.Button(win, text="★", bg=FACE, fg="#e6c800", font=FONT,
              relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=197, y=264, width=20,
                                                height=21)
    tk.Button(win, text="OK", bg=FACE, fg=TEXT, font=FONT, relief="flat",
              bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=398, y=264, width=73,
                                                height=21)
    return win


def keyboard_window(root):
    h = KBD_H - 30
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{KBD_W}x{h}")
    _titlebar(win, KBD_W, "Keyboard")
    tk.Button(win, text="Esc", bg=FACE, fg=TEXT, font=FONT,
              relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER).place(x=8, y=7, width=27,
                                                height=20)
    for i, x in enumerate([52, 84, 116, 148, 196, 228, 260, 292, 336,
                           368, 400, 430]):
        tk.Button(win, text="F%d" % (i + 1), bg=FACE, fg=TEXT, font=FONT,
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=BORDER).place(x=x, y=7, width=28,
                                                    height=20)
    # remaining rows normalised to fit 448px, as the spec records
    rows = [
        (27, [("`", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1),
              ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1),
              ("=", 1), ("BkSp", 2)]),
        (49, [("Tab", 1.5), ("q", 1), ("w", 1), ("e", 1), ("r", 1),
              ("t", 1), ("y", 1), ("u", 1), ("i", 1), ("o", 1), ("p", 1),
              ("[", 1), ("]", 1), ("\\", 1.5)]),
        (70, [("Caps", 1.9), ("a", 1), ("s", 1), ("d", 1), ("f", 1),
               ("g", 1), ("h", 1), ("j", 1), ("k", 1), ("l", 1),
               (";", 1), ("'", 1), ("Enter", 2.2)]),
        (91, [("Shift", 2.3), ("z", 1), ("x", 1), ("c", 1), ("v", 1),
               ("b", 1), ("n", 1), ("m", 1), (",", 1), (".", 1),
               ("/", 1), ("Shift", 2.8)]),
        (112, [("Ctrl", 1.4), ("Win", 1.4), ("Alt", 1.4), ("", 6.3),
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
    _combo(win, 8, 139, 150, "English")
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


def tray_menu(root):
    """Reference sheet for the tray menu's CONTENTS only.

    The real app never draws this: the tray menu is the OS's own, shown on
    right-clicking the taskbar icon (spec §5 hard rule 5), which is what
    ``app._make_tray``'s pystray icon does. This function exists so the
    item order can be eyeballed against the screenshot without a live
    taskbar icon, and is deliberately NOT self-styled beyond the colours
    the OS uses (no rounding, no shadow).
    """
    win = tk.Toplevel(root)
    win.configure(bg=FACE)
    win.geometry(f"{TRAY_W}x{TRAY_H}")
    menu = tk.Frame(win, bg=MENU_BG, bd=0, highlightthickness=0)
    menu.place(x=68, y=23, width=213, height=244)
    tk.Frame(menu, bg=MENU_BORDER, bd=0,
             highlightthickness=0).place(x=0, y=0, width=213, height=244)
    tk.Frame(menu, bg=MENU_BG, bd=0,
             highlightthickness=0).place(x=1, y=1, width=211, height=242)
    y = 5
    tk.Label(menu, text="QTranslate", bg=MENU_BG, fg="#000",
             font=("Segoe UI", 9, "bold")).place(x=38, y=y)
    for i, item in enumerate(TRAY_ITEMS[1:]):
        tk.Label(menu, text=item, bg=MENU_BG, fg="#000",
                 font=FONT).place(x=38, y=27 + i * 22)
    _hline(menu, 1, 160, 211, MENU_SEP)
    _check(menu, 14, 169, "Enable global hotkeys", on=True)
    tk.Label(menu, text="Mouse mode", bg=MENU_BG, fg="#000",
             font=FONT).place(x=38, y=190)
    tk.Label(menu, text="›", bg=MENU_BG, fg="#000",
             font=FONT).place(x=190, y=190)
    _hline(menu, 1, 213, 211, MENU_SEP)
    tk.Label(menu, text="Exit", bg=MENU_BG, fg="#000",
             font=FONT).place(x=38, y=221)
    return win


def launch(screen="main"):
    root = tk.Tk()
    root.withdraw()
    if screen == "tray":
        # the real thing: a taskbar icon whose right-click menu is the
        # OS's own (app._make_tray). Only if pystray + PIL are present.
        try:
            from qtranslate import app as _A
            _stub = _A.App.__new__(_A.App)
            _tray = _A._make_tray(root, _stub)
            if _tray is not None:
                import threading
                threading.Thread(target=_tray.run, daemon=True).start()
                print("tray icon running -- right-click it for the menu")
                root.mainloop()
                return
        except Exception as e:
            print("native tray unavailable (%r); falling back to the "
                  "reference sheet" % (e,))
    SCREENS[screen](root)
    root.mainloop()


if __name__ == "__main__":
    launch(sys.argv[1] if len(sys.argv) > 1 else "main")
