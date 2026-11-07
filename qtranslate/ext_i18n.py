"""Extension localization — the portable subset of upstream's
``PluginLocalization`` / ``DisplayText`` mechanism.

Upstream (.tmp ``core/plugin/text``) lets a plugin ship TOML files under
``localization/`` inside its JAR — ``localization/en.toml``,
``localization/de.toml`` — in the same format as the application's own
language files, and resolves a ``DisplayText(key, fallback, args)``
host-strings-first, then the declaring plugin's bundle, then the
fallback. This module ports the parts that survive being a folder of
``.py`` files instead of a JAR:

- An extension ships ``localization/<tag>.toml`` inside its own folder,
  where ``<tag>`` is an ISO language code (``en``, ``de``, ``ar-SA``).
  The TOML uses the same shape as upstream: dotted keys, optionally
  grouped under ``[namespace]`` tables, e.g.::

      [myplugin]
      api_key_rejected_title = "API key rejected"

  which flattens to the key ``myplugin.api_key_rejected_title`` — exactly
  what upstream's ``LanguageTomlParser`` produces for the same file.

- The active UI language comes from ``General.LocaleFoderName`` in
  Options.json, mapped through the locale pack's ``LanguageCode``
  (``"Vietnamese"`` -> ``"vi"``, ``"Chinese (Simplified)"`` ->
  ``"zh-CN"``). Candidate tags are tried most-specific first — the full
  code, its base language (``zh-CN`` -> ``zh``), then ``en`` — the same
  chain upstream documents.

Deliberate divergences from upstream, kept honest rather than silently
different:

- **No host-strings-first step.** Upstream checks the application's own
  string table before the plugin bundle so a plugin cannot shadow UI
  text. This app's locale packs address strings by integer id inside
  ``lang.json`` ``Strings`` pairs, not by the dotted keys extensions
  use, so there is no shared namespace to collide in; the extension
  bundle is the only lookup, then the fallback.
- **No ``DisplayText`` type.** Upstream threads a small value object
  through notify/settings signatures. The port's surface already takes
  plain strings, so ``api.tr(key, fallback, *args)`` resolves and
  formats in one call instead.
- **No ``@reference`` resolution or ``[meta]`` table.** Upstream's
  parser substitutes ``@other.key`` references and reads translation
  metadata; neither is needed for extension UI strings, so ``meta`` is
  ignored and ``@`` values are returned literally.
"""
from __future__ import annotations

import os

_BUNDLE_DIR = "localization"
_BASE_LANGUAGE = "en"

# (folder, tag, mtime, size) -> flattened {dotted_key: text}. Bundles are
# tiny and read once per tag per file version; the stat fields keep a
# re-written file from serving a stale translation.
_cache = {}
_CACHE_LIMIT = 256


def _flatten(node, prefix, out):
    """Flatten a parsed TOML table into ``{dotted.key: str}``.

    Only string leaves are kept — upstream's entries map is
    ``Map<String, String>`` too, so a number or array in a plugin bundle
    is not a translation. The ``meta`` table is skipped for the same
    reason upstream's parser routes it to ``LocalizedLanguageMeta``
    instead of the entries map.
    """
    for key, value in node.items():
        if prefix == "" and key == "meta":
            continue
        full = "%s.%s" % (prefix, key) if prefix else str(key)
        if isinstance(value, dict):
            _flatten(value, full, out)
        elif isinstance(value, str):
            out[full] = value


def _parse_bundle(path):
    """One ``localization/<tag>.toml`` -> flattened entries, or {}."""
    try:
        import tomllib
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:                       # noqa: BLE001 -- fail-open:
        return {}                           # a bad bundle costs the
                                             # extension its translations,
                                             # never the app its load
    if not isinstance(data, dict):
        return {}
    out = {}
    _flatten(data, "", out)
    return out


def bundle_for(folder, tag):
    """The extension's flattened strings for ``tag`` (cached by version)."""
    path = os.path.join(folder or "", _BUNDLE_DIR, tag + ".toml")
    try:
        st = os.stat(path)
    except OSError:
        return {}
    key = (os.path.abspath(folder), tag, st.st_mtime_ns, st.st_size)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    entries = _parse_bundle(path)
    if len(_cache) >= _CACHE_LIMIT:
        _cache.clear()
    _cache[key] = entries
    return entries


def active_language_tag():
    """The UI language as an ISO tag (``"en"``, ``"vi"``, ``"zh-CN"``).

    ``General.LocaleFoderName`` names a locale *pack folder*
    (``"Vietnamese"``); the pack's own ``LanguageCode`` is the tag
    upstream's ``LanguageCode.tag`` corresponds to. Any failure — no
    config, no pack, no code — falls back to ``"en"``, which is also the
    terminal candidate of every chain, so a broken setting degrades to
    English strings rather than none.
    """
    try:
        from qtranslate import config as _C
        from qtranslate import locale as _L
        name = str((_C.load() or {}).get("General", {})
                   .get("LocaleFoderName") or "English")
        code = str(_L.load_pack(name).get("LanguageCode") or "")
        if code:
            return code
    except Exception:                       # noqa: BLE001
        pass
    return _BASE_LANGUAGE


def candidate_tags(tag):
    """Tags to try, most specific first: ``zh-CN`` -> ``zh-CN``, ``zh``,
    ``en`` — upstream's written-then-base-then-English chain."""
    tag = str(tag or _BASE_LANGUAGE)
    tags = [tag]
    base = tag.split("-", 1)[0]
    if base != tag:
        tags.append(base)
    if _BASE_LANGUAGE not in tags:
        tags.append(_BASE_LANGUAGE)
    return tags


def translate(folder, key, tag=None):
    """The extension's own translation for ``key``, or None.

    ``folder`` is the extension's install folder (the one holding
    ``manifest.json``); ``None``/missing folder yields None, so an api
    used outside ``load_dir`` simply renders fallbacks. None is the
    normal answer — most extensions ship no bundle — not an error.
    """
    if not folder or not key:
        return None
    if tag is None:
        tag = active_language_tag()
    for candidate in candidate_tags(tag):
        value = bundle_for(folder, candidate).get(str(key))
        if value is not None:
            return value
    return None


def clear_cache():
    """Drop every cached bundle (tests, and a host that rewrites packs)."""
    _cache.clear()
