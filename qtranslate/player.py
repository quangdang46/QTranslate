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


def _extension_backend(text, lang, slow):
    """An extension's TTS backend, when one registered.

    ``registry.TTS_EXT`` is the live table (``api.register_tts``). The
    first registered backend is tried; when it raises, the built-in
    chain below runs, so a broken extension cannot take speech with it.
    """
    try:
        from qtranslate import registry as _RG
    except Exception:
        return None
    table = getattr(_RG, "TTS_EXT", None)
    if not table:
        return None
    for name in sorted(table):
        try:
            table[name](text, lang, slow)
            return name
        except Exception:
            continue
    return None


def _play_mp3_bytes_darwin(data: bytes, block: bool = True) -> None:
    """Play MP3 bytes on macOS: afplay over a temp file.

    BASS is a Windows DLL; CoreAudio's afplay reads the same MP3 bytes
    natively. Blocking waits on afplay's exit, mirroring
    ``BASS_ChannelIsActive`` polling.
    """
    import subprocess
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="qt_tts_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(data))
        if block:
            try:
                subprocess.run(["afplay", path], check=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        else:
            # Fire-and-forget: the temp file must outlive afplay, so the
            # wrapper shell removes it after playback ends.
            subprocess.Popen(
                ["sh", "-c", 'afplay "$1"; rm -f "$1"', "sh", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _speak_darwin(text: str, slow: bool = False) -> None:
    """Offline speech on macOS: the ``say`` command (no SAPI/comtypes)."""
    import subprocess
    cmd = ["say"]
    if slow:
        cmd += ["-r", "120"]
    cmd.append(text)
    subprocess.run(cmd, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def play_text(text: str, lang: str = "vi", block: bool = True,
              slow: bool = False) -> str:
    """Online mp3 -> platform player; on any failure fall back to offline TTS.

    Mirrors native TaskListenText: serviceListenRequest mp3 first,
    then the offline voice (SpVoice on Windows, ``say`` on macOS) when
    the download fails. slow maps Advanced.EnableSlowerListening
    (clearer TTS). Returns backend used.
    """
    backend = _extension_backend(text, lang, slow)
    if backend:
        return "extension:" + backend
    import sys
    sys.path.insert(0, ".")
    from qtranslate.tts import google_tts
    is_darwin = sys.platform == "darwin"
    try:
        data = google_tts(text, lang, slow=slow)
        if is_darwin:
            _play_mp3_bytes_darwin(data, block=block)
        else:
            play_mp3_bytes(data, block=block)
        return "afplay" if is_darwin else "bass"
    except Exception as e:
        print(f"online TTS failed ({e}); falling back to offline voice")
    if is_darwin:
        _speak_darwin(text, slow=slow)
        return "say"
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
