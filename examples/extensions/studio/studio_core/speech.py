"""Studio's speech / OCR / spell backends.

The TTS backend RECORDS what it was asked to speak (its own state, not
the app's), so the panel can show "last spoken"; the OCR backend
demonstrates the key-gate error path; the spell backend is native's
suggest shape.
"""


def make_tts(ctx):
    def studio_tts(text, lang, slow=False):
        ctx.last_spoken = (text or "")[:80]
        ctx.spoken_slow = bool(slow)
    return studio_tts


def make_ocr(ctx):
    def studio_ocr(image_bytes, lang, api_key):
        if not api_key:
            raise RuntimeError("studio.ocr: an API key is required")
        return ""
    return studio_ocr


def make_spell(ctx):
    def studio_spell(text, lang):
        return ["%s (%s?)" % (text, ctx.title)]
    return studio_spell
