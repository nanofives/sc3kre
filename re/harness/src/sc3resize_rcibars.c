/* ======================================================================================================== RCIBARS
 * (child rcibars 2026-11-02, owner: "can we modify the RCI to include Agricultural, Ports and Airports?", owner pick:
 * Aeropuerto + Puerto now, agriculture after research). #included by sc3resize.c after the GRAPHNEW block.
 * Evidence: re/sessions/STATUS_rcibars.md, re/analysis/PORTS_AIRPORTS.md.
 *
 * Airports and seaports have no demand of their own. They add supply to the "connection capacity" valves 5001
 * (commercial) / 8001 (industrial), and the month end turns their usage into the CAP byte (+0x3c, getter vt+0x70) of the
 * demand valves 5000 / 8000: 0 when demand is 0, 100 when supply < demand, else demand * 100 / supply
 * [CONFIRMED @ SIMRCI 0x1000ee50, 0x10016061]. The demand bar's ceiling is max - max * cap / 100, and the City Planner
 * warns above 75 (COMMERCIAL_CAP_PROBLEM / INDUSTRIAL_CAP_PROBLEM). The two new bars show that byte: A (Aeropuerto) =
 * cap of 5000, P (Puerto) = cap of 8000, "capacity in use", not demand.
 *
 * The RCI meter (SIMUI class vtable 0x100ab274) [CONFIRMED, PE vtable + bodies]:
 *  - Init +0x24 FUN_10064b08 loads the background art into a raster at +0xa8 (41 x 88), draws R C I into it with font 0xf
 *    of the window manager (FUN_10085065 vt+0x14), colour vt+0x184(0x1f, 0x29, 0x88), font vt+0x90(raster, x, y, s, n),
 *    and sizes the window to the raster (vt+0xc0).
 *  - SetRect +0xc8 FUN_100651ba(x, y, _, _) forces the size of the raster +0xa8; the base FUN_1006db90 runs vt+0x170 =
 *    FUN_1006d56c on a size change, which recreates the window surface +0x58 at the new size.
 *  - Draw +0x144 FUN_10065214: +0x5c vt+0x1c(0x10) begin, vt+0x118(raster +0xa8, its rect) background, three fills
 *    vt+0x7c(colour, rect + origin +0x24, 0), vt+0x20(0x10) end. Bars x 5..10 / 14..19 / 23..28, up from y +0xec (51),
 *    height = permille * 0.001 * +0xe8 (16.0) [CONFIRMED @ SIMUI 0x10065cc9, disassembly].
 * So after the stock Init a raster RCB_EXTRA px wider replaces +0xa8 (made with the game's own recipe from FUN_1006d56c:
 * gfx FUN_10085039 vt+0x14(&r), r vt+0x0c(w, h, fmt from gfx vt+0x28, 0, sysmem, 0)): the stock art, two more column
 * strips copied from the C column, the right margin moved to the new edge, "A" and "P" in the stock font and colour.
 * Then one SetRect: the game sizes the window and its surface itself, and every later SetRect (sc3resize BARKIDS) keeps
 * the new width. The Draw wrap adds the two fills (same 16 px scale, the stock fill path, inside NATIVETEXT's RCI window
 * so they are drawn sharp) and a 1 px tick at 75%. A tooltip button over the two new columns gives the numbers.
 * SC3RESIZE_RCIBARS=0: none of this (the stock 3-bar RCI). SC3RESIZE_RCIBARS_LOG=1 logs every value change. */
static int   g_rcibars = 1, g_rcb_log;
#define RCB_EXTRA 18                 /* two columns at the stock pitch of 9 */
#define RCB_NATW  41
#define RCB_NATH  88
#define RCB_BTN   0x5D0B0001u
#define RCB_TOP   30                 /* first panel row of the RCI art (rows above = the globe tab) */
static void *g_rcb_init_orig, *g_rcb_draw_orig;
static void *g_rcb_btn;              /* our tooltip button (own reference), released at the next Init */
static LONG  g_rcb_shown[2] = { -1, -1 };
static char  g_rcb_tip[200];

typedef DWORD (__fastcall *RCB_FN0)(void *);
static void *rcb_newraster(BYTE *win, LONG w, LONG h);

/* cap byte of valve 5000 / 8000 and supply / demand of 5001 / 8001; 0 when the city or a valve is missing */
static int rcb_read(LONG cap[2], LONG sd[2][2]) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    static const DWORD vid[2] = { 5000, 8000 };
    BYTE *city;
    void *L, *vl = NULL;
    int k, ok = 0;
    cap[0] = cap[1] = -1;
    memset(sd, 0, 4 * sizeof(LONG));
    if (!sui) return 0;
    __try {
        city = (BYTE *)((void *(__cdecl *)(void))((BYTE *)sui + 0x8e7da))();
        if (!city) return 0;
        L = (void *)ho_v(city, 0x1b8, 1, 0x80f1e6d3, 0, 0, 0, 0);   /* the valve layer, as GRAPHNEW gn_ctx */
        if (!L) return 0;
        if (!(ho_v(L, 0x00, 2, 0x40a42f1c, (DWORD)&vl, 0, 0, 0) & 0xff)) vl = NULL;
        ho_v(L, 0x08, 0, 0, 0, 0, 0, 0);
        if (!vl) return 0;
        for (k = 0; k < 2; k++) {
            void *va = NULL, *vs = NULL;
            if ((ho_v(vl, 0x14, 3, vid[k], 0xf1ec30, (DWORD)&va, 0, 0) & 0xff) && va) {
                cap[k] = (LONG)(ho_v(va, 0x70, 0, 0, 0, 0, 0, 0) & 0xff);
                ho_v(va, 0x08, 0, 0, 0, 0, 0, 0);
                ok++;
            }
            if ((ho_v(vl, 0x14, 3, vid[k] + 1, 0xf1ec30, (DWORD)&vs, 0, 0) & 0xff) && vs) {
                sd[k][0] = (LONG)ho_v(vs, 0x28, 0, 0, 0, 0, 0, 0);   /* last month's supply  (+0x0c) */
                sd[k][1] = (LONG)ho_v(vs, 0x2c, 0, 0, 0, 0, 0, 0);   /* last month's demand  (+0x10) */
                ho_v(vs, 0x08, 0, 0, 0, 0, 0, 0);
            }
        }
        ho_v(vl, 0x08, 0, 0, 0, 0, 0, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return ok == 2;
}

static void rcb_settip(void) {
    BYTE s[0x20];
    if (!g_rcb_btn) return;
    ho_str(s, g_rcb_tip);
    ho_v(g_rcb_btn, 0x8c, 1, (DWORD)s, 0, 0, 0, 0);
    ho_str_free(s);
}

static void rcb_maketip(LONG ca, LONG ci) {
    if (ho_spanish())
        wsprintfA(g_rcb_tip, "Capacidad en uso: Aeropuerto %ld%%, Puerto %ld%%",
                  ca < 0 ? 0 : ca, ci < 0 ? 0 : ci);
    else
        wsprintfA(g_rcb_tip, "Capacity in use: Airport %ld%%, Seaport %ld%%",
                  ca < 0 ? 0 : ca, ci < 0 ? 0 : ci);
}

/* The tooltip button (recipe of the RCI's own 0x7d1 button, SIMUI 0x10064b08: factory FUN_10085065 vt+0x30(id, caption,
   img, rect, 0), vt+0x8c tooltip, flags as there). Its image is NOT the stock 0x52fb06f0: that one is the globe tab of the
   "Visitar Bolsa de SimCity" link (33x30, the first build drew a second globe). It is a copy of the RCI's own pixels under
   the button, the "A P" letter rows between the up and down bars, so the button is invisible and never covers a bar.
   Image buttons take a strip of 4 frames side by side (states): the first build passed one 18 px frame and got a 4 px button. */
static void rcb_button(BYTE *rci, void *R, LONG x0, LONG y0, LONG x1, LONG y1) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    BYTE cap[0x20];
    void *fac, *btn, *win, *img;
    LONG *r, s[4], d[4], rc[4], f;
    if (g_rcb_btn) { ho_v(g_rcb_btn, 0x08, 0, 0, 0, 0, 0, 0); g_rcb_btn = NULL; }
    if (!(img = rcb_newraster(rci, 4 * (x1 - x0), y1 - y0))) { logf("RCIBARS> no button image, no tooltip"); return; }
    for (f = 0; f < 4; f++) {
        s[0] = x0; s[1] = y0; s[2] = x1; s[3] = y1; d[0] = f * (x1 - x0); d[1] = 0; d[2] = d[0] + x1 - x0; d[3] = y1 - y0;
        ho_v(img, 0x118, 4, (DWORD)R, (DWORD)s, (DWORD)d, 0, 0);
    }
    rc[0] = 0; rc[1] = 0; rc[2] = 4 * (x1 - x0); rc[3] = y1 - y0;
    fac = ((void *(__cdecl *)(void))(sui + 0x85065))();
    ho_str(cap, "");
    btn = fac ? (void *)ho_v(fac, 0x30, 5, RCB_BTN, (DWORD)cap, (DWORD)img, (DWORD)rc, 0) : NULL;
    ho_str_free(cap);
    ho_v(img, 0x08, 0, 0, 0, 0, 0, 0);
    if (!btn) { logf("RCIBARS> button not made, no tooltip"); return; }
    ho_v(btn, 0x24, 2, 4, 0, 0, 0, 0);
    ho_v(btn, 0x24, 2, 0x100, 1, 0, 0, 0);
    ho_v(btn, 0x98, 1, 0x1000000, 0, 0, 0, 0);
    win = (void *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
    if (!win || !(ho_v(rci, 0x34, 1, (DWORD)win, 0, 0, 0, 0) & 0xff)) { ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0); logf("RCIBARS> button not added"); return; }
    ho_v(win, 0xc8, 4, (DWORD)x0, (DWORD)y0, (DWORD)x1, (DWORD)y1, 0);
    r = (LONG *)((BYTE *)win + 0x80);
    logf("RCIBARS> tooltip button local [%ld %ld %ld %ld]", r[0], r[1], r[2], r[3]);
    g_rcb_btn = btn;                 /* our reference: kept to update the text */
    rcb_maketip(-1, -1);
    rcb_settip();
}

/* A raster of w x h in the display format, the game's own recipe (SIMUI 0x1006d56c): gfx FUN_10085039 vt+0x14(&r), then
   r vt+0x0c(w, h, format from gfx vt+0x28, 0, sysmem as the window's flag 0x100000, 0). One reference, NULL on failure. */
static void *rcb_newraster(BYTE *win, LONG w, LONG h) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    void *gfx = ((void *(__cdecl *)(void))(sui + 0x85039))(), *R = NULL;
    DWORD a[7], fmt[2], *fp;
    if (!gfx) return NULL;
    ho_v(gfx, 0x14, 1, (DWORD)&R, 0, 0, 0, 0);
    if (!R) return NULL;
    fp = (DWORD *)ho_v(gfx, 0x28, 2, (DWORD)fmt, 0, 0, 0, 0);
    a[0] = (DWORD)w; a[1] = (DWORD)h; a[2] = fp ? fp[0] : 0; a[3] = fp ? fp[1] : 0; a[4] = 0;
    a[5] = (ho_v(win, 0xf0, 1, 0x100000, 0, 0, 0, 0) & 0xff) ? 1 : 0; a[6] = 0;
    if (!fp || !(rz_thiscall_ret(R, (void *)(*(DWORD **)R)[0x0c / 4], a, 7) & 0xff)) { ho_v(R, 0x08, 0, 0, 0, 0, 0, 0); return NULL; }
    return R;
}

/* After the stock Init: the wider background raster, then one SetRect. */
static void rcb_widen(BYTE *rci) {
    BYTE *sui = (BYTE *)GetModuleHandleA("SIMUI.DLL");
    void *old = *(void **)(rci + 0xa8), *R, *wm, *font;
    LONG w0, h0, W, s[4], d[4], ly, fh, k;
    BYTE *os, *rs;
    DWORD ofl;
    LONG *e = (LONG *)(rci + 0x80);
    if (!old) return;
    w0 = (LONG)ho_v(old, 0x38, 0, 0, 0, 0, 0, 0);
    h0 = (LONG)ho_v(old, 0x3c, 0, 0, 0, 0, 0, 0);
    if (w0 != RCB_NATW || h0 != RCB_NATH) { logf("RCIBARS> RCI art %ldx%ld, not the stock 41x88: left alone", w0, h0); return; }
    W = w0 + RCB_EXTRA;
    if (!(R = rcb_newraster(rci, W, h0))) { logf("RCIBARS> raster create %ldx%ld failed: stock RCI", W, h0); return; }
    /* letter band = the rows the stock letters use: y = (0x3e - 0x33) / 2 + 0x33 - font height / 2 (SIMUI 0x10064b08) */
    wm = ((void *(__cdecl *)(void))(sui + 0x85065))();
    font = wm ? (void *)ho_v(wm, 0x14, 1, 0xf, 0, 0, 0, 0) : NULL;
    if (!font && wm) font = (void *)ho_v(wm, 0x14, 1, 0, 0, 0, 0, 0);
    fh = font ? (LONG)ho_v(font, 0x60, 1, 0, 0, 0, 0, 0) : 14;
    ly = ((0x3e - 0x33) / 2 + 0x33) - fh / 2;
#define RCB_CP(sx0, sy0, sx1, sy1, dx0, dy0) do { s[0] = (sx0); s[1] = (sy0); s[2] = (sx1); s[3] = (sy1); \
        d[0] = (dx0); d[1] = (dy0); d[2] = (dx0) + (sx1) - (sx0); d[3] = (dy0) + (sy1) - (sy0); \
        ho_v(R, 0x118, 4, (DWORD)old, (DWORD)s, (DWORD)d, 0, 0); } while (0)
    /* Colour key: GZGraphicD's surface Blt (sub-object vt+0x2c = 0x10018c58) passes the SOURCE sub-object's flags +0xdc and
       DDBLTFX +0x78 to IDirectDrawSurface::Blt [CONFIRMED @ GZGraphicD 0x10018c58], so the stock art is keyed through
       them. A keyed copy skips the key pixels and left them black in the new raster (the first picture: black boxes
       beside the globe tab). So the copies run with the key bits (DDBLT_KEYSRC 0x8000, KEYSRCOVERRIDE 0x10000) masked
       and the new raster gets the stock flags and DDBLTFX after. */
    os = *(BYTE **)((BYTE *)old + 0x44); rs = *(BYTE **)((BYTE *)R + 0x44);
    if (!os || !rs || IsBadWritePtr(os, 0xe0) || IsBadWritePtr(rs, 0xe0) || *(DWORD *)os != (DWORD)GetModuleHandleA("GZGraphicD.dll") + GZ_RVA_VT_SURFACE ||
        *(DWORD *)rs != *(DWORD *)os) { logf("RCIBARS> surface objects not the known class: stock RCI"); ho_v(R, 0x08, 0, 0, 0, 0, 0, 0); return; }
    ofl = *(DWORD *)(os + 0xdc);
    *(DWORD *)(os + 0xdc) = ofl & ~0x18000u;
    RCB_CP(0, 0, w0, h0, 0, 0);                                 /* the stock art, R C I included */
    /* Rows 0..29 are the globe tab of the "Bolsa de SimCity" button, rows 30.. the panel (measured in an 800x600 frame
       dump, verify/rcibars): only panel rows are copied into the new columns, so the tab stays one tab. */
    for (k = 0; k < 2; k++) {                                   /* column strips [12, 21) = C, without its letter */
        LONG dx = 30 + 9 * k;
        RCB_CP(12, RCB_TOP, 21, ly, dx, RCB_TOP);
        LONG y;
        /* letter rows: plain panel row 32 (above the columns), one row at a time. The right margin is NOT plain: x 32..40
           is the panel's right-edge shading (measured, verify/rcibars), and the first build showed it as a grey box. */
        for (y = ly; y < ly + fh; y++) RCB_CP(12, RCB_TOP + 2, 21, RCB_TOP + 3, dx, y);
        RCB_CP(12, ly + fh, 21, h0, dx, ly + fh);
    }
    RCB_CP(30, RCB_TOP, w0, h0, 30 + RCB_EXTRA, RCB_TOP);       /* right margin [30, 41) to the new edge */
    for (k = w0; k < W; k++) RCB_CP(0, 0, 1, RCB_TOP, k, 0);    /* above the panel: stock column 0 (outside the tab, keyed) */
    if (g_hudpos_bolsa) {
        /* HUDPOS (owner 2026-11-02, "move the Visitar Bolsa de SimCity icon near the minimap"): the globe tab and its plate
           (stock x 0..41, rows 0..29) go to the right end of the wider raster, flush with the minimap's edge; the columns they
           leave get stock column 0 (keyed above the panel). Copied from the STOCK raster, not within R (overlapping Blt). */
        LONG kx;
        RCB_CP(0, 0, w0, RCB_TOP, RCB_EXTRA, 0);
        for (kx = 0; kx < RCB_EXTRA; kx++) RCB_CP(0, 0, 1, RCB_TOP, kx, 0);
    }
    *(DWORD *)(os + 0xdc) = ofl;
    memcpy(rs + 0x78, os + 0x78, 0x64);                         /* DDBLTFX, the key at +0x5c */
    *(DWORD *)(rs + 0xdc) = ofl;
#undef RCB_CP
    if (font) {
        static const char *lt[2] = { "A", "P" };
        DWORD oc = ho_v(font, 0x2c, 0, 0, 0, 0, 0, 0), col = ho_v(rci, 0x184, 3, 0x1f, 0x29, 0x88, 0, 0);
        if (ho_v(font, 0x34, 1, col, 0, 0, 0, 0) & 0xff) {
            for (k = 0; k < 2; k++) {
                LONG bl = 32 + 9 * k, tw = (LONG)ho_v(font, 0x78, 2, (DWORD)lt[k], 1, 0, 0, 0);
                ho_v(font, 0x90, 5, (DWORD)R, (DWORD)((5 - tw) / 2 + bl), (DWORD)ly, (DWORD)lt[k], 1);
            }
            ho_v(font, 0x34, 1, oc, 0, 0, 0, 0);
        }
    }
    *(void **)(rci + 0xa8) = R;                                 /* the RCI's reference moves to R */
    ho_v(old, 0x08, 0, 0, 0, 0, 0, 0);
    {   LONG x = e[2] > e[0] ? e[2] - W : e[0];                /* keep the right edge */
        logf("RCIBARS> RCI raster %ldx%ld -> %ldx%ld (letters band y %ld..%ld); local [%ld %ld %ld %ld] -> x %ld",
             w0, h0, W, h0, ly, ly + fh, e[0], e[1], e[2], e[3], x);
        ho_v(rci, 0xc8, 4, (DWORD)x, (DWORD)e[1], (DWORD)(x + W), (DWORD)(e[1] + h0), 0);
        logf("RCIBARS> RCI local now [%ld %ld %ld %ld], surface +0x58 %08lX", e[0], e[1], e[2], e[3], *(DWORD *)(rci + 0x58));
    }
    if (g_hudpos_bolsa) {   /* the stock 0x7d1 link button follows its art by RCB_EXTRA px */
        void *bw = (void *)ho_v(rci, 0x78, 1, 0x7d1, 0, 0, 0, 0);
        if (bw && !IsBadWritePtr(bw, 0xa0)) {
            LONG *be = (LONG *)((BYTE *)bw + 0x80), b0 = be[0], b1 = be[1], b2 = be[2], b3 = be[3];
            ho_v(bw, 0xc8, 4, (DWORD)(b0 + RCB_EXTRA), (DWORD)b1, (DWORD)(b2 + RCB_EXTRA), (DWORD)b3, 0);
            logf("HUDPOS> Bolsa button local [%ld %ld %ld %ld] -> [%ld %ld %ld %ld]", b0, b1, b2, b3, be[0], be[1], be[2], be[3]);
        } else logf("HUDPOS> Bolsa button 0x7d1 not found: art moved, button not");
    }
    rcb_button(rci, R, 30, 0x33, 30 + RCB_EXTRA, 0x3e);   /* rows 51..62: between the up (+0xec) and down (+0xf0) bars */
    g_rcb_shown[0] = g_rcb_shown[1] = -1;
}

static DWORD __fastcall rcb_init(void *self) {
    DWORD r = ((RCB_FN0)g_rcb_init_orig)(self);
    if ((r & 0xff) && g_rcibars) {
        __try { rcb_widen((BYTE *)self); }
        __except (EXCEPTION_EXECUTE_HANDLER) { logf("RCIBARS> fault 0x%08lX while widening: stock RCI", GetExceptionCode()); }
    }
    return r;
}

static void rcb_fill(BYTE *rci, void *dst, DWORD col, LONG l, LONG t, LONG r, LONG b) {
    LONG rc[4], *o = (LONG *)(rci + 0x24);
    if (r <= l || b <= t) return;
    rc[0] = l + o[0]; rc[1] = t + o[1]; rc[2] = r + o[0]; rc[3] = b + o[1];
    ho_v(dst, 0x7c, 3, col, (DWORD)rc, 0, 0, 0);
}

static DWORD __fastcall rcb_draw(void *self) {
    BYTE *rci = (BYTE *)self;
    DWORD r = ((RCB_FN0)g_rcb_draw_orig)(self);
    __try {
        void *ras = *(void **)(rci + 0xa8), *dst = *(void **)(rci + 0x5c);
        LONG cap[2], sd[2][2], k;
        float sc;
        if (!g_rcibars || !ras || !dst || (LONG)ho_v(ras, 0x38, 0, 0, 0, 0, 0, 0) != RCB_NATW + RCB_EXTRA) return r;
        if (!rcb_read(cap, sd)) cap[0] = cap[1] = 0;
        if (cap[0] != g_rcb_shown[0] || cap[1] != g_rcb_shown[1]) {
            if (g_rcb_log || g_rcb_shown[0] < 0)
                logf("RCIBARS> capacity in use: commercial %ld%% (5001 supply %ld demand %ld), industrial %ld%% (8001 supply %ld demand %ld)",
                     cap[0], sd[0][0], sd[0][1], cap[1], sd[1][0], sd[1][1]);
            g_rcb_shown[0] = cap[0]; g_rcb_shown[1] = cap[1];
            rcb_maketip(cap[0], cap[1]);
            rcb_settip();
        }
        sc = *(float *)(rci + 0xe8);
        if (sc <= 0 || sc > 64) sc = 16.0f;
        InterlockedIncrement(&g_nt_inrci);   /* NATIVETEXT keeps fills made inside the RCI Draw as sharp records */
        __try {
        if (ho_v(dst, 0x1c, 1, 0x10, 0, 0, 0, 0) & 0xff) {
            static const BYTE rgb[2][3] = { { 0x90, 0x30, 0xc0 }, { 0xd0, 0x70, 0x00 } };   /* A purple, P orange */
            LONG base = *(LONG *)(rci + 0xec), tick = base - (LONG)(sc * 75.0f / 100.0f + 0.5f);
            DWORD tcol = ho_v(rci, 0x184, 3, 0x80, 0x00, 0x00, 0, 0);
            for (k = 0; k < 2; k++) {
                LONG bl = 32 + 9 * k, h = (LONG)(sc * (cap[k] < 0 ? 0 : cap[k] > 100 ? 100 : cap[k]) / 100.0f + 0.5f);
                if (h > 0) rcb_fill(rci, dst, ho_v(rci, 0x184, 3, rgb[k][0], rgb[k][1], rgb[k][2], 0, 0), bl, base - h, bl + 5, base);
                rcb_fill(rci, dst, tcol, bl - 1, tick, bl + 6, tick + 1);   /* the advisor's 75% */
            }
            ho_v(dst, 0x20, 1, 0x10, 0, 0, 0, 0);
        }
        } __finally { InterlockedDecrement(&g_nt_inrci); }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    return r;
}

static void rcb_install(HMODULE suim) {
    DWORD sui = (DWORD)suim, old, *si, *sd;
    if (!g_rcibars || !sui) return;
    si = (DWORD *)(sui + 0xab274 + 0x24);
    sd = (DWORD *)(sui + 0xab274 + 0x144);
    if (IsBadReadPtr(si, 4) || IsBadReadPtr(sd, 4) || *si != sui + 0x64b08 || *sd != sui + 0x65214) {
        logf("RCIBARS> RCI vtable slots +0x24 / +0x144 are not FUN_10064b08 / FUN_10065214: off"); return;
    }
    if (!VirtualProtect(si, 0x124, PAGE_EXECUTE_READWRITE, &old)) return;
    g_rcb_init_orig = (void *)*si;
    g_rcb_draw_orig = (void *)*sd;
    g_rcb_drawfn = (void *)rcb_draw;   /* NATIVETEXT accepts this in the slot when it wraps the Draw */
    InterlockedExchange((LONG volatile *)sd, (LONG)(DWORD)rcb_draw);
    InterlockedExchange((LONG volatile *)si, (LONG)(DWORD)rcb_init);
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    logf("RCIBARS> on: RCI Init (vt+0x24) and Draw (vt+0x144) wrapped, A = commercial / P = industrial capacity in use");
}
