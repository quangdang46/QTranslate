# Endpoint + config-key coverage sweep (2026-10-14)

Date: 2026-10-14
Target: `docs/review/artifacts/QTranslate.6.10.0.exe`
Tooling: REA 6.4.0 -> Ghidra 12.1.4 (`rea search`, snapshot `qt6`)

Purpose: find native network endpoints and config keys that the Python
port has NOT reproduced, ordered by how much work they'd remove.

## Every hostname/path string in the image

```
0x51c81c  http://xiph.org/flac/                                (libFLAC banner)
0x51d800  https://quest-app.appspot.com/faq
0x51d6f0  https://quest-app.appspot.com/download
0x52271c  https://quest-app.appspot.com
0x522780  https://quest-app.appspot.com/download
0x5227d0  https://quest-app.appspot.com
0x52a8cc  https://translate.yandex.com/
0x52a6e8  https://www.bing.com/translator
0x52a888  https://www.bing.com/ttranslatev3
0x52a910  https://www.online-translator.com/translation
0x52aa98  https://www.online-translator.com/api/pageLoad
0x52aca8  https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=%s&fields=href
0x529b68  https://api.ocr.space/parse/image
0x522e108 (XML manifest, no network)
0x5225c8  https://www.google.com/speech-api/full-duplex/v1/up?
0x522668  https://www.google.com/speech-api/full-duplex/v1/down?
0x52ad68  /update?v=
0x51f380  /services/spellservice.json/checkText
```

## Disposition, one line each

| Native string | Port state |
|---|---|
| bing ttranslatev3 / bing.com/translator | ported (`_t_bing`, services/microsoft.py) |
| online-translator.com/translation | ported (promt.service_host) |
| online-translator.com/api/pageLoad | **ported 2026-10-14** (FUN_0045f372) |
| cloud-api.yandex.net/v1/disk/... | **ported 2026-10-14** (FUN_0046185d) |
| api.ocr.space/parse/image | ported (services/ocr.py OCR_HOST) |
| google full-duplex up/down | ported (speech_input.py, byte-verified) |
| /update?v= | ported (updater.py FUN_00461ADE parser; host retired) |
| spellservice checkText | ported (services/spell.py) |
| quest-app.appspot.com/* | `dead:host-retired` (R1/R2) |
| xiph.org/flac | banner string, not a request |

So after this sweep the image contains **no unported network endpoint**.

## Config-flag sweep

Regex `(Enable|Disable|Auto|Show|Hide|Check|Use)[A-Za-z]{4,}` over all
strings: 48 hits, and the only 5 absent from the port are Win32 *API
import names* (`CheckDlgButton`, `CheckMenuItem`, `CheckMenuRadioItem`,
`EnableMenuItem`, `EnableWindow`) — not config keys. Every native
configuration key is represented.

## Conclusion

The two remaining true gaps found this session were both closed (Promt
`pageLoad`, Yandex.Disk href resolver). Remaining `not-started` rows
(C10/F13/J6/G9) are terminal-by-design as recorded in
`docs/RE_COVERAGE_CHECKLIST.md`.
