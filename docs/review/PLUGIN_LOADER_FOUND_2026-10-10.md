# The plugin loader, found — `Service.js` is runtime-loaded, so the E rows cannot be image-verified

> Read-only verification, from a **full-analysis** Ghidra run (`QT_FULL`,
> ~9.5 min). This closes `SERVICE_JS_PROVENANCE_2026-10-10.md` §5's open
> question with a definite answer, and the answer is stronger than "the
> endpoints are absent": **the binary cannot contain them, because the
> services are files loaded at runtime from a `Services/` directory.**
>
> No row state changed by this document.

## 1. The loader, decompiled

`FUN_0045d6a9` — the plugin discovery loop, verbatim shape:

```c
FUN_0045b1cf(L"Services", &local_c);              // <config dir>/Services
DVar3 = GetFileAttributesW(local_c);
if (DVar3 == 0xffffffff) return 0;                // no Services dir -> bailed

FUN_00401f21(&local_14, L"Common.js");            // load the framework first
FUN_0045b9d9(&local_18, &local_14);               //   .../Services/Common.js
FUN_00401f21(&local_14, PTR_0051ca10);            // the directory listing
FUN_0045b81b(&local_c, &local_14, 1, &local_30);  // enumerate subdirs

do {
    puVar4 = FUN_00402478(&local_30, uVar7);      // each directory name
    FUN_0045b9fe(&local_8, &local_c, puVar4);     //   .../Services/<name>/
    FUN_00401f21(&local_1c, L"Service.js");
    FUN_0045b9fe(&local_20, &local_8, &local_1c);//   .../Services/<name>/Service.js
    DVar3 = GetFileAttributesW(local_20);
    if (DVar3 != 0xffffffff) {                    // exists?
        FUN_00402161(&local_10, ...);
        cVar1 = FUN_0043df32(pWVar6, &local_10);  // read + compile it
        if (cVar1 != '\0') FUN_0045d160(&local_8, &local_10);
    }
} while (...);
```

So: `Services/` must exist, `Common.js` is loaded first, then **each
subdirectory's `Service.js`** is read, compiled, and handed to
`FUN_0045d160`.

`FUN_0045d160` — the per-service registration:

```c
local_6c[0] = services::Script::vftable;                    // a real C++ class
FUN_0043b777(local_6c, *puVar2, 0);                         // register the script
pvVar4 = FUN_0045d024(param_1);                             // load Service.ico
FUN_00465a92(local_6c, L"PreferredDomain", &DAT_005494e0);  // set a JS global
FUN_0043b942(local_6c, L"serviceHeader", 0, 0, &local_8);   // CALL INTO JS
```

`FUN_0045d024` is the icon loader — it builds `Services/<name>/Service.ico`
and `LoadImageW`s it at 16×16. And `serviceHeader` is invoked as a **script
callback** through `FUN_0043b942`, i.e. the host pulls a function object out of
the compiled plugin and calls it.

Everything a service *does* — `serviceTranslateRequest`, `serviceHeader`,
`serviceTranslateResponse` — is a JS function in a file the host calls into.
The `L"..."` names in the binary are the **host's** vocabulary, which is exactly
what `SERVICE_JS_PROVENANCE_2026-10-10.md` found and could not explain.

## 2. What this settles, and it settles it categorically

| Question | Answer |
|---|---|
| Is a `Service.js` in the binary? | **No, and none can be.** They are read from disk by path. |
| Where does a dictionary provider's URL live? | In its `Service.js`, i.e. in a file that ships with QTranslate but is **not in `QTranslate.6.10.0.exe`**. |
| Can E4/E6/E9–E20's endpoint shape be image-verified? | **No.** Not "not yet" — the bytes do not exist in this artifact. |
| Is the *plugin protocol* verifiable? | **Partly.** The hook names and the registration path are (above). The individual services are not. |

So the 15 rows' `VERIFIED` RE state rests, as `SERVICE_JS_PROVENANCE` argued,
on evidence that is not the binary. The loader tells us **why** they can't be,
which converts "I could not find it" into "it is impossible to find it here" —
a categorically stronger and more useful statement for the row owner.

## 3. What the image *does* establish about the plugin contract

Even without a single `Service.js`, the host side of the contract is now
readable, and it is not nothing:

| Host obligation | Evidence |
|---|---|
| `Services/` must exist or the loader returns 0 | `FUN_0045d6a9` |
| `Common.js` loads before any service | `L"Common.js"` before the subdir loop |
| one subdirectory per service, containing `Service.js` | `FUN_0045b9fe(L"Service.js")` |
| optional `Service.ico` at 16×16 | `FUN_0045d024`, `LoadImageW(...,1,0x10,0x10,0x30)` |
| service dir name is an opaque key | enumerated, never parsed |
| `PreferredDomain` is exposed to the script | `FUN_00465a92` |
| `serviceHeader` is called by the host | `FUN_0043b942(..., L"serviceHeader", ...)` |

That last two are the load-bearing part: the host **calls into** the plugin,
so a compliant plugin must define those names with those signatures. The port's
`dictionary.py` and the E rows assert a URL shape per service; what *would*
check them against native is a real `Service.js` file, and the only way to get
one is from an installed QTranslate directory (`Services/` next to the exe),
which this repo does not contain.

## 4. Practical consequence for the checklist

The affected rows are E1 (framework), E4, E6, E9, E10, E11, E12, E13, E14, E15,
E16, E17, E18, E19, E20 — and the E rows that cite `Services/Microsoft
Translator/Service.js` for the `/tlookupv3` dictionary block (E22). What is
**not** affected is E2/E3/E5/E7, whose endpoints are compiled in
(`translate.google.`, `bing.com/*`, `translate.yandex.com`, `fanyi.baidu.com`),
and everything in the C/D/F/G/I/J groups that cites a `FUN_` address.

Recommendation to the row owner, **not actioned here**: mark these `INFERRED`
for the endpoint-shape claim while leaving the behaviour column at whatever the
live probe supports, or move them to `UNRECOVERABLE` with the reason
"service plugins are runtime files absent from the recovered artifact" — which
the checklist's own definition permits, since it is a *reason + impact* case.
That is a Gate-affecting decision and the checklist has a single writer.

## 5. Method note, because the first attempt at this was wrong twice

`SERVICE_JS_PROVENANCE` §5 recorded that I decompiled `FUN_004561f0` expecting a
plugin loader and got an `Options.json` handler. The fix was not cleverness:

1. **Run full analysis, not `-noanalysis`.** Under `-noanalysis` five of the
   seven xrefs had no enclosing function at all, so the loader was invisible.
   This is the same class of mistake as the "no JDK on this host" conclusion —
   each check correct, the conclusion wrong, because the instrument couldn't
   see the thing.
2. **Then map xref → containing function** (`tools/ghidra/Enclosing.java`),
   because an immediate-scan gives an *operand* offset, which
   `DecompileNamed.java` reports as `NOT FOUND`.
3. **Then decompile and read it**, rather than inferring the loader's role from
   the string it references.

`FUN_0045d160` referencing `L"Service.js"` is what pointed at the loader; the
xrefs to `ServicesOrder` were the operand reuse that misled the first pass.
The generalizable rule, same family as the "generated code vs executed code"
point: **an xref to a string proves the string is used there, not that the
function does what the string names.**
