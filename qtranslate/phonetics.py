"""Read-phonetically display — port of FUN_0042ED3F's phonetics branch (J7).

Native evidence (Ghidra decompile of the recovered image,
`docs/review/ARTIFACT_RECOVERY_2026-10-10.md`):

```c
if ((((char)uVar1 == '\0') && (*(int *)(param_1[5] + -0xc) != 0))
    && (DAT_00549414 != '\0')) {
    FUN_00401f21(&DAT_0052284c);              // append "\r\r"
    FUN_00451d23(&param_2, 0xba);            // append string resource 186
    FUN_004089fe(param_1 + 5, 0);            // append entry[5] (the phonetics)
}
```

`uVar1 = FUN_00403897(param_1)`, which decompiles to:

```c
uVar1 = FUN_00401fc2((ushort *)L"<Error>");   // CString::Find
return 1 - (uVar1 != 0);                      // 1 when "<Error>" is ABSENT
```

so gate 1 is **"the result is not an `<Error>` marker"** — *not* "the result is
empty". Phonetics are an **annotation on a successful translation**, never a
fallback shown instead of an error.

The three appended literals were located by content search over the recovered
image (not by VA→file-offset mapping, which returns empty for the
runtime-initialized pointer). The offsets below are **file offsets** into
`docs/review/artifacts/QTranslate.6.10.0.exe`, as re-verified by
`docs/review/J7_PHONETICS_NATIVE_2026-10-10.md` §4c — not image VAs:

| Literal | File offset | First bytes | Meaning |
|---------|-------------|-------------|---------|
| `"\r\r"` | `0x12184c` | `0d 00 0d 00` | `DAT_0052284c`, the separator |
| `"Romanization: "` | `0x158c00` | `52 00 6f 00 6d 00` | `RT_STRING` id **186** (`0xBA`) |
| `"<Error>"` | `0x121af0` | `3c 00 45 00 72 00` | the marker that suppresses the append |

The id 186 is not just read off the decompile: `FUN_00451d23` reaches
`FindResourceW(hModule, (LPCWSTR)((id >> 4) + 1), (LPCWSTR)6)`, so a type-6
leaf's `nameId` is `block + 1`. Id 186 → block 11 → nameId 12 → ids 176..191,
whose slot 10 is `"Romanization: "`. Id **190** under the same leaf resolves to
`"No data returned (timeout while sending data.)"` — the string this port
already emits on failure, which is the second, independent confirmation.

`DAT_00549414` is the `ReadPhonetically` option (loader `FUN_0045869F`, saver
`FUN_004561F0`, menu `0x802d` toggled in `FUN_00430C52`). The effect is
**display only** — it appends to the result pane. It is not a TTS/audio
feature, and the older "phonetic TTS/effect untraced" label was wrong.

**"Romanization: " is the native label and is used verbatim.** Unlike the
`--- back-translation ---` separator (a port invention, confirmed absent from
the binary), this string genuinely exists there; inventing our own wording
would look native while being ours.
"""
from __future__ import annotations

# DAT_0052284c — two raw CR bytes at file offset 0x12184c in the recovered image.
PHONETICS_SEPARATOR = "\r\r"
# RT_STRING id 186 (0xBA), file offset 0x158c00 — the native label.
PHONETICS_LABEL = "Romanization: "
# Gate-1 marker, file offset 0x121af0.
ERROR_MARKER = "<Error>"


def phonetics_enabled(options: dict | None) -> bool:
    """General.ReadPhonetically — DAT_00549414, default off (native default)."""
    try:
        return bool((options or {}).get("General", {})
                    .get("ReadPhonetically", False))
    except Exception:
        return False


def append_phonetics(text: str, phonetics: str | None, enabled: bool = False,
                     label: str | None = PHONETICS_LABEL) -> str:
    """Port of FUN_0042ED3F's phonetics branch.

    Appends ``separator + label + phonetics`` only when native would:
    the `ReadPhonetically` flag is on, the phonetics field is non-empty, and
    the result is not an `<Error>` marker. Returns the input unchanged
    otherwise — native likewise appends nothing.
    """
    if not enabled:
        return text
    if ERROR_MARKER in (text or ""):
        return text
    phon = (phonetics or "").strip()
    if not phon:
        return text
    out = (text or "") + PHONETICS_SEPARATOR
    if label:
        out += label
    return out + phon


def is_phonetics_enabled_from_config(load) -> bool:
    """Read General.ReadPhonetically via a `load()` callable (config.load)."""
    try:
        return phonetics_enabled(load())
    except Exception:
        return False
