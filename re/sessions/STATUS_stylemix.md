# STATUS stylemix (child, round 2026-11-18) - DONE

## goal
Simtropolis (NicoMT): a switch that turns off the building style mix (European +400000 / Asian +1500000 growables)
like the other features. Row "Building style mix" in the Features column of Turn mods on/off, default on, env
switch SC3NETMOD_STYLEMIX=0, 7 languages. Saves with mix buildings must keep loading.

## verdict + deciding RVA
Done, best outcome: off = no new copies grow, saved copies load as themselves with their own art.
With SC3NETMOD_STYLEMIX=0 sc3netmod serves a same-length copy of the overlay BUILDFAM.IXF (%TEMP%\sc3netmod_nomix_<pid>.IXF)
in which every family Key line with an id above 65535 has weight 0. SIMGEOM 0x10001250 skips a weight-0 line and
lowers BuildingCount (0x1000136f). Exemplars and art containers unchanged. Details: verify/stylemix/RESULTS.md (top section).

## built
sc3netmod.dll + sc3resize.dll in dev/stylemix/inst, clean. sc3lang check clean (347 keys x 7).

## proven game-side vs static only
Game-side (Sacramento, 600 s arms, churn anarchy 5000):
- ON last autosave: euro 2,808, asian 2,291. OFF last autosave: 0 / 0 with 8,792 lots rebuilt (all stock).
- ON save loaded with switch off: save written at load keeps 2,808 / 2,291; same frame as a switch-on load except cars;
  queried house = id 400116 (European copy) drawn with its art. No crash in 6 starts.
- Copies fade only as lots rebuild (test churn rebuilt run-grown buildings ~90% regardless of style).
- Row write both ways (MODTOGGLE log + ini), loader applies it (sc3mods.log), stale temp copy sweep.
Static only: weight-0 semantics of 0x10001250 (and confirmed by the 0 / 0 count).

## blocked on
nothing

## files owned
dev/stylemix/wt: re/harness/src/sc3netmod.c, re/harness/src/sc3resize.c, re/harness/lang/de.txt en.txt es.txt fr.txt
it.txt nl.txt sv.txt, re/tools/netmod/stylemix_switch_run.py (new), re/tools/netmod/examples/style_mix/README.md.
MAIN: verify/stylemix/RESULTS.md (new top section), re/sessions/STATUS_stylemix.md.
Not to commit: verify/stylemix/owner_shots/sw1..sw5 *.jpg (game art).

## game-harness need
own tree dev/stylemix/tree only. No game running. Tree ini reset to default (row on).

## asks of other sessions
none. Release: rebuild sc3netmod + sc3resize and ship the 7 sc3lang tables; no netpack change.
