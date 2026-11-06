# sc3mods-2026-11-04b (patch release, 2026-11-06)

https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-11-04b, target 209346bee53539ee5bbe731dbcc19f8dfa954307.
Asset `sc3mods_2026-11-04b.zip` 142 entries, SHA-256 `0b19b68210c797ce7921e7f21f201f5fdc8417d3abdb39a061ccc027aa648546`
(verified by download).

Built from the published sc3mods_2026-11-04 zip: every entry's content compared by SHA-256, only `README.txt` and
`sc3mods_patch.ps1` differ. The script is main's `re/scripts/sc3mods_patch.ps1` (signed-copy support,
verify/steamsig/RESULTS.md). README: release line, install step 1 says SC3U.exe is inside Apps, step 2 names signed
copies and the report, a "NEW IN 2026-11-04b" block. No mod DLL changed, so no game smoke test (the script was tested
on stock, fake-signed and altered copies of the GOG 2.0.949 exe).

Not in it: the community-mods work on main (terrain panel, weather, Bosque button, Civic Deals / Apache installers,
CHEATFIX). Not done: the LAN server (`re/scripts/lan_release`), which serves an already patched tree.
