# Wiktionary (example extension)

Free dictionary lookups through the official MediaWiki REST API —
a port of the `.tmp` `wikimedia-reference` plugin's Wiktionary service.

Copy this folder into the per-user extensions directory
(`~/.config/QTranslate/extensions/` off Windows), restart QTranslate,
and "wiktionary" appears as a cell in the dictionary window's bottom
strip. Lookups use the source language's Wiktionary edition when one
exists (`zh-Hans`/`zh-TW` → `zh`), else English; a language with no
edition is a miss, not an error.

Rate limiting follows the plugin: requests are spaced at least 300 ms
apart. Nothing is sent anywhere except `*.wiktionary.org`.
