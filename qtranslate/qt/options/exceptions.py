"""The Exceptions page of the Options dialog.

The geometry was MEASURED off the native capture 2139: the combo at the
top, the list of programs with its two columns and the rule between
them, the three buttons under it and the checkbox at the foot.

WIRED: the list is the ``Exceptions`` section of Options.json (the
``Disabled`` program/class pairs), the checkbox writes
``Exceptions.DisabledMode`` (the same flag ``qtranslate.exclusions``
reads), and Add / Modify / Delete edit the list for real. ``build``
runs on the shell instance, so the row state lives on the shell
(``_ex_rows`` / ``_ex_sel`` / ``_ex_labels``) and the handlers are
module functions.
"""

from PySide6.QtWidgets import QInputDialog

from qtranslate_style import WINDOW

from .base import OptionsBase, button, check, combo, label, panel, rect

# The rows a fresh install starts with: native's own exclusions for
# list/combo/scrollbar window classes plus the terminal multiplexer.
DEFAULT_ROWS = [("* All Programs *", "SysListView32"),
                ("* All Programs *", "SysTreeView32"),
                ("* All Programs *", "ListBox"),
                ("* All Programs *", "ScrollBar"),
                ("* All Programs *", "ComboBox"),
                ("* All Programs *", "msctls_hotkey32"),
                ("* All Programs *", "ConsoleWindowClass"),
                ("mstsc.exe", "* All Windows *")]


def _rows():
    """The configured exception pairs (program, window class).

    ``Exceptions.Disabled`` absent -> the built-in defaults are shown
    (they are not persisted until the user edits the list). An
    explicitly saved list -- even an empty one -- is shown as-is, so
    deleting every row and saving does not resurrect the defaults.
    """
    from .base import cfg_section
    ex = cfg_section("Exceptions")
    if "Disabled" not in ex:
        return [tuple(r) for r in DEFAULT_ROWS]
    rows = ex.get("Disabled") or []
    out = []
    for r in rows:
        if isinstance(r, (list, tuple)) and len(r) >= 2:
            out.append((str(r[0]), str(r[1])))
        elif isinstance(r, dict):
            out.append((str(r.get("program", "")),
                        str(r.get("window_class", ""))))
    return out


def _save_rows(rows):
    from qtranslate import config as _C
    try:
        cfg = _C.load() or {}
        cfg.setdefault("Exceptions", {})["Disabled"] = [
            [a, b] for a, b in rows]
        _C.save(cfg)
    except Exception:
        pass


def _fill_rows(shell):
    t = shell._ex_panel
    for w in shell._ex_labels:
        try:
            w.setParent(None)
            w.deleteLater()
        except Exception:
            pass
    shell._ex_labels = []
    for i, (a, b) in enumerate(shell._ex_rows):
        la = label(t, 160, 92 + 17 * i, a)
        lb = label(t, 400, 92 + 17 * i, b)
        for w in (la, lb):
            w.setProperty("row", i)
            w.mousePressEvent = (lambda _e, idx=i, s=shell:
                                 _select(s, idx))
        shell._ex_labels += [la, lb]


def _select(shell, idx):
    shell._ex_sel = idx
    for w in shell._ex_labels:
        try:
            w.setStyleSheet(
                "QLabel{background:%s;}"
                % ("#cfe3ff" if w.property("row") == idx
                   else "transparent"))
        except Exception:
            pass


def _add_row(shell):
    prog, ok = QInputDialog.getText(
        shell, "Add exception", "Program name:")
    if not ok:
        return
    cls, ok = QInputDialog.getText(
        shell, "Add exception", "Window class name:")
    if not ok:
        return
    # Empty sides are the matcher's match-anything (""), never the
    # '* All ... *' display sentinels -- a blank program field gives a
    # class-only row like the defaults' SysListView32 ones.
    a, b = prog.strip(), cls.strip()
    if not a and not b:
        return
    shell._ex_rows.append((a, b))
    _save_rows(shell._ex_rows)
    _fill_rows(shell)


def _modify_row(shell):
    sel = getattr(shell, "_ex_sel", -1)
    if not (0 <= sel < len(shell._ex_rows)):
        return
    prog, ok = QInputDialog.getText(
        shell, "Modify exception", "Program name:",
        text=shell._ex_rows[sel][0])
    if not ok:
        return
    cls, ok = QInputDialog.getText(
        shell, "Modify exception", "Window class name:",
        text=shell._ex_rows[sel][1])
    if not ok:
        return
    # Same rule as _add_row: blank sides persist as "" (match-anything);
    # only a fully blank row is refused, since ("", "") excludes all.
    a, b = prog.strip(), cls.strip()
    if not a and not b:
        return
    shell._ex_rows[sel] = (a, b)
    _save_rows(shell._ex_rows)
    _fill_rows(shell)


def _delete_row(shell):
    sel = getattr(shell, "_ex_sel", -1)
    if not (0 <= sel < len(shell._ex_rows)):
        return
    del shell._ex_rows[sel]
    shell._ex_sel = -1
    _save_rows(shell._ex_rows)
    _fill_rows(shell)


class ExceptionsPage(OptionsBase):
    SEL = 6

    def build(self):
        from .base import cfg_section, cfg_set
        ex = cfg_section("Exceptions")
        # The combo: the frame runs from the client's x 154 to 634 and is
        # 19px tall. Its text starts 8px inside the frame, not the 6
        # the style sheet asks for: MEASURED off the capture.
        c = combo(self, 155, 33, 481, "Disabled for these programs:", h=19)
        c.setStyleSheet("QComboBox{padding-left:7px;}")
        # The list: the client's x 152..634, y 32..254.
        self._ex_panel = t = panel(self, 153, 58, 483, 223)
        # The header sits a pixel higher than the rows under it: the
        # theme's header control draws its text there (MEASURED).
        label(t, 160, 71, "Program Name")
        label(t, 400, 71, "Window Class Name")
        # The rule between the two columns, under the header.
        rect(t, 393, 60, 1, 24, "#e5e5e5")
        self._ex_rows = _rows()
        self._ex_labels = []
        self._ex_sel = -1
        _fill_rows(self)
        b_add = button(self, 155, 287, 73, "Add", shadow=True)
        b_mod = button(self, 234, 287, 73, "Modify", shadow=True)
        b_del = button(self, 314, 287, 73, "Delete", shadow=True)
        b_add.clicked.connect(lambda: _add_row(self))
        b_mod.clicked.connect(lambda: _modify_row(self))
        b_del.clicked.connect(lambda: _delete_row(self))
        # The checkbox: the box is the client's x 152..165, y 288..301.
        # The theme draws the label beside the box and centres it on the
        # BOX, not on the widget, so the label is a label of its own.
        check(self, 153, 321, "",
              bool(ex.get("DisabledMode", True))
              ).toggled.connect(
            lambda v: cfg_set("Exceptions", "DisabledMode", bool(v)))
        label(self, 172, 320, "Enable smart detection")
        # The sunken frame's 1px white shadow, under the list.
        rect(self, 152, 281, 485, 1, WINDOW)
