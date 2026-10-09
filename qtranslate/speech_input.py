"""Speech input — Google full-duplex streaming ASR (port of FUN_004434FE).

Native lifecycle (J5/J6, REVERIFIED 2026-10-09):

  mic
    -> BASS_RecordStart(dev, 1, 0, cb FUN_00445606, ctx)   (FUN_0044555D)
    -> frame alloc FUN_00444D94 / enqueue FUN_00445659
    -> FLAC encode: init FUN_00466509 ("fLaC" magic), per-buffer
       FUN_00467437(encoder, samples, n)                    (call site FUN_00445716)
    -> upload as ``audio/x-flac; rate=<rate>`` to the full-duplex "up" URL
  results read from the parallel "down" URL.

  up:   https://www.google.com/speech-api/full-duplex/v1/up?
        key=<K>&pair=<P>&output=json&lang=<code>&pFilter=<2|0>&
        maxAlternatives=1&app=chromium&<continuous|endpoint=1>[&interim]
  down: https://www.google.com/speech-api/full-duplex/v1/down?
        key=<K>&pair=<P>&output=json

``build_urls()`` / ``new_pair_id()`` reconstruct the parts that are purely
local and evidence-backed (the embedded key string and every query parameter
are byte-verified from the binary). The live round-trip is
``dead:native-unavailable``: it needs (a) a working embedded key and (b) a
Win32 microphone + FLAC capture path (BASS record) which the port does not
implement. Nothing here performs network I/O, so it cannot fake a result.
"""
from __future__ import annotations

import secrets

# Embedded literal from FUN_004434FE:
#   FUN_0041e3a3(..., L"key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw")
GOOGLE_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
BASE = "https://www.google.com/speech-api/full-duplex/v1"

DEFAULT_RATE = 16000
DEFAULT_LANG = "en-US"  # native default when LanguageSpeechRecognition unset


def new_pair_id() -> str:
    """Random pair id (native FUN_00443b9a: 8 CryptGenRandom bytes encoded)."""
    return secrets.token_hex(8)


def build_urls(lang: str = DEFAULT_LANG, rate: int = DEFAULT_RATE,
               pair: str | None = None, pfilter: int = 2,
               continuous: bool = False, interim: bool = False) -> dict:
    """Build the native up/down URLs + upload Content-Type.

    ``pfilter``  -> ``pFilter`` (native: 2 when the flag at ctx+0xc is set,
                    else 0). ``continuous`` -> ``continuous`` else
                   ``endpoint=1``. ``interim`` adds the bare ``interim`` param.
    All four are exposed for faithfulness; defaults are the common case.
    """
    pair = pair or new_pair_id()
    common = "key={0}&pair={1}&output=json".format(GOOGLE_KEY, pair)

    down = "{0}/down?{1}".format(BASE, common)

    up_params = [
        common,
        "lang={0}".format(lang),
        "pFilter={0}".format(pfilter),
        "maxAlternatives=1",
        "app=chromium",
        "continuous" if continuous else "endpoint=1",
    ]
    if interim:
        up_params.append("interim")
    up = "{0}/up?{1}".format(BASE, "&".join(up_params))

    return {
        "up": up,
        "down": down,
        "content_type": "audio/x-flac; rate={0}".format(rate),
        "pair": pair,
    }
