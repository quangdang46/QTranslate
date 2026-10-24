"""Studio's dictionary backend: the glossary as a lookup card."""


def make_dictionary(ctx):
    def studio_dict(word, src, tgt):
        hit = ctx.lookup(word, src, tgt)
        if hit is None:
            raise LookupError("studio.dict: no entry for %r" % word)
        return ("<b>%s</b> <i>%s→%s</i><br>%s"
                % (word, src, tgt, hit))
    return studio_dict
