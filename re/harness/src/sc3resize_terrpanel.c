/* ================= TERRPANEL (child/terrpanel 2026-11-06): a taller terrain editor panel with room for more options
 * Owner (2026-11-06): forest fill from the Civic Deals mod "also as an option in the terraformer at the beginning of
 * the game as a tick (we might need to rework that side panel to allow for more option and more customization)",
 * then "do a taller panel". Plan: re/analysis/COMMUNITY_MODS.md.
 *
 * The panel [static reads, cited]:
 *   window-proc vtable SIMUI 0x100aaae0 (Linux name cSC3WinProcTerrEdit), slot +0xc DoWinMsg 0x1005f352
 *     (5 args, ret 0x14). Message 0xa2bf8ace builds the controls (0x1005f621), message 3 with p3 1 is a button click
 *     (0x100607ab) [CONFIRMED @ SIMUI 0x1005f352].
 *   the window is 172 x 480 from image 2 of 22DEC90F_TerrEdit.ixf, docked right and centred vertically
 *     [CONFIRMED @ SIMUI 0x1005f44c]. sc3resize's dock (rz_dialogs_poll) knows it by width 172 and height >= 400 and
 *     centres it by its real height, so the width stays 172 and only the height grows.
 *   controls: all ids 0x72e867a1..b2, Accept at y 0x1a6, Re-Generate 0x72e867a2 posts message 0x2f2ee63.
 * What this adds, after the stock build: the window grows by TP_STRIP_H, a framed panel (the MODSUI recipe) fills the
 * new strip, and on it a heading and a "Bosque denso" checkbox.
 *
 * Forest fill [static reads]:
 *   terrain = city vt+0x13c (vtable SIMDIRT 0x1002046c), slot +0x90 InitFloraLevel(x, y, level) 0x100064a0: with no
 *     generation grid (+0x44 == 0) and level > 0x1f it calls city vt+0x148 FloraLayer, slot +0x6c with
 *     (x << 8, y << 8, 0) and density level >> 5 [CONFIRMED @ SIMDIRT 0x100064a0, SIMCITY 0x10002b56].
 *   the iOS named build calls that slot goFloraLayer::SetFloraDensity: it replaces a tree already there and plants
 *     nothing on water [iOS-HINT @ 0x00206964].
 *   cells: terrain vt+0xb0 / +0xb4 = vertex rows / cols, so rows - 1 by cols - 1 cells (the loop shape of the
 *     regenerate handler SIMDIRT 0x10005500).
 * When it runs: ticking the box fills the current terrain at once. While it is ticked, every Re-Generate fills the new
 * terrain too: the terrain's message handler (vtable slot SIMDIRT 0x1002046c + 0xc = 0x10005500, the only reference
 * to that function) is wrapped and the fill runs after it has handled 0x2f2ee63. Unticking takes effect at the next
 * Re-Generate (trees already planted stay).
 * SC3RESIZE_TERRPANEL=0: nothing installed (stock panel). SC3RESIZE_TERRPANEL_LOG=1: every message 3 the panel gets. */

static int   g_terrpanel = 1, g_tp_log = 0;
static void *g_orig_f352;          /* trampoline of SIMUI DoWinMsg 0x1005f352 */
static DWORD g_tp_orig_dirtmsg;    /* SIMDIRT 0x10005500 */
static HMODULE g_tp_dirt;
static int   g_tp_forest;          /* the box is ticked */
static void *g_tp_win;             /* the panel the box belongs to */

#define TP_STRIP_H   82
#define TP_PANEL     0x02F95D00
#define TP_HDR       0x02F95D01
#define TP_FOREST    0x02F95D02
#define TP_W         172
#define TP_BACK      0x02F95D03
#define TP_NATWORLD  0x02F95D04

static void *tp_terrain(void) {
    void *city = sf_city(), *t;
    if (!city || !g_tp_dirt) return NULL;
    t = (void *)ho_v(city, 0x13c, 0, 0, 0, 0, 0, 0);
    if (!t || IsBadReadPtr(t, 0x48) || *(DWORD *)t != (DWORD)g_tp_dirt + 0x2046c) return NULL;
    return t;
}

typedef BYTE (__fastcall *TP_INITFLORA)(void *self, void *edx, DWORD x, DWORD y, DWORD level);

/* TREEBAR (owner 2026-11-08: "bosque denso enabled should also depend on the tree bar"). The panel's three sliders are
   0x72e867ad / ae / af, left to right under the hills / water / tree icons of image 2 of 22DEC90F_TerrEdit.ixf (decoded
   2026-11-08). DoWinMsg stores their values (0..0xff, range set at build) in the window proc's bytes +0x12 / +0x13 /
   +0x14 on message 3 p3 0xc [CONFIRMED @ SIMUI 0x1005f352]; getters vt+0x1c / +0x20 / +0x24 return those bytes
   (0x1005f615, 0x1005f619, 0x100052ec). Re-Generate packs them into msg[1] as (af >> 1) << 16 | (ae >> 1) << 8 | ad >> 1
   [CONFIRMED @ SIMUI 0x10060ab2], so the tree value of a regenerate is ((msg[1] >> 16) & 0x7f) << 1.
   InitFloraLevel plants only levels above 0x1f, at density level >> 5 (1..7): the bar maps 0..0xff onto 0x20..0xff,
   so the tick always plants something and the bar picks how dense. SC3RESIZE_TP_TREEBAR=0: always 0xff, as before. */
static int   g_tp_treebar = 1;
static BYTE *g_tp_proc;            /* the terrain panel's window proc (DoWinMsg this), for the slider bytes */
#define TP_TREES_SLIDER 0x72e867af

static DWORD tp_level(int trees) {   /* trees 0..0xff, -1 = unknown */
    if (!g_tp_treebar || trees < 0) return 0xff;
    return 0x20 + (DWORD)trees * (0xff - 0x20) / 0xff;
}
static int tp_trees_now(void) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    if (!g_tp_proc || !sui || IsBadReadPtr(g_tp_proc, 0x18) || *(DWORD *)g_tp_proc != (DWORD)sui + 0xaaae0) return -1;
    return g_tp_proc[0x14];
}

/* FILLSLICE (owner 2026-11-08, 1024 map: "it froze the game for a few seconds"; his log: 1,048,576 cells, 2157 ms in
   one call on the UI thread). The fill now runs in slices of about TP_SLICE_MS from a ONE-SHOT thread timer
   (SetTimer(NULL), dispatched on the game thread, the RELOCATE / PICKER pattern), re-armed TP_GAP_MS after each slice
   ends, so the game draws between slices. Measured on LIVING-PC, 1024 map, 1,048,576 cells (~3.6 s of planting here):
   - a periodic 10 ms timer: due again after every slice, the game drew 0 fps for the whole 3.7 s;
   - one slice per frame posted from the frame hook (fnlog_enter idx 0): that hook ran only ~3 times a second on this
     screen, 58 s in total;
   - one-shot 40 ms slices, 20 ms gap: 15.4 s in total for 5.7 s of planting (the gap is timer resolution + a frame).
   A new start (tick, Re-Generate, tree bar moved) restarts it from row 0. Accept finishes what is left at once before
   the stock handler, so the city never starts half filled. The terrain or the city changing stops it.
   SC3RESIZE_TP_SLICE=0: the old single-call fill. */
static int   g_tp_slice = 1;
#define TP_SLICE_MS 50
#define TP_GAP_MS   10
static struct { void *t, *city; int rows, cols, x, n, slices; DWORD level, t0, busy_ms; UINT_PTR timer; } g_tpf;

/* rows from g_tpf.x until done or the deadline (0 = no deadline); 1 = finished or stopped */
static int tp_fill_rows(DWORD deadline) {
    TP_INITFLORA fn;
    int y, done = 0;
    DWORD s0 = GetTickCount();
    if (!g_tpf.t) return 1;
    if (tp_terrain() != g_tpf.t || sf_city() != g_tpf.city) {
        logf("TERRPANEL> forest fill stopped at row %d of %d: the terrain changed", g_tpf.x, g_tpf.rows - 1);
        g_tpf.t = NULL;
        return 1;
    }
    __try {
        fn = (TP_INITFLORA)(*(DWORD **)g_tpf.t)[0x90 / 4];
        while (g_tpf.x < g_tpf.rows - 1) {
            for (y = 0; y < g_tpf.cols - 1; y++)
                if (fn(g_tpf.t, NULL, (DWORD)g_tpf.x, (DWORD)y, g_tpf.level) & 0xff) g_tpf.n++;
            g_tpf.x++;
            if (deadline && (LONG)(GetTickCount() - deadline) >= 0) break;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        logf("TERRPANEL> forest fill: fault at row %d after %d cells, stopped", g_tpf.x, g_tpf.n);
        g_tpf.t = NULL;
        return 1;
    }
    g_tpf.slices++;
    g_tpf.busy_ms += GetTickCount() - s0;
    if (g_tpf.x >= g_tpf.rows - 1) {
        logf("TERRPANEL> forest fill: %d of %d cells planted at level 0x%02lx (density %lu), %d slice(s), %lu ms busy, %lu ms total",
             g_tpf.n, (g_tpf.rows - 1) * (g_tpf.cols - 1), g_tpf.level, g_tpf.level >> 5, g_tpf.slices, g_tpf.busy_ms,
             GetTickCount() - g_tpf.t0);
        g_tpf.t = NULL;
        done = 1;
    }
    return done;
}

/* one slice, then the timer again TP_GAP_MS after it ended (a periodic timer is already due when a slice ends) */
static void CALLBACK tp_fill_timer(HWND h, UINT m, UINT_PTR id, DWORD tm) {
    (void)h; (void)m; (void)tm;
    KillTimer(NULL, id);
    if (g_tpf.timer == id) g_tpf.timer = 0;
    if (g_tpf.t && !tp_fill_rows(GetTickCount() + TP_SLICE_MS) && !g_tpf.timer) {
        g_tpf.timer = SetTimer(NULL, 0, TP_GAP_MS, tp_fill_timer);
        if (!g_tpf.timer) { logf("TERRPANEL> SetTimer failed: filling the rest now"); tp_fill_rows(0); }
    }
}

/* start (or restart) a fill of terrain t (NULL = the current one) at a tree value 0..0xff (-1 = unknown) */
static void tp_fill(void *t, int trees) {
    int rows, cols;
    if (!t) t = tp_terrain();
    if (!t) { logf("TERRPANEL> forest fill: no terrain"); return; }
    __try {
        rows = (int)ho_v(t, 0xb0, 0, 0, 0, 0, 0, 0);
        cols = (int)ho_v(t, 0xb4, 0, 0, 0, 0, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("TERRPANEL> forest fill: fault reading the size"); return; }
    if (rows < 2 || cols < 2 || rows > 4097 || cols > 4097) { logf("TERRPANEL> forest fill: odd size %d x %d", rows, cols); return; }
    g_tpf.t = t; g_tpf.city = sf_city(); g_tpf.rows = rows; g_tpf.cols = cols;
    g_tpf.x = 0; g_tpf.n = 0; g_tpf.slices = 0; g_tpf.busy_ms = 0; g_tpf.t0 = GetTickCount();
    g_tpf.level = tp_level(trees);
    logf("TERRPANEL> forest fill started: %d x %d cells, tree bar %d -> level 0x%02lx (density %lu)%s", rows - 1, cols - 1,
         trees, g_tpf.level, g_tpf.level >> 5, g_tp_slice ? ", in slices" : "");
    if (!g_tp_slice) { tp_fill_rows(0); return; }
    if (!tp_fill_rows(GetTickCount() + TP_SLICE_MS) && !g_tpf.timer) {
        g_tpf.timer = SetTimer(NULL, 0, TP_GAP_MS, tp_fill_timer);
        if (!g_tpf.timer) { logf("TERRPANEL> SetTimer failed: filling the rest now"); tp_fill_rows(0); }
    }
}

/* Accept: plant what is left before the city starts */
static void tp_fill_finish(void) {
    if (!g_tpf.t) return;
    logf("TERRPANEL> Accept during the fill: planting the last %d rows now", g_tpf.rows - 1 - g_tpf.x);
    tp_fill_rows(0);
}

/* after the stock handler: a regenerated terrain gets the forest when the box is ticked */
static DWORD __fastcall tp_dirt_msg(void *self, void *edx, DWORD *msg) {
    DWORD a[1], r;
    (void)edx;
    a[0] = (DWORD)msg;
    r = rz_thiscall_ret(self, (void *)g_tp_orig_dirtmsg, a, 1);
    if (g_tp_forest && msg && !IsBadReadPtr(msg, 8) && msg[0] == 0x2f2ee63) tp_fill(self, (int)(((msg[1] >> 16) & 0x7f) << 1));
    return r;
}

/* a flat framed rectangle, the MODSUI mp_panel recipe with the colour as a parameter */
static int tp_rect(void *fac, void *win, DWORD id, int x, int y, int w, int h, DWORD colid) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void **svc, *obj = NULL, *pw;
    LONG r[4];
    int ok;
    svc = (void **)((MP_GETSVC)((BYTE *)sui + 0x8489d))();
    if (!svc || IsBadReadPtr(svc, 4)) return 0;
    if (!(ho_v(svc, 0x0c, 3, 0x4303e5b6, 0xe303e5ae, (DWORD)&obj, 0, 0) & 0xff) || !obj) return 0;
    ho_v(obj, 0x0c, 1, 0x22, 0, 0, 0, 0);
    ho_v(obj, 0x14, 1, ho_v(fac, 0x80, 2, colid, 0, 0, 0, 0), 0, 0, 0, 0);
    r[0] = 0; r[1] = 0; r[2] = w; r[3] = h;
    pw = (void *)ho_v(obj, 0x38, 0, 0, 0, 0, 0, 0);
    ho_v(pw, 0xc4, 1, (DWORD)r, 0, 0, 0, 0);
    ho_v(pw, 0xec, 1, id, 0, 0, 0, 0);
    ho_v(pw, 0xf4, 2, 0x800, 0, 0, 0, 0);
    ho_v(pw, 0xcc, 2, (DWORD)x, (DWORD)y, 0, 0, 0);
    pw = (void *)ho_v(obj, 0x38, 0, 0, 0, 0, 0, 0);
    ok = (int)(ho_v(win, 0x34, 1, (DWORD)pw, 0, 0, 0, 0) & 0xff);
    ho_v(obj, 0x08, 0, 0, 0, 0, 0, 0);
    return ok;
}

/* The six tool buttons are built at x 0x1c / 0x47 / 0x72, rows y 0x156 / 0x17e [CONFIRMED @ SIMUI 0x1005f621], but
   the circles printed in the background art (image 2 of 22DEC90F_TerrEdit.ixf) are 41 px apart, not 43, and 1 px
   higher. Measured by matching each stock button against the decoded art: the art circle sits at the button + (3, -1),
   (1, -1), (-1, -1) for the three columns, the same on both rows (verify/terrpanel/RESULTS.md). Stock shows a ring of
   the printed circle around each button. Each button is moved onto its circle, only if it is still at the stock spot. */
static void tp_align_tools(void *win) {
    static const DWORD ids[6] = { 0x72e867a7, 0x72e867a8, 0x72e867a9, 0x72e867aa, 0x72e867ab, 0x72e867ac };
    static const LONG sx[3] = { 0x1c, 0x47, 0x72 }, dx[3] = { 3, 1, -1 }, sy[2] = { 0x156, 0x17e };
    LONG *pr = (LONG *)((BYTE *)win + 0x14);
    int i, n = 0;
    for (i = 0; i < 6; i++) {
        void *c = mp_child(win, ids[i]);
        LONG *r;
        if (!c || IsBadReadPtr(c, 0x24)) continue;
        r = (LONG *)((BYTE *)c + 0x14);
        /* +0x14 holds screen coords (measured: 656 = panel 628 + 0x1c); SetPos +0xcc takes parent-local ones */
        if (r[0] - pr[0] != sx[i % 3] || r[1] - pr[1] != sy[i / 3]) continue;
        ho_v(c, 0xcc, 2, (DWORD)(sx[i % 3] + dx[i % 3]), (DWORD)(sy[i / 3] - 1), 0, 0, 0);
        n++;
    }
    logf("TERRPANEL> %d of 6 tool buttons moved onto their printed circles", n);
}

static void tp_build(void *win) {
    void *fac;
    LONG *r;
    int es = ho_spanish(), ok = 0, w, h;
    DWORD col;
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    if (!sui || !win || IsBadReadPtr(win, 0xa4)) return;
    r = (LONG *)((BYTE *)win + 0x14);
    w = r[2] - r[0]; h = r[3] - r[1];
    logf("TERRPANEL> build message: panel 0x%p [%ld %ld %ld %ld]", win, r[0], r[1], r[2], r[3]);
    if (w != TP_W || h < 400 || h > 600) { logf("TERRPANEL> panel is %d x %d, not the stock 172 x 480: left as is", w, h); return; }
    if (ho_v(win, 0x78, 1, TP_FOREST, 0, 0, 0, 0)) return;   /* already ours */
    fac = ((void *(__cdecl *)(void))((BYTE *)sui + 0x85065))();
    if (!fac || IsBadReadPtr(fac, 4)) return;
    ho_v(win, 0xc0, 2, (DWORD)w, (DWORD)(h + TP_STRIP_H), 0, 0, 0);          /* SetSize, as CreateTerrEditWin does */
    ho_v(win, 0xcc, 2, (DWORD)r[0], (DWORD)(r[1] > TP_STRIP_H / 2 ? r[1] - TP_STRIP_H / 2 : 0), 0, 0, 0);   /* keep it centred */
    tp_align_tools(win);
    logf("TERRPANEL> grown, adding the strip");
    /* the background bitmap is stretched to the window (tBGBltType 1 at +0xc0, GZPaint SIMUI 0x1002cb73: 0 = plain
       blit, 1 = stretch, 2 = 9-slice): blit it at its own 480 rows instead, and paint the new strip ourselves */
    if (*(DWORD *)win == (DWORD)sui + 0xa4d64 && *(DWORD *)((BYTE *)win + 0xc0) == 1) *(DWORD *)((BYTE *)win + 0xc0) = 0;
    else logf("TERRPANEL> background mode not the stock stretch (vt 0x%08lx, mode %lu): left as is",
              *(DWORD *)win - (DWORD)sui, *(DWORD *)((BYTE *)win + 0xc0));
    ok += tp_rect(fac, win, TP_BACK, 0, h, w, TP_STRIP_H, 0x62e56a2b);
    ok += tp_rect(fac, win, TP_PANEL, 8, h + 2, w - 16, TP_STRIP_H - 10, 0x62e56a2c);
    g_ho_lblcol = 1;
    ok += ho_add_label(fac, win, TP_HDR, SC3TR(es, "resize.tp_more", "M\xe1s opciones:", "More options:"), 16, h + 6, w - 32);
    g_ho_lblcol = 0;
    col = ho_v(fac, 0x80, 1, 0x62e56a2e, 0, 0, 0, 0);
    ok += mp_checkbox(fac, win, TP_FOREST, SC3TR(es, "resize.tp_forest", "Bosque denso", "Dense forest"), g_tp_forest, 16, h + 26, w - 32, col);
    if (g_nw_orig_load)   /* NATWORLD: only when sc3natworld.bin was read and the palette hook is in */
        ok += mp_checkbox(fac, win, TP_NATWORLD, SC3TR(es, "resize.tp_natworld", "Natural World", "Natural World"), g_nw_on, 16, h + 46, w - 32, col);
    g_tp_win = win;
    logf("TERRPANEL> panel %d x %d -> %d x %d, %d controls added, forest %s", w, h, w, h + TP_STRIP_H, ok, g_tp_forest ? "on" : "off");
}

static DWORD __fastcall tp_msg(void *self, void *edx, DWORD win, DWORD msg, DWORD p3, DWORD p4, DWORD p5) {
    DWORD a[5], r;
    (void)edx;
    if (g_tp_log && msg == 3) logf("TERRPANEL> msg 3 p3 0x%lx p4 0x%08lx p5 0x%lx", p3, p4, p5);
    g_tp_proc = (BYTE *)self;
    if (msg == 3 && p3 == 1 && p4 == 0x72e867a1) tp_fill_finish();   /* Accept: no half-filled city */
    a[0] = win; a[1] = msg; a[2] = p3; a[3] = p4; a[4] = p5;
    r = rz_thiscall_ret(self, g_orig_f352, a, 5);
    if (msg == 0xa2bf8ace && (r & 0xff) && win) tp_build((void *)win);
    else if (msg == 3 && p3 == 0xc && p4 == TP_TREES_SLIDER && g_tp_forest && g_tp_treebar) {
        /* tree bar moved with the box ticked: refill at the new density (the stock byte is stored by now) */
        int tr = tp_trees_now();
        if (tr >= 0 && tp_level(tr) >> 5 != g_tpf.level >> 5) tp_fill(NULL, tr);   /* only when the density step changes */
    }
    else if (msg == 3 && p4 == TP_FOREST && win) {   /* our box: read its state after the stock handling */
        int v = pp_read_box((void *)win, TP_FOREST);
        if (v >= 0 && v != g_tp_forest) {
            g_tp_forest = v;
            logf("TERRPANEL> forest %s", v ? "ticked: filling now and after every Re-Generate" : "unticked: from the next Re-Generate");
            if (v) tp_fill(NULL, tp_trees_now());
            else if (g_tpf.t) { logf("TERRPANEL> forest fill stopped at row %d (unticked)", g_tpf.x); g_tpf.t = NULL; }
        }
        r = 1;
    } else if (msg == 3 && p4 == TP_NATWORLD && win) {
        int v = pp_read_box((void *)win, TP_NATWORLD);
        if (v >= 0 && v != g_nw_on) nw_set(v);
        r = 1;
    }
    return r;
}

static void tp_install(HMODULE sui) {
    static const BYTE ef352[6] = { 0x55, 0x8b, 0xec, 0x56, 0x8b, 0xf1 };   /* push ebp; mov ebp,esp; push esi; mov esi,ecx */
    HMODULE dm = GetModuleHandleA("SIMDIRT.DLL");
    DWORD *slot, old;
    if (!g_terrpanel) { logf("TERRPANEL> off (SC3RESIZE_TERRPANEL=0): stock terrain panel"); return; }
    if (*(DWORD *)((BYTE *)sui + 0xaaae0 + 0xc) != (DWORD)sui + 0x5f352) { logf("TERRPANEL> SIMUI terrain vtable differs from shipped: off"); return; }
    if (dm) {
        slot = (DWORD *)((BYTE *)dm + 0x20478);   /* terrain vtable 0x1002046c + 0xc */
        if (*slot == (DWORD)dm + 0x5500 && *(DWORD *)((BYTE *)dm + 0x2046c + 0x90) == (DWORD)dm + 0x64a0 &&
            VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) {
            g_tp_dirt = dm;
            g_tp_orig_dirtmsg = *slot;
            *slot = (DWORD)tp_dirt_msg;
        } else logf("TERRPANEL> SIMDIRT terrain vtable differs from shipped: no forest fill");
    } else logf("TERRPANEL> SIMDIRT.DLL not loaded yet: no forest fill");
    nw_install();   /* NATWORLD: palette hook, before the panel so the strip knows whether to offer the switch */
    if (g_tp_dirt) ho_hook(sui, 0x5f352, ef352, 6, (void *)tp_msg, &g_orig_f352, "Terrain panel messages FUN_1005f352");
    logf("TERRPANEL> %s", g_orig_f352 ? "on: taller terrain panel with \"Bosque denso\"" : "NOT installed");
}
