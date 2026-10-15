# Dict-task language builder — `FUN_00414f54` traced, port gap recorded

> Read-only trace from the Ghidra database (QTranslate 6.10.0). No row state
> changed by this document. The dict-language builder was the last open
> non-GUI RE item; this closes the *builder* half and records the port gap.

## 1. What `FUN_00414f54` does (decompile evidence)

`FUN_00414f54(this, param_1)` is the dictionary task dispatcher. It reads the
entry struct and, crucially, **overwrites the target language** before
dispatching:

```c
FUN_004048b7(this, 0x8163, 0, param_1);          // get source text
uVar3 = FUN_004048b7(this, 0x8163, 1, param_1);   // get source lang
if (uVar3 && param_1 && *(param_1[1] - 0xc)) {   // source non-empty
    if (param_1[2] == 1) {                        // source == AUTO (1)
        FUN_0045f609(local_c8);                   // fresh script ctx
        FUN_0045f6c1(local_c8, DAT_005495e0, 1);  // seed options
        FUN_0045fde8(local_c8, param_1+1, param_1+2); // detect
        FUN_00404b7b(local_c8);
    }
    if (param_1[4] == 1) {                        // target == AUTO (1)
        param_1[4] = DAT_005493f4;                // -> LanguageDictionary
    }
    uVar3 = FUN_004048b7(this, 0x8163, 2, param_1); // get target lang
    if (uVar3) {
        // walk ActiveDictionaryServices, dispatch FUN_004150c2 (online)
        // or FUN_004151c3 (offline XDXF) per service
    }
}
```

So the builder is:

| Condition | Native action | Evidence |
|-----------|---------------|----------|
| `param_1[2] == 1` (source auto) | detect source first | `FUN_0045fde8` call |
| `param_1[4] == 1` (target auto) | replace with `DAT_005493f4` | direct assignment |

`DAT_005493f4` is the runtime value of `General.LanguageDictionary`
(Options.json default 17 = `en`). It is **not** the same as
`LanguageTo` — it is a separate "Dictionary:" combo on the Options page.

## 2. The two dispatch branches

- **`FUN_004150c2`** (online dict): reads `param_1[1]` (source text) and
  `param_1[2]` (source lang), seeds options, calls `FUN_0045ff04` (translate
  fallback when the dict returns nothing). It does **not** re-read
  `param_1[4]` — the target was already rewritten by the builder.
- **`FUN_004151c3`** (offline XDXF): reads `param_1 + 0x14` (the word) and
  `param_2 + 1` (source lang). The XDXF path uses the **source** lang, not
  the target.

## 3. Port gap (recorded, not fixed)

`qtranslate/app.py:3768` calls every dict provider as:

```python
frag = fn(word_q, "en", self.target)
```

- The `"en"` is hardcoded — the port does not model `LanguageDictionary`
  as a separate option. The Options page has the combo
  (`app.py:2853` `"Dictionary:" -> "LanguageDictionary"`) but the dict
  task never reads it.
- `self.target` is always a concrete code (the port's target combo is
  never `auto`), so the `param_1[4] == 1` branch is a no-op in the port
  today. The gap is **latent**: it activates only if the port's target
  combo is set to `auto`.

This is the same shape as the `DictionaryExactSearch` gap: the native
builder is understood, the port does not model the option, and the
divergence is currently unreachable because the port's target is always
concrete.

## 4. What would close it

To make the port match native, the dict task would need to:

1. Read `General.LanguageDictionary` (default 17 = `en`) as the dict
   target, separate from `LanguageTo`.
2. When the dict target combo is `auto` (index 1), substitute
   `LanguageDictionary` — mirroring `param_1[4] = DAT_005493f4`.
3. Pass that resolved target to each dict provider instead of the
   hardcoded `"en"`.

This is a **port** change, not an RE change. The RE side (the builder)
is now closed.
