"""Studio's panel and popup-body renderers.

Both render FROM THE CONTEXT (settings + counters), which is the point
of the seam: the app hands over a slot, the extension renders what it
likes, and a settings change flows through without touching the app.
"""


def make_top_panel(ctx):
    def top_panel():
        spoken = getattr(ctx, "last_spoken", "")
        lines = ["%s — %d glossary entries, %d misses"
                 % (ctx.title, len(ctx.glossary.get("en", {}).get("vi", {})),
                    ctx.misses)]
        if spoken:
            lines.append("last spoken: %s" % spoken)
        return "\n".join(lines)
    return top_panel


def make_popup_body(ctx):
    def popup_body(source, result, pair):
        if not isinstance(result, str) or not result:
            return None
        return "%s\n\n[%s · %s]" % (result, ctx.title, pair)
    return popup_body
