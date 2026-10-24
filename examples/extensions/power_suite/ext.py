"""A WORKED example: one extension, all eight capabilities, done the way
a real one would be written.

The three shipped examples (``hello_provider``, ``custom_ui``,
``custom_theme``) each show ONE plumbing path with three lines of
behaviour. This one is the other half of the story -- the parts you
need before an extension survives contact with a user:

* a provider with LANGUAGE GATING (it only claims the pairs it can
  serve) and CLASSIFIED FAILURES (it raises on a miss instead of
  returning a wrong answer, so the engine's fallback chain takes over);
* a post-translation WORKFLOW step that annotates the result -- and
  knows a step that raises is skipped, never fatal;
* dictionary / TTS / OCR / spell backends with the signatures the live
  dispatch tables expect;
* a POPUP body renderer and a tray-menu entry through the UI slots;
* a PARTIAL theme record (unset slots inherit, exactly like a partial
  native theme file);
* STATE that survives a restart, written to the extension's OWN file in
  the per-user data dir (D16) -- never into the app's Options.json and
  never into its own install folder;
* an OVERRIDE declared in the manifest, so the user -- not the load
  order -- decides whether it wins (D18).

Copy this folder into the per-user extensions directory and restart
QTranslate. Delete the folder and every table it wrote disappears with
it: the loader is the only writer.

The contract is ``docs/EXTENSION_SDK.md`` (§4 manifest, §6 override
rules, §7 fail-open, §9 capability table).
"""

import json
import os

# ---------------------------------------------------------------- state --
# D16: per-user data dir, extension-scoped file. The app's own
# Options.json is the APP's file; an extension must not squat in it.
try:
    from qtranslate.platforms import app_data_dir

    _STATE_PATH = os.path.join(app_data_dir(), "extensions",
                               "power_suite_state.json")
except Exception:                       # noqa: BLE001 -- headless/frozen
    _STATE_PATH = None


def _load_state():
    """The persisted state, or the defaults on any failure.

    Fail-open at every layer: a corrupt state file must not stop the
    extension from loading, because §7 makes the whole extension
    disabled the moment ``register`` raises.
    """
    try:
        with open(_STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                   # noqa: BLE001
        return {"lookups": 0}


def _save_state(state):
    if not _STATE_PATH:
        return
    try:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:                   # noqa: BLE001
        pass                            # read-only disk: keep serving


# ------------------------------------------------------------- provider --
# A GLOSSARY provider: exact matches only, and it SAYS SO. A provider
# that quietly returned the input on a miss would be worse than one
# that raises -- the engine classifies a raise as "this provider has no
# answer" and falls through to the next in the chain (RELIABILITY.md).
_GLOSSARY = {
    ("en", "vi"): {"good morning": "chào buổi sáng",
                   "thank you": "cảm ơn"},
    ("en", "ja"): {"good morning": "おはようございます",
                   "thank you": "ありがとう"},
}
GREETING = "〔glossary〕"


def glossary_translate(text, src, tgt):
    """``fn(text, src, tgt) -> str`` -- the registry's provider shape.

    ``src`` may be ``"auto"``: this provider cannot detect, so an auto
    request for a word it knows in one language still may not be served
    -- raising here is the honest answer, and the chain answers instead.
    """
    key = text.strip().lower()
    hit = _GLOSSARY.get((src, tgt), {}).get(key)
    if hit is None:
        # Anything works as the error; the engine records the provider
        # in ``Result.failures`` either way. A custom exception class
        # would only matter if the extension also caught its own.
        raise LookupError("glossary: no entry for %r %s->%s"
                          % (key, src, tgt))
    state = _load_state()
    state["lookups"] = state.get("lookups", 0) + 1
    _save_state(state)
    return "%s %s" % (GREETING, hit)


def broken_translate(text, src, tgt):
    """Deliberately broken, to show the fail-open rule with skin on.

    Registering this is safe: when the engine picks it, the raise lands
    in ``Result.failures`` and the next provider answers. Remove it
    once the shape is familiar.
    """
    raise RuntimeError("power_suite: this provider is broken ON PURPOSE")


# ----------------------------------------------------------- dictionary --
def glossary_lookup(word, src, tgt):
    """``fn(word, src, tgt)`` -- the dict-dispatch shape."""
    hit = _GLOSSARY.get((src, tgt), {}).get(word.strip().lower())
    if hit is None:
        raise LookupError("glossary: no dictionary entry")
    return "<b>%s</b>: %s <i>(glossary)</i>" % (word, hit)


# ------------------------------------------------------------------ tts --
def beep_tts(text, lang, slow=False):
    """``fn(text, lang, slow=False)`` -- play or die; the player tries
    the next backend when this raises. No audio hardware is touched
    here: the example just proves the resolution order."""
    with open(os.devnull, "w"):
        pass                            # the "playback"


# ------------------------------------------------------------------ ocr --
def upper_ocr(image_bytes, lang, api_key):
    """``fn(image_bytes, lang, api_key) -> str``.

    A real recogniser decodes the bytes; this one refuses without a key
    the way a hosted one would, so the error path is visible too.
    """
    if not api_key:
        raise RuntimeError("power_suite.ocr: an API key is required")
    return ""


# ---------------------------------------------------------------- spell --
def prefix_spell(text, lang):
    """``fn(text, lang) -> list`` -- native's suggest shape."""
    return [text + "-ish"]


# ------------------------------------------------------------- workflow --
def annotate_workflow(text, src, tgt):
    """``fn(text, src, tgt) -> text`` -- runs on a FINISHED translation.

    A step that raises is skipped (engine._run_workflows), so this one
    guards its own edges instead of trusting the caller.
    """
    if not isinstance(text, str) or not text:
        return text
    words = len(text.split())
    return "%s  〔%d words, %s->%s〕" % (text, words, src, tgt)


# ------------------------------------------------------------------- ui --
def tray_entry():
    """The tray-menu callable: the host adds one action per entry."""
    return "Power suite: %d glossary lookups so far" % (
        _load_state().get("lookups", 0))


def popup_body(source, result, pair):
    """``("popup", "body")`` -- render the popup's body text.

    The host tries ``contrib(source, result, pair)`` first and falls
    back to ``contrib(result)``; returning None leaves the built-in
    body alone.
    """
    return "%s\n── via power_suite (%s) ──" % (result or source, pair)


def top_panel():
    """``("panel", "top")`` -- the main window's top strip."""
    return "power_suite active"


# ---------------------------------------------------------------- theme --
# A PARTIAL record: only the slots named are claimed; everything else
# reports UNSET and inherits (Slice 9a). Same shape as a partial native
# theme file -- an extension never needs the full palette.
_THEME = {
    "Common": {"ClientBackColor": "101418"},
    "Window": {"Normal": {"Back": "101418", "Text": "d7e3f4"}},
}


def register(api):
    """Called once at startup with the host's ExtensionAPI object.

    Every register_* call here lands in a LIVE dispatch table the app
    reads in place -- no copy, no re-import. A raise anywhere in this
    function disables the whole extension and the app continues (§7).
    """
    api.register_provider("power.glossary", glossary_translate)
    api.register_provider("power.broken", broken_translate)
    api.register_dictionary("power.glossary", glossary_lookup)
    api.register_tts("power.beep", beep_tts)
    api.register_ocr("power.ocr", upper_ocr)
    api.register_spell("power.spell", prefix_spell)
    api.register_workflow("power.annotate", annotate_workflow)
    api.register_ui("menu", "tray", tray_entry)
    api.register_ui("popup", "body", popup_body)
    api.register_ui("panel", "top", top_panel)
    api.register_theme("power_dark", _THEME)
