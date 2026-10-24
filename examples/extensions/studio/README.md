# Studio — a mini-repo extension

The other examples fit in one file. A real extension does not stay that
size, and the loader supports the grown-up shape natively:

| piece | what it is |
|---|---|
| `manifest.json` | `entrypoint: "__init__:register"` — the FOLDER is the package root |
| `__init__.py` | the thin entrypoint; imports `bootstrap` relatively |
| `bootstrap.py` | the whole surface in one readable file — every `register_*` call |
| `studio_core/` | the modules: context+settings, providers, dictionary, speech, workflow, themes |
| `studio_core/data/glossary.json` | a DATA FILE shipped inside the extension, loaded by path |
| `studio_core/ui/` | the panel / popup-body / menu renderers |

Why this shape works and matters:

- **Relative imports only.** The loader imports the entrypoint under a
  UNIQUE per-extension module name (`qtranslate_ext_<id>.__init__`), so
  this tree cannot collide with another extension's files or with Core,
  and the extension never touches `sys.path` itself.
- **One context object** (`StudioContext`) carries settings, data and
  counters; the UI renders from it, so a settings change flows through
  without touching the app.
- **Settings are the host's persistence**: `api.get_setting` /
  `set_setting` under `Extensions.Settings.<ext id>`; undeclared keys
  are refused against the manifest's `settings_schema`.
- **Fail-open everywhere**: a missing data file becomes an empty
  glossary, a raising provider hands the chain over, a raising workflow
  step is skipped.

Copy the folder into the per-user extensions directory and restart.
Pinned by `tests/regress_extension_studio.py`, which loads THIS tree
through the real loader and drives every capability across MODULE
BOUNDARIES (a settings change made through the API changes what the
provider, the panel and the workflow render).
