/* ================= NATWORLD (child/terrpanel 2026-11-06): Classic Natural World terrain + water colours, switchable
 * Classic Natural World v1.0 (thronevintagetech, author's permission, re/analysis/COMMUNITY_MODS.md) replaces four
 * palette files. Owner call: make it switchable, one switch for terrain and water, in the terrain editor strip.
 * We do not replace any game file: re/tools/natworld_pack.py keeps only the colours in sc3natworld.bin beside this DLL,
 * and the colours are written over the game's palette tables after each stock load.
 *
 * Palette tables [static reads, cited]:
 *   holder = *(SIMDIRT 0x10024a28) (the dirt singleton, ctor 0x1001665c, which loads ids 0..8 through 0x100170b1).
 *   sc3_dirt_load_palette(holder, id) SIMDIRT 0x10016cce (thiscall, 1 arg): entry = *(holder + 0xc) + id * 8,
 *     { u8 loaded, u8, u16 rows - 1, u16 **rows }, each row = width u16 pixels (FUN_10012342: vt+0x3c rows,
 *     vt+0x38 width, vt+0xb4(x, y)). Images are decoded into a 16-bit buffer (colour type {4, 0x10}).
 *   id 4 = land palette: scheme manager (SIMDIRT 0x1001cb0f -> vt+0x80) vt+0x34(holder+0x28 landscape, &group,
 *     &instance) -> resource {group 0x455A72B1, instance 1..5}; ids 6 / 7 / 8 = palWater / palEdgeL / palEdgeD.bmp
 *     from Res\Dirt\palette\ (0x100121f6).
 *   landscape change FUN_10016c45: city vt+0x21c, vt+0x234, reload id 4, post message 0x45462fd2 through SIMDIRT
 *     0x10019a8b vt+0x10, city vt+0x220, vt+0x238. The switch repeats that sequence for ids 4, 6, 7, 8.
 * The 16-bit packing and row order are not read from the decoder: they are measured on the first stock load, by
 * comparing the table against the stock file on disk packed four ways (565 / 555, rows top-down / bottom-up). No match
 * of 98% or better = NATWORLD writes nothing (logged).
 * SC3RESIZE_NATWORLD=0: nothing installed. The switch is saved as sc3resize.ini [natworld] on=0|1. */

static int   g_natworld = 1;          /* feature present */
static int   g_nw_on;                 /* the switch */
static int   g_nw_fmt = -1;           /* measured: bit 0 = 555, bit 1 = rows bottom-up; -1 not yet, -2 no match */
static void *g_nw_orig_load;          /* trampoline of SIMDIRT 0x10016cce */
static HMODULE g_nw_dm;
typedef struct { int w, h; BYTE *rgb; } NW_PAL;
static NW_PAL g_nw[9];                /* slot 1..8, from sc3natworld.bin */

static void nw_ini(char *p, int cap) { ho_ini_path(p, cap); }

static int nw_load_data(void) {
    char p[MAX_PATH];
    FILE *f;
    BYTE hd[12];
    DWORD n, i, sl[3];
    int got = 0;
    rz_mb_path(p, sizeof(p), "sc3natworld.bin");
    f = fopen(p, "rb");
    if (!f) { logf("NATWORLD> %s missing: no Natural World switch", p); return 0; }
    if (fread(hd, 1, 12, f) != 12 || memcmp(hd, "SC3NW1\0\0", 8)) { fclose(f); logf("NATWORLD> sc3natworld.bin: bad header"); return 0; }
    n = *(DWORD *)(hd + 8);
    for (i = 0; i < n && i < 16; i++) {
        BYTE *px;
        if (fread(sl, 4, 3, f) != 3 || sl[0] < 1 || sl[0] > 8 || sl[1] < 1 || sl[1] > 64 || sl[2] < 1 || sl[2] > 1024) break;
        px = (BYTE *)malloc(sl[1] * sl[2] * 3);
        if (!px || fread(px, 3, sl[1] * sl[2], f) != sl[1] * sl[2]) { free(px); break; }
        g_nw[sl[0]].w = (int)sl[1]; g_nw[sl[0]].h = (int)sl[2]; g_nw[sl[0]].rgb = px;
        got++;
    }
    fclose(f);
    logf("NATWORLD> sc3natworld.bin: %d of %lu palettes read", got, n);
    return got == 8;
}

/* a 24-bit BMP from memory -> RGB top-down (malloc'd), 0 if not one */
static BYTE *nw_bmp(const BYTE *b, DWORD len, int *w, int *h) {
    LONG ww, hh;
    DWORD off, stride, y, x;
    BYTE *o;
    int flip;
    if (len < 54 || b[0] != 'B' || b[1] != 'M' || *(WORD *)(b + 28) != 24 || *(DWORD *)(b + 30) != 0) return NULL;
    off = *(DWORD *)(b + 10); ww = *(LONG *)(b + 18); hh = *(LONG *)(b + 22);
    flip = hh > 0; if (hh < 0) hh = -hh;
    if (ww < 1 || ww > 64 || hh < 1 || hh > 1024) return NULL;
    stride = ((DWORD)ww * 3 + 3) & ~3u;
    if (off + stride * (DWORD)hh > len) return NULL;
    o = (BYTE *)malloc((size_t)ww * hh * 3);
    if (!o) return NULL;
    for (y = 0; y < (DWORD)hh; y++) {
        const BYTE *row = b + off + (flip ? (DWORD)hh - 1 - y : y) * stride;
        for (x = 0; x < (DWORD)ww; x++) {
            o[(y * ww + x) * 3] = row[x * 3 + 2]; o[(y * ww + x) * 3 + 1] = row[x * 3 + 1]; o[(y * ww + x) * 3 + 2] = row[x * 3];
        }
    }
    *w = (int)ww; *h = (int)hh;
    return o;
}

static BYTE *nw_read_file(const char *p, DWORD *len) {
    FILE *f = fopen(p, "rb");
    BYTE *b;
    long n;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
    b = n > 0 && n < 8 * 1024 * 1024 ? (BYTE *)malloc(n) : NULL;
    if (b && fread(b, 1, n, f) != (size_t)n) { free(b); b = NULL; }
    fclose(f);
    *len = (DWORD)n;
    return b;
}

/* the stock palette for a slot, from the player's own files: Apps\Res\Dirt\Palette */
static BYTE *nw_stock(int slot, int *w, int *h) {
    char p[MAX_PATH], *s;
    static const char *names[9] = { 0, 0, 0, 0, 0, 0, "PALWATER.BMP", "PALEDGEL.BMP", "PALEDGED.BMP" };
    BYTE *b, *o = NULL;
    DWORD len, i;
    GetModuleFileNameA(NULL, p, sizeof(p));
    s = strrchr(p, '\\'); if (!s) return NULL;
    s[1] = 0;
    strcat(p, "Res\\Dirt\\Palette\\");
    strcat(p, slot >= 6 ? names[slot] : "455A72B1_LandPalettes.IXF");
    b = nw_read_file(p, &len);
    if (!b) return NULL;
    if (slot >= 6) o = nw_bmp(b, len, w, h);
    else if (len > 24 && *(DWORD *)b == 0x80C381D7) {
        for (i = 4; i + 20 <= len; i += 20) {   /* IXF index: group, instance, type, offset, size; zero record ends it */
            DWORD *r = (DWORD *)(b + i);
            if (!r[0] && !r[1] && !r[2]) break;
            if (r[0] == 0x455A72B1 && r[1] == (DWORD)slot && r[3] + r[4] <= len) { o = nw_bmp(b + r[3], r[4], w, h); break; }
        }
    }
    free(b);
    return o;
}

static WORD nw_pack(const BYTE *c, int fmt) {
    return (fmt & 1) ? (WORD)(((c[0] >> 3) << 10) | ((c[1] >> 3) << 5) | (c[2] >> 3))
                     : (WORD)(((c[0] >> 3) << 11) | ((c[1] >> 2) << 5) | (c[2] >> 3));
}

static BYTE *nw_entry(void *holder, int id) {
    BYTE *t;
    if (!holder || IsBadReadPtr(holder, 0x2c)) return NULL;
    t = *(BYTE **)((BYTE *)holder + 0xc);
    if (!t || IsBadReadPtr(t + id * 8, 8) || !t[id * 8]) return NULL;
    return t + id * 8;
}

/* compare the loaded table with a packing of rgb; returns matching pixels in per mille */
static int nw_match(BYTE *e, const BYTE *rgb, int w, int h, int fmt) {
    WORD **rows = *(WORD ***)(e + 4);
    int y, x, ok = 0;
    if ((int)*(WORD *)(e + 2) + 1 != h || !rows || IsBadReadPtr(rows, h * 4)) return -1;
    for (y = 0; y < h; y++) {
        const WORD *r = rows[(fmt & 2) ? h - 1 - y : y];
        if (!r || IsBadReadPtr(r, w * 2)) return -1;
        for (x = 0; x < w; x++) ok += r[x] == nw_pack(rgb + (y * w + x) * 3, fmt);
    }
    return (int)((LONGLONG)ok * 1000 / (w * h));
}

static int nw_land_slot(void *holder) {
    void *m;
    DWORD grp = 0, inst = 0;
    m = ((void *(__cdecl *)(void))((BYTE *)g_nw_dm + 0x1cb0f))();
    m = m ? (void *)ho_v(m, 0x80, 0, 0, 0, 0, 0, 0) : NULL;
    if (!m || !(ho_v(m, 0x34, 3, *(DWORD *)((BYTE *)holder + 0x28), (DWORD)&grp, (DWORD)&inst, 0, 0) & 0xff)) return 0;
    return grp == 0x455A72B1 && inst >= 1 && inst <= 5 ? (int)inst : 0;
}

/* after a stock load of id: measure the packing once, then write our colours when the switch is on */
static void nw_after_load(void *holder, int id) {
    BYTE *e = nw_entry(holder, id), *st;
    int slot = id == 4 ? nw_land_slot(holder) : id >= 6 && id <= 8 ? id : 0, w, h, fmt, best = -1, bf = -1, y, x;
    WORD **rows;
    if (!e || !slot || !g_nw[slot].rgb) return;
    if (g_nw_fmt == -1) {
        st = nw_stock(slot, &w, &h);
        if (!st) { logf("NATWORLD> stock palette slot %d not readable from disk", slot); return; }
        for (fmt = 0; fmt < 4; fmt++) { int m = nw_match(e, st, w, h, fmt); if (m > best) { best = m; bf = fmt; } }
        free(st);
        g_nw_fmt = best >= 980 ? bf : -2;
        logf("NATWORLD> table vs stock file (slot %d): best %d.%d%% as %s, rows %s -> %s", slot, best / 10, best % 10,
             bf & 1 ? "555" : "565", bf & 2 ? "bottom-up" : "top-down", g_nw_fmt >= 0 ? "colours can be written" : "NO MATCH, off");
    }
    if (!g_nw_on || g_nw_fmt < 0) return;
    w = g_nw[slot].w; h = g_nw[slot].h;
    rows = *(WORD ***)(e + 4);
    if ((int)*(WORD *)(e + 2) + 1 != h || !rows) { logf("NATWORLD> id %d: table has %d rows, ours %d: not written", id, *(WORD *)(e + 2) + 1, h); return; }
    for (y = 0; y < h; y++) {
        WORD *r = rows[(g_nw_fmt & 2) ? h - 1 - y : y];
        if (!r || IsBadWritePtr(r, w * 2)) return;
        for (x = 0; x < w; x++) r[x] = nw_pack(g_nw[slot].rgb + (y * w + x) * 3, g_nw_fmt);
    }
    logf("NATWORLD> palette %d written (%s %d, %dx%d)", id, id == 4 ? "landscape" : "file slot", slot, w, h);
}

static void __fastcall nw_load_detour(void *self, void *edx, DWORD id) {
    DWORD a[1];
    (void)edx;
    a[0] = id;
    rz_thiscall_ret(self, g_nw_orig_load, a, 1);
    __try { nw_after_load(self, (int)(id & 0xff)); } __except (EXCEPTION_EXECUTE_HANDLER) { logf("NATWORLD> fault after loading palette %lu", id & 0xff); }
}

/* the switch: reload ids 4, 6, 7, 8 the way a landscape change does (FUN_10016c45) */
static void nw_set(int on) {
    char p[MAX_PATH];
    void *holder, *city, *ms;
    DWORD m[4] = { 0x45462fd2, 0, 0, 0 };
    static const int ids[4] = { 4, 6, 7, 8 };
    int i;
    g_nw_on = on;
    nw_ini(p, sizeof(p));
    WritePrivateProfileStringA("natworld", "on", on ? "1" : "0", p);
    if (!g_nw_dm || !g_nw_orig_load) return;
    holder = *(void **)((BYTE *)g_nw_dm + 0x24a28);
    if (!holder) return;
    city = sf_city();
    ms = ((void *(__cdecl *)(void))((BYTE *)g_nw_dm + 0x19a8b))();
    if (city) { ho_v(city, 0x21c, 0, 0, 0, 0, 0, 0); ho_v(city, 0x234, 0, 0, 0, 0, 0, 0); }
    for (i = 0; i < 4; i++) nw_load_detour(holder, NULL, (DWORD)ids[i]);
    if (ms) ho_v(ms, 0x10, 2, (DWORD)m, 0, 0, 0, 0);
    if (city) { ho_v(city, 0x220, 0, 0, 0, 0, 0, 0); ho_v(city, 0x238, 0, 0, 0, 0, 0, 0); }
    logf("NATWORLD> switch %s: palettes 4, 6, 7, 8 reloaded, refresh posted", on ? "ON (Natural World)" : "OFF (stock)");
}

static void nw_install(void) {
    char p[MAX_PATH];
    BYTE *fn, ex[5];
    HMODULE dm = GetModuleHandleA("SIMDIRT.DLL");
    if (!g_natworld) { logf("NATWORLD> off (SC3RESIZE_NATWORLD=0)"); return; }
    if (!dm) { logf("NATWORLD> SIMDIRT.DLL not loaded: off"); return; }
    if (!nw_load_data()) return;
    fn = (BYTE *)dm + 0x16cce;
    if (fn[0] != 0xB8 || fn[5] != 0xE8) { logf("NATWORLD> SIMDIRT 0x10016cce differs from shipped: off"); return; }
    memcpy(ex, fn, 5);                         /* mov eax, <EH handler>; the call to _EH_prolog after it stays in place */
    g_nw_dm = dm;
    nw_ini(p, sizeof(p));
    g_nw_on = GetPrivateProfileIntA("natworld", "on", 0, p) != 0;
    ho_hook(dm, 0x16cce, ex, 5, (void *)nw_load_detour, &g_nw_orig_load, "SIMDIRT palette load 0x10016cce");
    if (!g_nw_orig_load) return;
    logf("NATWORLD> on: switch %s", g_nw_on ? "ON" : "off");
    {   void *holder = *(void **)((BYTE *)dm + 0x24a28);   /* palettes already loaded at startup: measure / apply now */
        if (holder) __try { nw_after_load(holder, 6); if (g_nw_on) { nw_after_load(holder, 4); nw_after_load(holder, 7); nw_after_load(holder, 8); } }
                    __except (EXCEPTION_EXECUTE_HANDLER) { logf("NATWORLD> fault on the startup pass"); } }
}
