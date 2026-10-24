"""Studio -- a MINI-REPO extension, not a single file.

The point of this example is the LAYOUT: a real extension grows into a
package with data files, several modules and cross-module state, and
the loader supports that natively. The manifest's entrypoint is
``__init__:register`` (the folder itself is the package root), and every
module below uses RELATIVE imports -- so the whole tree lives under the
loader's unique per-extension module name, cannot collide with another
extension's files, and never needs to touch ``sys.path`` itself.

    studio/
      manifest.json          -- entrypoint: __init__:register
      __init__.py            -- this file: the thin entrypoint
      bootstrap.py           -- wires the modules onto the host API
      studio_core/
        __init__.py          -- the shared context + settings
        data/glossary.json   -- a DATA file shipped inside the extension
        providers.py         -- 2 providers
        dictionaries.py      -- a dictionary backend
        speech.py            -- tts + ocr + spell backends
        workflow.py          -- the post-translation pipeline
        theme.py             -- two theme records
        ui/panels.py         -- the panel + popup-body renderers
        ui/menus.py          -- the tray + history menu entries
      README.md              -- what each piece is for

Nothing here is exotic: it is exactly the shape a real extension reaches
once it has more than a screenful of code.
"""

from .bootstrap import register

__all__ = ["register"]
