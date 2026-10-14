# Native history export dispatches on the file extension (FUN_00428483)

Date: 2026-10-14
Target: `C:\Program Files (x86)\QTranslate\QTranslate.exe` (6.10.0),
recovered artifact `docs/review/artifacts/QTranslate.6.10.0.exe`
(sha256 `f35a3bc8e09e217130ff97efe85ba02bd86573b2e0796b003526604454338227`)
Tooling: REA 6.4.0 -> Ghidra 12.1.4 (`rea search` / `rea xrefs` / `rea decompile`,
snapshot `qt6`, `JAVA_HOME=/c/java/jdk-25.0.4.1+1`,
`GHIDRA_INSTALL_DIR=/c/Users/ADMIN/ghidra/ghidra_12.1.4_PUBLIC`)

## What was asked

`qtranslate/history.py` already exported CSV / HTML / JSON / TXT, and
`docs/RE_COVERAGE_CHECKLIST.md` row R1 records the Checker group as
`dead:host-retired`, so the *formats* were considered settled. The open
question was different: **which** format native chooses for a given
"Save as…" filename. The port's `app.py::on_export_history` always called
`H.html_export(...)` regardless of the filename the user typed, which is a
guess, not evidence.

## Evidence

`historyFileExtension` is a real string in the image at `0x51f06c`
(`rea search --kind strings --pattern historyFileExtension`), with four
direct references:

```
0x427ed5  0x42850e  0x428622  0x429d85
```

Decompiling `0x42850e` (REA's `--procedure` accepts an address inside the
function, it resolves to the entry `FUN_00428483`) gives the whole rule:

```c
int __fastcall FUN_00428483(void *param_1, undefined4 *param_2)
{
  iVar8 = 0;
  if (*(int *)((LPCWSTR)*param_2 + -6) == 0) {   // empty BSTR -> 0
    iVar8 = 0;
  } else {
    pWVar1 = PathFindExtensionW((LPCWSTR)*param_2);
    FUN_00401f21(&local_8, (uint *)pWVar1);       // ext WITH the dot
    if (*(int *)(local_8 + -6) != 0) {           // no extension -> 0
      FUN_0042a159((int *)&local_8);
      FUN_0042a1bb((int *)&local_8);
      FUN_00428708(local_5c);
      local_5c[0] = plugins::HistoryScript::vftable;   // RTTI-typed base
      if (*(int *)((int)local_c + 4) != 0) {
        do {
          puVar2 = (undefined4 *)FUN_00402478(local_c, uVar6); // walk list
          FUN_00428096(local_5c, puVar2);
          piVar3 = (int *)FUN_00402cbd();
          FUN_00402161(&local_8, piVar3);
          uVar4 = FUN_0043b9be(local_5c, (uint *)L"historyFileExtension",
                               0, 0, (int *)&local_8);   // call the hook
          if ((char)uVar4 != '\0') {
            piVar3 = FUN_0042a1bb((int *)&local_8);
            uVar5 = FUN_00401fc2(piVar3, puVar7);      // compare ext
            if (uVar5 == 0) {                          // EQUAL -> wins
              FUN_004033d1((undefined4 *)(local_8 + -8));
              iVar8 = uVar6 + 1;
              break;                                   // first match stops
            }
          }
          FUN_004033d1((undefined4 *)(local_8 + -8));
          uVar6 = uVar6 + 1;
        } while (uVar6 < *(uint *)((int)local_c + 4));
      }
      FUN_0043b748(local_5c);
    }
  }
  return iVar8;   // 1-based index+1 of the matched script, 0 = none
}
```

### Facts read off the decompilation

1. **The format is chosen from the filename, not by a fixed default.**
   `PathFindExtensionW` on the target path is what drives the choice.
2. **The extension includes the dot.** `puVar7` keeps whatever
   `PathFindExtensionW` returned and is later compared as-is, so a plugin's
   `historyFileExtension` value is compared against e.g. `.html`.
3. **The selection rule is first-match-wins.** `break` fires on the first
   equal extension; the return value is `index + 1`, and `0` means "no
   registered script handles it".
4. **No extension means nothing runs.** Both the empty-string test and the
   `local_8 + -6 != 0` guard (zero-length extension) return early with 0.
5. **Native is plugin-driven**, so "csv/html/json/txt" is not a native
   taxonomy: it is whatever the installed `HistoryScript` plugins declare.
   The port's four exporters are its own built-in substitutes for that
   vtable list.
6. **A miss is not silently converted to a default.** Returning 0 leaves
   the caller with no writer; native does not fall back to writing HTML.

## Consequence for the port

* `qtranslate/history.py` gains `exporter_for(path)` and
  `describe_extension(ext)`, reproducing rules 1-4 and 6 (rule 5 is a
  structural difference: dict instead of vtable walk, same ordering rule).
* `app.py::on_export_history` now picks the writer from the filename via
  `exporter_for`, and reports an error when the extension is unknown
  instead of silently writing HTML.
* `defaultextension=".html"` on the file dialog is retained, so the default
  path still yields HTML as before.

## Scope note

This closes the *selection rule* only. It does not claim the shipped
plugins' full list (the CHECKLIST's R1 row records the checker host as
retired, and `PLUGIN_LOADER_FOUND_2026-10-10.md` records that
`Services/*/Service.js` are absent from the recovered artifact, so the
plugin set itself cannot be enumerated from this binary).
