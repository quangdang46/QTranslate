"""The Exceptions page of the Options dialog.

The geometry was MEASURED off the native capture 2139: the combo at the
top, the list of programs with its two columns and the rule between
them, the three buttons under it and the checkbox at the foot.
"""

from .base import OptionsBase, button, check, combo, label, panel, rect

# The rows native's list holds, in its order.
ROWS = [("* All Programs *", "SysListView32"),
        ("* All Programs *", "SysTreeView32"),
        ("* All Programs *", "ListBox"),
        ("* All Programs *", "ScrollBar"),
        ("* All Programs *", "ComboBox"),
        ("* All Programs *", "msctls_hotkey32"),
        ("* All Programs *", "ConsoleWindowClass"),
        ("mstsc.exe", "* All Windows *")]


class ExceptionsPage(OptionsBase):
    SEL = 6

    def build(self):
        # The combo: the frame runs from the client's x 154 to 634 and is
        # 19px tall.
        combo(self, 155, 33, 481, "Disabled for these programs:", h=19)
        # The list: the client's x 152..634, y 32..254.
        t = panel(self, 153, 58, 483, 223)
        label(t, 160, 72, "Program Name")
        label(t, 400, 72, "Window Class Name")
        # The rule between the two columns, under the header.
        rect(t, 393, 60, 1, 24, "#e5e5e5")
        for i, (a, b) in enumerate(ROWS):
            label(t, 160, 92 + 17 * i, a)
            label(t, 400, 92 + 17 * i, b)
        button(self, 155, 287, 73, "Add", shadow=True)
        button(self, 234, 287, 73, "Modify", shadow=True)
        button(self, 314, 287, 73, "Delete", shadow=True)
        # The checkbox's box is the client's x 152..165, y 288..301.
        check(self, 153, 321, "Enable smart detection", True)
