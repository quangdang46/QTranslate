"""Regression: updater manifest parser (R2, FUN_00461ADE)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__))))
from qtranslate import updater as U  # noqa: E402
fail=[]
def ck(n,c,d=""):
    if not c: fail.append(n+(" -- "+d if d else ""))
m = U.parse_manifest('{"urls":[{"href":"http://x/q.exe","provider":"p"}],'
                     '"version":"6.10.1","date":"2022-01-01",'
                     '"changelog":"fixes","notes":[{"version":"6.10.0",'
                     '"date":"2021-01-01","changelog":"old"}]}')
ck("urls parsed", m["urls"]==[{"href":"http://x/q.exe","provider":"p"}], str(m["urls"]))
ck("version/date/changelog", (m["version"],m["date"],m["changelog"])==("6.10.1","2022-01-01","fixes"))
ck("history list parsed", m["history"]==[{"version":"6.10.0","date":"2021-01-01","changelog":"old"}], str(m["history"]))
ck("valid true", m["valid"] is True)
ck("bad json -> valid False, no crash", U.parse_manifest("not json")["valid"] is False)
if fail: raise SystemExit("FAIL:\n  "+"\n  ".join(fail))
print("OK: updater manifest parser")
