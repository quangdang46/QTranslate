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

## 3. Port gap (CLOSED in working tree 2026-10-15)

`qtranslate/app.py:3768` called every dict provider as:

```python
frag = fn(word_q, "en", self.target)
```

- The `"en"` was hardcoded — the port did not model
  `LanguageDictionary` as a separate option. **Now fixed:**
  `go_all` resolves `_dsl` from `General.LanguageDictionary`
  (default 17 = `en`), guards auto/`-1`/out-of-range back to `"en"`,
  and passes `_dsl` through. Pinned by `regress_dict_lang` (9 checks).
- `self.target` is always a concrete code (the port's target combo is
  never `auto`), so the `param_1[4] == 1` branch stays a no-op in the
  port — latent, by the same shape as `DictionaryExactSearch`.

## 4. What closed it (and what remains)

To make the port match native, the dict task needed to:

1. Read `General.LanguageDictionary` (default 17 = `en`) as the dict
   target, separate from `LanguageTo`.
2. When the dict target combo is `auto` (index 1), substitute
   `LanguageDictionary` — mirroring `param_1[4] = DAT_005493f4`.
3. Pass that resolved target to each dict provider instead of the
   hardcoded `"en"`.

Steps 1 and 3 are **done** (see §5: source resolved from
`General.LanguageDictionary`); step 2 stays latent because the port's
dict target is never `auto`. This is a **port** change, not an RE
change. The RE side (the builder) is now closed.

## 5. Follow-up audit 2026-10-15 (all three axes checked)

- **Source:** fixed in working tree — `go_all` resolves `_dsl` from
  `General.LanguageDictionary` (pinned by `regress_dict_lang`, 9/9).
- **Target:** no bug — dict window reuses the main-window target
  (`self.target` from `LanguageTo`, default 57/vi with bounds check),
  matching the native entry-from-UI-state flow. No per-dict target
  combo exists natively either.
- **Offline XDXF:** no bug — `lookup(word, path, exact)` takes no
  target language because XDXF articles are file-scoped; matches
  `FUN_004151c3` (word + source lang only).
