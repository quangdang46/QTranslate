"""Extract Resources/XdxfArticle.xslt from the recovered NSIS payload.

Method (docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md §1): walk the stream
as <uint32-LE length><body> from offset 0; classify by content marker, never
by position.  The XSLT is the one chunk whose body starts with a UTF-8 BOM
followed by "<?xml" (or "<xsl").

Run:  python3.11 -I tools/_scratch_xdxf/extract_xslt.py
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys

PAYLOAD = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "review", "artifacts", "nsis_payload_unpacked.bin")


def walk(data: bytes):
    """Yield (index, offset, body) for every <u32 len><body> chunk."""
    off = 0
    idx = 0
    while off < len(data):
        if off + 4 > len(data):
            raise ValueError("truncated length field at %d" % off)
        (n,) = struct.unpack_from("<I", data, off)
        body = data[off + 4: off + 4 + n]
        if len(body) != n:
            raise ValueError("truncated body at %d (want %d got %d)"
                             % (off, n, len(body)))
        yield idx, off, body
        off += 4 + n
        idx += 1


def main() -> int:
    with open(PAYLOAD, "rb") as f:
        data = f.read()
    hits = []
    total = 0
    for idx, off, body in walk(data):
        total = idx + 1
        stripped = body[3:] if body[:3] == b"\xef\xbb\xbf" else body
        if stripped.startswith(b"<?xml") or stripped.startswith(b"<xsl"):
            hits.append((idx, off, body))
    if not hits:
        print("NO XSLT CHUNK FOUND")
        return 1
    print("chunks walked: %d" % total)
    for idx, off, body in hits:
        print("--- chunk index %d at stream offset 0x%x, %d bytes ---"
              % (idx, off, len(body)))
        print("sha256(body) = %s" % hashlib.sha256(body).hexdigest())
        print("first bytes: %r" % body[:24])
        text = body.decode("utf-8-sig")
        sys.stdout.write(text)
        print("\n--- end chunk %d ---" % idx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
