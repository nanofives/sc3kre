# AUDIO.DLL — C0 slice analysis (25 largest, all bodies read)

All facts below are from the decompiled bodies in `re/ghidra_export_audio/functions/`. Addresses are Ghidra VAs. Every function was read in full; all are rated **C2** (body read, mechanics described, callees identified, named). None required execution.

## Shared structural facts (the AudioManager object)

The module is built around one central class — call it the **AudioManager** — constructed at `0x10004f20` and stored as the global singleton `DAT_10026f00` [CONFIRMED @ 0x10004f20:127]. `DAT_10026ef0` is the low-level sound-device/driver object (its vtable slot `+0x64`/`+100` and `+0x58` create sound instances; used everywhere). Key `this` offsets recovered by cross-referencing the init, dispatch, tick and shutdown:

- `+0xc` init flag; `+0x18` play-state (5 = running); `+0x1c` saved state
- `+0x24` SFX vol, `+0x28` music vol, `+0x2c` ambience/master vol [CONFIRMED @ 0x100053e3:96-116, 0x10008d77:189-198]
- `+0x34..0x78` the tunable block (see table below)
- `+0x10` music player; `+0x18c` city-sim/traffic layer (queried via vtable +0x60/0x70/0x74/0x88/0x90/0x94/0xa0/0xa8) — the `[iOS-HINT] goCitySimulator/goTrafficLayer` witness, unconfirmed on x86 side
- `+0x10c..0x168` per-terrain/per-zone "fsc" ambience-set objects (each `operator_new(0x40c0)`)
- **`+0x190` (decimal 400) = base of a 512-entry sound-instance pointer array**, indexed `this + id*4 + 400`, id ∈ [1,0x200) [CONFIRMED @ 0x10008d77:53, 0x10002e5a:182, 0x1000865b:48-60]
- `+0x9e8..0xa20` = 15 channel/voice descriptor objects (`operator_new(0x2c)`, ctor `FUN_10004e72`) [CONFIRMED @ 0x100053e3:1771-1890]
- `+0x9bc` zoom level; `+0x9cc` rotation/mode; `+0x990..0x9b8` cached listener/view

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100053e3,audio-init/config,C2,sc3_audio_manager_init_from_ini,"AudioManager::Init; opens audio.ini, reads ~40 [Options] keys via FUN_100189b6, builds 22 zone fsc sets (operator_new 0x40c0) + 15 voice descriptors (FUN_10004e72), then 512-slot init loop [0x100053e3:117-1899]"
0x10008d77,audio-dispatch,C2,sc3_audio_handle_message,"central message-id dispatch; nested switch over ids 1..0x421 driving the 512-slot table and layer; sets vols on 0x3ea/0x3eb/0x3ec [0x10008d77:40-441]"
0x10009890,audio-sim-tick,C2,sc3_audio_update_ambience_mix,"per-tick mixer, gated every 4 ticks (this+0xac); walks visible cells, drives per-zone ambience vols/fades; calls FUN_1000a995,FUN_1000a145 [0x10009890:24-305]"
0x1000ea5e,audio-serialization,C2,sc3_audio_load_freshness_table,"loads text table (version 5/6/7) via FUN_1001bc1c/1bd26/1be7c; sscanf header 14 ints -> this+4..0x38; nested rows*cols grid of 0x5c-byte cells at this+(row*0x40+col)*4 [0x1000ea5e:71-471]"
0x10018068,audio-ini,C2,sc3_audio_ini_write_key,"read-modify-write of an INI section; detects '[' headers, ';' comments, '=' split (DAT_10026c28); formats [%s]/%s = %s; writes via vtable+0x40 [0x10018068:130-309]"
0x10002e5a,audio-serialization,C2,sc3_audio_parse_sound_entry_a,"parses 2 token strings (delims DAT_10026270/1002626c) via FUN_1001b24c; if id in [1,0x200) builds sound obj operator_new(0xb8)+FUN_10012d97 into slot table [0x10002e5a:181-198]"
0x1000865b,audio-shutdown,C2,sc3_audio_manager_shutdown,"tears down everything if this+0xc set: music player, 512 slots (+0x1c/+0xc), 15 voice descs, all fsc sets (+0x20/+0x10/+0x58), cache; clears this+0xc [0x1000865b:16-298]"
0x10009890,,,,
0x1000401f,audio-serialization,C2,sc3_audio_parse_multi_sound_entry,"parses entry with sub-list (count local_2c -> array of operator_new(0x14)) and date range sscanf %2d-%2d..%2d-%2d default 1/1..12/31; obj operator_new(0x154)+FUN_1001422b into slot table [0x1000401f:137-228]"
0x10003a1e,audio-serialization,C2,sc3_audio_parse_sound_entry_b,"variant parser; several bool flags (iVar!=1); obj operator_new(0x78)+FUN_100147ec into slot table if id<0x200 [0x10003a1e:181-198]"
0x1000287d,audio-serialization,C2,sc3_audio_parse_sound_entry_c,"variant parser; validates id 1..0x200 + FUN_10004bdc; obj operator_new(0x5c)+FUN_100127a4 into slot table [0x1000287d:59-212]"
0x1000467b,audio-serialization,C2,sc3_audio_parse_music_entry,"parses entry, chooses operator_new(0x5c)+FUN_100109b0 or operator_new(0xc8)+FUN_10010c40 by local_3c; inits via vtable[0], registers into music player (FUN_100103a7) [0x1000467b:153-181]"
0x10003584,audio-serialization,C2,sc3_audio_parse_sound_entry_d,"variant parser; obj operator_new(0x64)+FUN_10013c61 into slot table if id 1..0x1ff [0x10003584:141-157]"
0x10012f16,audio-streamsound,C2,sc3_audio_streamsound_init,"creates 3 stream sounds via DAT_10026ef0 vtable+100 into this+0x3c/0x40/0x44 from names at this+0x4c/0x60/0x74; sets vol(this+0x10+0x4c) & flag _DAT_10021154; this+0x14=1 [0x10012f16:34-166]"
0x1000d418,audio-music-sched,C2,sc3_audio_music_scheduler_tick,"music/freshness scheduler; advances day counter param_1[0x15] on FUN_10019f58 clock (86400000ms/day), per day walks grid calling FUN_1000f6e9 per cell; stats DAT_10026f7c..f90 [0x1000d418:30-159]"
0x1000f6e9,audio-music-state,C2,sc3_audio_song_update_state,"per-song state machine (this+8: 1=load,2=play,3,4=fadeout/repeat,5=stop); builds path FUN_1000b83d, creates via DAT_10026ef0+100, play vtable+0x70 [0x1000f6e9:31-202]"
0x10011a6e,audio-event-map,C2,sc3_audio_classify_tile_sound,"tile->sound-category classifier; looks up occupant via FUN_10015b45 vtable+0x88/0x7c, matches type ids (0x2454,0x21fc,0x302a,...) via this+0x24 vtable+0x24, returns category 1..0xe [0x10011a6e:15-152]"
0x1000dca1,audio-music-select,C2,sc3_audio_pick_random_song_cell,"random eligible song-cell picker; rand()->row/col mod grid dims (this+0x30+0x24/0x28); scans for cell type==4 & +0x15==0; uniform pick via FUN_1001a253 [0x1000dca1:21-127]"
0x10004f20,audio-init,C2,sc3_audio_manager_ctor,"AudioManager ctor; sets 2 vtables, default tunables (0x400 vols,10000,0xfa,300...), zeroes 512-slot array, allocs sub-objs (FUN_1001b691,FUN_10019f90); sets singleton DAT_10026f00 [0x10004f20:19-150]"
0x1000a459,audio-listener,C2,sc3_audio_update_listener_position,"view/camera change handler (msg 0x400); caches zoom/rot/center to this+0x990..0x9b8; pushes listener pos (vtable+0x7c) to all fsc sets + 15 voices; then FUN_10009890 [0x1000a459:21-134]"
0x1000b48b,audio-event-map,C2,sc3_audio_play_building_sound,"one-shot positional building/disaster sound (dispatch case 200); layer vtable+0x94 group id (0x118,0x119,0x11b-0x11e), variant table DAT_1002050c via RNG, quadrant pan _DAT_10020608/10020610 [0x1000b48b:70-151]"
0x10018c53,audio-ini,C2,sc3_audio_ini_foreach_key,"enumerates a [section]'s key=value lines (split DAT_10026c28), collects 0x28-byte pairs, invokes callback param_2(key,val,param_3) per entry [0x10018c53:74-107]"
0x100189b6,audio-ini,C2,sc3_audio_ini_get_value,"INI key read (GetPrivateProfileString-equiv); finds section, splits '=' , compares key (FUN_1000c68a), writes value to param_3, returns bool; powers all audio.ini tunables [0x100189b6:54-108]"
0x100143c8,audio-emitters,C2,sc3_audio_update_random_emitters,"per-tick random emitter spawner; reaps done voices (+0xe0 array), region gate via layer+0xa8, RNG (FUN_1001a253) vs weight*BuildingRandMultiplier(mgr+0x38), creates+plays; vol from mgr+0x2c/+0x50/zoom [0x100143c8:39-139]"
0x1000da02,audio-music-select,C2,sc3_audio_find_best_cell,"best-scoring cell search in a random-jittered window (rand within +/-this+0x74/0x70 of this+0x40/0x44); scores cells via vtable+0x98, tracks max into param_1/param_2 [0x1000da02:35-117]"
```

## 2. Notable findings (highest value)

**Tunable table — `audio.ini` `[Options]` keys (the modding surface).** `FUN_100053e3` reads ~40 named keys through `sc3_audio_ini_get_value` (`FUN_100189b6`) and writes each to a fixed `this` offset. Section string `s_Options_10026860`, file `s_audio_ini_1002688c`. Confirmed key → offset map [all CONFIRMED @ 0x100053e3]:

| Key (string) | Store | Key | Store |
|---|---|---|---|
| MusicPlayerSongDurationMsec | `*(this+0x10)+0x9c` | HonkAttenuation | this+0x58 |
| MusicPlayerSongDelayMsec | `*(this+0x10)+0xa0` | HonkMinZoom | this+0x5c |
| FreshnessIntroDurationMsec | `*(this+0x10)+0xa4` | VehicleAttenuation | this+0x60 |
| FreshnessOutroDurationMsec | `*(this+0x10)+0xa8` | VehicleMinZoom | this+0x64 |
| FreshnessMaxXSpeed | `*(this+0x10)+0xac` | VehicleEffectsLevel | this+0x68 |
| ZoomLoopVol | this+0x34 | VehicleEffectsPreset | this+0x6c (+ device vtable+0x80) |
| BuildingRandMultiplier | this+0x38 | VehicleEffectsTallBuildingCrit | this+0x70 |
| UseCdForMusic | this+0x38 | ForceCrimeTempo | this+0x74 |
| TrafficDensityMin | this+0x3c | ForceAmbienceQuadrant | this+0x78 (sets DAT_10026ffc/DAT_10027000) |
| TrafficDensityMultiplier | this+0x40 | AmbienceStartFadeAtPercent | this+0xa2c |
| VehicleHonkDivisor | this+0x44 | AmbienceMinimumFadedVolume | this+0xa30 |
| VehicleMaxDistance | this+0x48 | FreshnessSelectionAreaMinMsec | this+0xa34 |
| VehicleMinDistance | this+0x4c | MusicStartDelayAfterStop | this+0xa38 |
| BuildingsInAmbienceAttenuation | this+0x50 | UseC2HCache / CachePath / CacheSize | cache obj this+0x188 |
| BuildingsInAmbienceMinZoom | this+0x54 | MusicDataDir | music path |

Also `Res/Sound/` prefix (`s_Res_Sound__10026898`), and the 22 hard-coded ambience file stems (`commercial.fsc`, `industrial.fsc`, `Nature.fsc`, `Desert.fsc`, `Jungle.fsc`, `Arctic.fsc`, `Wind.fsc`, `construction.fsc`, `water.fsc`, `zm3.fsc`, `zm3city.fsc`, `traffic.fsc`, `Agricult.fsc`, `Seaport.fsc`, `Airports.fsc`, `Abandoned.fsc`, `Garbage.fsc`, `Crime.fsc`, `Unpwrd.fsc`, `pipes.fsc`, `subway_v.fsc`) each paired with an `sfx_zones_*` sound-set name [CONFIRMED @ 0x100053e3:986-1768].

**Message-id dispatch table** — `sc3_audio_handle_message` (`0x10008d77`). The single entry point that routes engine events to audio. Confirmed ids: 1-0xc = per-slot ops on `this+id*4+400`; `0xc8` = play building sound; `0xcb` = classify+play tile sound (via `sc3_audio_classify_tile_sound`); `0xcf` = random ambience; `0x3ea/0x3eb/0x3ec` = set SFX/music/ambience volume; `0x3f2-0x3fa` = music transport (play/stop/pause via `this+0x10`); `0x40d-0x420` = city sim register (`0x40e` binds layer to `this+0x18c`)/teardown (`0x40f` stops all fsc + 512 slots)/pause/resume state machine on `this+0x18`. [CONFIRMED @ 0x10008d77:40-441]

**Tick entry points** — `sc3_audio_update_ambience_mix` (`0x10009890`, gated 1-in-4 via `this+0xac`) and `sc3_audio_music_scheduler_tick` (`0x1000d418`, day-clock driven, 86400000 ms/day). The latter is the "Freshness"/music-rotation scheduler stepping a calendar grid loaded by `sc3_audio_load_freshness_table`.

**Serializer** — `sc3_audio_load_freshness_table` (`0x1000ea5e`) is the one true file loader (versions 5/6/7, 14-int header, rows×cols grid of 0x5c-byte cells). The six `sc3_audio_parse_sound_entry_*` functions (`0x10002e5a`, `0x1000401f`, `0x10003a1e`, `0x1000287d`, `0x1000467b`, `0x10003584`) are a **parser family**: each consumes the same two tokenized strings (delimiters `DAT_10026270`, `DAT_1002626c`) and constructs a different sound-object subclass (ctors `FUN_10012d97`/0xb8, `FUN_1001422b`/0x154, `FUN_100147ec`/0x78, `FUN_100127a4`/0x5c, `FUN_10013c61`/0x64, `FUN_100109b0`/`FUN_10010c40`) into the 512-slot table — i.e. one parser per sound "type".

**INI subsystem** — `sc3_audio_ini_get_value` (`0x100189b6`), `sc3_audio_ini_write_key` (`0x10018068`), `sc3_audio_ini_foreach_key` (`0x10018c53`) form a self-contained INI reader/writer keyed on `'='` (`DAT_10026c28`), `'['` sections, `';'` comments.

## 3. Not determined / uncertain

- **Tokenizer delimiter literals.** `DAT_10026270` and `DAT_1002626c` (the two split strings used by every entry parser) and `DAT_10026c28` (INI split) are referenced by address only; I did not read their byte values. [UNCERTAIN] — missing: a Read of `strings.csv`/`globals.csv` or the data bytes at those RVAs to confirm they are `","` / `" "` / `"="`.
- **`this+0x18c` layer identity.** Consumed purely by vtable index (e.g. +0x94 = tile group id, +0xa8 = view region). The `[iOS-HINT]` name `goCitySimulator`/`goTrafficLayer` is plausible but unconfirmed here; missing an SC3U-side string/RTTI witness.
- **Return-code semantics of `sc3_audio_classify_tile_sound` (`0x10011a6e`).** Returns 1..0xe used as a slot/category index by the dispatcher, but the mapping of each numeric code to a concrete sound is not literal in this body (it depends on the matched building-group constants). Mechanically fully described; semantic labels not determined without the building-group id table.
- No function in the slice was left unclassified.
