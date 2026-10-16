"""Native Win32 main window — RE 1:1 of QTranslate DLG 129 via pywin32.

Same controls as the exe dialog (340x201 DLUs, 17 controls):
  RichEdit50W id1000 (source) / id1017 (result) / id1018 (aux, third pane),
  ComboBox id1001 (src lang) / id1002 (tgt lang),
  Buttons: help 1009, New 1021, menu 1022, swap 1015, Translate 1004,
           Fav 1029, Speech-radio 1030, Play 1027 (src) / 1028 (result),
  SysLink 1161 "Info", separators 1134/1135.

  ID MAPPING CORRECTED 2026-10-16. This file claimed "RE 1:1" while using
  the source pane's id as 1017 and the result pane's as 1018 -- the two were
  off by one. DLG129 has THREE RichEdits and the two Play buttons settle
  which is which: 1027 sits inside the top pane (1000), so 1000 is the
  SOURCE; 1028 sits inside the middle pane (1017), so 1017 is the RESULT.
  1018 is the small bottom pane, which native's docs do not name. See
  docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md.
Backend reuses qtranslate.services + config/history/locale/theme.

Run: uv run --with pywin32 -- python -I qtranslate/win32app.py
"""
import sys

sys.path.insert(0, ".")

import win32con
import win32gui

from qtranslate import config as C

APP_TITLE = "QTranslate"

# DLG 129 template is 340x201 dialog units; at MS Shell Dlg 8pt
# (baseunit 7x15) that is 595x376 px -- /4 horizontally (340*7/4=595) and
# /8 vertically (201*15/8=376), because the two DLU axes use different
# divisors (see docs/review/G9_PART_A_CLOSED_2026-10-16.md §1 and
# TEMPLATE_GEOMETRY in placement.py). This read `W, H = 595, 753` for a
# while: the height was divided by 4 as well, giving a window nearly twice
# as tall as native's. The old 526x366 here was a different error -- a
# stale saved-placement constant from another machine, not the template.
W, H = 595, 376

# control ids from DLG 129
# DLG129's real ids (corrected 2026-10-16; see the module docstring).
ID_SRC = 1000          # the top, largest pane
ID_OUT = 1017          # the middle pane
ID_AUX = 1018          # the small bottom pane -- native-only, see note
ID_INFO = 1161         # SysLink "Info" strip
ID_SRC_LANG = 1001
ID_TGT_LANG = 1002
ID_NEW = 1021
ID_MENU = 1022
ID_SWAP = 1015
ID_GO = 1004
ID_FAV = 1029
ID_SPEECH = 1030
ID_PLAY_SRC = 1027
ID_PLAY_OUT = 1028
ID_HELP = 1009


class MainWindow:
    def __init__(self):
        self.hinst = win32gui.GetModuleHandle(None)
        self._register()
        self.hwnd = win32gui.CreateWindowEx(
            0, "QTranslateRE", APP_TITLE,
            win32con.WS_OVERLAPPEDWINDOW & ~win32con.WS_MAXIMIZEBOX,
            876, 292, W, H, 0, 0, self.hinst, None)
        self._build()

    def _register(self):
        # keep the bound proc alive for the window lifetime
        self._proc = self._wndproc
        wc = win32gui.WNDCLASS()
        wc.hInstance = self.hinst
        wc.lpszClassName = "QTranslateRE"
        wc.lpfnWndProc = self._proc
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_BTNFACE + 1
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        if msg == win32con.WM_COMMAND:
            self._on_command(win32gui.LOWORD(wparam))
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _child(self, cls, text, x, y, w, h, cid, style=0):
        return win32gui.CreateWindowEx(
            0, cls, text,
            win32con.WS_CHILD | win32con.WS_VISIBLE | style,
            x, y, w, h, self.hwnd, cid, self.hinst, None)

    def _build(self):
        import ctypes
        ctypes.windll.msftedit  # ensure RichEdit50W class (native loads msftedit.dll)
        # nav row: back/forward + service link + overflow (DLG129 top)
        self._child("Button", "<", 4, 4, 24, 22, 1101)
        self._child("Button", ">", 30, 4, 24, 22, 1102)
        self.svc_link = self._child("Static", "Google", 58, 6, 60, 18,
                                     1103, win32con.SS_NOTIFY)
        self._child("Button", ":", 496, 4, 22, 22, ID_MENU)
        # source pane (id1000) + result pane (id1017)
        self.src = self._child("RichEdit50W", "", 4, 30, 514, 120, ID_SRC,
                               win32con.ES_MULTILINE | win32con.ES_AUTOVSCROLL
                               | win32con.WS_VSCROLL)
        self.out = self._child("RichEdit50W", "", 4, 196, 514, 96, ID_OUT,
                               win32con.ES_MULTILINE | win32con.ES_AUTOVSCROLL
                               | win32con.WS_VSCROLL | win32con.ES_READONLY)
        # language row
        self.src_lang = self._child("ComboBox", "", 60, 164, 130, 120,
                                    ID_SRC_LANG,
                                    win32con.CBS_DROPDOWNLIST)
        self.tgt = self._child("ComboBox", "", 240, 164, 130, 120,
                               ID_TGT_LANG, win32con.CBS_DROPDOWNLIST)
        for name in ("Auto-Detect", "English", "Vietnamese"):
            win32gui.SendMessage(self.src_lang, win32con.CB_ADDSTRING, 0,
                                 name)
            win32gui.SendMessage(self.tgt, win32con.CB_ADDSTRING, 0, name)
        win32gui.SendMessage(self.src_lang, win32con.CB_SETCURSEL, 0, 0)
        win32gui.SendMessage(self.tgt, win32con.CB_SETCURSEL, 2, 0)
        # buttons
        self._child("Button", "New", 4, 162, 30, 23, ID_NEW)
        self._child("Button", "<>", 194, 162, 40, 23, ID_SWAP)
        self._child("Button", "Translate", 376, 162, 70, 23, ID_GO)
        self._child("Button", "?", 496, 28, 22, 22, ID_HELP)
        # default text = version line + help.txt (native EditSource)
        try:
            with open("C:/Program Files (x86)/QTranslate/Locales/English/"
                      "help.txt", encoding="utf-8-sig") as f:
                default = "QTranslate Version 6.10.0\n\n" + f.read().strip()
        except Exception:
            default = "QTranslate Version 6.10.0"
        win32gui.SetWindowText(self.src, default)
        # service strip (ids 2000+): icon buttons + short names,
        # ServicesOrder [1,5,12,13,11,26,28,30,31]
        import os as _os
        _svc = [("Google", "Go..", "Google Translate"),
                ("Microsoft", "Mi..", "Microsoft Translator"),
                ("Promt", "Pr..", "Promt"),
                ("Babylon", "Ba..", "Babylon"),
                ("Yandex", "Ya..", "Yandex"),
                ("youdao", "yo..", "youdao"),
                ("Baidu", "Ba..", "Baidu"),
                ("Papago", "Pa..", "Naver"),
                ("DeepL", "DeepL", "DeepL")]
        self.strip_btns = {}
        # 9 services in 514px: icon 22 + label 30 -> 56px each = 504
        x = 4
        for _i, (disp, short, folder) in enumerate(_svc):
            ico = _os.path.join(
                "C:/Program Files (x86)/QTranslate/Services",
                folder, "Service.ico")
            hicon = 0
            if _os.path.exists(ico):
                try:
                    # IMAGE_ICON=1, LR_LOADFROMFILE=0x10, LR_DEFAULTSIZE=0x40
                    hicon = win32gui.LoadImage(
                        0, ico, 1, 16, 16, 0x10 | 0x40)
                except Exception:
                    hicon = 0
            b = self._child("Button", "" if hicon else short,
                            x, 300, 22 if hicon else 30, 22, 2000 + _i,
                            win32con.BS_ICON if hicon else 0)
            if hicon:
                win32gui.SendMessage(b, 0x00F7, 1, hicon)  # BM_SETIMAGE
            lab = self._child("Static", short, x + 22, 302, 30, 18,
                              2100 + _i)
            x += 54
        # error line in result pane (native shows timeout text)
        win32gui.SetWindowText(
            self.out, "No data returned (timeout while sending data).")

    def _on_command(self, cid):
        if cid == ID_GO:
            self._translate()
        elif cid == ID_NEW:
            win32gui.SetWindowText(self.src, "")
            win32gui.SetWindowText(self.out, "")

    def _combo_text(self, hwnd):
        # CBS_DROPDOWNLIST has no edit text; read the selected item.
        i = win32gui.SendMessage(hwnd, win32con.CB_GETCURSEL, 0, 0)
        n = win32gui.SendMessage(hwnd, win32con.CB_GETLBTEXTLEN, i, 0)
        buf = win32gui.PyMakeBuffer(n + 1)
        win32gui.SendMessage(hwnd, win32con.CB_GETLBTEXT, i, buf)
        raw = bytes(buf)[:n * 2].decode("utf-16-le", errors="replace")
        return raw.rstrip("\x00")

    def _translate(self):
        from qtranslate.app import do_translate
        n = win32gui.GetWindowTextLength(self.src)
        buf = win32gui.PyMakeBuffer(n + 1)
        win32gui.GetWindowText(self.src, buf, n + 1)
        text = buf[:n].decode("utf-16-le", errors="replace") \
            if isinstance(buf[:n], bytes) else str(buf)[:n]
        _code = {"Auto-Detect": "auto", "English": "en",
                 "Vietnamese": "vi"}
        src = _code.get(self._combo_text(self.src_lang), "auto")
        tgt = _code.get(self._combo_text(self.tgt), "vi")
        try:
            out_text = do_translate("google", text, tgt, src=src).text
        except Exception as e:
            out_text = f"[error] {e}"
        win32gui.SetWindowText(self.out, out_text)

    def run(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.PumpMessages()


def main():
    MainWindow().run()


if __name__ == "__main__":
    main()
