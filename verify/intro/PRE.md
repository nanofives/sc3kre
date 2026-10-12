# PRE: intro movie shown whole (task intro, 2026-10-12)

Written before the first run of the INTRO build. Owner report: "arreglar la intro que se ve cortada"
(release sc3mods-2026-10-12, stock install, laptop).

## Mechanism established before this file (static + live trace, no fix loaded)

- SC3U `FUN_00429f95` plays `Res/UI/Shared/Movies/Intro.tgq` through UV.DLL. Placement: x0 = (surface w - 640)/2,
  y0 = (surface h - 480)/2, converted by the graphics driver `vt+0x68`, then `vt+0x40((x & 0xffff) >> 1, y)` on the
  movie object (`FUN_0043f126` stores them as UV ctx `+0x68/+0x6c`). [CONFIRMED @ 0x00429f95]
- UV ctx flags = `0x038114C3` (live): `0x400` = the codec Locks the PRIMARY and writes pixels itself, `0x40` = double width.
  Movie source 320x480 (ctx `+100`, `+0x60`, live).
- Frame write: UV `FUN_10005c40` case 4 calls `FUN_10006900(p, src, bits + x*4 + y*pitch, ..., pitch)` at UV `0x10005ef9`.
  One DWORD per source pixel. [CONFIRMED @ UV 0x10005c40, live: writer FUN_10006900, frame type 4]
- Live, dev PC, windowed 800x600 window, mods loaded: primary 1680x1050, pitch 6720, **32bpp**. Client origin on screen
  (440,212). Codec dest x,y = **260,272** = ((440+80)/2, 212+60).
- In-process dump of a written frame (`codec_frame_32bpp_dump.png`): a **320x480** picture, correct colours, from the dest.

So on a 32bpp primary the movie is half width and starts 180 px left of the client: 260..580 against a client 440..1240.
Only screen columns 440..579 (the right 140 of 320) fall in the window. That is the cut picture.

## Predictions for the INTRO build (default, SC3RESIZE_INTRO unset)

1. Log: `--- INTRO: armed (mode 1)`, `INTRO> primary 1680x1050 pitch 6720 bpp 32`.
2. First frame line: client 800x600 at 440,212, movie 320x480 shown **640x480 at 520,272** (centred, 80/60 px black bars).
3. In-process witness (Frida at the codec's Unlock call, UV `0x10005ffa`): the client region of the locked primary holds
   the full picture 640 wide (left edge content present at client x=80), black bars elsewhere, nothing magenta.
4. Maximized during the intro: the frame line logs the new client and the picture at 2x (1280x960) if the client is at
   least 1280x960, centred.
5. `SC3RESIZE_INTRO=0`: log `--- INTRO: off`, codec dest x,y 260,272 again (stock behaviour).
6. On screen (sc3io grab, only if the display is awake): whole picture, not squeezed, centred, black bars.
7. Stock install (`Simcity_stock`): same log lines and same result.

## What would falsify

- bpp read as 16 on this PC (then the cut has another cause on 32bpp-free setups).
- Any write outside the client, a crash in UV, or the game failing to reach the menu after the movie.
- The picture still 320 wide (would mean the 2x horizontal is not applied).
