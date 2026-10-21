"""Phase 7 (6/6): split `App`'s main window out into `windows.MainWindow`.

A split is a MOVE, not a rewrite (see `qtranslate/windows.py`'s header). The
main window is special in that it is not a window hanging off the app -- it
*is* the app's own window -- so the extracted class holds the main window's
construction and its operations and is handed the live `App` to read and
write, exactly as the other Phase 7 classes are.

The rewrite rules, applied with AST positions (so strings and comments are
never touched):

  * `self.<attr>`  -> `self.app.<attr>`   (the App owns the state)
  * `self.<moved>` -> `self.<moved>`       (an internal call stays internal:
                                            no round trip through the
                                            delegator)
  * `self.X = ...` -> `self.app.X = ...`   (an assignment target is ALWAYS
                                            the App's, even for a moved
                                            name -- there is no such
                                            attribute on the window class)
  * a bare `self`  -> `self.app`

`app.py` keeps a thin delegator per moved method, so every existing suite
still reaches the same behaviour through the same entry point.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

APP = Path("qtranslate/app.py")
WIN = Path("qtranslate/windows.py")

# The main window's own methods. Everything else stays in `App`: the history
# store, the lifecycle hooks, and the delegators to the other windows.
MOVED = [
    "_build_main",
    "toggle_backtr", "dict_with_service", "toggle_fullscreen", "reset_pair",
    "slot_service", "slot_pair", "cycle_service", "toggle_pane",
    "open_service_page_n", "_ui_icon", "_load_svc_icon", "_init_opt_flags",
    "show_result_menu", "ordered_services", "default_source_text",
    "hist_back", "hist_forward", "copy_to_source", "open_service_page",
    "show_nav_menu",
    "on_new", "on_paste", "on_mic", "_mark_service", "switch_service",
    "apply_theme", "current", "tag_links", "render", "_apply_backtr_split",
    "_click_link_dict", "_click_link",
    "on_swap", "toggle_multi_service", "on_go", "on_clear", "on_listen",
    "on_copy", "on_layout", "on_type", "accept_suggestion", "show_hotkeys",
    "show_about", "show_override_conflicts",
    "on_ocr", "on_ocr_file", "_ocr_bytes", "_ocr_region", "open_keyboard",
]


def collect_self_rewrites(func: ast.AST, moved: set):
    """Byte positions of the `self` tokens that must become `self.app`."""
    rewrites = []
    assigned = set()

    def is_self_attr(node):
        return (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self")

    # Assignment / deletion targets are always the App's.
    for node in ast.walk(func):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        elif isinstance(node, ast.Delete):
            targets = node.targets
        for tgt in targets:
            if is_self_attr(tgt):
                assigned.add((tgt.value.lineno, tgt.value.col_offset))

    for node in ast.walk(func):
        if isinstance(node, ast.Attribute) and is_self_attr(node):
            if node.attr in moved:
                continue          # an internal call -- leave it
            rewrites.append((node.value.lineno, node.value.col_offset))
        elif isinstance(node, ast.Name) and node.id == "self" \
                and not isinstance(node.ctx, ast.Store):
            # a bare `self` used as a value
            rewrites.append((node.lineno, node.col_offset))
    return rewrites, assigned


def main() -> int:
    src = APP.read_text(encoding="utf-8")
    data = src.encode("utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "App")
    methods = {f.name: f for f in cls.body
               if isinstance(f, ast.FunctionDef)}
    missing = [m for m in MOVED if m not in methods]
    if missing:
        print(f"methods not found in App: {missing}", file=sys.stderr)
        return 2

    # Byte offset of the start of each line.
    line_start = []
    off = 0
    for line in lines:
        line_start.append(off)
        off += len(line.encode("utf-8"))

    moved_set = set(MOVED)

    # ---- build the new MainWindow body ------------------------------------
    new_methods = []
    delegators = []
    for name in MOVED:
        func = methods[name]
        seg = "".join(lines[func.lineno - 1: func.end_lineno])
        rewrites, assigned = collect_self_rewrites(func, moved_set)
        # Rewrite from the end so the offsets stay valid.
        positions = sorted(set(rewrites) | assigned, reverse=True)
        seg_bytes = seg.encode("utf-8")
        seg_lines = seg.splitlines(keepends=True)
        base = line_start[func.lineno - 1]
        for (lineno, col) in positions:
            # The offset inside the extracted segment: the method's own
            # first line is the segment's origin.
            abs_off = (line_start[lineno - 1]
                       - line_start[func.lineno - 1]) + col
            seg_bytes = seg_bytes[:abs_off] + b"self.app" + seg_bytes[abs_off + 4:]
        seg = seg_bytes.decode("utf-8")
        new_methods.append(seg.rstrip("\n"))

        # ---- the delegator -------------------------------------------------
        header_end = None
        for i in range(func.lineno - 1, func.body[0].lineno - 1):
            if lines[i].rstrip().endswith(":"):
                header_end = i
                break
        if header_end is None:
            print(f"cannot find the end of the signature of {name}",
                  file=sys.stderr)
            return 2
        header = "".join(lines[func.lineno - 1: header_end + 1])
        header = header.rstrip("\n")
        delegator = (
            header + "\n"
            + '        """The main window (Phase 7 `MainWindow`).\n'
            + "\n"
            + "        Body lives in ``qtranslate/windows.py``; this is the\n"
            + "        delegator. The signature and the reachable behavior are\n"
            + "        unchanged.\n"
            + '        """\n'
            + f"        return self._main.{name}({', '.join(_arg_names(func))})\n"
        )
        delegators.append(delegator)

    # ---- rewrite app.py ----------------------------------------------------
    # Remove the moved methods (from the last one backwards so the line
    # numbers stay valid) and insert the delegators where they were.
    out_lines = list(lines)
    inserts = []
    for name in MOVED:
        func = methods[name]
        # the decorator/blank lines before the def
        start = func.lineno - 1
        while start > 0 and out_lines[start - 1].strip() == "":
            start -= 1
        inserts.append((start, func.end_lineno, name))
    inserts.sort(reverse=True)

    delegator_by_name = {}
    for d in delegators:
        name = next(n for n in MOVED
                    if f"self._main.{n}(" in d)
        delegator_by_name[name] = d

    for start, end, name in inserts:
        block = delegator_by_name[name]
        out_lines[start:end] = [block]

    # App.__init__ must build the window through the new class.
    text = "".join(out_lines)
    old_init = """        self._init_opt_flags()
        self._build_main()"""
    new_init = """        # Phase 7 (6/6): the main window's body lives in
        # ``qtranslate.windows.MainWindow``. It is handed the live App, so
        # every widget and every piece of state stays where it was.
        from qtranslate.windows import MainWindow
        self._main = MainWindow(self)
        self._init_opt_flags()
        self._main._build_main()"""
    if text.count(old_init) != 1:
        print("cannot find the App.__init__ build call", file=sys.stderr)
        return 2
    text = text.replace(old_init, new_init, 1)
    APP.write_text(text, encoding="utf-8")

    # ---- append the MainWindow class to windows.py ------------------------
    win = WIN.read_text(encoding="utf-8")
    cls_src = (
        "\n\nclass MainWindow:\n"
        '    """The main window (DLG129) -- the app\'s own window.\n'
        "\n"
        "    Phase 7 asks for *\"Split `App` into `MainWindow`, ...\"*. This\n"
        "    is that class. It is not a window hanging off the app -- it IS the\n"
        "    app's own window -- so it is handed the live ``App`` and reads and\n"
        "    writes its state there, exactly as the other Phase 7 classes are\n"
        "    handed ``root`` and ``app``.\n"
        "\n"
        "    **A split is a MOVE, not a rewrite.** The bodies below are the\n"
        "    ``app.py`` bodies, with the mechanical substitutions spelled out in\n"
        "    ``app.py``'s Phase 7 note:\n"
        "\n"
        "      ``self``        -> ``self.app``   (the App owns the state)\n"
        "      ``self.X = ...``-> ``self.app.X = ...``\n"
        "      an internal call to another moved method stays ``self.X``\n"
        "\n"
        "    No window is created on import (pinned by\n"
        "    ``tests/regress_windows.py``).\n"
        '    """\n'
        "\n"
        "    def __init__(self, app):\n"
        "        self.app = app\n"
        + "\n".join(new_methods)
        + "\n"
    )
    WIN.write_text(win.rstrip("\n") + "\n" + cls_src, encoding="utf-8")
    print(f"moved {len(MOVED)} methods; app.py now {len(APP.read_text().splitlines())} "
          f"lines, windows.py {len(WIN.read_text().splitlines())} lines")
    return 0


def _arg_names(func):
    """The parameter names of a function, without `self`."""
    a = func.args
    names = [arg.arg for arg in a.posonlyargs + a.args]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [arg.arg for arg in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return names[1:]      # drop `self`


if __name__ == "__main__":
    raise SystemExit(main())
