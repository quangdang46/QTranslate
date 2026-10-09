# The native dictionary template is verified — but the port never renders it

> Read-only verification, and **a correction to
> `DICT_TEMPLATE_NATIVE_2026-10-10.md` §3**, whose central conclusion I
> re-measured rather than accepted.
>
> The byte-level finding in that document stands: I independently reproduced
> the offset (`0x157d08`), the length (3062), and the zero-delta
> CRLF-normalized equality against `qtranslate/dict_template.html`, and the
> whole element-id contract. **The framing of what that buys the port does not
> stand**, and the difference is not cosmetic.

## 1. What I confirmed independently

Re-derived, not taken from the peer's numbers:

```python
blob  = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
native = blob[0x157d08:0x157d08 + 3062]     # ends at first NUL: \r\n</html>\r\n
port   = open("qtranslate/dict_template.html", "rb").read()
native.replace(b"\r\n", b"\n") == port      # True, zero delta
```

The id contract, read out of the native JS itself rather than from the
peer's table:

| Accessor | Native source (verbatim) |
|---|---|
| service | `function service(id) { return $("qt-s" + id); }` |
| header | `function header(id)  { return $("qt-h" + id); }` |
| data | `function data(id)    { return $("qt-d" + id); }` |
| link | `function link(id)    { return $("qt-l" + id); }` |

plus the clip, which is a hardcoded literal in the function body:

```js
function checkEntry(id) {
  var h = data(id).offsetHeight;
  if (h > 200) { data(id).style.height = "200px"; link(id).style.display = "block"; }
}
```

and the nav-id assignment, which confirms `li<id>`:

```js
var li = document.createElement('li');
li.setAttribute("id", "li" + id);
$("qt-menu").appendChild(li);
```

`showNavigation()` sets `qt-content`'s `margin-left` to `24px` and reveals
`qt-navigation`. Containers `qt-navigation` / `qt-menu` / `qt-content` are the
three `getElementById` literals in the file (`$('id')` is the wrapper). Eight
functions: `service header data link toggle checkEntry fullEntry
appendMenuItem showNavigation` (nine including `$`).

So `dict_render.py`'s emitted ids — `qt-s/h/d/l{id}` at lines 26-30 — and its
`appendMenuItem(...)`, `checkEntry(...)` calls at 32-33 match native's
contract exactly. Nothing in the peer's §1/§2 needs correcting.

## 2. The correction: no JS engine is ever involved

> **`DICT_TEMPLATE_NATIVE_2026-10-10.md` §3 says the 200px clip is honoured
> "by loading native's own JS rather than by a Python reimplementation". That
> is not what the port does.**

`dict_render.render_cards()` does build the complete page — I confirmed the
built string carries `qt-s1..qt-l2`, three `appendMenuItem(...)` calls and
three `checkEntry(...)` calls. But the call site in `app.py:3534` discards it:

```python
page = DR.render_cards(cards)              # app.py:3534
try:
    open("dict_last.html", "w", encoding="utf-8").write(page)   # written to disk
except Exception:
    pass
summary = "\n\n".join(                     # app.py:3539
    f"===== {t} =====\n" + _strip_html(f)[:800]
    for _, t, f in cards)
```

`page` is never used again. The user-visible widget is a Tk `Text` filled with
`summary` — the fragments with tags stripped, concatenated with a `=====` rule.
`dict_last.html` is a write-only debug artifact.

I checked every browser path in the program to make sure the page reaches one
somewhere else: the only `webbrowser` uses in `app.py` are at `:477` (`_open_url`,
honouring `Advanced.DefaultBrowserId`), `:1062` and `:1212` (both opening a
dictionary service's external *link* via `_dict_service_link`). All three open a
URL. **None loads the rendered page.** There is no `WebBrowser` control, no
`tkhtml`, no embedded webview anywhere in `qtranslate/`.

**Consequence, stated plainly:** the 200px clip does not run in this port on
any host, with or without a working JS engine. Native shows a collapsible
per-service card set with a 24px nav column and a "more..." link on long
entries; the port shows flat stripped text under `=====` headings in a `Text`
widget. That is a rendering-model difference, not a fidelity delta.

## 3. What this does to the classification argument

The peer's §3 declined to promote the dictionary row to `behaviour-verified`
on the grounds that the distinction "is a G9-class runtime question". I agree
with the outcome and want to record why the *reason* is stronger than stated:

A template that is byte-identical is real evidence — that the port **copied the
right bytes**. It is not evidence that the port **behaves** like native, because
the thing the template does (clip at 200px, collapse via `toggle`, expand via
`fullEntry`, reveal a 24px nav) is performed by JS in the page, and the port
never executes that JS. Byte-identity of a dead artifact is not
behavioural verification; it is a *precondition* for it. The row's `ported`
state is correct and the reason is that the render model is different, not that
rendered pixel output is hard to reach.

## 4. The risk, re-scoped

The peer asked me to record this: "the 200px clip is honoured *because the port
loads native's own JS* … it silently vanishes on a host without a working JS
engine. Nobody has measured what happens there."

Two corrections to that framing:

1. **The clip does not vanish without a JS engine — it never exists.** There is
   nothing to lose; `checkEntry` is never invoked. The scenario "host without a
   working JS engine" is not reachable from this code, because the page is not
   loaded by an engine at all.
2. **What would have to exist for the risk to be real:** a browser/webview pane
   that loads `dict_last.html`. That is a G9-class addition — it needs a
   WebBrowser control on Windows (or a bundled renderer), i.e. it is exactly
   the missing piece, not a caveat on an existing one. If it is ever added, the
   port gains the 200px clip and the nav for free, *because* the template is
   byte-identical. That is the honest value of the peer's finding: it makes a
   future webview pane cheap, and it is not a current behaviour.

## 5. Not verified by me

- The **scripting** claim is static. I did not run the port under Tk (no
  `_tkinter` on this host) to watch which widget receives the text; I read
  `_show()` and confirmed it inserts `summary` into `out`. Device-independent,
  but it is a code read, not an observation.
- Which dictionary **services** work is untested. My input was two synthetic
  cards with `"Google"` and `"Oxford"` titles; the live-service branches in the
  `work()` loop need a machine that can reach them.
- Native's own rendering is verified only as **template + JS contract**, never
  as a rendered page (`G9_RESULT_2026-10-09.md`: no Windows host).
