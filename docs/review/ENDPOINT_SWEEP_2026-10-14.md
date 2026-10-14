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

## Appendix: byte-level string scan (no Ghidra needed) — 2026-10-14 update

A pure-Python UTF-16LE scan of the artifact (2156 wide strings) resolves
questions the Ghidra string inventory could not, because `rea search`
only reports *Ghidra-defined string Data*:

| Native string | In the port? |
|---|---|
| `YandexAppId`, `BaiduGtk`, `BaiduToken`, `BaiduCookie` | yes (Options session slots) |
| `PromtCookie`, `PromtPaft`, `PromtXsrf` | yes |
| `GoogleDomain`, `GoogleTkk` | yes |
| `SOFTWARE\Microsoft\Windows\CurrentVersion\Run` | yes (Start-with-Windows) |
| `SOFTWARE\...\Uninstall\QTranslate`, `UninstallString` | n/a (installer metadata) |

### Two findings worth recording

1. **The five provider display names are absent from the image** —
   `DeepL`, `Papago`, `youdao`, `Naver`, `Babylon` return **0** wide-string
   hits (only `Promt`/`Baidu`/`Yandex`/`Google` appear, and those only as
   Options-session keys, never as display names). This is the direct
   confirmation of `PLUGIN_LOADER_FOUND_2026-10-10.md`: the service
   `Service.js` files that carry the provider names are **not** in the
   recovered artifact. So the port's provider display names come from the
   UI spec / live sites, not from this binary — and any claim that they
   were "verified from the binary" would be false.

2. **`text=car&fromLang=en&to=ru&token=%s&key=%s&isAuthv2=true`**
   (at VA `0x529810`, file offset `0x129810`) is an **orphan**: Ghidra
   reports **zero references** to it. It therefore is not an active
   request body. `qtranslate/services/microsoft.py`'s `ttranslatev3`
   body (which does *not* contain `isAuthv2=true`) is correct as-is —
   recorded so nobody "fixes" this into the port later.
