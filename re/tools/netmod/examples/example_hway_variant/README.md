# example_hway_variant

Test fixture for netbridge: highway straight 73 cloned as variant 20073, art derived at build time with the `yellow`
recolour (no art stored here). `replace_base` retargets every stage-rule RESULT of the HWAY network that places 73
(107 rules), and inheritance (on by default) gives 20073 Convert rows that read as 73, so the neighbouring highway
pieces tile exactly as around 73 (offline arm S1 in `verify/netbridge/PRE.md`). Crossings, diagonals and removal
follow the base through sc3netmod.dll (CROSS and INHERIT). Results: `verify/netbridge/RESULTS.md`.
