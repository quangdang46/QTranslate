# Yandex.Disk public-key href resolver (FUN_0046185d)

Date: 2026-10-14
Target: `docs/review/artifacts/QTranslate.6.10.0.exe`
Tooling: REA 6.4.0 -> Ghidra 12.1.4 (`rea search` / `xa` / `decompile`,
snapshot `qt6`)

## Evidence

`https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=%s&fields=href`
is a real string at `0x52aca8`, referenced once (`0x461881`) inside
`FUN_0046185d`. Decompiled body:

```c
FUN_004023f1(&local_c, (uint *)L"https://cloud-api.yandex.net/v1/disk/"
  "public/resources/download?public_key=%s&fields=href");
FUN_00401f21(&local_10, (uint *)&PTR_0051ca10);
bVar1 = FUN_0045ba87(&local_c, &local_10, &local_8);   // the request
if (bVar1) {
  piVar3 = FUN_0043f71a(&local_20, &local_8);          // parse JSON
  if (piVar3 != (int *)0x0) {
    cVar2 = (**(code **)(*piVar3 + 0x20))(&local_18);  // root is object?
    uVar6 = 0;
    if (cVar2 != '\0') {
      FUN_00401f21(&local_10, (uint *)L"href");
      uVar4 = FUN_00440984(local_18, &local_10, param_2);  // look up "href"
      if ((char)uVar4 != '\0') { uVar5 = 1; uVar6 = 1; }
    }
    (**(code **)*piVar3)(1);
  }
}
```

### Facts

1. The URL template is verbatim, with `public_key=%s` interpolated and a
   constant `fields=href`.
2. Success requires the JSON root to be an object (the `+0x20` check) and
   the `href` member to be present.
3. Anything else returns `uVar6 = 0` -- never a half-built URL.

## Consequence for the port

* `qtranslate/services/yandex.py` gains `DISK_PUBLIC_URL` and
  `resolve_public_href(public_key, opener=None)` reproducing 1-3 (GET
  substituted for native's POST-with-empty-params wrapper
  FUN_0045ba87, documented).
* `tests/regress_yandex_disk.py` (8 assertions) pins the template, the
  href extraction, and every failure branch headlessly.
