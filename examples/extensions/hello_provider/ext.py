"""The example extension's entrypoint -- the smallest thing that works.

Copy this folder into the per-user extensions directory, restart
QTranslate, and the provider named ``hello`` is live: pick it in the
main window's service list (or press ``Ctrl+Tab`` until it is selected)
and translate. Break the extension -- rename this file, or raise in
``register`` -- and the app falls open to the built-in providers
instead of failing to start.

The contract is ``docs/EXTENSION_SDK.md`` §3-§4: ``manifest.json``
declares the extension, and the ``entrypoint`` names the
``module:callable`` that receives the SDK's API object.
"""

# The provider's calling convention is the registry's: fn(text, src,
# tgt) -> the translated text (see `qtranslate/registry.py`'s
# TRANSLATORS table).
_PREFIX = "Hello, "


def _hello_translate(text, src, tgt):
    """A provider that needs no network: it echoes the source text.

    The point of the example is the PLUMBING, not the translation.
    """
    return _PREFIX + (text or "")


def register(api):
    """Called once at startup with the SDK's API object."""
    api.register_provider("hello", _hello_translate)
