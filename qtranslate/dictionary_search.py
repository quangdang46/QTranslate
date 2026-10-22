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
    return SERVICE_KEYS.get(display_name, display_name.split()[0].lower()
                            if display_name else "")


def search(word: str, exact: bool = True, services=None, target: str = "vi",
           cfg: dict | None = None):
    """Look ``word`` up. Returns ``(cards, summary)``.

    ``cards`` is the list the renderer takes -- ``(kind, title, text)``
    triples -- and ``summary`` is the plain text the result pane shows
    when the cards cannot be rendered as HTML.

    ``services`` is the list of display names to ask; None means every
    dictionary the registry knows.
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

    if services is None:
        names = list(_RG.DICTS)
    else:
        names = [service_key(n) for n in services]
    for key in names:
        fn = _RG.DICTS.get(key)
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
