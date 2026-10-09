# The source-language rule, settled from the live image — and the port's `_NATIVE_AUTO` set is wrong

> Read-only verification. This answers the one question
> `COMPATIBILITY_MATRIX.md` §B left open ("decide one rule… should *all*
> capture paths honor the selected source language, or only the popup
> hotkey?"), using functions that resolve in the **full-analysis** project
> `QT_FULL`.
>
> No checklist row or matrix row changed by this document. It records the
> measured rule so the row edit is a decision made on facts.

## 1. The chain

`FUN_00404a12` — the dispatcher (note: Ghidra labels it lowercase,
`FUN_00404a12`, so `DecompileNamed.java` must be given that spelling):

```c
in_EAX = (int *)param_1[1];               // the service object
if (in_EAX[-3] == 0) return;              // no service -> bail
if (param_2 == 0) in_EAX = FUN_0045cede();   // no service named -> default
else              in_EAX = FUN_0045cc50(param_2);
if ((*(byte *)(in_EAX + 4) & 1) == 0) return;   // caps gate: TRANSLATE bit
FUN_0045f609(local_c4);                    // build the request
iVar1 = FUN_0045f6c1(local_c4, in_EAX, '\x01');
```

`FUN_0045f6c1` — the request constructor, and this is where the mechanism is:

```c
if ((param_1 == 0) || (*param_1 != 0)) return 2;
*(int **)((int)this + 0x4c) = param_1;
uVar3 = FUN_0043b777(this, ..., (int *)((int)this + 0x88));   // register the service
uVar3 = FUN_0043b8ce(this, L"usesAutoDetectCode", 0, 0, &piStack_1c);   // ASK THE SERVICE
if ((char)uVar3 != '\0' && (short)piStack_1c == 0xb) {
    *(bool *)((int)this + 0x50) = (short)piStack_14 != 0;      // store the answer
}
```

**`usesAutoDetectCode` is a JS hook the host calls on the service.** The
boolean lands at `this + 0x50`. This is the same host->JS call shape as
`serviceHeader` in the plugin loader and `appendMenuItem` in the card builder
(`FUN_0043b8ce` / `FUN_00423d7f`).

`FUN_004606ba` — the translate stage, which consumes `+0x50`:

```c
if ((0x49 < *(uint *)(param_1 + 0x10) - 2) || FUN_0045ff70(this, *(uint *)(param_1 + 0x10))) {
    puVar1 = (uint *)(param_1 + 8);                 // +8 = source language
    if (0x49 < *puVar1 - 2) {                       // if it is not a concrete code
        if ((*(char *)((int)this + 0x50) == '\0') || (0x49 < *(int *)(param_1 + 0x10) - 2U)) {
            iVar3 = FUN_0045fde8(this, (int *)(param_1 + 4), (int *)puVar1);   // DETECT
            ...
```

`0x49 < x - 2U` is the same `param_2 - 2U < 0x4a` clamp from
`J7_PHONETICS_NATIVE_2026-10-10.md` §7 — a "code is absent/invalid" test, not a
range check on real codes.

## 2. The rule, stated once

**Native asks the service whether it accepts auto-detect, and only calls the
detect step itself when the service does *not*.**

| Service's `usesAutoDetectCode` | Field `+8` when the source is unset | Native's action |
|---|---|---|
| true | unset | **pass it through unset** — the service resolves it |
| false | unset | **call `FUN_0045fde8` (detect) itself**, then substitute the concrete code |

The condition in `FUN_004606ba` also has a second disjunct — it runs detect
when the *target* is also not a concrete code, regardless of the service flag.
And there is a `src == dst` short-circuit in the dispatcher:

```c
if ((param_1[2] - 2U < 0x4a) && (param_1[2] == param_1[4])) {
    FUN_00401ec9(param_1 + 3, param_1 + 1);   // src == dst: echo, skip the service
    goto LAB_00404b33;
}
```

**So the matrix's question has a definite answer, and it is neither option it
offers.** Not "all capture paths honor the selected source" and not "only the
popup hotkey": the rule is *capability-dependent and per-service*, resolved
once by asking the service, then applied uniformly by the engine.

## 3. Why the port's `_NATIVE_AUTO` set is wrong

`qtranslate/app.py:561-567`:

```python
_NATIVE_AUTO = {"google", "microsoft", "bing", "deepl"}
fn = TRANSLATORS.get(service, _t_google)
if src == "auto" and service not in _NATIVE_AUTO:
    src = detect_language(text)
out = fn(text[:5000], src, target)
```

with the comment "their Service.js sends `sl=auto`". Three problems, in
increasing severity:

1. **It is a hardcoded set where native has a per-service query.** The membership
   is not read from anything — it is four names in a literal. A fifth service
   answering `usesAutoDetectCode` would be silently mis-routed.
2. **The justification cites the runtime-loaded files.**
   `PLUGIN_LOADER_FOUND_2026-10-10.md` proves `Services/*/Service.js` are loaded
   from disk and are not in the artifact, so the comment asserts a fact about
   files nobody in this repo has read. It may even be *true* — but nothing here
   can check it, which is the same evidence-class error as the 15 E rows.

> **Correction to this section's first draft, which is why it is kept rather
> than quietly fixed:** I wrote here that `"bing"` is not a service id in this
> port and its `_NATIVE_AUTO` entry is inert. **False.** `app.py`'s
> `TRANSLATORS` has both `"bing": _t_bing` and `"microsoft": _t_bing` (the two
> ids alias the same function, as native's id 5 does), so `"bing"` is a live
> key and the set member does real work. I asserted the negative from having
> only seen `microsoft` in the config, which is the "a grep result is evidence
> about naming, never about behavior" failure in its purest form — and it would
> have sent a reader to delete a working line.

**Consequence for the matrix row:** the row's "inconsistent
(`app.py:3356`=src, `:3449/3593/3514`=auto)" is real, but the *rule* to decide is
now known. The port should query capability, not membership — and absent a JS
engine to call `usesAutoDetectCode`, the honest port-side encoding is a
per-provider **declared** capability in `services/*.py`, with the default
matching native's detect-yourself fallback.

## 4. The `src == dst` echo is missing entirely

The port has no equivalent of the dispatcher's short-circuit: with
`src == target` it still calls the provider. `FUN_00404a12` copies the source
into the result slot `param_1 + 3` and skips the service call. That is a
behaviour difference on the most ordinary input there is.

## 5. Not verified by me

- **Which services actually answer `usesAutoDetectCode` as true.** The hook is
  called by name; the answer lives in the runtime-loaded `Service.js`, which the
  loader proves is not in the artifact. So the *mechanism* is measured, and the
  *per-service truth table* is not. The four names in `_NATIVE_AUTO` may well be
  the right four — I am reporting that the port cannot currently know that, not
  that the set is wrong.
- **`DAT_0054941f`'s identity**, used in the dispatcher as
  `CONCAT31(param_2._1_3_, DAT_0054941f)`. Its role is clear from position (a
  byte flag carried alongside the service handle), but I did not trace its
  readers to name it.
- **`FUN_0045fde8`** is the detect step by its call position and the
  `FUN_0045FF70` language-validity checks around it; I did not decompile it, so
  "detect" is inferred from structure rather than read from the body. That is a
  weaker claim than the rest of this document and is labelled as such.
- **The full-analysis caveat.** `FUN_00404a12` did not resolve by name under
  `-noanalysis` — it needed the `QT_FULL` project. This is the same
  instrument-can't-see-the-thing failure as the loader hunt
  (`PLUGIN_LOADER_FOUND` §5) and it will recur for every address in the
  disassembly-dense regions.
