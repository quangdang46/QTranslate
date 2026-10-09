# The native dictionary template, recovered from the image — and the port matches it

> Read-only verification. This came out of two background tasks that hung on
> `find` over the home directory; the underlying question was answerable
> directly from the recovered image, so it was answered that way instead.
> Companion to `ARTIFACT_RECOVERY_2026-10-10.md` and
> `ADDRESS_VERIFICATION_2026-10-10.md`.

## 1. What was found

`docs/review/artifacts/QTranslate.6.10.0.exe` contains a complete, embedded
HTML page in `.rdata` at file offset **`0x157d08`**, length **3062 bytes**,
terminated by the first NUL after it (ends `</html>\r\n`):

```
0x157d08 .. 0x1588fe   (3062 bytes, md5 fa312ed6c1f7b72dc1fa7076fd22c997)
```

It is `<!DOCTYPE HTML><html><head><title>Dictionary</title>` plus a `<style>`
block, a two-element `<body>`, and a `<script>` block of eight small
functions. This is the **dictionary renderer's template** — the page the
native WebBrowser control is handed, into which the service's
`qt-s<id>` / `qt-h<id>` / `qt-d<id>` / `qt-l<id>` sections are inserted.

The JS is worth naming because it is the *host* contract, and it explains the
ids every dictionary service must emit:

| Function | Role |
|---|---|
| `$(id)`, `service/header/data/link(id)` | `getElementById` wrappers for the four required ids |
| `toggle(id)` | show/hide one service's `qt-d<id>` block |
| `fullEntry(id)` | expand a clipped entry |
| `checkEntry(id)` | clip any block over **200px** and reveal the "read more" link |
| `appendMenuItem(title, iconUrl)` | build the left nav entry |
| `showNavigation()` | reveal the 24px nav column |

So the required per-service element ids are `qt-s<id>`, `qt-h<id>`, `qt-d<id>`,
`qt-l<id>` (the four accessors), the nav id is `li<id>`, and containers are
`qt-navigation`, `qt-menu`, `qt-content`. That is a pinned contract, not a
convention the port guessed.

## 2. The port matches it

`qtranslate/dict_template.html` is **content-identical** to the recovered
bytes. The one difference is line endings:

| | CRLF | lone LF | size |
|---|---|---|---|
| native (`0x157d08..0x1588fe`) | **77** | 0 | 3062 |
| port (`dict_template.html`) | 0 | **77** | 2985 |

Normalizing the native region's CRLF→LF makes the two **byte-identical with
zero remaining delta** (verified: `native.replace(b"\r\n",b"\n") == port`).
So the port is a faithful copy of the native template, checked into the repo
with Unix line endings — almost certainly a `core.autocrlf`/editor artifact
rather than a fidelity decision.

**Two consequences, one each way:**

- **This is real verification value.** A dictionary-rendering row that depends
  on "the template matches native" now rests on bytes compared against bytes,
  not on inspection. It is the same class of evidence as the J7 string ids:
  measured, reproducible from an artifact in the repo.
- **The CRLF difference is a real (small) fidelity gap.** If the native
  WebBrowser control is fed the template with `\r\n` and the port feeds it
  `\n`, nothing user-visible changes in an HTML renderer — both are legal
  whitespace outside `<pre>`. So this is **not** a behavioural difference,
  and recording it as one would overstate it. It is worth cleaning up only if
  the template is ever compared byte-wise again, or if it becomes the input to
  a fixture test that diffs against a captured native page.

## 3. What this does and does not settle

- **Does:** the native dictionary template is in hand and reproducible from
  the committed artifact; the port's copy of it is verified identical modulo
  line endings.
- **Does:** pin the service element-id contract (`qt-s/h/d/l<id>`, `li<id>`,
  the 200px clip threshold) as native behavior rather than port convention.
  If any dictionary service or `dict_render.py` emits different ids, that is
  now a demonstrable divergence rather than a style question.
- **Does not:** tell us which provider fills native's phonetics slot
  (`entry[5]`). The page above is the *dictionary* renderer; it has no
  romanization field. The per-provider logic lives in the `Services/*/Service.js`
  files the app downloads at runtime, and those are **not** in the image — only
  the strings naming the hooks are. Verified present, by UTF-16LE content
  search:

  | String | Offset |
  |---|---|
  | `"Service.js"` | `0x121aa4` |
  | `"ServicesOrder"` | `0x121e7c` |
  | `"serviceHeader"` | `0x12c300` |
  | `"serviceLink"` | `0x12c334` |
  | `"serviceTranslateRequest"` | `0x12c3c4` |
  | `"serviceTranslateResponse"` | `0x12c3f4` |

  (`"serviceURL"`, which I first listed here, is **absent** from the image —
  corrected after checking every address cited in this table rather than
  writing it from expectation.) So the J6-style question "which service writes
  `entry[5]`" remains unanswerable from this artifact, re-confirmed here
  rather than assumed.
- **Does not:** change any checklist row or the tally. A `ported` row whose
  template is byte-identical could arguably be `behaviour-verified`, but
  that classification is the checklist owner's, and the distinction the row
  would change (rendered pixel output) is a G9-class runtime question.

## 4. Reproduce

```python
blob = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
native = blob[0x157d08:0x157d08+3062]          # ends at the first NUL: </html>\r\n
port = open("qtranslate/dict_template.html", "rb").read()
assert native.replace(b"\r\n", b"\n") == port
assert native.count(b"\r\n") == 77 and port.count(b"\n") == 77
```

The region bounds are not magic: `0x157d08` is the first `<!DOCTYPE` in the
image (there are two `<html` markers, `0x157d08` and `0x157d19`, the second
being `DOCTYPE HTML><html>`), and the end is the first NUL after the start.
