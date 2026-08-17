# Registry portability — SimCity 3000 Unlimited

**Verdict: the game is already folder-portable, and `-noreg` closes the last gap.**
Nothing in the registry is load-bearing, and data files are located from the exe's own
directory, so a copied game folder runs anywhere. `sc3launch -noreg` serves the few registry
values from `<exedir>\SC3Portable.ini` so the game touches HKLM/HKCU not at all.

## What the game reads/writes (verified by decompilation AND live intercept)

All registry access is in `SC3U.exe` (zero in any DLL). Reads funnel through ONE read-only
helper `FUN_0040698b` (`0x0040698b`, `RegOpenKeyExA` with `KEY_QUERY_VALUE`, then
`RegQueryValueExA`); it returns "not found" on any miss and never aborts — the caller uses a
default.

`HKLM\Software\Electronic Arts\Maxis\SimCity 3000 Unlimited\`:

| value | reader | gates | if absent |
|---|---|---|---|
| `Country`  | `FUN_0040586a` | localization | keeps default |
| `Language` | `FUN_0040586a` | localization | falls back to `Maxis.ini [Default Locale] Language`, then a hardcoded default |
| `User`     | `FUN_00417c23` | City Exchange login | INI `[Internet] CityExchangeUser` first; empty otherwise |
| `Password` | `FUN_00417c23` | City Exchange login | INI `[Internet] CityExchangePassword`; empty |
| `ergc`     | `FUN_00417c23` | City Exchange serial | INI `[Internet] CityExchangeSerialNumber`; empty |
| `SKU`      | `FUN_0043a31e`, `FUN_0043e28b` | SKU-specific resources (e.g. main-menu bitmap) | default resources |

The only registry WRITE in the binary is `HKCU\...\Internet Settings\EnableAutodial`
(`FUN_0049b78b`, WinInet autodial), non-essential.

**Live confirmation:** with `-noreg` and an empty INI, a menu boot intercepts exactly
`Language, Country, User, Password, ergc, SKU` and `EnableAutodial` — the predicted set, nothing
more — and the game boots and renders (harness_check PASS) with every value served "absent".

## Data files are exe-relative, not registry (decisive)

`FUN_0048273a` (`0x0048273a`): `GetModuleFileNameA(NULL, ...)` -> split -> the exe directory is
stored as the data root (`this+0x24`, trailing `\` enforced) and every data subpath is built
from it (`+0x34/+0x48/+0x5c`). No registry, no `GetCurrentDirectory`, no absolute path. The game
also reads `Maxis.ini` from the exe directory (`FUN_00482aee`). Copy the folder -> data resolves.

## `-noreg`: serve the registry from the folder

`sc3launch -noreg` (probe: `noreg_install`) IAT-hooks SC3U.exe's `advapi32` imports
(`RegOpenKeyExA` / `RegQueryValueExA` / `RegCloseKey` / `RegSetValueExA`). Opens of the EA/Maxis
key and Internet Settings return fake handles; queries are served from `<exedir>\SC3Portable.ini`;
a value absent from the INI returns `ERROR_FILE_NOT_FOUND` (identical to a missing registry
value); sets are written to the INI, never the registry. A commented template is written on
first run.

```
[Registry]        ; HKLM\Software\Electronic Arts\Maxis\SimCity 3000 Unlimited\
Language=9
SKU=Unlimited
; Country=1
; User=  Password=  ergc=

[InternetSettings] ; HKCU\...\Internet Settings\
; EnableAutodial=0
```

No byte patches (IAT hooks only), so it is not in `harness_patches.py`. Combine with the windowed
switches for a fully self-contained run:

```
sc3launch -nocom -windowed -origin -fix16 -fitclient -nointro -noreg
```

## Standalone (no injected probe)

Not built. Because all reads go through the single non-fatal helper `FUN_0040698b`, a static
patch could redirect it to an INI reader — but it is unnecessary for portability: with data
already exe-relative and no registry value load-bearing, the folder is portable as-is; `-noreg`
only removes the (harmless) registry reads.
