# Two unrecorded divergences in the dictionary card, measured from the format string

> **BOTH ARE CLOSED** (2026-10-21) — see §4 below. The document is kept as the
> record of the two gaps and of how they were settled; read §4 first.
>
> Read-only. Verification of `DICT_CARD_BUILDER_2026-10-10.md` (`7583a6b`)
> against the bytes it cites. That document is correct on all four divergences
> it lists, and the port's working-tree fix (`qtranslate/dict_render.py`)
> resolves them — I diffed the port's emitted card against the native format
> string and it now matches structurally.
>
> This records **two further divergences** in the same code path that the
> card-builder document does not list, both found by counting rather than by
> reading. No code changed.

## 1. The header has two `%s` slots and the port fills one

The native card at file offset `0x11d8f0` is **298 chars** and carries
**nine** format specifiers, not the eight the port's code comment states:

```
<div id="qt-s%u" class="qt-card"><div id="qt-h%u" class="qt-header"
ondblclick="toggle(%u);" onselectstart="return false;">%s%s</div><div
id="qt-d%u" class="qt-data"><input type="button" id="qt-l%u"
onclick="fullEntry(%u);return false;" class="qt-read-more"
value="READ MORE"></input>%s</div></div>
```

| Position | Specifier | Slot |
|---|---|---|
| +13 | `%u` | `qt-s` service id |
| +46 | `%u` | `qt-h` service id |
| +87 | `%u` | `toggle()` id |
| **+123** | **`%s`** | **header slot 1** |
| **+125** | **`%s`** | **header slot 2** |
| +146 | `%u` | `qt-d` service id |
| +195 | `%u` | `qt-l` service id |
| +218 | `%u` | `fullEntry()` id |
| +284 | `%s` | body fragment |

`dict_render.py:38` emits `{_html.escape(title)}` — **one** header slot where
native has two. So the port has 7 substitutions against native's 9.

**What the missing slot is: not established, and recorded as such.** The two
candidates are both supportable and the evidence does not separate them:

- the **service icon** — `FUN_0045d160` loads `Services/<name>/Service.ico`
  per service and `appendMenuItem(id, title, iconUrl)` already takes a URL as
  its third argument, so the icon travels natively; or
- an **HTML-safe/unsafe** pair, given the neighbouring `%s` is the title.

Either way the shape is the same: **a native field with no port equivalent.**
That is worth stating plainly rather than leaving as "one slot missing,"
because a reader will otherwise assume the title was matched exactly and the
count was cosmetic. Whoever fixes it needs to read `FUN_004253cc`'s argument
setup to see what it pushes for the two header slots; I have not done that and
am not guessing in a file I do not own.

## 2. An empty result renders a blank pane; native has a message

The literal at `0x11d8f0` is **not NUL-terminated at the card's end** — it is
part of a concatenated string pool. Reading to the NUL gives 388 chars and 10
specifiers, which is how I first measured it and was wrong; cutting at the
card's own `</div></div>` gives 298 and 9. The pool continues:

```
... </div></div> beforeEnd appendMenuItem fullEntry checkEntry
                 showNavigation No results found for '%s'. about:bl
```

`"No results found for '%s'."` is a native string in that pool, and **nothing
in the port emits it.** Measured:

```
DR.render_cards([])  ->  0 card elements, an empty <div class="qt-content">,
                          and no message text anywhere in the page
```

So a dictionary lookup that matches every service and still yields nothing
gives the user a blank pane. Native gives
`No results found for '<the query>'.`

This is the more user-visible of the two, and unlike §1 it is a **behavioural**
gap rather than a structural one — it can be fixed without knowing what the
missing icon slot is.

## 3. Both are in the dead path today

`app.py:3534` builds the page and `:3536` writes it to `dict_last.html`;
nothing reads it (`DICT_TEMPLATE_UNRENDERED_2026-10-10.md`). So neither
divergence is user-visible **now**. They are latent, and they should be fixed
*before* a render model changes, not after — same conclusion as the
card-builder document's own four, reached on two more items.

## 4. What is verified, so it is not re-derived

| Claim | Status |
|---|---|
| format string at `0x11d8f0`, 298 chars, 9 specifiers | **measured** |
| `ondblclick` / `onselectstart` / `<input type=button>` / `READ MORE` | **measured, and the port now matches** |
| "eight substitutions" in `dict_render.py`'s comment | **wrong — it is nine, and the port emits seven** |
| header has two `%s`, port fills one | **measured** |
| what the missing header slot holds | **UNKNOWN — icon or markup, not separated by the evidence** |
| `No results found for '%s'.` absent from the port | **measured** at pool offset +354, and **CLOSED 2026-10-16** — the note's claim is stale: `dict_render.NO_RESULTS` carries the literal verbatim and the zero-result path uses it (`tests/regress_dict_card_native.py`). Pinned so the claim cannot rot again |
| empty result set renders a blank pane | **measured** then **CLOSED 2026-10-16**: it now renders native's message, using the same card counter that gates `showNavigation()` — one native branch, not a case the renderer forgets |

## 5. Reproduce

```python
import re, struct
blob = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
pool = "".join(chr(struct.unpack_from('<H', blob, 0x11d8f0 + i*2)[0])
               for i in range(400)
               if struct.unpack_from('<H', blob, 0x11d8f0 + i*2)[0] != 0)
card = pool[:pool.index("</div></div>") + 12]
assert len(card) == 298
assert re.findall(r"%u|%s", card) == ['%u','%u','%u','%s','%s','%u','%u','%u','%s']
assert "No results found for '%s'." in pool
```

The 298/9 counts are the ones to assert; a NUL-scan gives 388/10 and is the
mistake this section exists to prevent.

---

## 4. CLOSED 2026-10-21 — both divergences are settled, and the path is live

Neither gap is open any more, and the third claim (that the code path is
dead) is stale as well.

**§1 — the second header slot.** Settled by reading `FUN_004253cc`'s own
dataflow rather than by guessing between the two candidates this document
left open. The function builds `local_8c` (the icon HTML) first and
`local_78` (the link-or-title) second, and the card format takes them in
that order; `ADD ESP,0x2c` after the call confirms **nine** varargs for the
nine specifiers, so no argument is unaccounted for.

| Slot | Native | Port |
|---|---|---|
| 1 | the service icon, `<img src="%s" style="vertical-align: middle"></img>&nbsp;` over `Services/<name>/Service.ico` | **empty** -- and that is faithful, not a gap |
| 2 | `<a href="%s" class="qt-link-browser" title="Open in browser">%s</a>` when the service has a home page, else the bare title | **emitted** |

The port emits the empty icon slot because native does: the function pushes
the wide `"Service.ico"` at `0x0042546a`, builds the path, calls
`GetFileAttributesW` at `0x004254c3`, and on `CMP EAX,-0x1 / JZ 0x004254e3`
skips the `file:///` format (`PUSH 0x51e7d4`) entirely -- an absent `.ico`
yields **no** `<img>` in slot 1, not a `Default.ico` reference (`0x522a78`
is referenced from a different function and never appears on this path).
Off Windows the file never exists, so the faithful port emits the same
empty slot native would.

Slot 2 is emitted, and its value is native's own `serviceLink()`: the
per-service links table in `dict_render.py` is transcribed from each
`services/*/Service.js`, and `""` means "native has no home page", in
which case the bare title is emitted -- matching the `FUN_00401ec9`
else-branch.

**§2 — the empty-result message.** Emitted. `render_cards([], "hello world")`
now yields native's `No results found for 'hello world'.` in the content
area, with the query substituted in and escaped (it is user input reaching
HTML). This was the more user-visible of the two, and it is closed.

**§3 — "both are in the dead path today" is stale.** The card is no longer
written to a file nothing reads: `qtranslate/windows.py:638` calls
`DR.render_cards(cards, word_q)` and the **Dictionary window** renders it,
so the empty-result message is user-visible today, on a lookup that matches
every service and still yields nothing.

Verified on 2026-10-21:

```
DR.render_cards([], "hello world")   ->  "No results found for 'hello world'."
DR.render_cards([(10, "Google Search", "<p>body</p>")], "hello")
    ->  qt-header carries <a href="https://www.google.com"
        class="qt-link-browser" title="Open in browser">Google Search</a>
```
