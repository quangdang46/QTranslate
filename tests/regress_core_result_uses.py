"""Regression: every do_translate caller holds a core.Result, not a str.

`do_translate` returned `str` until 5f18daa, when it started returning
`core.Result`. Commit 5f18daa updated the 7 call sites it knew about
(on_go single, on_go multi, on_hotkey, _translate_text, _poll, _retype_selection,
win32app._translate) and `regress_source_language.py` — but one more call site
caught the exception instead of the Result:

    except Exception as e:
        r = f"[error] {e}"          # <- bare str

then used `r.text` two lines later. `str` has no `.text`, so the
multi-service path raised AttributeError instead of rendering the error.

The suite pins the invariant that this cannot come back: the exception
branch must build a core.Result, because every consumer of do_translate
indexes `.text`/`.provider_used`/`.ok`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import qtranslate.app as A  # noqa: E402
from qtranslate.core import Result  # noqa: E402

fails = []
n = 0


def check(name, cond, detail=""):
    global n
    n += 1
    if not cond:
        fails.append(name + (" -- " + detail if detail else ""))


# 1. A normal call returns a Result (regression against the old str return).
r = A.do_translate("google", "hello world", "vi")
check("normal call returns Result", isinstance(r, Result), type(r).__name__)
check("normal call exposes .text", isinstance(r.text, str), repr(r.text))

# 2. An EMPTY input is a Result with empty text (not ""), so callers that
#    index .text keep working.
re = A.do_translate("google", "", "vi")
check("empty input returns Result", isinstance(re, Result), type(re).__name__)
check("empty input .text == ''", re.text == "", repr(re.text))
check("empty input not ok", re.ok is False)

# 3. The bug this suite exists for: the multi-service exception branch. A
#    Result built there must support both .text and .text[:200], which is what
#    the two lines after it do. Note provider_used carries the REQUESTED
#    service (matching app.py's call), so .ok is True — "a service was tried",
#    not "an answer arrived". The failure is in `.note` and the "[error]"
#    prefix, exactly as the other do_translate failure paths do it.
err_r = Result("baidu", "[error] boom", "baidu", note="exception before translate")
check("exception-branch shape: .text", err_r.text == "[error] boom",
      repr(err_r.text))
check("exception-branch shape: .text[:200]",
      err_r.text[:200] == "[error] boom", repr(err_r.text[:200]))
check("exception-branch keeps the requested service",
      err_r.provider_used == "baidu" and err_r.note
      == "exception before translate", repr(err_r))

# 4. And the actual code path: no site in the module assigns a bare str where
#    a Result is later consumed. Scan the source for the anti-pattern.
src = open("qtranslate/app.py", encoding="utf-8").read()
check("no bare-str Result-shaped assignment remains",
      'r = f"[error] {e}"' not in src,
      "the str assignment that caused the AttributeError is gone")

if fails:
    print("FAIL %d/%d" % (len(fails), n))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_core_result_uses: all checks ok (%d assertions)" % n)
