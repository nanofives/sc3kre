/* ===== WEATHER (owner 2026-11-06: the community "clouds on/off" cheat as a switch on the mods page). =====
 * "Clima: Lluvia y nubes" ticked = the game's own clouds and rain stay on. Unticked = stock weather.
 * Saved as sc3resize.ini [weather] rain=1, applied on OK and at every start. SC3RESIZE_WEATHER=0: nothing installed.
 *
 * Static read (re/analysis/COMMUNITY_MODS.md "Weather"):
 *  - SIMMISC cSC3WeatherLayer vtable 0x10041000. SetWeather (+0x60, 0x1001b733, thiscall (type, int), ret 8) stores
 *    +0x7c / +0x80 and posts message 0xF2ED2A04. The layer's season tick (0x1001b4bb) calls SetWeather(0) on some
 *    season changes; the type is not saved, so every load starts at 0.
 *  - SIMSPR cSC3WeatherViewSimulator: clouds and rain show only while visibility byte +0x18 / +0x48 == 0xF.
 *    The 0xF2ED2A04 handler (0x1002b526) clears bit 2 for type 0, but for a non-zero type sets it only when
 *    RandomUint32Uniform(3) == 0: `85 c0 75 7f` at 0x1002b559. That 1-in-3 roll is why the cheat's rain "fades".
 * While on: the jnz at SIMSPR 0x1002b55b is NOPed (every non-zero SetWeather shows weather) and the SetWeather vtable
 * cell SIMMISC 0x10041060 is wrapped so a type 0 becomes 1. The view only tests zero / non-zero. Off: the two bytes are
 * put back, the wrapper passes through, and SetWeather(0) clears the sky now (stock weather resumes on its own). */
static int    g_weather = 1;          /* feature present (SC3RESIZE_WEATHER=0 off) */
static int    g_wx_on = 0;            /* the switch */
static HMODULE g_wx_spr, g_wx_misc;
static DWORD  g_wx_orig_set;          /* SIMMISC 0x1001b733 */
static BYTE  *g_wx_jnz;               /* SIMSPR 0x1002b55b */

static void __fastcall wx_setweather(void *self, void *edx, int type, int a2) {
    if (g_wx_on && type == 0) type = 1;
    ((void (__fastcall *)(void *, void *, int, int))g_wx_orig_set)(self, edx, type, a2);
}

static int wx_install(void) {
    static const BYTE roll[4] = { 0x85, 0xc0, 0x75, 0x7f };   /* test eax,eax; jnz +0x7f */
    DWORD *cell, old;
    BYTE *j;
    if (g_wx_orig_set) return 1;
    if (!g_weather) return 0;
    g_wx_spr = GetModuleHandleA("SIMSPR.DLL"); g_wx_misc = GetModuleHandleA("SIMMISC.DLL");
    if (!g_wx_spr || !g_wx_misc) { logf("WEATHER> SIMSPR/SIMMISC not loaded: off"); g_weather = 0; return 0; }
    cell = (DWORD *)((BYTE *)g_wx_misc + 0x41060);
    j = (BYTE *)g_wx_spr + 0x2b559;
    if (*(DWORD *)((BYTE *)g_wx_misc + 0x41000 + 0x60) != (DWORD)g_wx_misc + 0x1b733 || memcmp(j, roll, 4)) {
        logf("WEATHER> SIMMISC SetWeather / SIMSPR weather roll differ from shipped: off"); g_weather = 0; return 0; }
    if (!VirtualProtect(cell, 4, PAGE_EXECUTE_READWRITE, &old) || !VirtualProtect(j, 4, PAGE_EXECUTE_READWRITE, &old)) {
        logf("WEATHER> VirtualProtect failed: off"); g_weather = 0; return 0; }
    g_wx_jnz = j + 2;
    g_wx_orig_set = *cell;
    *cell = (DWORD)wx_setweather;
    logf("WEATHER> installed: SetWeather wrapped (SIMMISC 0x10041060), weather roll at SIMSPR 0x1002b55b");
    return 1;
}

/* the current city's weather layer: cISC3City::WeatherLayer slot +0x190 (SIMCITY 0x10002bd4, mov eax,[ecx+0xf8]) */
static void *wx_layer(void) {
    void *c = sf_city(), *l = NULL;
    if (!c || IsBadReadPtr(c, 0x100)) return NULL;
    __try { l = (void *)ho_v(c, 0x190, 0, 0, 0, 0, 0, 0); } __except (EXCEPTION_EXECUTE_HANDLER) { l = NULL; }
    if (!l || IsBadReadPtr(l, 0x84) || *(DWORD *)l != (DWORD)g_wx_misc + 0x41000) return NULL;
    return l;
}

/* on = 1/0; live = also change the current city's sky now */
static void wx_set(int on, int live) {
    void *l;
    if (!wx_install()) return;
    g_wx_on = on ? 1 : 0;
    g_wx_jnz[0] = on ? 0x90 : 0x75; g_wx_jnz[1] = on ? 0x90 : 0x7f;
    FlushInstructionCache(GetCurrentProcess(), g_wx_jnz, 2);
    if (live && (l = wx_layer()) != NULL) {
        __try { ((void (__fastcall *)(void *, void *, int, int))g_wx_orig_set)(l, NULL, on ? 1 : 0, 0); }
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("WEATHER> fault in SetWeather"); }
    }
    logf("WEATHER> rain and clouds %s%s", on ? "ON" : "off (stock weather)", live ? (wx_layer() ? ", applied to this city" : ", no city open") : "");
}

static int wx_ini_on(void) {
    char p[MAX_PATH];
    ho_ini_path(p, sizeof(p));
    return GetPrivateProfileIntA("weather", "rain", 0, p) ? 1 : 0;
}

static void wx_save(int on) {
    char p[MAX_PATH];
    ho_ini_path(p, sizeof(p));
    WritePrivateProfileStringA("weather", "rain", on ? "1" : "0", p);
}

/* per-frame poll (game thread): a city view built while the type was 0 never gets weather (measured: a load with the
 * switch saved on showed no clouds, the view's SetupInitialWeather 0x1002ab1a reads GetWeather once). So 3 s after a
 * new city layer appears, SetWeather(1) once more. */
static void  *g_wx_seen;
static DWORD  g_wx_seen_ms, g_wx_poll_ms;
static void wx_tick(void) {
    DWORD now;
    void *l;
    if (!g_wx_on || !g_wx_orig_set) return;
    now = GetTickCount();
    if (now - g_wx_poll_ms < 500) return;
    g_wx_poll_ms = now;
    l = wx_layer();
    if (l != g_wx_seen) { g_wx_seen = l; g_wx_seen_ms = l ? now : 0; return; }
    if (l && g_wx_seen_ms && now - g_wx_seen_ms >= 3000) {
        g_wx_seen_ms = 0;
        __try { ((void (__fastcall *)(void *, void *, int, int))g_wx_orig_set)(l, NULL, 1, 0); }
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("WEATHER> fault in SetWeather"); return; }
        logf("WEATHER> new city: rain and clouds requested");
    }
}

/* at start: install only when the saved switch is on, so an unticked game runs the stock code bytes */
static void wx_startup(void) {
    if (!g_weather) { logf("WEATHER> off (SC3RESIZE_WEATHER=0)"); return; }
    if (wx_ini_on()) wx_set(1, 0);
}
