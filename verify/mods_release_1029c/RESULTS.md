# RESULTS - sc3mods release 2026-10-29c + LAN republish

Replaces `sc3mods-2026-10-29b`. Owner call 2026-10-29: "Release now" after the startcrash fix. Source as of `dc9ec03`.

| what | commits | record |
|---|---|---|
| NULLBLIT (sc3resize): a blit into the screen device with no raster is skipped and the screen surface rebuilt with GZ's own startup calls (startup crash GZGraphicD+0x14904) | dc9ec03 | verify/startcrash/RESULTS.md |

Also recorded: sc3undo recording only while paused is by design (owner 2026-10-29).

## Stage and checks

- `stage/bins_1029c` = `stage/bins_1029b` + sc3resize built from main. Label `2026-10-29c`, 3,612 files, 706.0 MB.
- Launch check (stage/release patched, windowed, no input): Berlin, `8 mod(s) loaded`, `NULLBLIT: on - 2 of 2 device vtables
  wrapped`, only the benign `0xC0000096 @ SC3U+0x84122`. Then `-Restore`, logs deleted, 3,612 manifest files re-hashed: 0 changed,
  0 missing, 0 extra.

LAN: 1 of 3,612 files sent (0.5 MB). Served label `2026-10-29c`, served sc3resize SHA-256 matches the stage.

| file | bytes | SHA-256 |
|---|---|---|
| Apps/sc3resize.dll | 472064 | 6DAD4EA2FB9CA9BF2CE1FF4A53C3F50280111DE7F30B101D221B1F980A857DA3 |
| README.txt | | 2026-10-29c section |
| every other file | | as `verify/mods_release_1029b/RESULTS.md` |
| `sc3mods_2026-10-29c.zip` | 50,222,421 | 53AD169417379AE7A8C904C639499B2874D3A700BC6DCF738CEA39CE7534C313 |

GitHub: `sc3mods-2026-10-29c`, target `baa17d0`, https://github.com/nanofives/sc3kre/releases/tag/sc3mods-2026-10-29c, asset
downloaded back, SHA-256 matches. The 10-29b notes now start with a "superseded" line.
