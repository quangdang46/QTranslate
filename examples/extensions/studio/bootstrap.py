"""Studio's wiring: every module meets the host API exactly once, here.

This is the file a reviewer reads first: it IS the extension's surface.
Each factory receives the shared context and returns a callable the
host stores in its live dispatch table.
"""

from .studio_core import StudioContext
from .studio_core import dictionaries, providers, speech, theme, workflow
from .studio_core.ui import menus, panels


def register(api):
    ctx = StudioContext(api)

    api.register_provider("studio.glossary", providers.make_glossary(ctx))
    api.register_provider("studio.summariser",
                          providers.make_summariser(ctx))
    api.register_dictionary("studio.dict", dictionaries.make_dictionary(ctx))
    api.register_tts("studio.tts", speech.make_tts(ctx))
    api.register_ocr("studio.ocr", speech.make_ocr(ctx))
    api.register_spell("studio.spell", speech.make_spell(ctx))
    api.register_workflow("studio.pipeline", workflow.make_pipeline(ctx))
    api.register_theme("studio_dark", theme.DARK)
    api.register_theme("studio_high_contrast", theme.HIGH_CONTRAST)
    api.register_ui("menu", "tray", menus.make_tray_entry(ctx))
    api.register_ui("menu", "history_ctx", menus.make_history_entry(ctx))
    api.register_ui("panel", "top", panels.make_top_panel(ctx))
    api.register_ui("popup", "body", panels.make_popup_body(ctx))
    return ctx
