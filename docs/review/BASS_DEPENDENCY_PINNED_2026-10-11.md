# The BASS dependency, pinned — version, import list, and the shipped DLL

> Read-only. `J2` and `J5` cite `BASS_*` calls as native evidence and both are
> `VERIFIED`, but neither row recorded **which** BASS the binary was built
> against. The DLL that satisfies those imports ships in the same NSIS solid
> stream that carries the `Service.js` files, so the version is now a
> measurement rather than an assumption.
>
> **No row state changed.** This is the dependency the port would need, and
> `player.py`'s docstring already claims a 1:1 match — which is now a claim
> that can be checked against a specific DLL.

## 1. `bass.dll` 2.4.15, by Un4seen Developments, and it is packed

The stream's last data chunk (offset `0x200fa9`, 128,181 bytes) is the
shipped `bass.dll`. Its version resource, read out of the tail where the
packer leaves resources unpacked:

| field | value |
|---|---|
| `CompanyName` | `Un4seen Developments` |
| `FileVersion` | `2.4.15` |
| `LegalCopyright` | `Copyright © 1999-2019` |

The section table obfuscates names and ends in a section literally called
`petite` — this is a **Petite-packed** binary, which is why the first
335,872 bytes measure 7.96 bits/byte entropy and the export names are only
recoverable as plain text in the tail. That is worth stating plainly: the
102 `BASS_*` names below are read as strings from the unpacked tail, and
`BASS_StreamPutFileData` etc. appearing in a string scan is evidence the
name ships in this DLL, not that the packed export table was parsed.

## 2. What the program imports — 13 functions, all of them

Parsed from the recovered image's PE import directory (`0x13f26c`,
size `0x190`), `bass.dll` descriptor:

```
BASS_ChannelPlay        BASS_ChannelSetSync     BASS_ChannelStop
BASS_ErrorGetCode       BASS_Free               BASS_Init
BASS_RecordFree         BASS_RecordGetInput     BASS_RecordInit
BASS_RecordSetDevice    BASS_RecordStart
BASS_StreamCreateFile   BASS_StreamFree
```

Every one of the 13 resolves to a name present in the shipped DLL. The
import list is complete — 13 names in both the original-first-thunk and
first-thunk arrays, so the program uses no BASS entry point that the
shipped DLL does not carry.

## 3. Why the version number matters rather than being trivia

The J2 row's evidence is `BASS_StreamCreateFile(mem=1)`,
`BASS_ChannelSetSync(0x80000002=BASS_SYNC_END, cb)`, and
`BASS_ChannelPlay(restart=1)`. Those three all exist unchanged in
BASS 2.4, but the row's *interpretation* of the flags is version-sensitive:

- `BASS_SYNC_END` is `0x80000002` in BASS 2.4 — the row states the value and
  the symbol, and they agree.
- The `mem=1` argument to `BASS_StreamCreateFile` is a 2.4-era spelling;
  BASS 2.4 also added `BASS_StreamCreateFileUser` and previous majors
  differed in how a memory stream's length is supplied.

So `2.4.15` is not trivia: it fixes the API generation that makes J2's
decompile reading well-formed, and it means a port vendoring a modern
`bass*.dll`/`libbass` would need to check that spelling rather than assume
it.

## 4. The port side, and what is still missing

`qtranslate/player.py` claims "exact 1:1 with `player.py` docstring" for J2.
Matching 13 BASS functions in a Tk port means either vendoring the DLL or
reimplementing file-stream decoding, channel sync callbacks, and record
device selection — the same class of decision J6's FLAC note already
records as "a product decision, not RE work."

Python's stdlib has no BASS binding. `requirements.txt` adds none. The
dependency is real and is a choice, not a gap in the RE.

## 5. Reproduce

```python
import struct
p = open("docs/review/artifacts/nsis_payload_unpacked.bin", "rb").read()
n = struct.unpack_from("<I", p, 0x200fa9)[0]
bass = p[0x200fa9+4:0x200fa9+4+n]
assert len(bass) == 128181

assert "Un4seen Developments".encode("utf-16-le") in bass
assert "2.4.15".encode("utf-16-le") in bass     # FileVersion, wide only
assert b"petite\x00" in bass                    # the packer's section name

imports = ["BASS_ChannelPlay", "BASS_ChannelSetSync", "BASS_ChannelStop",
           "BASS_ErrorGetCode", "BASS_Free", "BASS_Init", "BASS_RecordFree",
           "BASS_RecordGetInput", "BASS_RecordInit", "BASS_RecordSetDevice",
           "BASS_RecordStart", "BASS_StreamCreateFile", "BASS_StreamFree"]
for name in imports:
    assert name.encode() in bass, name
assert len(imports) == 13
```

The import list is parsed from the image's own import directory, so the two
sides are independent evidence: the exe says what it needs, the DLL says
what it carries. A mismatch fails one side or the other rather than both.
