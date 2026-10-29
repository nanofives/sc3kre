# STATUS cartrees (child of "SC3 mods page layout + autosave rotation + load crash", 2026-10-28 / 29)

## goal
Owner report 2026-10-28: "some cars are rendering over the trees" (MAIN verify/cartrees/owner_report.png). Owner call
2026-10-29: option A (art), stock 11204 included.

## verdict + deciding RVAs
Stock behaviour, fixed. 11204's near half has its median trees only in layer 0 of a first-pass cell. SIMSPR `0x1000dc17`
draws first-pass records before every sorted record, so far-half cars behind those trees were drawn over them. The far
half's trees are layer 1, a cell-attached DSR (flags 0x02, layer byte 2) that comparator `0x1000c7a6` draws after
overlapping layer-1 cars. Records built by `0x1000be25`; depth = Linux GetDistanceToSpriteMicroUnits. Full notes:
re/analysis/NET_ART.md 8.2, verify/cartrees/RESULTS.md.

## built
- avenue_markings.py `build --trees`: 11204 layer 1 in slots 1 / 2 + the partner half's trees (outside-diamond pixels
  of layer 0 slot (r+2)%4, one cell over). Pixel-identical to stock with no car (offline, 10 frames).
- avenue_lanes 0.4.0: 21700 gets it; new look-only twin 21742 (`avlp 21742 21700`).
- sc3netmod_avp.c: two-way bands' straight rows painted with the straight's twin; off `SC3NETMOD_AVPSTRAIGHT=0`.
  Built in dev/cartrees/inst/sc3netmod.dll (main 783a8ba + this change).

## proven game-side vs static only
Game-side (Seoul, zoom 4): far-half cars behind every median tree on both lanes, near-half cars in front, no dirty-rect
fragments in views 0 / 1 / 2, AVP paints 21742 on band rows only (row facing a 39 stays 11204). Boulevard middle row checked
in a lab boulevard: correct as is, not changed. Static only: zooms 0..3 (offline pixel identity only), English-UK.

## blocked on
Nothing.

## installed
stage\src: avenue_lanes 0.3.0 uninstalled, 0.4.0 installed from dev/cartrees/wt/re/tools/netmod/examples/avenue_lanes;
overlay / ledger / table byte-identical to the tested tree. The copied pack README in stage\src says 6.7% where the
committed README says 6.9% (wording fixed after install, text only).

## files owned (to commit, by path)
- re/harness/src/sc3netmod_avp.c
- re/tools/netmod/avenue_markings.py
- re/tools/netmod/examples/avenue_lanes/manifest.json
- re/tools/netmod/examples/avenue_lanes/README.md
- re/analysis/NET_ART.md
- MAIN verify/cartrees/RESULTS.md, MAIN re/sessions/STATUS_cartrees.md
- never git add: MAIN verify/cartrees/owner_shots/*, worktree examples/avenue_lanes/art/ (gitignored, game-derived)

## game-harness need
None running. My tree dev/cartrees/tree has stage\src's ledger + packs and avenue_lanes 0.4.0; its Seoul was not saved
(autosave files "(auto ...)" only).

## asks of other sessions
None.
