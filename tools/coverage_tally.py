"""Coverage tally + validator for docs/RE_COVERAGE_CHECKLIST.md.

Two jobs:
  1. Regenerate the derived tally between <!-- TALLY:START --> / <!-- TALLY:END -->
     so header numbers can never drift from the rows (a hand-written header once
     drifted 118 -> 122 -> 123).
  2. VALIDATE the table: duplicate item ids, per-group count vs the locked
     inventory (catches a silently deleted row), missing/invalid RE state,
     missing/invalid Port state, unknown `dead:` slug, `UNRECOVERABLE` rows
     lacking `reason:`/`impact:`, and malformed waivers. These are structural
     errors and fail.
     Note: this checks counts against a hand-maintained EXPECTED_TOTALS, not
     "every conceivable feature exists" — it cannot know what was never listed.

WAIVERS (explicit, per-row, requires approval to add):
  A row may carry an explicit, approved exception so the Gate can account for it
  WITHOUT relabelling its honest RE state. Marker: a non-empty `WAIVER: <reason>`
  token anywhere in the row (the reason is mandatory). A waiver is only valid on
  an `INFERRED`/`UNKNOWN` row — waiving a `VERIFIED`/`UNRECOVERABLE` row is an
  error. Waived rows are reported SEPARATELY and NEVER counted as `VERIFIED`.
  The validator never assigns a waiver itself; waivers exist only if a human put
  them in the document. Absent a valid waiver, an INFERRED/UNKNOWN row blocks.

Exit codes:
  0  structure valid AND the Gate is open (every INFERRED/UNKNOWN row is either
     absent or carries a valid approved waiver)
  1  structure invalid (bad table, malformed waiver, invalid waiver target)
  2  structure valid but Gate BLOCKED (INFERRED/UNKNOWN rows lack a valid waiver)

Usage:
  python -I tools/coverage_tally.py           # regen + validate (default)
  python -I tools/coverage_tally.py --check    # validate only, no write
  python -I tools/coverage_tally.py --selftest # run built-in waiver tests
"""
import re
import sys
from collections import Counter, OrderedDict

DOC = "docs/RE_COVERAGE_CHECKLIST.md"

RE_STATES = ("VERIFIED", "INFERRED", "UNKNOWN", "UNRECOVERABLE")
GATE_OK_RE = ("VERIFIED", "UNRECOVERABLE")
WAIVABLE_RE = ("INFERRED", "UNKNOWN")
PORT_BASE = ("not-started", "analysed", "ported", "behaviour-verified")
DEAD_SLUGS = {"host-retired", "needs-session-token", "bot-walled",
              "native-unavailable"}

# Matches `WAIVER:` followed by the rest of the line (the reason).
_WAIVER_RE = re.compile(r"WAIVER:\s*(.*)", re.IGNORECASE)

# Locked inventory (enumeration evidence in RE_COVERAGE_CHECKLIST.md).
# This is a DELIBERATE hand-maintained expectation, not derived: it catches a
# row deleted from the doc without a matching inventory change. Bump it only
# when the locked inventory intentionally changes (with evidence).
EXPECTED_TOTALS = {"A": 9, "B": 6, "C": 10, "D": 11, "E": 22, "F": 13,
                   "G": 9, "H": 8, "I": 9, "J": 7, "K": 4, "L": 4,
                   "M": 23, "N": 4, "O": 4, "P": 3, "Q": 3, "R": 3}


def _port_state(cell: str):
    if cell in PORT_BASE:
        return cell, None
    if cell.startswith("dead:"):
        slug = cell.split(":", 1)[1]
        return "dead:*", (None if slug in DEAD_SLUGS else slug)
    return None, None


def parse(text: str):
    groups = OrderedDict()
    rows = []
    errors = []
    cur = None
    seen_ids = {}
    for lineno, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^## ([A-R])\. ", line)
        if m:
            cur = m.group(1)
            groups.setdefault(cur, 0)
            continue
        if not (cur and line.startswith("| ")):
            continue
        first = line.split("|")[1].strip()
        if not re.match(r"^[A-R]\d", first):
            continue
        item_id = re.match(r"^([A-R]\d+[a-z]?)", first).group(1)
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if item_id in seen_ids:
            errors.append(f"line {lineno}: duplicate id {item_id} "
                          f"(first at line {seen_ids[item_id]})")
        seen_ids[item_id] = lineno
        re_state = next((c for c in cells if c in RE_STATES), None)
        port_state, bad_slug = next(
            ((ps, bs) for ps, bs in (_port_state(c) for c in cells) if ps),
            (None, None))
        if re_state is None:
            errors.append(f"line {lineno}: {item_id} has no valid RE state")
        if port_state is None:
            errors.append(f"line {lineno}: {item_id} has no valid Port state")
        if bad_slug:
            errors.append(f"line {lineno}: {item_id} unknown dead slug "
                          f"'dead:{bad_slug}'")
        groups[cur] += 1
        # UNRECOVERABLE Gate condition: reason AND impact must be present.
        if re_state == "UNRECOVERABLE":
            blob = " ".join(cells).lower()
            if "reason:" not in blob:
                errors.append(f"line {lineno}: {item_id} UNRECOVERABLE "
                              f"missing 'reason:'")
            if "impact:" not in blob:
                errors.append(f"line {lineno}: {item_id} UNRECOVERABLE "
                              f"missing 'impact:'")
        # WAIVER parsing: explicit, per-row, reason mandatory, only on
        # INFERRED/UNKNOWN. Never auto-assigned.
        line_text = " ".join(cells)
        wm = _WAIVER_RE.search(line_text)
        waived = False
        if wm is not None:
            reason = wm.group(1).strip().rstrip("|").strip()
            if not reason:
                errors.append(f"line {lineno}: {item_id} WAIVER missing reason")
            elif re_state not in WAIVABLE_RE:
                errors.append(f"line {lineno}: {item_id} WAIVER on a "
                              f"{re_state} row (only {WAIVABLE_RE} may be "
                              f"waived)")
            else:
                waived = True
        rows.append((item_id, re_state, port_state, waived))
    # Missing-vs-inventory check: every expected id present, none extra.
    for g, expected in EXPECTED_TOTALS.items():
        got = groups.get(g, 0)
        if got != expected:
            errors.append(f"group {g}: {got} items but inventory expects "
                          f"{expected} (locked inventory)")
    for g in groups:
        if g not in EXPECTED_TOTALS:
            errors.append(f"group {g} not in locked inventory")
    return groups, rows, errors


def unresolved_rows(rows):
    """Rows blocking the Gate: INFERRED/UNKNOWN without a valid waiver."""
    return [r for r in rows if r[1] not in GATE_OK_RE and not r[3]]


def render(groups, rows) -> str:
    re_c = Counter(r[1] for r in rows)
    pt_c = Counter(r[2] for r in rows)
    waived_rows = [r for r in rows if r[3]]
    unresolved = unresolved_rows(rows)
    out = [f"**Total items: {len(rows)}**", ""]
    out.append("| RE state (native) | Count | | Port state (Python) | Count |")
    out.append("|---|---|---|---|---|")
    re_order = list(RE_STATES)
    pt_order = list(PORT_BASE) + ["dead:*"]
    for i in range(max(len(re_order), len(pt_order))):
        a = re_order[i] if i < len(re_order) else ""
        b = re_c.get(a, "") if a else ""
        c = pt_order[i] if i < len(pt_order) else ""
        d = pt_c.get(c, "") if c else ""
        out.append(f"| {a} | {b} | | {c} | {d} |")
    out.append("")
    out.append("| Group | Items |")
    out.append("|---|---|")
    out += [f"| {g} | {groups[g]} |" for g in groups]
    out.append("")
    if waived_rows:
        out.append(f"**WAIVED (approved exceptions): {len(waived_rows)}**")
        out += [f"  - `{r[0]}` ({r[1]})" for r in waived_rows]
        out.append("  Waivers are NOT RE evidence and are not counted as "
                   "VERIFIED.")
    state = "OPEN" if not unresolved else "BLOCKED"
    out.append(f"**Gate status: {state}** — {len(unresolved)} rows still "
               f"`INFERRED`/`UNKNOWN` without a valid waiver.")
    return "\n".join(out)


def main(argv):
    check_only = "--check" in argv
    text = open(DOC, encoding="utf-8").read()
    groups, rows, errors = parse(text)
    if errors:
        print("STRUCTURE INVALID:")
        for e in errors:
            print("  -", e)
        return 1
    block = render(groups, rows)
    if not check_only:
        new = re.sub(r"(<!-- TALLY:START -->\n).*?(\n<!-- TALLY:END -->)",
                     lambda m: m.group(1) + block + m.group(2), text, flags=re.S)
        if new != text:
            open(DOC, "w", encoding="utf-8").write(new)
            print("tally updated")
    waived = [r for r in rows if r[3]]
    unresolved = unresolved_rows(rows)
    print(f"items={len(rows)} "
          f"re={dict(Counter(r[1] for r in rows))} "
          f"port={dict(Counter(r[2] for r in rows))}")
    if waived:
        print(f"waived={len(waived)} "
              + " ".join(f"{r[0]}[{r[1]}]" for r in waived))
    print(f"gate={'OPEN' if not unresolved else 'BLOCKED'} "
          f"({len(unresolved)} unresolved)")
    return 0 if not unresolved else 2


# --------------------------------------------------------------- self-tests
def _selftest():
    """Built-in tests for the waiver policy. Run: --selftest."""
    ok = True

    def row(item, re_state, extra=""):
        return (f"| {item} x | ev | {re_state} | ported | note {extra} |")

    def run(rows, expect_errors, expect_waived, expect_unresolved):
        nonlocal ok
        text = "## A. test\n\n| Item | Ev | RE state | Port state | Note |\n"
        text += "|---|---|---|---|---|\n" + "\n".join(rows)
        groups, parsed, errors = parse(text)
        # Ignore the inventory-total mismatch (test uses a tiny fake inventory).
        errors = [e for e in errors if "inventory expects" not in e]
        n_waived = sum(1 for r in parsed if r[3])
        n_unresolved = len(unresolved_rows(parsed))
        good = (len(errors) == expect_errors
                and n_waived == expect_waived
                and n_unresolved == expect_unresolved)
        ok = ok and good
        return good

    # 1. INFERRED without waiver -> unresolved, no error.
    run([row("A1", "INFERRED")], 0, 0, 1)
    # 2. INFERRED with valid waiver -> waived, resolved, no error.
    run([row("A1", "INFERRED", "WAIVER: approved 2026-10-09 user")],
        0, 1, 0)
    # 3. UNKNOWN with valid waiver -> waived, resolved.
    run([row("A1", "UNKNOWN", "WAIVER: environment-bound")], 0, 1, 0)
    # 4. WAIVER with empty reason -> structural error.
    run([row("A1", "INFERRED", "WAIVER:")], 1, 0, 1)
    # 5. WAIVER on VERIFIED -> structural error (not waivable).
    run([row("A1", "VERIFIED", "WAIVER: should not be allowed")], 1, 0, 0)
    # 6. All resolved (VERIFIED only) -> gate open.
    run([row("A1", "VERIFIED")], 0, 0, 0)
    print(f"selftest: {'PASS' if ok else 'FAIL'} "
          f"({'all 6 cases ok' if ok else 'see failures above'})")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    sys.exit(main(sys.argv[1:]))
