# power_suite — a worked, all-capabilities extension

The three sibling examples (`hello_provider`, `custom_ui`, `custom_theme`)
each show one plumbing path. This one is the whole surface at once —
all eight capabilities in one extension, plus the parts a real one
needs before it survives a user:

| capability | what `ext.py` registers | what the app does with it |
|---|---|---|
| `provider` | `power.glossary` (exact-match glossary, raises on a miss) and `power.broken` (raises always) | `engine.translate` — a raise means "no answer", the fallback chain answers instead |
| `dictionary` | `power.glossary` | `sdk.dict_lookup` / the dictionary window |
| `tts` | `power.beep` | `player.play_text` tries extension backends first, built-ins on raise |
| `ocr` | `power.ocr` | `services.ocr.ocr_text` |
| `spell` | `power.spell` | the suggest path |
| `workflow` | `power.annotate` | runs on a FINISHED translation; a raising step is skipped, never fatal |
| `theme` | `power_dark` — a PARTIAL record | Options → Appearance lists it; unset slots inherit slot-by-slot |
| `ui` | tray menu entry, `("popup","body")` renderer, top panel | the running hosts read the slots live |

Non-capability lessons in the same file:

- **State that survives restarts** goes to the extension's OWN file under
  the per-user data dir (`D16`) — never the app's `Options.json`, never
  the install folder.
- **Fail-open everywhere**: a corrupt state file, a raising provider, a
  raising workflow step — each degrades to the built-in behaviour
  instead of taking the app down (`EXTENSION_SDK.md` §7).
- **Override is the user's decision** (`D18`): declare `replaces` in the
  manifest; the runtime never lets load order decide.

Copy the folder into the per-user extensions directory, restart, and
the tray entry reports the persisted lookup count. Delete the folder
and every table it wrote disappears — the loader is the only writer.

Pinned by `tests/regress_extension_power_suite.py`, which loads THIS
folder through the real loader and drives every capability through the
real call path.
