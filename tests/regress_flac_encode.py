"""Regression: the J6 FLAC encoder (``qtranslate/flac_encode.py``)
and its ``speech_input.flac_payload`` chain link.

Native's speech chain is mic -> int16 widen -> block-wise libFLAC
encode -> ``audio/x-flac`` upload. The port's encoder is
libsndfile-backed (soundfile); the upload target is dead upstream, so
this suite pins the ENCODE stage only:

  1. ``encode`` emits a ``fLaC`` stream that decodes back to the exact
     int16 samples (lossless, like libFLAC);
  2. raw little-endian int16 bytes and float arrays are accepted;
  3. ``FlacEncoder`` streams multiple blocks into one valid stream;
  4. ``content_type``/``flac_payload`` produce the native header
     ``audio/x-flac; rate=<rate>``;
  5. a missing soundfile/numpy raises ``FlacUnavailableError``
     (honest failure, never a fake byte string).

Offscreen-free: pure encode/decode, no Qt.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


try:
    import numpy as np
    import soundfile as sf
    from qtranslate import flac_encode as FE
    from qtranslate import speech_input as SI
except Exception as exc:                                # noqa: BLE001
    print("SKIP regress_flac_encode: deps missing (%s)" % exc)
    raise SystemExit(0)


SR = 16000
t = np.arange(SR) / SR
PCM = (np.sin(2 * np.pi * 440 * t) * 30000).astype(np.int16)

# --- one-shot encode ----------------------------------------------------
flac = FE.encode(PCM, SR)
ck("encode emits fLaC magic", flac[:4] == b"fLaC", flac[:8])

import io
info = sf.info(io.BytesIO(flac))
ck("stream reports rate/channels/format",
   info.samplerate == SR and info.channels == 1
   and info.format == "FLAC", repr(info))
back, _ = sf.read(io.BytesIO(flac), dtype="int16")
ck("round-trip is bit-exact",
   back.shape == PCM.shape
   and int(np.abs(back.astype(np.int32)
                   - PCM.astype(np.int32)).max()) == 0)

# --- input shapes --------------------------------------------------------
flac_bytes = FE.encode(PCM.tobytes(), SR)
ck("raw int16 LE bytes accepted", flac_bytes[:4] == b"fLaC")
flac_f32 = FE.encode(PCM.astype(np.float32) / 32768.0, SR)
back_f, _ = sf.read(io.BytesIO(flac_f32), dtype="int16")
ck("float input encodes", back_f.shape == PCM.shape)

stereo = np.stack([PCM, PCM], axis=1).reshape(-1)
flac_st = FE.encode(stereo, SR, channels=2)
sinfo = sf.info(io.BytesIO(flac_st))
ck("stereo encode reports 2 channels",
   sinfo.channels == 2, repr(sinfo))
try:
    FE.encode(b"\x01\x02\x03", SR)      # odd-length int16 bytes
    odd_ok = False
except ValueError:
    odd_ok = True
ck("odd-length PCM bytes fail honestly", odd_ok)

# --- streaming encoder ---------------------------------------------------
enc = FE.FlacEncoder(SR)
step = 4000
for i in range(0, len(PCM), step):
    enc.write(PCM[i:i + step])
streamed = enc.close()
ck("streamed encode emits fLaC", streamed[:4] == b"fLaC")
sback, _ = sf.read(io.BytesIO(streamed), dtype="int16")
ck("streamed round-trip bit-exact",
   sback.shape == PCM.shape
   and int(np.abs(sback.astype(np.int32)
                   - PCM.astype(np.int32)).max()) == 0)
try:
    enc.write(PCM[:10])
    write_after_close = False
except RuntimeError:
    write_after_close = True
ck("write after close raises", write_after_close)

# --- content type + speech_input link ------------------------------------
ck("content_type matches native header",
   FE.content_type(16000) == "audio/x-flac; rate=16000")
payload, ctype = SI.flac_payload(PCM.tobytes(), rate=SR)
ck("flac_payload returns (bytes, header)",
   payload[:4] == b"fLaC" and ctype == "audio/x-flac; rate=16000")

# --- honest failure when deps absent --------------------------------------
saved_sf = sys.modules.get("soundfile")
saved_np = sys.modules.get("numpy")
sys.modules["soundfile"] = None
sys.modules["numpy"] = None
try:
    try:
        FE.encode(PCM, SR)
        raised = False
    except FE.FlacUnavailableError:
        raised = True
    ck("missing soundfile -> FlacUnavailableError", raised)
finally:
    if saved_sf is not None:
        sys.modules["soundfile"] = saved_sf
    else:
        sys.modules.pop("soundfile", None)
    if saved_np is not None:
        sys.modules["numpy"] = saved_np
    else:
        sys.modules.pop("numpy", None)

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_flac_encode: all checks ok (%d assertions)" % n[0])
