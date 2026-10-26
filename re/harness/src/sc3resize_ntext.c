/* ======================================================================================================== NATIVETEXT
 * (child nativetext 2026-10-26; owner: "keep working on adding native rendering to the scaled UI instead of zooming in,
 * like font, RCI indicators, clock, teleprompter"). #included by sc3resize.c right before rz_hs_pre.
 *
 * HUDSCALE / DLGSCALE resample the HUD and the dialogs from their native pixels, so their text is magnified bitmap text.
 * This block draws that text again, sharp, at the factor, after the resample:
 *  - every glyph the game draws goes through GZServiceD FUN_10006e54 (font this, dest raster, x, y, char): cell `char` of
 *    the rect table font+0x14 (left top right bottom advance, 0x14 bytes each) copied from the 8-bit sheet font+0x34
 *    through the dest raster's vt+0x118; the colour is the sheet palette font+0x20, entries 1..16 a ramp from the text
 *    colour (entry 1) to entry 16 written by font vt+0x34 / +0x38 [CONFIRMED @ GZServiceD 0x10006e54, 0x100070aa,
 *    0x100071b2, 0x10007d9f]. An entry detour records each glyph with its dest DirectDraw surface (raster+0x44 -> +4);
 *  - the records follow the pixels: a 1:1 Blt carries the source surface's records (clipped to the source rect) to the
 *    dest surface, an opaque Blt or a colour fill drops the dest records it covers. So at the present the composite holds
 *    the text in client coordinates (raster -> raster copies of the same format are IDirectDrawSurface::Blt, GZGraphicD
 *    FUN_10014894 -> sub vt+0x2c FUN_10018c58 [CONFIRMED]);
 *  - in the HUD pass, a record inside an enlarged HUD window or dialog whose glyph pixels still match the native frame
 *    (85% of its ink) is erased from the enlarged copy (its ink inpainted from the pixels around it, that area resampled
 *    again) and drawn at the factor with the record's text colour: look A a TrueType face, look B the game's own glyph
 *    rebuilt from its coverage levels at the dest resolution.
 * SC3RESIZE_NATIVETEXT=0 off (the resampled text, as before), 1 look A, 2 look B (default). _FACE=<TrueType face> (A),
 * _LOG=1 census of the glyph callers every 10 s, _DUMP=<abs prefix> writes each font sheet once. */
#pragma comment(lib, "gdi32.lib")
double __cdecl floor(double);   /* not <math.h>: it declares logf, which clashes with the logger */
double __cdecl fabs(double);
static int   g_nt_on = 2;
static int   g_nt_log;
static char  g_nt_dump[MAX_PATH];
static char  g_nt_face[64];   /* empty: Comic Sans MS for the anti-aliased fonts, Arial Bold for the 1-bit one */
static int   g_nt_inst, g_nt_hooked;   /* hooked: records are kept (also while _CTL switches the look off) */
static char  g_nt_ctl[MAX_PATH];        /* SC3RESIZE_NATIVETEXT_CTL=<file>: its first digit switches the look live (0 off, 1 A, 2 B) */
static void *g_nt_orig;
static CRITICAL_SECTION g_nt_cs;
static int   g_nt_csok;
static ULONG64 g_nt_cyc;
static DWORD   g_nt_selfmv;   /* self-Blt record moves (the ticker scroll), per 10 s */
static __int64 g_nt_time;static DWORD g_nt_frames, g_nt_drawn, g_nt_rej, g_nt_beat, g_nt_glyphs, g_nt_maskb;

#define NT_FMAX 12
#define NT_AMC  4                    /* mask cache sets per font (scale pairs) */
#define NT_PH   8                    /* look B: sub-pixel phases per axis (1/8 dest px) */
#define NT_AMN  (256 * NT_PH * NT_PH)
typedef struct {
    double kx, ky; int look; DWORD used;
    /* per glyph and phase (slot ch * 64 + py * 8 + px): alpha 0..255, size, offset from floor(mapped cell origin),
       alpha centroid in x and the first / last+1 column with alpha >= 128 (mask-local), for the spacing check */
    BYTE **am; LONG *amw, *amh, *amx, *amy, *aml, *amr; float *amc;
    HFONT hf; LONG tta, ttpx;                                     /* look A: GDI font, its ascent, pixel size */
} NT_AMSET;
static int   g_nt_phase = 1;         /* SC3RESIZE_NATIVETEXT_PHASE=0: look B placed at the rounded dest pixel (old) */
typedef struct {
    BYTE *font, *sheet, *tab;        /* identity */
    LONG w, h, fh;                   /* sheet size, font line height (font+0x1c) */
    BYTE *pix;                       /* sheet copy, w*h indices */
    LONG cell[256][5];
    LONG ink[256][4];                /* ink box of each glyph, cell-local (empty: [0]>=[2]) */
    LONG inkn[256];                  /* its ink pixel count */
    float cx[256], tl[256], tr[256]; /* coverage centroid in x, first / last+1 column with coverage >= 0.5 (cell-local) */
    BYTE key;
    int ok, idx, aa;                 /* aa: more than one ink level (the Comic-style UI fonts); else the 1-bit bold sans */
    LONG cap, base;                 /* 'H' ink height and the row under it (cell-local) */
    NT_AMSET set[NT_AMC];
} NT_FONT;
static NT_FONT g_nt_f[NT_FMAX];
static int     g_nt_nf;

typedef struct {
    LONG x0, y0, x1, y1;             /* glyph cell in the surface */
    LONG c0, c1, c2, c3;             /* its visible part */
    WORD pal[17];
    BYTE fi, ch;
    BYTE kind, pad;                  /* 0 glyph, 1 solid fill (the RCI bars; colour in pal[1]) */
    WORD org;                        /* 0 drawn here, else 1 + index of the surface it came from */
    DWORD batch;
} NT_REC;
typedef struct { void *surf; NT_REC *r; int n, cap; DWORD used; } NT_SURF;
#define NT_SMAX 96
static NT_SURF g_nt_s[NT_SMAX];
static DWORD   g_nt_tick, g_nt_batch;
static void   *g_nt_lsurf;
static LONG    g_nt_lx, g_nt_ly, g_nt_total;

/* census (SC3RESIZE_NATIVETEXT_LOG=1) */
#define NT_CB 64
static struct { DWORD ra[3]; void *surf; int fi; DWORD n, batch; char s[72]; int sl; LONG x, y; WORD fg; } g_nt_cb[NT_CB];
static DWORD g_nt_cbt;
static int   g_nt_dbgnow, g_nt_dbgfr;   /* _LOG=2: one frame of per-area diag lines every 10 s */

static NT_SURF *nt_surf(void *surf, int make) {
    int i, lru = -1;
    for (i = 0; i < NT_SMAX; i++) if (g_nt_s[i].surf == surf) { g_nt_s[i].used = ++g_nt_tick; return &g_nt_s[i]; }
    if (!make) return NULL;
    for (i = 0; i < NT_SMAX; i++) {
        if (!g_nt_s[i].surf) { lru = i; break; }
        if (lru < 0 || g_nt_s[i].used < g_nt_s[lru].used) lru = i;
    }
    g_nt_total -= g_nt_s[lru].n; g_nt_s[lru].n = 0;
    g_nt_s[lru].surf = surf; g_nt_s[lru].used = ++g_nt_tick;
    return &g_nt_s[lru];
}
static NT_REC *nt_push(NT_SURF *s) {
    if (s->n >= s->cap) {
        if (s->cap >= 4096) {   /* never seen; bound it: drop the oldest half */
            int k = s->n / 2;
            memmove(s->r, s->r + k, (s->n - k) * sizeof(NT_REC)); s->n -= k; g_nt_total -= k;
        } else {
            int nc = s->cap ? s->cap * 2 : 64;
            NT_REC *p = (NT_REC *)realloc(s->r, nc * sizeof(NT_REC));
            if (!p) return NULL;
            s->r = p; s->cap = nc;
        }
    }
    g_nt_total++;
    return &s->r[s->n++];
}
/* mode 0: an opaque Blt/fill covers rc: drop what it covers fully, trim a side it covers. mode 1: a glyph of batch `a`
 * is drawn at rc: drop the glyphs drawn here by other batches under it. mode 2: a copy from surface org `a` lands at rc:
 * drop the earlier copies from that surface there. */
static void nt_drop(NT_SURF *s, const LONG *rc, int mode, DWORD a) {
    int i, j = 0;
    for (i = 0; i < s->n; i++) {
        NT_REC *r = &s->r[i];
        int hit = r->c0 < rc[2] && rc[0] < r->c2 && r->c1 < rc[3] && rc[1] < r->c3, drop = 0;
        if (hit) {
            if (mode == 1) drop = r->org == 0 && r->batch != a;
            else if (mode == 2) drop = r->org == (WORD)a;
            else {
                int cx = rc[0] <= r->c0 && rc[2] >= r->c2, cy = rc[1] <= r->c1 && rc[3] >= r->c3;
                if (cx && cy) drop = 1;
                else if (cy && rc[0] <= r->c0) r->c0 = rc[2];
                else if (cy && rc[2] >= r->c2) r->c2 = rc[0];
                else if (cx && rc[1] <= r->c1) r->c1 = rc[3];
                else if (cx && rc[3] >= r->c3) r->c3 = rc[1];
                if (r->c0 >= r->c2 || r->c1 >= r->c3) drop = 1;
            }
        }
        if (!drop) { if (j != i) s->r[j] = *r; j++; }
    }
    g_nt_total -= s->n - j; s->n = j;
}

/* ---- fonts */
static float nt_covv(const NT_FONT *f, BYTE v) {   /* coverage of a sheet index: key 0, ramp 1..16, other ink 1 */
    if (v == f->key) return 0.0f;
    if (v >= 1 && v <= 16) return 1.0f - (float)(v - 1) / 16.0f;
    return 1.0f;
}
static void nt_set_free(NT_AMSET *m) {
    int c;
    if (m->am) for (c = 0; c < NT_AMN; c++) free(m->am[c]);
    free(m->am); free(m->amw); free(m->amh); free(m->amx); free(m->amy); free(m->aml); free(m->amr); free(m->amc);
    if (m->hf) DeleteObject(m->hf);
    memset(m, 0, sizeof(*m));
}
static void nt_font_dump(NT_FONT *f, BYTE *font) {
    char path[MAX_PATH + 40];
    HANDLE h;
    DWORD wr, i;
    LONG y, rowb = (f->w + 3) & ~3;
    BITMAPFILEHEADER bf; BITMAPINFOHEADER bi; RGBQUAD q[256];
    BYTE *row = (BYTE *)calloc(1, rowb);
    BYTE *pal = *(BYTE **)(font + 0x20);
    if (!row) return;
    wsprintfA(path, "%sfont%d.bmp", g_nt_dump, f->idx);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        memset(&bf, 0, sizeof(bf)); memset(&bi, 0, sizeof(bi));
        for (i = 0; i < 256; i++) { BYTE v = (BYTE)(i * 15 > 255 ? 255 : i * 15); q[i].rgbRed = q[i].rgbGreen = q[i].rgbBlue = v; q[i].rgbReserved = 0; }
        bf.bfType = 0x4d42; bf.bfOffBits = sizeof(bf) + sizeof(bi) + sizeof(q); bf.bfSize = bf.bfOffBits + rowb * f->h;
        bi.biSize = sizeof(bi); bi.biWidth = f->w; bi.biHeight = f->h; bi.biPlanes = 1; bi.biBitCount = 8; bi.biClrUsed = 256;
        WriteFile(h, &bf, sizeof(bf), &wr, NULL); WriteFile(h, &bi, sizeof(bi), &wr, NULL); WriteFile(h, q, sizeof(q), &wr, NULL);
        for (y = f->h - 1; y >= 0; y--) { memcpy(row, f->pix + y * f->w, f->w); WriteFile(h, row, rowb, &wr, NULL); }
        CloseHandle(h);
    }
    free(row);
    wsprintfA(path, "%sfont%d.txt", g_nt_dump, f->idx);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        char ln[160];
        int n = wsprintfA(ln, "font 0x%08lX sheet %ldx%ld key %u height %ld keyflag %u type %lu\r\n", (DWORD)font, f->w, f->h,
                          f->key, f->fh, font[0x29], *(DWORD *)(font + 4));
        WriteFile(h, ln, n, &wr, NULL);
        if (pal && !IsBadReadPtr(pal, 0x14) && *(LONG *)(pal + 0xc) == 16 && *(LONG *)(pal + 8) >= 32 && !IsBadReadPtr(*(void **)(pal + 0x10), 64)) {
            const WORD *pe = *(const WORD **)(pal + 0x10);
            n = wsprintfA(ln, "pal"); WriteFile(h, ln, n, &wr, NULL);
            for (i = 0; i < 32; i++) { n = wsprintfA(ln, " %04X", pe[i]); WriteFile(h, ln, n, &wr, NULL); }
            WriteFile(h, "\r\n", 2, &wr, NULL);
        }
        for (i = 0; i < 256; i++) {
            const LONG *c = f->cell[i];
            if (c[2] <= c[0] && !c[4]) continue;
            n = wsprintfA(ln, "%lu %ld %ld %ld %ld %ld\r\n", i, c[0], c[1], c[2], c[3], c[4]);
            WriteFile(h, ln, n, &wr, NULL);
        }
        CloseHandle(h);
    }
    logf("NATIVETEXT> font %d dumped to %sfont%d.bmp/.txt", f->idx, g_nt_dump, f->idx);
}
static int nt_font_load(NT_FONT *f, BYTE *font, BYTE *sheet, BYTE *tab) {
    DWORD *svt, a = 0x40, bits, pitch;
    LONG w, h, y, i;
    f->ok = 0; f->font = font; f->sheet = sheet; f->tab = tab;
    if (IsBadReadPtr(tab, 0x1400) || IsBadReadPtr(sheet, 0x48)) return 0;
    svt = *(DWORD **)sheet;
    if (!svt || IsBadReadPtr(svt, 0x1b0) || *(DWORD *)(sheet + 0x10) != 8) {
        logf("NATIVETEXT> font 0x%08lX: sheet 0x%08lX is not 8-bit (format %lu) - not handled", (DWORD)font, (DWORD)sheet,
             IsBadReadPtr(sheet, 0x14) ? 0 : *(DWORD *)(sheet + 0x10));
        return 0;
    }
    w = *(LONG *)(sheet + 0x24); h = *(LONG *)(sheet + 0x28);
    if (w <= 0 || h <= 0 || w > 4096 || h > 2048) return 0;
    if (!rz_thiscall(sheet, (void *)svt[0x1c / 4], &a, 1)) return 0;
    bits = rz_thiscall_ret(sheet, (void *)svt[0x1a8 / 4], NULL, 0);
    pitch = rz_thiscall_ret(sheet, (void *)svt[0x1ac / 4], NULL, 0);
    if (bits && pitch >= (DWORD)w && !IsBadReadPtr((void *)bits, pitch * (h - 1) + w)) {
        BYTE *p = (BYTE *)realloc(f->pix, w * h);
        if (p) { f->pix = p; for (y = 0; y < h; y++) memcpy(p + y * w, (BYTE *)bits + y * pitch, w); f->ok = 1; }
    }
    rz_thiscall(sheet, (void *)svt[0x20 / 4], &a, 1);
    if (!f->ok) return 0;
    f->w = w; f->h = h; f->fh = *(LONG *)(font + 0x1c);
    memcpy(f->cell, tab, sizeof(f->cell));
    f->key = f->pix[0];
    for (i = 0; i < 256; i++) {   /* ink boxes; refuse cells outside the sheet */
        LONG *c = f->cell[i], *k = f->ink[i], x;
        k[0] = k[1] = 0x7fff; k[2] = k[3] = -1; f->inkn[i] = 0;
        if (c[0] < 0 || c[1] < 0 || c[2] > w || c[3] > h || c[2] < c[0] || c[3] < c[1]) { c[0] = c[1] = c[2] = c[3] = 0; continue; }
        for (y = c[1]; y < c[3]; y++)
            for (x = c[0]; x < c[2]; x++)
                if (f->pix[y * w + x] != f->key) {
                    f->inkn[i]++;
                    if (x - c[0] < k[0]) k[0] = x - c[0];
                    if (x - c[0] + 1 > k[2]) k[2] = x - c[0] + 1;
                    if (y - c[1] < k[1]) k[1] = y - c[1];
                    if (y - c[1] + 1 > k[3]) k[3] = y - c[1] + 1;
                }
        if (k[2] < 0) k[0] = k[1] = k[2] = k[3] = 0;
    }
    f->cap = f->ink['H'][3] - f->ink['H'][1]; f->base = f->ink['H'][3];
    if (f->cap <= 0) { f->cap = f->fh * 2 / 3; f->base = f->fh * 4 / 5; }
    for (i = 0; i < 256; i++) {   /* coverage centroid and 50% edges per glyph (the spacing check) */
        const LONG *c = f->cell[i];
        double sw = 0, sx = 0;
        LONG x, l = -1, r = -1;
        for (x = c[0]; x < c[2]; x++) {
            double col = 0;
            for (y = c[1]; y < c[3]; y++) col += nt_covv(f, f->pix[y * w + x]);
            sw += col; sx += col * (x - c[0] + 0.5);
            for (y = c[1]; y < c[3]; y++) if (nt_covv(f, f->pix[y * w + x]) >= 0.5f) { if (l < 0) l = x - c[0]; r = x - c[0] + 1; break; }
        }
        f->cx[i] = sw > 0 ? (float)(sx / sw) : 0.0f;
        f->tl[i] = (float)(l < 0 ? 0 : l); f->tr[i] = (float)(r < 0 ? 0 : r);
    }
    for (i = 0; i < NT_AMC; i++) nt_set_free(&f->set[i]);   /* a reload drops the masks */
    {   int hist[256], used = 0, mx = 0;
        LONG x;
        memset(hist, 0, sizeof(hist));
        for (y = 0; y < h; y++) for (x = 0; x < w; x++) hist[f->pix[y * w + x]]++;
        for (i = 0; i < 256; i++) if (hist[i] && i != f->key) { used++; mx = i; }
        f->aa = used > 2;   /* index 17 is only sheet padding in all three sheets measured */
        logf("NATIVETEXT> font %d = 0x%08lX: sheet %ldx%ld, line height %ld, key index %u (flag %u), %d ink indices up to %d, cap %ld base %ld",
             f->idx, (DWORD)font, w, h, f->fh, f->key, font[0x29], used, mx, f->cap, f->base);
    }
    if (g_nt_dump[0]) nt_font_dump(f, font);
    return 1;
}
static int nt_font(BYTE *font) {
    BYTE *sheet, *tab;
    int i;
    if (IsBadReadPtr(font, 0x3c)) return -1;
    sheet = *(BYTE **)(font + 0x34); tab = *(BYTE **)(font + 0x14);
    if (!sheet || !tab) return -1;
    for (i = 0; i < g_nt_nf; i++)
        if (g_nt_f[i].font == font) {
            if (g_nt_f[i].sheet != sheet || g_nt_f[i].tab != tab) nt_font_load(&g_nt_f[i], font, sheet, tab);
            return g_nt_f[i].ok ? i : -1;
        }
    if (g_nt_nf >= NT_FMAX) return -1;
    i = g_nt_nf++;
    g_nt_f[i].idx = i;
    nt_font_load(&g_nt_f[i], font, sheet, tab);
    return g_nt_f[i].ok ? i : -1;
}

/* ---- census */
static void *nt_owner_walk(BYTE *w, void *surf, int depth, int *budget) {
    BYTE **head, **n;
    int guard = 0;
    if (!w || depth > 7 || *budget <= 0 || IsBadReadPtr(w, 0x60)) return NULL;
    (*budget)--;
    {   BYTE *ras = *(BYTE **)(w + 0x58);
        if (ras && !IsBadReadPtr(ras, 0x48)) {
            BYTE *sub = *(BYTE **)(ras + 0x44);
            if (sub && !IsBadReadPtr(sub, 8) && *(void **)(sub + 4) == surf) return w;
        }
    }
    head = *(BYTE ***)(w + 0x34);
    if (!head || IsBadReadPtr(head, 4)) return NULL;
    n = (BYTE **)*head;
    while (n && n != head && guard++ < 400 && *budget > 0) {
        void *r;
        if (IsBadReadPtr(n, 12)) break;
        if ((r = nt_owner_walk(n[2], surf, depth + 1, budget)) != NULL) return r;
        n = (BYTE **)n[0];
    }
    return NULL;
}
static const char *nt_mod(DWORD a, DWORD *rva) {
    static char nm[8][40]; static int k;
    HMODULE m = NULL;
    char p[MAX_PATH], *s;
    *rva = a;
    if (!a || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)a, &m) || !m) return "?";
    *rva = a - (DWORD)m + ((DWORD)m == (DWORD)GetModuleHandleA(NULL) ? 0x400000 : 0x10000000);   /* the Ghidra address */
    if (!GetModuleFileNameA(m, p, sizeof(p))) return "?";
    s = strrchr(p, '\\');
    k = (k + 1) & 7;
    lstrcpynA(nm[k], s ? s + 1 : p, sizeof(nm[k]));
    return nm[k];
}
static void nt_census_flush(void) {
    int i;
    void *root = rz_ui_root();
    logf("NATIVETEXT> census (10 s): glyphs %lu, records held %ld", g_nt_glyphs, g_nt_total);
    g_nt_glyphs = 0;
    for (i = 0; i < NT_CB; i++) {
        DWORD r0, r1, r2;
        const char *m0, *m1, *m2;
        char own[96];
        BYTE *w;
        int budget = 5000;
        if (!g_nt_cb[i].n) continue;
        m0 = nt_mod(g_nt_cb[i].ra[0], &r0); m1 = nt_mod(g_nt_cb[i].ra[1], &r1); m2 = nt_mod(g_nt_cb[i].ra[2], &r2);
        own[0] = 0;
        if (g_nt_cb[i].surf == g_hs_comp) lstrcpyA(own, "the composite");
        else if (root && (w = (BYTE *)nt_owner_walk((BYTE *)root, g_nt_cb[i].surf, 0, &budget)) != NULL) {
            DWORD vt = *(DWORD *)w, rv;
            const char *mv = nt_mod(vt, &rv);
            const LONG *r = (const LONG *)(w + 0x14);
            wsprintfA(own, "own surface of window vt %s 0x%08lX [%ld %ld %ld %ld]", mv, rv, r[0], r[1], r[2], r[3]);
        } else wsprintfA(own, "surface 0x%08lX (no window owns it)", (DWORD)g_nt_cb[i].surf);
        g_nt_cb[i].s[g_nt_cb[i].sl < 71 ? g_nt_cb[i].sl : 71] = 0;
        logf("NATIVETEXT>   %5lu glyphs  font %d  colour %04X  at (%ld,%ld)  callers %s 0x%08lX < %s 0x%08lX < %s 0x%08lX  into %s  \"%s\"",
             g_nt_cb[i].n, g_nt_cb[i].fi, g_nt_cb[i].fg, g_nt_cb[i].x, g_nt_cb[i].y, m0, r0, m1, r1, m2, r2, own, g_nt_cb[i].s);
        g_nt_cb[i].n = 0;
    }
}
static void nt_census(DWORD *fp, void *surf, int fi, LONG x, LONG y, BYTE ch, WORD fg, DWORD batch) {
    DWORD ra[3] = {0, 0, 0}, *e = fp;
    int i, k, free_i = -1;
    for (k = 0; k < 3 && e && !IsBadReadPtr(e, 8); k++) { ra[k] = e[1]; e = (DWORD *)e[0]; }
    for (i = 0; i < NT_CB; i++) {
        if (g_nt_cb[i].surf == surf && !memcmp(g_nt_cb[i].ra, ra, sizeof(ra)) && g_nt_cb[i].fi == fi) break;
        if (free_i < 0 && !g_nt_cb[i].surf) free_i = i;
    }
    if (i == NT_CB) {
        if (free_i < 0) return;
        i = free_i; memset(&g_nt_cb[i], 0, sizeof(g_nt_cb[i]));
        g_nt_cb[i].surf = surf; g_nt_cb[i].fi = fi; memcpy(g_nt_cb[i].ra, ra, sizeof(ra));
    }
    if (g_nt_cb[i].batch != batch) { g_nt_cb[i].batch = batch; g_nt_cb[i].sl = 0; g_nt_cb[i].x = x; g_nt_cb[i].y = y; g_nt_cb[i].fg = fg; }
    if (g_nt_cb[i].sl < 71) g_nt_cb[i].s[g_nt_cb[i].sl++] = ch >= 32 ? (char)ch : '?';
    g_nt_cb[i].n++;
}

/* ---- the glyph detour (game thread) */
static void nt_add(BYTE *font, BYTE *dst, LONG x, LONG y, BYTE ch, DWORD *fp) {
    BYTE *sub, *pal;
    void *surf;
    int fi;
    const LONG *c;
    LONG cr[4];
    NT_SURF *s;
    NT_REC *r;
    if (IsBadReadPtr(dst, 0x48)) return;
    sub = *(BYTE **)(dst + 0x44);
    if (!sub || IsBadReadPtr(sub, 8) || !(surf = *(void **)(sub + 4))) return;
    pal = *(BYTE **)(font + 0x20);
    if (!pal || IsBadReadPtr(pal, 0x14) || *(LONG *)(pal + 0xc) != 16 || *(LONG *)(pal + 8) < 17 ||
        IsBadReadPtr(*(void **)(pal + 0x10), 34)) return;
    EnterCriticalSection(&g_nt_cs);
    fi = nt_font(font);
    if (fi < 0) { LeaveCriticalSection(&g_nt_cs); return; }
    c = g_nt_f[fi].cell[ch];
    g_nt_glyphs++;
    if (surf != g_nt_lsurf || y != g_nt_ly || x < g_nt_lx) g_nt_batch++;
    g_nt_lsurf = surf; g_nt_ly = y; g_nt_lx = x;
    if (g_nt_log) {
        nt_census(fp, surf, fi, x, y, ch, (*(WORD **)(pal + 0x10))[1], g_nt_batch);
        if (!g_nt_cbt) g_nt_cbt = GetTickCount();
        if (GetTickCount() - g_nt_cbt >= 10000) { g_nt_cbt = GetTickCount(); nt_census_flush(); }
    }
    if (g_nt_hooked && c[2] > c[0] && c[3] > c[1] && g_nt_f[fi].ink[ch][2] > 0) {
        cr[0] = x; cr[1] = y; cr[2] = x + c[2] - c[0]; cr[3] = y + c[3] - c[1];
        s = nt_surf(surf, 1);
        nt_drop(s, cr, 1, g_nt_batch);
        if ((r = nt_push(s)) != NULL) {
            r->x0 = r->c0 = cr[0]; r->y0 = r->c1 = cr[1]; r->x1 = r->c2 = cr[2]; r->y1 = r->c3 = cr[3];
            memcpy(r->pal, *(WORD **)(pal + 0x10), sizeof(r->pal));
            r->fi = (BYTE)fi; r->ch = ch; r->org = 0; r->batch = g_nt_batch;
        }
    }
    LeaveCriticalSection(&g_nt_cs);
}
typedef DWORD (__fastcall *NT_GLYPH)(void *, void *, void *, LONG, LONG, DWORD);
static DWORD __fastcall nt_glyph(BYTE *font, void *edx, BYTE *dst, LONG x, LONG y, DWORD ch) {
    DWORD *fp;
    __asm mov fp, ebp
    nt_add(font, dst, x, y, (BYTE)ch, fp ? (DWORD *)fp[0] : NULL);   /* fp[0]: the text loop's frame */
    return ((NT_GLYPH)g_nt_orig)(font, edx, dst, x, y, ch);
}
static void nt_install(void) {
    static const BYTE pro[6] = { 0x55, 0x8b, 0xec, 0x83, 0xec, 0x10 };   /* push ebp; mov ebp,esp; sub esp,0x10 */
    BYTE *fn, *tr;
    DWORD old;
    HMODULE m;
    if (g_nt_inst || !(g_nt_on || g_nt_log)) return;
    g_nt_inst = 1;
    if (!(m = GetModuleHandleA("GZServiceD.dll"))) { g_nt_inst = 0; return; }
    if (!g_nt_csok) { InitializeCriticalSection(&g_nt_cs); g_nt_csok = 1; }
    fn = (BYTE *)m + 0x6e54;
    if (IsBadReadPtr(fn, 6) || memcmp(fn, pro, 6)) { logf("NATIVETEXT> GZServiceD+0x6e54 prologue differs from the anchor - off"); g_nt_on = g_nt_log = 0; return; }
    tr = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tr) { g_nt_on = g_nt_log = 0; return; }
    memcpy(tr, pro, 6);
    tr[6] = 0xE9; *(DWORD *)(tr + 7) = (DWORD)(fn + 6) - (DWORD)(tr + 11);
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    if (!VirtualProtect(fn, 6, PAGE_EXECUTE_READWRITE, &old)) { g_nt_on = g_nt_log = 0; return; }
    g_nt_orig = tr; g_nt_hooked = 1;
    fn[5] = 0x90;
    *(DWORD *)(fn + 1) = (DWORD)nt_glyph - (DWORD)(fn + 5);
    fn[0] = 0xE9;
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    FlushInstructionCache(GetCurrentProcess(), fn, 6);
    logf("NATIVETEXT> on: look %s, glyph draw GZServiceD+0x6e54 hooked%s", g_nt_on == 1 ? "A (TrueType)" : g_nt_on == 2 ? "B (game font rebuilt)" : "off (census only)",
         g_nt_log ? ", census every 10 s" : "");
}

/* ---- RCI bars: the RCI Draw (SIMUI vt 0x100ab274 slot +0x144 = FUN_10065214) blits its background and makes 3 solid
   fills (raster vt+0x7c -> sub vt+0x18 FUN_100197d9 = IDirectDrawSurface::Blt flags 0x1000400, colour at DDBLTFX+0x50)
   [CONFIRMED @ SIMUI 0x10065214, GZGraphicD 0x1001552e, 0x100197d9]. While it runs, colour fills are kept as fill
   records, so the bars are redrawn at the factor with exact edges like the glyphs. SC3RESIZE_NATIVETEXT_RCI=0 off. */
static int   g_nt_rci = 1, g_nt_rcinst;
static volatile LONG g_nt_inrci;
static void *g_nt_rci_orig;
typedef DWORD (__fastcall *NT_DRAW0)(void *);
static DWORD __fastcall nt_rci_draw(void *self) {
    DWORD r;
    InterlockedIncrement(&g_nt_inrci);
    r = ((NT_DRAW0)g_nt_rci_orig)(self);
    InterlockedDecrement(&g_nt_inrci);
    return r;
}
static void nt_rci_install(void) {
    DWORD sui = (DWORD)GetModuleHandleA("SIMUI.DLL"), old, cur;
    DWORD *slot;
    if (g_nt_rcinst || !g_nt_rci || !sui) return;
    g_nt_rcinst = 1;
    slot = (DWORD *)(sui + 0xab274 + 0x144);
    if (IsBadReadPtr(slot, 4) || *slot != sui + 0x65214) { logf("NATIVETEXT> RCI vt+0x144 is not FUN_10065214 - RCI bars stay resampled"); return; }
    if (!VirtualProtect(slot, 4, PAGE_EXECUTE_READWRITE, &old)) return;
    g_nt_rci_orig = (void *)(cur = *slot);
    if ((DWORD)InterlockedCompareExchange((LONG volatile *)slot, (LONG)(DWORD)nt_rci_draw, (LONG)cur) != cur) { g_nt_rci_orig = NULL; return; }
    (void)0; /* no restore (task onramp): a restore can land mid-write in another mod on the same page */
    logf("NATIVETEXT> RCI bars: the RCI Draw (SIMUI vt 0x100ab274 +0x144) wrapped, its colour fills are redrawn at the factor");
}

/* ---- the records follow the Blts (rz_blt_hook_inner, every Blt) */
static void nt_blt(void *dst, const RECT *dr, void *src, const RECT *sr, DWORD fl, const void *fx) {
    NT_SURF *d, *s;
    LONG rc[4];
    int i, keyed;
    if (g_nt_hooked && g_nt_csok && g_nt_inrci && !src && (fl & 0x400) && dr && fx && !IsBadReadPtr(dr, sizeof(RECT)) &&
        !IsBadReadPtr(fx, 0x54) && dr->right > dr->left && dr->bottom > dr->top) {   /* an RCI bar */
        NT_REC *r;
        EnterCriticalSection(&g_nt_cs);
        d = nt_surf(dst, 1);
        rc[0] = dr->left; rc[1] = dr->top; rc[2] = dr->right; rc[3] = dr->bottom;
        nt_drop(d, rc, 0, 0);
        if ((r = nt_push(d)) != NULL) {
            memset(r, 0, sizeof(*r));
            r->x0 = r->c0 = rc[0]; r->y0 = r->c1 = rc[1]; r->x1 = r->c2 = rc[2]; r->y1 = r->c3 = rc[3];
            r->pal[1] = (WORD)*(const DWORD *)((const BYTE *)fx + 0x50);
            r->kind = 1; r->batch = ++g_nt_batch;
        }
        LeaveCriticalSection(&g_nt_cs);
        return;
    }
    if (!g_nt_hooked || !g_nt_total || !g_nt_csok) return;
    EnterCriticalSection(&g_nt_cs);
    d = nt_surf(dst, 0);
    s = src && src != dst ? nt_surf(src, 0) : NULL;    if (s && !s->n) s = NULL;
    if (!d && !s) { LeaveCriticalSection(&g_nt_cs); return; }
    if (dr && !IsBadReadPtr(dr, sizeof(RECT))) { rc[0] = dr->left; rc[1] = dr->top; rc[2] = dr->right; rc[3] = dr->bottom; }
    else { rc[0] = rc[1] = -0x40000; rc[2] = rc[3] = 0x40000; }
    keyed = (fl & 0x1E000) != 0;   /* DDBLT_KEYDEST, KEYDESTOVERRIDE, KEYSRC, KEYSRCOVERRIDE */
    if (d && src == dst && dr && sr && !IsBadReadPtr(dr, sizeof(RECT)) && !IsBadReadPtr(sr, sizeof(RECT)) &&
        dr->right - dr->left == sr->right - sr->left && dr->bottom - dr->top == sr->bottom - sr->top) {
        /* a Blt of a surface onto itself, shifted: the ticker scrolls its strip this way (SC3U FUN_0044428d, step px
           to the left). The records under the source rect move with the pixels. */
        static NT_REC *mv; static int mvcap;
        LONG dx = dr->left - sr->left, dy = dr->top - sr->top;
        int n = 0;
        if (mvcap < d->n) { free(mv); mv = (NT_REC *)malloc(d->n * sizeof(NT_REC)); mvcap = mv ? d->n : 0; }
        for (i = 0; mv && i < d->n; i++) {
            const NT_REC *a = &d->r[i];
            LONG c0 = max(a->c0, sr->left), c1 = max(a->c1, sr->top), c2 = min(a->c2, sr->right), c3 = min(a->c3, sr->bottom);
            if (c2 <= c0 || c3 <= c1) continue;
            mv[n] = *a;
            mv[n].x0 += dx; mv[n].x1 += dx; mv[n].y0 += dy; mv[n].y1 += dy;
            mv[n].c0 = c0 + dx; mv[n].c1 = c1 + dy; mv[n].c2 = c2 + dx; mv[n].c3 = c3 + dy;
            n++;
        }
        nt_drop(d, rc, 0, 0);
        for (i = 0; i < n; i++) { NT_REC *b = nt_push(d); if (!b) break; *b = mv[i]; }
        g_nt_selfmv++;
        LeaveCriticalSection(&g_nt_cs);
        return;
    }
    if (d && (!keyed || !src)) nt_drop(d, rc, 0, 0);
    if (s && dr && sr && !IsBadReadPtr(dr, sizeof(RECT)) && !IsBadReadPtr(sr, sizeof(RECT)) &&
        dr->right - dr->left == sr->right - sr->left && dr->bottom - dr->top == sr->bottom - sr->top) {
        LONG dx = dr->left - sr->left, dy = dr->top - sr->top;
        WORD o = (WORD)(1 + (s - g_nt_s));
        if (!d) d = nt_surf(dst, 1);
        nt_drop(d, rc, 2, o);
        for (i = 0; i < s->n; i++) {
            const NT_REC *a = &s->r[i];
            NT_REC *b;
            LONG c0 = max(a->c0, sr->left), c1 = max(a->c1, sr->top), c2 = min(a->c2, sr->right), c3 = min(a->c3, sr->bottom);
            if (c2 <= c0 || c3 <= c1) continue;
            if (!(b = nt_push(d))) break;
            a = &s->r[i];   /* (d != s: the push cannot move s->r) */
            *b = *a;
            b->x0 += dx; b->x1 += dx; b->y0 += dy; b->y1 += dy;
            b->c0 = c0 + dx; b->c1 = c1 + dy; b->c2 = c2 + dx; b->c3 = c3 + dy;
            b->org = o;
        }
    }
    LeaveCriticalSection(&g_nt_cs);
}

/* ---- glyph masks */
static float nt_cov(const NT_FONT *f, BYTE ch, LONG x, LONG y) {   /* coverage of the native glyph pixel, cell-local */
    const LONG *c = f->cell[ch];
    BYTE v;
    if (x < 0 || y < 0 || x >= c[2] - c[0] || y >= c[3] - c[1]) return 0.0f;
    v = f->pix[(c[1] + y) * f->w + c[0] + x];
    if (v == f->key) return 0.0f;
    if (v >= 1 && v <= 16) return 1.0f - (float)(v - 1) / 16.0f;
    return 1.0f;
}
static float nt_cubic(float a, float b, float c, float d, float t) {   /* Catmull-Rom */
    return b + 0.5f * t * (c - a + t * (2.0f * a - 5.0f * b + 4.0f * c - d + t * (3.0f * (b - c) + d - a)));
}
static void nt_mask_stats(NT_AMSET *m, int s) {   /* alpha centroid and the 128 edges, mask-local */
    const BYTE *a = m->am[s];
    LONG W = m->amw[s], H = m->amh[s], i, j, l = -1, r = -1;
    double sw = 0, sx = 0;
    for (i = 0; i < W; i++) {
        LONG col = 0, hi = 0;
        for (j = 0; j < H; j++) { col += a[j * W + i]; if (a[j * W + i] >= 128) hi = 1; }
        sw += col; sx += col * (i + 0.5);
        if (hi) { if (l < 0) l = i; r = i + 1; }
    }
    m->amc[s] = sw > 0 ? (float)(sx / sw) : 0.0f; m->aml[s] = l < 0 ? 0 : l; m->amr[s] = r < 0 ? 0 : r;
}
/* look B: mask pixel (i, j) sits at dest (floor(X) - 1 + i, floor(Y) - 1 + j), X/Y the mapped cell origin, whose
   fractional part is the phase (px + 0.5) / 8, (py + 0.5) / 8. So every glyph is sampled where the native glyph maps,
   with no rounding of its position, and the spacing between letters is the native spacing x factor. */
static void nt_mask_b(NT_FONT *f, NT_AMSET *m, BYTE ch, int ph) {
    const LONG *c = f->cell[ch];
    int s = ch * NT_PH * NT_PH + ph;
    double fx = ((ph % NT_PH) + 0.5) / NT_PH, fy = ((ph / NT_PH) + 0.5) / NT_PH;
    LONG gw = c[2] - c[0], gh = c[3] - c[1], W = (LONG)(gw * m->kx + 0.999) + 3, H = (LONG)(gh * m->ky + 0.999) + 3, i, j;
    float gx = (float)(m->kx * 0.9 < 1.0 ? 1.0 : m->kx * 0.9), gy = (float)(m->ky * 0.9 < 1.0 ? 1.0 : m->ky * 0.9), g = gx < gy ? gx : gy;
    BYTE *a = (BYTE *)malloc(W * H);
    if (!a) return;
    if (!g_nt_phase) fx = fy = 0.0;   /* the old placement: origin rounded, sampled at phase 0 */
    if (g > 4.0f) g = 4.0f;
    for (j = 0; j < H; j++) {
        float v = (float)((j - 1 + 0.5 - fy) / m->ky - 0.5);
        LONG yb = (LONG)(v < 0 ? v - 1 : v);
        float ty = v - (float)yb;
        for (i = 0; i < W; i++) {
            float u = (float)((i - 1 + 0.5 - fx) / m->kx - 0.5), col[4], cv;
            LONG xb = (LONG)(u < 0 ? u - 1 : u), k;
            float tx = u - (float)xb;
            for (k = 0; k < 4; k++)
                col[k] = nt_cubic(nt_cov(f, ch, xb - 1, yb - 1 + k), nt_cov(f, ch, xb, yb - 1 + k), nt_cov(f, ch, xb + 1, yb - 1 + k),
                                  nt_cov(f, ch, xb + 2, yb - 1 + k), tx);
            cv = nt_cubic(col[0], col[1], col[2], col[3], ty);
            cv = (cv - 0.5f) * g + 0.5f;
            a[j * W + i] = (BYTE)(cv <= 0.0f ? 0 : cv >= 1.0f ? 255 : (int)(cv * 255.0f + 0.5f));
        }
    }
    m->am[s] = a; m->amw[s] = W; m->amh[s] = H; m->amx[s] = -1; m->amy[s] = -1;
    nt_mask_stats(m, s);
}
/* look A: the TrueType face at the size whose 'H' matches the game font's cap height at the factor; each glyph's ink
   starts where the game glyph's ink starts and sits on the game font's baseline. */
static void nt_mask_a(NT_FONT *f, NT_AMSET *m, BYTE ch) {
    HDC dc;
    HBITMAP bm, ob;
    HFONT of;
    BITMAPINFO bi;
    DWORD *px = NULL;
    LONG W, H, i, j, l = 0x7fff, pad, base;
    char s[2];
    const LONG *k = f->ink[ch];
    if (!(dc = CreateCompatibleDC(NULL))) return;
    if (!m->hf) {   /* size: cap height of the face measured at 100 px */
        LONG want = (LONG)(f->cap * m->ky + 0.5), px100 = 100, cap100 = 72;
        TEXTMETRICA tm;
        GLYPHMETRICS gm;
        MAT2 id = { {0, 1}, {0, 0}, {0, 0}, {0, 1} };
        const char *face = g_nt_face[0] ? g_nt_face : f->aa ? "Comic Sans MS" : "Arial";
        int wt = f->aa ? FW_NORMAL : FW_BOLD;
        HFONT t = CreateFontA(-px100, 0, 0, 0, wt, 0, 0, 0, ANSI_CHARSET, OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS,
                              ANTIALIASED_QUALITY, DEFAULT_PITCH, face);
        if (t) {
            HFONT o2 = (HFONT)SelectObject(dc, t);
            if (GetGlyphOutlineA(dc, 'H', GGO_METRICS, &gm, 0, NULL, &id) != GDI_ERROR) cap100 = gm.gmBlackBoxY;
            SelectObject(dc, o2); DeleteObject(t);
        }
        if (want < 4) want = 4;
        m->ttpx = (want * px100 + cap100 / 2) / (cap100 > 0 ? cap100 : 72);
        m->hf = CreateFontA(-m->ttpx, 0, 0, 0, wt, 0, 0, 0, ANSI_CHARSET, OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS,
                            ANTIALIASED_QUALITY, DEFAULT_PITCH, face);
        if (m->hf) { of = (HFONT)SelectObject(dc, m->hf); GetTextMetricsA(dc, &tm); m->tta = tm.tmAscent; SelectObject(dc, of); }
        logf("NATIVETEXT> look A: font %d, \"%s\"%s %ld px (game cap %ld x %.3f = %ld px), ascent %ld", f->idx, face, wt == FW_BOLD ? " bold" : "", m->ttpx,
             f->cap, m->ky, want, m->tta);
    }
    if (!m->hf) { DeleteDC(dc); return; }
    pad = m->ttpx / 2 + 2;
    W = (LONG)((f->cell[ch][2] - f->cell[ch][0]) * m->kx) + 2 * pad; H = m->ttpx * 2 + 2 * pad;
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = W; bi.bmiHeader.biHeight = -H;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    bm = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, (void **)&px, NULL, 0);
    if (!bm || !px) { if (bm) DeleteObject(bm); DeleteDC(dc); return; }
    ob = (HBITMAP)SelectObject(dc, bm); of = (HFONT)SelectObject(dc, m->hf);
    memset(px, 0, W * H * 4);
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(255, 255, 255));
    s[0] = (char)ch; s[1] = 0;
    TextOutA(dc, pad, pad, s, 1);
    GdiFlush();
    for (i = 0; i < W; i++) { for (j = 0; j < H; j++) if (px[j * W + i] & 0xff00) break; if (j < H) { l = i; break; } }
    if (l != 0x7fff) {
        BYTE *a = (BYTE *)malloc(W * H);
        if (a) {
            for (j = 0; j < W * H; j++) a[j] = (BYTE)((px[j] >> 8) & 0xff);
            int sl = ch * NT_PH * NT_PH;   /* look A: phase 0 only, placed at the rounded origin */
            base = pad + m->tta;   /* baseline row in the bitmap */
            m->am[sl] = a; m->amw[sl] = W; m->amh[sl] = H;
            m->amx[sl] = (LONG)(k[0] * m->kx + 0.5) - l;
            m->amy[sl] = (LONG)(f->base * m->ky + 0.5) - base;
            nt_mask_stats(m, sl);
        }
    }
    SelectObject(dc, of); SelectObject(dc, ob); DeleteObject(bm); DeleteDC(dc);
}
static NT_AMSET *nt_set(NT_FONT *f, double kx, double ky) {
    int i, lru = 0;
    for (i = 0; i < NT_AMC; i++) {
        NT_AMSET *m = &f->set[i];
        if (m->am && m->look == g_nt_on * 2 + g_nt_phase && fabs(m->kx - kx) < 0.002 && fabs(m->ky - ky) < 0.002) { m->used = ++g_nt_tick; return m; }
        if (f->set[i].used < f->set[lru].used) lru = i;
    }
    {   NT_AMSET *m = &f->set[lru];
        nt_set_free(m);
        m->am = (BYTE **)calloc(NT_AMN, sizeof(BYTE *));
        m->amw = (LONG *)calloc(NT_AMN, sizeof(LONG)); m->amh = (LONG *)calloc(NT_AMN, sizeof(LONG));
        m->amx = (LONG *)calloc(NT_AMN, sizeof(LONG)); m->amy = (LONG *)calloc(NT_AMN, sizeof(LONG));
        m->aml = (LONG *)calloc(NT_AMN, sizeof(LONG)); m->amr = (LONG *)calloc(NT_AMN, sizeof(LONG));
        m->amc = (float *)calloc(NT_AMN, sizeof(float));
        if (!m->am || !m->amw || !m->amh || !m->amx || !m->amy || !m->aml || !m->amr || !m->amc) { nt_set_free(m); return NULL; }
        m->kx = kx; m->ky = ky; m->look = g_nt_on * 2 + g_nt_phase; m->used = ++g_nt_tick;
        return m;
    }
}

/* ---- compose: one enlarged area (a HUD window or a dialog), dest = a + b * native per axis */
typedef struct {
    LONG n[4], d[4];
    double ax, bx, ay, by;
    const WORD *src; LONG stride, sx, sy;    /* native pixel (x, y) = src[(y - sy) * stride + x - sx] */
    int filt;
} NT_TGT;
static NT_REC  *g_nt_v; static int g_nt_vcap;    /* this target's records */
static short   *g_nt_own; static LONG g_nt_owncap; /* native px -> last record (draw order) whose ink covers it, +1 */
static WORD    *g_nt_cln; static LONG g_nt_clncap;
static BYTE    *g_nt_ink; static LONG g_nt_inkcap;
static LONG    *g_nt_tab; static LONG g_nt_tabcap;
static LONG   (*g_nt_vb)[4];                       /* per record: the dest box this pass wrote */
static LONG    *g_nt_hit;                          /* per record: its ink pixels that match the frame */
static DWORD    g_nt_twin, g_nt_fills;
static DWORD    g_nt_sp_n, g_nt_sp_bad, g_nt_gp_bad;   /* spacing check (per 10 s): letter pairs, pairs off by > 0.5 px, gaps off by >= 1.5 px */
static double   g_nt_sp_sum, g_nt_sp_max, g_nt_gp_sum, g_nt_gp_max;
/* per area: last frame's result. Same valid records and same native pixels under them -> the stored dest boxes are
   pasted (most text is static; the ticker is the one that changes every frame). */
typedef struct { LONG n[8]; DWORD sig, hs, used; int nb; LONG (*box)[4]; WORD *px; LONG pxcap, boxcap; } NT_CSLOT;   /* n: area + group box */
#define NT_CS 96
static NT_CSLOT g_nt_cslot[NT_CS];
static DWORD    g_nt_chit, g_nt_cmiss;
static NT_CSLOT **g_nt_gs; static short *g_nt_grp; static int g_nt_ng;   /* this target's groups (nt_target) */
static NT_CSLOT *nt_cslot(const LONG *n) {
    int i, lru = 0;
    for (i = 0; i < NT_CS; i++) {
        if (!memcmp(g_nt_cslot[i].n, n, sizeof(g_nt_cslot[i].n))) { g_nt_cslot[i].used = ++g_nt_tick; return &g_nt_cslot[i]; }
        if (g_nt_cslot[i].used < g_nt_cslot[lru].used) lru = i;
    }
    memcpy(g_nt_cslot[lru].n, n, sizeof(g_nt_cslot[lru].n));
    g_nt_cslot[lru].sig = g_nt_cslot[lru].hs = 0; g_nt_cslot[lru].nb = 0; g_nt_cslot[lru].used = ++g_nt_tick;
    return &g_nt_cslot[lru];
}

static WORD nt_px(const NT_TGT *t, LONG x, LONG y) { return t->src[(y - t->sy) * t->stride + x - t->sx]; }
/* the record's sheet index at surface pixel (x, y): a fill is index 1 (its colour is pal[1]) everywhere */
static BYTE nt_rp(const NT_REC *v, LONG x, LONG y) {
    const NT_FONT *f;
    const LONG *c;
    if (v->kind) return 1;
    f = &g_nt_f[v->fi]; c = f->cell[v->ch];
    return f->pix[(c[1] + y - v->y0) * f->w + c[0] + x - v->x0];
}
static BYTE nt_rkey(const NT_REC *v) { return v->kind ? 0xFF : g_nt_f[v->fi].key; }
static void nt_target(const NT_TGT *t, const NT_SURF *cs, BYTE *bits, LONG pitch, LONG ox, LONG oy, int g6) {
    LONG nw = t->n[2] - t->n[0], nh = t->n[3] - t->n[1], x, y;
    int i, nv = 0, k;
    NT_CSLOT *cl = NULL;
    int dbx = 0;
    if (nw <= 0 || nh <= 0 || !cs || !cs->n) return;
    if (g_nt_vcap < cs->n) {
        free(g_nt_v); free(g_nt_vb); free(g_nt_hit);
        g_nt_v = (NT_REC *)malloc(cs->n * sizeof(NT_REC)); g_nt_vb = (LONG (*)[4])malloc(cs->n * sizeof(g_nt_vb[0]));
        g_nt_hit = (LONG *)malloc(cs->n * sizeof(LONG));
        g_nt_vcap = g_nt_v && g_nt_vb && g_nt_hit ? cs->n : 0;
        if (!g_nt_vcap) return;
    }
    if (g_nt_owncap < nw * nh) {
        free(g_nt_own); free(g_nt_ink);
        g_nt_own = (short *)calloc(nw * nh, sizeof(short)); g_nt_ink = (BYTE *)calloc(nw * nh, 1);
        g_nt_owncap = g_nt_own && g_nt_ink ? nw * nh : 0;
        if (!g_nt_owncap) return;
    }
    for (i = 0; i < cs->n; i++) {   /* the records inside this area, in draw order */
        const NT_REC *r = &cs->r[i];
        LONG mx = (r->x0 + r->x1) / 2, my = (r->y0 + r->y1) / 2;
        NT_REC *v;
        if (mx < t->n[0] || mx >= t->n[2] || my < t->n[1] || my >= t->n[3] || nv >= 32000) continue;
        v = &g_nt_v[nv++]; *v = *r;
        v->c0 = max(v->c0, t->n[0]); v->c1 = max(v->c1, t->n[1]); v->c2 = min(v->c2, t->n[2]); v->c3 = min(v->c3, t->n[3]);
        if (v->c2 <= v->c0 || v->c3 <= v->c1) nv--;
    }
    if (!nv) return;
    for (k = 0; k < nv; k++) {   /* stamp: which record's ink the frame should show at each pixel */
        const NT_REC *v = &g_nt_v[k];
        const NT_FONT *f = &g_nt_f[v->fi];
        const LONG *c = f->cell[v->ch];
        (void)f; (void)c;
        for (y = v->c1; y < v->c3; y++)
            for (x = v->c0; x < v->c2; x++)
                if (nt_rp(v, x, y) != nt_rkey(v)) g_nt_own[(y - t->n[1]) * nw + x - t->n[0]] = (short)(k + 1);
    }
    for (k = 0; k < nv; k++) {   /* verify against the native pixels: 85% of the ink it still owns */
        NT_REC *v = &g_nt_v[k];
        const NT_FONT *f = &g_nt_f[v->fi];
        const LONG *c = f->cell[v->ch];
        LONG vis = 0, own = 0, hit = 0, m0 = 0x7fffffff, m1 = 0x7fffffff, m2 = -0x7fffffff, m3 = -0x7fffffff;
        for (y = v->c1; y < v->c3; y++)
            for (x = v->c0; x < v->c2; x++) {
                BYTE p = nt_rp(v, x, y);
                (void)c;
                if (p == nt_rkey(v)) continue;
                vis++;
                if (g_nt_own[(y - t->n[1]) * nw + x - t->n[0]] != k + 1) continue;
                own++;
                if (p <= 16 && nt_px(t, x, y) == v->pal[p]) {
                    hit++;
                    if (x < m0) m0 = x;
                    if (x + 1 > m2) m2 = x + 1;
                    if (y < m1) m1 = y;
                    if (y + 1 > m3) m3 = y + 1;
                }
            }
        v->batch = own > 0 && hit * 100 >= own * 85;   /* reused as the valid flag */
        g_nt_hit[k] = hit;
        (void)vis;
        if (v->batch && !v->kind && (v->c0 > v->x0 || v->c2 < v->x1 || v->c1 > v->y0 || v->c3 < v->y1) && hit * 100 < f->inkn[v->ch] * 60)
            v->batch = 0;   /* cut (the glyph the ticker is scrolling in at its end): too little of it shows to be sure */
        if (g_nt_dbgfr && dbx < 12 && v->y0 > t->n[1] && (!v->batch || v->c0 != v->x0 || v->c2 != v->x1 || hit < own)) {   /* rejected, cut or covered */
            dbx++;
            logf("NATIVETEXT> diag: area [%ld %ld %ld %ld] glyph '%c' (org %u) %s cell [%ld %ld %ld %ld] clip [%ld %ld %ld %ld] visible ink %ld owned %ld matched %ld of %ld, matched box [%ld %ld %ld %ld]",
                 t->n[0], t->n[1], t->n[2], t->n[3], v->ch, v->org, v->batch ? "drawn" : "REJECTED", v->x0, v->y0, v->x1, v->y1, v->c0, v->c1, v->c2, v->c3,
                 vis, own, hit, f->inkn[v->ch], m0, m1, m2, m3);
        }
        if (!v->batch) g_nt_rej++;
        else if (hit < own) {   /* partly covered (a frame drawn over the ticker's end): only where its ink still shows */
            v->c0 = max(v->c0, m0); v->c1 = max(v->c1, m1); v->c2 = min(v->c2, m2); v->c3 = min(v->c3, m3);
        }
    }
    for (k = 0; k < nv; k++) {   /* one glyph drawn twice: the ticker strip holds the same glyph again 1 or 2 px off (stale
                                    copies from its scroll); of such twins only the one matching the most pixels is drawn */
        NT_REC *a = &g_nt_v[k];
        int j;
        if (!a->batch || a->kind) continue;
        for (j = k + 1; j < nv && a->batch; j++) {
            NT_REC *b = &g_nt_v[j];
            if (!b->batch || b->kind || b->ch != a->ch || b->fi != a->fi || labs(b->x0 - a->x0) > 2 || labs(b->y0 - a->y0) > 2 ||
                b->pal[1] != a->pal[1]) continue;   /* (a shadow, like the compass "N" one 1 px off, is another colour) */
            if (g_nt_hit[j] >= g_nt_hit[k]) a->batch = 0; else b->batch = 0;
            g_nt_twin++;
        }
    }
    for (k = 0; k < nv; k++) {   /* clear the stamp (over the uncut cell); mark the ink that shows, of the valid ones */
        const NT_REC *v = &g_nt_v[k];
        const NT_FONT *f = &g_nt_f[v->fi];
        const LONG *c = f->cell[v->ch];
        LONG s0 = max(v->x0, t->n[0]), s1 = max(v->y0, t->n[1]), s2 = min(v->x1, t->n[2]), s3 = min(v->y1, t->n[3]);
        for (y = s1; y < s3; y++)
            for (x = s0; x < s2; x++) {
                LONG o = (y - t->n[1]) * nw + x - t->n[0];
                BYTE p;
                g_nt_own[o] = 0;
                if (!v->batch || x < v->c0 || x >= v->c2 || y < v->c1 || y >= v->c3) continue;
                p = nt_rp(v, x, y);
                (void)f; (void)c;
                if (p != nt_rkey(v) && p <= 16 && nt_px(t, x, y) == v->pal[p]) g_nt_ink[o] = 1;
            }
    }
    /* The cache, per group of glyphs (a line of text: records whose boxes come within NT_GAP native px). Groups that far
       apart never touch each other's dest pixels (erase margin 2 px, mask overhang under 2 px), so each group's result
       can be pasted or recomputed alone. A group is pasted when its records and the native pixels around them match
       the last frame's; batch becomes 3 (pasted) or 2 (recompute below). */
    {
#define NT_GAP 6
#define NT_GMAX 96
        static LONG gb[NT_GMAX][4];
        static NT_CSLOT *gs[NT_GMAX];
        static short grp[32768];
        int ng = 0, gi, merged;
        for (k = 0; k < nv; k++) {
            const NT_REC *v = &g_nt_v[k];
            grp[k] = -1;
            if (!v->batch) continue;
            for (gi = 0; gi < ng; gi++)
                if (v->c0 < gb[gi][2] + NT_GAP && gb[gi][0] - NT_GAP < v->c2 && v->c1 < gb[gi][3] + NT_GAP && gb[gi][1] - NT_GAP < v->c3) break;
            if (gi == ng) {
                if (ng >= NT_GMAX) gi = ng - 1;   /* (never seen) everything left joins the last group */
                else { gb[ng][0] = v->c0; gb[ng][1] = v->c1; gb[ng][2] = v->c2; gb[ng][3] = v->c3; ng++; }
            }
            grp[k] = (short)gi;
            gb[gi][0] = min(gb[gi][0], v->c0); gb[gi][1] = min(gb[gi][1], v->c1); gb[gi][2] = max(gb[gi][2], v->c2); gb[gi][3] = max(gb[gi][3], v->c3);
        }
        do {   /* groups that grew into each other */
            int a, b;
            merged = 0;
            for (a = 0; a < ng && !merged; a++)
                for (b = a + 1; b < ng && !merged; b++)
                    if (gb[b][0] < gb[a][2] + NT_GAP && gb[a][0] - NT_GAP < gb[b][2] && gb[b][1] < gb[a][3] + NT_GAP && gb[a][1] - NT_GAP < gb[b][3]) {
                        gb[a][0] = min(gb[a][0], gb[b][0]); gb[a][1] = min(gb[a][1], gb[b][1]);
                        gb[a][2] = max(gb[a][2], gb[b][2]); gb[a][3] = max(gb[a][3], gb[b][3]);
                        for (k = 0; k < nv; k++) if (grp[k] == b) grp[k] = (short)a; else if (grp[k] == ng - 1) grp[k] = (short)b;
                        memcpy(gb[b], gb[ng - 1], sizeof(gb[b])); ng--; merged = 1;
                    }
        } while (merged);
        for (gi = 0; gi < ng; gi++) {
            DWORD sig = 2166136261u, hs = 2166136261u;
            LONG geo[8], key[8];
            int nm = 0;
            NT_CSLOT *c2;
            geo[0] = g_nt_on * 2 + g_nt_phase; geo[1] = t->filt; geo[2] = t->d[0]; geo[3] = t->d[1]; geo[4] = t->d[2];
            geo[5] = (LONG)(t->bx * 65536.0); geo[6] = (LONG)(t->by * 65536.0); geo[7] = t->d[3];
            for (i = 0; i < 8; i++) sig = (sig ^ (DWORD)geo[i]) * 16777619u;
            for (k = 0; k < nv; k++) {
                const NT_REC *v = &g_nt_v[k];
                LONG h0, h1, h2, h3;
                if (grp[k] != gi) continue;
                nm++;
                sig = (sig ^ (DWORD)v->x0) * 16777619u; sig = (sig ^ (DWORD)v->y0) * 16777619u;
                sig = (sig ^ (DWORD)(v->c0 | v->c2 << 16)) * 16777619u; sig = (sig ^ (DWORD)(v->c1 | v->c3 << 16)) * 16777619u;
                sig = (sig ^ (DWORD)(v->fi | v->ch << 8 | (DWORD)v->pal[1] << 16)) * 16777619u;
                h0 = max(v->c0 - 5, t->n[0]); h1 = max(v->c1 - 5, t->n[1]); h2 = min(v->c2 + 5, t->n[2]); h3 = min(v->c3 + 5, t->n[3]);
                for (y = h1; y < h3; y++) {
                    const WORD *p = t->src + (y - t->sy) * t->stride - t->sx;
                    for (x = h0; x < h2; x++) hs = (hs ^ p[x]) * 16777619u;
                }
            }
            memcpy(key, t->n, 4 * sizeof(LONG)); memcpy(key + 4, gb[gi], 4 * sizeof(LONG));
            c2 = nt_cslot(key);
            if (c2->nb && c2->sig == sig && c2->hs == hs) {
                const WORD *q = c2->px;
                for (i = 0; i < c2->nb; i++) {
                    const LONG *b = c2->box[i];
                    for (y = b[1]; y < b[3]; y++) { memcpy((WORD *)(bits + (oy + y) * pitch) + ox + b[0], q, (b[2] - b[0]) * 2); q += b[2] - b[0]; }
                }
                g_nt_chit++; g_nt_drawn += nm;
                for (k = 0; k < nv; k++) if (grp[k] == gi) g_nt_v[k].batch = 3;
                gs[gi] = NULL;
            } else {
                c2->sig = sig; c2->hs = hs; c2->nb = 0;   /* filled after the draw below */
                g_nt_cmiss++;
                for (k = 0; k < nv; k++) if (grp[k] == gi) g_nt_v[k].batch = 2;
                gs[gi] = c2;
            }
        }
        cl = ng ? gs[0] : NULL;   /* (non-NULL: something to recompute) */
        for (gi = 0; gi < ng && !cl; gi++) cl = gs[gi];
        g_nt_gs = gs; g_nt_grp = grp; g_nt_ng = ng;
        if (!cl) goto clear_ink;
    }
    for (k = 0; k < nv; k++) { g_nt_vb[k][0] = g_nt_vb[k][1] = 0x7fffffff; g_nt_vb[k][2] = g_nt_vb[k][3] = -0x7fffffff; }
    for (k = 0; k < nv; k++) {   /* erase: inpaint the ink from the pixels around it, resample that box again */
        const NT_REC *v = &g_nt_v[k];
        LONG b0 = max(v->c0 - 2, t->n[0]), b1 = max(v->c1 - 2, t->n[1]), b2 = min(v->c2 + 2, t->n[2]), b3 = min(v->c3 + 2, t->n[3]);
        LONG bw = b2 - b0, bh = b3 - b1, dx0, dx1, dy0, dy1;
        if (v->batch != 2 || bw <= 0 || bh <= 0) continue;
        if (g_nt_clncap < bw * bh) { free(g_nt_cln); g_nt_cln = (WORD *)malloc(bw * bh * 2); g_nt_clncap = g_nt_cln ? bw * bh : 0; if (!g_nt_cln) return; }
        for (y = 0; y < bh; y++) for (x = 0; x < bw; x++) g_nt_cln[y * bw + x] = nt_px(t, b0 + x, b1 + y);
        for (y = 0; y < bh; y++)
            for (x = 0; x < bw; x++) {
                LONG l, rr, u, dd, n = 0, rs = 0, gs = 0, bs = 0;
                WORD q[4];
                int qn = 0, j;
                if (!g_nt_ink[(b1 + y - t->n[1]) * nw + b0 + x - t->n[0]]) continue;
                for (l = x - 1; l >= 0 && g_nt_ink[(b1 + y - t->n[1]) * nw + b0 + l - t->n[0]]; l--) ;
                for (rr = x + 1; rr < bw && g_nt_ink[(b1 + y - t->n[1]) * nw + b0 + rr - t->n[0]]; rr++) ;
                for (u = y - 1; u >= 0 && g_nt_ink[(b1 + u - t->n[1]) * nw + b0 + x - t->n[0]]; u--) ;
                for (dd = y + 1; dd < bh && g_nt_ink[(b1 + dd - t->n[1]) * nw + b0 + x - t->n[0]]; dd++) ;
                if (l >= 0) q[qn++] = nt_px(t, b0 + l, b1 + y);
                if (rr < bw) q[qn++] = nt_px(t, b0 + rr, b1 + y);
                if (u >= 0) q[qn++] = nt_px(t, b0 + x, b1 + u);
                if (dd < bh) q[qn++] = nt_px(t, b0 + x, b1 + dd);
                if (!qn) { g_nt_cln[y * bw + x] = v->pal[16]; continue; }
                for (j = 0; j < qn; j++) {
                    WORD p = q[j];
                    if (g6) { rs += p >> 11; gs += (p >> 5) & 63; } else { rs += (p >> 10) & 31; gs += (p >> 5) & 31; }
                    bs += p & 31; n++;
                }
                rs = (rs + n / 2) / n; gs = (gs + n / 2) / n; bs = (bs + n / 2) / n;
                g_nt_cln[y * bw + x] = g6 ? (WORD)((rs << 11) | (gs << 5) | bs) : (WORD)((rs << 10) | (gs << 5) | bs);
            }
        /* dest pixels whose taps lie in [b0, b2 - 1] x [b1, b3 - 1] */
        dx0 = (LONG)(t->ax + t->bx * (b0 + 1)) - 1; dx1 = (LONG)(t->ax + t->bx * (b2 - 1)) + 2;
        dy0 = (LONG)(t->ay + t->by * (b1 + 1)) - 1; dy1 = (LONG)(t->ay + t->by * (b3 - 1)) + 2;
        dx0 = max(dx0, t->d[0]); dy0 = max(dy0, t->d[1]); dx1 = min(dx1, t->d[2]); dy1 = min(dy1, t->d[3]);
        if (dx1 <= dx0 || dy1 <= dy0) continue;
        g_nt_vb[k][0] = min(g_nt_vb[k][0], dx0); g_nt_vb[k][1] = min(g_nt_vb[k][1], dy0);
        g_nt_vb[k][2] = max(g_nt_vb[k][2], dx1); g_nt_vb[k][3] = max(g_nt_vb[k][3], dy1);
        if (g_nt_tabcap < (dx1 - dx0) + (dy1 - dy0)) {
            free(g_nt_tab); g_nt_tab = (LONG *)malloc(((dx1 - dx0) + (dy1 - dy0)) * 2 * sizeof(LONG));
            g_nt_tabcap = g_nt_tab ? (dx1 - dx0) + (dy1 - dy0) : 0;
            if (!g_nt_tab) return;
        }
        {   /* per dest column / row: source index relative to the box (-1 = a tap outside it), weight 0..256 */
            LONG *tx = g_nt_tab, *ty = g_nt_tab + 2 * (dx1 - dx0);
            for (x = dx0; x < dx1; x++) {
                double uu = (x + 0.5 - t->ax) / t->bx - (t->filt ? 0.5 : 0.0);
                LONG xb = (LONG)floor(uu), fx = t->filt ? (LONG)((uu - xb) * 256.0) : 0;
                if (xb < b0 || xb >= b2 || (xb + 1 >= b2 && fx)) xb = -1; else xb -= b0;
                tx[2 * (x - dx0)] = xb; tx[2 * (x - dx0) + 1] = fx;
            }
            for (y = dy0; y < dy1; y++) {
                double vv = (y + 0.5 - t->ay) / t->by - (t->filt ? 0.5 : 0.0);
                LONG yb = (LONG)floor(vv), fy = t->filt ? (LONG)((vv - yb) * 256.0) : 0;
                if (yb < b1 || yb >= b3 || (yb + 1 >= b3 && fy)) yb = -1; else yb -= b1;
                ty[2 * (y - dy0)] = yb; ty[2 * (y - dy0) + 1] = fy;
            }
            for (y = dy0; y < dy1; y++) {
                LONG yb = ty[2 * (y - dy0)], fy = ty[2 * (y - dy0) + 1];
                const WORD *r0, *r1;
                WORD *o = (WORD *)(bits + (oy + y) * pitch) + ox;
                if (yb < 0) continue;
                r0 = g_nt_cln + yb * bw; r1 = fy ? r0 + bw : r0;
                for (x = dx0; x < dx1; x++) {
                    LONG xb = tx[2 * (x - dx0)], fx = tx[2 * (x - dx0) + 1];
                    WORD a, c;
                    if (xb < 0) continue;
                    if (!fx && !fy) { o[x] = r0[xb]; continue; }
                    a = fx ? rz_hs_lerp(r0[xb], r0[xb + 1], fx, g6) : r0[xb];
                    if (!fy) { o[x] = a; continue; }
                    c = fx ? rz_hs_lerp(r1[xb], r1[xb + 1], fx, g6) : r1[xb];
                    o[x] = rz_hs_lerp(a, c, fy, g6);
                }
            }
        }
    }
    {   static int pk = -1;   /* spacing check: the previous drawn glyph of this pass */
        static double pe; static LONG pr; static double pnr;
        pk = -1;
    for (k = 0; k < nv; k++) {   /* draw */
        const NT_REC *v = &g_nt_v[k];
        NT_FONT *f = &g_nt_f[v->fi];
        NT_AMSET *m;
        const BYTE *a;
        LONG X, Y, q0, q1, q2, q3, W;
        WORD fg = v->pal[1];
        int s, ph = 0;
        double dx0, dy0;
        if (v->batch != 2) continue;
        if (v->kind) {   /* a solid fill (RCI bar): its exact mapped rect, partial coverage on the edge pixels */
            double L = t->ax + t->bx * v->c0, R = t->ax + t->bx * v->c2, T = t->ay + t->by * v->c1, B = t->ay + t->by * v->c3;
            q0 = max((LONG)floor(L), t->d[0]); q2 = min((LONG)floor(R) + 1, t->d[2]);
            q1 = max((LONG)floor(T), t->d[1]); q3 = min((LONG)floor(B) + 1, t->d[3]);
            for (y = q1; y < q3; y++) {
                WORD *o = (WORD *)(bits + (oy + y) * pitch) + ox;
                double cy = min((double)y + 1, B) - max((double)y, T);
                if (cy <= 0) continue;
                for (x = q0; x < q2; x++) {
                    double cv = (min((double)x + 1, R) - max((double)x, L)) * cy;
                    LONG al = cv >= 0.999 ? 256 : (LONG)(cv * 256.0);
                    if (al <= 0) continue;
                    o[x] = al >= 256 ? fg : rz_hs_lerp(o[x], fg, al, g6);
                }
            }
            if (q2 > q0 && q3 > q1) {
                g_nt_vb[k][0] = min(g_nt_vb[k][0], q0); g_nt_vb[k][1] = min(g_nt_vb[k][1], q1);
                g_nt_vb[k][2] = max(g_nt_vb[k][2], q2); g_nt_vb[k][3] = max(g_nt_vb[k][3], q3);
            }
            g_nt_fills++;
            continue;
        }
        if (!(m = nt_set(f, t->bx, t->by))) continue;
        dx0 = t->ax + t->bx * v->x0; dy0 = t->ay + t->by * v->y0;
        if (g_nt_on == 2 && g_nt_phase) {
            ph = (int)((dx0 - floor(dx0)) * NT_PH) + NT_PH * (int)((dy0 - floor(dy0)) * NT_PH);
            if (ph < 0 || ph >= NT_PH * NT_PH) ph = 0;
        }
        s = v->ch * NT_PH * NT_PH + ph;
        if (!m->am[s]) { if (g_nt_on == 1) nt_mask_a(f, m, v->ch); else nt_mask_b(f, m, v->ch, ph); g_nt_maskb++; }
        if (!(a = m->am[s])) continue;
        W = m->amw[s];
        if (g_nt_on == 2 && g_nt_phase) { X = (LONG)floor(dx0) + m->amx[s]; Y = (LONG)floor(dy0) + m->amy[s]; }
        else { X = (LONG)floor(dx0 + 0.5) + m->amx[s]; Y = (LONG)floor(dy0 + 0.5) + m->amy[s]; }
        {   /* spacing check against the native text x factor: glyph centroid error, and the ink gap to the previous glyph */
            double e = X + m->amc[s] - (t->ax + t->bx * (v->x0 + f->cx[v->ch]));
            double nl = v->x0 + f->tl[v->ch], nr = v->x0 + f->tr[v->ch];
            if (pk >= 0 && g_nt_v[pk].y0 == v->y0 && g_nt_v[pk].fi == v->fi && v->x0 > g_nt_v[pk].x0 &&
                v->x0 - g_nt_v[pk].x1 <= 2 && m->aml[s] < m->amr[s]) {
                double de = e - pe, ge = (double)((X + m->aml[s]) - pr) - t->bx * (nl - pnr);
                if (de < 0) de = -de;
                if (ge < 0) ge = -ge;
                g_nt_sp_n++; g_nt_sp_sum += de; if (de > g_nt_sp_max) g_nt_sp_max = de; if (de > 0.5) g_nt_sp_bad++;
                g_nt_gp_sum += ge; if (ge > g_nt_gp_max) g_nt_gp_max = ge; if (ge >= 1.5) g_nt_gp_bad++;
            }
            if (m->aml[s] < m->amr[s]) { pk = k; pe = e; pr = X + m->amr[s]; pnr = nr; }
        }
        q0 = (LONG)floor(t->ax + t->bx * v->c0 + 0.5); q2 = (LONG)floor(t->ax + t->bx * v->c2 + 0.5);
        q1 = (LONG)floor(t->ay + t->by * v->c1 + 0.5); q3 = (LONG)floor(t->ay + t->by * v->c3 + 0.5);
        if (v->c0 == v->x0) q0 -= 2 * (LONG)t->bx + 2;   /* the glyph's own edges: let the mask overhang them */
        if (v->c2 == v->x1) q2 += 2 * (LONG)t->bx + 2;
        if (v->c1 == v->y0) q1 -= 2 * (LONG)t->by + 2;
        if (v->c3 == v->y1) q3 += 2 * (LONG)t->by + 2;
        q0 = max(max(q0, X), t->d[0]); q1 = max(max(q1, Y), t->d[1]);
        q2 = min(min(q2, X + W), t->d[2]); q3 = min(min(q3, Y + m->amh[s]), t->d[3]);
        if (q2 > q0 && q3 > q1) {
            g_nt_vb[k][0] = min(g_nt_vb[k][0], q0); g_nt_vb[k][1] = min(g_nt_vb[k][1], q1);
            g_nt_vb[k][2] = max(g_nt_vb[k][2], q2); g_nt_vb[k][3] = max(g_nt_vb[k][3], q3);
        }
        for (y = q1; y < q3; y++) {
            WORD *o = (WORD *)(bits + (oy + y) * pitch) + ox;
            const BYTE *ar = a + (y - Y) * W - X;
            for (x = q0; x < q2; x++) {
                BYTE al = ar[x];
                if (al) o[x] = al == 255 ? fg : rz_hs_lerp(o[x], fg, al + (al >> 7), g6);
            }
        }
        g_nt_drawn++;
    }
    }
    for (k = 0; k < nv; k++) {
        LONG *b = g_nt_vb[k];
        b[0] = max(b[0], t->d[0]); b[1] = max(b[1], t->d[1]); b[2] = min(b[2], t->d[2]); b[3] = min(b[3], t->d[3]);
    }
    for (i = 0; i < g_nt_ng; i++) {   /* store each recomputed group's result for the next frame */
        LONG need = 0, nb = 0;
        WORD *q;
        if (!(cl = g_nt_gs[i])) continue;
        for (k = 0; k < nv; k++) {
            const LONG *b = g_nt_vb[k];
            if (g_nt_grp[k] == i && g_nt_v[k].batch == 2 && b[2] > b[0] && b[3] > b[1]) { need += (b[2] - b[0]) * (b[3] - b[1]); nb++; }
        }
        if (cl->pxcap < need) { free(cl->px); cl->px = (WORD *)malloc(need * 2); cl->pxcap = cl->px ? need : 0; }
        if (cl->boxcap < nb) { free(cl->box); cl->box = (LONG (*)[4])malloc(nb * sizeof(cl->box[0])); cl->boxcap = cl->box ? nb : 0; }
        if (cl->pxcap < need || cl->boxcap < nb) continue;
        q = cl->px;
        for (k = 0; k < nv; k++) {
            const LONG *b = g_nt_vb[k];
            if (g_nt_grp[k] != i || g_nt_v[k].batch != 2 || b[2] <= b[0] || b[3] <= b[1]) continue;
            memcpy(cl->box[cl->nb++], b, sizeof(cl->box[0]));
            for (y = b[1]; y < b[3]; y++) { memcpy(q, (WORD *)(bits + (oy + y) * pitch) + ox + b[0], (b[2] - b[0]) * 2); q += b[2] - b[0]; }
        }
    }
clear_ink:
    for (k = 0; k < nv; k++) {   /* clear the ink marks */
        const NT_REC *v = &g_nt_v[k];
        for (y = v->c1; y < v->c3; y++) memset(g_nt_ink + (y - t->n[1]) * nw + v->c0 - t->n[0], 0, v->c2 - v->c0);
    }
}

/* HUD pass hook-up 1: after the enlarged HUD (and MININAT), before the native and enlarged dialogs */
static void nt_hud(void *comp, int n, BYTE *bits, LONG pitch, LONG ox, LONG oy, LONG cw, LONG ch, int g6, double s) {
    NT_SURF *cs;
    NT_TGT t;
    LARGE_INTEGER t0, t1;
    ULONG64 c0, c1;
    int i;
    nt_install();
    nt_rci_install();
    if (g_nt_ctl[0]) {   /* diag: live look switch */
        static DWORD lt;
        if (GetTickCount() - lt > 500) {
            HANDLE h = CreateFileA(g_nt_ctl, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
            lt = GetTickCount();
            if (h != INVALID_HANDLE_VALUE) {
                char b[4] = {0};
                DWORD rd;
                if (ReadFile(h, b, 2, &rd, NULL) && rd && b[0] >= '0' && b[0] <= '2' &&
                    (b[0] - '0' != g_nt_on || (rd > 1 && (b[1] == '0' || b[1] == '1') && b[1] - '0' != g_nt_phase))) {
                    g_nt_on = b[0] - '0';
                    if (rd > 1 && (b[1] == '0' || b[1] == '1')) g_nt_phase = b[1] - '0';
                    logf("NATIVETEXT> look switched to %d (phase %d) by %s", g_nt_on, g_nt_phase, g_nt_ctl);
                }
                CloseHandle(h);
            }
        }
    }
    if (!g_nt_on || !g_nt_csok) return;
    g_nt_dbgfr = g_nt_dbgnow; g_nt_dbgnow = 0;
    QueryPerformanceCounter(&t0);
    rz_hp_cyc(&c0);
    EnterCriticalSection(&g_nt_cs);
    cs = nt_surf(comp, 0);
    for (i = 0; cs && i < n; i++) {
        memcpy(t.n, g_hs_src[i], sizeof(t.n)); memcpy(t.d, g_hs_dst[i], sizeof(t.d));
        t.bx = t.by = s; t.ax = cw * (1.0 - s); t.ay = ch * (1.0 - s);
        t.src = g_hs_snap; t.stride = cw; t.sx = 0; t.sy = 0; t.filt = g_hs_filter;
        nt_target(&t, cs, bits, pitch, ox, oy, g6);
    }
    LeaveCriticalSection(&g_nt_cs);
    QueryPerformanceCounter(&t1);
    rz_hp_cyc(&c1);
    g_nt_time += t1.QuadPart - t0.QuadPart; g_nt_frames++; g_nt_cyc += c1 - c0;
    if (!g_nt_beat) g_nt_beat = GetTickCount();
    if (GetTickCount() - g_nt_beat >= 10000) {
        logf("NATIVETEXT> %lu frames: %.3f ms, %.2f M thread cycles per frame (HUD + dialogs); %lu glyphs drawn per frame, %lu rejected per frame (frame pixels differ); areas pasted from the cache %lu, recomputed %lu; %lu twins dropped, %lu self-Blt moves; %lu masks built, %ld records held",
             g_nt_frames, g_freq.QuadPart ? 1000.0 * (double)g_nt_time / (double)g_freq.QuadPart / g_nt_frames : 0.0,
             (double)g_nt_cyc / 1e6 / g_nt_frames, g_nt_drawn / g_nt_frames, g_nt_rej / g_nt_frames, g_nt_chit, g_nt_cmiss, g_nt_twin, g_nt_selfmv, g_nt_maskb, g_nt_total);
        g_nt_twin = 0; g_nt_selfmv = 0;
        if (g_nt_sp_n || g_nt_fills)
            logf("NATIVETEXT> spacing (look %d, %s): %lu letter pairs redrawn, centroid spacing error vs native x factor mean %.3f max %.3f px, %lu pairs > 0.5 px; ink gap error mean %.3f max %.3f px, %lu gaps >= 1.5 px; %lu fills drawn",
                 g_nt_on, g_nt_on == 2 ? (g_nt_phase ? "sub-pixel phase" : "rounded origin") : "rounded origin",
                 g_nt_sp_n, g_nt_sp_n ? g_nt_sp_sum / g_nt_sp_n : 0.0, g_nt_sp_max, g_nt_sp_bad,
                 g_nt_sp_n ? g_nt_gp_sum / g_nt_sp_n : 0.0, g_nt_gp_max, g_nt_gp_bad, g_nt_fills);
        g_nt_sp_n = g_nt_sp_bad = g_nt_gp_bad = g_nt_fills = 0; g_nt_sp_sum = g_nt_sp_max = g_nt_gp_sum = g_nt_gp_max = 0;
        if (g_nt_log >= 2) g_nt_dbgnow = 1;   /* the next frame logs one diag line per area */
        g_nt_beat = GetTickCount(); g_nt_frames = 0; g_nt_time = 0; g_nt_cyc = 0; g_nt_drawn = g_nt_rej = g_nt_maskb = 0; g_nt_chit = g_nt_cmiss = 0;
    }
}
/* hook-up 2: after each enlarged dialog (or cost label) is drawn */
static void nt_dlg(void *comp, const HD_SLOT *d, BYTE *bits, LONG pitch, LONG ox, LONG oy, int g6) {
    NT_SURF *cs;
    NT_TGT t;
    LARGE_INTEGER t0, t1;
    ULONG64 c0, c1;
    if (!g_nt_on || !g_nt_csok || !d->dw || !d->w || !d->h) return;
    QueryPerformanceCounter(&t0);
    rz_hp_cyc(&c0);
    EnterCriticalSection(&g_nt_cs);
    if ((cs = nt_surf(comp, 0)) != NULL) {
        memcpy(t.n, d->nat, sizeof(t.n)); memcpy(t.d, d->dst, sizeof(t.d));
        t.bx = (double)d->dw / d->w; t.by = (double)d->dh / d->h;
        t.ax = d->dst[0] - d->nat[0] * t.bx; t.ay = d->dst[1] - d->nat[1] * t.by;
        t.src = d->prev; t.stride = d->w; t.sx = d->nat[0]; t.sy = d->nat[1]; t.filt = g_hs_filter;   /* prev = this frame's (swapped) */
        nt_target(&t, cs, bits, pitch, ox, oy, g6);
    }
    LeaveCriticalSection(&g_nt_cs);
    QueryPerformanceCounter(&t1);
    rz_hp_cyc(&c1);
    g_nt_time += t1.QuadPart - t0.QuadPart; g_nt_cyc += c1 - c0;
}
