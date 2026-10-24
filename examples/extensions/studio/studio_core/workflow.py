"""Studio's post-translation pipeline.

A workflow step runs on a FINISHED translation; a step that raises is
skipped, so this one guards its own edges. The annotation uses the
context's settings, so the operator's Options changes show up in every
new translation.
"""


def make_pipeline(ctx):
    def pipeline(text, src, tgt):
        if not isinstance(text, str) or not text:
            return text
        words = len(text.split())
        tag = "%s · %s→%s · %d words" % (ctx.title, src, tgt, words)
        return "%s\n— %s" % (text, tag)
    return pipeline
