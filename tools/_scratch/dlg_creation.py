import importlib.util, os, struct
spec = importlib.util.spec_from_file_location(
    "dp", "/Users/tranquangdang21/Projects/QTranslate/tools/dlg_parse.py")
dp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dp)
EXE = "/Users/tranquangdang21/Projects/QTranslate/docs/review/artifacts/QTranslate.6.10.0.exe"
blob = open(EXE, "rb").read()
dialogs, raw, rva_base = dp._dialogs(blob)
cur = dp._Cursor(blob[raw:raw + 0x13600], rva_base)
for did in (173, 175, 154, 129):
    rva, size = dialogs[did]
    hdr, ctrls = dp.parse_template(cur, rva - rva_base)
    print("### DLG", did)
    for c in ctrls:
        if c["creation_len"]:
            cd = c["creation"]
            words = struct.unpack("<%dH" % (len(cd)//2), cd[:len(cd)//2*2]) if len(cd)>=2 else ()
            print("   id=%-6s class=%-12s text=%-12r creation=%s words=%s"
                  % (c["id"], c["class"], c["text"], cd.hex(), words))
