/* ======================================================================================================== VDTABS
 * (child graphs2 2026-11-02, owner: "the line-graph tabs must look like real clickable tabs, not radio boxes, and be
 * aligned / the Cuadros radio buttons become tabs too"). #included by sc3resize.c right before sc3resize_graphs.c.
 * Used by the Graficas page (GRAPHNEW tabs, sc3resize_graphs.c) and the Cuadros page (sc3resize_vdbars.c).
 *
 * GZWIND has no tab class: its 19 window classes (FUN_1000121d) hold none, and FUN_1001a420, once tagged "layout_tabs",
 * is the draw routine of a scrolling item list [CONFIRMED @ GZWIND 0x1000121d, 0x1001a420]. A tab here is made of
 * native windows of the page, so DLGSCALE / NATIVETEXT treat it like the page's own text:
 *  - the shape: filled polygons of the leader-line shape class (0x4303E5B6 / 0xE303E5AE, style 0x11, points through
 *    vt+0x34, the recipe of GRAPHAXIS gx_tick): a trapezoid fill, two slanted edges and a bottom edge. A row hangs
 *    under a rule line (the chart's bottom edge). The selected tab is lighter, one pixel higher and two lower, and the
 *    rule is broken under it, so it reads as joined to the chart above.
 *  - the click and the caption: a text button (widget factory +0x2c = class cGZWinBtn 0x22ECFC47, kind 2
 *    [CONFIRMED @ GZWIND 0x1000b53b, 0x10008559]) without its art (iface vt+0x58(NULL)) and with style bit 0x10 (no
 *    bevel when there is no image) [CONFIRMED @ GZWIND 0x10008935, 0x10008adf], so only its caption draws, over the
 *    shapes added before it (a window draws itself, then its children in order, FUN_1001ed43). Its click reaches the
 *    page's control handler as message 3, p3 1, id [CONFIRMED @ GZWIND 0x10008fdb, 0x1001e983]. Caption colours by
 *    state: iface vt+0x64(0 normal / 2 hover / 4 disabled, colour) [CONFIRMED @ GZWIND 0x10009a0b].
 *  - widths: from a per-character width table of the dialog font (font 0xf, measured on the stock radio captions
 *    2026-11-02: "Ciudad" 39 px, "Economia" 57, "Servicios" 54, "Redes" 37, "Ambiente" 54, "Electricidad" 68 at 1x).
 *    The button's own auto-size (style 0x6a4 bit 0x20) gave 54..67 px for every caption, "Agua" too: not a text width.
 * Shapes are disabled (vt+0xf4(2, 0)): a shape forwards mouse input to its parent, never to a sibling, so it must not
 * sit over a button [CONFIRMED @ GZWIND 0x1000a074]; here every shape is under its button anyway.
 * SC3RESIZE_VDTABS=0: none of this; the Graficas page keeps its radio row (graphtabs) and Cuadros its stock radios. */
static int g_vdtabs = 1, g_vt_font = 0xf, g_vt_log;
static int g_vt_cur = 0xf;       /* font of the strip being built: g_vt_font, or the Cuadros one (tabfont) */
static void *g_vt_fac;           /* factory of the strip being built, for measuring */
#define TB_MAX 8
#define VT_R 9
#define VT_GAP 2
static int g_vt_round = 1;   /* SC3RESIZE_VDTABSROUND=0: the old trapezoid tabs */
static int g_vt_small = 1, g_vt_small_id = 0x11;   /* SC3RESIZE_VDTABSSMALL=0: Cuadros tabs in font 0xf again; _VDTABSFONT=<id> */

/* id layout of one strip: +1+i button, +0x10+i fill, +0x20+i left edge, +0x30+i right edge, +0x40+i bottom edge,
   +0x50 / +0x51 the two pieces of the rule */
typedef struct {
    DWORD id0;
    void *win;                 /* the page window the strip was built on */
    int n, sel;
    int x0, x1, y, h;          /* rule from x0 to x1 at y (page-local), tabs y .. y + h */
    int tx[TB_MAX], tw[TB_MAX], mw[TB_MAX];
} TB;

static WORD g_vt_c_border, g_vt_c_sel, g_vt_c_off, g_vt_c_text, g_vt_c_hover;

static void vt_colours(void *fac) {
    static int done;
    DWORD c;
    if (done) return;
    done = 1;
    g_vt_c_border = gx_col16(0x6E84E0);
    g_vt_c_off    = gx_col16(0x98A8E4);
    g_vt_c_text   = gx_col16(0x31347B);       /* the range radios' text colour (SIMUI 0x1002e6cb) */
    g_vt_c_hover  = gx_col16(0x2050D0);
    /* the light panel behind the Cuadros charts: colour 0x62E56A2B of the factory (SIMUI FUN_1002095a) */
    c = fac ? ho_v(fac, 0x80, 2, 0x62e56a2b, 0, 0, 0, 0) : 0;
    g_vt_c_sel = c ? (WORD)c : gx_col16(0xDCE2FA);
    if (g_vt_log) logf("VDTABS> colours border %04X sel %04X (panel 0x%08lX) off %04X text %04X", g_vt_c_border, g_vt_c_sel, c, g_vt_c_off, g_vt_c_text);
}

/* a filled polygon window (style 0x31: fill vt+0x14, line vt+0x18) `id` of `win` at page-local (x, y), w x h, npt points relative to it; created on first use */
static void vt_poly2(void *win, DWORD id, WORD col, WORD line, int x, int y, int w, int h, const LONG *pts, int npt) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    void *obj = NULL, *sw;
    LONG r[4];
    if (w <= 0 || h <= 0) { gx_show(mp_child(win, id), 0); return; }
    if (!(sw = mp_child(win, id))) {
        void **svc = (void **)((MP_GETSVC)((BYTE *)sui + 0x8489d))();
        if (!svc || IsBadReadPtr(svc, 4) || !(ho_v(svc, 0x0c, 3, 0x4303e5b6, 0xe303e5ae, (DWORD)&obj, 0, 0) & 0xff) || !obj) return;
        ho_v(obj, 0x0c, 1, 0x31, 0, 0, 0, 0);       /* filled + outlined polygon (SIMUI 0x10046590, 0x10051c53); 0x11 only strokes */
        r[0] = 0; r[1] = 0; r[2] = w; r[3] = h;
        sw = (void *)ho_v(obj, 0x38, 0, 0, 0, 0, 0, 0);
        ho_v(sw, 0xc4, 1, (DWORD)r, 0, 0, 0, 0);
        ho_v(sw, 0xec, 1, id, 0, 0, 0, 0);
        ho_v(sw, 0xf4, 2, 0x800, 0, 0, 0, 0);
        if (!(ho_v(win, 0x34, 1, (DWORD)sw, 0, 0, 0, 0) & 0xff)) { ho_v(sw, 0x28, 0, 0, 0, 0, 0, 0); ho_v(obj, 0x08, 0, 0, 0, 0, 0, 0); return; }
    } else if (!(ho_v(win, 0x80, 3, id, 0xe303e5ae, (DWORD)&obj, 0, 0) & 0xff)) obj = NULL;
    if (obj) {
        ho_v(obj, 0x34, 2, (DWORD)npt, (DWORD)pts, 0, 0, 0);
        ho_v(obj, 0x14, 1, col, 0, 0, 0, 0); ho_v(obj, 0x18, 1, line, 0, 0, 0, 0); ho_v(obj, 0x1c, 1, line, 0, 0, 0, 0);
        ho_v(obj, 0x08, 0, 0, 0, 0, 0, 0);
    }
    if (sw && !IsBadReadPtr(sw, 0xa4)) {
        ho_v(sw, 0xc8, 4, (DWORD)x, (DWORD)y, (DWORD)(x + w), (DWORD)(y + h), 0);
        ho_v(sw, 0xf4, 2, 2, 0, 0, 0, 0);            /* disabled: clicks never stop here */
        gx_show(sw, 1);
    }
}
static void vt_poly(void *win, DWORD id, WORD col, int x, int y, int w, int h, const LONG *pts, int npt) {
    vt_poly2(win, id, col, col, x, y, w, h, pts, npt);
}
static void vt_rect(void *win, DWORD id, WORD col, int x, int y, int w, int h) {
    LONG p[8];
    p[0] = 0; p[1] = 0; p[2] = 0; p[3] = h; p[4] = w; p[5] = h; p[6] = w; p[7] = 0;
    vt_poly(win, id, col, x, y, w, h, p, 4);
}

/* a label `id` of `win`; align = vertical + 3 * horizontal (0 left / 1 centre / 2 right) [CONFIRMED @ GZWIND 0x1000f049] */
static void vt_label(void *fac, void *win, DWORD id, const char *text, WORD col, int x, int y, int w, int h, int align) {
    BYTE s[0x20];
    BYTE *lw = (BYTE *)mp_child(win, id);
    ho_str(s, text);
    if (!lw) {
        void *lbl = (void *)ho_v(fac, 0x44, 2, id, (DWORD)s, 0, 0, 0);
        if (lbl) {
            if (g_gx_font >= 0) ho_v(lbl, 0x40, 1, ho_v(fac, 0x14, 1, (DWORD)g_gx_font, 0, 0, 0, 0), 0, 0, 0, 0);
            lw = (BYTE *)ho_v(lbl, 0x0c, 0, 0, 0, 0, 0, 0);
            ho_v(lw, 0xec, 1, id, 0, 0, 0, 0);
            if (!(ho_v(win, 0x34, 1, (DWORD)lw, 0, 0, 0, 0) & 0xff)) { ho_v(lw, 0x28, 0, 0, 0, 0, 0, 0); lw = NULL; }
            ho_v(lbl, 0x08, 0, 0, 0, 0, 0, 0);
        }
    }
    if (lw && !IsBadReadPtr(lw, 0xa8)) {
        ho_v(lw + 0xa4, 0x44, 1, (DWORD)align, 0, 0, 0, 0);
        ho_v(lw + 0xa4, 0x24, 1, col, 0, 0, 0, 0);
        ho_v(lw, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);
        ho_v(lw, 0xc8, 4, (DWORD)x, (DWORD)y, (DWORD)(x + w), (DWORD)(y + h), 0);
        gx_show(lw, 1);
    }
    ho_str_free(s);
}

/* the caption-only button of a tab; returns the caption width it auto-sized to (0 = not measured) */
static int vt_tab_btn(void *fac, void *win, DWORD id, const char *text) {
    BYTE s[0x20];
    void *btn;
    BYTE *bw;
    int mw = 0;
    if (mp_child(win, id)) return 0;
    ho_str(s, text);
    btn = (void *)ho_v(fac, 0x2c, 5, id, (DWORD)s, 0, 0, 0);
    if (btn) {
        ho_v(btn, 0x58, 1, 0, 0, 0, 0, 0);                         /* no art: the no-image path */
        ho_v(btn, 0x24, 2, 0x10, 1, 0, 0, 0);                      /* ... draws no bevel */
        ho_v(btn, 0x24, 2, 4, 1, 0, 0, 0);                         /* caption on */
        ho_v(btn, 0x24, 2, 0x80, 0, 0, 0, 0);                      /* caption does not move when pressed */
        ho_v(btn, 0x60, 1, ho_v(fac, 0x14, 1, (DWORD)g_vt_cur, 0, 0, 0, 0), 0, 0, 0, 0);
        ho_v(btn, 0x64, 2, 0, g_vt_c_text, 0, 0, 0);
        ho_v(btn, 0x64, 2, 2, g_vt_c_hover, 0, 0, 0);
        ho_v(btn, 0x64, 2, 4, g_vt_c_text, 0, 0, 0);
        bw = (BYTE *)ho_v(btn, 0x1c, 0, 0, 0, 0, 0, 0);
        if (bw && !IsBadReadPtr(bw, 0xa4)) {
            ho_v(bw, 0x10c, 1, (DWORD)s, 0, 0, 0, 0);
            mw = (int)(*(LONG *)(bw + 0x88) - *(LONG *)(bw + 0x80));   /* auto-sized to the caption (style 0x6a4 has 0x20) */
            ho_v(btn, 0x24, 2, 0x20, 0, 0, 0, 0);
            ho_v(bw, 0xf4, 2, 2, 1, 0, 0, 0);
            ho_v(bw, 0xf4, 2, 0x20000, 1, 0, 0, 0);                /* no-image window flag (GZWIND 0x1000901e) */
            if (!(ho_v(win, 0x34, 1, (DWORD)bw, 0, 0, 0, 0) & 0xff)) { ho_v(bw, 0x28, 0, 0, 0, 0, 0, 0); mw = 0; }
        }
        ho_v(btn, 0x08, 0, 0, 0, 0, 0, 0);
    }
    ho_str_free(s);
    return mw;
}

/* width of `t` in font `fid` from the font's own glyph table (cell `char` of the table at font+0x14, 0x14 bytes: left top right
   bottom advance [CONFIRMED @ GZServiceD 0x10006e54], see HUD_SCALE.md); -1 when the table is not readable */
static int vt_font_w(int fid, const char *t) {
    BYTE *f, *tb;
    int w = 0;
    const unsigned char *c;
    if (!g_vt_fac || !(f = (BYTE *)ho_v(g_vt_fac, 0x14, 1, (DWORD)fid, 0, 0, 0, 0)) || IsBadReadPtr(f, 0x18)) return -1;
    tb = *(BYTE **)(f + 0x14);
    if (!tb || IsBadReadPtr(tb, 0x14 * 256)) return -1;
    for (c = (const unsigned char *)t; *c; c++) w += *(LONG *)(tb + 0x14 * *c + 0x10);
    return w;
}
static void vt_font_probe(void) {
    int id;
    static const char *s[3] = { "Electricidad", "Ciudad", "H" };
    for (id = 0; id < 0x30; id++) {
        BYTE *f = g_vt_fac ? (BYTE *)ho_v(g_vt_fac, 0x14, 1, (DWORD)id, 0, 0, 0, 0) : NULL;
        BYTE *tb;
        if (!f || IsBadReadPtr(f, 0x18)) continue;
        tb = *(BYTE **)(f + 0x14);
        logf("VDTABS> font probe id 0x%02x obj 0x%08lX table %s: Electricidad %d, Ciudad %d, H adv %d cell h %d", id, (DWORD)f,
             (tb && !IsBadReadPtr(tb, 0x14 * 256)) ? "ok" : "unreadable", vt_font_w(id, s[0]), vt_font_w(id, s[1]), vt_font_w(id, s[2]),
             (tb && !IsBadReadPtr(tb, 0x14 * 256)) ? (int)(*(LONG *)(tb + 0x14 * 'H' + 12) - *(LONG *)(tb + 0x14 * 'H' + 4)) : -1);
    }
}

/* caption width estimate (font 0xf): table in tenths of a pixel */
static int vt_text_w(const char *t) {
    int w = 0;
    if (g_vt_cur != 0xf) { int m = vt_font_w(g_vt_cur, t); if (m > 0) return m; }
    const unsigned char *c;
    for (c = (const unsigned char *)t; *c; c++) {
        unsigned char ch = *c;
        int v = 66;
        if (strchr("iljI.,:;'!|", ch) || ch == 0xed || ch == 0xec) v = 33;
        else if (strchr("tfr ", ch)) v = 44;
        else if (strchr("scz", ch)) v = 55;
        else if (strchr("mwMW", ch)) v = 110;
        else if (ch >= 'A' && ch <= 'Z') v = 77;
        else if (strchr("odbpqnuhgaeyvkx", ch) || ch == 0xf3 || ch == 0xfa || ch == 0xe1 || ch == 0xe9 || ch == 0xf1) v = 72;
        w += v;
    }
    return (w + 9) / 10;
}

/* place the tabs from x0 by their caption widths, padding shrunk to fit x0..x1 */
static void tb_layout(TB *t) {
    int g_vt_gap = g_vt_round ? VT_GAP : -1;
    int i, sum = 0, pad, x, avail = t->x1 - t->x0 - 4;
    for (i = 0; i < t->n; i++) sum += t->mw[i];
    pad = t->n ? (avail - sum - g_vt_gap * (t->n - 1)) / t->n : 0;
    if (pad > 22) pad = 22;
    if (pad < 4) pad = 4;
    x = t->x0 + 4;
    for (i = 0; i < t->n; i++) {
        t->tx[i] = x;
        t->tw[i] = t->mw[i] + pad;
        x += t->tw[i] + g_vt_gap;                    /* ROUND: a gap between tabs; old look: neighbours share an edge pixel */
    }
    if (x > t->x1 && sum > 0) {                     /* still too wide: scale (captions may clip, logged) */
        double k = (double)(t->x1 - t->x0 - 4) / (double)(x - t->x0 - 4);
        x = t->x0 + 4;
        for (i = 0; i < t->n; i++) { t->tx[i] = x; t->tw[i] = (int)(t->tw[i] * k); x += t->tw[i] + g_vt_gap; }
        logf("VDTABS> strip 0x%08lX: %d tabs need %d px, %d available: scaled", t->id0, t->n, sum + t->n * 4, avail);
    }
}

/* one rounded-top tab body in colour `col` at (x, y), w x H, corner radius R, as up to 4 stacked rects (a polygon of more than 4
   points drew skewed: only the 4-point recipe is known good). Rows are grouped by their corner inset (a circle's), so the corner is a
   pixel-art stair. ids id[0..3] */
static void vt_round_tab(void *win, const DWORD *id, WORD col, int x, int y, int w, int H, int R) {
    int k, g = 0, y0 = 0, cur = -1, in_[VT_R + 1];
    for (k = 0; k < R; k++) {
        int d2 = 2 * R - 2 * k - 1, v4 = 4 * R * R - d2 * d2, sr = 0;
        while ((2 * sr + 1) * (2 * sr + 1) <= v4) sr++;          /* sr = round(sqrt(v4 / 4)) */
        in_[k] = R - sr;
    }
    for (k = 0; k < R && in_[k] > 0; k++) {
        if (cur >= 0 && in_[k] != cur && g < 5) { vt_rect(win, id[g++], col, x + cur, y + y0, w - 2 * cur, k - y0); y0 = k; }
        cur = in_[k];
    }
    if (cur >= 0 && k > y0 && g < 5) { vt_rect(win, id[g++], col, x + cur, y + y0, w - 2 * cur, k - y0); y0 = k; }
    vt_rect(win, id[g++], col, x, y + y0, w, H - y0);       /* the rows with no inset, down to the bottom */
    while (g < 6) gx_show(mp_child(win, id[g++]), 0);
}

/* shapes + button rects for the current selection */
static void tb_draw(TB *t) {
    void *win = t->win;
    int i;
    if (!win || IsBadReadPtr(win, 0xa4)) return;
    for (i = 0; i < t->n; i++) {
        int s = i == t->sel, x = t->tx[i], w = t->tw[i], top = s ? t->y - 1 : t->y + 1, bot = t->y + t->h - (s ? 0 : 2), H = bot - top;
        LONG f[8], l[8], r[8];
        BYTE *bw;
        if (g_vt_round && w > 2 * VT_R + 4 && H > VT_R + 4 && TB_MAX <= 8) {
            /* ROUND: vertical sides, rounded top corners (radius VT_R at 1x; DLGSCALE scales the page surface).
               The shape class takes few points (a 20-point outline drew as a chamfer), so every polygon here has 7:
               an outline layer in the border colour (corner L, corner R, body) and the same three inset by 1 px in the fill colour. */
            WORD fc = s ? g_vt_c_sel : g_vt_c_off;
            DWORD io[6], ii[6];
            int q;
            for (q = 0; q < 6; q++) { io[q] = t->id0 + 0x10 + 8 * q + i; ii[q] = t->id0 + 0x90 + 8 * q + i; }
            vt_round_tab(win, io, g_vt_c_border, x, top, w, H, VT_R);
            vt_round_tab(win, ii, fc, x + 1, top + 1, w - 2, H - 2, VT_R - 1);
            if ((bw = (BYTE *)mp_child(win, t->id0 + 1 + i)) && !IsBadReadPtr(bw, 0xa4)) {
                ho_v(bw, 0xc8, 4, (DWORD)x + 2, (DWORD)top, (DWORD)(x + w - 2), (DWORD)bot, 0);
                gx_show(bw, 1);
            }
            continue;
        }
        f[0] = 0; f[1] = 0; f[2] = w; f[3] = 0; f[4] = w - 3; f[5] = H; f[6] = 3; f[7] = H;
        l[0] = 0; l[1] = 0; l[2] = 1; l[3] = 0; l[4] = 4; l[5] = H; l[6] = 3; l[7] = H;
        r[0] = 3; r[1] = 0; r[2] = 4; r[3] = 0; r[4] = 1; r[5] = H; r[6] = 0; r[7] = H;
        vt_poly(win, t->id0 + 0x10 + i, s ? g_vt_c_sel : g_vt_c_off, x, top, w, H, f, 4);
        vt_poly(win, t->id0 + 0x20 + i, g_vt_c_border, x, top, 4, H, l, 4);
        vt_poly(win, t->id0 + 0x30 + i, g_vt_c_border, x + w - 4, top, 4, H, r, 4);
        vt_rect(win, t->id0 + 0x40 + i, g_vt_c_border, x + 3, bot - 1, w - 6, 1);
        if ((bw = (BYTE *)mp_child(win, t->id0 + 1 + i)) && !IsBadReadPtr(bw, 0xa4)) {
            ho_v(bw, 0xc8, 4, (DWORD)x + 2, (DWORD)top, (DWORD)(x + w - 2), (DWORD)bot, 0);
            gx_show(bw, 1);
        }
    }
    /* the rule, broken under the selected tab */
    if (t->sel >= 0 && t->sel < t->n) {
        vt_rect(win, t->id0 + 0x50, g_vt_c_border, t->x0, t->y, t->tx[t->sel] - t->x0 + (g_vt_round ? (VT_R * 4) / 9 : 1), 1);
        { int rx = t->tx[t->sel] + t->tw[t->sel] - (g_vt_round ? (VT_R * 4) / 9 : 1); vt_rect(win, t->id0 + 0x51, g_vt_c_border, rx, t->y, t->x1 - rx, 1); }
    } else {
        vt_rect(win, t->id0 + 0x50, g_vt_c_border, t->x0, t->y, t->x1 - t->x0, 1);
        gx_show(mp_child(win, t->id0 + 0x51), 0);
    }
    ho_v(win, 0x168, 0, 0, 0, 0, 0, 0);   /* local rects moved: rebuild the derived ones (graphtabs trap) */
    ho_v(win, 0x14c, 0, 0, 0, 0, 0, 0);
    ho_v(win, 0x154, 0, 0, 0, 0, 0, 0);
}

/* build a strip of n tabs on `win`: shapes first (under), then the buttons */
static int tb_make(void *fac, void *win, TB *t, DWORD id0, const char **txt, int n, int sel, int x0, int x1, int y, int h) {
    int i, made = 0;
    char lg[200];
    int k = 0;
    if (!fac || !win || n <= 0 || n > TB_MAX) return 0;
    vt_colours(fac);
    g_vt_fac = fac;
    if (g_vt_log) { static int pr; if (!pr) { pr = 1; vt_font_probe(); } }
    memset(t, 0, sizeof(*t));
    t->id0 = id0; t->win = win; t->n = n; t->sel = sel; t->x0 = x0; t->x1 = x1; t->y = y; t->h = h;
    for (i = 0; i < n; i++) { t->tx[i] = x0 + 4 + i * 40; t->tw[i] = 40; }
    tb_draw(t);                                   /* creates the shapes in z order before the buttons */
    for (i = 0; i < n; i++) {
        int mw = vt_tab_btn(fac, win, id0 + 1 + i, txt[i]);
        if (mp_child(win, id0 + 1 + i)) made++;
        t->mw[i] = vt_text_w(txt[i]);
        mw = t->mw[i];
        k += wsprintfA(lg + k, " %d", mw);
    }
    tb_layout(t);
    tb_draw(t);
    k += wsprintfA(lg + k, ", x");
    for (i = 0; i < n && k < 150; i++) k += wsprintfA(lg + k, " %d+%d", t->tx[i], t->tw[i]);
    logf("VDTABS> strip 0x%08lX on 0x%08lX: %d/%d tabs, rule %d..%d y %d, caption widths%s, sel %d", id0, (DWORD)win, made, n, x0, x1, y, lg, sel);
    return made == n;
}

/* the tab index of a clicked control id, -1 if none */
static int tb_hit(const TB *t, void *win, DWORD id) {
    if (!t->n || t->win != win || id <= t->id0 || id > t->id0 + (DWORD)t->n) return -1;
    return (int)(id - t->id0 - 1);
}
