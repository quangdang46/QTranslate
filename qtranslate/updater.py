"""Updater manifest parser — port of FUN_00461ADE (R2).

Native parses the update manifest JSON from
``https://quest-app.appspot.com/update?v=6.10.0`` (R1, FUN_00461A26 —
endpoint retired 2022). Shape, byte-verified from FUN_00461ADE:

    {
      "urls": [ {"href": "...", "provider": "..."}, ... ],
      "version": "...",
      "date": "...",
      "changelog": "...",
      "<list>": [ {"version": "...", "date": "...", "changelog": "..."}, ... ]
    }

Only the parser is reconstructed (the fetch is dead: the host retired in
2022, so this is classified ``dead:host-retired``). No network here.
"""
from __future__ import annotations

import json


def parse_manifest(text: str) -> dict:
    """Parse an update manifest. Tolerant: missing fields -> empty/default.

    Returns {urls:[{href,provider}], version, date, changelog, history:[...]}.
    Mirrors FUN_00461ADE: it reads `urls` (href+provider pairs), then
    `version`/`date`/`changelog`, then a trailing list of
    {version,date,changelog} entries.
    """
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return {"urls": [], "version": "", "date": "", "changelog": "",
                "history": [], "valid": False}
    if not isinstance(obj, dict):
        return {"urls": [], "version": "", "date": "", "changelog": "",
                "history": [], "valid": False}

    urls = []
    for u in obj.get("urls", []) or []:
        if isinstance(u, dict):
            urls.append({"href": str(u.get("href", "")),
                         "provider": str(u.get("provider", ""))})

    # trailing list: native reads the remaining object member that is an
    # array of {version,date,changelog}. Accept the first such list found
    # beyond the known keys.
    history = []
    for key, val in obj.items():
        if key in ("urls", "version", "date", "changelog"):
            continue
        if isinstance(val, list):
            for it in val:
                if isinstance(it, dict):
                    history.append({
                        "version": str(it.get("version", "")),
                        "date": str(it.get("date", "")),
                        "changelog": str(it.get("changelog", "")),
                    })

    return {
        "urls": urls,
        "version": str(obj.get("version", "")),
        "date": str(obj.get("date", "")),
        "changelog": str(obj.get("changelog", "")),
        "history": history,
        "valid": bool(urls) or "version" in obj,
    }
