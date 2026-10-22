"""The Exceptions page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.
"""

from .base import OptionsBase, button, check, combo, label, panel, rect


class ExceptionsPage(OptionsBase):
    SEL = 6

    def build(self):
        combo(self, 155, 33, 481, "Disabled for these programs:")
        t = panel(self, 153, 60, 483, 221)
        label(t, 161, 72, "Program Name")
        label(t, 400, 72, "Window Class Name")
        rect(t, 393, 62, 1, 18, "#e5e5e5")
        exceptions = [("* All Programs *", c) for c in
                      ["SysListView32", "SysTreeView32", "ListBox", "ScrollBar",
                       "ComboBox", "msctls_hotkey32", "ConsoleWindowClass"]]
        exceptions.append(("mstsc.exe", "* All Windows *"))
        for i, (a, b) in enumerate(exceptions):
            label(t, 161, 92 + 17.6 * i, a)
            label(t, 400, 92 + 17.6 * i, b)
        button(self, 155, 288, 71, "Add")
        button(self, 234, 288, 72, "Modify")
        button(self, 314, 288, 72, "Delete")
        check(self, 154, 321, "Enable smart detection", True)
