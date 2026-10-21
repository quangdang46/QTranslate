"""Patch app.py: bundle the service icons and fix the strip's button sizing.

Two defects, both visible in the port's main window:

1. `_load_svc_icon` only ever looked at
   `C:/Program Files (x86)/QTranslate/Services/<Name>/Service.ico`. Off
   Windows that path does not exist, so no icon was loaded and the button
   fell back to TEXT.
2. `tk.Button(width=22, height=22)` means **22 characters** for a text
   button but **22 pixels** for an image button. With no image, each strip
   button became a 230-pixel-wide text button: the strip's requested width
   went to 2334px inside a 587px window, and six of the nine services were
   pushed off-screen entirely.

The native's own service icons are recoverable from the installer payload and
are pixel-identical to the icons it draws, so they are bundled with the
package (`qtranslate/assets/service_icons/`) and used on every platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("qtranslate/app.py")

OLD = '''    def _load_svc_icon(self, name, button):
        """Load Services/<Name>/Service.ico as the strip button image."""
        import glob
        import os
        try:
            pats = {
                "google": "Google Translate", "deepl": "DeepL",
                "yandex": "Yandex", "baidu": "Baidu", "naver": "Naver",
                "youdao": "youdao", "bing": "Microsoft Translator",
                "microsoft": "Microsoft Translator", "promt": "Promt",
                "reverso": "Reverso", "babylon": "Babylon",
            }
            folder = pats.get(name, name)
            ico = os.path.join("C:/Program Files (x86)/QTranslate/Services",
                               folder, "Service.ico")
            if not os.path.exists(ico):
                button.config(text=name[:4])
                return
            try:
                from PIL import Image, ImageTk
                im = Image.open(ico)
                im = im.convert("RGBA").resize((22, 22), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
            except Exception:
                photo = tk.PhotoImage(file=ico)
                w, h = photo.width(), photo.height()
                if w > 24 or h > 24:
                    photo = photo.subsample(max(1, w // 22),
                                            max(1, h // 22))
            self.svc_icons[name] = photo  # keep ref
            button.config(image=photo, text="")
        except Exception:
            try:
                button.config(text=name[:4])
            except Exception:
                pass
'''

NEW = '''    def _load_svc_icon(self, name, button):
        """Give the strip button the service's own icon.

        The icons are the native ones, recovered from the QTranslate 6.10.0
        installer payload and committed under
        ``qtranslate/assets/service_icons/`` — pixel-identical to the icons
        the native main window draws in its bottom strip (see
        ``docs/review/rea/service_icons/_pairs.png``). Bundling them is what
        makes the strip render on every platform: the previous code only ever
        looked at ``C:/Program Files (x86)/QTranslate/Services/<Name>/
        Service.ico``, so off Windows no icon was loaded at all.

        The button is always given an IMAGE, because Tk reads a button's
        ``width``/``height`` as **characters** for a text button and as
        **pixels** for an image button. Without an image, ``width=22`` became
        a 230-pixel-wide text button and six of the nine services were pushed
        off the end of the strip.
        """
        import os
        photo = None
        bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "service_icons", name + ".png")
        if name == "bing":
            bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "assets", "service_icons",
                                    "microsoft.png")
        try:
            if os.path.exists(bundled):
                photo = tk.PhotoImage(file=bundled)
                if photo.width() != SVC_ICON_PX or photo.height() != SVC_ICON_PX:
                    photo = photo.subsample(
                        max(1, photo.width() // SVC_ICON_PX),
                        max(1, photo.height() // SVC_ICON_PX))
            else:
                # Fall back to a real installed copy (Windows).
                pats = {
                    "google": "Google Translate", "deepl": "DeepL",
                    "yandex": "Yandex", "baidu": "Baidu", "naver": "Naver",
                    "youdao": "youdao", "bing": "Microsoft Translator",
                    "microsoft": "Microsoft Translator", "promt": "Promt",
                    "reverso": "Reverso", "babylon": "Babylon",
                }
                folder = pats.get(name, name)
                ico = os.path.join(
                    "C:/Program Files (x86)/QTranslate/Services",
                    folder, "Service.ico")
                if not os.path.exists(ico):
                    button.config(text=name[:4])
                    return
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(ico)
                    im = im.convert("RGBA").resize((SVC_ICON_PX, SVC_ICON_PX),
                                                    Image.LANCZOS)
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    photo = tk.PhotoImage(file=ico)
                    w, h = photo.width(), photo.height()
                    if w > 24 or h > 24:
                        photo = photo.subsample(max(1, w // SVC_ICON_PX),
                                                max(1, h // SVC_ICON_PX))
            self.svc_icons[name] = photo  # keep ref
            button.config(image=photo, text="")
        except Exception:
            try:
                button.config(text=name[:4])
            except Exception:
                pass
'''

# The strip cell: a 16px icon and the short name, sized in pixels.
OLD_CELL = '''            cell = tk.Frame(strip, bg=bg)
            cell.pack(side="left", padx=2)
            b = tk.Button(cell, width=22, height=22, borderwidth=0,
                          bg=bg, activebackground=bg,
                          command=lambda n=name: self.switch_service(n))
            b.pack(side="left")
            b.bind("<Button-2>",
                   lambda e, n=name: self.open_service_page_n(n))
            b.bind("<Button-3>",
                   lambda e, n=name: self.toggle_multi_service(n))
            tk.Label(cell, text=_SHORT.get(name, name[:2] + ".."), bg=bg,
                     fg="black", font=("Tahoma", 8)).pack(side="left",
                                                          padx=(1, 0))
'''

NEW_CELL = '''            cell = tk.Frame(strip, bg=bg)
            cell.pack(side="left", padx=2)
            # width/height are PIXELS here because the button always ends up
            # with an image (see _load_svc_icon). A text button would read
            # them as characters and be 10x too wide.
            b = tk.Button(cell, width=SVC_ICON_PX, height=SVC_ICON_PX,
                          borderwidth=0, bg=bg, activebackground=bg,
                          highlightthickness=0,
                          command=lambda n=name: self.switch_service(n))
            b.pack(side="left")
            b.bind("<Button-2>",
                   lambda e, n=name: self.open_service_page_n(n))
            b.bind("<Button-3>",
                   lambda e, n=name: self.toggle_multi_service(n))
            tk.Label(cell, text=_SHORT.get(name, name[:2] + ".."), bg=bg,
                     fg="black", font=("Tahoma", 8)).pack(side="left",
                                                          padx=(1, 0))
'''

EDITS = [(OLD, NEW), (OLD_CELL, NEW_CELL)]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"anchor found {count} times (expected 1): {old[:60]!r}",
                  file=sys.stderr)
            return 2
        text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
