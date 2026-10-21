"""Recover the locale packs and pair each `help.txt` with its `lang.json`.

The installer payload holds 35 `Locales/<dir>/lang.json` and 35
`Locales/<dir>/help.txt` files, interleaved but NOT paired: the chunk after
a `lang.json` is usually a *different* language's help file. The payload
carries no filenames, so the pairing has to be recovered from content.

The pairing is done by vocabulary: a pack's `lang.json` holds the locale's
translated UI strings, and its `help.txt` holds the same locale's translated
hotkey descriptions. Scoring the word overlap between a help file and every
pack's strings identifies the right pack -- and the margin between the best
and the second-best score says whether the identification is trustworthy.

Writes `qtranslate/assets/locales/<code>/{lang.json,help.txt}`.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "docs/review/artifacts/nsis_payload_unpacked.bin"
OUT = ROOT / "qtranslate/assets/locales"
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def walk_chunks(blob: bytes):
    off = 0
    index = 0
    while off < len(blob):
        (length,) = struct.unpack_from("<I", blob, off)
        off += 4
        yield index, blob[off : off + length]
        off += length
        index += 1


def all_strings(obj):
    """Every string value in a pack, however it is nested."""
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(obj)
    return out


def words(texts):
    bag = set()
    for text in texts:
        for word in WORD.findall(text.lower()):
            bag.add(word)
    return bag


def main() -> int:
    blob = PAYLOAD.read_bytes()
    packs = []          # (chunk, code, wordset)
    helps = []          # (chunk, bytes, wordset)
    for index, body in walk_chunks(blob):
        text = body.decode("utf-8", errors="replace")
        if '"LanguageCode"' in text and '"Strings"' in text:
            code = re.search(r'"LanguageCode"\s*:\s*"([^"]+)"', text)
            if not code:
                continue
            try:
                obj = json.loads(text.lstrip("﻿"))
            except Exception:
                obj = None
            if obj is None:
                # Native's packs are JSON-with-trailing-commas (and a couple
                # carry a double comma); strip them the way the theme loader
                # does before parsing.
                cleaned = re.sub(r",(\s*,)+\s*", ",", text.lstrip("﻿"))
                cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
                try:
                    obj = json.loads(cleaned)
                except Exception:
                    obj = None
            if obj is None:
                print(f"  chunk {index}: pack unparseable, skipped", file=sys.stderr)
                continue
            # The native's installed tree names each directory by the
            # pack's English display name ("Bulgarian", "Vietnamese"), and
            # the port's own API uses those names (`load_pack("Vietnamese")`).
            # The bundled tree has to match, so it is named the same way.
            dirname = obj.get("LanguageName") or code.group(1)
            packs.append((index, code.group(1),
                          words(all_strings(obj)), body, dirname))
            continue
        if "=>" in text and "Ctrl" in text:
            helps.append((index, body, words([text])))

    print(f"packs: {len(packs)}  helps: {len(helps)}")
    if len(packs) != 35 or len(helps) != 35:
        print("unexpected counts", file=sys.stderr)

    # Score every (help, pack) pair.
    scored = []
    for hi, (hchunk, hbody, hwords) in enumerate(helps):
        best = []
        for pi, (pchunk, code, pwords, _body, _dn) in enumerate(packs):
            if not hwords or not pwords:
                continue
            inter = len(hwords & pwords)
            score = inter / len(hwords)
            best.append((score, pi))
        best.sort(reverse=True)
        scored.append((hi, best))
        if hi < 3:
            margin = (best[0][0] - best[1][0]) if len(best) > 1 else 0
            print(f"  help {hchunk}: best={packs[best[0][1]][1]} "
                  f"score={best[0][0]:.3f} margin={margin:.3f}")

    # English is identified by CONTENT, not by score: the payload carries two
    # English copies (chunk 57 = 6.10.0's, with three mouse modes and the
    # F11 entry; chunk 91 = a stale two-mode copy). The 6.10.0 one is 57.
    ENGLISH_CHUNK = 57
    assignment = {}
    taken = set()
    for hi, (hchunk, hbody, _hw) in enumerate(helps):
        if hchunk == ENGLISH_CHUNK:
            pi = next((i for i, (_c, code, _w, _b, _dn) in enumerate(packs)
                       if code == "en"), None)
            if pi is not None:
                assignment[hi] = (1.0, pi)
                taken.add(pi)
            break
    order = sorted(range(len(scored)),
                   key=lambda i: -(scored[i][1][0][0] if scored[i][1] else 0))
    for hi in order:
        if hi in assignment:
            continue
        best = scored[hi][1]
        for score, pi in best:
            if pi in taken:
                continue
            taken.add(pi)
            assignment[hi] = (score, pi)
            break

    margins = []
    for hi, (score, pi) in assignment.items():
        second = None
        for s, p in scored[hi][1]:
            if p != pi:
                second = s
                break
        margins.append((score - (second or 0.0), score, packs[pi][1]))

    # Confidence: the margin between the best and the second-best pack for
    # a help file. Below the threshold the pairing is not shipped.
    MIN_MARGIN = 0.05
    confident = set()
    for hi, best in scored:
        if hi not in assignment:
            continue
        score, pi = assignment[hi]
        second = 0.0
        for s, p in best:
            if p != pi:
                second = s
                break
        if score - second >= MIN_MARGIN:
            confident.add(hi)

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.is_dir():
            for sub in old.rglob("*"):
                sub.unlink()
            old.rmdir()
        else:
            old.unlink()

    manifest = []
    for pi, (pchunk, code, _pwords, pbody, dirname) in enumerate(packs):
        d = OUT / dirname
        d.mkdir(parents=True, exist_ok=True)
        (d / "lang.json").write_bytes(pbody)
        entry = {"code": code, "directory": dirname,
                 "lang_chunk": pchunk,
                 "lang_sha256": hashlib.sha256(pbody).hexdigest()}
        hi = next((h for h, (s, p) in assignment.items() if p == pi), None)
        if hi is not None and hi not in confident:
            hi = None
        if hi is not None:
            hchunk, hbody, _ = helps[hi]
            (d / "help.txt").write_bytes(hbody)
            score = assignment[hi][0]
            entry["help_chunk"] = hchunk
            entry["help_sha256"] = hashlib.sha256(hbody).hexdigest()
            entry["match_score"] = round(score, 3)
        manifest.append(entry)

    (OUT / "_manifest.json").write_text(json.dumps({
        "source_payload": str(PAYLOAD.relative_to(ROOT)),
        "note": "Recovered from the QTranslate 6.10.0 installer payload. The "
                "lang.json files are byte-identical to the installed "
                "Locales/<dir>/lang.json; the help.txt files are paired to "
                "their pack by vocabulary overlap (the payload interleaves "
                "the two streams without pairing them).",
        "locales": manifest,
    }, indent=1) + "\n", encoding="utf-8")

    margins.sort()
    print()
    print("weakest pairings (margin, score, code):")
    for margin, score, code in margins[:6]:
        print(f"  margin={margin:.3f} score={score:.3f} {code}")
    print(f"  median margin: {margins[len(margins) // 2][0]:.3f}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
