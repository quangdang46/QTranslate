# Ghidra MCP was unavailable — and the reason recorded first was wrong (2026-10-10)

> Operational note. The first version of this file was titled "host has no
> JDK" and stated the blocker as a system-level limitation. **That was false:
> there is a JDK on this host, a Homebrew `openjdk@21`, and `~/ghidra/ghidra.sh`
> already set `JAVA_HOME` to it.** The correction is §"Why the first restart
> attempt failed". The file is kept and corrected in place rather than deleted,
> because the wrong version read as thorough diligence rather than as an error,
> which is the kind that survives.
>
> **Status 2026-10-10, later:** the server is restartable. `ghidraRun` with
> `JAVA_HOME` set launches the GhidraMCP plugin, which serves the same
> endpoints the MCP tools call. If you are reading this because
> `mcp__ghidra__*` is timing out again, the fix is to launch with
> `JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`
> — not to conclude the tool is gone.

## What broke

The `ghidra` MCP tool (`mcp__ghidra__decompile_function` etc.) returns:

```
HTTPConnectionPool(host='127.0.0.1', port=8080): Read timed out.
```

The MCP **bridge** is alive — `bridge_mcp_ghidra.py` is still running:

```
/Users/tranquangdang21/ghidra/GhidraMCP/.venv/bin/python \
  /Users/tranquangdang21/ghidra/GhidraMCP/bridge_mcp_ghidra.py \
  --ghidra-server http://127.0.0.1:8080/
```

but the Ghidra server on `127.0.0.1:8080` that it forwards to was gone.
Orphaned `decompile` helper processes from earlier runs are still up
(`Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile`), which is why the
port is reachable-ish and then times out rather than refusing.

## Restarting it

`analyzeHeadless` is not the path — GhidraMCP is a **Java plugin**
(`GhidraMCPPlugin.java`, `DEFAULT_PORT = 8080`, an embedded
`com.sun.net.httpserver.HttpServer`), so its endpoints exist only when a tool
with a loaded program is running. Launch the GUI with the project:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  ~/ghidra/ghidra_12.1.4_PUBLIC/ghidraRun ~/Projects/QT_REAL.rep
```

The installed extension is at
`~/ghidra/ghidra_12.1.4_PUBLIC/Ghidra/Extensions/GhidraMCP/`, and the plugin's
routes (`/decompile`, `/list_functions`, `/methods`, `/xrefs_to`, …) are the
endpoints `bridge_mcp_ghidra.py` calls. Note the plugin starts its server when
the tool initializes with a program open, so the port may take a while after
launch before it answers.

## Why the first restart attempt failed — and the correction

The first attempt ran `analyzeHeadless` without a `JAVA_HOME`:

```
$ ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless ...
Unable to locate a Java Runtime.
ERROR: Unable to prompt user for JDK path, no TTY detected.
```

And the first version of this note concluded from that, plus four negative
checks:

- `/Library/Java/JavaVirtualMachines/` is empty
- `/usr/libexec/java_home -V` → "Unable to locate a Java Runtime"
- `/usr/bin/java` exists but is the macOS stub — same error, exit 0
- no JDK bundled under `~/.hermes/tools/` either

**That conclusion was WRONG, and it was wrong in a way worth recording.**
There is a JDK, and the repo already documented it:

```sh
# ~/ghidra/ghidra.sh   <- written earlier, on this machine, for this exact purpose
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
```

```
$ /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java -version
openjdk version "21.0.12.1" 2026-07-18
OpenJDK 64-Bit Server VM (build 21.0.12.1+0, mixed mode, sharing mode)
```

The four negative checks were each true and together misleading, because
`java_home` does not list **keg-only** Homebrew formulae — which is exactly
what `openjdk@21` is. So "not in the standard location" was read as "not
installed." The lesson, in the same shape as the grep failure recorded
elsewhere in this doc set: **a lookup tool's silence is evidence about the
lookup tool, not about the machine.** The five-minute fix was to read the
script that had already launched Ghidra successfully on this host.

No JDK was ever missing, so there was never a system change to make and
nothing to ask the user about — a false blocker that this note itself
presented as an honest limitation. Corrected in place rather than deleted.

## What still works without Ghidra

The recovered PE on disk (`docs/review/artifacts/QTranslate.6.10.0.exe`,
1,462,272 bytes) is directly parseable, and this was enough to close J6:

| Result | How |
|---|---|
| libFLAC 1.2.1 statically linked | `reference libFLAC 1.2.1 20070917` at file `0x12d220`; 69 `FLAC__*` enum names; `"fLaC"` at `0x123310` |
| All 8 J6 addresses resolve | PE32 parse → ImageBase `0x400000`, `.text` VA `0x401000..0x50cc00`, RVA→offset map |
| Section layout | `.text/.rdata/.data/.rsrc/.reloc` with raw offsets |

So a dead MCP is a **coverage** problem, not a total stop: string/constant
extraction, GUID discovery and address resolution still work from raw bytes.
Decompiling a specific function's control flow does not.

## Practical effect on this session's goals

- The remaining 4 `not-started` rows are all rows where decompilation would
  not have changed the answer (C10 is a proven negative, F13 is a
  documented divergence, G9 needs a screenshot, J6 needs a dependency).
- Anything requiring a *new* decompile should be queued for a host with a
  JDK, or asked of the peer session which still has Ghidra working.

---

## Addendum 2026-10-10 (later): **Ghidra works here after all** — and the
diagnostic trap that nearly cost it a second time

This doc's headline claim was wrong (see the correction above). It is
superseded by this addendum, kept because the *shape* of the error recurs.

The headless pipeline runs fine on this host:

```sh
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
  ~/Projects QT_REAL -process "QTranslate.6.10.0.exe" -noanalysis \
  -scriptPath tools/ghidra -postScript DecompileNamed.java FUN_00404901
```

### The trap: a compile error presents as "script not found"

`tools/ghidra/DisasmNamed.java` was added during the C3 work and failed **three
times before it ran**. Every failure looked like the same symptom — a *name*
problem, not a *code* problem:

```
skipping /Users/.../tools/ghidra/DisasmNamed.java
ERROR REPORT SCRIPT ERROR: DisasmNamed.java : The class could not be found.
  It must be the public class of the .java file: DisasmNamed not found by ...
Caused by: java.lang.ClassNotFoundException: DisasmNamed not found by ...
```

`ClassNotFoundException` for a class that plainly exists, with the right name
in the right file, reads as "the filename doesn't match the class" — which is
itself a documented Ghidra rule and therefore the obvious repair. It is the
**wrong** repair. The real errors were two compile failures printed ~15 lines
earlier in the same log:

1. `error: incompatible types: InstructionIterator cannot be converted to
   AddressIterator` — `Listing.getInstructions()` returns an
   `InstructionIterator`, not an `AddressIterator`.
2. `error: cannot find symbol / class InstructionIterator` — the type is not
   implicitly imported for scripts.

So the rule is: **grep `error:` in the headless log before reading its last
line.** `skipping <path>` plus a `ClassNotFoundException` means *your script did
not compile*; only a bare `Script not found` means the script was not found.
Two independent sources hit this in one day (qtranslate-ed reports
`getScriptArgs` vs `getArguments` and an ambiguous overload, both surfacing the
same way), which is why it belongs here next to the pipeline notes rather than
in a commit message.

The related trap, from the same script: a Ghidra decompiler rendering such as
`(*pIVar2->get_accName)(...)` **presumes** the member's vtable offset. When the
question is "which offset", decompile the C *and* disassemble — the raw
instruction carries it (`CALL dword ptr [ECX + 0x28]` ⇒ slot 10 on a 32-bit
vtable). This is what turned a plausible port assumption into a measured match
for C3.

### Consequence for the note's own list of "what a dead MCP costs"

The line above says "anything requiring a *new* decompile should be queued for a
host with a JDK". No host change is needed; `JAVA_HOME` is. Two documents were
written from a false premise and both have since been corrected in place:
`J6_FLAC_DECOMPILE_2026-10-10.md` (FLAC chain re-decompiled) and
`C3_C8_C10_MOUSE_2026-10-10.md` (vtable offsets, import thunks).
