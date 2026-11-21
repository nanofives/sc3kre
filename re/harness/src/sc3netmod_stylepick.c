/* sc3netmod_stylepick.c - STYLEPICK (task stylepick 2026-11-21, Simtropolis: "work like SC4? choosing a building style
 * doesn't change the appearance of existing buildings, but it does affect what buildings get built").
 * Included by sc3netmod.c. SC3NETMOD_STYLEPICK=0 (Turn mods on/off row "Style picks new buildings") = stock re-skin.
 *
 * Stock (evidence in re/analysis/BUILDING_PICK.md section 8, verify/stylepick/RESULTS.md):
 *   - Options > City Properties = menu item 0x1000900A, command 0x855a2dc4 param 0 (SYS.PAK MenuItem.INI). SIMUI
 *     Execute 0x10011bc5 runs the modal dialog (ctor 0x1005b6f4, mode 0 reads the current set from scheme vt+0x64)
 *     and on OK calls scheme vt+0x18 SetCityScheme(landscape, flora, building set, progress = mode == 0). The New City
 *     flows use the same command with modes 1..3 (progress 0).
 *   - SetCityScheme SIMINIT 0x10006589 with a new building set unloads the old set archives, registers the new ones
 *     FRONT in GZResourceD and re-Inits every live occupant of their keys (FUN_10006f69): standing buildings re-skin.
 *     Then FUN_10006ec9 (Linux name UpdateDevelopers) drops every family resource and has the ZoneLayer re-read the
 *     developers (vt+0x90(1)), so family weights are re-read at run time.
 *   - The city saves [building set, flora, landscape] in record {0x0525A6B9, 0x4525A6E2, 1}: SIMCITY 0x10004ccd
 *     (cSC3City::SaveCitySchemeInfo) writes it, SIMINIT 0x10009e1f (cSC3CmdLoadCity::SetCityScheme) reads it.
 *   - Families: SIMGEOM 0x10001250 parses each BUILDFAM record into the vector at family+0x20 of {attrib, weight}
 *     pairs, count at +0x1c (vt+0x10 returns it, vt+0x14 copies that many pairs to the rules).
 *
 * With STYLEPICK on:
 *   - The SKIN (the set archives loaded, what base ids draw as) changes only on a city load (the saved set, stock) or
 *     a New City (always 0). City Properties never re-skins: SetCityScheme is called with the current skin, so the
 *     stock code loads nothing and re-Inits nothing; landscape and flora still apply.
 *   - The STYLE the player picks (set P, plus the "Mix" box M of the dialog, sc3resize SPMIX) decides which family
 *     members grow. After each parse the family vector is filtered (sp_filter) by id: base ids, European copies
 *     (+400000), Asian copies (+1500000) and North American copies (+2600000, style_mix 1.1.0 "00000000"). Members
 *     the filter drops are removed and the count lowered: the state the stock parser leaves for a weight-0 line
 *     (0x1000136f), which STYLEMIX already ships. A family the filter would empty is left whole.
 *   - P and M are saved in their own record {0x0525A6B9, 0x4525A6E2, SP_INST} next to the stock one. A stock game
 *     never asks for that key. A city without it (every save so far) loads with P = its saved set and M = 1, which is
 *     what it grew before (the style mix).
 *   - The dialog shows P (scheme vt+0x64 answers P to the dialog's constructor only).
 * With STYLEPICK off nothing is hooked except the family filter, which then only drops the North American copies, so
 * the mix keeps the ratio it had before style_mix 1.1.0. */

#define SP_EURO   0xE523F3FBu
#define SP_ASIA   0x6523F3D5u
#define SP_OFF_E  400000u
#define SP_OFF_A  1500000u
#define SP_OFF_N  2600000u
#define SP_SPAN   65536u
#define SP_INST   0x5354594Cu          /* save record instance ("LYTS") under the stock scheme record's type + group */
#define SP_MAGIC  0x53505031u          /* "1PPS" */

static int  g_sp_on = 0;               /* SC4-like mode (SC3NETMOD_STYLEPICK, default on) */
static int  g_sp_filter = 0;           /* the family filter is in */
static volatile LONG g_sp_set = 0;     /* P: the style the player picked (building set id, 0 = North American) */
static volatile LONG g_sp_mix = 1;     /* M: grow all three styles */
static volatile LONG g_sp_pend = -1;   /* the dialog's Mix box on OK (sc3resize), -1 = none */
static volatile LONG g_sp_parsed = -1; /* sp_key() the last filtered family used */
static volatile LONG g_sp_nfilt, g_sp_ndrop, g_sp_nkeep_all;
static BYTE *g_sp_init, *g_sp_ui;      /* SIMINIT / SIMUI bases */
static DWORD g_sp_uisize;              /* SIMUI SizeOfImage */
static DWORD g_sp_o_scs, g_sp_o_cur, g_sp_o_parse, g_sp_o_load, g_sp_o_save;
static int  g_sp_loading;              /* inside cSC3CmdLoadCity::SetCityScheme (UI thread) */
static int  g_sp_lhave; static DWORD g_sp_lset, g_sp_lmix;

static BYTE *sp_scheme(void) {         /* scheme manager = [app + 0x108], app = [SC3U 0x4fa86c] (batslots_lab) */
    BYTE *app, *s;
    if (IsBadReadPtr((void *)0x4fa86c, 4)) return NULL;
    app = *(BYTE **)0x4fa86c;
    if (!app || IsBadReadPtr(app + 0x108, 4)) return NULL;
    s = *(BYTE **)(app + 0x108);
    if (!s || IsBadReadPtr(s, 0x60) || !g_sp_init || *(BYTE **)s != g_sp_init + 0x2f528) return NULL;
    return s;
}
static DWORD sp_skin(void) {           /* +0x58 set archives loaded, +0x50 the set (GetCurrentBuildingSet 0x100054a8) */
    BYTE *s = sp_scheme();
    return (s && s[0x58]) ? *(DWORD *)(s + 0x50) : 0;
}
static LONG sp_key(void) {             /* what the filter depends on, packed */
    DWORD sk = sp_skin(), p = (DWORD)g_sp_set;
    LONG k = (sk == SP_EURO ? 1 : sk == SP_ASIA ? 2 : sk ? 3 : 0);
    k |= (p == SP_EURO ? 1 : p == SP_ASIA ? 2 : p ? 3 : 0) << 2;
    return k | (g_sp_mix ? 16 : 0) | (g_sp_on ? 32 : 0);
}
static const char *sp_name(DWORD s) { return s == SP_EURO ? "European" : s == SP_ASIA ? "Asian" : s ? "other" : "North American"; }

/* ---- the family filter (after SIMGEOM 0x10001250) ---- */
typedef struct { void *a; LONG w; } SP_PAIR;
static DWORD sp_id(void *attrib) {     /* attrib vt+0x14 Key() -> const cGZResourceKey & (CodeView) */
    DWORD *k;
    if (!attrib || IsBadReadPtr(attrib, 4) || IsBadReadPtr(*(void **)attrib, 0x18)) return 0;
    k = ((DWORD *(__fastcall *)(void *, void *))(*(DWORD **)attrib)[5])(attrib, NULL);
    if (!k || IsBadReadPtr(k, 12) || k[0] != 0x207EDC0E || k[1] != 0x57E) return 0;
    return k[2];
}
static int sp_cls(DWORD id, DWORD *b) {   /* 0 base / other, 1 European copy, 2 Asian, 3 North American */
    if (id >= SP_OFF_E && id < SP_OFF_E + SP_SPAN) { *b = id - SP_OFF_E; return 1; }
    if (id >= SP_OFF_A && id < SP_OFF_A + SP_SPAN) { *b = id - SP_OFF_A; return 2; }
    if (id >= SP_OFF_N && id < SP_OFF_N + SP_SPAN) { *b = id - SP_OFF_N; return 3; }
    *b = id; return 0;
}
#define SP_MAXF 1024
static void sp_filter(BYTE *fam) {
    SP_PAIR *v, *e;
    DWORD ids[SP_MAXF], base[SP_MAXF], sk, p;
    BYTE cls[SP_MAXF], keep[SP_MAXF];
    int n, i, j, k = 0, mix;
    if (!fam || IsBadReadPtr(fam, 0x2c)) return;
    v = *(SP_PAIR **)(fam + 0x20); e = *(SP_PAIR **)(fam + 0x24);
    if (!v || e < v) return;
    n = (int)(e - v);
    if (n <= 0 || n > SP_MAXF || (DWORD)n != *(DWORD *)(fam + 0x1c) || IsBadWritePtr(v, n * sizeof(SP_PAIR))) return;
    sk = sp_skin(); p = (DWORD)g_sp_set; mix = g_sp_mix != 0;
    for (i = 0; i < n; i++) { ids[i] = sp_id(v[i].a); cls[i] = (BYTE)sp_cls(ids[i], &base[i]); }
    for (i = 0; i < n; i++) {
        int hasE = 0, hasA = 0, hasN = 0, wantN, wantE, wantA, skinned;
        DWORD b = base[i];
        if (!ids[i]) { keep[i] = 1; continue; }
        for (j = 0; j < n; j++) if (ids[j] && base[j] == b) { hasE |= cls[j] == 1; hasA |= cls[j] == 2; hasN |= cls[j] == 3; }
        skinned = (sk == SP_EURO && hasE) || (sk == SP_ASIA && hasA);
        if (!g_sp_on) { keep[i] = cls[i] != 3; continue; }           /* stock: only the North American copies go */
        wantE = mix || (p == SP_EURO && hasE);
        wantA = mix || (p == SP_ASIA && hasA);
        wantN = mix || !((p == SP_EURO && hasE) || (p == SP_ASIA && hasA));
        switch (cls[i]) {
        case 1: keep[i] = (BYTE)wantE; break;
        case 2: keep[i] = (BYTE)wantA; break;
        case 3: keep[i] = (BYTE)(wantN && skinned); break;
        default: keep[i] = (BYTE)(wantN && !(skinned && hasN)); break;
        }
    }
    for (i = 0; i < n; i++) k += keep[i];
    InterlockedIncrement(&g_sp_nfilt);
    g_sp_parsed = sp_key();
    if (k == n) return;
    if (!k) { InterlockedIncrement(&g_sp_nkeep_all); return; }         /* never empty a family */
    for (i = 0, j = 0; i < n; i++) if (keep[i]) v[j++] = v[i];
    *(SP_PAIR **)(fam + 0x24) = v + k;
    *(DWORD *)(fam + 0x1c) = (DWORD)k;
    InterlockedExchangeAdd(&g_sp_ndrop, n - k);
}
static char __fastcall sp_parse(void *fam, void *edx, void *stream) {   /* replaces the call at SIMGEOM 0x10001170 */
    char r = ((char (__fastcall *)(void *, void *, void *))g_sp_o_parse)(fam, edx, stream);
    if (r) sp_filter((BYTE *)fam);
    return r;
}

/* ---- run-time refresh: drop and re-read the families (SIMINIT FUN_10006ec9, UpdateDevelopers) ---- */
static void sp_refresh(BYTE *scheme, const char *why) {
    void *city = ((void *(__cdecl *)(void))(g_sp_init + 0x298b6))();   /* SL::City */
    if (g_sp_parsed == sp_key()) return;
    if (city) ((void (__fastcall *)(void *, void *))(*(DWORD **)city)[0x234 / 4])(city, NULL);   /* lock, as 0x10006589 */
    ((void (__fastcall *)(void *))(g_sp_init + 0x6ec9))(scheme);
    if (city) ((void (__fastcall *)(void *, void *))(*(DWORD **)city)[0x238 / 4])(city, NULL);
    logf("stylepick: families re-read (%s), %ld family parse(s) so far, %ld member(s) left out", why, g_sp_nfilt, g_sp_ndrop);
}

/* ---- SetCityScheme, scheme vt+0x18 ---- */
static char __fastcall sp_scs(BYTE *self, void *edx, DWORD land, DWORD flora, DWORD set, DWORD prog) {
    DWORD ra = (DWORD)_ReturnAddress(), skin = (self[0x58] ? *(DWORD *)(self + 0x50) : 0), pass = set;
    const char *who = "other";
    char r;
    LONG pend;
    if (g_sp_on) {
        if (g_sp_loading) {                                       /* a city load: the saved skin, stock */
            who = "load";
            g_sp_set = (LONG)(g_sp_lhave ? g_sp_lset : set);
            g_sp_mix = (LONG)(g_sp_lhave ? (g_sp_lmix != 0) : 1);
        } else if (g_sp_ui && ra >= (DWORD)g_sp_ui && ra < (DWORD)g_sp_ui + g_sp_uisize) {   /* Execute 0x10011bc5 */
            pend = InterlockedExchange(&g_sp_pend, -1);
            g_sp_set = (LONG)set;
            if (pend >= 0) g_sp_mix = pend != 0;
            if (prog & 0xff) { who = "City Properties"; pass = skin; }   /* in game: keep the skin, no re-skin */
            else { who = "New City"; pass = 0; }                      /* a new city: skin 0, the style grows */
        }
        logf("stylepick: SetCityScheme from %s (ret 0x%08lX): asked set %08lX, skin %08lX -> %08lX, style %s%s",
             who, ra, set, skin, pass, sp_name((DWORD)g_sp_set), g_sp_mix ? " + mix" : "");
    }
    r = ((char (__fastcall *)(void *, void *, DWORD, DWORD, DWORD, DWORD))g_sp_o_scs)(self, edx, land, flora, pass, prog);
    if (g_sp_on) sp_refresh(self, who);
    return r;
}

/* ---- GetCurrentBuildingSet, scheme vt+0x64: the City Properties dialog sees P ---- */
static char __fastcall sp_getcur(BYTE *self, void *edx, DWORD *out) {
    DWORD ra = (DWORD)_ReturnAddress();
    char r = ((char (__fastcall *)(void *, void *, DWORD *))g_sp_o_cur)(self, edx, out);
    if (g_sp_on && g_sp_ui && ra >= (DWORD)g_sp_ui + 0x5b6f4 && ra < (DWORD)g_sp_ui + 0x5b96d && out) {
        *out = (DWORD)g_sp_set;
        r = 1;
    }
    return r;
}

/* ---- save / load of P and M: record {0x0525A6B9, 0x4525A6E2, SP_INST} = magic, P, M ---- */
typedef char (__fastcall *SP_V1)(void *, void *, void *);
typedef char (__fastcall *SP_V2)(void *, void *, void *, void *);
static int sp_rec_read(void *seg, DWORD *v) {
    DWORD key[3] = { 0x0525A6B9, 0x4525A6E2, SP_INST };
    void *rec = NULL, *st = NULL;
    int ok = 0, i;
    if (!seg || IsBadReadPtr(seg, 4)) return 0;
    if (!((SP_V2)(*(DWORD **)seg)[0x20 / 4])(seg, NULL, key, &rec) || !rec) return 0;   /* as SIMINIT 0x10009e1f */
    if (((SP_V2)(*(DWORD **)rec)[0])(rec, NULL, (void *)0x199627, &st) && st) {
        for (ok = 1, i = 0; i < 3 && ok; i++) ok = ((SP_V1)(*(DWORD **)st)[0x38 / 4])(st, NULL, &v[i]) != 0;
        ((void (__fastcall *)(void *, void *))(*(DWORD **)st)[2])(st, NULL);
    }
    ((SP_V1)(*(DWORD **)seg)[0x24 / 4])(seg, NULL, &rec);
    return ok && v[0] == SP_MAGIC;
}
static int sp_rec_write(void *seg) {
    DWORD key[3] = { 0x0525A6B9, 0x4525A6E2, SP_INST }, v[3];
    void *rec = NULL, *st = NULL;
    int ok = 0, i;
    v[0] = SP_MAGIC; v[1] = (DWORD)g_sp_set; v[2] = (DWORD)g_sp_mix;
    if (!seg || IsBadReadPtr(seg, 4)) return 0;
    if (!((SP_V2)(*(DWORD **)seg)[0x30 / 4])(seg, NULL, key, &rec) || !rec) return 0;   /* as SIMCITY 0x10004ccd */
    if (((SP_V2)(*(DWORD **)rec)[0])(rec, NULL, (void *)0x199627, &st) && st) {
        for (ok = 1, i = 0; i < 3 && ok; i++)
            ok = ((char (__fastcall *)(void *, void *, DWORD))(*(DWORD **)st)[0x88 / 4])(st, NULL, v[i]) != 0;
        ((void (__fastcall *)(void *, void *))(*(DWORD **)st)[2])(st, NULL);
    }
    ((SP_V1)(*(DWORD **)seg)[0x24 / 4])(seg, NULL, &rec);
    return ok;
}
static char __fastcall sp_save(void *city, void *edx, void *seg) {       /* replaces the call at SIMCITY 0x10004458 */
    char r = ((SP_V1)g_sp_o_save)(city, edx, seg);
    if (g_sp_on) {
        int ok = sp_rec_write(seg);
        logf("stylepick: save: style %s%s %s (skin %08lX in the stock record)", sp_name((DWORD)g_sp_set),
             g_sp_mix ? " + mix" : "", ok ? "written" : "### NOT written", sp_skin());
    }
    return r;
}
static char __fastcall sp_load(void *cmd, void *edx, void *seg) {        /* replaces the call at SIMINIT 0x10008f9c */
    DWORD v[3] = { 0, 0, 0 };
    char r;
    g_sp_lhave = g_sp_on && sp_rec_read(seg, v);
    g_sp_lset = v[1]; g_sp_lmix = v[2];
    if (g_sp_on) logf("stylepick: load: %s", g_sp_lhave ? "the city has a saved style" : "no saved style (style = the city's set, mix on)");
    g_sp_loading = 1;
    r = ((SP_V1)g_sp_o_load)(cmd, edx, seg);
    g_sp_loading = 0;
    return r;
}

/* ---- exports for sc3resize (City Properties "Mix" box) ---- */
__declspec(dllexport) int sc3netmod_stylepick_state(DWORD *set, int *mix) {
    if (set) *set = (DWORD)g_sp_set;
    if (mix) *mix = g_sp_mix != 0;
    return g_sp_on;
}
__declspec(dllexport) void sc3netmod_stylepick_pending_mix(int mix) { g_sp_pend = mix ? 1 : 0; }

/* ---- arming ---- */
static int sp_vt_swap(DWORD *slot, void *to, DWORD want, DWORD *orig) {
    DWORD old;
    if (IsBadReadPtr(slot, 4) || *slot != want) return 0;
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) return 0;   /* left writable (memory project-mod-startup-races) */
    *orig = *slot;
    InterlockedExchange((volatile LONG *)slot, (LONG)to);
    return 1;
}
static DWORD WINAPI stylepick_thread(LPVOID param) {
    BYTE *geom, *city;
    DWORD a = 0, b = 0, c = 0, d = 0, e = 0;
    (void)param;
    g_sp_on = !env_off("SC3NETMOD_STYLEPICK");
    while (!(geom = (BYTE *)GetModuleHandleA("SIMGEOM.DLL")) || !(g_sp_init = (BYTE *)GetModuleHandleA("SIMINIT.DLL")) ||
           !(city = (BYTE *)GetModuleHandleA("SIMCITY.DLL")) || !(g_sp_ui = (BYTE *)GetModuleHandleA("SIMUI.DLL"))) Sleep(1);
    {   IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_sp_ui + ((IMAGE_DOS_HEADER *)g_sp_ui)->e_lfanew);
        g_sp_uisize = nt->OptionalHeader.SizeOfImage; }
    g_sp_o_parse = (DWORD)geom + 0x1250;                             /* set before the call can reach the thunk */
    a = retarget_call(geom, 0x1170, 0x1250, (void *)sp_parse);
    if (a) g_sp_filter = 1;
    if (!g_sp_on) {
        logf("stylepick: OFF (SC3NETMOD_STYLEPICK=0): stock re-skin; family filter %s (drops the North American copies only)",
             a ? "in" : "### NOT in, the shipped bytes differ");
        return 0;
    }
    g_sp_o_load = (DWORD)g_sp_init + 0x9e1f;                         /* set before the call can reach the thunk */
    g_sp_o_save = (DWORD)city + 0x4ccd;
    b = retarget_call(g_sp_init, 0x8f9c, 0x9e1f, (void *)sp_load);
    c = retarget_call(city, 0x4458, 0x4ccd, (void *)sp_save);
    d = sp_vt_swap((DWORD *)(g_sp_init + 0x2f528 + 0x64), (void *)sp_getcur, (DWORD)g_sp_init + 0x54a8, &g_sp_o_cur);
    e = sp_vt_swap((DWORD *)(g_sp_init + 0x2f528 + 0x18), (void *)sp_scs, (DWORD)g_sp_init + 0x6589, &g_sp_o_scs);
    if (!(a && b && c && d && e)) {
        /* undo what went in: all or nothing (the filter alone would grow one style without the dialog to change it) */
        if (e) InterlockedExchange((volatile LONG *)(g_sp_init + 0x2f528 + 0x18), (LONG)g_sp_o_scs);
        if (d) InterlockedExchange((volatile LONG *)(g_sp_init + 0x2f528 + 0x64), (LONG)g_sp_o_cur);
        if (c) write_rel(city + 0x4458, 0xE8, (void *)c, 5);
        if (b) write_rel(g_sp_init + 0x8f9c, 0xE8, (void *)b, 5);
        g_sp_on = 0;
        logf("### stylepick: hook sites do not match the shipped bytes (filter %d load %d save %d getcur %d scheme %d): "
             "STYLEPICK OFF, stock re-skin", !!a, !!b, !!c, !!d, !!e);
        return 0;
    }
    logf("stylepick: ON (SC4-like: the city's building style picks what grows, City Properties does not re-skin; "
         "SC3NETMOD_STYLEPICK=0 = stock). Hooks: SIMGEOM+0x1170 family parse, SIMINIT+0x8f9c load, SIMCITY+0x4458 save, "
         "scheme vt+0x18 / vt+0x64");
    for (;;) {                                                          /* stats, like the other blocks */
        LONG n0 = g_sp_nfilt;
        Sleep(30000);
        if (g_sp_nfilt != n0)
            logf("stylepick: stats: %ld family parse(s), %ld member(s) left out, %ld family(ies) kept whole; style %s%s, skin %08lX",
                 g_sp_nfilt, g_sp_ndrop, g_sp_nkeep_all, sp_name((DWORD)g_sp_set), g_sp_mix ? " + mix" : "", sp_skin());
    }
}
