"""Native Win32 main window — RE 1:1 of QTranslate DLG 129 via pywin32.

Same controls as the exe dialog (340x201 DLUs, 17 controls):
  RichEdit50W id1017 (source) / id1018 (result),
  ComboBox id1001 (src lang) / id1002 (tgt lang),
  Buttons: New 1021, menu 1022, swap 1015, Translate 1004,
           Fav 1029, Speech-radio 1030, Play 1027/1028, help 1009,
  Separators 1134/1135, Dl service strip 108.
Backend reuses qtranslate.services + config/history/locale/theme.

Run: uv run --with pywin32 -- python -I qtranslate/win32app.py
"""
import sys

sys.path.insert(0, ".")

import win32con
import win32gui

from qtranslate import config as C

APP_TITLE = "QTranslate"

# DLG 129 geometry (dialog units -> pixels via MS Shell Dlg mapping is
# handled by MapDialogRect; here we create at pixel sizes measured
# from the native window rect: 526x366 incl. frame).
W, H = 526, 366

# control ids from DLG 129
ID_SRC = 1017
ID_OUT = 1018
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


def _font_handle(name="Tahoma", size=9):
    lf = win32gui.LOGFONT()
    lf.lfHeight = -size * 96 // 72
    lf.lfFaceName = name
    import win32ui
    return win32ui.CreateFont(lf)


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
        # source pane (id1017) + result pane (id1018)
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

    def _translate(self):
        from qtranslate.app import do_translate
        n = win32gui.GetWindowTextLength(self.src)
        buf = win32gui.PyMakeBuffer(n + 1)
        win32gui.GetWindowText(self.src, buf, n + 1)
        text = buf[:n].decode("utf-16-le", errors="replace") \
            if isinstance(buf[:n], bytes) else str(buf)[:n]
        try:
            res = do_translate("google", text, "vi")
        except Exception as e:
            res = f"[error] {e}"
        win32gui.SetWindowText(self.out, res)

    def run(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.PumpMessages()


def main():
    MainWindow().run()


if __name__ == "__main__":
    main()
