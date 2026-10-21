"""Recover the 8 native theme files from the installer payload.

The census (`PAYLOAD_CHUNK_CENSUS_2026-10-15.md`) proved the payload holds
8 `Themes/*.json` files, SHA-256-identical to the installed ones. They are
written to `qtranslate/assets/themes/` here, named by the colour scheme each
file carries (the payload has no filenames).

`qtranslate/theme.py` then prefers the bundled copies over the Windows
install, the same way `locale.py` now does.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
OUT = ROOT / "qtranslate/assets/themes"

# A theme file's own name is not in it; its colour scheme is. The payload
# order is the install order, and the themes are the 8 chunks the census
# identified as `{"Common": {"ButtonRadius"...`.
NAME_HINTS = ("Blue", "Green", "Grey", "Gray", "Orange", "Purple", "Red",
               "Yellow", "Silver", "Dark", "Light", "Metallic", "Beige",
               "Brown", "Caramel", "Coffee", "Emerald", "Marine", "Navy",
               "Olive", "Peach", "Pink", "Plum", "Sand", "Sky", "Violet")


def walk_chunks(blob: bytes):
    off = 0
    index = 0
    while off < len(blob):
        (length,) = struct.unpack_from("<I", blob, off)
        off += 4
        yield index, blob[off : off + length]
        off += length
        index += 1


def main() -> int:
    blob = PAYLOAD.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()

    found = []
    for index, body in walk_chunks(blob):
        text = body.decode("utf-8", errors="replace")
        if '"Common"' not in text or '"ButtonRadius"' not in text:
            continue
        found.append((index, body, text))

    print(f"theme chunks: {len(found)}")
    used = set()
    for index, body, text in found:
        name = None
        for hint in NAME_HINTS:
            if hint.lower() in text.lower():
                name = hint
                break
        if name is None or name in used:
            name = f"Theme{index}"
        used.add(name)
        (OUT / f"{name}.json").write_bytes(body)
        print(f"  chunk {index:3d} -> {name}.json ({len(body)} B)")
        if name == "Theme%d" % index:
            # Fall back to a stable, readable name.
            (OUT / f"{name}.json").rename(OUT / f"Theme{index:03d}.json")
            used.discard(name)
            used.add(f"Theme{index:03d}")

    (OUT / "_manifest.json").write_text(json.dumps({
        "source_payload": str(PAYLOAD.relative_to(ROOT)),
        "note": "The 8 native Themes/*.json, recovered from the installer "
                "payload (byte-identical to the installed copies). Named by "
                "the colour scheme each file carries -- the payload has no "
                "filenames.",
        "themes": [{"file": p.name, "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in sorted(OUT.glob("*.json"))
                   if not p.name.startswith("_")],
    }, indent=1) + "\n", encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
