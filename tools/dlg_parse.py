"""Parse DLGTEMPLATEEX resources from QTranslate.exe (run via uv)."""
import pefile
import struct
import sys

CLS = {0x0080: "Button", 0x0081: "Edit", 0x0082: "Static",
       0x0083: "ListBox", 0x0084: "ScrollBar", 0x0085: "ComboBox"}
BTN_STYLE = {0x0: "PUSHBUTTON", 0x1: "DEFPUSHBUTTON", 0x2: "CHECKBOX",
             0x3: "AUTOCHECKBOX", 0x4: "RADIOBUTTON", 0x5: "AUTORADIOBUTTON",
             0x7: "GROUPBOX", 0x8: "USERBUTTON", 0x9: "AUTO3STATE",
             0xB: "ICON", 0xC: "BITMAP", 0xD: "LEFT_TEXT", 0xE: "RIGHTBUTTON"}


def wz(d, o):
    e = d.find(b"\x00\x00", o)
    if e < 0:
        return "", len(d)
    return d[o:e].decode("utf-16-le", errors="replace"), e + 2


def parse(exe, dlg_id):
    pe = pefile.PE(exe)
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id != 5:
            continue
        for d in t.directory.entries:
            if d.id != dlg_id:
                continue
            for lang in d.directory.entries:
                data = pe.get_data(lang.data.struct.OffsetToData,
                                   lang.data.struct.Size)
                ver, sig, hlp, ex, st, cdit, x, y, cx, cy = \
                    struct.unpack_from("<HHIIIHHHHH", data, 0)
                o = 22
                for _ in range(3):
                    if data[o:o + 2] == b"\x00\x00":
                        o += 2
                    elif data[o:o + 2] == b"\xff\xff":
                        o += 4
                    else:
                        _, o = wz(data, o)
                o = (o + 3) // 4 * 4
                print(f"DLG {dlg_id}: n={cdit} {cx}x{cy} style={st:08x}")
                for i in range(cdit):
                    o = (o + 3) // 4 * 4
                    h2, e2, s2, x2, y2, cx2, cy2, cid = \
                        struct.unpack_from("<IIIHHHHI", data, o)
                    o += 24
                    if data[o:o + 2] == b"\xff\xff":
                        cc = struct.unpack_from("<H", data, o + 2)[0]
                        cls = CLS.get(cc, "sys%02x" % cc)
                        o += 4
                    else:
                        cls, o = wz(data, o)
                    if data[o:o + 2] == b"\x00\x00":
                        txt = ""
                        o += 2
                    else:
                        txt, o = wz(data, o)
                    o += 2  # extra creation data word
                    extra = ""
                    if isinstance(cls, str) and cls == "Button":
                        extra = " type=" + BTN_STYLE.get(s2 & 0xF, "?")
                    safe_cls = str(cls).encode(
                        "ascii", "replace").decode()
                    safe_txt = txt.encode("ascii", "replace").decode()
                    print(f"  {i}: {safe_cls} id={cid & 0xffff} "
                          f"style={s2:08x}{extra} "
                          f"{cx2}x{cy2}@{x2},{y2} txt={safe_txt!r}")


if __name__ == "__main__":
    parse(sys.argv[1], int(sys.argv[2]))
