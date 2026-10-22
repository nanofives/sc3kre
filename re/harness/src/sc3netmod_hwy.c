/* sc3netmod_hwy.c - the HWY block of sc3netmod.dll (task hwcore, highway program 2026-10-18): the shared base the
 * highway shape blocks (hwx, hwt, hwdx, hwdd) build on. #included by sc3netmod.c after the DBV block. Shared by every
 * highway-program stream: copy it verbatim, ask hwcore for changes.
 *
 * Highway retiles reach RBT's retile-pass hook (FUN_1001547b entry, sc3netmod_rbt.c rb_pass) as net == 4 passes; the
 * city-load pass (rb_load_pass) runs once over the whole map. RBT calls, for a highway pass:
 *     rb_hwy(mgr, x0, z0, x1, z1, who):  hp = hwy_begin(...)   reads the cells of the box (+ HWY_MARGIN), clears claims
 *                                        <shape block>_run(hp)  one line per block in rb_hwy, marked with its task
 *                                        hwy_end(hp)            the proof rule, then unkept pieces reverted
 * and the shape blocks use only the helpers below (their prototypes go at the top of sc3netmod_rbt.c, struct HwyPass *).
 *
 * Helpers (cells are real map cells):
 *   hwy_at(hp, x, z)         0, or HWY_ON | state << 16 | id: the surface occupant the manager's network test vt+0x14c
 *                            accepts for netType 4 (the HWAY predicate the retile gathers its nodes with)
 *   hwy_id(v), hwy_st(v)     id / state of an hwy_at value
 *   hwy_free(hp, x, z)       1 = a variant may be written into this EMPTY cell: inside the map and not on its edge
 *                            row, flat (FUN_10016ccd), not water (FUN_10016d69), and the stock On-ramp tool's own
 *                            free-cell test FUN_10009c65 redone on the manager's objects: the terrain object
 *                            (selection +0x54 there = manager +0x30, both city vt+0x13c, FUN_10012609) vt+0xd0(x, z)
 *                            accepts the cell, and the surface occupant (layer +0x3c vt+0x78) is none or major type
 *                            5 = trees, which the writer clears. Other networks and buildings (occupants of the same
 *                            layer, as TMPL's check reads them) fail it [CONFIRMED @ 0x10009c65]; zoned empty land
 *                            passes [UNCERTAIN: what terrain vt+0xd0 tests is not decoded]
 *   hwy_claimed(x, z)        1 = a block already took this cell in this pass (check it before matching a shape)
 *   hwy_claim(hp, x, z)      take a cell (also done by hwy_put / hwy_keep)
 *   hwy_put(hp, x, z, piece, state)   write a variant (FUN_10008919, free: the highway is paid for), claim + keep it;
 *                            a cell that already holds piece.state is only kept. Works on a highway cell and on a
 *                            free cell. -> 1 written, 0 already there, -1 refused (cell neither highway nor free)
 *   hwy_keep(hp, x, z)       keep an hwyp piece that is right as it is
 *   hwy_keep_far(hp, x, z, v)  task hwtdel: keep a cell that may lie outside the read box (v = its hwy_read value),
 *                            so the re-place below covers an interchange's cells past the box too
 *   hwy_rd(hp, x, z)         task hwtdel: hwy_at for any map cell (the buffer inside the box, a fresh read past it):
 *                            blocks vote and check over their whole footprint with it
 *   hwy_put past the box     task hwtdel: a cell outside the buffer is never written; when it already holds
 *                            piece.state it is kept (hwy_keep_far) -> 0, else -1. So a block's normal "put every
 *                            cell" loop keeps the interchange's cells past the box for the re-place
 *   hwy_unput(hp, x, z, piece, state)  task hwtdel: take back a cell of an interchange part that no longer holds when
 *                            it lies on the box's border row or past the box (land: hwy_drop; on highway: its stock
 *                            piece, border row only); the interior is hwy_end's
 *   hwy_gap_cap(...)         task hwtdel: the stock end cap facing a bulldozed neighbour, for a cut interchange's
 *                            straight cells
 *   hwy_drop(hp, x, z)       remove whatever highway occupant the cell holds at hwy_end (a declared piece or a stock
 *                            highway cell, e.g. a T's stem stub when the T breaks): manager remover vt+0xb8, then the
 *                            3x3 rect retile; wins over keep. Any map cell: one outside the read box (or on its border
 *                            row) is queued (HWY_XDROP per pass) and read fresh at hwy_end, so a block can clear the
 *                            far side of a broken interchange the box did not reach
 * Kept cells are re-placed at hwy_end when a revert's rect retile changed them (the stock tiler re-places the cells
 * around a removed land piece, kept on-highway pieces included; measured 2026-10-22, task hwtdel: an in-place retile
 * of one highway cell re-tiled the run 6 cells away and wrote 15149 there). Task hwtdel's 15149 net (hwy_net_take /
 * hwy_net_fix, below) then puts the pre-revert piece back in any cell of the box + HWY_RING that a revert left as 15149.
 * Revert (hwy_end): every cell of the read box (one cell in from its border) holding a declared piece (hwyp) that no
 * block kept in this pass goes back: a LAND piece (written into a free cell) is removed with the manager's own remover
 * vt+0xb8 = FUN_1000909f (vt+0x108 = FUN_100090f4 checks map-edge neighbour links, then layer vt+0x48), then the rect
 * retile (manager vt+0xb0, mask 3) over its 3x3 so the highway beside it re-tiles; a piece on a player's highway cell
 * is re-tiled in place (rect retile: its base must not be Protected, or the tiler leaves it).
 * Pieces: give land pieces a Protected HWAY base (15099..15105, 15107..15114, 15123..15128, 15130..15141; the variant
 * inherits the list, netbridge INHERIT) so the stock tiler never removes them and the highway beside them sees their
 * base through Convert; give on-highway pieces a plain base (73, 15051, ...) so a retile re-places them as highway.
 * Save: a declared piece saves as its `save` id if given, else as its base (SAVEBASE); with the mod the variant ids come
 * back from section 0x4E56, without it the city holds the bases.
 *
 * Table lines (netpack manifest "highway_lines", raw):
 *   hwyp <piece> <land 0|1> [<save id> [<state delta>]]   a highway-program piece (any stream's): land = written into
 *                                         free cells; save id 0 = its base; the saved state is (state + delta) & 3
 *                                         (a game without the mod reads the base turned that way), undone on load
 *                                         (the variant section keeps the original state)
 *   hwys <piece> <id0> <st0> <id1> <st1> <id2> <st2> <id3> <st3>
 *                                         saved (id, state) of the piece at each of its states 0..3 (id 0 = its save id
 *                                         / base), e.g. a rewritten highway cell saves as the stock straight or band piece
 *                                         for its heading. Needs the piece's hwyp line before it. Overrides the delta.
 *   hwyl <piece> <twin>                   task hwlight: the LIT TWIN of a piece a block also writes at odd states (same
 *                                         base, lanes and hwrc class; art from the scene turned one state, hwpaint.py
 *                                         paint_twin). Every read sees the piece (rb_read / hwy_read via hwlt_read),
 *                                         every write of the piece at an odd state puts the twin (hwlt_want), the save
 *                                         uses the piece's hwyp / hwys entry. Needs the piece's hwyp line before it.
 *   hwyt <pieceA> <pieceB>                the hwcore proof rule: the free cell past a highway END gets a ramp-down
 *                                         piece (art: deck descending from H to the ground toward the cell's +z at
 *                                         state 0; A has the outer parapet on +x, B on -x), so the end of a two-cell
 *                                         highway gets one A and one B. Both must be hwyp land pieces.
 * Off: SC3NETMOD_HWY=0 (the whole block, shape blocks included). The proof rule runs only with SC3NETMOD_HWYT=1
 * (task hwlone: with highway_core installed it put a ramp past every highway end, owner bug 2026-10-21; off, its
 * pieces are "kept by no block" and removed by the next pass, the load pass included).
 */

#define HWY_ON 0x80000000UL
#define HWY_MAXP 4096                         /* declared pieces (all streams together; 347 in the combined program) */
#define HWY_MARGIN 8
#define HWY_CLAIM 16384                       /* claims hash slots (power of two) */
#define HWY_XDROP 1024                        /* hwy_drop cells outside the read box, per pass */
#define HWY_KEEP 4096                         /* kept cells re-checked after the reverts, per pass */

typedef struct { WORD piece, save; BYTE land, sdelta, tab; WORD tid[4]; BYTE tst[4]; } HwyPiece;
struct HwyPass {
    BYTE *mgr;
    void *lay;
    int W, H, x0, z0, x1, z1;                 /* map size; the read box (cells) */
    RbBuf b;                                  /* hwy_at values of the read box */
    BYTE *flag;                               /* [cell]: 1 kept, 2 free tested, 4 free, 8 drop, 16 in kp[], 32 reverted */
    const char *who;
    int nput, nrev;
    int nx;                                   /* hwy_drop cells outside the read box (or on its border row) */
    int nk;                                   /* kept cells: what a block wants there, re-placed if a revert retile moved it */
    struct { short x, z; WORD id; BYTE st; } kp[HWY_KEEP];
    int xd[HWY_XDROP][2];
};
typedef struct HwyPass HwyPass;

static HwyPiece g_hwy_p[HWY_MAXP];
static WORD g_hwy_idx[65536];                 /* piece id -> index in g_hwy_p + 1, 0 = not declared */
static int g_hwy_np, g_hwy_off;
static WORD g_hwy_t[2];                       /* hwyt proof rule pieces A, B */
static DWORD *g_hwy_claim;
static int g_hwy_nclaim;
static volatile LONG g_hwy_n_pass, g_hwy_n_put, g_hwy_n_rev, g_hwy_n_load, g_hwy_n_fault;

typedef char (__fastcall *PFN_HwyTer)(void *ter, void *edx, int x, int z);           /* terrain vt+0xd0 ret 8 */
typedef char (__fastcall *PFN_HwyPos)(void *mgr, void *edx, int *pos);               /* FUN_10016ccd / 6d69 ret 4 */
typedef DWORD (__fastcall *PFN_HwyRemove)(void *mgr, void *edx, void *lay, void *occ); /* vt+0xb8 FUN_1000909f ret 8 */
typedef char (__fastcall *PFN_HwyAt)(void *lay, void *edx, int x, int z, void **out); /* layer vt+0x7c ret 0xc */

static int hwy_piece(WORD id);

static void hwy_line(const char *path, const char *line) {
    unsigned long p, l, s = 0, a, b, sd = 0;
    int k;
    if (g_hwy_off) return;
    if (!strncmp(line, "hwyp ", 5)) {
        k = sscanf(line + 5, "%lu %lu %lu %lu", &p, &l, &s, &sd);
        if (k < 2 || !p || p > 0xffff || l > 1 || s > 0xffff || sd > 3 || !g_base[p]) {
            logf("### hwy: %s: bad piece line (or not a variant) '%s'", path, line);
            return;
        }
        if (g_hwy_idx[p]) {
            logf("### hwy: %s: piece %lu declared twice - the later line '%s' ignored", path, p, line);
            return;
        }
        if (g_hwy_np >= HWY_MAXP) { logf("### hwy: %s: too many pieces - '%s' ignored", path, line); return; }
        g_hwy_p[g_hwy_np].piece = (WORD)p; g_hwy_p[g_hwy_np].land = (BYTE)l; g_hwy_p[g_hwy_np].save = (WORD)s;
        g_hwy_p[g_hwy_np].sdelta = (BYTE)sd;
        g_hwy_np++;
        g_hwy_idx[p] = (WORD)g_hwy_np;
        logf("hwy: %s: piece %lu (%s), saves as %lu, state + %lu", path, p, l ? "land" : "on highway", s ? s : g_base[p], sd);
        return;
    }
    if (!strncmp(line, "hwys ", 5)) {            /* hwys <piece> <id0> <st0> .. <id3> <st3>: saved (id, state) per state */
        unsigned long v[9];
        int j;
        if (sscanf(line + 5, "%lu %lu %lu %lu %lu %lu %lu %lu %lu", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6], &v[7],
                   &v[8]) != 9 || (k = hwy_piece((WORD)v[0])) < 0) {
            logf("### hwy: %s: bad save-table line (or its piece has no hwyp line before it) '%s'", path, line);
            return;
        }
        for (j = 0; j < 4; j++) {
            if (v[1 + 2 * j] > 0xffff || v[2 + 2 * j] > 3) { logf("### hwy: %s: bad save-table entry '%s'", path, line); return; }
            g_hwy_p[k].tid[j] = (WORD)v[1 + 2 * j]; g_hwy_p[k].tst[j] = (BYTE)v[2 + 2 * j];
        }
        g_hwy_p[k].tab = 1;
        logf("hwy: %s: piece %lu saves as %lu.%lu / %lu.%lu / %lu.%lu / %lu.%lu at states 0..3", path, v[0], v[1], v[2], v[3],
             v[4], v[5], v[6], v[7], v[8]);
        return;
    }
    if (!strncmp(line, "hwyl ", 5)) {            /* task hwlight: hwyl <piece> <twin> */
        if (sscanf(line + 5, "%lu %lu", &a, &b) != 2 || !a || a > 0xffff || !b || b > 0xffff || a == b || !g_base[b] ||
            g_base[b] != g_base[a] || hwy_piece((WORD)a) < 0 || g_hwlt_p[a] || g_hwlt_t[b] ||
            (g_hwlt_t[a] && g_hwlt_t[a] != b) || (g_hwlt_p[b] && g_hwlt_p[b] != a)) {
            logf("### hwy: %s: bad lit-twin line (twin not a variant of the piece's base, piece without hwyp, or a twin "
                 "named twice) '%s'", path, line);
            return;
        }
        g_hwlt_t[a] = (WORD)b; g_hwlt_p[b] = (WORD)a;
        return;
    }
    if (!strncmp(line, "hwyt ", 5)) {
        if (sscanf(line + 5, "%lu %lu", &a, &b) != 2 || !a || a > 0xffff || !b || b > 0xffff || !g_base[a] || !g_base[b]) {
            logf("### hwy: %s: bad proof-rule line '%s'", path, line);
            return;
        }
        g_hwy_t[0] = (WORD)a; g_hwy_t[1] = (WORD)b;
        logf("hwy: %s: proof rule: ramp-down pieces %lu (outer +x) / %lu (outer -x) past highway ends", path, a, b);
        return;
    }
    logf("### hwy: %s: unknown line '%s'", path, line);
}

static int hwy_piece(WORD id) {                 /* per cell and per save record: an id-indexed lookup */
    int k;
    if (g_hwlt_p[id]) id = g_hwlt_p[id];        /* task hwlight: a twin is its piece (saves included) */
    k = g_hwy_idx[id] - 1;
    return (id && k >= 0 && k < g_hwy_np) ? k : -1;   /* k < g_hwy_np: SC3NETMOD_HWY=0 / install errors set np 0 */
}

/* SAVEBASE: what a declared piece at state `st` is saved as, so a game without the mod reads the stock piece the stock
   tiler would have placed there: from its hwys table (id, state per state; id 0 = keep the save id / base), else its
   hwyp state delta ((st + delta) & 3). -> 1 when it overrides; the saver records the original state in the variant
   section and the load side puts it back (sc3netmod.c save_rec / load_rec). */
static int hwy_save_override(WORD id, int st, WORD *sid, int *sst) {
    int k = hwy_piece(id);
    if (k < 0) return 0;
    if (g_hwy_p[k].tab) { *sid = g_hwy_p[k].tid[st & 3]; *sst = g_hwy_p[k].tst[st & 3]; return 1; }
    if (g_hwy_p[k].sdelta) { *sid = 0; *sst = (st + g_hwy_p[k].sdelta) & 3; return 1; }
    return 0;
}

/* SAVEBASE: the save id of a declared piece, 0 = its base */
static WORD hwy_save_id(WORD id) {
    int k = hwy_piece(id);
    return k < 0 ? 0 : g_hwy_p[k].save;
}

/* ---------------------------------------------------------------- claims */
static DWORD hwy_hash(int x, int z) { return (((DWORD)x * 2654435761UL) ^ ((DWORD)z * 40503UL)) & (HWY_CLAIM - 1); }

static int hwy_claimed(int x, int z) {
    DWORD key, h;
    if (!g_hwy_claim || !g_hwy_nclaim || x < 0 || z < 0) return 0;
    key = ((DWORD)(x & 0xfff) << 12 | (DWORD)(z & 0xfff)) + 1;
    h = hwy_hash(x, z);
    while (g_hwy_claim[h]) {
        if (g_hwy_claim[h] == key) return 1;
        h = (h + 1) & (HWY_CLAIM - 1);
    }
    return 0;
}

static void hwy_claim(HwyPass *hp, int x, int z) {
    DWORD key = ((DWORD)(x & 0xfff) << 12 | (DWORD)(z & 0xfff)) + 1, h = hwy_hash(x, z);
    (void)hp;
    if (!g_hwy_claim || g_hwy_nclaim >= HWY_CLAIM / 2 || x < 0 || z < 0) return;
    while (g_hwy_claim[h] && g_hwy_claim[h] != key) h = (h + 1) & (HWY_CLAIM - 1);
    if (!g_hwy_claim[h]) { g_hwy_claim[h] = key; g_hwy_nclaim++; }
}

/* ---------------------------------------------------------------- reading */
static DWORD hwy_read(BYTE *mgr, void *lay, int x, int z, int W, int H) {
    void *occ = NULL;
    DWORD r = 0, vt;
    if (x < 0 || z < 0 || x >= W || z >= H) return 0;
    if (!((PFN_HwyAt)VT(lay, 0x7c))(lay, 0, x, z, &occ) || !occ) return 0;
    vt = *(DWORD *)occ;
    if (vt >= (DWORD)g_rb_m && vt < (DWORD)g_rb_m + g_rb_msize && ((PFN_Pred)VT(mgr, 0x14c))(mgr, 0, 4, occ))
        r = HWY_ON | ((*(DWORD *)((BYTE *)occ + 0x10) >> 30) << 16) | (*(DWORD *)((BYTE *)occ + 0x14) & 0xffff);
    ((PFN_B0)VT(occ, 8))(occ);
    return hwlt_read(r);                        /* task hwlight */
}

static WORD hwy_id(DWORD v) { return (WORD)(v & 0xffff); }
static int hwy_st(DWORD v) { return (int)((v >> 16) & 3); }

static DWORD hwy_at(HwyPass *hp, int x, int z) { return rb_at(&hp->b, x, z); }

/* task hwtdel: any map cell, the pass buffer inside the read box, a fresh read past it. Interchange blocks vote and
   check over their whole footprint with it: a pass box may hold only part of an interchange */
static int hwy_inbuf(HwyPass *hp, int x, int z) {
    return x >= hp->b.x0 && z >= hp->b.z0 && x < hp->b.x0 + hp->b.w && z < hp->b.z0 + hp->b.h;
}
static DWORD hwy_rd(HwyPass *hp, int x, int z) {
    return hwy_inbuf(hp, x, z) ? hwy_at(hp, x, z) : hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
}

static BYTE *hwy_flag(HwyPass *hp, int x, int z) {
    static BYTE dummy;
    x -= hp->b.x0; z -= hp->b.z0;
    if (x < 0 || z < 0 || x >= hp->b.w || z >= hp->b.h) { dummy = 0; return &dummy; }
    return &hp->flag[z * hp->b.w + x];
}

static int hwy_free(HwyPass *hp, int x, int z) {
    BYTE *f = hwy_flag(hp, x, z);
    int pos[3], ok;
    if (x < 1 || z < 1 || x >= hp->W - 1 || z >= hp->H - 1) return 0;
    if (*f & 2) return (*f & 4) != 0;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ok = !hwy_at(hp, x, z) && ((PFN_HwyPos)(g_rb_m + 0x16ccd))(hp->mgr, 0, pos) &&
         !((PFN_HwyPos)(g_rb_m + 0x16d69))(hp->mgr, 0, pos);
    if (ok) {   /* FUN_10009c65's test with the manager's own objects: terrain (+0x30) vt+0xd0, surface occupant */
        void *ter = *(void **)(hp->mgr + 0x30), *occ = NULL;
        ok = ter && ((PFN_HwyTer)VT(ter, 0xd0))(ter, 0, x, z);
        if (ok && ((PFN_Get)VT(hp->lay, 0x78))(hp->lay, 0, pos, &occ) && occ) {
            ok = ((PFN_B0)VT(occ, 0x54))(occ) == 5;
            ((PFN_B0)VT(occ, 8))(occ);
        }
    }
    *f |= 2 | (ok ? 4 : 0);
    return ok;
}

/* ---------------------------------------------------------------- writing */
static void hwy_keep(HwyPass *hp, int x, int z) {
    BYTE *f = hwy_flag(hp, x, z);
    DWORD v = hwy_at(hp, x, z);
    int k;
    *f |= 1;
    hwy_claim(hp, x, z);
    if (!v) return;
    if (*f & 16) {                                    /* recorded already: keep the latest piece */
        for (k = 0; k < hp->nk; k++)
            if (hp->kp[k].x == x && hp->kp[k].z == z) { hp->kp[k].id = hwy_id(v); hp->kp[k].st = (BYTE)hwy_st(v); return; }
    }
    if (hp->nk >= HWY_KEEP) return;
    hp->kp[hp->nk].x = (short)x; hp->kp[hp->nk].z = (short)z; hp->kp[hp->nk].id = hwy_id(v); hp->kp[hp->nk].st = (BYTE)hwy_st(v);
    hp->nk++;
    *f |= 16;
}

/* task hwtdel: keep a cell that may lie outside the read box (or on its border row), holding v (its hwy_read value):
   recorded for the re-place after the reverts, because a revert's rect retile re-tiles the whole highway run around
   it, past the box (owner bug 2026-10-22: a T cut to 15149 cells by a pass that only grazed it). Inside the box =
   hwy_keep. */
static void hwy_keep_far(HwyPass *hp, int x, int z, DWORD v) {
    int k;
    if (x >= hp->b.x0 && z >= hp->b.z0 && x < hp->b.x0 + hp->b.w && z < hp->b.z0 + hp->b.h) { hwy_keep(hp, x, z); return; }
    if (!v || hp->nk >= HWY_KEEP) return;
    hwy_claim(hp, x, z);
    for (k = 0; k < hp->nk; k++) if (hp->kp[k].x == x && hp->kp[k].z == z) return;
    hp->kp[hp->nk].x = (short)x; hp->kp[hp->nk].z = (short)z; hp->kp[hp->nk].id = hwy_id(v); hp->kp[hp->nk].st = (BYTE)hwy_st(v);
    hp->nk++;
}

static void hwy_drop(HwyPass *hp, int x, int z) {
    int k;
    if (x < 1 || z < 1 || x >= hp->W - 1 || z >= hp->H - 1) return;
    if (x > hp->x0 && x < hp->x1 && z > hp->z0 && z < hp->z1) {
        BYTE *f = hwy_flag(hp, x, z);
        *f = (BYTE)((*f & ~1) | 8);
        return;
    }
    for (k = 0; k < hp->nx; k++) if (hp->xd[k][0] == x && hp->xd[k][1] == z) return;
    if (hp->nx >= HWY_XDROP) { logf("### hwy: %s: more than %d drops outside the box - (%d,%d) skipped", hp->who, HWY_XDROP, x, z); return; }
    hp->xd[hp->nx][0] = x; hp->xd[hp->nx][1] = z; hp->nx++;
}

static int hwy_put(HwyPass *hp, int x, int z, WORD piece, int state) {
    DWORD cur = hwy_at(hp, x, z);
    int pos[3];
    if (!hwy_inbuf(hp, x, z)) {   /* task hwtdel: past the box a cell is only kept (re-placed after reverts), never written */
        cur = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
        if (cur && hwy_id(cur) == piece && hwy_st(cur) == (state & 3) && !(cur & HWLT_LIT)) { hwy_keep_far(hp, x, z, cur); return 0; }
        return -1;
    }
    if (cur && hwy_id(cur) == piece && hwy_st(cur) == (state & 3) && !(cur & HWLT_LIT)) { hwy_keep(hp, x, z); return 0; }
    if (!cur && !hwy_free(hp, x, z)) return -1;
    pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
    ((PFN_Put)(g_rb_m + 0x8919))(hp->mgr, 0, hp->lay, pos, hwlt_want(((DWORD)piece << 8) | (DWORD)(state & 3)), -1, 8, 0);
    {   /* re-read: the buffer must show what is there now (the next block reads it) */
        int bx = x - hp->b.x0, bz = z - hp->b.z0;
        if (bx >= 0 && bz >= 0 && bx < hp->b.w && bz < hp->b.h)
            hp->b.c[bz * hp->b.w + bx] = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
    }
    hwy_keep(hp, x, z);
    hp->nput++;
    return 1;
}

/* task hwtdel: the stock piece a declared piece saves as at state st (hwys table / save id / base), 0 = none */
static WORD hwy_stock_of(WORD id, int st, int *sst) {
    WORD sid = 0;
    *sst = st;
    if (!hwy_save_override(id, st, &sid, sst)) { sid = 0; *sst = st; }
    if (!sid) sid = hwy_save_id(id);
    if (!sid) sid = g_base[id];
    return sid;
}

/* task hwtdel: take back one cell of an interchange part that no longer holds, wherever it lies. Inside the box
   interior hwy_end reverts it (nothing to do). On the box's border row or past the box: a land piece is dropped
   (hwy_drop queues it), an on-highway piece on the border row gets its stock piece (hwy_stock_of). Only when the cell
   still holds piece.state. An on-highway cell past the box stays for a later pass (never written past the box). */
static void hwy_unput(HwyPass *hp, int x, int z, WORD piece, int state) {
    DWORD v = hwy_rd(hp, x, z);
    int k = hwy_piece(piece), sst;
    WORD sid;
    if (!v || hwy_id(v) != piece || hwy_st(v) != (state & 3) || k < 0) return;
    if (x > hp->x0 && x < hp->x1 && z > hp->z0 && z < hp->z1) return;
    if (g_hwy_p[k].land) { hwy_drop(hp, x, z); return; }
    if (!hwy_inbuf(hp, x, z) || hwy_claimed(x, z)) return;
    sid = hwy_stock_of(piece, state & 3, &sst);
    if (sid && sid != 15149) hwy_put(hp, x, z, sid, sst);
}

/* task hwtdel: the stock end cap for a straight highway cell (x, z) whose own highway runs along (ux, uz), when exactly
   one of its two neighbours along it holds no highway (the player bulldozed the next cell): the cap facing that gap.
   (px, pz) = the step toward the other lane of its carriageway pair (picks the lane's cap, hwcap_cap_of). -> 1 and
   the cap, 0 = no gap or both sides open. A block that rewrites a cut interchange's cells with plain highway uses it so
   the cut ends do not draw open (the re-place after reverts would otherwise keep a straight piece over the stock cap) */
static void hwcap_cap_of(int sx, int sz, int lower, WORD *id, int *st);
static int hwy_gap_cap(HwyPass *hp, int x, int z, int ux, int uz, int px, int pz, WORD *id, int *st) {
    int s, gx = 0, gz = 0, n = 0;
    for (s = -1; s <= 1; s += 2)
        if (!hwy_rd(hp, x + s * ux, z + s * uz)) { gx = s * ux; gz = s * uz; n++; }
    if (n != 1) return 0;
    hwcap_cap_of(gx, gz, px + pz > 0, id, st);
    return 1;
}

/* ---------------------------------------------------------------- the proof rule (hwyt) */
static void hwy_rot(int k, int *dx, int *dz) {        /* one state: (x, z) -> (-z, x) */
    while (k-- > 0) { int t = *dx; *dx = -*dz; *dz = t; }
}

static void hwyt_run(HwyPass *hp) {
    int x, z, k;
    char on[8];
    if (!g_hwy_t[0] || !GetEnvironmentVariableA("SC3NETMOD_HWYT", on, sizeof(on)) || on[0] != '1') return;   /* task hwlone: opt-in */
    for (z = hp->z0 + 1; z < hp->z1; z++)
        for (x = hp->x0 + 1; x < hp->x1; x++) {
            DWORD v = hwy_at(hp, x, z);
            WORD id = hwy_id(v);
            int alz, dx, dz, sx, sz, ex, ox, oz, bx, bz, j, have;
            if (!v || hwy_piece(id) >= 0) continue;
            if (id == 73 || id == 11235 || id == 11237) alz = 1;            /* carriageway cells along z */
            else if (id == 15051 || id == 15053 || id == 15054) alz = 0;    /* along x */
            else continue;
            for (j = 0; j < 2; j++) {
                dx = alz ? 0 : (j ? 1 : -1); dz = alz ? (j ? 1 : -1) : 0;    /* D = toward the end */
                bx = x + dx; bz = z + dz;                                      /* the beyond cell */
                if (!hwy_at(hp, x - dx, z - dz)) continue;                    /* highway behind */
                have = hwy_at(hp, bx, bz) != 0;
                if (have && hwy_piece(hwy_id(hwy_at(hp, bx, bz))) < 0) continue;   /* highway goes on: not an end */
                /* the sibling carriageway across: the outer parapet faces away from it */
                sx = alz ? 1 : 0; sz = alz ? 0 : 1;
                if (hwy_at(hp, x + sx, z + sz) && !hwy_at(hp, x - sx, z - sz)) { ox = -sx; oz = -sz; }
                else if (hwy_at(hp, x - sx, z - sz) && !hwy_at(hp, x + sx, z + sz)) { ox = sx; oz = sz; }
                else continue;
                if (hwy_claimed(bx, bz) || (!have && !hwy_free(hp, bx, bz))) continue;
                for (k = 0; k < 4; k++) {                                     /* state k: +z turned k times = D */
                    int tx = 0, tz = 1, px = 1, pz = 0;
                    hwy_rot(k, &tx, &tz);
                    if (tx != dx || tz != dz) continue;
                    hwy_rot(k, &px, &pz);                                     /* A's outer side at state k */
                    ex = px == ox && pz == oz ? 0 : 1;
                    if (hwy_put(hp, bx, bz, g_hwy_t[ex], k) > 0)
                        logf("hwy: %s: highway end at (%d,%d) -> proof piece %u.%d in (%d,%d)", hp->who, x, z,
                             g_hwy_t[ex], k, bx, bz);
                    break;
                }
            }
        }
}

/* ---------------------------------------------------------------- the pass */
static HwyPass *hwy_begin(BYTE *mgr, int x0, int z0, int x1, int z1, const char *who) {
    static HwyPass P;
    int W = (*(int *)(mgr + 0x5c) >> 8) + 1, H = (*(int *)(mgr + 0x60) >> 8) + 1, x, z;
    if (g_hwy_off || !g_rb_m || W < 4 || H < 4 || W > 4096 || H > 4096) return NULL;
    if (!g_hwy_claim) g_hwy_claim = (DWORD *)VirtualAlloc(NULL, HWY_CLAIM * sizeof(DWORD), MEM_COMMIT, PAGE_READWRITE);
    if (g_hwy_claim) { ZeroMemory(g_hwy_claim, HWY_CLAIM * sizeof(DWORD)); g_hwy_nclaim = 0; }
    x0 -= HWY_MARGIN; z0 -= HWY_MARGIN; x1 += HWY_MARGIN; z1 += HWY_MARGIN;
    if (x0 < 0) x0 = 0;
    if (z0 < 0) z0 = 0;
    if (x1 > W - 1) x1 = W - 1;
    if (z1 > H - 1) z1 = H - 1;
    if (x0 > x1 || z0 > z1) return NULL;
    ZeroMemory(&P, sizeof(P));
    P.mgr = mgr; P.lay = *(void **)(mgr + 0x3c); P.W = W; P.H = H; P.who = who;
    P.x0 = x0; P.z0 = z0; P.x1 = x1; P.z1 = z1;
    P.b.x0 = x0; P.b.z0 = z0; P.b.w = x1 - x0 + 1; P.b.h = z1 - z0 + 1;
    P.b.c = (DWORD *)VirtualAlloc(NULL, (SIZE_T)P.b.w * P.b.h * 5, MEM_COMMIT, PAGE_READWRITE);
    if (!P.b.c) return NULL;
    P.flag = (BYTE *)(P.b.c + P.b.w * P.b.h);
    for (z = 0; z < P.b.h; z++)
        for (x = 0; x < P.b.w; x++) P.b.c[z * P.b.w + x] = hwy_read(mgr, P.lay, x0 + x, z0 + z, W, H);
    InterlockedIncrement(!strcmp(who, "load") ? &g_hwy_n_load : &g_hwy_n_pass);
    return &P;
}

/* task hwtdel: the 15149 net. A revert's rect retile re-tiles the whole highway run around the cell, past the read box,
 * and where the stock tiler then sees an interchange's land pieces (Protected HWAY bases) beside the highway it writes
 * 15149 "Highway Construction" (measured 2026-10-22: one in-place revert left 13 of them in a T 6 cells away; a
 * cloverleaf's box-edge cells the same). The kept-cell re-place covers only cells some block kept. So hwy_end
 * snapshots the box plus HWY_RING cells around it before it reverts, and afterwards puts the snapshot piece back in
 * any cell that turned into 15149 from another piece. A cell reverted in this pass is skipped when it was a land piece
 * (removed), but an on-highway piece re-tiled in place into 15149 gets the stock piece it saves as (hwys / save id /
 * base: what the player's highway held before the interchange; measured: a dropped hwdx quadrant's join cell), unless
 * that is 15149 itself (stub pieces). A 15149 the game made before the pass (a real stock side hit) is in the snapshot
 * and stays. */
#define HWY_RING 8
#define HWY_15149 15149

typedef struct { int x0, z0, w, h; DWORD *v; } HwyNet;

static void hwy_net_take(HwyPass *hp, HwyNet *n) {
    int x, z;
    n->x0 = hp->x0 - HWY_RING; n->z0 = hp->z0 - HWY_RING;
    if (n->x0 < 0) n->x0 = 0;
    if (n->z0 < 0) n->z0 = 0;
    n->w = (hp->x1 + HWY_RING < hp->W ? hp->x1 + HWY_RING : hp->W - 1) - n->x0 + 1;
    n->h = (hp->z1 + HWY_RING < hp->H ? hp->z1 + HWY_RING : hp->H - 1) - n->z0 + 1;
    n->v = (DWORD *)VirtualAlloc(NULL, (SIZE_T)n->w * n->h * sizeof(DWORD), MEM_COMMIT, PAGE_READWRITE);
    if (!n->v) return;
    for (z = 0; z < n->h; z++)
        for (x = 0; x < n->w; x++) {
            int cx = n->x0 + x, cz = n->z0 + z;
            n->v[z * n->w + x] = (cx >= hp->b.x0 && cz >= hp->b.z0 && cx < hp->b.x0 + hp->b.w && cz < hp->b.z0 + hp->b.h)
                                 ? hwy_at(hp, cx, cz) : hwy_read(hp->mgr, hp->lay, cx, cz, hp->W, hp->H);
        }
}

static void hwy_net_fix(HwyPass *hp, HwyNet *n) {
    int x, z, k;
    if (!n->v) return;
    for (z = 0; z < n->h; z++)
        for (x = 0; x < n->w; x++) {
            int cx = n->x0 + x, cz = n->z0 + z, pos[3], rev = 0, kp;
            DWORD was = n->v[z * n->w + x], v;
            if (!was || hwy_id(was) == HWY_15149) continue;
            if (cx > hp->x0 && cx < hp->x1 && cz > hp->z0 && cz < hp->z1) rev = (*hwy_flag(hp, cx, cz) & 32) != 0;
            for (k = 0; k < hp->nx && !rev; k++) rev = hp->xd[k][0] == cx && hp->xd[k][1] == cz;
            kp = hwy_piece(hwy_id(was));
            if (rev && (kp < 0 || g_hwy_p[kp].land || (*hwy_flag(hp, cx, cz) & 8))) continue;   /* removed: not ours */
            v = hwy_read(hp->mgr, hp->lay, cx, cz, hp->W, hp->H);
            if (!v || hwy_id(v) != HWY_15149) continue;
            if (rev) {   /* our on-highway piece re-tiled in place into 15149: the stock piece it saves as (what was there) */
                int sst;
                WORD sid = hwy_stock_of(hwy_id(was), hwy_st(was), &sst);
                if (!sid || sid == HWY_15149) continue;                   /* a stub piece: 15149 is its stock aftermath */
                was = HWY_ON | ((DWORD)(sst & 3) << 16) | sid;
            }
            pos[0] = cx << 8; pos[1] = cz << 8; pos[2] = 0;
            ((PFN_Put)(g_rb_m + 0x8919))(hp->mgr, 0, hp->lay, pos, hwlt_want(((DWORD)hwy_id(was) << 8) | (DWORD)hwy_st(was)), -1, 8, 0);
            hp->nput++;
            logf("hwy: %s: (%d,%d) 15149 left by a revert retile -> %u.%d put back", hp->who, cx, cz, hwy_id(was), hwy_st(was));
        }
    VirtualFree(n->v, 0, MEM_RELEASE);
    n->v = NULL;
}

static void hwy_end(HwyPass *hp) {
    int x, z;
    HwyNet net = {0};
    if (!hp || !hp->b.c) return;
    hwyt_run(hp);                                     /* the proof rule last: the shape blocks claim first */
    for (z = hp->z0 + 1; z < hp->z1 && !net.v; z++)  /* task hwtdel: the 15149 net, only when something reverts */
        for (x = hp->x0 + 1; x < hp->x1 && !net.v; x++) {
            DWORD v = hwy_at(hp, x, z);
            int k = v ? hwy_piece(hwy_id(v)) : -1;
            if ((v && (*hwy_flag(hp, x, z) & 8)) || (k >= 0 && !(*hwy_flag(hp, x, z) & 1))) hwy_net_take(hp, &net);
        }
    if (!net.v && hp->nx) hwy_net_take(hp, &net);
    for (z = hp->z0 + 1; z < hp->z1; z++)
        for (x = hp->x0 + 1; x < hp->x1; x++) {
            DWORD v = hwy_at(hp, x, z);
            int k = v ? hwy_piece(hwy_id(v)) : -1, rect[6], drop = v && (*hwy_flag(hp, x, z) & 8);
            if (!drop && (k < 0 || (*hwy_flag(hp, x, z) & 1))) continue;
            *hwy_flag(hp, x, z) |= 32;                /* task hwtdel: reverted in this pass (the 15149 net skips it) */
            if (drop || g_hwy_p[k].land) {
                void *occ = NULL;
                if (((PFN_HwyAt)VT(hp->lay, 0x7c))(hp->lay, 0, x, z, &occ) && occ) {
                    ((PFN_HwyRemove)VT(hp->mgr, 0xb8))(hp->mgr, 0, hp->lay, occ);
                    ((PFN_B0)VT(occ, 8))(occ);
                }
                rect[0] = (x - 1) << 8; rect[1] = (z - 1) << 8; rect[3] = (x + 1) << 8; rect[4] = (z + 1) << 8;
            } else {
                rect[0] = x << 8; rect[1] = z << 8; rect[3] = x << 8; rect[4] = z << 8;
            }
            rect[2] = 0; rect[5] = 0;
            ((PFN_Retile)VT(hp->mgr, 0xb0))(hp->mgr, 0, rect, 3);
            hp->nrev++;
            logf("hwy: %s: (%d,%d) piece %u.%d %s", hp->who, x, z, hwy_id(v), hwy_st(v),
                 drop ? "dropped by a block -> removed, 3x3 retile" :
                 g_hwy_p[k].land ? "kept by no block -> removed (land), 3x3 retile" : "kept by no block -> stock retile");
        }
    {   /* drops outside the read box: read now, remove any highway occupant */
        int k;
        for (k = 0; k < hp->nx; k++) {
            int x = hp->xd[k][0], z = hp->xd[k][1], rect[6];
            DWORD v = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
            void *occ = NULL;
            if (!v) continue;
            if (((PFN_HwyAt)VT(hp->lay, 0x7c))(hp->lay, 0, x, z, &occ) && occ) {
                ((PFN_HwyRemove)VT(hp->mgr, 0xb8))(hp->mgr, 0, hp->lay, occ);
                ((PFN_B0)VT(occ, 8))(occ);
            }
            rect[0] = (x - 1) << 8; rect[1] = (z - 1) << 8; rect[2] = 0; rect[3] = (x + 1) << 8; rect[4] = (z + 1) << 8;
            rect[5] = 0;
            ((PFN_Retile)VT(hp->mgr, 0xb0))(hp->mgr, 0, rect, 3);
            hp->nrev++;
            logf("hwy: %s: (%d,%d) piece %u.%d dropped by a block (outside the box) -> removed, 3x3 retile", hp->who, x, z,
                 hwy_id(v), hwy_st(v));
        }
    }
    if (hp->nrev) {   /* a revert's rect retile can re-place kept cells next to it with stock pieces: put them back */
        int k, nre = 0;
        for (k = 0; k < hp->nk; k++) {
            int x = hp->kp[k].x, z = hp->kp[k].z, pos[3];
            DWORD v = hwy_read(hp->mgr, hp->lay, x, z, hp->W, hp->H);
            if (*hwy_flag(hp, x, z) & 8) continue;    /* dropped later in the pass */
            if (v && hwy_id(v) == hp->kp[k].id && hwy_st(v) == hp->kp[k].st && !(v & HWLT_LIT)) continue;
            pos[0] = x << 8; pos[1] = z << 8; pos[2] = 0;
            ((PFN_Put)(g_rb_m + 0x8919))(hp->mgr, 0, hp->lay, pos, hwlt_want(((DWORD)hp->kp[k].id << 8) | hp->kp[k].st), -1, 8, 0);
            nre++;
            logf("hwy: %s: (%d,%d) kept piece %u.%d re-placed after a revert retile (cell held %u.%d)", hp->who, x, z,
                 hp->kp[k].id, hp->kp[k].st, hwy_id(v), hwy_st(v));
        }
        hp->nput += nre;
    }
    hwy_net_fix(hp, &net);                            /* task hwtdel */
    InterlockedExchangeAdd(&g_hwy_n_put, hp->nput);
    InterlockedExchangeAdd(&g_hwy_n_rev, hp->nrev);
    if (hp->nput || hp->nrev || !strcmp(hp->who, "load"))
        logf("hwy: %s pass over (%d,%d)-(%d,%d): %d written, %d reverted", hp->who, hp->x0, hp->z0, hp->x1, hp->z1,
             hp->nput, hp->nrev);
    VirtualFree(hp->b.c, 0, MEM_RELEASE);
    hp->b.c = NULL;
}

static int hwy_install(void) {
    if (env_off("SC3NETMOD_HWY")) { g_hwy_off = 1; g_hwy_np = 0; g_hwy_t[0] = 0; logf("hwy: off (SC3NETMOD_HWY=0)"); }
    if (!g_hwy_np) logf("hwy: no highway-program pieces in the tables");
    return g_hwy_np > 0;
}

static void hwy_stats(void) {
    static LONG last;
    LONG n = g_hwy_n_pass + g_hwy_n_put + g_hwy_n_rev + g_hwy_n_load + g_hwy_n_fault;
    if (!g_hwy_np || n == last) return;
    last = n;
    logf("stats: hwy HWAY passes=%ld, load passes=%ld, cells written=%ld, reverted=%ld, faults=%ld", g_hwy_n_pass,
         g_hwy_n_load, g_hwy_n_put, g_hwy_n_rev, g_hwy_n_fault);
}
