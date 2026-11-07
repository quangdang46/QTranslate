"""The dictionary lookup — native's dict-task builder (FUN_00414f54).

The lookup itself is not a view thing: it resolves the dictionary
language, asks the selected dictionary services, tries the offline
XDXF dictionaries, and renders the cards. The window around it (the
entry, the service strip, the result pane) is the view's.

It lives here, in Core, because the tkinter front end had it inside
its dictionary window and the PySide6 front end needs the same
behaviour — and because a headless test can now exercise it without
opening a window.

Evidence for the pieces:

* the dictionary language is ``General.LanguageDictionary``, a Google
  language INDEX (17 = "en"), and native overwrites the request's
  target with it when the target is "auto"
  (``docs/review/DICT_LANG_BUILDER_2026-10-15.md``);
* the offline dictionaries come first (native's OfflineDictionaries
  list), then the selected online ones;
* ``DictionaryExactSearch`` (options +0x181) makes the match exact;
  off, it is broadened to a substring match.
"""
from __future__ import annotations

# The dictionary services, by the key the registry uses. The display
# name in the strip is what the settings file names them by, and the
# registry's key is the first word of it in lower case.
SERVICE_KEYS = {
    "Google Search": "google-search",
    "Wikipedia": "wikipedia",
    "Multitran": "multitran",
    "ImTranslator": "imtranslator",
    "WordReference": "wordreference",
    "Babylon": "babylon",
    "Reverso": "reverso",
    "Urban Dictionary": "urban",
    "ABBYY Lingvo Live": "lingvo",
    "youdao": "youdao",
    "Oxford Learner Dictionary": "oxford",
}


def dictionary_language(cfg: dict | None = None) -> str:
    """The language the dictionary lookup runs in, as a code.

    ``General.LanguageDictionary`` holds a Google language INDEX (17 is
    "en"), the same table the main window's language pair uses. A
    language the table does not have falls back to "en", which is what
    native does.
    """
    try:
        if cfg is None:
            from qtranslate import config as _C
            cfg = _C.load() or {}
        from qtranslate import config as _D
        index = int((cfg.get("General", {}) or {}).get(
            "LanguageDictionary", _D.LANG_DEFAULTS["LanguageDictionary"]))
    except Exception:
        index = 17  # the native default; the table import path failed too
    try:
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        table = list(SUPPORTED_LANGS)
    except Exception:
        table = []
    code = table[index] if 0 <= index < len(table) else "en"
    if code in (-1, "auto"):
        code = "en"
    return code


def service_key(display_name: str) -> str:
    """The registry key for a dictionary service's display name."""
    # Extension dictionaries (``api.register_dictionary``) have no
    # display-name mapping -- their strip cell shows the key itself.
    try:
        from qtranslate import registry as _RG
        if display_name in getattr(_RG, "DICT_EXT", {}):
            return display_name
    except Exception:
        pass
    return SERVICE_KEYS.get(display_name, display_name.split()[0].lower()
                            if display_name else "")


def _enabled_dict_keys(cfg: dict | None = None):
    """The registry keys of the ENABLED dictionary services.

    ``DictionariesOrder`` ids minus ``DisabledDictionaries`` -- the same
    set ``qt/dictionary.py::_enabled_dict_ids`` computes for the strip.
    The settings file names dictionaries by numeric id and
    ``config.DICT_DISPLAY`` maps id -> display name, which
    ``service_key`` turns into the ``registry.DICTS`` key, so the filter
    lands on the same names ``search()`` iterates.

    Returns ``None`` when the config cannot be read: a broken settings
    file must not silently empty the lookup, so the caller then skips
    filtering entirely (every registry key stays eligible).
    """
    from qtranslate import config as _C
    try:
        if cfg is None:
            cfg = _C.load() or {}
        order = cfg.get("DictionariesOrder")
        if order is None:
            order = _C.DEFAULT_DICTIONARIES_ORDER
        disabled = set(cfg.get("DisabledDictionaries") or [])
        keys = set()
        for i in order:
            if i in disabled:
                continue
            name = _C.DICT_DISPLAY.get(i)
            if name:
                keys.add(service_key(name))
        return keys
    except Exception:
        return None


def search(word: str, exact: bool = True, services=None, target: str = "vi",
           cfg: dict | None = None):
    """Look ``word`` up. Returns ``(cards, summary)``.

    ``cards`` is the list the renderer takes -- ``(kind, title, text)``
    triples -- and ``summary`` is the plain text the result pane shows
    when the cards cannot be rendered as HTML.

    ``services`` is the list of display names to ask; None means every
    ENABLED dictionary the registry knows. ``DisabledDictionaries`` is
    honoured here too, not only in the Qt window: headless and direct
    callers used to fan out to every ``registry.DICTS`` entry and
    resurrect services the user unchecked on the Services page. An
    explicit ``services`` list is still honoured, but intersected with
    the enabled set -- a disabled id cannot be queried by name either.
    """
    from qtranslate import dict_render as _DR
    from qtranslate import registry as _RG

    word = (word or "").strip()[:500]
    if not word:
        return [], ""

    dsl = dictionary_language(cfg)

    cards = []
    # The offline dictionaries first (native's OfflineDictionaries list).
    try:
        from qtranslate import config as _C
        from qtranslate import xdxf as _X
        offline = (_C.load() or {}).get("OfflineDictionaries", []) or []
        for path in offline:
            try:
                frag = _X.lookup(word, path, exact=exact)
                if frag:
                    cards.append(("xdxf",
                                  path.split("/")[-1].split("\\")[-1],
                                  frag[:8000]))
            except Exception:
                pass
    except Exception:
        pass

    enabled_keys = _enabled_dict_keys(cfg)
    # DICT_EXT entries have no DictionariesOrder id -- they are installed
    # deliberately, so they stay eligible unless the enabled filter is
    # unreadable (None), matching how id-less translate providers join
    # the strip. An extension entry wins over a built-in of the same
    # key, the same last-wins rule sdk.dict_lookup uses.
    ext = getattr(_RG, "DICT_EXT", {}) or {}
    if services is None:
        names = [k for k in _RG.DICTS
                 if enabled_keys is None or k in enabled_keys]
        names += list(ext)
    else:
        names = [service_key(n) for n in services]
    if enabled_keys is not None:
        names = [k for k in names
                 if k in enabled_keys or k in ext]
    for key in names:
        fn = ext.get(key) or _RG.DICTS.get(key)
        if fn is None:
            continue
        try:
            frag = fn(word, dsl, target)
        except Exception:
            continue
        if frag:
            cards.append((key, key, frag[:8000]))

    summary = "\n\n".join("===== %s =====\n%s" % (t, f[:800])
                          for _k, t, f in cards)
    if not summary:
        summary = _DR.NO_RESULTS % word
    return cards, summary


def render(cards, word: str) -> str:
    """The HTML page of the cards (native writes ``dict_last.html``)."""
    from qtranslate import dict_render as _DR
    try:
        return _DR.render_cards(cards, word)
    except Exception:
        return ""
