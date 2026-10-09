# Ghidra MCP unavailable — host has no JDK (2026-10-10)

> Operational note. Recorded because it changes what *can* be verified in
> this session, and because the fix is not something I should do silently.

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

but the Ghidra headless server on `127.0.0.1:8080` that it forwards to is gone.
Five orphaned `decompile` helper processes from earlier runs are still up
(`Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile`), which is why the
port is reachable-ish and then times out rather than refusing.

## Why it cannot be restarted here

Restarting needs `analyzeHeadless`, which needs a JVM:

```
$ ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless ...
Unable to locate a Java Runtime.
ERROR: Unable to prompt user for JDK path, no TTY detected.
```

There is **no JDK on this host**:

- `/Library/Java/JavaVirtualMachines/` is empty
- `/usr/libexec/java_home -V` → "Unable to locate a Java Runtime"
- `/usr/bin/java` exists but is the macOS stub — it prints the same error
  and exits 0
- no JDK bundled under `~/.hermes/tools/` either

The Ghidra 12.1.4 install and the `QT_REAL.rep` project (3812 functions) are
both intact at `~/ghidra/ghidra_12.1.4_PUBLIC` and
`/Users/tranquangdang21/Projects/QT_REAL.rep` — only the runtime is missing.
Installing a JDK is a **system change to the user's machine** and was not
something I did unprompted; flagging it instead.

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
