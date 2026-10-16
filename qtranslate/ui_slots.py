"""UI extension slots — Phase 7's "publish the slots" half.

Phase 7 asks for *"Publish UI extension slots; migrate theme/panel/menu/popup
extension points"*. The theme and provider slots already exist
(`extensions.py`'s `register_theme` / `register_provider`, and the
`theme.slot()` accessors). This module publishes the remaining three —
**menu**, **panel**, and **popup** — as named slots with a declared shape.

The names are not invented. They come from the native UI surface, which the
locale packs enumerate verbatim (`qtranslate/locale.py`):

* **menu** — every `Menus[].Id` in a pack, with its ``[id, text]`` item
  pairs. Ten menus ship (main 1, source-context 2, result-context 3, ...,
  tray 5, OCR 10), and every item id is a slot an extension can target.
* **panel** — the three showable panes the native Options page toggles:
  `ShowTopPane`, `ShowMiddlePane`, `ShowServicesPane`.
* **popup** — the popup window and its icon row (`PopupWindowIcons`).

An extension registers against one of these names and gets a deterministic
place in the order; nothing here imports tkinter, so Core and headless
callers can build and inspect the composition without a display.

Conflict policy, same as the provider/theme slots (`extensions.py`):
last-registered wins, and a declared ``replaces`` binds a conflict to a name
so the outcome never depends on discovery order.
"""
from __future__ import annotations

import dataclasses

# ---------------------------------------------------------------- the slots

MENU_SLOTS = ("menu", )
PANEL_SLOTS = ("panel", )
POPUP_SLOTS = ("popup", )

UI_KINDS = MENU_SLOTS + PANEL_SLOTS + POPUP_SLOTS

# The native pane toggles, verbatim from the Options/Basics page and the
# locale packs' main menu (id 1, items 65/70/80 = the three Show*Pane
# entries). Their option keys are what the native UI reads, so an extension
# panel claims one of THESE to be placed in it.
PANES = ("top", "middle", "services")


@dataclasses.dataclass(frozen=True)
class Slot:
    """One published UI slot, with the shape an extension fills."""

    kind: str          # "menu" | "panel" | "popup"
    name: str          # the slot's stable identifier
    native_id: int | None = None   # the native control/menu id, when known
    doc: str = ""


# The menu slots, with the native ids the locale packs declare. Only the
# ones an extension may extend are published; an internal menu with no
# extension surface is listed as closed rather than omitted, so nobody has
# to guess whether an absence is deliberate.
MENU_SLOT_IDS = {
    # name            native menu id   what it is
    "main":           1,    # main window's context menu (source pane)
    "source_context": 2,    # source-text context menu
    "result_context": 3,    # result-text context menu
    "language":       4,    # language-combo context menu
    "tray":           5,    # system-tray menu
    "history_ctx":    6,    # history row context menu
    "dict_header":    7,    # dictionary window header menu
    "history_menu":   9,    # history window menu
    "ocr":            10,   # text-recognition (OCR) window menu
}


def menu_slots() -> list[Slot]:
    """The published menu slots, in native-id order."""
    return [Slot("menu", name, mid, "native Menus[].Id %d" % mid)
            for name, mid in sorted(MENU_SLOT_IDS.items(),
                                    key=lambda kv: kv[1])]


def panel_slots() -> list[Slot]:
    """The three showable panes native's Options page toggles."""
    doc = "native Options key Show%sPane" % name.capitalize()
    return [Slot("panel", name, None, doc) for name in PANES]


def popup_slots() -> list[Slot]:
    """The popup window's icon row and its body."""
    return [Slot("popup", "icons", None, "native PopupWindowIcons"),
            Slot("popup", "body", None, "the popup's content pane")]


def all_slots() -> list[Slot]:
    """Every published slot, in a stable order."""
    return menu_slots() + panel_slots() + popup_slots()


def slot_names(kind: str | None = None) -> tuple:
    """The slot names, optionally for one kind."""
    out = tuple(s.name for s in all_slots() if kind in (None, s.kind))
    return out


# ------------------------------------------------------------- the registry

class UISlotRegistry:
    """Extension contributions to UI slots, with last-wins conflict policy.

    Mirrors `extensions.ExtensionManager`'s policy rather than inventing a
    second one: a contribution carries an optional ``replaces`` name, so a
    conflict is decided by declaration instead of by load order. Without it
    the later registration wins, which is the same rule the provider and
    theme slots use.
    """

    def __init__(self):
        self._slots: dict[tuple, list] = {}

    def _key(self, kind: str, name: str) -> tuple:
        if kind not in UI_KINDS:
            raise ValueError("unknown UI slot kind %r (want one of %r)"
                             % (kind, list(UI_KINDS)))
        if kind == "menu" and name not in MENU_SLOT_IDS:
            raise ValueError("unknown menu slot %r (want one of %r)"
                             % (name, sorted(MENU_SLOT_IDS)))
        if kind == "panel" and name not in PANES:
            raise ValueError("unknown panel slot %r (want one of %r)"
                             % (name, list(PANES)))
        if kind == "popup" and name not in ("icons", "body"):
            raise ValueError("unknown popup slot %r (want 'icons'/'body')"
                             % (name,))
        return (kind, name)

    def add(self, kind: str, name: str, contribution, replaces: str = "") \
            -> str:
        """Register a contribution; returns the winning owner's label."""
        key = self._key(kind, name)
        label = replaces or self._label(contribution)
        self._slots.setdefault(key, []).append(
            {"label": label, "contribution": contribution,
             "replaces": replaces})
        return label

    @staticmethod
    def _label(contribution) -> str:
        for attr in ("__name__", "name", "label"):
            got = getattr(contribution, attr, None)
            if isinstance(got, str) and got:
                return got
        return contribution.__class__.__name__

    def entries(self, kind: str, name: str) -> list:
        """Every contribution to one slot, in registration order."""
        return list(self._slots.get(self._key(kind, name), ()))

    def winner(self, kind: str, name: str):
        """The winning contribution, or None for an empty slot.

        Resolution: the highest ``replaces`` among the registered labels
        wins, exactly as `extensions.OverrideConflict` does for providers —
        so a declared name beats an undeclared one and a conflict between
        two declared names raises rather than resolving by luck.
        """
        entries = self.entries(kind, name)
        if not entries:
            return None
        declared = [e for e in entries if e["replaces"]]
        if len({e["replaces"] for e in declared}) > 1 or (
                len(declared) > 1 and len(declared) != len(entries)):
            raise ValueError(
                "conflicting %s/%s contributions (labels %r): a declared "
                "'replaces' may not disagree with another"
                % (kind, name, sorted({e["label"] for e in entries})))
        if declared:
            return declared[-1]
        return entries[-1]

    def contributions(self, kind: str, name: str) -> list:
        """Every contribution in order, so a host can compose them."""
        return [e["contribution"] for e in self.entries(kind, name)]

    def is_empty(self, kind: str, name: str) -> bool:
        return not self.entries(kind, name)


if __name__ == "__main__":
    print("UI extension slots (Phase 7):")
    for kind in UI_KINDS:
        print("  %-6s %s" % (kind, list(slot_names(kind))))
    reg = UISlotRegistry()
    reg.add("panel", "top", lambda: "builtin")
    print("\npanel/top winner:", reg.winner("panel", "top")["contribution"]())
    print("menu/tray empty:", reg.is_empty("menu", "tray"))
