"""MVP demo — translate/detect through the public SDK (Slice 5).

This is the "no rebuild" demo from ``IMPLEMENTATION_PLAN.md`` Phase 6:
a consumer that uses only ``qtranslate.sdk``, not ``app.py``.

Run:
    python -I examples/demo_translate.py "hello world" [service] [target]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import sdk


def main(argv):
    text = argv[1] if len(argv) > 1 else "hello world"
    service = argv[2] if len(argv) > 2 else "google"
    target = argv[3] if len(argv) > 3 else "vi"

    lang = sdk.detect(text)
    print("detected:", lang)
    res = sdk.translate(service, text, target, src=lang or "auto")
    print("provider:", res.provider_used)
    print("text:", res.text)
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
