"""End-to-end TTS->BASS verification (needs 32-bit python + real bass.dll).

Mirrors native TaskListenText (FUN_00461642):
  google_tts mp3 -> BASS_StreamCreateFile(mem) -> ChannelPlay -> block till end.
Run: <py32> tests/live_bass.py
"""
import sys

sys.path.insert(0, ".")

from qtranslate import player, tts

mp3 = tts.google_tts("Xin chào", "vi")
assert len(mp3) > 1000 and mp3[:2] == b"\xff\xf3", "not an MP3 frame"
print("mp3 bytes:", len(mp3))
player.play_mp3_bytes(mp3, block=True)
print("BASS PLAY OK (stream decoded to end)")

mp3n = __import__("qtranslate.services.naver", fromlist=["tts"]).tts("Hello", "en")
assert len(mp3n) > 1000, "naver tts too small"
print("naver mp3 bytes:", len(mp3n))
player.play_mp3_bytes(mp3n, block=True)
print("NAVER BASS PLAY OK")
