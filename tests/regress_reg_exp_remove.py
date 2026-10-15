"""Regression: ``regExpRemove`` primitive (Common.js) -- native semantics.

Recovered `Common.js` (NSIS chunk at `0x13af4`)::

    function regExpRemove(a,b,c){if(!b)return a;b=format(c,b.join("|"));
                                 return a.replace(new RegExp(b,"g"),"")}

Three facts this suite pins, because the three helpers built on top of it
(removeTags/removeAttributes/removeElements) all carried invented
divergence before 4e6af04:

  1. the guard is ``if(!b)`` -- the **tag list**, not the string. An empty
     input string still runs the regex; an empty tag list returns the
     input untouched;
  2. the compiled pattern carries only ``"g"`` -- **no ``i`` flag** and no
     ``re.S``/DOTALL in JS terms, so matching is CASE-SENSITIVE. (The port
     passes ``re.S``; JS has no equivalent of ``.`` matching newlines
     unless the pattern itself says ``(.|\\n)``, which the native
     ``removeElements`` pattern does explicitly -- so ``re.S`` reproduces
     exactly that, and no more);
  3. ``a.replace(re,"")`` removes **every** occurrence, not just the first.

No network, no Tk.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import reg_exp_remove  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


PAT = r"</?({0})[^>]*>"          # native removeTags pattern
PE = r"<\s*({0})[^>]*>((.|\n)*?)<\s*/\s*({0})>"   # native removeElements

# --- 1. guard is on the tag list -----------------------------------------
ck("empty tag list returns the input untouched (native: if(!b) return a)",
   reg_exp_remove("<b>x</b>", [], PAT) == "<b>x</b>")
ck("empty string with tags still runs the regex (returns '')",
   reg_exp_remove("", ["b"], PAT) == "")
ck("both empty returns ''", reg_exp_remove("", [], PAT) == "")

# --- 2. case-SENSITIVE (no i flag) ---------------------------------------
ck("lowercase tag is removed",
   reg_exp_remove("<b>x</b>", ["b"], PAT) == "x")
ck("UPPERCASE tag is NOT removed (native has no i flag)",
   reg_exp_remove("<B>x</B>", ["b"], PAT) == "<B>x</B>",
   reg_exp_remove("<B>x</B>", ["b"], PAT))
ck("mixed case: only the lowercase closing tag matches (case-sensitive)",
   reg_exp_remove("<B>x</b>", ["b"], PAT) == "<B>x",
   reg_exp_remove("<B>x</b>", ["b"], PAT))

# --- 3. all occurrences removed, not just the first ----------------------
ck("every occurrence is removed",
   reg_exp_remove("<b>a</b><b>b</b>", ["b"], PAT) == "ab",
   reg_exp_remove("<b>a</b><b>b</b>", ["b"], PAT))

# --- the multi-tag join is an alternation, as format(c, b.join("|")) ----
ck("two tags form one alternation",
   reg_exp_remove("<b>a</b><i>b</i>", ["b", "i"], PAT) == "ab")
ck("a longer tag name partially matches the shorter pattern (native does "
   "this too: </?b[^>]*> matches the <b inside <bt)",
   reg_exp_remove("<bt>x</bt>y", ["b"], PAT) == "xy",
   reg_exp_remove("<bt>x</bt>y", ["b"], PAT))
ck("an explicit longer tag in the list matches its whole name",
   reg_exp_remove("<b>x</b>", ["bt", "b"], PAT) == "x")

# --- the native removeElements pattern crosses newlines explicitly ------
ck("removeElements pattern matches across a newline (its own (.|\\n))",
   reg_exp_remove("<b>\nx\n</b>keep", ["b"], PE) == "keep",
   reg_exp_remove("<b>\nx\n</b>keep", ["b"], PE))
ck("and it does NOT cross a newline where nothing asks it to",
   reg_exp_remove("<b>x</b>\n<b>y</b>", ["b"], PE) == "\n",
   reg_exp_remove("<b>x</b>\n<b>y</b>", ["b"], PE))

# --- the port must not broaden the semantics of its own accord ----------
src = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "common.py"),
    encoding="utf-8").read()
ck("reg_exp_remove does not pass re.I",
   "re.I" not in src.split("def reg_exp_remove")[1].split("def ")[0])
ck("reg_exp_remove keeps re.S (the JS pattern's own (.|\\n) equivalent)",
   "re.S" in src.split("def reg_exp_remove")[1].split("def ")[0])
ck("the native guard is quoted in the docstring", "if(!b)" in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_reg_exp_remove: all checks ok (%d assertions)" % n[0])
