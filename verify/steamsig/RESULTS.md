# Steam SC3U.exe refused by sc3mods_patch.ps1 (Simtropolis report, 2026-11-06)

Report: Steam app 2741560, build 12966690 ("Default Public Version Mar 2, 2024"), Windows 11. File version 2.0.949.0,
SHA-256 `38781BC3C0041A71E9055A490BEDE08E0E5393380782B9F593FDC89136B7C8AF`. The script refused it: not 2.0.0.3
(49DD55E1...) nor 2.0.949 (42E30CE0...). We had assumed Steam = GOG 2.0.949 (`project-gog-2-0-949-build`).

Evidence in the report's screenshot: the exe's Properties has a **Digital Signatures** tab and shows 1.11 MB where the
stock 1,155,072-byte exe shows 1.10 MB. [UNCERTAIN] that the Steam file is the GOG 2.0.949 exe plus an Authenticode
signature: we do not have the file.

## Change (re/scripts/sc3mods_patch.ps1)

- A build is also recognised by its normalised bytes: signature at the end of the file cut, security directory and PE
  checksum zeroed. Both known builds are unsigned with checksum 0, so their normalised hash is the listed one.
- A signed copy is patched without its signature (it would sit between the last section and ours, and it is void
  once the import table changes). SC3U.exe.orig keeps the signed file. `-Restore` accepts a signed backup.
- The new section starts at a FileAlignment boundary (it used to start at the old end of file).
- An unknown exe prints a report (size, timestamp, checksum, security directory, normalised hash, per-section VA / raw
  / size / hash) to paste into a bug report.

| check (copies of the GOG 2.0.949 exe, Windows PowerShell 5.1) | result |
|---|---|
| stock | recognised 2.0.949, patched, SHA-256 85BE3349... |
| fake signed copy (6,008-byte certificate appended, security dir + checksum set) | recognised "2.0.949 (signed copy)", patched output byte-identical to the stock one (85BE3349...) |
| -Restore on it, then patch again | signed exe restored as it was (1,161,080 bytes), patch works again |
| one byte changed in .text | refused, report printed |

Not checked: the real Steam file. If it is not a signed copy the script now prints the report the player can post.
