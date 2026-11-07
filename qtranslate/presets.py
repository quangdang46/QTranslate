"""Service presets -- named bundles of {translator, comparison services}.

Port of .tmp's ``ServicePreset`` + ``PresetManager`` reduced to the
selection points this port actually exposes: the main translator and the
comparison set. .tmp presets also pin TTS/spell/OCR/dictionary role
services, but this port resolves those roles through fallback chains
with no per-role picker, so there is nothing user-visible to store.

Storage (``General`` section of Options.json):

- ``ServicePresets``: list of ``{"id", "name", "translator",
  "comparison": [service keys]}``.
- ``ActivePresetId``: id of the last applied preset, "" when the user
  changed services by hand afterwards.
- ``ActiveService``: the translator key the main window last used --
  written by ``QtApp.switch_service`` so a preset (or a plain strip
  click) survives a restart.
"""

import json
import uuid

PRESETS_KEY = "ServicePresets"
ACTIVE_KEY = "ActivePresetId"
SERVICE_KEY = "ActiveService"


def _general(cfg):
    return cfg.setdefault("General", {})


def _clean(p):
    """One preset dict -> normalized dict, or None when unusable."""
    if not isinstance(p, dict):
        return None
    pid = str(p.get("id") or "")
    name = str(p.get("name") or "").strip()
    translator = str(p.get("translator") or "").strip()
    comp = p.get("comparison") or []
    if isinstance(comp, str):
        comp = [s for s in comp.replace("|", ",").split(",") if s.strip()]
    comparison = [str(s).strip() for s in comp if str(s).strip()]
    if not pid or not name or not translator:
        return None
    return {"id": pid, "name": name, "translator": translator,
            "comparison": comparison}


def presets(cfg):
    """The stored preset list, malformed entries dropped."""
    raw = _general(cfg).get(PRESETS_KEY)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        c = _clean(p)
        if c is not None:
            out.append(c)
    return out


def active_id(cfg):
    return str(_general(cfg).get(ACTIVE_KEY) or "")


def find(cfg, pid):
    for p in presets(cfg):
        if p["id"] == pid:
            return p
    return None


def create(cfg, name, translator, comparison):
    """Append a preset; returns the stored dict (id is a uuid4)."""
    name = str(name or "").strip() or "Preset"
    p = {"id": uuid.uuid4().hex[:12], "name": name,
         "translator": str(translator or ""),
         "comparison": [str(s) for s in (comparison or [])]}
    g = _general(cfg)
    g[PRESETS_KEY] = presets(cfg) + [p]
    return p


def rename(cfg, pid, name):
    name = str(name or "").strip()
    if not name:
        return False
    ps = presets(cfg)
    for p in ps:
        if p["id"] == pid:
            p["name"] = name
            _general(cfg)[PRESETS_KEY] = ps
            return True
    return False


def delete(cfg, pid):
    ps = presets(cfg)
    kept = [p for p in ps if p["id"] != pid]
    if len(kept) == len(ps):
        return False
    _general(cfg)[PRESETS_KEY] = kept
    if active_id(cfg) == pid:
        _general(cfg)[ACTIVE_KEY] = ""
    return True


def snapshot(cfg):
    """The CURRENT service selection as a preset-shaped dict."""
    g = _general(cfg)
    return {"translator": str(g.get(SERVICE_KEY) or ""),
            "comparison": list(g.get("ComparisonServices") or [])}


def apply(cfg, preset):
    """Write a preset's selection into General and mark it active.

    Returns the normalized preset, or None when the id is unknown.
    The caller is responsible for pushing the change into the running
    app (switch_service + comparison refresh).
    """
    p = preset if isinstance(preset, dict) else find(cfg, preset)
    if p is None:
        return None
    p = _clean(p)
    if p is None:
        return None
    g = _general(cfg)
    g[SERVICE_KEY] = p["translator"]
    g["ComparisonServices"] = list(p["comparison"])
    g[ACTIVE_KEY] = p["id"]
    return p


def clear_active(cfg):
    """Manual service changes detach the active preset."""
    if active_id(cfg):
        _general(cfg)[ACTIVE_KEY] = ""
