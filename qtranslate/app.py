"""Minimal runnable clone of the QTranslate pipeline (Windows).

Flow (mirrors native Task pipeline in docs/NATIVE_ARCH.md):
  hotkey (Ctrl+Alt+Q) -> capture clipboard -> translate via service plugin
  -> popup window with result (+ TTS listen button).

Requires: pip install keyboard pyperclip
  python -I qtranslate/app.py [service] [target_lang]
"""
import sys
import threading
import tkinter as tk

sys.path.insert(0, ".")

from qtranslate.services.google_translate import translate as _tr
from qtranslate.tts import google_tts

try:
    import keyboard
    import pyperclip
except ImportError:
    print("pip install keyboard pyperclip")
    raise SystemExit(1)

SERVICE = sys.argv[1] if len(sys.argv) > 1 else "google"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "vi"


def speak(text, lang):
    # Port of native TaskListenText -> FUN_00461642 -> BASS_ChannelPlay.
    # 32-bit bass.dll requires 32-bit Python:
    #   uv run --python cpython-3.12.13-windows-x86-none -I qtranslate/app.py
    from qtranslate.player import play_mp3_bytes
    play_mp3_bytes(google_tts(text, lang))


def show_popup(source, result):
    win = tk.Tk()
    win.title(f"QTranslate-re [{SERVICE} -> {TARGET}] (Ctrl+Alt+Q to re-capture)")
    win.attributes("-topmost", True)
    tk.Label(win, text=source, wraplength=480, justify="left",
             fg="gray").pack(padx=12, pady=(12, 4))
    tk.Label(win, text=result, wraplength=480, justify="left",
             font=("Segoe UI", 13)).pack(padx=12, pady=4)
    frm = tk.Frame(win)
    frm.pack(pady=(0, 12))
    tk.Button(frm, text="🔊 Listen",
              command=lambda: threading.Thread(
                  target=speak, args=(result, TARGET),
                  daemon=True).start()).pack(side="left", padx=6)
    tk.Button(frm, text="Close", command=win.destroy).pack(side="left")
    win.mainloop()


def on_hotkey():
    # TaskCopySelection: clipboard already holds selected text (user pressed Ctrl+C)
    try:
        text = pyperclip.paste().strip()
    except Exception as e:
        print("clipboard error:", e)
        return
    if not text:
        print("clipboard empty — select text + Ctrl+C first")
        return
    print(f"translating {len(text)} chars...")
    try:
        result = _tr(text[:5000], "auto", TARGET)
    except Exception as e:
        result = f"[error] {e}"
    threading.Thread(target=show_popup, args=(text[:300], result),
                     daemon=True).start()


def on_layout_hotkey():
    # TaskConvertTextLayout: retype clipboard text in the other layout.
    try:
        text = pyperclip.paste().strip()
    except Exception as e:
        print("clipboard error:", e)
        return
    if not text:
        print("clipboard empty — select text + Ctrl+C first")
        return
    from qtranslate.layout import convert_layout
    fixed = convert_layout(text)
    pyperclip.copy(fixed)
    print(f"layout-fixed {len(text)} chars -> clipboard: {fixed[:80]}")


print(f"qtranslate-re running: press Ctrl+Alt+Q after Ctrl+C (target={TARGET})")
print("  Ctrl+Alt+L: convert keyboard layout of clipboard text")
keyboard.add_hotkey("ctrl+alt+q", on_hotkey)
keyboard.add_hotkey("ctrl+alt+l", on_layout_hotkey)
keyboard.wait()
