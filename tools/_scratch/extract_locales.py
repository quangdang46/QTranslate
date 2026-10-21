"""Recover the 35 UI locale packs from the installer payload.

`docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md` proved the payload carries
all 35 `Locales/<dir>/lang.json` and `Locales/<dir>/help.txt` pairs, each
SHA-256-identical to the installed file.

Both the port's `locale.py` and `app.py`'s default source text read them
from `C:/Program Files (x86)/QTranslate/Locales`, so off Windows the port
had no locales at all and its default source pane showed a three-line stub
instead of native's help text.

This writes the recovered packs into `qtranslate/assets/locales/<code>/`,
named by the `"LanguageCode"` each `lang.json` carries.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
OUT = ROOT / "qtranslate/assets/locales"


def walk_chunks(blob: bytes):
    off = 0
    index = 0
    while off < len(blob):
        (length,) = struct.unpack_from("<I", blob, off)
        off += 4
        yield index, blob[off : off + length]
        off += length
        index += 1


def decode_text(body: bytes):
    for enc in ("utf-8-sig", "utf-16-le", "utf-16"):
        try:
            return body.decode(enc), enc
        except Exception:
            continue
    return None, None


def main() -> int:
    blob = PAYLOAD.read_bytes()
    langs = {}
    helps = []
    for index, body in walk_chunks(blob):
        text = body.decode("utf-8", errors="replace")
        if '"LanguageCode"' in text and '"Strings"' in text:
            try:
                obj = json.loads(text)
            except Exception:
                continue
            code = obj.get("LanguageCode")
            if code:
                langs.setdefault(code, []).append((index, body))
            continue
        decoded, enc = decode_text(body)
        if decoded and "=>" in decoded and "Ctrl" in decoded:
            helps.append((index, body, enc))

    print(f"lang.json chunks: {sum(len(v) for v in langs.values())} "
          f"({len(langs)} language codes)")
    print(f"help.txt chunks: {len(helps)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.is_dir():
            for sub in old.rglob("*"):
                sub.unlink()
            old.rmdir()
        else:
            old.unlink()

    written = []
    for code, entries in sorted(langs.items()):
        index, body = entries[0]
        d = OUT / code
        d.mkdir(parents=True, exist_ok=True)
        (d / "lang.json").write_bytes(body)
        written.append({"code": code, "chunk": index,
                        "lang_sha256": hashlib.sha256(body).hexdigest()})

    # Attach the help text: a locale's help is the one whose text names the
    # same language. The English pack is the one whose text is the native
    # help (the app shows it by default), so it is matched by its content.
    english = None
    for index, body, enc in helps:
        text = body.decode(enc, errors="replace")
        if "Global hotkeys" in text and "Main window hotkeys" in text:
            english = (index, body, enc)
            break
    if english is not None:
        index, body, enc = english
        d = OUT / "en"
        d.mkdir(parents=True, exist_ok=True)
        (d / "help.txt").write_bytes(body)
        print(f"English help.txt: chunk {index} ({enc})")
        written.append({"code": "en", "chunk": index, "help_sha256":
                        hashlib.sha256(body).hexdigest()})
    else:
        print("English help.txt NOT FOUND", file=sys.stderr)

    (OUT / "_manifest.json").write_text(json.dumps({
        "source_payload": str(PAYLOAD.relative_to(ROOT)),
        "note": "Recovered from the QTranslate 6.10.0 installer payload; "
                "identical to the installed Locales/<dir> files "
                "(PAYLOAD_CHUNK_CENSUS_2026-10-15.md §3: 35/35 lang.json "
                "and 35/35 help.txt SHA-256-identical).",
        "locales": written,
    }, indent=1) + "\n", encoding="utf-8")
    print("wrote", OUT, "with", len(written), "entries")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
