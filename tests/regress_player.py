"""Pin the TTS playback orchestration (row F BASS / Offline TTS fallback).

Native `FUN_00461642` plays an in-memory mp3 via BASS
(`BASS_StreamCreateFile(mem=TRUE,...)` + `BASS_SYNC_END` + `ChannelPlay
restart=1`); on failure the app falls back to SAPI. `player.play_text`
mirrors that chain: online TTS mp3 -> BASS, any failure -> SAPI.

Offline: google_tts / play_mp3_bytes / sapi.speak are monkey-patched;
no audio, no network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


import qtranslate.player as P

# --- online path: bass ---------------------------------------------------
import qtranslate.tts as TTS

_calls = {}
_orig_tts = TTS.google_tts
_orig_play = P.play_mp3_bytes
_orig_speak = None

TTS.google_tts = lambda t, l, slow=False: (_calls.__setitem__("slow", slow),
                                           b"MP3")[1]
P.play_mp3_bytes = lambda data, block=True: _calls.__setitem__("bytes", data)
try:
    used = P.play_text("hello", "vi")
    ck("online success uses bass", used == "bass", used)
    ck("mp3 bytes passed to the player", _calls.get("bytes") == b"MP3")
    ck("slow flag forwarded to the TTS builder",
       _calls.get("slow") is False, repr(_calls.get("slow")))
finally:
    TTS.google_tts = _orig_tts
    P.play_mp3_bytes = _orig_play

# --- slow flag propagation ----------------------------------------------
TTS.google_tts = lambda t, l, slow=False: (_calls.__setitem__("slow2", slow),
                                           b"MP3")[1]
P.play_mp3_bytes = lambda data, block=True: None
try:
    P.play_text("hello", "vi", slow=True)
    ck("slow=True reaches the TTS builder", _calls.get("slow2") is True,
       repr(_calls.get("slow2")))
finally:
    TTS.google_tts = _orig_tts
    P.play_mp3_bytes = _orig_play

# --- offline fallback: sapi ---------------------------------------------
import qtranslate.sapi as SAPI

_orig_sapi = SAPI.speak
_seen = {}


def _boom(_t, _l, slow=False):
    raise RuntimeError("online down")


def _fake_speak(text, rate=0):
    _seen["text"] = text
    _seen["rate"] = rate


TTS.google_tts = _boom
SAPI.speak = _fake_speak
try:
    used = P.play_text("xin chào", "vi")
    ck("online failure falls back to sapi", used == "sapi", used)
    ck("sapi receives the text", _seen.get("text") == "xin chào",
       repr(_seen.get("text")))
    ck("sapi rate is 0 at normal speed", _seen.get("rate") == 0,
       repr(_seen.get("rate")))
    _seen.clear()
    P.play_text("x", "vi", slow=True)
    ck("sapi rate is -4 when slow", _seen.get("rate") == -4,
       repr(_seen.get("rate")))
finally:
    TTS.google_tts = _orig_tts
    SAPI.speak = _orig_sapi

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_player: all checks ok (%d assertions)" % n[0])
