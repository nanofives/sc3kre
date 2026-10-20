/* sc3netmod_rbt.c - the RBT block of sc3netmod.dll (task roundabout3, 2026-10-14): automatic 2x2 roundabouts.
 * #included by sc3netmod.c after the TMPL block; shares the variant table, patch helpers, log and save hooks.
 * Rule, evidence and owner guide: re/analysis/MULTITILE.md section 5, verify/roundabout3/.
 *
 * A package declares `rbt <piece> <min_arms>` (netpack manifest "auto_roundabouts"; piece = a ROAD variant of T 39,
 * art and lanes for the pinwheel states 3,0 / 2,1). A block = the 2x2 of ROAD cells with origin (X, Z). It becomes
 * that piece (same states) when ALL hold, and goes back to the stock tiles when one stops holding:
 *  (a) the 4 cells are the stock pinwheel: (X,Z) state 3, (X+1,Z) 0, (X+1,Z+1) 1, (X,Z+1) 2, each T 39 when its exit
 *      holds road and curve 11203 when it does not (the piece itself counts as either);
 *  (b) no closed cell (X-1,Z+1) (X,Z-1) (X+2,Z) (X+1,Z+2) holds road;
 *  (c) no exit that holds road is part of a 2x2 of road outside the block (the exit, the corner beside it and the two
 *      cells beyond them): a 2-wide road or another 2x2 block;
 *  (d) at least min_arms of the exits W (X-1,Z), N (X+1,Z-1), E (X+2,Z+1), S (X,Z+2) hold road.
 * "Road" = an occupant of the surface layer (manager +0x3c) that the manager's network test vt+0x14c accepts for
 * netType 1 (FUN_10007791 -> the ROAD predicate DAT_100323c0, the one the rect retile gathers its nodes with).
 * Offline twin: re/tools/netmod/rb_auto.py (same rule on a save).
 *
 * When: (1) after every ROAD call of the retile pass FUN_1001547b (entry hooked; all three callers, the rect retile
 * FUN_100151f1, the drag build FUN_10014a23 and the On-ramp build FUN_1000abde, go through it), over the blocks whose
 * cells or surroundings fall in the box of the pass's work list (its 4th argument, written by the pass); (2) once
 * after a city load (manager vt+0x1c = FUN_100130e9 wrapped; the pass runs from a message posted to the game window,
 * so on the UI thread after the load call returns), over the whole map.
 * Convert = the game's piece writer FUN_10008919 per cell (as the TMPL click), free (the road is paid for). Revert =
 * the rect retile FUN_100151f1 (manager vt+0xb0, mask 3) over the block: the piece is NOT in the Protected list, so
 * the stock tiler re-places the cells as it would for road; any later retile that reaches the block does the same.
 * Save: SAVEBASE writes the stock id of each cell (39, or 11203 for a cell without an arm), not just the base id.
 * Off: SC3NETMOD_RBT=0 (whole block), SC3NETMOD_RBT_LOAD=0 (no pass after a load).
 *
 * Task roundabout4: `rbt <piece> <min_arms> <closed>` names a second variant of T 39 for the quarter whose exit holds
 * no road (art closed on that side, lanes only round the ring). Each block cell then becomes <piece> when its exit
 * holds road and <closed> when it does not, in the cell's own state; (a) counts either piece as either stock tile.
 * <closed> is always saved as curve 11203 (it only ever sits on an arm-less quarter). Without the third number the
 * block behaves as in roundabout3 (every quarter <piece>).
 */

#define RB_WM (WM_APP + 0x5D1)

typedef void (__fastcall *PFN_Pass)(void *mgr, void *edx, DWORD list, int net, int *box);   /* FUN_1001547b ret 0xc */
typedef char (__fastcall *PFN_At)(void *lay, void *edx, int x, int z, void **out);          /* layer vt+0x7c ret 0xc */
typedef char (__fastcall *PFN_Load)(void *mgr, void *edx, void *p1, void *p2);              /* FUN_100130e9 ret 8 */

static WORD g_rb_piece, g_rb_closed;          /* g_rb_closed: arm-less quarter piece, 0 = none (roundabout4) */
static int g_rb_min = 3, g_rb_on;
static BYTE *g_rb_m;
static DWORD g_rb_msize;
static DWORD g_rb_eh, g_rb_cont, g_rb_orig_load;
static volatile LONG g_rb_busy, g_rb_load_pending;
static void *g_rb_mgr;
static BYTE *g_rb_stock;                     /* [z * 1024 + x]: 0 unknown, 1 stock T 39, 2 stock curve 11203 */
static HWND g_rb_hwnd;
static WNDPROC g_rb_oldproc;
static volatile LONG g_rb_n_pass, g_rb_n_conv, g_rb_n_rev, g_rb_n_load, g_rb_n_fault;
static int g_rb_logged_box;

static const signed char RB_CELL[4][3] = { { 0, 0, 3 }, { 1, 0, 0 }, { 1, 1, 1 }, { 0, 1, 2 } };  /* dx, dz, state */
static const signed char RB_EXIT[4][2] = { { 1, -1 }, { 2, 1 }, { 0, 2 }, { -1, 0 } };     /* by state 0..3 */
static const signed char RB_CORNER[4][2] = { { 2, -1 }, { 2, 2 }, { -1, 2 }, { -1, -1 } };
static const signed char RB_OUT[4][2] = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } };
static const signed char RB_CLOSED[4][2] = { { -1, 1 }, { 0, -1 }, { 2, 0 }, { 1, 2 } };

/* task diagave: the DAV block (sc3netmod_dav.c, #included after this file) shares these hooks */
static WORD g_dav_inner[3];
static int g_dav_on, g_rb_off;
static void dav_line(const char *path, const char *line);
static void dav_jline(const char *path, const char *line);
static void dav_mline(const char *path, const char *line);
static void dav_sline(const char *path, const char *line);
static void dav_xline(const char *path, const char *line);       /* task diagx: crossings */
static void dav_xgline(const char *path, const char *line);
static void dav_xwline(const char *path, const char *line);
static void dav_oline(const char *path, const char *line);       /* task avdiag: davu / davn / davt */
static void dav_init_table(void);
static void dav_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);
static int dav_is_mid(WORD id);
static int dav_save_43(WORD id);
/* task avx: the AVX block (sc3netmod_avx.c, #included after sc3netmod_dav.c) shares these hooks */
static int g_avx_on, g_avx_nbox;
static void avx_line(const char *path, const char *line);
static void avx_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);
static WORD avx_save_id(WORD id);
static WORD g_bv_p[7];                                                       /* task boulevard: BV block */
static void bv_line(const char *path, const char *line);                     /* task boulevard */
static void bv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);  /* task boulevard */
/* task bigrbt: the RBT9 block (sc3netmod_rbt9.c, #included after DAV) runs on these hooks too */
static WORD g_r9_centre;
static void r9_line(const char *path, const char *line);
static int r9_complete(void);
static void r9_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);
static void r9_stats(void);
static int g_bvx_nbox;                                                       /* task bvx: sc3netmod_bvx.c */
static void bvx_line(const char *path, const char *line);                    /* task bvx */
static WORD g_dbv_out;                                                       /* task diagbv: DBV block */
static int g_dbv_on;                                                         /* task diagbv */
static void dbv_line(const char *path, const char *line);                    /* task diagbv */
static void dbv_run(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who); /* task diagbv */
static int dbv_claimed(int x, int z);                                        /* task diagbv: DAV / BV stop there */
struct HwyPass;                                                              /* task hwcore: HWY base (sc3netmod_hwy.c) */
static int g_hwy_np;                                                         /* task hwcore */
static void hwy_line(const char *path, const char *line);                    /* task hwcore */
static struct HwyPass *hwy_begin(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);   /* task hwcore */
static void hwy_end(struct HwyPass *hp);                                     /* task hwcore */
static WORD hwy_save_id(WORD id);                                            /* task hwcore */
static int hwy_install(void);                                                /* task hwcore */
static void hwy_stats(void);                                                 /* task hwcore */
static void hwt_line(const char *path, const char *line);                    /* task hwt */
static void hwt_run(struct HwyPass *hp);                                     /* task hwt */
static void hwt_stats(void);                                                 /* task hwt */
static void hwx_line(const char *path, const char *line);                    /* task hwx */
static void hwx_run(struct HwyPass *hp);                                     /* task hwx */
static void hwx_stats(void);                                                 /* task hwx */
static void hwdd_run(struct HwyPass *hp);                                    /* task hwdd */
static void hwdd_stats(void);                                                /* task hwdd */
static void hwdx_run(struct HwyPass *hp);                                    /* task hwdx */
static void hwdx_stats(void);                                                /* task hwdx */
static void hwask_line(const char *path, const char *line);                  /* task hwask */
static void hwask_stats(void);                                               /* task hwask */
static void hwave_line(const char *path, const char *line);                  /* task hwave */
static void hwave_run(struct HwyPass *hp);                                   /* task hwave */
static void hwave_road(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who, int pre);   /* task hwave */
static void hwavd_line(const char *path, const char *line);                  /* task hwave */
static int hwave_claimed(int x, int z);                                      /* task hwave: DAV skips them */
static int g_avl_on;                                                         /* task avcore: AVL block (sc3netmod_avl.c) */
static WORD g_avl_straight;                                                  /* task avcore */
static void avl_line(const char *path, const char *line);                    /* task avcore */
static void avl_pass(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who);  /* task avcore */
static void avl_stats(void);                                                 /* task avcore */
static void hwave_stats(void);                                               /* task hwave */

/* ---------------------------------------------------------------- table line */
static void rb_file(const char *path) {
    char line[256];
    FILE *f = fopen(path, "r");
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        unsigned long p, n, c = 0;
        int k;
        if (!strncmp(line, "davj ", 5)) { dav_jline(path, line); continue; }      /* task diagave: junctions */
        if (!strncmp(line, "davm ", 5)) { dav_mline(path, line); continue; }      /* task diagave: merges */
        if (!strncmp(line, "davs ", 5)) { dav_sline(path, line); continue; }      /* task diagave: save as 43 */
        if (!strncmp(line, "davx ", 5)) { dav_xline(path, line); continue; }      /* task diagx: crossings */
        if (!strncmp(line, "davxg ", 6)) { dav_xgline(path, line); continue; }    /* task diagx */
        if (!strncmp(line, "davxw ", 6)) { dav_xwline(path, line); continue; }    /* task diagx */
        if (!strncmp(line, "davu ", 5) || !strncmp(line, "davn ", 5) || !strncmp(line, "davt ", 5)) { dav_oline(path, line); continue; }   /* task avdiag */
        if (!strncmp(line, "dav ", 4)) { dav_line(path, line); continue; }        /* task diagave */
        if (!strncmp(line, "avx", 3)) { avx_line(path, line); continue; }         /* task avx */
        if (!strncmp(line, "bvx", 3)) { bvx_line(path, line); continue; }         /* task bvx */
        if (!strncmp(line, "bv", 2) && line[3] == ' ') { bv_line(path, line); continue; }   /* task boulevard */
        if (!strncmp(line, "avl", 3) && line[4] == ' ') { avl_line(path, line); continue; }   /* task avcore */
        if (!strncmp(line, "rbt9 ", 5)) { r9_line(path, line); continue; }       /* task bigrbt */
        if (!strncmp(line, "dbvb ", 5) || !strncmp(line, "dbvs ", 5)) { dbv_line(path, line); continue; } /* task diagbv */
        if (!strncmp(line, "hwt ", 4) || !strncmp(line, "hwtc ", 5)) { hwt_line(path, line); continue; } /* task hwt (hwtc: task hwcap2) */
        if (!strncmp(line, "hwx ", 4)) { hwx_line(path, line); continue; } /* task hwx */
        if (!strncmp(line, "hwask ", 6)) { hwask_line(path, line); continue; } /* task hwask */
        if (!strncmp(line, "hwave ", 6)) { hwave_line(path, line); continue; } /* task hwave */
        if (!strncmp(line, "hwavd ", 6)) { hwavd_line(path, line); continue; } /* task hwave */
        if (!strncmp(line, "hwrc ", 5)) continue;                            /* task hwave: read by NETRAMP */
        if (!strncmp(line, "hwy", 3)) { hwy_line(path, line); continue; }  /* task hwcore */
        if (strncmp(line, "rbt ", 4) || g_rb_off) continue;
        k = sscanf(line + 4, "%lu %lu %lu", &p, &n, &c);
        if (k < 2 || !p || p > 0xffff || n < 1 || n > 4 || g_base[p] != 39 ||
            (k == 3 && (!c || c > 0xffff || c == p || g_base[c] != 39))) {
            logf("### rbt: %s: bad line or piece not a variant of T 39: '%s'", path, line);
            continue;
        }
        if (k < 3) c = 0;
        if (g_rb_piece && g_rb_piece != (WORD)p) {
            logf("### rbt: %s: a second roundabout piece %lu (already %u) - ignored", path, p, g_rb_piece);
            continue;
        }
        g_rb_piece = (WORD)p; g_rb_min = (int)n; g_rb_closed = (WORD)c;
        logf("rbt: %s: automatic 2x2 roundabout = piece %lu, at least %lu arm(s), arm-less quarter %lu%s", path, p, n,
             c, c ? "" : " (none: every quarter is the piece)");
    }
    fclose(f);
}

/* ---------------------------------------------------------------- reading cells */
/* -> 0 = no road, else 0x80000000 | state << 16 | id. The occupant of a network piece: +0x10 word0 (state bits
   30-31), +0x14 low 16 = id (np_drive.py cells, QUERY_ID.md 2). */
static DWORD rb_read(BYTE *mgr, void *lay, int x, int z, int W, int H) {
    void *occ = NULL;
    DWORD r = 0, vt;
    if (x < 0 || z < 0 || x >= W || z >= H) return 0;
    if (!((PFN_At)VT(lay, 0x7c))(lay, 0, x, z, &occ) || !occ) return 0;
    vt = *(DWORD *)occ;
    if (vt >= (DWORD)g_rb_m && vt < (DWORD)g_rb_m + g_rb_msize && ((PFN_Pred)VT(mgr, 0x14c))(mgr, 0, 1, occ))
        r = 0x80000000UL | ((*(DWORD *)((BYTE *)occ + 0x10) >> 30) << 16) | (*(DWORD *)((BYTE *)occ + 0x14) & 0xffff);
    ((PFN_B0)VT(occ, 8))(occ);
    return r;
}

typedef struct { int x0, z0, w, h; DWORD *c; } RbBuf;

static DWORD rb_at(RbBuf *b, int x, int z) {
    x -= b->x0; z -= b->z0;
    if (x < 0 || z < 0 || x >= b->w || z >= b->h) return 0;
    return b->c[z * b->w + x];
}

/* the rule; -> arms (>= min) when the block qualifies, else -1 (why in *why) */
static int rb_check(RbBuf *b, int X, int Z, const char **why) {
    int k, arms = 0;
    DWORD c[4];
    for (k = 0; k < 4; k++) {
        DWORD v = rb_at(b, X + RB_CELL[k][0], Z + RB_CELL[k][1]), id = v & 0xffff;
        if (!v || (int)((v >> 16) & 3) != RB_CELL[k][2] ||
            (id != 39 && id != 11203 && id != g_rb_piece && (!g_rb_closed || id != g_rb_closed))) {
            *why = "a"; return -1;
        }
        c[k] = id;
    }
    for (k = 0; k < 4; k++) {
        int s = RB_CELL[k][2], ex = X + RB_EXIT[s][0], ez = Z + RB_EXIT[s][1];
        int has = rb_at(b, ex, ez) != 0;
        if ((c[k] == 39 && !has) || (c[k] == 11203 && has)) { *why = "a (stock tile disagrees with its exit)"; return -1; }
        if (has) {
            int cx = X + RB_CORNER[s][0], cz = Z + RB_CORNER[s][1], ox = RB_OUT[s][0], oz = RB_OUT[s][1];
            if (rb_at(b, cx, cz) && rb_at(b, ex + ox, ez + oz) && rb_at(b, cx + ox, cz + oz)) {
                *why = "c (exit in a 2x2 of road)"; return -1;
            }
            arms++;
        }
    }
    for (k = 0; k < 4; k++)
        if (rb_at(b, X + RB_CLOSED[k][0], Z + RB_CLOSED[k][1])) { *why = "b (closed cell holds road)"; return -1; }
    if (arms < g_rb_min) { *why = "d (arms)"; return -1; }
    return arms;
}

/* ---------------------------------------------------------------- the pass over block origins [ox0..ox1] x [oz0..oz1] */
static void rb_run(BYTE *mgr, int ox0, int oz0, int ox1, int oz1, const char *who) {
    void *lay = *(void **)(mgr + 0x3c);
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1;
    int x, z, k, nconv = 0, nrev = 0, nq = 0;
    RbBuf b;
    BYTE *q;
    if (W < 2 || H < 2 || W > 4096 || H > 4096) return;
    if (ox0 < 0) ox0 = 0;
    if (oz0 < 0) oz0 = 0;
    if (ox1 > W - 2) ox1 = W - 2;
    if (oz1 > H - 2) oz1 = H - 2;
    if (ox0 > ox1 || oz0 > oz1) return;
    b.x0 = ox0 - 2; b.z0 = oz0 - 2; b.w = ox1 - ox0 + 6; b.h = oz1 - oz0 + 6;
    b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)b.w * b.h * 4 + (SIZE_T)(ox1 - ox0 + 1) * (oz1 - oz0 + 1), MEM_COMMIT,
                                PAGE_READWRITE);
    if (!b.c) return;
    q = (BYTE *)(b.c + b.w * b.h);                    /* q[origin] = 1 qualifies */
    for (z = 0; z < b.h; z++)
        for (x = 0; x < b.w; x++) b.c[z * b.w + x] = rb_read(mgr, lay, b.x0 + x, b.z0 + z, W, H);
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            const char *why = "";
            int arms = rb_check(&b, x, z, &why), need = 0;
            WORD want[4];
            if (arms < 0) continue;
            q[(z - oz0) * (ox1 - ox0 + 1) + (x - ox0)] = 1;
            nq++;
            for (k = 0; k < 4; k++) {
                int cx = x + RB_CELL[k][0], cz = z + RB_CELL[k][1], s = RB_CELL[k][2];
                int has = rb_at(&b, x + RB_EXIT[s][0], z + RB_EXIT[s][1]) != 0;
                want[k] = (has || !g_rb_closed) ? g_rb_piece : g_rb_closed;     /* roundabout4: arm-less quarter */
                if ((rb_at(&b, cx, cz) & 0xffff) != want[k]) need = 1;
                if (g_rb_stock && cx < 1024 && cz < 1024) g_rb_stock[cz * 1024 + cx] = has ? 1 : 2;
            }
            if (!need) continue;
            for (k = 0; k < 4; k++) {
                int pos[3];
                pos[0] = (x + RB_CELL[k][0]) << 8; pos[1] = (z + RB_CELL[k][1]) << 8; pos[2] = 0;
                ((PFN_Put)(g_rb_m + 0x8919))(mgr, 0, lay, pos, ((DWORD)want[k] << 8) | RB_CELL[k][2], -1, 8, 0);
            }
            nconv++;
            logf("rbt: %s: (%d,%d) -> roundabout, %d arm(s): %u %u / %u %u", who, x, z, arms, want[0], want[1], want[3],
                 want[2]);
        }
    /* 20400 cells of blocks (origin in range) that do not qualify: back to the stock tiles */
    for (z = oz0; z <= oz1; z++)
        for (x = ox0; x <= ox1; x++) {
            int found = 0, rect[6];
            if (q[(z - oz0) * (ox1 - ox0 + 1) + (x - ox0)]) continue;
            for (k = 0; k < 4 && !found; k++) {
                DWORD v = rb_at(&b, x + RB_CELL[k][0], z + RB_CELL[k][1]);
                found = ((v & 0xffff) == g_rb_piece || (g_rb_closed && (v & 0xffff) == g_rb_closed)) &&
                        (int)((v >> 16) & 3) == RB_CELL[k][2];
            }
            if (!found) continue;
            rect[0] = x << 8; rect[1] = z << 8; rect[2] = 0; rect[3] = (x + 1) << 8; rect[4] = (z + 1) << 8; rect[5] = 0;
            ((PFN_Retile)VT(mgr, 0xb0))(mgr, 0, rect, 3);
            nrev++;
            {
                const char *why = "";
                rb_check(&b, x, z, &why);
                logf("rbt: %s: (%d,%d) roundabout cells, block no longer qualifies (%s) -> stock retile", who, x, z, why);
            }
        }
    VirtualFree(b.c, 0, MEM_RELEASE);
    InterlockedExchangeAdd(&g_rb_n_conv, nconv);
    InterlockedExchangeAdd(&g_rb_n_rev, nrev);
    if (nconv || nrev || !strcmp(who, "load"))
        logf("rbt: %s pass over origins (%d,%d)-(%d,%d) [tid %04lx]: %d qualify, %d converted, %d reverted", who, ox0,
             oz0, ox1, oz1, GetCurrentThreadId(), nq, nconv, nrev);
}

/* ---------------------------------------------------------------- the retile pass hook (FUN_1001547b entry) */
static __declspec(naked) void rb_tramp(void) {
    __asm {
        mov eax, dword ptr [g_rb_eh]
        jmp dword ptr [g_rb_cont]
    }
}

/* task hwcore: a highway retile (net 4) or the load pass: the HWY base, then every highway shape block */
static void rb_hwy(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    struct HwyPass *hp = hwy_begin(mgr, x0, z0, x1, z1, who);
    if (!hp) return;
    /* highway shape blocks, one line each (task hwx, hwt, hwdx, hwdd): <block>_run(hp); */
    hwt_run(hp);                                                                 /* task hwt */
    hwx_run(hp);                                                                 /* task hwx */
    hwdd_run(hp);                                                            /* task hwdd */
    hwdx_run(hp);                                                            /* task hwdx */
    hwave_run(hp);                                                           /* task hwave */
    hwy_end(hp);
}

static void __fastcall rb_pass(BYTE *mgr, void *edx, DWORD list, int net, int *box) {
    int x0, z0, x1, z1;
    ((PFN_Pass)(void *)rb_tramp)(mgr, edx, list, net, box);
    if (net == 4 && box && !g_rb_busy && g_hwy_np && box[0] != 0x7fffffff && box[1] != 0x7fffffff) {  /* task hwcore */
        g_rb_mgr = mgr;
        InterlockedIncrement(&g_rb_busy);
        __try {
            rb_hwy(mgr, min(box[0], box[3]) >> 8, min(box[1], box[4]) >> 8, max(box[0], box[3]) >> 8,
                   max(box[1], box[4]) >> 8, "edit");
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            InterlockedIncrement(&g_rb_n_fault);
            logf("### hwy: exception 0x%08lX in the highway pass", GetExceptionCode());
        }
        InterlockedDecrement(&g_rb_busy);
        return;
    }
    if (net != 1 || !box || g_rb_busy) return;
    g_rb_mgr = mgr;
    if (box[0] == 0x7fffffff || box[1] == 0x7fffffff || box[3] == 0x7fffffff || box[4] == 0x7fffffff) return;
    x0 = min(box[0], box[3]) >> 8; x1 = max(box[0], box[3]) >> 8;
    z0 = min(box[1], box[4]) >> 8; z1 = max(box[1], box[4]) >> 8;
    if (g_rb_logged_box < 6) {
        g_rb_logged_box++;
        logf("rbt: retile pass ROAD [tid %04lx], work box {%d,%d,%d,%d,%d,%d} -> cells (%d,%d)-(%d,%d)",
             GetCurrentThreadId(), box[0], box[1], box[2], box[3], box[4], box[5], x0, z0, x1, z1);
    }
    InterlockedIncrement(&g_rb_n_pass);
    InterlockedIncrement(&g_rb_busy);
    __try {
        if (g_rb_piece) rb_run(mgr, x0 - 3, z0 - 3, x1 + 2, z1 + 2, "edit");   /* blocks whose cells/ring/beyond touch the box */
        if (g_hwy_np) hwave_road(mgr, x0, z0, x1, z1, "road", 1);            /* task hwave: before DAV, claims */
        dbv_run(mgr, x0, z0, x1, z1, "edit");                  /* task diagbv: first, its claims stop DAV / BV */
        if (g_dav_on) dav_run(mgr, x0, z0, x1, z1, "edit");                  /* task diagave */
        if (g_avx_on) avx_run(mgr, x0, z0, x1, z1, "edit");                  /* task avx */
        if (g_bv_p[0]) bv_run(mgr, x0, z0, x1, z1, "edit");                  /* task boulevard */
        if (g_r9_centre) r9_run(mgr, x0, z0, x1, z1, "edit");                /* task bigrbt */
        if (g_hwy_np) hwave_road(mgr, x0, z0, x1, z1, "road", 0);            /* task hwave: after DAV, builds */
        if (g_avl_on) avl_pass(mgr, x0, z0, x1, z1, "edit");                 /* task avcore: last (+ its post hooks) */
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_rb_n_fault);
        logf("### rbt: exception 0x%08lX in the edit pass", GetExceptionCode());
    }
    InterlockedDecrement(&g_rb_busy);
}

/* ---------------------------------------------------------------- after a load */
static void rb_load_pass(void) {
    BYTE *mgr = (BYTE *)g_rb_mgr;
    if (!mgr || !InterlockedExchange(&g_rb_load_pending, 0)) return;
    InterlockedIncrement(&g_rb_n_load);
    InterlockedIncrement(&g_rb_busy);
    __try {
        if (g_rb_piece) rb_run(mgr, 0, 0, 0x7fffffff, 0x7fffffff, "load");
        if (g_hwy_np) hwave_road(mgr, 0, 0, 0x7fffff, 0x7fffff, "load", 1);  /* task hwave: before DAV, claims */
        dbv_run(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");        /* task diagbv: first, its claims stop DAV / BV */
        if (g_dav_on) dav_run(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");        /* task diagave */
        if (g_avx_on) avx_run(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");        /* task avx */
        if (g_bv_p[0]) bv_run(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");        /* task boulevard */
        if (g_r9_centre) r9_run(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");      /* task bigrbt */
        if (g_hwy_np) rb_hwy(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");         /* task hwcore */
        if (g_avl_on) avl_pass(mgr, 0, 0, 0x7fffff, 0x7fffff, "load");       /* task avcore: last (+ its post hooks) */
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_rb_n_fault);
        logf("### rbt: exception 0x%08lX in the load pass", GetExceptionCode());
    }
    InterlockedDecrement(&g_rb_busy);
}

static char __fastcall rb_load(BYTE *mgr, void *edx, void *p1, void *p2) {
    char r;
    logf("rbt: city load (manager vt+0x1c) [tid %04lx]", GetCurrentThreadId());
    r = ((PFN_Load)g_rb_orig_load)(mgr, edx, p1, p2);
    g_rb_mgr = mgr;
    if (g_rb_stock) ZeroMemory(g_rb_stock, 1024 * 1024);
    if (!env_off("SC3NETMOD_RBT_LOAD")) {
        InterlockedExchange(&g_rb_load_pending, 1);
        logf("rbt: city load returned %d [tid %04lx]; full-map pass posted to the game window 0x%08lX", (int)r,
             GetCurrentThreadId(), (DWORD)g_rb_hwnd);
        if (g_rb_hwnd) PostMessageA(g_rb_hwnd, RB_WM, 0, 0);
    }
    return r;
}

static LRESULT CALLBACK rb_wndproc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == RB_WM) {
        logf("rbt: load pass message [tid %04lx]", GetCurrentThreadId());
        rb_load_pass();
        return 0;
    }
    return CallWindowProcA(g_rb_oldproc, h, m, wp, lp);
}

/* SAVEBASE: the stock id of a roundabout cell (39, or 11203 where the cell has no arm; the arm-less quarter piece
   is always 11203) */
static WORD rb_save_id(DWORD w0, WORD id) {
    DWORD x = w0 & 0x7ff, z = (w0 >> 11) & 0x7ff;
    if (g_dav_on && dav_save_43(id)) return 43;  /* task diagave: a middle cell holds both roads; stock 35 draws one */
    if (g_avx_on && avx_save_id(id)) return avx_save_id(id);   /* task avx: a T's far half saves as 11204 */
    if (g_hwy_np && hwy_save_id(id)) return hwy_save_id(id);  /* task hwcore: a highway-program piece's save id */
    if (g_rb_on && g_rb_closed && id == g_rb_closed) return 11203;
    if (!g_rb_on || id != g_rb_piece || !g_rb_stock || x >= 1024 || z >= 1024) return 0;
    return g_rb_stock[z * 1024 + x] == 2 ? 11203 : 0;
}

/* ---------------------------------------------------------------- install */
static int rbt_install(BYTE *m) {
    char path[MAX_PATH], pat[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE hf;
    BYTE *e = m + 0x1547b;
    DWORD *s_load = (DWORD *)(m + 0x2c7bc + 0x1c), v;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(m + ((IMAGE_DOS_HEADER *)m)->e_lfanew);
    if (env_off("SC3NETMOD_RBT")) { g_rb_off = 1; logf("rbt: off (SC3NETMOD_RBT=0)"); }
    if (GetEnvironmentVariableA("SC3NETMOD_TABLE", path, sizeof(path))) rb_file(path);
    else if (g_rootlen) {
        static char names[64][MAX_PATH];
        int k, j, cnt = 0;
        _snprintf(pat, sizeof(pat), "%smods\\netmod\\tables\\*.txt", g_root);
        pat[sizeof(pat) - 1] = 0;
        hf = FindFirstFileA(pat, &fd);
        if (hf != INVALID_HANDLE_VALUE) {
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && cnt < 64) lstrcpynA(names[cnt++], fd.cFileName, MAX_PATH);
            } while (FindNextFileA(hf, &fd));
            FindClose(hf);
        }
        for (k = 1; k < cnt; k++)
            for (j = k; j > 0 && lstrcmpiA(names[j - 1], names[j]) > 0; j--) {
                char t[MAX_PATH]; lstrcpyA(t, names[j]); lstrcpyA(names[j], names[j - 1]); lstrcpyA(names[j - 1], t);
            }
        for (k = 0; k < cnt; k++) {
            _snprintf(path, sizeof(path), "%smods\\netmod\\tables\\%s", g_root, names[k]);
            path[sizeof(path) - 1] = 0;
            rb_file(path);
        }
    }
    if (g_dav_inner[0] && env_off("SC3NETMOD_DAV")) { g_dav_inner[0] = 0; logf("dav: off (SC3NETMOD_DAV=0)"); }
    if (g_avx_nbox && env_off("SC3NETMOD_AVX")) { g_avx_nbox = 0; logf("avx: off (SC3NETMOD_AVX=0)"); }   /* task avx */
    if (!g_avx_nbox) logf("avx: no avenue junctions in the tables");                                  /* task avx */
    if (!g_rb_piece) logf("rbt: no automatic roundabout in the tables");
    if (!g_dav_inner[0]) logf("dav: no automatic diagonal avenue in the tables");
    if (g_bv_p[0] && env_off("SC3NETMOD_BV")) { g_bv_p[0] = 0; logf("bv: off (SC3NETMOD_BV=0)"); }  /* task boulevard */
    if (g_r9_centre && (env_off("SC3NETMOD_RBT9") || !r9_complete())) {    /* task bigrbt */
        logf("rbt9: off (%s)", r9_complete() ? "SC3NETMOD_RBT9=0" : "a piece role is missing in the tables");
        g_r9_centre = 0;
    }
    if (g_bvx_nbox && env_off("SC3NETMOD_BVX")) { g_bvx_nbox = 0; logf("bvx: off (SC3NETMOD_BVX=0)"); }   /* task bvx */
    if (g_dbv_out && env_off("SC3NETMOD_DBV")) { g_dbv_out = 0; logf("dbv: off (SC3NETMOD_DBV=0)"); }  /* task diagbv */
    hwy_install();                                                                                  /* task hwcore */
    if (g_avl_straight && env_off("SC3NETMOD_AVL")) { g_avl_straight = 0; logf("avl: off (SC3NETMOD_AVL=0)"); }   /* task avcore */
    if (!g_rb_piece && !g_dav_inner[0] && !g_avx_nbox && !g_bv_p[0] && !g_r9_centre && !g_dbv_out && !g_hwy_np &&
        !g_avl_straight)                                                                            /* task avcore */
        return 0;                                    /* avx, boulevard, bigrbt, diagbv, hwcore (bvx runs in BV) */
    g_rb_m = m;
    g_rb_msize = nt->OptionalHeader.SizeOfImage;
    if (IsBadReadPtr(e, 10) || e[0] != 0xb8 || *(DWORD *)(e + 1) != (DWORD)m + 0x27a52 || e[5] != 0xe8 ||
        (DWORD)(e + 10) + *(DWORD *)(e + 6) != (DWORD)m + 0x266d4 || *s_load != (DWORD)m + 0x130e9) {
        logf("### rbt: FUN_1001547b entry or manager vt+0x1c differ from shipped - RBT and DAV OFF");
        g_rb_piece = 0; g_dav_inner[0] = 0; g_avx_nbox = 0; g_bv_p[0] = 0; g_r9_centre = 0;   /* avx, boulevard, bigrbt */
        g_hwy_np = 0;                                                                         /* task hwcore */
        g_avl_straight = 0;                                                                   /* task avcore */
        return 0;
    }
    g_rb_stock = (BYTE *)VirtualAlloc(NULL, 1024 * 1024, MEM_COMMIT, PAGE_READWRITE);
    g_rb_eh = (DWORD)m + 0x27a52;
    g_rb_cont = (DWORD)m + 0x15480;
    g_rb_orig_load = *s_load;
    v = (DWORD)rb_load;
    if (!write_code((BYTE *)s_load, &v, 4) || !write_rel(e, 0xE9, (void *)rb_pass, 5)) {
        logf("### rbt: patch failed - RBT and DAV OFF");
        g_rb_piece = 0; g_dav_inner[0] = 0; g_avx_nbox = 0; g_bv_p[0] = 0; g_r9_centre = 0;   /* avx, boulevard, bigrbt */
        g_hwy_np = 0;                                                                         /* task hwcore */
        g_avl_straight = 0;                                                                   /* task avcore */
        return 0;
    }
    g_rb_on = 1;
    if (g_dav_inner[0]) { dav_init_table(); g_dav_on = 1; }
    if (g_avx_nbox) { g_avx_on = 1; logf("avx: avenue junctions on, %d box piece(s)", g_avx_nbox); }   /* task avx */
    if (g_r9_centre) logf("rbt9: automatic 3x3 roundabouts on (centre piece %u)", g_r9_centre);   /* task bigrbt */
    if (g_dbv_out) { g_dbv_on = 1; logf("dbv: diagonal boulevards on"); }                           /* task diagbv */
    if (g_avl_straight) { g_avl_on = 1; logf("avl: one-way avenue halves on (straight %u)", g_avl_straight); }   /* task avcore */
    logf("rbt: hooked the retile pass FUN_1001547b (entry) and the city load (manager vt+0x1c); piece %u, min %d arm(s), "
         "arm-less quarter %u; diagonal avenues %s (inner %u %u %u)", g_rb_piece, g_rb_min, g_rb_closed,
         g_dav_on ? "on" : "off", g_dav_inner[0], g_dav_inner[1], g_dav_inner[2]);
    return 1;
}

static void rbt_window(void) {
    HWND h = NULL;
    if (!g_rb_on || g_rb_hwnd) return;
    EnumWindows(tm_enum, (LPARAM)&h);
    if (!h) return;
    g_rb_oldproc = (WNDPROC)SetWindowLongA(h, GWL_WNDPROC, (LONG)rb_wndproc);
    g_rb_hwnd = h;
    logf("rbt: window 0x%08lX subclassed for the load pass", (DWORD)h);
    if (g_rb_load_pending) PostMessageA(h, RB_WM, 0, 0);
}

static void rbt_stats(void) {
    static LONG last;
    r9_stats();                                                              /* task bigrbt */
    hwy_stats();                                                             /* task hwcore */
    hwt_stats();                                                             /* task hwt */
    hwx_stats();                                                             /* task hwx */
    hwdd_stats();                                                            /* task hwdd */
    hwdx_stats();                                                            /* task hwdx */
    hwave_stats();                                                           /* task hwave */
    hwask_stats();                                                           /* task hwask */
    avl_stats();                                                             /* task avcore */
    LONG n = g_rb_n_pass + g_rb_n_conv + g_rb_n_rev + g_rb_n_load + g_rb_n_fault;
    if (!g_rb_on || n == last) return;
    last = n;
    logf("stats: rbt ROAD passes=%ld, blocks converted=%ld, reverted=%ld, load passes=%ld, faults=%ld", g_rb_n_pass,
         g_rb_n_conv, g_rb_n_rev, g_rb_n_load, g_rb_n_fault);
}
