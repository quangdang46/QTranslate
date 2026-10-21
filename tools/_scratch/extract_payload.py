"""Extract the JS/asset chunks out of the recovered NSIS payload.

The installer payload (`docs/review/artifacts/nsis_payload_unpacked.bin`) is a
flat stream of `<uint32-LE length><body>` chunks with no filenames. This
script walks that stream exactly and writes each chunk into a directory tree
named from its *content*, never from its position.

Naming follows `docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md` §1:
  - ``new ServiceHeader(`` in the first 300 B -> ``Services/<name>/Service.js``
  - ``var Const={MAX_URI_LEN`` in the first 2000 B -> ``Common.js``
  - ``historyHeader`` anywhere -> ``Plugins/History/<kind>.js``
  - ``<?xml`` / ``<xsl`` head -> ``Resources/XdxfArticle.xslt``

The output directory must be new and empty; this script refuses otherwise so a
previous extraction can never be silently mixed in.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

PAYLOAD = Path("docs/review/artifacts/nsis_payload_unpacked.bin")
OUT = Path("docs/review/rea/js_root")


def walk_chunks(blob: bytes):
    off = 0
    index = 0
    while off < len(blob):
        if off + 4 > len(blob):
            raise ValueError(f"truncated length prefix at {off}")
        (length,) = struct.unpack_from("<I", blob, off)
        off += 4
        if off + length > len(blob):
            raise ValueError(f"chunk {index} claims {length} bytes, only {len(blob) - off} left")
        yield index, blob[off : off + length]
        off += length
        index += 1


def classify(body: bytes):
    """Return (relative_path, kind) for a chunk, or (None, None) if it is not ours."""
    head = body[:300]
    if b"new ServiceHeader(" in head:
        return ("Services/<name>/Service.js", "service")
    if b"var Const={MAX_URI_LEN" in body[:2000]:
        return ("Common.js", "common")
    if b"historyHeader" in body:
        return ("Plugins/History/<kind>.js", "history")
    # The XSLT chunk carries a UTF-8 BOM ahead of the XML declaration.
    stripped = body.lstrip(b"\xef\xbb\xbf")
    if stripped[:5] == b"<?xml" or stripped[:4] == b"<xsl":
        return ("Resources/XdxfArticle.xslt", "xslt")
    return (None, None)


def service_name(body: bytes) -> str:
    """Recover the service directory name from the chunk's own content.

    Native builds the header as ``new ServiceHeader(<id>, "<name>", "<info>")``.
    """
    match = re.search(rb'new ServiceHeader\(\s*\d+\s*,\s*"([^"]*)"', body[:400])
    return match.group(1).decode("utf-8", errors="replace").strip() if match else ""


def history_kind(body: bytes) -> str:
    """Name a history exporter from the shape of its own output."""
    if b"<!DOCTYPE HTML" in body[:400] or b"quoteHtml" in body[:400]:
        return "html"
    if b"escFunc" in body[:400] or b"JSON.stringify" in body[:400]:
        return "json"
    if b"escapeValue" in body[:400]:
        return "csv"
    return "txt"


def main() -> int:
    blob = PAYLOAD.read_bytes()
    if OUT.exists() and any(OUT.iterdir()):
        print(f"refusing: {OUT} exists and is not empty", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = []
    total = 0
    for index, body in walk_chunks(blob):
        total += 1
        rel, kind = classify(body)
        if rel is None:
            continue
        if kind == "service":
            name = service_name(body) or f"unknown_{index}"
            rel = rel.replace("<name>", name)
        elif kind == "history":
            rel = rel.replace("<kind>", history_kind(body))
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        manifest.append({
            "chunk": index,
            "path": rel,
            "kind": kind,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })

    (OUT / "_manifest.json").write_text(json.dumps({
        "source_payload": str(PAYLOAD),
        "payload_sha256": hashlib.sha256(blob).hexdigest(),
        "payload_bytes": len(blob),
        "chunks_walked": total,
        "extracted": len(manifest),
        "files": manifest,
    }, indent=1), encoding="utf-8")
    print(f"walked {total} chunks, extracted {len(manifest)}")
    for item in manifest:
        print(f"  {item['path']:45s} {item['bytes']:7d} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
