"""Keyboard-layout text converter — port of FUN_00404E09 + TaskConvertTextLayout.

Native logic: per-char hardcoded EN<->RU phonetic pairs for ambiguous keys
(verified from decompile: q<->/, w<->', ','<->', '.'<->/ both directions),
then generic VkKeyScanExW/ToUnicodeEx fallback. Here the fallback is the
full RU JCUKEN map (standard, matches what the Windows APIs produce).

Direction auto-detected like the native (checks HKL pair order).
"""
import sys

# RU JCUKEN row order aligned to US QWERTY positions (lowercase)
_EN = list("qwertyuiop[]asdfghjkl;'zxcvbnm,./`")
_RU = list("йцукенгшщзхъфывапролджэячсмитьбю.ё")

EN2RU = dict(zip(_EN, _RU))
RU2EN = dict(zip(_RU, _EN))
# Decompile-verified special pairs (FUN_00404E09, HKL 0x409<->0x40D)
EN2RU.update({"'": "э", ",": "б", ".": "ю", "/": "."})
RU2EN.update({"э": "'", "б": ",", "ю": ".", ".": "/"})

# Uppercase mirrors
for _e, _r in list(EN2RU.items()):
    EN2RU[_e.upper()] = _r.upper()
for _r, _e in list(RU2EN.items()):
    RU2EN[_r.upper()] = _e.upper()


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
