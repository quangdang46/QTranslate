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

# The in-flight playback, so a new speak request can cut the old one
# off (native's BASS path frees the previous stream before starting
# the next -- FUN_00461691 -- and every TTS trigger re-enters here).
_current = {"proc": None, "stream": None}


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


def stop() -> None:
    """Cut off whatever is playing right now (subprocess or BASS)."""
    proc = _current.get("proc")
    _current["proc"] = None
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass
    stream = _current.get("stream")
    _current["stream"] = None
    if stream:
        try:
            b = _load()
            b.BASS_ChannelStop(stream)
            b.BASS_StreamFree(stream)
        except Exception:
            pass


def play_mp3_bytes(data: bytes, block: bool = True) -> None:
    """Play MP3 bytes in memory exactly like FUN_00461642 (mem=TRUE stream)."""
    import time
    stop()
    b = _load()
    buf = ctypes.create_string_buffer(bytes(data))
    stream = b.BASS_StreamCreateFile(
        True, buf, 0, len(data), 0, 0)  # mem, file, offset, length, flags
    if not stream:
        raise RuntimeError("BASS_StreamCreateFile failed")
    _current["stream"] = stream
    try:
        if not b.BASS_ChannelPlay(stream, True):
            raise RuntimeError("BASS_ChannelPlay failed")
        if block:
            while b.BASS_ChannelIsActive(stream):
                time.sleep(0.05)
    finally:
        if _current.get("stream") == stream:
            _current["stream"] = None
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
    ``BASS_ChannelIsActive`` polling. The Popen handle is registered in
    ``_current`` so ``stop()`` can cut playback off.
    """
    import subprocess
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="qt_tts_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(data))
        if block:
            proc = subprocess.Popen(
                ["afplay", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _current["proc"] = proc
            try:
                proc.wait()
            finally:
                if _current.get("proc") is proc:
                    _current["proc"] = None
                try:
                    os.unlink(path)
                except OSError:
                    pass
        else:
            # Fire-and-forget: the temp file must outlive afplay, so the
            # wrapper shell removes it after playback ends.
            proc = subprocess.Popen(
                ["sh", "-c", 'afplay "$1"; rm -f "$1"', "sh", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _current["proc"] = proc
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _speak_darwin(text: str, lang: str = "", slow: bool = False) -> None:
    """Offline speech on macOS: the ``say`` command (no SAPI/comtypes).

    VoiceLocaleMapper port: pick an installed voice covering ``lang``
    when one exists; the system default voice otherwise.
    """
    import subprocess
    cmd = ["say"]
    voice = None
    try:
        from qtranslate.services import system_tts
        voice = system_tts.preferred_voice(lang)
    except Exception:
        voice = None
    if voice:
        cmd += ["-v", voice]
    if slow:
        cmd += ["-r", "120"]
    cmd.append(text)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    _current["proc"] = proc
    proc.wait()
    if _current.get("proc") is proc:
        _current["proc"] = None


def play_text(text: str, lang: str = "vi", block: bool = True,
              slow: bool | None = None) -> str:
    """Online mp3 -> platform player; on any failure fall back to offline TTS.

    Mirrors native TaskListenText: serviceListenRequest mp3 first,
    then the offline voice (SpVoice on Windows, ``say`` on macOS) when
    the download fails. slow maps Advanced.EnableSlowerListening
    (clearer TTS); ``None`` reads the setting so EVERY caller honours it,
    not just the history window. Returns backend used.
    """
    if slow is None:
        try:
            from qtranslate import config as _C
            slow = bool((_C.load() or {}).get("Advanced", {})
                        .get("EnableSlowerListening", False))
        except Exception:
            slow = False
    # A new speak request replaces whatever is playing -- overlapping
    # audio is never intended (native frees the old stream first).
    stop()
    backend = _extension_backend(text, lang, slow)
    if backend:
        return "extension:" + backend
    import sys
    sys.path.insert(0, ".")
    from qtranslate.tts import bing_tts, google_tts
    is_darwin = sys.platform == "darwin"
    backend_name = "afplay" if is_darwin else "bass"
    # .tmp ServiceRole.TTS: General.PreferredServices.tts promotes one
    # backend; "system" goes straight to the offline voice. Unknown or
    # empty keeps the google -> bing order.
    try:
        from qtranslate import config as _C
        pref = ((_C.general_setting("PreferredServices", {}) or {})
                .get("tts") or "")
    except Exception:
        pref = ""
    fetches = [("google", google_tts), ("bing", bing_tts)]
    if pref == "system":
        fetches = []
    elif pref in ("google", "bing"):
        fetches.sort(key=lambda kv: kv[0] != pref)
    for name, fetch in fetches:
        try:
            data = fetch(text, lang, slow=slow)
        except Exception as e:
            print(f"{name} tts failed ({e}); trying next backend")
            continue
        try:
            if is_darwin:
                _play_mp3_bytes_darwin(data, block=block)
            else:
                play_mp3_bytes(data, block=block)
            return backend_name
        except Exception as e:
            print(f"{name} tts playback failed ({e}); trying next")
    if is_darwin:
        _speak_darwin(text, lang=lang, slow=slow)
        return "say"
    try:
        # .tmp WindowsTtsBackend equivalent: SAPI SpVoice with
        # VoiceLocaleMapper-style voice matching (comtypes, lazy).
        from qtranslate.services import system_tts as _ST
        if _ST.speak(text, lang=lang, slow=slow):
            return "sapi"
    except Exception:
        pass
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
