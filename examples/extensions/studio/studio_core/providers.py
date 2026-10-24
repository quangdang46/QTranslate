"""Studio's translation providers.

Two providers, one context: the glossary answers an exact hit and RAISES
on a miss (so the engine's chain answers instead), and the summariser
shows a provider that uses its own SETTINGS -- change
``Studio.MaxWords`` in Options' settings and its output changes.
"""


def make_glossary(ctx):
    def glossary_translate(text, src, tgt):
        hit = ctx.lookup(text, src, tgt)
        if hit is None:
            ctx.record_miss()
            raise LookupError("studio.glossary: no entry for %r" % text)
        return "%s %s" % (ctx.greeting, hit)
    return glossary_translate


def make_summariser(ctx):
    def summarise(text, src, tgt):
        words = (text or "").split()
        cut = words[:ctx.max_words]
        out = " ".join(cut)
        if len(words) > len(cut):
            out += " …"
        return "%s %s (%d words)" % (ctx.greeting, out, len(words))
    return summarise
