"""BASS-based MP3 playback — faithful port of the native TaskListenText path.

Reversed from QTranslate.exe (see docs/NATIVE_ARCH.md, FUN_00461642):

    FUN_00461691(ctx);                                     // free old stream
    stream = BASS_StreamCreateFile(mem=TRUE, data, 0, len, 0, 0);
    ctx[0x30] = stream;
    BASS_ChannelSetSync(stream, BASS_SYNC_END, 0, on_end, ctx);
    BASS_ChannelPlay(stream, /*restart*/TRUE);

Uses the real bass.dll shipped with QTranslate via ctypes (no dependency to
install — the DLL is already on disk next to QTranslate.exe).
"""
import ctypes
import os

_BASS_PATHS = [
    "C:/Program Files (x86)/QTranslate/bass.dll",
    os.path.join(os.path.dirname(__file__), "bass.dll"),
]

_bass = None


def _load():
    global _bass
    if _bass is not None:
        return _bass
    for p in _BASS_PATHS:
        if os.path.exists(p):
            _bass = ctypes.WinDLL(p)
            break
    if _bass is None:
        raise FileNotFoundError("bass.dll not found next to QTranslate install")
    b = _bass
    b.BASS_Init.restype = ctypes.c_bool
    b.BASS_Init.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                            ctypes.c_void_p, ctypes.c_void_p]
    b.BASS_StreamCreateFile.restype = ctypes.c_ulong
    b.BASS_StreamCreateFile.argtypes = [ctypes.c_bool, ctypes.c_void_p,
                                        ctypes.c_ulonglong, ctypes.c_ulonglong,
                                        ctypes.c_ulong, ctypes.c_ulong]
    b.BASS_ChannelPlay.restype = ctypes.c_bool
    b.BASS_ChannelPlay.argtypes = [ctypes.c_ulong, ctypes.c_bool]
    b.BASS_ChannelIsActive.restype = ctypes.c_ulong
    b.BASS_ChannelIsActive.argtypes = [ctypes.c_ulong]
    b.BASS_StreamFree.restype = ctypes.c_bool
    b.BASS_StreamFree.argtypes = [ctypes.c_ulong]
    b.BASS_Free.restype = ctypes.c_bool
    if not b.BASS_Init(-1, 44100, 0, None, None):
        raise RuntimeError("BASS_Init failed")
    return b


def play_mp3_bytes(data: bytes, block: bool = True) -> None:
    """Play MP3 bytes in memory exactly like FUN_00461642 (mem=TRUE stream)."""
    import time
    b = _load()
    buf = ctypes.create_string_buffer(bytes(data))
    stream = b.BASS_StreamCreateFile(
        True, buf, 0, len(data), 0, 0)  # mem, file, offset, length, flags
    if not stream:
        raise RuntimeError("BASS_StreamCreateFile failed")
    try:
        if not b.BASS_ChannelPlay(stream, True):
            raise RuntimeError("BASS_ChannelPlay failed")
        if block:
            while b.BASS_ChannelIsActive(stream):
                time.sleep(0.05)
    finally:
        b.BASS_StreamFree(stream)  # mirrors FUN_00461691 free-old-stream


def play_file(path: str, block: bool = True) -> None:
    with open(path, "rb") as f:
        play_mp3_bytes(f.read(), block=block)


def play_text(text: str, lang: str = "vi", block: bool = True,
              slow: bool = False) -> str:
    """Online mp3 -> BASS; on any failure fall back to offline SAPI.

    Mirrors native TaskListenText: serviceListenRequest mp3 first,
    SpVoice (FUN_00448BEC) when offline. slow maps
    Advanced.EnableSlowerListening (clearer TTS). Returns backend used.
    """
    import sys
    sys.path.insert(0, ".")
    from qtranslate.tts import google_tts
    try:
        play_mp3_bytes(google_tts(text, lang, slow=slow), block=block)
        return "bass"
    except Exception as e:
        print(f"online TTS failed ({e}); falling back to SAPI")
    from qtranslate.sapi import speak
    speak(text, rate=-4 if slow else 0)
    return "sapi"


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    text = sys.argv[1] if len(sys.argv) > 1 else "Xin chào"
    lang = sys.argv[2] if len(sys.argv) > 2 else "vi"
    print(f"downloading TTS for {text!r} ...")
    print("played via", play_text(text, lang))
