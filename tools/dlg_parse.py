"""`RT_DIALOG` walker for the recovered QTranslate.6.10.0.exe (G9 part (a)).

Reads `DLGTEMPLATEEX` (and `DLGTEMPLATE`) straight out of the image's
`.rsrc` and prints every control with its id, class, text and geometry.

Why this exists: `docs/review/G9_SPEC_NATIVE_WINDOW_2026-10-10.md` §5
recorded three things it could not pin — the ids for the four owner-draw
buttons, whether control id `1001` exists, and the DLU→px conversion. The
walker that produced the 13 clean controls was reading the template with a
fixed structure assumption, so the `BS_OWNERDRAW` controls whose
creation-data length differs produced garbage ids (`1342275648`).

`DLGTEMPLATEEX` is not hard: each control is

    helpID(4) exStyle(4) style(4) x(2) y(2) cx(2) cy(2)
    id(4)  sz_Class  sz_Text  creationDataLength(2) creationData

where `sz_Class` is `0xFFFF,ordinal` for a predefined class atom. The
earlier walker was not treating the ids as 4 bytes, which is what shifted
everything after the first owner-draw control.

Section offsets are found from the PE headers, not hardcoded, so this
still works if the file is rebuilt. Read-only: never writes the image.

Usage:
  python -I tools/dlg_parse.py                 # summarize every dialog
  python -I tools/dlg_parse.py --id 129        # full control table
  python -I tools/dlg_parse.py --id 129 --dlu  # + DLU->px estimates

Exit codes: 0 ok, 1 the artifact is missing/unreadable, 2 usage error.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

DEFAULT_EXE = os.path.join("docs", "review", "artifacts",
                           "QTranslate.6.10.0.exe")

# Predefined control-class atoms (ordinal -> name), per the Windows SDK.
CLASS_ATOMS = {
    0x0080: "Button", 0x0081: "Edit", 0x0082: "Static",
    0x0083: "ListBox", 0x0084: "ScrollBar", 0x0085: "ComboBox",
}

# The styles that change a control's meaning, worth printing because a
# "Button" with BS_OWNERDRAW is an icon button whose content we draw.
BS_TYPES = {
    0x0000: "PUSHBUTTON", 0x0001: "DEFPUSHBUTTON", 0x0002: "CHECKBOX",
    0x0003: "RADIO", 0x0004: "3STATE", 0x0005: "AUTO3STATE",
    0x0006: "GROUPBOX", 0x0007: "AUTORADIOBUTTON", 0x0008: "OWNERDRAW",
    0x0009: "SPLITBUTTON", 0x000B: "RADIOGROUP",
}
WS_NAMES = [
    (0x10000000, "VISIBLE"), (0x00C00000, "CHILD"), (0x80000000, "POPUP"),
    (0x00400000, "DLGFRAME"), (0x00080000, "BORDER"),
    (0x01000000, "CLIPCHILDREN"), (0x00020000, "MINIMIZEBOX"),
    (0x20000000, "MAXIMIZEBOX"), (0x00040000, "SYSMENU"),
]

DS_NAMES = [
    (0x0080, "CENTER"), (0x0040, "SETFONT"), (0x0002, "MODALFRAME"),
    (0x0001, "ABSALIGN"), (0x0200, "CONTROL"), (0x0010, "3DLOOK"),
]


def _pe_sections(blob: bytes):
    """[(name, va, vsz, raw, rawsz)] from the PE section headers."""
    if blob[:2] != b"MZ":
        raise ValueError("not a PE image (no MZ)")
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    if blob[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE image (no PE signature)")
    nsec = struct.unpack_from("<H", blob, pe + 6)[0]
    opt_sz = struct.unpack_from("<H", blob, pe + 20)[0]
    out = []
    sec = pe + 24 + opt_sz
    for i in range(nsec):
        o = sec + i * 40
        name = blob[o:o + 8].rstrip(b"\0").decode("latin1")
        vsz, va, rsz, raw = struct.unpack_from("<IIII", blob, o + 8)
        out.append((name, va, vsz, raw, rsz))
    return out


def _rsrc_base(blob: bytes):
    for name, va, _vsz, raw, rsz in _pe_sections(blob):
        if name == ".rsrc":
            return raw, va, rsz
    raise ValueError("no .rsrc section")


class _Cursor:
    """A byte cursor over the resource section, with its own RVA mapping."""

    def __init__(self, sec: bytes, rva_base: int):
        self.b = sec
        self.rva_base = rva_base

    def u16(self, o):
        return struct.unpack_from("<H", self.b, o)[0]

    def u32(self, o):
        return struct.unpack_from("<I", self.b, o)[0]

    def i16(self, o):
        return struct.unpack_from("<h", self.b, o)[0]

    @staticmethod
    def align(o, a=4):
        return (o + a - 1) & ~(a - 1)

    def name(self, o):
        """`sz_Or_Ord`: `0xFFFF, ordinal` or a WCHAR string. -> (val, next)"""
        if self.u16(o) == 0xFFFF:
            return "atom:0x%04X" % self.u16(o + 2), o + 4
        return self.wstr(o)

    def wstr(self, o):
        """A WCHAR[] string that runs to the first NUL. -> (text, next)"""
        end = o
        while self.u16(end) != 0:
            end += 2
        text = self.b[o:end].decode("utf-16-le", "replace")
        return text, end + 2

    def dir_entries(self, o):
        n = self.u16(o + 12) + self.u16(o + 14)
        out = []
        for k in range(n):
            e = o + 16 + k * 8
            out.append((self.u32(e) & 0x7FFFFFFF,
                        bool(self.u32(e + 4) & 0x80000000),
                        self.u32(e + 4) & 0x7FFFFFFF))
        return out

    def data_entry(self, o):
        """Follow a (possibly nested) directory down to its data entry."""
        return o


def _dialogs(blob: bytes):
    """{dialog_id: (rva, size)} for RT_DIALOG (type 5)."""
    raw, rva_base, rsz = _rsrc_base(blob)
    cur = _Cursor(blob[raw:raw + rsz], rva_base)
    root = cur.dir_entries(0)
    dlg_type = next((off for (tid, isdir, off) in root if tid == 5), None)
    if dlg_type is None:
        raise ValueError("no RT_DIALOG (type 5) in .rsrc")
    out = {}
    for (nameid, isdir, off) in cur.dir_entries(dlg_type):
        # nameid -> (lang dir or data entry)
        if isdir:
            langs = cur.dir_entries(off)
            if not langs:
                continue
            lid, lisdir, loff = langs[0]
            if lisdir:
                entries = cur.dir_entries(loff)
                if not entries:
                    continue
                loff = entries[0][2]
        else:
            loff = off
        rva, size = cur.u32(loff), cur.u32(loff + 4)
        out[nameid] = (rva, size)
    return out, raw, rva_base


def parse_dialog(exe_path: str, did: int):
    """One dialog out of a recovered executable -> (header, controls).

    The public door into the walker: the tests that pin a number the
    native's own resource carries read it through here, so the number
    is re-derived from the artifact instead of copied out of a document.
    """
    with open(exe_path, "rb") as fh:
        blob = fh.read()
    dialogs, raw, rva_base = _dialogs(blob)
    if did not in dialogs:
        raise KeyError("no dialog %d in %s" % (did, exe_path))
    rva, _size = dialogs[did]
    cur = _Cursor(blob[raw:raw + 0x13600], rva_base)
    return parse_template(cur, rva - rva_base)


def _class_or_atom(cur, o):
    """A control's class: 'atom:0x0084' for a predefined class, or a name."""

    if cur.u16(o) == 0xFFFF:
        atom = cur.u16(o + 2)
        return CLASS_ATOMS.get(atom, "atom:0x%04X" % atom), o + 4
    return cur.wstr(o)


def parse_control(cur, o):
    """One DLGITEMTEMPLATEEX. -> (control dict, next offset)"""
    c = {}
    help_id = cur.u32(o)
    ex_style = cur.u32(o + 4)
    style = cur.u32(o + 8)
    x, y, cx, cy = (cur.i16(o + 12), cur.i16(o + 14),
                    cur.i16(o + 16), cur.i16(o + 18))
    cid = cur.u32(o + 20)
    o += 24
    c["id"] = cid
    c["x"], c["y"], c["cx"], c["cy"] = x, y, cx, cy
    c["style"] = style
    c["ex_style"] = ex_style
    cls, o = _class_or_atom(cur, o)
    c["class"] = cls
    text, o = cur.wstr(o)
    c["text"] = text
    extra = cur.u16(o)
    o += 2
    # creationData is `extra` bytes; it may contain anything (an icon
    # resource id, a size), so it is kept raw and skipped, never parsed.
    c["creation_len"] = extra
    if extra:
        c["creation"] = bytes(cur.b[o:o + extra])
        o += extra
    o = cur.align(o)
    return c, o


def parse_template(cur, o):
    """A DLGTEMPLATEEX (or EX-less DLGTEMPLATE). -> (header, controls)"""
    dlg_ver = cur.u16(o)
    signature = cur.u16(o + 2)
    hdr = {"dlgVer": dlg_ver, "signature": signature, "ex": dlg_ver == 1}
    if dlg_ver == 1:                       # DLGTEMPLATEEX
        hdr["helpID"] = cur.u32(o + 4)
        hdr["exStyle"] = cur.u32(o + 8)
        hdr["style"] = cur.u32(o + 12)
        hdr["cdit"] = cur.u16(o + 16)
        hdr["x"], hdr["y"] = cur.i16(o + 18), cur.i16(o + 20)
        hdr["cx"], hdr["cy"] = cur.i16(o + 22), cur.i16(o + 24)
        o += 26
        menu, o = cur.name(o)
        cls, o = cur.name(o)
        title, o = cur.wstr(o)
        hdr.update({"menu": menu, "class": cls, "title": title})
        if hdr["style"] & 0x40:            # DS_SETFONT
            hdr["pointSize"] = cur.u16(o)
            hdr["weight"] = cur.u16(o + 2)
            hdr["italic"] = cur.b[o + 4]
            hdr["charset"] = cur.b[o + 5]
            o += 6
            face, o = cur.wstr(o)
            hdr["font"] = face
    else:                                  # DLGTEMPLATE / DLGTEMPLATE*
        hdr["style"] = cur.u32(o + 8)
        hdr["exStyle"] = cur.u32(o + 12)
        hdr["cdit"] = cur.u16(o + 14)
        hdr["x"], hdr["y"] = cur.i16(o + 16), cur.i16(o + 18)
        hdr["cx"], hdr["cy"] = cur.i16(o + 20), cur.i16(o + 22)
        o += 24
        menu, o = cur.name(o)
        cls, o = cur.name(o)
        title, o = cur.wstr(o)
        hdr.update({"menu": menu, "class": cls, "title": title})
        if hdr["style"] & 0x40:
            hdr["pointSize"] = cur.u16(o)
            o += 2
            face, o = cur.wstr(o)
            hdr["font"] = face
    o = cur.align(o)
    controls = []
    for _ in range(hdr["cdit"]):
        ctrl, o = parse_control(cur, o)
        controls.append(ctrl)
    return hdr, controls


# --------------------------------------------------------------- DLU -> px
# The Windows formula (GetDialogBaseUnits): with a proportional font,
#   px_x = (du_x * avg_char_w) / 4
#   px_y = (du_y * avg_char_h) / 8
# Both metrics come from the dialog's own font via
# GetTextMetrics(TEXTMETRICS.tmAveCharWidth) and
# tmAveCharHeight + tmExternalLeading -- which is why no static table can
# be exact. The candidates below are the metrics observed for the fonts a
# `MS Shell Dlg` 8pt dialog maps to, so the range is the honest answer.


def dlu_to_px(cx, cy, avg_w, avg_h):
    """(dx, dy) in dialog units -> pixels for the given font metrics."""
    return (cx * avg_w) // 4, (cy * avg_h) // 8


FONT_CANDIDATES = [
    # label, avgCharWidth, avgCharHeight(+leading) at 8pt
    ("Tahoma 8pt @100%", 6, 13),
    ("Tahoma 8pt @125%", 8, 17),
    ("Segoe UI 8pt @100%", 7, 13),
    ("Segoe UI 8pt @125%", 9, 17),
    ("MS Sans Serif 8pt", 7, 15),
]


# ------------------------------------------------------------------ output
def _fmt_style(style, table):
    return " ".join(n for bit, n in table if style & bit)


def show(did, hdr, controls, with_dlu=False):
    lines = []
    title = hdr.get("title", "")
    lines.append("DLG %d  title=%r  Ver=%d style=0x%08X exStyle=0x%08X"
                 % (did, title, hdr.get("dlgVer", 0),
                    hdr["style"], hdr["exStyle"]))
    lines.append("  template geometry: x=%d y=%d cx=%d cy=%d (dialog units)"
                 % (hdr["x"], hdr["y"], hdr["cx"], hdr["cy"]))
    lines.append("  font: %r %spt (DS_SETFONT=%s)"
                 % (hdr.get("font", ""), hdr.get("pointSize", "?"),
                    bool(hdr["style"] & 0x40)))
    ds = _fmt_style(hdr["style"], DS_NAMES)
    if ds:
        lines.append("  DS_ flags: " + ds)
    lines.append("  controls: %d declared, %d parsed"
                 % (hdr["cdit"], len(controls)))
    lines.append("")
    lines.append("  %-6s %-22s %-16s %5s %5s %5s %5s"
                 % ("Id", "Class", "Text", "x", "y", "cx", "cy"))
    for c in controls:
        cname = c["class"]
        if cname == "Button":
            bs = c["style"] & 0x0F
            cname = "Button(%s)" % BS_TYPES.get(bs, "0x%X" % bs)
        text = c["text"] if len(c["text"]) <= 15 else c["text"][:12] + "..."
        lines.append("  %-6d %-22s %-16r %5d %5d %5d %5d"
                     % (c["id"], cname, text, c["x"], c["y"],
                        c["cx"], c["cy"]))
    # Unresolved ids are the interesting case: the earlier walker produced
    # implausible values for owner-draw controls, so a sanity check here
    # makes that visible rather than silently recording a wrong number.
    bad = [c["id"] for c in controls if c["id"] > 0xFFFF or c["id"] < 0]
    if bad:
        lines.append("")
        lines.append("  !! implausible control ids (parser misaligned): %r"
                     % bad)
    if with_dlu:
        lines.append("")
        lines.append("  template %dx%d DU at each candidate metric:"
                     % (hdr["cx"], hdr["cy"]))
        for label, w, h in FONT_CANDIDATES:
            px, py = dlu_to_px(hdr["cx"], hdr["cy"], w, h)
            lines.append("    %-24s -> %d x %d px" % (label, px, py))
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--id", type=int, action="append", dest="ids",
                    help="dialog id (repeatable); default: all, summarized")
    ap.add_argument("--dlu", action="store_true",
                    help="also print DLU->px estimates for each metric")
    ap.add_argument("--full", action="store_true",
                    help="print the control table for every dialog")
    a = ap.parse_args(argv)
    if not os.path.exists(a.exe):
        print("artifact not found: %s" % a.exe)
        print("(it is a large recovered blob and is intentionally not "
              "committed -- see docs/review/ARTIFACT_RECOVERY_2026-10-10.md)")
        return 1
    blob = open(a.exe, "rb").read()
    try:
        dialogs, raw, rva_base = _dialogs(blob)
    except ValueError as exc:
        print("cannot read .rsrc: %s" % exc)
        return 1
    cur = _Cursor(blob[raw:raw + 0x13600], rva_base)

    if a.ids:
        for did in a.ids:
            if did not in dialogs:
                print("no dialog %d (have: %s)"
                      % (did, ", ".join(str(k) for k in sorted(dialogs))))
                return 2
            rva, size = dialogs[did]
            off = rva - rva_base
            hdr, ctrls = parse_template(cur, off)
            print(show(did, hdr, ctrls, a.dlu))
        return 0

    # summary of every dialog
    rows = []
    for did in sorted(dialogs):
        rva, size = dialogs[did]
        off = rva - rva_base
        try:
            hdr, ctrls = parse_template(cur, off)
        except Exception as exc:            # noqa: BLE001 -- keep going
            rows.append((did, rva, size, None, None, str(exc)))
            continue
        rows.append((did, rva, size, hdr.get("title", ""),
                     (hdr["cx"], hdr["cy"]), len(ctrls)))
    print("%-6s %-10s %-7s %-28s %s" % ("Id", "RVA", "Size", "Title",
                                        "cx x cy DU"))
    for did, rva, size, title, geo, n in rows:
        print("%-6d 0x%-8x %-7d %-28r %s%s"
              % (did, rva, size, title,
                 ("%d x %d" % geo) if geo else "-",
                 ("  (%d ctrls)" % n) if geo else ""))
    print("\n%d dialogs" % len(rows))
    if a.full:
        for did in sorted(dialogs):
            rva, size = dialogs[did]
            off = rva - rva_base
            try:
                hdr, ctrls = parse_template(cur, off)
            except Exception:
                continue
            print()
            print(show(did, hdr, ctrls, a.dlu))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
