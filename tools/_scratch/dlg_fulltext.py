"""Full control TEXT for every dialog (dlg_parse truncates at 15 chars)."""
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location(
    "dp", "/Users/tranquangdang21/Projects/QTranslate/tools/dlg_parse.py")
dp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dp)

EXE = "/Users/tranquangdang21/Projects/QTranslate/docs/review/artifacts/QTranslate.6.10.0.exe"
blob = open(EXE, "rb").read()
dialogs, raw, rva_base = dp._dialogs(blob)
cur = dp._Cursor(blob[raw:raw + 0x13600], rva_base)
IDS = [171, 172, 173, 174, 175, 176, 179, 185, 190, 205, 129, 154, 164, 162]
out = {}
for did in IDS:
    rva, size = dialogs[did]
    hdr, ctrls = dp.parse_template(cur, rva - rva_base)
    rows = []
    for c in ctrls:
        rows.append((c["id"], c["class"], c["text"]))
    out[did] = rows
    print("### DLG", did, hdr.get("title", ""))
    for cid, cls, txt in rows:
        print("   %-6s %-22s %r" % (cid, cls, txt))
import json
open("/Users/tranquangdang21/Projects/QTranslate/tools/_scratch/dlg_text.json","w").write(json.dumps(out, indent=1))
