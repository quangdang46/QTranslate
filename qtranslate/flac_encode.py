"""FLAC encoder — the J6 encode stage of native's speech-input chain.

Native (J5/J6, `docs/review/J6_FLAC_DECOMPILE_2026-10-10.md`): BASS
captures int16 mic frames, each frame is widened int16->int32
(`FUN_00445716`), and `FUN_00467437` encodes BLOCK-WISE into a
statically-linked **libFLAC 1.2.1** (file `0x12d220`, `"fLaC"` magic at
`0x123310`). The encoder keeps a partial block at `ctx+0x1b8c` and
clamps to the room left — block chunking the libFLAC API itself does
not expose. The upload Content-Type is `audio/x-flac; rate=<rate>`.

The port has no consumer yet: native's upload target (Google's
full-duplex speech API) is retired and the live speech path is
SAPI/SFSpeechRecognizer (`qt/app.py::hotkey_speech_input`). This
module is the encoder substrate that chain would need, implemented
against `soundfile`'s bundled libsndfile (which itself links libFLAC)
rather than a vendored encoder. libsndfile owns frame/block
buffering internally, so native's `+0x1b8c` partial-block state is
subsumed — same wire format, same `fLaC` stream.

Honest failure: when `soundfile`/`numpy` are absent every entry point
raises `FlacUnavailableError` (a RuntimeError) naming the missing
dependency — never a silent WAV or a fake byte string.
"""
from __future__ import annotations


class FlacUnavailableError(RuntimeError):
    """soundfile/numpy missing — the encoder cannot run."""


def _sf():
    try:
        import numpy  # noqa: F401  (soundfile needs it for buffers)
        import soundfile
        return soundfile
    except ImportError as exc:
        raise FlacUnavailableError(
            "FLAC encoding needs: pip install soundfile "
            "(bundles libsndfile+libFLAC); missing %s" % exc) from exc


def content_type(rate: int) -> str:
    """The native upload header value: ``audio/x-flac; rate=<rate>``."""
    return "audio/x-flac; rate=%d" % int(rate)


def _as_array(pcm):
    """Accept int16 PCM as numpy array, array-like, or raw LE bytes."""
    import numpy as np
    if isinstance(pcm, (bytes, bytearray, memoryview)):
        raw = bytes(pcm)
        if len(raw) % 2:
            raise ValueError("int16 PCM byte string has odd length")
        return np.frombuffer(raw, dtype="<i2").copy()
    arr = np.asarray(pcm)
    if arr.dtype == np.int16:
        return arr
    if arr.dtype.kind == "i" and arr.itemsize <= 4:
        return arr.astype(np.int16)
    if arr.dtype.kind == "f":
        return np.clip(arr * 32768.0, -32768, 32767).astype(np.int16)
    raise ValueError("unsupported PCM dtype %r (want int16)" % arr.dtype)


def encode(pcm, samplerate: int, channels: int = 1,
           subtype: str = "PCM_16") -> bytes:
    """One-shot PCM -> FLAC bytes (``fLaC`` stream, native's format).

    ``pcm`` is mono int16 samples (numpy array, sequence, or raw
    little-endian int16 bytes — the BASS frame shape). ``channels``>1
    expects interleaved samples, matching libsndfile's frame layout.
    """
    sf = _sf()
    import io
    data = _as_array(pcm)
    if channels > 1:
        data = data.reshape(-1, channels)
    buf = io.BytesIO()
    sf.write(buf, data, int(samplerate), format="FLAC", subtype=subtype)
    return buf.getvalue()


class FlacEncoder:
    """Block-wise encoder — the streaming counterpart of native's
    ``FUN_00467437`` loop.

    Feed int16 PCM blocks with :meth:`write`; :meth:`close` finishes
    the stream and returns the complete FLAC bytes. Partial-block
    carry-over is libsndfile's job (native kept it at ``+0x1b8c``).
    """

    def __init__(self, samplerate: int, channels: int = 1,
                 subtype: str = "PCM_16"):
        sf = _sf()
        import io
        self._buf = io.BytesIO()
        # The SoundFile object must stay alive AND be closed for
        # libsndfile to finalize the FLAC stream (header + metadata
        # are written on close); module-level sf.write() would reopen
        # the buffer per call and never finalize.
        self._file = sf.SoundFile(self._buf, mode="w",
                                  samplerate=int(samplerate),
                                  channels=int(channels), format="FLAC",
                                  subtype=subtype)
        self._channels = int(channels)
        self._closed = False

    def write(self, pcm) -> None:
        if self._closed:
            raise RuntimeError("encoder already closed")
        data = _as_array(pcm)
        if self._channels > 1:
            data = data.reshape(-1, self._channels)
        self._file.write(data)

    def close(self) -> bytes:
        if not self._closed:
            self._closed = True
            self._file.close()
        self._buf.seek(0)
        return self._buf.getvalue()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
