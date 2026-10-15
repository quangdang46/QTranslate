"""Keyboard-layout text converter — port of FUN_00404E09 + TaskConvertTextLayout.

Native logic (checklist P2 evidence note, from FUN_00404E09 decompile):
explicit special pairs for the ambiguous-key set ``q w ' , . /`` —
RU->EN ``'->w, comma->apostrophe, .->/, /->q`` and EN->RU
``'->comma, /->., q->/, w->apostrophe`` — then the generic
VkKeyScanExW/ToUnicodeEx fallback. Here the fallback is the full RU
JCUKEN map (standard, matches what the Windows APIs produce).

Build order is load-bearing: generic map -> uppercase mirrors ->
explicit pairs LAST, so a special pair is never clobbered by the mirror
loop (which would uppercase ``w``->``W``). This matches native trying
special pairs before VkKeyScan.

Direction auto-detected like the native (checks HKL pair order).
"""
import sys

# RU JCUKEN row order aligned to US QWERTY positions (lowercase) — the
# GENERIC fallback (native VkKeyScanExW/ToUnicodeEx path).
_EN = list("qwertyuiop[]asdfghjkl;'zxcvbnm,./`")
_RU = list("йцукенгшщзхъфывапролджэячсмитьбю.ё")

EN2RU = dict(zip(_EN, _RU))
RU2EN = dict(zip(_RU, _EN))

# Uppercase mirrors (generic only — explicit pairs come after)
for _e, _r in list(EN2RU.items()):
    EN2RU[_e.upper()] = _r.upper()
for _r, _e in list(RU2EN.items()):
    RU2EN[_r.upper()] = _e.upper()

# Explicit special pairs from FUN_00404E09 decompile (HKL 0x409<->0x40D),
# checklist P2 — CORRECTED 2026-10-15. The old table here
# ({"'": "э", ",": "б", ".": "ю", "/": "."} and its partial inverse) was
# the generic JCUKEN mapping restated, NOT the native explicit set: it got
# 6 of 8 pairs wrong (EN w->ц not ', EN q->й not /, EN '->э not comma,
# RU ' and , and / missing entirely).
# RU->EN: '->w, comma->apostrophe, .->/, /->q
RU2EN.update({"'": "w", ",": "'", ".": "/", "/": "q"})
# EN->RU: '->comma, /->., q->/, w->apostrophe
EN2RU.update({"'": ",", "/": ".", "q": "/", "w": "'"})
# Uppercase mirrors of the explicit pairs (punctuation unaffected, but
# q/w/Q/W explicitly pinned both cases)
EN2RU.update({"Q": "/", "W": "'"})
RU2EN.update({"/": "q"})
# Cyrillic letters produced only by the generic path keep their JCUKEN
# mapping (untouched above); the ambiguous-key set is q w ' , . / only.


def _looks_like_ru(text: str) -> bool:
    ru = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    return ru * 2 >= len(text) and ru > 0


def convert_layout(text: str, to_ru: bool | None = None) -> str:
    """Retype text as if typed in the other layout (TaskConvertTextLayout)."""
    if to_ru is None:
        to_ru = not _looks_like_ru(text)
    table = EN2RU if to_ru else RU2EN
    return "".join(table.get(c, c) for c in text)


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(convert_layout("Ghbdtn"))   # -> Привет
    print(convert_layout("Привет"))   # -> Ghbdtn
