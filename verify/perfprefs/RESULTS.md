# perfprefs results (2026-10-12)

Build: branch `child/perfprefs` (sc3resize + sc3perf from the worktree), instance `re/harness/inst_perfprefs` (MAIN live
install) and `Simcity_stock_windowed/re/harness/inst_perfprefs` (stock GZGraphicD/SIMSPR, release perf.ini).
Europolis 256 copy, 800x600 windowed.

**Visual check: DONE at 14:55 on the stock copy** (`Simcity_stock_perfprefs`, own hard-linked mod-free tree per
protocol section 10, release perf.ini), images in MAIN `verify/perfprefs/` (gitignored), each looked at:

| image | shows |
|---|---|
| `21_city_busy_on.png` | city, yellow FPS line and the red busy line (text injected with `busytest`) top-left |
| `22_prefs_open.png` | Preferencias from the in-city flyout: "Ver FPS" and "Ver perfilador" checked, on the row under "Ir a los desastres automatico", left of "Suavizado", no overlap |
| `23_prefs_unchecked.png` | both boxes unchecked, the lines still drawn (nothing applies before OK) |
| `24_after_ok_both_off.png` | one second after OK: no FPS line, no red line, the city under them intact |
| `30_menu_after_restart.png` | after a restart, main menu with no FPS line |
| `31_menu_prefs_saved_state.png` | main menu Preferencias: both boxes unchecked = the saved state |
| `32_menu_after_ok_fps_on.png` | both checked + OK: FPS line back on the main menu at once |

Before the display woke (13:04 to 14:55 it was asleep), the tests below were run on runtime evidence that does not
need the screen: the mods' logs, perf.ini on disk, the live UI
tree (`uiwin_dump.py`), and a Frida hook counting the `TextOutA` calls made from sc3perf.dll
(`textout_count`, numbers normalised to `#`). The overlay is drawn only by those calls.

| # | result | evidence |
|---|---|---|
| T1 | PASS (log + tree) | `PERFPREFS> Preferences ...: FPS box added (1), profiler box added (1)`. Rects: FPS `[18 400 84 417]`, profiler `[120 400 221 417]`, Suavizado `[250 400 327 417]`, game box `[18 381 212 398]`: no overlap. Visual: pending |
| T2 | PASS (runtime) | stock: before, 169 FPS-line draws in 3 s; uncheck + OK -> `PERFPREFS> OK: FPS 0, profiler 1`, perf.ini `overlay=0`, next 3 s: **0** draws |
| T3 | PASS (log) | reopen showed FPS box unchecked (saved state), checked it, Esc: `closed with 0x02F95AD6 (cancel): dialog showed FPS 1 profiler 1, kept 0 1`, perf.ini unchanged |
| T4 | PASS (runtime) | busy text injected (`busytest`). MAIN main menu: profiler off -> 0 busy draws, profiler on + OK -> 74 busy draws in 4 s. Stock city: 53 busy draws in 3 s, profiler off + OK -> 0 |
| T5 | PASS (log) | restart: `sc3perf loaded: overlay=0 ... busy_show=1` (MAIN), `overlay=0 ... busy_show=0` (stock), dialog then showed the saved state |
| T6 | PASS (log + runtime) | main menu Preferencias (MAIN): same two boxes at the same rects, state FPS 0 profiler 1 = saved; FPS on + profiler off + OK applied at once (`OK: FPS 1, profiler 0`) |
| T7 | PASS (runtime) | both on from the main menu -> FPS and busy lines drawn; both off -> `TextOutA from sc3perf in 4 s: none` |
| T8 | PASS (log + tree) | `SC3RESIZE_PERFPREFS=0`: `PERFPREFS> off`, HUDOPT controls added, the only child at y 400 is Suavizado |
| T9 | PASS for T1/T2/T4/T5 on stock (Simcity_stock_windowed) | a second no-city launch there died at 0.12 s: another session copied mod DLLs into `Simcity_stock_windowed\Apps` at 14:03 (the known "mods in Apps + mods from inst_" crash). Not this change |

The Preferences dialog does not raise the busy line by itself: with it open `sim_status` reads `hold: 2`, and the
detector treats a held city as a deliberate pause.

perf.ini after the dialog wrote it: `overlay=0` replaced in place under its comment, `busy_show=0` appended at the
end of `[perf]`, every other line and comment unchanged.
