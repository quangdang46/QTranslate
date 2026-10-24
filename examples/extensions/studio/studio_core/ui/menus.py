"""Studio's menu entries.

A menu contribution is a callable returning the label; the host runs it
and shows the answer (``run_ui_contribution``). The history_ctx entry
goes to the history window's right-click menu -- the same slot native's
menu id 6 publishes.
"""


def make_tray_entry(ctx):
    def tray_entry():
        return "%s is alive: %d misses recorded" % (ctx.title, ctx.misses)
    return tray_entry


def make_history_entry(ctx):
    def history_entry():
        return "%s: the selected entry came from history" % ctx.title
    return history_entry
