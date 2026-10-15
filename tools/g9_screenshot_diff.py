#!/usr/bin/env python3
"""G9 runtime screenshot-diff harness (TEST-ONLY, stdlib-only).

Purpose
-------
Evaluate G9 "visual fidelity to native" by comparing a **native** QTranslate
6.10.0 screenshot against a **port** screenshot, but only when the two captures
were taken under equivalent conditions (same window size, UI state, input).

This is a *measurement* tool. It does **not** perform reverse engineering, it
does **not** touch application code, and it does **not** open the Gate. See
`docs/review/G9_HARNESS.md`, in particular the distinction between
"harness self-test" (mechanics) and "G9 acceptance result" (real evidence).

Result semantics (exactly three outcomes)
-----------------------------------------
- PASS    : both images decoded, geometry equal, protocol metadata equal, and
            the pixel difference is within tolerance.
- FAIL    : evidence exists but the comparison is negative -- either the two
            window geometries differ, or the difference exceeds tolerance.
- BLOCKED : the comparison could not be run on usable evidence -- a missing or
            unreadable input, a capture that failed, or protocol metadata
            (ui_state / input) that does not match. Never a fabricated PASS.

Synthetic fixtures (produced by `make-sample`/`selftest`) exercise the
*mechanics* only. They are tagged `synthetic` in every report and are NEVER
native-versus-port fidelity evidence.

Exit codes
----------
0 PASS | 1 FAIL | 2 BLOCKED | 3 usage / mechanism error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

TOOL = "g9_screenshot_diff"
VERSION = "1"

# --------------------------------------------------------------------------
# Minimal PNG codec (stdlib only). Supports 8-bit, non-interlaced PNG with
# colour types 0/2/4/6 -> normalised to RGB. Alpha is dropped (screenshots are
# opaque); this is documented in G9_HARNESS.md.
# --------------------------------------------------------------------------

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def png_decode(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG file")
    pos, idat = 8, bytearray()
    w = h = bd = ct = interlace = None
    while pos + 8 <= len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        typ = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct, _comp, _filt, interlace = struct.unpack(">IIBBBBB", chunk)
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
    if w is None:
        raise ValueError("PNG has no IHDR")
    if bd != 8:
        raise ValueError(f"unsupported PNG bit depth {bd} (need 8)")
    if interlace != 0:
        raise ValueError("interlaced PNG is not supported")
    ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ct)
    if ch is None:
        raise ValueError(f"unsupported PNG colour type {ct} (0/2/4/6 only)")
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    if len(raw) < h * (stride + 1):
        raise ValueError("truncated PNG image data")
    out = bytearray(h * stride)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i : i + stride])
        i += stride
        if f == 1:
            for x in range(stride):
                line[x] = (line[x] + (line[x - ch] if x >= ch else 0)) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                c = prev[x - ch] if x >= ch else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 255
        elif f != 0:
            raise ValueError(f"unsupported PNG filter {f}")
        out[y * stride : (y + 1) * stride] = line
        prev = line
    rgb = bytearray(w * h * 3)
    if ch == 3:
        rgb[:] = out
    elif ch == 1:
        for p in range(w * h):
            v = out[p]
            rgb[3 * p] = rgb[3 * p + 1] = rgb[3 * p + 2] = v
    elif ch == 2:
        for p in range(w * h):
            v = out[2 * p]
            rgb[3 * p] = rgb[3 * p + 1] = rgb[3 * p + 2] = v
    else:  # ch == 4
        for p in range(w * h):
            rgb[3 * p : 3 * p + 3] = out[4 * p : 4 * p + 3]
    return w, h, bytes(rgb)


def png_encode(w: int, h: int, rgb: bytes) -> bytes:
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride : (y + 1) * stride]
    return (
        PNG_SIG
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# Comparison core
# --------------------------------------------------------------------------


def _load_meta(path: Path) -> dict:
    meta = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "app", "window_title", "width", "height", "ui_state", "input",
        "capture_kind", "source",
    ):
        if key not in meta:
            raise ValueError(f"metadata missing required field '{key}'")
    if meta["app"] not in ("native", "port"):
        raise ValueError("metadata 'app' must be 'native' or 'port'")
    if meta["capture_kind"] not in ("mechanics", "acceptance"):
        raise ValueError("metadata 'capture_kind' must be 'mechanics' or 'acceptance'")
    if not isinstance(meta["source"], str) or not meta["source"].strip():
        raise ValueError("metadata 'source' must be a non-empty string (provenance)")
    # Acceptance captures MUST carry a content hash; mechanics captures may omit it.
    if meta["capture_kind"] == "acceptance":
        h = meta.get("sha256")
        if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("acceptance metadata needs a 64-hex 'sha256' of the PNG")
    return meta


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diff(native: bytes, port: bytes, w: int, h: int, tol: int):
    diff_pixels = 0
    max_delta = 0
    total_delta = 0
    diff_rgb = bytearray(native)
    for p in range(w * h):
        o = 3 * p
        dr = abs(native[o] - port[o])
        dg = abs(native[o + 1] - port[o + 1])
        db = abs(native[o + 2] - port[o + 2])
        worst = max(dr, dg, db)
        total_delta += dr + dg + db
        if worst > max_delta:
            max_delta = worst
        if worst > tol:
            diff_pixels += 1
            diff_rgb[o] = 255
            diff_rgb[o + 1] = 0
            diff_rgb[o + 2] = 0
    total = w * h
    mean_delta = (total_delta / (total * 3)) if total else 0.0
    return diff_pixels, total, mean_delta, max_delta, bytes(diff_rgb)


def cmd_compare(args) -> int:
    # --- P2a: reject meaningless tolerance arguments (usage error, never PASS) ---
    if not (0 <= args.channel_tolerance <= 255):
        print(f"usage error: --channel-tolerance must be 0..255, got {args.channel_tolerance}")
        return 3
    if not (0.0 <= args.max_diff_ratio <= 1.0):
        print(f"usage error: --max-diff-ratio must be 0.0..1.0, got {args.max_diff_ratio}")
        return 3

    native_p = Path(args.native)
    port_p = Path(args.port)
    native_m = Path(args.native_meta)
    port_m = Path(args.port_meta)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "tool": TOOL,
        "version": VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tolerance": {
            "channel": args.channel_tolerance,
            "max_diff_ratio": args.max_diff_ratio,
        },
    }

    def blocked(reason: str) -> int:
        report["result"] = "BLOCKED"
        report["reason"] = reason
        # P2: a BLOCKED report can never claim G9-evidence eligibility.
        # (A comparison FAIL is different -- it is a valid negative finding
        # and may keep g9_evidence: true. Only BLOCKED is forced to false.)
        report["g9_evidence"] = False
        report.setdefault("evidence_kind", "unknown")
        _write_report(out_dir, report)
        print(f"BLOCKED: {reason}")
        return 2

    # --- gather inputs (missing/unreadable => BLOCKED, never fabricated) ---
    for label, p in (("native", native_p), ("port", port_p)):
        if not p.is_file():
            return blocked(f"missing {label} screenshot: {p}")
    for label, p in (("native", native_m), ("port", port_m)):
        if not p.is_file():
            return blocked(f"missing {label} metadata: {p}")
    try:
        nm = _load_meta(native_m)
        pm = _load_meta(port_m)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        return blocked(f"bad metadata: {exc}")

    # --- P1b: metadata must be on the correct side ---
    if nm["app"] != "native":
        return blocked(f"native metadata declares app={nm['app']!r} (expected 'native')")
    if pm["app"] != "port":
        return blocked(f"port metadata declares app={pm['app']!r} (expected 'port')")

    # --- P2b: catch any corrupt-data exception as BLOCKED (zlib.error, EOFError,
    # MemoryError, struct.error, ... are all "unusable evidence", not crashes) ---
    try:
        nw, nh, npx = png_decode(native_p)
        pw, ph, ppx = png_decode(port_p)
    except (ValueError, OSError, zlib.error, EOFError, struct.error, MemoryError) as exc:
        return blocked(f"cannot decode screenshot: {exc}")

    report["native"] = {"path": str(native_p), "meta": nm}
    report["port"] = {"path": str(port_p), "meta": pm}
    # Eligibility is decided LAST, only once every protocol check below has
    # passed (P2) -- never set True before that point. Concretely:
    #   * BLOCKED                     -> g9_evidence always False
    #   * FAIL (geometry mismatch)    -> False (protocol not equivalent; this
    #                                    check runs before provenance)
    #   * FAIL (diff ratio > tol)     -> may be True: the captures were
    #                                    equivalent and provenance verified, so
    #                                    a below-fidelity result is itself valid
    #                                    evidence a human should review.
    report["g9_evidence"] = False
    report["evidence_kind"] = "unknown"

    # --- protocol equivalence: meta must agree with images and each other ---
    if (nm["width"], nm["height"]) != (nw, nh):
        return blocked("native metadata dimensions disagree with its image")
    if (pm["width"], pm["height"]) != (pw, ph):
        return blocked("port metadata dimensions disagree with its image")
    if nm["ui_state"] != pm["ui_state"] or nm["input"] != pm["input"]:
        return blocked(
            "protocol mismatch: ui_state/input differ "
            f"(native ui_state={nm['ui_state']!r} input={nm['input']!r}; "
            f"port ui_state={pm['ui_state']!r} input={pm['input']!r})"
        )

    # --- geometry: a size mismatch is a real negative (FAIL), not a block ---
    report["geometry"] = {
        "native": [nw, nh],
        "port": [pw, ph],
        "match": (nw, nh) == (pw, ph),
    }
    if (nw, nh) != (pw, ph):
        report["metrics"] = None
        report["result"] = "FAIL"
        report["reason"] = f"geometry-mismatch: {nw}x{nh} vs {pw}x{ph}"
        _write_report(out_dir, report)
        # still preserve both originals as evidence
        _save(out_dir / "native.png", nw, nh, npx)
        _save(out_dir / "port.png", pw, ph, ppx)
        print(f"FAIL: {report['reason']} (pixel diff skipped)")
        return 1

    # --- P1a: evidence classification + provenance verification. Only run
    # once width/height/ui_state/input/geometry have all agreed above --
    # otherwise a protocol mismatch could coexist with g9_evidence: true. ---
    kinds = {nm["capture_kind"], pm["capture_kind"]}
    if "mechanics" in kinds:
        report["evidence_kind"] = "mechanics"
        report["g9_evidence"] = False
        report["evidence_note"] = (
            "mechanics capture(s) present — mechanics result, NOT G9 acceptance evidence"
        )
    else:
        # Both sides are self-declared "acceptance". What this block actually
        # verifies: (a) file integrity -- the PNG bytes on disk match the
        # sha256 recorded in the metadata at capture time, and (b) a
        # non-empty, not-obviously-synthetic `source` string is present.
        # It does NOT and CANNOT verify that the PNG was truly produced by
        # running the native application or the port -- that is an external
        # fact about provenance that no hash or string field can prove from
        # inside this tool. A determined caller can hand-write a conforming
        # sha256/source pair for any image, mechanics or not; this harness
        # has no way to detect that. See `selftest` case 11 and
        # `G9_HARNESS.md` §3.1/§6 for the explicit limitation.
        h_ok = True
        for label, meta, p in (("native", nm, native_p), ("port", pm, port_p)):
            actual = _sha256_file(p)
            if actual != meta["sha256"]:
                h_ok = False
                report.setdefault("provenance_errors", []).append(
                    f"{label} sha256 mismatch (meta {meta['sha256'][:12]}… vs file {actual[:12]}…)"
                )
            if meta["source"].strip().lower().startswith("synth"):
                h_ok = False
                report.setdefault("provenance_errors", []).append(
                    f"{label} source looks synthetic ({meta['source']!r})"
                )
        if not h_ok:
            return blocked(
                "provenance invalid: " + "; ".join(report["provenance_errors"])
            )
        report["evidence_kind"] = "acceptance-declared"
        report["g9_evidence"] = True
        report["evidence_note"] = (
            "file integrity (sha256) and a declared source string check out, and all "
            "protocol checks (dimensions/ui_state/input/geometry) agree. This does "
            "**NOT** prove the images were actually captured from the native app and "
            "the port -- only a human reviewing the actual screenshots, diff.png, and "
            "the capture circumstances can establish that. Treat as 'eligible for "
            "human review', not as a self-certifying G9 result."
        )

    diff_pixels, total, mean_delta, max_delta, diff_rgb = _diff(
        npx, ppx, nw, nh, args.channel_tolerance
    )
    ratio = diff_pixels / total if total else 0.0
    report["metrics"] = {
        "total_pixels": total,
        "diff_pixels": diff_pixels,
        "diff_ratio": round(ratio, 6),
        "max_channel_delta": max_delta,
        "mean_channel_delta": round(mean_delta, 4),
    }

    _save(out_dir / "native.png", nw, nh, npx)
    _save(out_dir / "port.png", nw, nh, ppx)
    _save(out_dir / "diff.png", nw, nh, diff_rgb)
    report["artifacts"] = {
        "native_png": str(out_dir / "native.png"),
        "port_png": str(out_dir / "port.png"),
        "diff_png": str(out_dir / "diff.png"),
    }

    if ratio <= args.max_diff_ratio:
        report["result"] = "PASS"
        report["reason"] = (
            f"diff_ratio {ratio:.6f} <= {args.max_diff_ratio} "
            f"(tol {args.channel_tolerance}/channel)"
        )
        report["pass_caveat"] = (
            "PASS is a quantitative threshold result under the configured "
            "tolerance. It does NOT by itself mean the UI is functionally "
            "equivalent: two images can pass while a small button or region "
            "still differs. Review the diff image and key UI regions."
        )
        _write_report(out_dir, report)
        print(f"PASS: {report['reason']}")
        print(f"  note: {report['pass_caveat']}")
        return 0

    report["result"] = "FAIL"
    report["reason"] = (
        f"diff_ratio {ratio:.6f} > {args.max_diff_ratio} "
        f"(tol {args.channel_tolerance}/channel)"
    )
    _write_report(out_dir, report)
    print(f"FAIL: {report['reason']}")
    return 1


def _save(path: Path, w: int, h: int, rgb: bytes) -> None:
    path.write_bytes(png_encode(w, h, rgb))


def _write_report(out_dir: Path, report: dict) -> None:
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(_report_md(report), encoding="utf-8")


def _report_md(r: dict) -> str:
    lines = [
        "# G9 screenshot-diff report",
        "",
        f"- tool: `{r['tool']}` v{r['version']}",
        f"- timestamp: {r.get('timestamp', '?')}",
        f"- **result: `{r['result']}`** — {r.get('reason', '')}",
        f"- evidence kind: **{r.get('evidence_kind', '?')}**",
        f"- eligible as G9 acceptance evidence: **{r.get('g9_evidence', False)}**",
        "",
    ]
    if r.get("evidence_note"):
        lines += [f"> {r['evidence_note']}", ""]
    if r.get("pass_caveat"):
        lines += [f"> **PASS caveat:** {r['pass_caveat']}", ""]
    if r.get("provenance_errors"):
        lines += ["## Provenance errors", ""]
        lines += [f"- {e}" for e in r["provenance_errors"]]
        lines.append("")
    if r.get("evidence_kind") == "mechanics":
        lines += [
            "> ⚠️ MECHANICS capture — this exercises the harness mechanics only.",
            "> It is **NOT** native-versus-port fidelity evidence and must not be",
            "> cited as a G9 result.",
            "",
        ]
    elif r.get("evidence_kind") == "acceptance-declared":
        lines += [
            "> ⚠️ **File integrity + declared source checked out — this is NOT proof",
            "> of real capture.** sha256 only shows the file matches what its own",
            "> metadata claims; `source` is an unverified human-supplied string. A",
            "> human must still review `native.png`/`port.png`/`diff.png` and the",
            "> actual capture circumstances before this counts as a G9 result.",
            "",
        ]
    tol = r.get("tolerance")
    if tol:
        lines += [
            "## Tolerance",
            f"- per-channel absolute tolerance: {tol['channel']}",
            f"- max diff ratio allowed: {tol['max_diff_ratio']}",
            "",
        ]
    for side in ("native", "port"):
        if side in r:
            lines += [f"## {side}", f"- path: `{r[side]['path']}`",
                      f"- meta: `{json.dumps(r[side]['meta'], ensure_ascii=False)}`", ""]
    if r.get("geometry"):
        g = r["geometry"]
        lines += [
            "## Geometry",
            f"- native: {g['native'][0]}x{g['native'][1]}",
            f"- port:   {g['port'][0]}x{g['port'][1]}",
            f"- match: {g['match']}",
            "",
        ]
    if r.get("metrics"):
        m = r["metrics"]
        lines += [
            "## Metrics",
            f"- total pixels: {m['total_pixels']}",
            f"- differing pixels: {m['diff_pixels']} (ratio {m['diff_ratio']})",
            f"- max channel delta: {m['max_channel_delta']}",
            f"- mean channel delta: {m['mean_channel_delta']}",
            "",
        ]
    if r.get("artifacts"):
        lines += ["## Artifacts", ""]
        for k, v in r["artifacts"].items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Capture (best-effort, Windows only). Failure => BLOCKED, never fabricated.
# --------------------------------------------------------------------------


def _capture_windows(title: str, hwnd: int | None):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    if not hwnd:
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            found: list[int] = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

            def cb(h, _l):
                n = user32.GetWindowTextLengthW(h)
                if n:
                    b = ctypes.create_unicode_buffer(n + 1)
                    user32.GetWindowTextW(h, b, n + 1)
                    if title.lower() in b.value.lower():
                        found.append(h)
                return True

            user32.EnumWindows(EnumProc(cb), 0)
            if not found:
                return None, f"no window title containing {title!r}"
            hwnd = found[0]

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None, "window has no area"

    hdc = user32.GetWindowDC(hwnd)
    if not hdc:
        return None, "GetWindowDC failed"
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    # P2b: PrintWindow returns BOOL — check it before trusting the bitmap.
    pw_ok = user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
    if not pw_ok:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, hdc)
        return None, "PrintWindow returned 0 (window did not render)"

    class BMIH(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth, bi.biHeight = w, -h  # top-down
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    if got == 0:
        return None, "GetDIBits failed"

    raw = buf.raw
    rgb = bytearray(w * h * 3)
    peak = 0
    for p in range(w * h):
        b_, g_, r_ = raw[4 * p], raw[4 * p + 1], raw[4 * p + 2]
        rgb[3 * p], rgb[3 * p + 1], rgb[3 * p + 2] = r_, g_, b_
        if r_ > peak:
            peak = r_
        if g_ > peak:
            peak = g_
        if b_ > peak:
            peak = b_
    if peak == 0:
        return None, "capture is all-black (PrintWindow unsupported for this window)"
    return (w, h, bytes(rgb)), None


def cmd_capture(args) -> int:
    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        print("BLOCKED: capture is Windows-only in this harness")
        return 2
    try:
        result, err = _capture_windows(args.title, args.hwnd)
    except Exception as exc:  # pragma: no cover - platform dependent
        result, err = None, f"capture raised {exc!r}"
    if result is None:
        print(f"BLOCKED: {err}")
        return 2
    if args.capture_kind == "acceptance" and not args.source:
        print("BLOCKED: --capture-kind acceptance requires --source (provenance)")
        return 2
    w, h, rgb = result
    _save(out_p, w, h, rgb)
    source = args.source or "live capture via g9_screenshot_diff capture (mechanics)"
    meta = {
        "app": args.app,
        "window_title": args.window_title or args.title,
        "width": w,
        "height": h,
        "ui_state": args.ui_state,
        "input": args.input,
        "capture_kind": args.capture_kind,
        "source": source,
        # content hash of the PNG actually written — verifiable provenance
        "sha256": _sha256_file(out_p),
    }
    (out_p.with_suffix(".json")).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"OK: captured {w}x{h} -> {out_p} (+ {out_p.with_suffix('.json').name}, "
          f"kind={args.capture_kind})")
    return 0


# --------------------------------------------------------------------------
# Synthetic fixtures + self-test (mechanics only)
# --------------------------------------------------------------------------


def _solid(w: int, h: int, rgb: tuple[int, int, int]) -> bytes:
    return bytes(rgb) * (w * h)


def _with_block(w: int, h: int, base, x0, y0, bw, bh, block) -> bytes:
    buf = bytearray(_solid(w, h, base))
    for y in range(y0, min(y0 + bh, h)):
        for x in range(x0, min(x0 + bw, w)):
            o = 3 * (y * w + x)
            buf[o : o + 3] = bytes(block)
    return bytes(buf)


def _write_meta(
    path: Path,
    app,
    w,
    h,
    ui_state="main",
    inp="none",
    capture_kind="mechanics",
    source="synthetic fixture (harness mechanics only)",
    png: Path | None = None,
    sha256: str | None = None,
):
    meta = {
        "app": app,
        "window_title": f"{app}-synth" if capture_kind == "mechanics" else f"{app}",
        "width": w,
        "height": h,
        "ui_state": ui_state,
        "input": inp,
        "capture_kind": capture_kind,
        "source": source,
    }
    if sha256:
        meta["sha256"] = sha256
    elif png is not None:
        meta["sha256"] = _sha256_file(png)
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _run_compare_quiet(native, port, nmeta, pmeta, out, tol, ratio) -> int:
    ns = argparse.Namespace(
        native=str(native), port=str(port), native_meta=str(nmeta),
        port_meta=str(pmeta), out=str(out), channel_tolerance=tol,
        max_diff_ratio=ratio,
    )
    return cmd_compare(ns)


def cmd_make_sample(args) -> int:
    """Generate synthetic fixtures + one PASS/one FAIL/one BLOCKED report.

    These are MECHANICS demonstrations, tagged synthetic, never G9 evidence.
    """
    base = Path(args.out)
    base.mkdir(parents=True, exist_ok=True)
    W, H = 64, 48
    base_rgb = (40, 44, 52)

    # PASS case: identical images
    a = base / "pass_native.png"
    b = base / "pass_port.png"
    _save(a, W, H, _solid(W, H, base_rgb))
    _save(b, W, H, _solid(W, H, base_rgb))
    _write_meta(base / "pass_native.json", "native", W, H)
    _write_meta(base / "pass_port.json", "port", W, H)
    rc_pass = _run_compare_quiet(
        a, b, base / "pass_native.json", base / "pass_port.json",
        base / "pass_out", 4, 0.005,
    )

    # FAIL case: a 10x10 block differs beyond tolerance (~3.3% of pixels)
    c = base / "fail_native.png"
    d = base / "fail_port.png"
    _save(c, W, H, _solid(W, H, base_rgb))
    _save(d, W, H, _with_block(W, H, base_rgb, 5, 5, 10, 10, (255, 255, 255)))
    _write_meta(base / "fail_native.json", "native", W, H)
    _write_meta(base / "fail_port.json", "port", W, H)
    rc_fail = _run_compare_quiet(
        c, d, base / "fail_native.json", base / "fail_port.json",
        base / "fail_out", 4, 0.005,
    )

    # BLOCKED case: protocol metadata mismatch (ui_state differs)
    e = base / "blocked_native.png"
    f = base / "blocked_port.png"
    _save(e, W, H, _solid(W, H, base_rgb))
    _save(f, W, H, _solid(W, H, base_rgb))
    _write_meta(base / "blocked_native.json", "native", W, H, ui_state="main")
    _write_meta(base / "blocked_port.json", "port", W, H, ui_state="options")
    rc_blocked = _run_compare_quiet(
        e, f, base / "blocked_native.json", base / "blocked_port.json",
        base / "blocked_out", 4, 0.005,
    )

    ok = (rc_pass, rc_fail, rc_blocked) == (0, 1, 2)
    print(f"make-sample: PASS={rc_pass} FAIL={rc_fail} BLOCKED={rc_blocked} "
          f"({'ok' if ok else 'UNEXPECTED'}) -> {base}")
    return 0 if ok else 3


def cmd_selftest(args) -> int:
    import tempfile

    cases: list[tuple[str, bool]] = []

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        W, H = 32, 24
        base_rgb = (10, 20, 30)

        def img(name, rgb):
            p = t / f"{name}.png"
            _save(p, W, H, rgb)
            return p

        def meta(name, app, ui="main", inp="none"):
            p = t / f"{name}.json"
            _write_meta(p, app, W, H, ui_state=ui, inp=inp)
            return p

        # 1. identical -> PASS (exit 0)
        n = img("n1", _solid(W, H, base_rgb))
        p = img("p1", _solid(W, H, base_rgb))
        rc = _run_compare_quiet(n, p, meta("n1", "native"), meta("p1", "port"),
                                t / "o1", 4, 0.005)
        cases.append(("identical -> PASS", rc == 0))

        # 2. small difference within tolerance -> PASS
        p = img("p2", _with_block(W, H, base_rgb, 0, 0, 2, 2, (14, 20, 30)))
        rc = _run_compare_quiet(n, p, meta("n1", "native"), meta("p2", "port"),
                                t / "o2", 8, 0.9)  # loose
        cases.append(("within tolerance -> PASS", rc == 0))

        # 3. large difference -> FAIL (exit 1)
        p = img("p3", _with_block(W, H, base_rgb, 0, 0, 16, 16, (255, 255, 255)))
        rc = _run_compare_quiet(n, p, meta("n1", "native"), meta("p3", "port"),
                                t / "o3", 4, 0.005)
        cases.append(("beyond tolerance -> FAIL", rc == 1))

        # 4. missing native file -> BLOCKED (exit 2)
        rc = _run_compare_quiet(t / "nope.png", p, meta("n1", "native"),
                                meta("p3", "port"), t / "o4", 4, 0.005)
        cases.append(("missing input -> BLOCKED", rc == 2))

        # 5. ui_state mismatch -> BLOCKED (exit 2)
        n2 = img("n5", _solid(W, H, base_rgb))
        p5 = img("p5", _solid(W, H, base_rgb))
        rc = _run_compare_quiet(n2, p5, meta("n5", "native", ui="main"),
                                meta("p5", "port", ui="popup"), t / "o5", 4, 0.005)
        cases.append(("ui_state mismatch -> BLOCKED", rc == 2))

        # 6. dimension mismatch -> FAIL (exit 1), pixel diff skipped
        n6 = img("n6", _solid(W, H, base_rgb))
        p6 = t / "p6.png"
        _save(p6, W + 4, H, _solid(W + 4, H, base_rgb))
        _write_meta(t / "p6.json", "port", W + 4, H)
        rc = _run_compare_quiet(n6, p6, meta("n6", "native"), t / "p6.json",
                                t / "o6", 4, 0.005)
        cases.append(("geometry mismatch -> FAIL", rc == 1))

        # 7. mechanics tag propagates; NOT eligible as G9 evidence
        rep = json.loads((t / "o1" / "report.json").read_text())
        cases.append(("mechanics flagged, not G9 evidence",
                      rep["evidence_kind"] == "mechanics" and rep["g9_evidence"] is False))

        # 8. P1b: metadata on the wrong side -> BLOCKED
        n8 = img("n8", _solid(W, H, base_rgb))
        p8 = img("p8", _solid(W, H, base_rgb))
        _write_meta(t / "n8.json", "port", W, H)   # wrong side for native slot
        _write_meta(t / "p8.json", "port", W, H)
        rc = _run_compare_quiet(n8, p8, t / "n8.json", t / "p8.json", t / "o8", 4, 0.05)
        cases.append(("wrong-side metadata -> BLOCKED", rc == 2))

        # 9. P2a: out-of-range channel tolerance -> usage error (exit 3)
        rc = _run_compare_quiet(n8, p8, meta("n1", "native"), meta("p1", "port"),
                                t / "o9", 300, 0.05)
        cases.append(("channel-tolerance out of range -> usage error", rc == 3))

        # 10. P2a: out-of-range ratio -> usage error (exit 3)
        rc = _run_compare_quiet(n8, p8, meta("n1", "native"), meta("p1", "port"),
                                t / "o10", 4, 1.5)
        cases.append(("max-diff-ratio out of range -> usage error", rc == 3))

        # 11. P1: a self-built image with a correctly-computed hash and a
        # plausible-looking `source` string passes the declared-provenance
        # check -- THIS IS THE DOCUMENTED LIMITATION, not a guarantee of real
        # capture. The tool can only verify file integrity + a human-supplied
        # claim, never that the bytes truly came from running the native app
        # or the port. Hence the label is `acceptance-declared`, and the
        # report explicitly says a human must still review the artifacts.
        na = img("na", _solid(W, H, base_rgb))
        pa = img("pa", _solid(W, H, base_rgb))
        _write_meta(t / "na.json", "native", W, H, capture_kind="acceptance",
                    source="QTranslate.exe 6.10.0 on Win11, ui_state=main",
                    png=na)
        _write_meta(t / "pa.json", "port", W, H, capture_kind="acceptance",
                    source="qtranslate port build on Win11, ui_state=main",
                    png=pa)
        rc = _run_compare_quiet(na, pa, t / "na.json", t / "pa.json", t / "o11", 4, 0.05)
        rep = json.loads((t / "o11" / "report.json").read_text())
        cases.append((
            "declared-provenance (NOT proof of real capture) -> PASS, human review required",
            rc == 0 and rep["evidence_kind"] == "acceptance-declared"
            and rep["g9_evidence"] is True
            and "NOT" in rep["evidence_note"]
        ))

        # 12. acceptance whose file hash does not match meta -> BLOCKED,
        # g9_evidence must be False (file integrity actually failed here)
        na2 = img("na2", _solid(W, H, base_rgb))
        pa2 = img("pa2", _solid(W, H, base_rgb))
        _write_meta(t / "na2.json", "native", W, H, capture_kind="acceptance",
                    source="QTranslate.exe capture", sha256="0" * 64)
        _write_meta(t / "pa2.json", "port", W, H, capture_kind="acceptance",
                    source="port capture", sha256="1" * 64)
        rc = _run_compare_quiet(na2, pa2, t / "na2.json", t / "pa2.json", t / "o12", 4, 0.05)
        rep = json.loads((t / "o12" / "report.json").read_text())
        cases.append(("acceptance hash mismatch -> BLOCKED, g9_evidence False",
                      rc == 2 and rep["g9_evidence"] is False))

        # 13. P2b: corrupt PNG (truncated) -> BLOCKED, not a crash
        nb = t / "nb.png"
        nb.write_bytes(PNG_SIG + b"\x00\x00\x00\x0dIHDR" + b"\x00\x00\x00\x20")  # trunc
        _write_meta(t / "nb.json", "native", W, H)
        rc = _run_compare_quiet(nb, p8, t / "nb.json", meta("p1", "port"),
                                t / "o13", 4, 0.05)
        cases.append(("corrupt PNG -> BLOCKED (no crash)", rc == 2))

        # 14. P2: valid hashes/source (would pass provenance) but protocol
        # mismatch (ui_state differs) -> must be BLOCKED with g9_evidence
        # False: a BLOCKED report must never carry g9_evidence: true.
        nc = img("nc", _solid(W, H, base_rgb))
        pc = img("pc", _solid(W, H, base_rgb))
        _write_meta(t / "nc.json", "native", W, H, ui_state="main",
                    capture_kind="acceptance", source="QTranslate.exe capture", png=nc)
        _write_meta(t / "pc.json", "port", W, H, ui_state="popup",
                    capture_kind="acceptance", source="port capture", png=pc)
        rc = _run_compare_quiet(nc, pc, t / "nc.json", t / "pc.json", t / "o14", 4, 0.05)
        rep = json.loads((t / "o14" / "report.json").read_text())
        cases.append((
            "valid hash but protocol mismatch -> BLOCKED, g9_evidence False (no contradiction)",
            rc == 2 and rep["result"] == "BLOCKED" and rep["g9_evidence"] is False
        ))

        # 15. P2 wording: a diff-ratio FAIL on equivalent acceptance captures
        # KEEPS g9_evidence: true -- a below-fidelity result is valid evidence.
        nf = img("nf", _solid(W, H, base_rgb))
        pf = img("pf", _with_block(W, H, base_rgb, 0, 0, 16, 16, (255, 255, 255)))
        _write_meta(t / "nf.json", "native", W, H, capture_kind="acceptance",
                    source="QTranslate.exe capture", png=nf)
        _write_meta(t / "pf.json", "port", W, H, capture_kind="acceptance",
                    source="port capture", png=pf)
        rc = _run_compare_quiet(nf, pf, t / "nf.json", t / "pf.json", t / "o15", 4, 0.005)
        rep = json.loads((t / "o15" / "report.json").read_text())
        cases.append((
            "diff-ratio FAIL keeps g9_evidence True (valid negative evidence)",
            rc == 1 and rep["result"] == "FAIL" and rep["g9_evidence"] is True
        ))

    width = max(len(c[0]) for c in cases) + 4
    all_ok = True
    for name, ok in cases:
        print(f"  {name:<{width}} {'ok' if ok else 'FAIL'}")
        all_ok &= ok
    print(f"selftest: {'PASS' if all_ok else 'FAIL'} "
          f"({sum(1 for _, o in cases if o)}/{len(cases)} cases ok)")
    return 0 if all_ok else 3


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="G9 screenshot-diff harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="compare a native and a port screenshot")
    c.add_argument("--native", required=True)
    c.add_argument("--port", required=True)
    c.add_argument("--native-meta", required=True)
    c.add_argument("--port-meta", required=True)
    c.add_argument("--out", required=True, help="output directory")
    c.add_argument("--channel-tolerance", type=int, default=4,
                   help="per-channel absolute tolerance (0..255), default 4")
    c.add_argument("--max-diff-ratio", type=float, default=0.005,
                   help="max fraction of differing pixels for PASS, default 0.005")
    c.set_defaults(func=cmd_compare)

    k = sub.add_parser("capture", help="best-effort window capture (Windows)")
    k.add_argument("--title", required=True, help="window title (substring)")
    k.add_argument("--window-title", default=None)
    k.add_argument("--hwnd", type=int, default=None)
    k.add_argument("--app", choices=["native", "port"], required=True)
    k.add_argument("--ui-state", default="unspecified")
    k.add_argument("--input", default="none")
    k.add_argument("--capture-kind", choices=["mechanics", "acceptance"],
                   default="mechanics",
                   help="acceptance captures carry provenance (source + sha256)")
    k.add_argument("--source", default=None,
                   help="provenance text; required for --capture-kind acceptance")
    k.add_argument("--out", required=True, help="output png path")
    k.set_defaults(func=cmd_capture)

    s = sub.add_parser("selftest", help="run harness mechanics self-test")
    s.set_defaults(func=cmd_selftest)

    m = sub.add_parser("make-sample", help="write synthetic PASS/FAIL/BLOCKED sample")
    m.add_argument("--out", required=True)
    m.set_defaults(func=cmd_make_sample)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
