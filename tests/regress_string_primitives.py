"""Regression: the remaining string primitives (Common.js).

Recovered `Common.js` (NSIS chunk at `0x13af4`)::

    function stringFind(a,b){if(b)if("string"===typeof b){
        var c=a.indexOf(b); if(-1<c)return{index:c,length:b.length}}
      else if(c=a.match(b))return{index:c.index,length:c[0].length}}
    function trimString(a){return a?a.replace(/(^\\s+)|(\\s+$)/g,""):""}
    function stringSplit(a,b){if(!IE_SPLIT_ISSUE)return a.split(b);
      /* IE workaround -- manual capture-group splice */}

``IE_SPLIT_ISSUE`` is ``3!=="a'b".split(/(')/g).length``, which is FALSE
on every engine that matters now, so native uses the plain
``String.split`` -- capture groups included. Python's ``re.split`` does
the same natively.

These were the last unported/unpinned Common.js primitives; all verified
correct here. No network, no Tk.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import (  # noqa: E402
    string_find, string_find_sub, string_split, trim_string,
)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- stringFind: string needle -------------------------------------------
ck("string needle found",
   string_find("hello", "ll") == {"index": 2, "length": 2})
ck("string needle at 0", string_find("hello", "he") == {"index": 0,
                                                       "length": 2})
ck("string needle absent -> None (JS undefined)",
   string_find("hello", "zz") is None)
ck("empty needle -> None (native: if(b) fails)", string_find("hello", "")
   is None)

# --- stringFind: regex needle -------------------------------------------
ck("regex needle found",
   string_find("hello", re.compile(r"l+")) == {"index": 2, "length": 2})
ck("regex length is the MATCH length, not the group length",
   string_find("hello world", re.compile(r"o (w)"))
   == {"index": 4, "length": 3},
   string_find("hello world", re.compile(r"o (w)")))
ck("regex absent -> None", string_find("hello", re.compile(r"z+"))
   is None)

# --- stringFindSub: the four include flags ------------------------------
P = "AAA_start_MIDDLE_end_ZZZ"
ck("incS=1 incE=1", string_find_sub(P, "_start_", True, "_end_", True)
   == P[3:21])
ck("incS=1 incE=0", string_find_sub(P, "_start_", True, "_end_", False)
   == P[3:16])
ck("incS=0 incE=1", string_find_sub(P, "_start_", False, "_end_", True)
   == P[10:21])
ck("incS=0 incE=0 -> the content",
   string_find_sub(P, "_start_", False, "_end_", False) == "MIDDLE")
ck("missing marker -> '' (native's falsy chain)",
   string_find_sub(P, "<no>", True, "_end_", True) == "")
ck("empty text -> ''", string_find_sub("", "a", True, "b", True) == "")
ck("empty marker -> '' (native's !b guard)",
   string_find_sub(P, "", True, "_end_", True) == "")
ck("regex markers work",
   string_find_sub(P, re.compile(r"_start_"), False, re.compile(r"_end_"),
                   False) == "MIDDLE")

# --- trimString ----------------------------------------------------------
ck("trims both ends", trim_string("  x  ") == "x")
ck("trims tabs and newlines", trim_string("\t\nx\r\n ") == "x")
ck("leaves interior space alone", trim_string(" a b ") == "a b")
ck("all-whitespace -> ''", trim_string("   ") == "")
ck("empty -> ''", trim_string("") == "")
ck("None -> '' (native's a?…:\"\")", trim_string(None) is not None
   and trim_string(None) == "")
ck("no trim needed", trim_string("x") == "x")

# --- stringSplit: modern JS semantics, capture groups kept --------------
ck("plain split", string_split("a-b-c", "-") == ["a", "b", "c"])
ck("regex split without groups", string_split("a1b22c", re.compile(r"\d+"))
   == ["a", "b", "c"])
ck("capture groups are KEPT (IE_SPLIT_ISSUE is false)",
   string_split("a'b", re.compile(r"(')")) == ["a", "'", "b"],
   string_split("a'b", re.compile(r"(')")))
ck("multiple capture groups are kept in order",
   string_split("x1y2z", re.compile(r"(\d)")) == ["x", "1", "y", "2", "z"])
ck("a split with no match returns the whole string",
   string_split("abc", re.compile(r"\d")) == ["abc"])

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_string_primitives: all checks ok (%d assertions)" % n[0])
