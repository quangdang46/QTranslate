"""Measure which theme colour slots the port can actually read.

Answers, from the seven themes in the NSIS payload rather than from a
decompilation: for each section, how many colour values exist, how many the
port's _STATE_SLOTS model can read, which key names it therefore misses, and
which states each section defines.
"""
import json
import re
import sys

PAYLOAD = "docs/review/artifacts/nsis_payload_unpacked.bin"
OFFSET = 0x97b30

# What qtranslate/theme.py reads today: one tuple applied to every section.
PORT_SLOTS = ("Back", "Text", "Border", "BorderInner", "Caption")

# FUN_00464c2f's states for the sections that matter.
STATES = ("Normal", "Disabled", "Hover", "Pressed", "Focused")


def load_themes():
    data = open(PAYLOAD, "rb").read()
    off = OFFSET
    out = []
    for _ in range(7):
        ln = int.from_bytes(data[off:off + 4], "little")
        body = data[off + 4:off + 4 + ln].decode("utf-8")
        out.append(json.loads(re.sub(r"//[^\n]*", "", body)))
        off += 4 + ln
    return out


def main():
    themes = load_themes()
    print("themes recovered: %d" % len(themes))

    for sec in ("Window", "WindowButton", "Button", "Edit", "Icon"):
        total = readable = 0
        missing = {}
        states = set()
        for t in themes:
            body = t.get(sec) or {}
            for st in STATES:
                rec = body.get(st)
                if isinstance(rec, dict):
                    states.add(st)
                src = rec if isinstance(rec, dict) else body.get("Normal", {})
                if not isinstance(src, dict):
                    continue
                for k, v in src.items():
                    total += 1
                    if k in PORT_SLOTS:
                        readable += 1
                    else:
                        missing[k] = missing.get(k, 0) + 1
        if total == 0:
            print("%-13s no colour values in any theme" % sec)
            continue
        status = "no reader in theme.py" if sec not in (
            "Window",) else "read (the one correct section)"
        print("\n%-13s %d values, %d readable, %d unreadable"
              % (sec, total, readable, total - readable))
        print("   states defined: %s" % (sorted(states) or "none"))
        print("   port model    : %s" % (list(PORT_SLOTS),))
        print("   keys missed    : %s" % (
            ", ".join("%s x%d" % kv for kv in sorted(missing.items())) or "none"))
        print("   port status   : %s" % status)

    return 0


if __name__ == "__main__":
    sys.exit(main())
