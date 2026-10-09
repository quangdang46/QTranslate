# The native dictionary card builder, decompiled — and three divergences in `dict_render.py`

> Read-only verification from the **full-analysis** project `QT_FULL`.
> This supersedes the card-level part of `DICT_TEMPLATE_NATIVE_2026-10-10.md`
> (whose *shell template* finding is correct and unchanged) by supplying the
> one artifact it could not: **the format string native actually fills in**.
>
> It also corrects my own `SERVICE_JS_PROVENANCE_2026-10-10.md`, in the same
> way qtranslate-ed corrected theirs: a true fact about a string that is not
> the claim under test.
>
> No row state changed by this document.

## 1. `FUN_004253cc` — the per-card builder

The card HTML is not assembled by string concatenation in Python-space; it is a
**single wide format string** the native code `printf`s, and it is the
authoritative shape of a dictionary card:

```c
FUN_004023f1(&local_84, L
  "<div id=\"qt-s%u\" class=\"qt-card\">"
  "<div id=\"qt-h%u\" class=\"qt-header\" ondblclick=\"toggle(%u);\" onselectstart=\"return false;\">%s%s</div>"
  "<div id=\"qt-d%u\" class=\"qt-data\">"
  "<input type=\"button\" id=\"qt-l%u\" onclick=\"fullEntry(%u);return false;\" class=\"qt-read-more\" value=\"READ MORE\"></input>"
  "%s</div></div>");
```

Literal at file offset **`0x11d8f0`**, 298 chars, RVA `0x11e8f0` / VA
`0x51e8f0`, referenced exactly once (xref at `0x42559d`) — so `FUN_004253cc` is
its only consumer, and this is not a duplicate string from another path.

The eight substitution points are, in order: service id twice for the card and
header ids, id again for the `toggle` argument, then **two** `%s` for the header
(`icon + link`), then the data id, the `qt-l` id, the `fullEntry` id, and the
data `%s`.

### The header's two `%s` are built first, and this is the interesting part

```c
FUN_004023f1(&local_8c, L"<img src=\"%s\" style=\"vertical-align: middle\"></img>&nbsp;");
if (local_84 == 0 && (puVar1[5] - 0xc) != 0 && FUN_00403897(puVar1) == '\0') {
    FUN_004023f1(&local_78,
        L"<a href=\"%s\" class=\"qt-link-browser\" title=\"Open in browser\">%s</a>");
} else {
    FUN_00401ec9(&local_78, piVar2);
}
```

So the header is `[icon img] + [optional "open in browser" link] + title`, and
the icon source is either the service's `Service.ico` under `Services/<name>/`
or — when it exists — a `file:///` URL:

```c
if (local_84 == 0) { ... L"Services" ... L"Service.ico" ... }
...
DVar4 = GetFileAttributesW(local_88);
if (DVar4 == 0xffffffff) { ...default icon... } else { FUN_004023f1(&local_80, L"file:///%s"); }
```

This is the same `Services/<name>/Service.ico` load that `FUN_0045d024`
performs in the plugin loader (`PLUGIN_LOADER_FOUND_2026-10-10.md`) — the icon
path is derived from the service directory, independently in both places.

### The JS calls, and the conditional between them

```c
FUN_00423d7f(*(void **)((int)local_6c + 0x108), L"appendMenuItem", auStack_50, 3);   // 3 args
...
if (local_6c != (void *)0x1) { pwVar7 = L"checkEntry"; } else { pwVar7 = L"fullEntry"; }
FUN_00423d7f(*(void **)(iVar9 + 0x108), pwVar7, auStack_60, 1);                    // 1 arg
...
if (1 < *(uint *)(iStack_28 + 0x180)) {   // more than one card
    FUN_00423d7f(*(void **)(iStack_28 + 0x108), L"showNavigation", 0, 0);
}
```

`FUN_00423d7f(obj, name, args, argc)` is the **host->JS call** — the same shape
as `FUN_0043b942(local_6c, L"serviceHeader", 0, 0, &local_8)` in the plugin
loader. So native really does drive `appendMenuItem`, `checkEntry`/`fullEntry`
and `showNavigation` through the script engine, which is the first time that is
seen in a decompile rather than inferred from the template's function names.

Three details the template alone could never give:

1. **`checkEntry` vs `fullEntry` is a real branch**, on `local_6c != 1`. Native
   calls `checkEntry` normally and `fullEntry` in some other state — the
   template ships both functions, and now we know both are reachable.
2. **`showNavigation()` is conditional on a counter being `> 1`**, i.e. **only
   when more than one service rendered**. `dict_render.py` emits
   `if(...length>1)showNavigation();` in JS, the same condition expressed
   client-side. That matches.
3. **`appendMenuItem` takes 3 arguments**, matching the template's
   `function appendMenuItem(id, title, iconUrl)`. The port's own
   `appendMenuItem({sid}, {title!r}, '')` is 3-positional. That matches too.

## 2. Three divergences in `qtranslate/dict_render.py`

Measured against the format string above, not against the template (the
template and the port agree with each other; the **port's emitter** is the
outlier):

| # | Native (`0x11d8f0`) | Port (`dict_render.py:26-30`) | Verdict |
|---|---|---|---|
| 1 | `ondblclick="toggle(%u);"` | `onclick="toggle(7)"` | **diverges** — native toggles on **double**-click |
| 2 | `onselectstart="return false;"` | absent | **diverges** — native suppresses selection start on the header |
| 3 | `<input type="button" ... value="READ MORE"></input>` | `<a ... href="javascript:void(0)" ... >more...</a>` | **diverges** — element type *and* label text |
| 4 | no `style="display:none"` on `qt-l`; `checkEntry` reveals it | `style="display:none"` inline | **diverges in mechanism, same intent** — native leaves it visible-by-default and lets `checkEntry` decide; the port hides it unconditionally |

Divergences 1-3 are real behavioural differences, not cosmetics: a single
click on a native service header does not collapse the entry, and the native
reveal control is a button reading **`READ MORE`**, not a link reading
`more...`.

Divergence 4 is subtler and arguably the port is *safer*: hiding the control
until `checkEntry` decides works when there is no JS, whereas native's version
renders a stray `READ MORE` button on a JS-less host. But it is a divergence,
and it is the one that keeps the port from being a faithful port if a JS engine
is ever attached.

**These are all in the dead path anyway** — `app.py:3534` builds the page and
never renders it (`DICT_TEMPLATE_UNRENDERED_2026-10-10.md`, independently
confirmed by qtranslate-ed). So none of the four is user-visible today. That is
the honest framing: they are latent divergences in an unexecuted code path, and
they should be fixed *before* the render model is fixed, not after.

## 3. Correction to my own `SERVICE_JS_PROVENANCE_2026-10-10.md`

That document said "the wide-string set that IS present is exactly the natively
compiled clients... So E2/E3/E5/E7 are image-checkable". qtranslate-ed was right
that this was overstated, and the card format string is a second instance of
the same lesson from the other direction:

- The strings I read as "native compiled-in endpoints"
  (`https://www.bing.com/translator`,
  `https://www.bing.com/ttranslatev3`,
  `var params_RichTranslateHelper = [`,
  `/translate_a/element.js`, `_ctkk='`) are **embedded JS source**, sitting in
  the script-source pool next to the dictionary template — not native
  compiled-in client strings. The host is `base::ActiveScript` /
  `base::ActiveScriptSite` / `services::Script` / `plugins::HistoryScript`
  (RTTI names present, `CoCreateInstance` imported, no `JScript` literal),
  i.e. Windows Scripting via COM.
- So "image-checkable" is even weaker than the peer's corrected version. Their
  sharper rule — *an endpoint is image-verifiable only when the full path the
  row cites is a literal* — is the one to keep, and by that rule
  `/translate_a/single`, `/api/v1/tr.json/translate`, `/v2transapi` and
  `/tlookupv3` are **all absent**, leaving essentially nothing
  endpoint-verifiable.

The distinction I got wrong twice has the same root both times: **the string
pool is heterogeneous.** `qt-s%u` (a native format string),
`https://www.bing.com/ttranslatev3` (JS source), `ServicesOrder` (a config key)
and `serviceHeader` (a JS hook name) all live in `.rdata` and all look alike to
a content search. Presence proves a string exists there; it does not identify
which layer authored it. The only way to tell is to find the consumer and read
it — which is what `Enclosing.java` -> `DecompileNamed.java` did here.

## 4. Method note

The xref hunt started from an immediate-scan that misled
`SERVICE_JS_PROVENANCE` (an operand reuse pointed at an `Options.json`
handler). The corrected sequence, which is what found `FUN_004253cc`:

1. **`-noanalysis` is not enough.** Under it, five of seven xrefs to the
   `Service.js` string had no enclosing function, so the loader was invisible.
   A full-analysis run is a *deliberate separate step*, not a background
   pancake — qtranslate-ed's wording, and it is right.
2. **Map xref -> containing function** with `tools/ghidra/Enclosing.java`;
   immediate-scan offsets are instruction operands, not entry points, and
   `DecompileNamed.java` reports `NOT FOUND` on them.
3. **Then decompile the consumer**, never infer its role from the string it
   references. `FUN_004253cc` referencing the card format string is how it was
   found; reading it is how the `ondblclick`/`READ MORE` divergences surfaced.
