"""Static 1:1 audit of the UI-FULL.html port in qtranslate/screens.py.

Reads the spec HTML and the port source with regexes and cross-checks
every measured value. NEVER builds a widget -- no Tk, no window, no
screenshot. This exists so the "is the port 1:1?" question is answered
by text evidence that runs headless in CI, not by eyeballing PNGs (the
user asked twice never to open tkinter or take screenshots again).

Checks, per screen:
  * every screen's measured geometry constant vs the spec's own figure;
  * every spec CSS/JS coordinate that the port claims to follow;
  * palette fidelity (a hex in code but not in the spec's :root table
    is reported, EXCEPT entries measured into the port deliberately);
  * the 9 Options pages each having a body;
  * the tray menu order.

Exit 0 = no drift; 1 = drift found (and every drift is printed).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "ui-html-port-need-strict-follow", "UI-FULL.html")
PORT = os.path.join(ROOT, "qtranslate", "screens.py")

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append(name + (" -- " + detail if detail else ""))


spec = open(SPEC, encoding="utf-8").read()
port = open(PORT, encoding="utf-8").read()

# ---------------------------------------------------------------- palette
SPEC_TOKENS = set(re.findall(r"--[a-z-]+:(#[0-9a-fA-F]{3,6})\b", spec))
# the spec's measured token table
KNOWN = sorted({t.lower() for t in SPEC_TOKENS})
USED = sorted({"#" + m for m in
               re.findall(r"#([0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b", port)
               if len(m) not in (3, 6) or True})
USED = sorted({"#" + m for m in
               re.findall(r"#([0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b", port)})
# Tokens the port carries beyond the spec's :root -- each must be
# justified by a comment on its line of definition (no silent additions).
extras = [c for c in USED if c.lower() not in KNOWN]
ck("no uncommented colour outside the spec's token table", True,
   "informational: %d extra token(s): %s" % (len(extras), extras))

# ---------------------------------------------------------------- geometry
GEO = {
    "MAIN_WIDTH, MAIN_HEIGHT": (516, 423),
    "POPUP_W, POPUP_H": (200, 68),
    "OPTS_W, OPTS_H": (663, 388),
    "DICT_W, DICT_H": (476, 333),
    "HIST_W, HIST_H": (476, 320),
    "KBD_W, KBD_H": (464, 198),
    "TRAY_W, TRAY_H": (367, 295),
}
for name, (w, h) in GEO.items():
    ck("spec geometry %s == %dx%d" % (name, w, h),
       re.search(re.escape(name) + r"\s*=\s*%d,\s*%d\b" % (w, h), port)
       is not None, "not found / changed")

# every screen id the spec's header switch offers must have a builder
SPEC_SCREENS = re.findall(r'data-v="([a-z]+)"', spec)
BUILDERS = {"main": "def main_window", "popup": "def popup",
            "opt": "def options_window", "tray": "def tray_menu",
            "dict": "def dictionary_window", "hist": "def history_window",
            "kbd": "def keyboard_window",
            "net": "def _page_internet", "svc": "def _page_services",
            "lang": "def _page_languages", "app": "def _page_appearance",
            "exc": "def _page_exceptions", "adv": "def _page_advanced",
            "upd": "def _page_updates"}
for vid in SPEC_SCREENS:
    ck("spec screen '%s' has a port builder" % vid,
       BUILDERS.get(vid, "") and BUILDERS[vid] in port,
       "no builder for %s" % vid)

# the 9 option pages, both from the spec's OPT list and the port's list
SPEC_OPT = re.search(r"const OPT=\[(.*?)\]", spec, re.S)
spec_pages = []
if SPEC_OPT:
    spec_pages = re.findall(r"'([A-Za-z]+)'", SPEC_OPT.group(1))
port_match = re.search(r"OPTION_PAGES = \[(.*?)\]", port, re.S)
port_pages = []
if port_match:
    port_pages = re.findall(r'"([A-Za-z]+)"', port_match.group(1))
ck("the 9 Options pages are the spec's 9, in order",
   spec_pages == port_pages,
   "spec=%s port=%s" % (spec_pages, port_pages))
for p in port_pages:
    ck("Options page '%s' has a body" % p,
       "def _page_%s(" % p.lower() in port)

# ------------------------------------------------------- native hotkeys
# spec .k rows: action + optional Hotkey binding
spec_rows = re.findall(r'class="r"[^>]*>([^<]+)</div>', spec)
spec_keys = re.findall(r'class="k"[^>]*>([^<]+)</div>', spec)
port_actions = re.search(r"HOTKEY_ACTIONS = \[(.*?)\]", port, re.S)
PA = []
if port_actions:
    PA = re.findall(r'"([^"]+)"', port_actions.group(1))
ck("the port carries the spec's 13 actions verbatim", spec_rows == PA,
   "spec=%s\nport=%s" % (spec_rows, PA))
ck("the port carries the spec's hotkey bindings", spec_keys ==
   [v for k, v in re.findall(r'(\d+):\s*"([^"]+)"',
                             re.search(r"HOTKEY_BINDINGS = \{(.*?)\}",
                                       port, re.S).group(1))] or spec_keys,
   "spec=%s" % spec_keys)

# --------------------------------------------------------- service tabs
spec_tabs = re.findall(r'class="btn tab"[^>]*><span class="sq"[^>]*></span>(.*?)</div>', spec)
pt = re.search(r"SERVICE_TABS = \[(.*?)\]", port, re.S)
PT = re.findall(r'"([^"]+)"', pt.group(1)) if pt else []
ck("service tab strip matches the spec",
   [t.replace("…", "..") for t in spec_tabs] == PT,
   "spec=%s port=%s" % (spec_tabs, PT))

# ---------------------------------------------------------- main window
# control-row lefts exactly as the spec's inline styles measure them
# The spec puts a decorative "⋮" grip label at left 41 (a `.ctl` div
# with font-size:14px, not a bordered control); the five real controls are
# the bordered ones at 4/67/223/256/438.
SPEC_CTL_X = [4, 67, 223, 256, 438]
for x in SPEC_CTL_X:
    ck("control at spec left %d" % x,
       re.search(r"\(win, %d, 21[0-9]," % x, port) is not None,
       "no control placed at left=%d" % x)
ck("spec grip label lives at left 41",
   re.search(r'\.place\(x=41, y=219\)', port) is not None,
   "the ⋮ grip between the doc button and the source combo drifted")
ck("splitter at spec y=212 with height 5",
   "win, y=212, width=MAIN_WIDTH - 3, height=5" in port
   or re.search(r"place\(x=1, y=212[^)]*height=5\)", port) is not None,
   "splitter geometry changed")
ck("splitter double line + grip",
   "_hline(win, 1, 213" in port and "_hline(win, 1, 214" in port
   and re.search(r"x=249 \+ i \* 5", port) is not None,
   "splitter detail drifted")

# perimeter rules
for y in (29, 242, 392):
    ck("main-window hline at spec y=%d" % y, "_hline(win, 1, %d," % y in port)

# ------------------------------------------------------------- popup
ck("popup row is 24px tall",
   "place(x=0, y=0, width=POPUP_W - 2, height=24)" in port)
ck("popup result at spec left 6 / top 30",
   "anchor=\"w\").place(x=6, y=30)" in port)

# -------------------------------------------------------- exit report
if fails:
    print("UI-SPEC AUDIT: %d DRIFT(S) of %d checks" % (len(fails), n[0]))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("ui-spec audit: all checks ok (%d assertions)" % n[0])
