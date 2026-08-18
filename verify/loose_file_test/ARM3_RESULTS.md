# ARM3 RESULTS — does the game read a SYS.PAK we wrote? (run 2026-08-17, game-running session)

## Bottom line: the SYS.PAK WRITER IS VALIDATED. The credits non-effect is NOT a writer defect.

The pre-registered interpretation ("credits scroll normally -> our archive is malformed in a way
a byte round-trip and re-parse both miss") is **falsified by a byte diff**, below.

## What was run

Install state at run time (verified): `Apps\Sys\SYS.PAK` = our writer's output
(sha `c224e8bf`, 272,507 B), `SYS.PAK.original` = shipped (sha `172c02d9`, 272,507 B), 0 loose
`.ini`. Launched windowed (`sc3launch` injection, `-quiet -filetrace`), viewed the credits.

## Observations

1. **The game OPENS our SYS.PAK and BOOTS on it.** `FILETRACE`: `GetFileAttributesA` exists +
   `CreateFileA` ok on `Apps\Sys\SYS.PAK`; the menu/UI rendered normally. Every boot-time
   resource comes from SYS.PAK members, so a normal boot means our archive's directory and
   members read correctly IN THE GAME. This is game-side validation, not self-consistency.
2. **The credits scrolled at NORMAL speed** (user-confirmed) — the `4242` value did not visibly
   change the scroll.
3. **Our SYS.PAK differs from the shipped archive by EXACTLY 4 bytes**, contiguous, at file
   offsets 249,902-249,905 — the `"1500"` -> `"4242"` digits of
   `ScrollRateInPixelsPerMinute`. Byte-identical everywhere else (272,507 B both). The member
   is stored UNCOMPRESSED (the string is plaintext in the PAK). `[verified by full byte diff]`

## Why this exonerates the writer

Because our archive is byte-identical to shipped except those 4 value bytes, the game reads it
*exactly* as it would read a hex-edited shipped archive. If the game read offset 249,902 for the
credit scroll rate it would get `4242` and scroll ~3x. It did not. Therefore the game does NOT
drive the credit scroll from that string at that offset — i.e. **the test premise is wrong**, not
the writer. A malformed-archive explanation is impossible: there is no malformation, only the
intended 4-byte edit.

## What is settled

- SETTLED: the **SYS.PAK writer works**. It reproduces the shipped archive byte-for-byte and a
  targeted single-value edit lands exactly at the right offset with nothing else changed, and the
  GAME boots and runs on the written archive. Roadmap gate T3's writer is validated against the
  binary, not just against itself.
- NOT SETTLED (and now a GAME/code question, not a writer question): whether
  `[CreditsTunables] ScrollRateInPixelsPerMinute` actually controls the credit scroll speed. The
  behavioural test could not confirm it because the value produced no visible change even though
  the game demonstrably read our archive. Re-examine the code path that consumes that tunable, or
  pick a tunable with a large, unambiguous visible effect for a behavioural check.

## Method note

The 4-byte diff is the decisive artifact here. A behavioural test that shows "no effect" is
ambiguous (bad writer vs bad premise); the byte diff removes the ambiguity by proving the archive
is sound. When a behavioural check comes back null, diff the artifact against the shipped one
before concluding anything about the tool that produced it.
