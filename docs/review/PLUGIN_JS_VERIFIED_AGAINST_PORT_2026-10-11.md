# The recovered `Service.js` sources, checked against the port

> Read-only verification. **This is what the recovered plugin source is *for***,
> which is a different document from the one that recovered it
> (`PLUGIN_JS_RECOVERED_2026-10-11.md`, peer commit `cd021c8`). It costs nothing
> to have the files and a great deal to have read them against the port.
>
> **No row state changed by this document.** It records what was checked, so any
> row owner can promote a row on measured grounds rather than on the mere
> *availability* of source.

## 1. Re-deriving the extraction, because a hash is only as good as its framing

I re-extracted all 19 `Service.js` bodies from
`docs/review/artifacts/nsis_payload_unpacked.bin` before using any of them,
rather than accepting the counts in the recovery document. The stream is
length-prefixed and the length field sits **immediately** before each body:

```python
i = p.find(b"function serviceHeader")
while i != -1:
    n = int.from_bytes(p[i-4:i], "little")     # the length field
    body = p[i:i+n]
    ...                       # body starts with b"function"
    i = p.find(b"function serviceHeader", i+1)
```

**19 files, 49,889 bytes** — matching the recovery document's number exactly,
derived independently. (My first attempt used a `-36` back-offset and extracted
only 7 of 19 with sizes up to 57 KB; the back-offset is not constant, and
guessing a framing is how a hash gets computed over the wrong bytes. Confirmed
by dumping the bytes between the candidate length field and the body: empty.)

| id | service | bytes | sha256 |
|---|---|---|---|
| 25 | ABBYY Lingvo Live | 2029 | `4c0ef8506ff3…` |
| 13 | Babylon | 1243 | `c12e825d73cb…` |
| 20 | Babylon Dictionary | 1243 | `f406c6fb3598…` |
| 28 | Baidu | 3490 | `910dfe9adcd7…` |
| 31 | DeepL | 2757 | `0abf80266900…` |
| 10 | Google Search | 1449 | `82885d093a2c…` |
| 1 | Google | 3388 | `f3459f952a2f…` |
| 18 | ImTranslator | 1303 | `76a9612fe84b…` |
| 5 | Microsoft | 3291 | `b1c12a050eda…` |
| 17 | Multitran | 1322 | `b9a6da58fe67…` |
| 30 | Papago | 9462 | `8eee5f6cb202…` |
| 29 | Oxford Learner Dictionary | 3379 | `60d291430ea0…` |
| 12 | Promt | 2040 | `1135da5bb2b1…` |
| 22 | Reverso | 1462 | `c9f069e3ddd8…` |
| 24 | Urban Dictionary | 1231 | `270440849c25…` |
| 14 | Wikipedia | 1495 | `b2dd1f2f3966…` |
| 19 | WordReference | 1531 | `2ada261c54f0…` |
| 11 | Yandex | 4431 | `93136ba152bf…` |
| 26 | youdao | 3343 | `6b2ee411798c…` |

Each `new ServiceHeader(id, "Name", …)` matches the installer's own manifest,
so the id in the file *is* the row id in the checklist — the mapping is not
inferred.

## 2. `serviceHost`, for all 15 that have one

Extracted from the source, not from the rows:

| service | `serviceHost` |
|---|---|
| ABBYY Lingvo Live | `https://www.lingvolive.com` |
| Babylon | `https://translation.babylon-software.com` |
| Babylon Dictionary | `https://dictionary.babylon-software.com` |
| DeepL | `https://www2.deepl.com` |
| Google | `https://translate.google.` |
| Google Search | `https://www.google.com` |
| ImTranslator | `http://imtranslator.net` |
| Microsoft | `https://` (domain-chosen at runtime) |
| Multitran | `https://www.multitran.com` |
| Oxford Learner Dictionary | `https://www.oxfordlearnersdictionaries.com` |
| Papago | `https://papago.naver.com` |
| Promt | `https://www.online-translator.com` |
| Reverso | `http://dictionary.reverso.net` (branch on `Capability.DICTIONARY`) |
| Urban Dictionary | `https://www.urbandictionary.com` |
| WordReference | `https://www.wordreference.com` |

**Every host appears in the port.** Twelve in `dictionary.py`, and the three
that do not — DeepL, Papago, Promt — are *translate* providers whose rows are
E4, E6 and E8, and each lives in its own module: `deepl.py:34`,
`naver.py:46`, `promt.py:38`. That is the correct placement, not a gap; the
check that would have flagged it as one is the check I had to run.

Reverso is the one branch case, and the port has it: `reverso_host(True)`
returns the dictionary host exactly as the JS's
`b==Capability.DICTIONARY` branch does.

## 3. `serviceDictionaryResponse`, spot-checked line-for-line

Read as source, not as endpoints. Three providers, chosen because the port
claims the most about them:

**WordReference (19)** — the port matches:

| JS | port |
|---|---|
| `stringFindSub(a,/<div id="(articleWRD\|article)">/,!1,'<div id="postArticle">',!1)` | `_sub(page, re.compile(r'<div id="(articleWRD\|article)">'), False, '<div id="postArticle">', False)` |
| `removeElements(a,["style"])` | `_remove_elements(frag, ["style"])` |
| `removeAttributes(a,["id","name","onclick"])` | present |
| `<style>.rh_me,span.phrase…` | present |
| `updateHtmlLinks(a, serviceHost(DICTIONARY))` | `_update_links(frag, WORDREF_HOST)` |
| `buildUri` = `format("/{0}{1}/{2}", …)` | `wordreference_build_uri` |
| `"https://www.wordreference.com"` | `WORDREF_HOST` |

**Reverso (22)** — the port matches, including the two markers and the
attribute list: `stringFindSub(a,'<div id="TableHTMLResult">',!1,"<!--Center section end",!1)`,
`removeAttributes(a,"id name class href onclick onmouseover onmouseout".split(" "))`,
`removeTags(a,["font","img"])`, and `buildUri` =
`format("/{0}-{1}/{2}")`.

**Oxford Learner (29)** — the port matches, down to the regexes:
`stringFindSub(a,'<div id="ox-wrapper"',!1,'<div id="rightcolumn"',!1)`, the
`qtdp:` rewrite, `removeAttributes("<div "+a,["id","dpsid","dpsref","geo"])`,
`removeElements(a,["script","img"])`, the sound-div strip, and the injected
`OXFORD_STYLE`.

`SupportedLanguages` is also checkable now, and it is the array the port's
docstring paraphrases ("None = unsupported, mirrors the -1 entries in the JS
arrays, indexed by internal lang id"). That paraphrase is accurate, and it can
be checked entry-by-entry for the first time.

## 4. What this does and does not license

**It licenses:** re-reading the port against source, which is the verification
the `VERIFIED` rows were always entitled to. Four providers are now checked
line-for-line — WordReference, Reverso, Oxford (from the first pass) and
**ABBYY Lingvo Live (25)**, read this session: the five-way `<div name="#…">`
slice start, the `HLjpm`→`<footer` end-marker fallback, the four removed
attributes (`data-reactid` is the easy one to drop), `removeElements(["button",
"svg"])`, the `_QT6_ALLs` style block, `buildUri`'s `/m.exe`-style shape, and
`langToUiLang`'s four cases.

**The provider count, corrected against the source rather than my own prose.**
An earlier version of this document said "14 dictionary providers remain
unread". Counting `Capability.DICTIONARY` in the recovered JS gives **11**,
of which **4** are now read and **7** unread. The 16 came from a loose
substring count, which is the same error mode as the one this document exists
to document. youdao (26) is the eleventh: it declares both TRANSLATE and
DICTIONARY. Ten are pure dictionary; one is mixed.

**It does not license:** calling a row `VERIFIED` on the strength of the source
existing. Each row still needs its own read. The honest statement for a row
checked here is "matches the recovered `Service.js` at hash `…`" — naming the
file, not the directory.

**It does not change** the Gate line or any tally. This document adds evidence;
it does not reclassify.

## 4b. `SupportedLanguages`: shipped for 11 providers, consulted by zero

This is the notable gap the Lingvo read surfaced, and it is **not** Lingvo's.

Every `Services/*/Service.js` declares a `SupportedLanguages` array indexed by
the app's shared language id, with `-1` meaning unsupported. The port ships
all eleven as `*_LANGS` tables (verified entry-by-entry for Lingvo: 76
entries, 55 unsupported, zero mismatches against the JS after normalising
`-1`→`None`). Ten of the eleven are **never read by anything**:

| table | referenced outside its own definition |
|---|---|
| `BABYLON_LANGS`, `BABYLON_DICT_LANGS`, `LINGVO_LANGS`, `REVERSO_LANGS`, `WORDREF_LANGS`, `OXFORD_LANGS`, `IMTRANS_LANGS`, `URBAN_LANGS`, `WIKI_LANGS`, `GSEARCH_LANGS` | no |
| `MULTITRAN_LANGS` | yes — one call, from `_multitran_code` |

The peer flagged LINGVO_LANGS and it is real. The generalisation is bigger than
the instance, and the generalisation is the part worth recording.

**What native does with an unsupported entry, stated honestly, because it is
NOT measured.** No service JS gates on it — I checked all 19 for an
`== -1`-style test and found none. The gate belongs to the framework
(`Common.js`), and `Common.js` is **absent from both artifacts**: 0 byte
occurrences of `Common.js` in the 2,263,053-byte NSIS payload, and exactly one
wide-string hit in the exe, which is the loader's `L"Common.js"` filename
(`FUN_0045d6a9`), not its source. So the framework's own gate — refuse, fall
back, or pass the raw value through — is **not recoverable from this repo**,
and a port that "refuses the request" would be guessing at the framework's
policy rather than porting it.

The port's own precedent for the same ambiguity is the honest one: native
Multitran's `buildUri` interpolates `codeFromLanguage(c)` and, for an
unsupported entry, that yields the raw entry — so `_multitran_code` returns the
value unchanged rather than inventing a code ("mirroring the native's lossy
build"). That is a measured convention from the 12 services that DO have a
readable `buildUri`.

**The reachable state, measured rather than assumed.** `app.py:3708` calls
`fn(word_q, "en", self.target)` — a **string** code, not a language index — so
the dictionary path currently never indexes these tables at all. That is why
they are dead: the resolution stage that would index them (ISO code →
`SupportedLanguages` index, which `language_from_code` already implements in
`common.py`) is not wired into the dictionary path. `multitran` is the one
provider with it, via `_multitran_code`'s lookup through `SUPPORTED_LANGS`.

**Consequence for the port, without a claim about native.** The live defect is
narrower than "requests unsupported pairs": for a provider whose table entry
is `None`, nothing currently consults it, so the request is issued with
whatever the caller passed. A gate is worth adding, but its *policy* is a
design call (raise, return `""`, or pass through as Multitran does) and no
artifact in this repo settles it. Recording that is the honest state; the
alternative is implementing a guess and calling it a port.

## 5. The method note that generalizes

The recovery document's own framing — *a 4-file search across two artifacts had
a blind spot three independent checks walked into* — is the finding. What this
pass adds is the second half of the rule:

> Having the artifact is not having verified the row. The failure mode
> inverted is having *more* evidence available and reading less of it.

The `Service.js | PRESENT — 0x121aa4` line I misread was a pointer to where
the file lives. The same line is now a pointer to 19 files, and a pointer is
not a checkpoint. Recording the checklist's status at this point: the files are
recovered and 2 providers are read; 14 dictionary providers and the translate
providers are unread; that is the remaining work, and it is *reading*, not
recovery.
