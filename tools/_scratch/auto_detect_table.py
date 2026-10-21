"""Derive native's per-service `usesAutoDetectCode` truth table.

Native asks each service whether it accepts an auto source by calling the
JS hook `usesAutoDetectCode`. That hook is not a per-service function: it is
a *framework* function in `Services/Common.js`

    function usesAutoDetectCode(){
        return SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE
    }

with `AUTO_DETECT_LANGUAGE = 1` and `UNKNOWN_LANGUAGE_CODE = -1`
(`Services/Common.js`, the `var SupportedLanguages=null,UNKNOWN_LANGUAGE_CODE=-1,
UNKNOWN_LANGUAGE=0,AUTO_DETECT_LANGUAGE=1,ENGLISH_LANGUAGE=17;` declaration).

`SupportedLanguages` is the per-service language table, so the answer is
"does this service's own table hold a real code in slot 1?".

When the hook cannot be called or does not return a boolean, native leaves the
request's auto-detect flag unset, and the translate stage then detects the
language itself. The default is therefore *detect yourself*.

This script reads the recovered JS and prints the table. It does not edit the
port.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("docs/review/rea/js_root")
AUTO_DETECT_LANGUAGE = 1
UNKNOWN_LANGUAGE_CODE = -1


def split_top_level(text: str) -> list[str]:
    """Split a JS array literal's body on top-level commas."""
    out, depth, cur, quote = [], 0, [], None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def find_supported_languages(body: str) -> list[str] | None:
    """Extract the SupportedLanguages array literal, if the service has one."""
    for match in re.finditer(r"SupportedLanguages\s*=\s*\[", body):
        start = match.end()
        depth = 1
        i = start
        quote = None
        while i < len(body) and depth:
            ch = body[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return split_top_level(body[start:i])
            i += 1
    return None


def main() -> int:
    common = (ROOT / "Common.js").read_text(encoding="utf-8", errors="replace")
    hook = "usesAutoDetectCode" in common
    print(f"Common.js defines usesAutoDetectCode: {hook}")
    for const, expect in (("AUTO_DETECT_LANGUAGE", AUTO_DETECT_LANGUAGE),
                          ("UNKNOWN_LANGUAGE_CODE", UNKNOWN_LANGUAGE_CODE)):
        found = re.search(rf"{const}\s*=\s*(-?\d+)", common)
        actual = int(found.group(1)) if found else None
        print(f"  {const} = {actual} (expected {expect}) "
              f"{'ok' if actual == expect else 'MISMATCH'}")
    if not hook:
        print("no hook -> native default is detect-yourself", file=sys.stderr)

    table = []
    for svc in sorted((ROOT / "Services").iterdir()):
        body = (svc / "Service.js").read_text(encoding="utf-8", errors="replace")
        langs = find_supported_languages(body)
        if langs is None:
            table.append({"service": svc.name, "slot": None, "uses_auto": False,
                          "note": "no SupportedLanguages table"})
            continue
        slot = langs[AUTO_DETECT_LANGUAGE] if len(langs) > AUTO_DETECT_LANGUAGE else None
        raw = slot.strip() if isinstance(slot, str) else slot
        if isinstance(raw, str):
            try:
                value = int(raw)
            except ValueError:
                value = raw
        else:
            value = raw
        uses = value is not None and value != UNKNOWN_LANGUAGE_CODE
        table.append({"service": svc.name, "slot": value, "uses_auto": uses,
                      "table_len": len(langs)})

    print()
    print(f"{'service':34s} {'slot[1]':>10s}  usesAutoDetectCode")
    for row in table:
        print(f"{row['service']:34s} {str(row['slot']):>10s}  {row['uses_auto']}")
    auto = [r["service"] for r in table if r["uses_auto"]]
    print()
    print(f"services answering TRUE ({len(auto)}): {', '.join(auto)}")
    out = Path("docs/review/rea/uses_auto_detect_table.json")
    out.write_text(json.dumps({"hook_in_common_js": hook,
                               "auto_detect_language_index": AUTO_DETECT_LANGUAGE,
                               "unknown_language_code": UNKNOWN_LANGUAGE_CODE,
                               "services": table}, indent=1) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
