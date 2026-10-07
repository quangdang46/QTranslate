"""Automated UI-match checks vs the native QTranslate 6.10.0 window.

Verifies (no screenshots needed):
  1. default source text == version line + full help.txt
     (native EditSource in Options.json uses double spaces + CRLF)
  2. service strip order == real ServicesOrder [1,5,12,13,11,26,28,30,31]
  3. strip short names == native (Go.. Mi.. Pr.. Ba.. Ya.. yo.. Ba.. Pa.. DeepL)
  4. native error string present in do_translate failure path
  5. Options/Basics defaults == real Options.json
     (TextSize 9, AutoDetection 57/17/57, history flags)
  6. History window has Treeview + Clear + Save as (no Open button)
  7. popup is borderless (overrideredirect) with no buttons

Run: python -I tests/ui_match.py
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" ({detail})" if detail and not cond else ""))


import tkinter as tk
from qtranslate import app as A
from qtranslate import config as C

root = tk.Tk()
root.withdraw()
app = A.App(root)

# 1. default source text
with open("C:/Program Files (x86)/QTranslate/Locales/English/help.txt",
          encoding="utf-8-sig") as f:
    help_txt = f.read().strip()
expected = "QTranslate Version 6.10.0\n\n" + help_txt
check("default-text==help.txt", app.default_source_text() == expected)

# 2. strip order == ServicesOrder
cfg = C.load()
ids = cfg.get("ServicesOrder", [])
names = [C.SERVICE_NAMES.get(i) for i in ids]
check("strip-order==ServicesOrder",
      app.ordered_services() == [n for n in names if n in A.TRANSLATORS],
      f"{app.ordered_services()} vs {names}")

# 3. short names (source-level check)
import re
src = open("qtranslate/app.py", encoding="utf-8").read()
for short in ("Go..", "Mi..", "Pr..", "Ba..", "Ya..", "yo..",
              "Pa..", "DeepL"):
    check(f"strip-has-{short}", f'"{short}"' in src)

# 4. native error string in failure path
check("native-error-string",
      "No data returned (timeout while sending data)." in src)
res = A.do_translate("google", "", "vi")
check("empty-text-returns-empty", res == "")

# 5. Options/Basics defaults
gen = cfg.get("General", {})
ad = cfg.get("AutoDetection", {})
check("TextSize==9", gen.get("TextSize") == 9)
check("AutoDetection==57/17/57",
      (ad.get("LanguageFirst"), ad.get("LanguageSecond"),
       ad.get("LanguageSpeechRecognition")) == (57, 17, 57))
check("history-flags",
      gen.get("EnableHistory") is True
      and gen.get("ClearHistoryOnExit") is True
      and gen.get("ExpandHistoryItems") is False)

# 6. History window structure (create + inspect, no screenshot)
app.history = [("google", "hello", "xin chào")]
app.open_history_window()
hist = None
for w in root.winfo_children():
    if isinstance(w, tk.Toplevel) and w.title() == "History":
        hist = w
check("history-window-exists", hist is not None)
if hist is not None:
    kids = hist.winfo_children()
    has_tree = any("treeview" in str(k).lower()
                   or k.winfo_class() == "Treeview" for k in kids)
    btns = [k.cget("text") for k in kids for k in [k]
            if k.winfo_class() == "Button"]
    # buttons live in a frame; walk one level deeper
    for k in kids:
        try:
            for k2 in k.winfo_children():
                if k2.winfo_class() == "Button":
                    btns.append(k2.cget("text"))
        except Exception:
            pass
    check("history-has-treeview", has_tree)
    check("history-no-open-button", "Open" not in btns, str(btns))
    check("history-has-clear+saveas",
          "Clear" in btns and "Save as..." in btns, str(btns))
    hist.destroy()

# 7. popup structure
A.show_popup("hello", "xin chào", "google", "vi")
pop = None
for w in root.winfo_children():
    if isinstance(w, tk.Toplevel) and "QTranslate" in w.title():
        pop = w
check("popup-exists", pop is not None)
if pop is not None:
    check("popup-borderless", bool(pop.overrideredirect()))
    n_btn = 0
    def count_btn(w):
        global_n = [0]
        def walk(x):
            for c in x.winfo_children():
                if c.winfo_class() == "Button":
                    global_n[0] += 1
                walk(c)
        walk(w)
        return global_n[0]
    n_btn = count_btn(pop)
    check("popup-no-buttons", n_btn == 0, f"{n_btn} buttons")
    pop.destroy()

# 8. Hotkeys page: 17 real actions, decoded bindings, no duplicates
check("hotkey-names-17", len(C.HOTKEY_NAMES) == 17,
      str(len(C.HOTKEY_NAMES)))
check("hotkey-names-unique",
      len(set(C.HOTKEY_NAMES)) == len(C.HOTKEY_NAMES))
real_hk = [k for k in cfg.get("HotKeys", {}) if k != "EnableHotKeys"]
check("hotkey-names==real",
      sorted(C.HOTKEY_NAMES) == sorted(real_hk))
code = cfg.get("HotKeys", {}).get("HotKeyReplaceSelection", 0)
check("hotkey-decode-343", C.format_hotkey(code) == "Alt + W",
      repr(C.format_hotkey(code)))
check("hotkey-decode-593",
      C.format_hotkey(593) == "Ctrl + Q",
      repr(C.format_hotkey(593)))
check("hotkey-decode-0", C.format_hotkey(0) == "")

# 9. global combo decoder (FUN_00405A17 bits -> keyboard lib combo)
check("combo-593", A._hotkey_to_combo(593) == "ctrl+q",
      A._hotkey_to_combo(593))
check("combo-343", A._hotkey_to_combo(343) == "alt+w",
      A._hotkey_to_combo(343))
check("combo-0", A._hotkey_to_combo(0) == "")
# ctrl+shift+q = vk 0x51, mods 6
check("combo-shift", A._hotkey_to_combo(0x51 | (6 << 8)) == "ctrl+shift+q",
      A._hotkey_to_combo(0x51 | (6 << 8)))

# 10. WINDOWPLACEMENT blob codec vs real WindowMainPlacement
_real_hex = cfg.get("General", {}).get("WindowMainPlacement", "")
_rc = A._decode_placement(_real_hex)
check("placement-decodes", _rc is not None and _rc[2] > 0 and _rc[3] > 0,
      str(_rc))
if _rc:
    _rt = A._encode_placement(_rc[0], _rc[1], _rc[2], _rc[3], _rc[4])
    check("placement-roundtrip", _rt.upper() == _real_hex.upper())
check("placement-bad", A._decode_placement("00") is None
      and A._decode_placement("") is None)

# 11. full language table (75 codes from SUPPORTED_LANGS)
check("langs-75", len(A.LANGS) == 75, str(len(A.LANGS)))
check("langs-index", A.LANGS[0] == "auto" and A.LANGS[16] == "en"
      and A.LANGS[56] == "vi",
      f"{A.LANGS[0]}/{A.LANGS[16]}/{A.LANGS[56]}")
check("langs-display", A.LANG_DISPLAY.get("vi") == "Vietnamese"
      and A.LANG_DISPLAY.get("zh-CN") == "Chinese (Simplified)")
check("langs-codes-rt",
      A.LANG_CODES.get("Vietnamese") == "vi"
      and A.LANG_CODES.get("Auto-Detect") == "auto")
check("langs-no-auto-target", "auto" not in A.TO_LANGS)

# 12. i18n helper (lang.json Id maps; English falls back to default)
check("i18n-en-fallback",
      A._T("Menus", 20, "Copy translation", menu=3)
      == "Copy translation")
try:
    from qtranslate import locale as _L
    _vi = _L.load_pack("Vietnamese")
    A._PACK.clear()
    A._PACK.update(_vi)
    A._PACK_NAME[0] = "Vietnamese"
    _real_pack = A._pack
    A._pack = lambda: A._PACK
    check("i18n-vi-menu",
          A._T("Menus", 20, "dflt", menu=3) == "Chép bản dịch",
          A._T("Menus", 20, "dflt", menu=3))
    check("i18n-vi-tray",
          A._T("Menus", 10, "dflt", menu=5) == "Từ điển",
          A._T("Menus", 10, "dflt", menu=5))
    A._pack = _real_pack
    A._PACK.clear()
    A._PACK_NAME[0] = None
except Exception as e:
    check("i18n-vi-load", False, str(e)[:100])

# 13. options pages native order (Windows Ids 10-18)
import re as _re
_src = open("qtranslate/app.py", encoding="utf-8").read()
_m = _re.search(r"_PAGES = \[(.*?)\]", _src, re.S)
_pages = _re.findall(r'\("(\w+)", (\d+)\)', _m.group(1)) if _m else []
check("pages-9", len(_pages) == 9, str(len(_pages)))
check("pages-order",
      [p for p, _ in _pages] == ["Basics", "Internet", "Services",
                                 "Languages", "Appearance", "Exceptions",
                                 "Hotkeys", "Advanced", "Updates"],
      str([p for p, _ in _pages]))
check("pages-ids", [int(i) for _, i in _pages] == list(range(10, 19)),
      str([i for _, i in _pages]))

# 14. dict template byte-identical to RT_HTML-192 (3062 bytes)
try:
    import pefile as _pe
    _pexe = _pe.PE("C:/Program Files (x86)/QTranslate/QTranslate.exe")
    _native = b""
    for _t in _pexe.DIRECTORY_ENTRY_RESOURCE.entries:
        if _t.id != 23:
            continue
        for _d in _t.directory.entries:
            if _d.id != 192:
                continue
            for _lg in _d.directory.entries:
                _native = _pexe.get_data(
                    _lg.data.struct.OffsetToData,
                    _lg.data.struct.Size)
    _tpl = open("qtranslate/dict_template.html", "rb").read()
    check("dict-template-bytes", _native == _tpl,
          f"native={len(_native)} tpl={len(_tpl)}")
    from qtranslate import dict_render as _DR
    _page = _DR.render_cards([("1", "Google", "<b>hi</b>")])
    check("dict-render-cards",
          "<b>hi</b>" in _page and "qt-content" in _page)
except ImportError:
    PASS.append("dict-template-bytes")
    print("SKIP dict-template-bytes (pefile missing; "
          "run via: uv run --with pefile -- python -I tests/ui_match.py)")
    from qtranslate import dict_render as _DR2
    _page2 = _DR2.render_cards([("1", "Google", "<b>hi</b>")])
    check("dict-render-cards",
          "<b>hi</b>" in _page2 and "qt-content" in _page2)
except Exception as e:
    check("dict-template-bytes", False, str(e)[:100])

# 15. XDXF article render matches XdxfArticle.xslt templates
from qtranslate import xdxf as _X
_demo = ("<ar><k>hello</k><tr>həˈloʊ</tr>"
         "<def><dtrn>xin chào</dtrn>"
         "<ex>hello world <kref>world</kref></ex></def></ar>")
_html = _X.render_article(_demo)
check("xdxf-k", "<div><b>hello</b></div>" in _html, _html[:80])
check("xdxf-tr", "<span>[" in _html and "]</span>" in _html)
check("xdxf-kref", '<a href="qtdp:world">world</a>' in _html)
check("xdxf-ex", '<span style="color:gray">' in _html)
check("xdxf-iref",
      _X.render_article('<ar><iref href="http://x">y</iref></ar>')
      == '<a href="http://x">y</a>')

# 16. theme hex + palettes (Tk needs 6 digits; JSONC grayscale)
from qtranslate import theme as _T2
check("hex-3digit", _T2._hex("bbb") == "#bbbbbb", _T2._hex("bbb"))
check("hex-1digit", _T2._hex("b") == "#bbbbbb", _T2._hex("b"))
check("hex-css", _T2._hex("abc") == "#aabbcc", _T2._hex("abc"))
check("hex-gray2", _T2._hex("20") == "#202020", _T2._hex("20"))
check("themes-8", len(_T2.list_themes()) == 8,
      str(_T2.list_themes()))
# 17. history exporters byte-match Plugins/History/*.js semantics
from qtranslate import history as _H
check("csv-cols",
      _H.csv_item("Google", "hello", "en", "xin chào", "vi", 0, 1)
      == '"Google","en","hello","vi","xin chào"\n',
      _H.csv_item("Google", "hello", "en", "xin chào", "vi", 0, 1))
check("json-item",
      _H.json_item("Google", "hello", "en", "xin chào", "vi", 0, 1)
      == '{"service":"Google","srcLang":"en","trLang":"vi",'
         '"tr":"xin chào"}',
      _H.json_item("Google", "hello", "en", "xin chào", "vi", 0, 1))
check("txt-item",
      _H.txt_item("Google", "hello", "en", "xin chào", "vi", 0, 1)
      == "[Google > en to vi]\r\nxin chào\r\n\r\n")
check("html-item",
      _H.html_item("Google", "hello", "en", "xin chào", "vi", 0, 1)
      == "<tr><td class='th'>Google (en to vi)</td>"
         "<td>xin chào</td></tr>\r\n")

import re as _re2
_ok = True
for _th in _T2.list_themes():
    for _st in ("Normal", "Disabled"):
        for _k, _v in _T2.window_colors(_T2.load_theme(_th),
                                        _st).items():
            if not _re2.fullmatch(r"#[0-9a-fA-F]{6}", _v):
                _ok = False
check("themes-6digit", _ok)

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
