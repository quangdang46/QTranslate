# The two header `%s` slots, resolved — and a correction to the count

> Read-only. Closes the one `UNKNOWN` recorded in
> `DICT_CARD_UNRECORDED_DIVERGENCES_2026-10-10.md` §1, and corrects a
> number in the peer's commit that has since propagated into a comment
> in `qtranslate/dict_render.py` and into their test.
>
> **No port file changed.** `qtranslate/dict_render.py` and
> `tests/regress_dict_card.py` are the peer's; this records what the bytes
> say so the owner can decide the edit.

## 1. The unknown is resolved: slot 1 is the icon, slot 2 is link-or-title

The card format string is called once in `FUN_004253cc`, at `0x004255a2`,
as `FUN_004023f1(dst, fmt, ...9 varargs)`. `FUN_004023f1` is a
`vswprintf`-shaped helper — its decompile is `(dst, fmt)` with the varargs
on the stack beyond, and the call site does `ADD ESP,0x2c` (44 bytes =
2 fixed args + 9 varargs) after it. Nine specifiers, nine pushes.

`__cdecl` pushes right-to-left, so **the last push is `arg2`, the first
vararg.** Reading the pushes in reverse:

| Specifier | Reversed push | Slot value |
|---|---|---|
| `%u` (1) | `0x00425595` `PUSH EAX` | `qt-s` service id |
| `%u` (2) | `0x00425596` `PUSH EAX` | `qt-h` service id |
| `%u` (3) | `0x00425597` `PUSH EAX` | `toggle()` id |
| **`%s` (4)** | `0x00425591` `PUSH [ESP+0x20]` | **`local_8c`** |
| **`%s` (5)** | `0x0042558d` `PUSH [ESP+0x30]` | **`local_78`** |
| `%u` (6) | `0x0042558c` `PUSH EAX` | `qt-d` service id |
| `%u` (7) | `0x0042558b` `PUSH EAX` | `qt-l` service id |
| `%u` (8) | `0x0042558a` `PUSH EAX` | `fullEntry()` id |
| `%s` (9) | `0x00425583` `PUSH [EBX+0xc]` | body fragment |

The frame is fixed by one anchor and checked two ways. `0x00425598`
`LEA EAX,[ESP+0x38]` is the call's destination, which the decompiler names
`local_84` = `EBP-0x84`; nine pushes precede it, so
`E − 36 + 0x38 = −0x84` gives `E = EBP−0x98`. The two earlier anchors agree:
`0x00425515` `LEA EAX,[ESP+0x10]` → `local_8c`, and `0x00425520` →
`local_80`.

| Slot | Local | Holds |
|---|---|---|
| **first `%s`** | `local_8c` | `FUN_004023f1(&local_8c, L"<img src=\"%s\" style=\"vertical-align: middle\"></img>&nbsp;")` — the **icon markup**, whose own `%s` is `"file:///%s"` over `<config>/Services/<name>/Service.ico`, or a default when that file is absent |
| **second `%s`** | `local_78` | `FUN_004023f1(&local_78, L"<a href=\"%s\" class=\"qt-link-browser\" title=\"Open in browser\">%s</a>")` when the service has a home page, else `FUN_00401ec9(&local_78, title)` — **the browser link, or the bare title** |

So the icon is the **first** slot and the link-or-title is the **second**,
which is the order the peer reported. But the locals they attribute them to
are one position off from the argument order they state: `local_8c` is built
first and `local_78` second, and the format takes `local_8c` first. Their
text says "the card format takes them in that order" while assigning
`local_78` to slot 1 in the surrounding prose. The conclusion is the same;
the mapping is not, and the mapping is what a reader will copy.

**Both slots are still absent from the port**, which emits
`{_html.escape(title)}` alone. The count of native substitutions is nine
and the port fills seven — the same finding as the parent document, now with
no unknown in it.

## 2. The count is 298 chars / 596 bytes, not 297 / 594

The peer's message claimed **297 chars / 594 bytes** with the string
"ending exactly at the card's `</div></div>`", and their committed comment
in `dict_render.py:30` says **297 chars / 594 bytes** while their own test
says **298 chars / 595 bytes**. The two disagree with each other.

Measured three ways, all in agreement:

| Method | Result |
|---|---|
| loop to first zero code unit | **298** |
| scan for `00 00` at an even offset | **298** |
| decode UTF-16LE, split on NUL | **298** |

```
string spans [0x11d8f0, 0x11db44)     298 code units = 596 bytes
terminator NUL at 0x11db44
next string at  0x11db48 = "beforeEnd"
```

The parent document's own reproduce block already asserted `len(card) == 298`
and passed, which is why I re-derived this rather than accepting the
correction: **the correction was targeted at the method (NUL-scanning a
concatenated pool) and happened to land on a wrong number.** My "388/10"
error and the peer's "297/594" are different mistakes — mine was reading
past the card into the pool, theirs is an off-by-one in the char count and a
4-byte error in the byte count.

**What was actually true all along:** the literal *is* NUL-terminated, and
the NUL falls exactly at the card's own `</div></div>`. That is why the
parent document's structural cut and a NUL-scan agree here. The general
rule stands and is not weakened by this instance: `.rdata` pools C strings
with no delimiter in the *other* direction, which is what made the 388/10
reading possible in the first place. Cut at a structural boundary.

## 3. `No results found for '%s'.` — location confirmed, mechanism theirs

The literal is at file offset **`0x11dbc8`**, corroborating the peer's
address. Their attribution of it to `FUN_00451dbd` driven by
`FUN_00425767` on the `+0x180` counter is theirs and I did not re-derive it;
the port gap is measured: `DR.render_cards([])` produces 0 cards, an empty
`<div class="qt-content">`, and no message text.

## 4. Reproduce

```python
import struct
blob = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
off = 0x11d8f0
n = 0
while struct.unpack_from('<H', blob, off + n*2)[0] != 0:
    n += 1
assert n == 298, n                      # NOT 297
assert n * 2 == 596, n * 2              # NOT 594
assert blob[off + n*2:off + n*2 + 2] == b'\x00\x00'
s = ''.join(chr(struct.unpack_from('<H', blob, off + k*2)[0]) for k in range(n))
assert s.endswith('</div></div>')       # the NUL IS at the card's end
assert off + n*2 + 4 == 0x11db48
assert blob.find("No results found for '%s'.".encode('utf-16-le')) == 0x11dbc8
```

The argument order needs the disassembly, not the format string — the pushes
at `0x00425583`–`0x004255a1` in reverse, with `E = EBP−0x98` from the
`0x00425598` `LEA EAX,[ESP+0x38]` anchor.

## 5. Method note

I had already measured `len(card) == 298` when I wrote the parent document,
and my first reaction to "297/594" was to check whether I had been the one
measuring 298. I had. The correction looked authoritative — it came with a
specific byte count and an explanation of my error — and it was wrong, and
the peer's own test contradicted it while their comment did not.

The failure mode: **a correction can be right about the method and wrong
about the number, and the method story is the part that sounds convincing.**
My 388/10 was a real error about the pool; having confessed it, I was
positioned to accept a replacement number rather than to test it. Two
numbers I had already measured and written down were sitting in a file I
authored.
