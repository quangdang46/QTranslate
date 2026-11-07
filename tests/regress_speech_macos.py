"""Regression: macOS speech input orchestration (qt-qyh).

``qtranslate/speech_macos.recognize`` is the PyObjC/SFSpeechRecognizer
path that replaces the dead Google full-duplex API on macOS. The real
recognition needs TCC grants and a microphone, so these tests inject the
TCC status (``auth=``) and the recognition session (``session=``) and
prove the contract that matters for the hotkey call site:

  * authorized + transcript        -> returns the text, reason cleared
  * denied / restricted / prompt   -> returns "" + stable reason string
  * recognizer unavailable         -> "" + reason (when frameworks exist)
  * session error / silence        -> "" + reason

No PyObjC, microphone or network is touched: every framework touchpoint
is either injected or lazily skipped. Runs on any platform.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))

from qtranslate import speech_macos as S  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


class FakeSession:
    """Stand-in for _SpeechSession: returns canned text/error."""

    def __init__(self, text="", error=None, seen_timeout=None):
        self._text = text
        self.error = error
        self.seen_timeout = seen_timeout

    def run(self, timeout_s):
        self.seen_timeout = timeout_s
        if self.error:
            raise RuntimeError(self.error)
        return self._text


class ErrorAttrSession:
    """Session that reports failure via .error instead of raising."""

    def __init__(self, error):
        self.error = error

    def run(self, timeout_s):
        return ""


class FakeRecognizer:
    def __init__(self, available=True):
        self._available = available

    def isAvailable(self):
        return self._available


# -- text path ------------------------------------------------------------

sess = FakeSession(text="xin chào thế giới")
text = S.recognize(timeout_s=7, auth=3, session=sess)
check("authorized text returned verbatim", text == "xin chào thế giới",
      repr(text))
check("reason cleared on success", S.last_reason() == "", S.last_reason())
check("timeout passed through to session", sess.seen_timeout == 7,
      repr(sess.seen_timeout))

# -- permission-denied paths ------------------------------------------------

text = S.recognize(timeout_s=1, auth=1)
check("denied returns empty", text == "", repr(text))
check("denied reason stable", S.last_reason() == "speech-permission-denied",
      S.last_reason())

text = S.recognize(timeout_s=1, auth=2)
check("restricted returns empty", text == "", repr(text))
check("restricted reason stable",
      S.last_reason() == "speech-permission-restricted", S.last_reason())

# notDetermined (0) goes through request_authorization; stub it so the
# test never pops a real TCC prompt, then prove the denied degrade.
_orig_req = S.request_authorization
try:
    S.request_authorization = lambda timeout_s=60.0: 1
    text = S.recognize(timeout_s=1, auth=0)
    check("prompt-then-denied returns empty", text == "", repr(text))
    check("prompt-then-denied reason",
          S.last_reason() == "speech-permission-denied", S.last_reason())
finally:
    S.request_authorization = _orig_req

# -- unsupported / unavailable ---------------------------------------------

if sys.platform != "darwin":
    text = S.recognize(timeout_s=1)
    check("non-darwin returns empty", text == "", repr(text))
    check("non-darwin reason", S.last_reason() == "unsupported-platform",
          S.last_reason())

# recognizer unavailable: only meaningful where the frameworks import.
if S._speech_frameworks() is not None:
    text = S.recognize(timeout_s=1, auth=3,
                       recognizer=FakeRecognizer(available=False))
    check("unavailable recognizer returns empty", text == "", repr(text))
    check("unavailable recognizer reason",
          S.last_reason() == "recognizer-unavailable", S.last_reason())

# -- failure reporting ------------------------------------------------------

text = S.recognize(timeout_s=1, auth=3,
                   session=FakeSession(error="boom"))
check("session exception returns empty", text == "", repr(text))
check("session exception reason prefix",
      S.last_reason().startswith("recognition-error:"), S.last_reason())

text = S.recognize(timeout_s=1, auth=3,
                   session=ErrorAttrSession("kAFAudioFileErrorDomain"))
check("session .error returns empty", text == "", repr(text))
check("session .error reason prefix",
      S.last_reason().startswith("recognition-error:"), S.last_reason())

text = S.recognize(timeout_s=1, auth=3, session=FakeSession(text=""))
check("silence returns empty", text == "", repr(text))
check("silence reason", S.last_reason() == "no-speech", S.last_reason())

# -- surface sanity ----------------------------------------------------------

check("available() is bool", isinstance(S.available(), bool))
check("authorization_status() int-or-None",
      S.authorization_status() is None
      or isinstance(S.authorization_status(), int))

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: speech_macos orchestration (text, permission-denied, degrade)")
