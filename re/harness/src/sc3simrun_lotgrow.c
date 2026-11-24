/* ============================================================ LOTGROW (non-square zoned buildings)
 * Owner 2026-11-24 ("build the full version", round 2026-11-24d, design re/analysis/LOT_SHAPES.md section 11).
 * Included by sc3simrun.c (the mod that already patches the zone developer: CHURN, SANDBOX, GENTLE, LVWRAP).
 *
 * Stock: a zone tile's develop call (SIMRCI 0x10029666) hands a W x D buildable block to up to 4 rules at random through
 * the rule interface's slot 0x1c, Apply(rect*, class, demand - filled, max), thiscall, ret 0x10. The generic Apply bodies
 * read each member's SizeInCellsX (attrib vt+0x40) and use it for BOTH axes: n-1+dx < W, n-1+dz < D, an n x n mark on a
 * 10 x 10 local grid (stride 10, row = x), corner offsets by n. None calls SizeInCellsZ (vt+0x44). Everything after
 * Apply is already X x Z: PlaceBuilding ZoneLayer vt+0x68 (0x10032dfc) claims, checks and clears X x Z, re-placement on
 * abandon / construction (0x10029a38) uses the origin, the evaluator (0x10028f12) visits a building at its origin.
 *
 * LOTGROW replaces the 9 generic bodies with C copies that take X from vt+0x40 and Z from vt+0x44, by rewriting the 9
 * rule-vtable slots (SIMRCI .rdata, table in sc3simrun_lotgrow_tab.h, made by re/tools/lotgrow_tab.py):
 *   block fill (kind 0): 0x10026b01 (no transport test), 0x10020762 0x10014794 0x100152a2 0x10013c66 0x1000c3eb
 *                        (the same code with a per-cell IsNearTransport test, ZoneLayer vt+0x6c(&cell, rule+0x30))
 *   corners + strip + fill (kind 1): 0x10027699, 0x1000dd1a
 *   com block (kind 2): 0x1000cf87
 * Each copy follows its body instruction for instruction (disassembly notes inline), including every RNG call
 * (cRZRandom::RandomUint32Uniform 0x10039a9a on rule+0x18) and every ZoneLayer call with the same arguments. A member
 * with X == Z takes exactly the stock path, so a city with only square buildings grows as stock. With X != Z:
 *   - the z extent uses Z (bounds, the grid mark: X rows of Z bytes, corner and strip offsets on z),
 *   - the anchor is refused unless all X x Z grid cells are free (stock tests the anchor only and lets PlaceBuilding
 *     remove what a square overlaps; a rectangle is held to the stricter rule),
 *   - it is refused while sc3perf LOTRECT is not installed (the lot would draw cut), and when X > Z (a stand-in for a
 *     missing X > Z key overlaps its neighbour, LOT_SHAPES 11.3) or |X - Z| != 1 (LOTRECT's draw order is exact only
 *     there, 8.3). A refused member is "does not fit": the RNG sequence is the stock one.
 * The fixed layouts (row houses, large lot, L blocks, farm, ports) are not touched.
 *
 * Switch: simrun.ini [lotgrow] enabled=1 (default), env SC3SIMRUN_LOTGROW=0 = stock (slots untouched). Mods page row
 *   "Non-square zoned buildings" (sc3resize MODTOGGLE, '-' row) writes [env] SC3SIMRUN_LOTGROW=0 when unchecked.
 * Verify: SC3SIMRUN_LOTGROW_VERIFY=1 (or [lotgrow] verify=1) runs every Apply twice: the C copy for real, recording its
 *   ZoneLayer calls and answers, then the STOCK body on the same rect / class / demand with the rule's RNG seed put
 *   back and rule+0x38 pointed at a replay layer that checks each call against the record and returns the recorded
 *   answer. Same calls in the same order with the same arguments, same final seed and the same result = identical
 *   growth. The world only sees the C copy's calls. Counts in the log every minute and in sc3simrun_lotgrow().
 * Log: SC3SIMRUN_LOTGROW_LOG=1 logs every non-square placement attempt.
 * Byte check: SIMRCI TimeDateStamp + SizeOfImage, each slot's pointer, and an FNV-1a hash of each body with its
 *   relocated dwords zeroed (so any other patch inside a body leaves LOTGROW off). All or nothing. */

#define LG_NRULES 9
#define LG_MAXREL 24
typedef struct {
    const char *name;
    DWORD body; int len; DWORD slot;
    int kind, transport;                 /* kind 0: per-cell transport test; kind 1: skip corners on an empty list */
    DWORD tune[6];                       /* demand %, min W, min D, max W, max D, pick % (VA, rebased at arm) */
    int nrel; WORD rel[LG_MAXREL];
    DWORD hash;
} LG_RULE;
#include "sc3simrun_lotgrow_tab.h"

enum { T_DEM, T_MINW, T_MIND, T_MAXW, T_MAXD, T_PICK };

static int g_lg_on = 1, g_lg_verify = 0, g_lg_log = 0, g_lg_armed = 0;
static DWORD g_lg_delta;
static DWORD g_lg_orig[LG_NRULES];       /* stock body address (rebased) */
static DWORD *g_lg_tune[LG_NRULES][6];

typedef DWORD (__fastcall *PFN_LgRand)(void *rng, void *edx, DWORD range);
typedef DWORD (__fastcall *PFN_LgGet)(void *obj, void *edx);
typedef DWORD (__fastcall *PFN_L68)(void *l, void *edx, void *attrib, DWORD *cell, DWORD st, DWORD rot, DWORD chk);
typedef DWORD (__fastcall *PFN_L6C)(void *l, void *edx, DWORD *cell, DWORD arg);
typedef DWORD (__fastcall *PFN_L70)(void *l, void *edx, DWORD *a, DWORD *b);
typedef BYTE (__fastcall *PFN_Apply)(void *rule, void *edx, DWORD *rect, DWORD cls, int dem, int max);
static PFN_LgRand g_lg_rand;

/* counts (game thread writes, logged / exported) */
static volatile LONG g_lg_calls[LG_NRULES], g_lg_nsq_try[LG_NRULES], g_lg_nsq_ok[LG_NRULES], g_lg_nsq_refused;
static volatile LONG g_lg_v_cmp, g_lg_v_same, g_lg_v_diff, g_lg_v_skip, g_lg_v_calls;
static volatile LONG g_lg_v_diff_nsq;    /* of g_lg_v_diff: calls where a non-square member was drawn (expected) */
static DWORD g_lg_last_sum;
static volatile __int64 g_lg_qpc;           /* QPC ticks spent in Apply (C copy; verify mode adds the stock replay) */

static void lotgrow_ini(const char *path) {
    char env[16];
    if (path[0]) {
        g_lg_on = GetPrivateProfileIntA("lotgrow", "enabled", 1, path) ? 1 : 0;
        g_lg_verify = GetPrivateProfileIntA("lotgrow", "verify", 0, path) ? 1 : 0;
    }
    if (GetEnvironmentVariableA("SC3SIMRUN_LOTGROW", env, sizeof(env))) g_lg_on = env[0] == '1';
    if (GetEnvironmentVariableA("SC3SIMRUN_LOTGROW_VERIFY", env, sizeof(env))) g_lg_verify = env[0] == '1';
    if (GetEnvironmentVariableA("SC3SIMRUN_LOTGROW_LOG", env, sizeof(env))) g_lg_log = env[0] == '1';
}

/* ---- LOTRECT present? sc3perf replaces SIMSPR 0x10019341 (sprite insert) with a jmp into sc3perf.dll last of all
   its sites (sc3perf_lotrect.c patch_lotrect). Checked when a non-square member first comes up, cached once true. */
static int g_lg_lotrect = 0;
static DWORD g_lg_lr_next;
static int lg_lotrect_on(void) {
    BYTE *spr, *perf, *t;
    DWORD now;
    if (g_lg_lotrect) return 1;
    now = GetTickCount();
    if ((LONG)(now - g_lg_lr_next) < 0) return 0;
    g_lg_lr_next = now + 10000;
    spr = (BYTE *)GetModuleHandleA("SIMSPR.DLL");
    perf = (BYTE *)GetModuleHandleA("sc3perf.dll");
    if (!spr || !perf) return 0;
    __try {
        IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(perf + ((IMAGE_DOS_HEADER *)perf)->e_lfanew);
        if (spr[0x19341] != 0xE9) return 0;
        t = spr + 0x19346 + *(LONG *)(spr + 0x19342);
        if (t >= perf && t < perf + nt->OptionalHeader.SizeOfImage) g_lg_lotrect = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    if (g_lg_lotrect) logf("LOTGROW> sc3perf LOTRECT is installed: non-square members may be placed");
    return g_lg_lotrect;
}

/* ---- helpers on the rule object (this): +8/+0xc family records, +0x18 RNG, +0x30 transport arg, +0x38 ZoneLayer */
#define LG_LAYER(rule) (*(void **)((rule) + 0x38))
#define LG_VT(o, off) ((*(void ***)(o))[(off) / 4])

static DWORD lg_rand(BYTE *rule, DWORD range) { return g_lg_rand(rule + 0x18, NULL, range); }

static DWORD lg_e70(BYTE *rule, DWORD ax, DWORD az, DWORD bx, DWORD bz) {   /* road-adjacent count along an edge */
    DWORD a[2], b[2];
    void *l = LG_LAYER(rule);
    a[0] = ax; a[1] = az; b[0] = bx; b[1] = bz;
    return ((PFN_L70)LG_VT(l, 0x70))(l, NULL, a, b);
}
static BYTE lg_e6c(BYTE *rule, DWORD *cell, DWORD arg) {
    void *l = LG_LAYER(rule);
    return (BYTE)((PFN_L6C)LG_VT(l, 0x6c))(l, NULL, cell, arg);
}
static BYTE lg_place(BYTE *rule, void *attrib, DWORD *cell) {   /* PlaceBuilding(attrib, cell, 4, 0 degrees, check 1) */
    void *l = LG_LAYER(rule);
    return (BYTE)((PFN_L68)LG_VT(l, 0x68))(l, NULL, attrib, cell, 4, 0, 1);
}
static DWORD lg_sx(void *a) { return ((PFN_LgGet)LG_VT(a, 0x40))(a, NULL); }   /* SizeInCellsX */
static DWORD lg_sz(void *a) { return ((PFN_LgGet)LG_VT(a, 0x44))(a, NULL); }   /* SizeInCellsZ */

static void lg_fill(BYTE *g, DWORD nx, DWORD nz) {      /* stock: rep stosd 0x01010101 + rep stosb, rows step 10 */
    DWORD i;
    for (i = 0; i < nx; i++) memset(g + i * 10, 1, nz);
}
static int lg_free(const BYTE *g, DWORD nx, DWORD nz) {
    DWORD i, j;
    for (i = 0; i < nx; i++) for (j = 0; j < nz; j++) if (g[i * 10 + j]) return 0;
    return 1;
}

/* Z for a member whose X is n: n itself for a square; for a rectangle, Z if this member may be placed now, else 0
   ("refuse": the caller treats it as not fitting). */
static DWORD lg_member_z(int ri, void *a, DWORD n, DWORD *cell) {
    DWORD z = lg_sz(a);
    if (z == n) return n;
    InterlockedIncrement(&g_lg_nsq_try[ri]);
    if (n == 0 || z == 0 || n > z || z - n != 1 || !lg_lotrect_on()) {
        InterlockedIncrement(&g_lg_nsq_refused);
        if (g_lg_log) logf("LOTGROW> %s: %lu x %lu member refused at (%lu, %lu): %s", g_lg_rules[ri].name, n, z,
                           cell ? cell[0] : 0, cell ? cell[1] : 0,
                           !lg_lotrect_on() ? "LOTRECT is not installed" : n > z ? "X > Z" : "sides differ by more than 1");
        return 0;
    }
    return z;
}
static void lg_nsq_placed(int ri, DWORD n, DWORD z, DWORD *cell, BYTE ok) {
    if (ok) InterlockedIncrement(&g_lg_nsq_ok[ri]);
    if (g_lg_log) logf("LOTGROW> %s: %lu x %lu placed at (%lu, %lu): %s", g_lg_rules[ri].name, n, z, cell[0], cell[1],
                       ok ? "yes" : "PlaceBuilding refused");
}

/* the common head of all 9 bodies: demand %, family record, block crop. Returns the record index or -1. */
typedef struct { DWORD x0, z0, x1, z1, W, D; } LG_BLOCK;
static int lg_head(int ri, BYTE *rule, const DWORD *rect, DWORD cls, int dem, int max, DWORD stride, LG_BLOCK *b) {
    DWORD **t = g_lg_tune[ri];
    DWORD cnt, i;
    DWORD *rec;
    if (dem * 100 / max < (int)*t[T_DEM]) return -1;                              /* imul, cdq, idiv; jl */
    cnt = (DWORD)((int)(*(DWORD *)(rule + 0xc) - *(DWORD *)(rule + 8)) / (int)stride);   /* cdq, idiv */
    rec = *(DWORD **)(rule + 8);
    for (i = 0; i < cnt; i++, rec = (DWORD *)((BYTE *)rec + stride)) if (rec[0] == cls) break;   /* jb loop */
    if (i == cnt) return -1;
    b->x0 = rect[0]; b->z0 = rect[1]; b->x1 = rect[2]; b->z1 = rect[3];
    b->W = b->x1 - b->x0 + 1;
    b->D = b->z1 - b->z0 + 1;
    if ((int)b->W < (int)*t[T_MINW] || (int)b->D < (int)*t[T_MIND]) return -1;   /* jl */
    if ((int)b->W > (int)*t[T_MAXW]) {                                             /* jle skips */
        int e0 = (int)lg_e70(rule, b->x0, b->z1, b->x0, b->z0);
        int e1 = (int)lg_e70(rule, b->x1, b->z0, b->x1, b->z1);
        if (e0 > e1) b->x1 = *t[T_MAXW] - 1 + b->x0; else b->x0 = b->x1 - *t[T_MAXW] + 1;
        b->W = *t[T_MAXW];
    }
    if ((int)b->D > (int)*t[T_MAXD]) {
        int e0 = (int)lg_e70(rule, b->x0, b->z0, b->x1, b->z0);
        int e1 = (int)lg_e70(rule, b->x1, b->z1, b->x0, b->z1);
        if (e0 > e1) b->z1 = *t[T_MAXD] - 1 + b->z0; else b->z0 = b->z1 - *t[T_MAXD] + 1;
        b->D = *t[T_MAXD];
    }
    return (int)i;
}

static void lg_zero(BYTE *grid, int ri) {        /* max W rows of max D bytes, as stock (both tunables capped at 10) */
    DWORD r, mw = *g_lg_tune[ri][T_MAXW], md = *g_lg_tune[ri][T_MAXD];
    for (r = 0; r < mw && r < 10; r++) memset(grid + r * 10, 0, md > 10 ? 10 : md);
}

#define LG_LIST(rule, ri_off, i, stride, off) (*(void ***)(*(BYTE **)((rule) + 8) + (i) * (stride) + (off)))
#define LG_LEN(rule, i, stride, off) ((DWORD)((int)(*(BYTE **)(*(BYTE **)((rule) + 8) + (i) * (stride) + (off) + 4) - \
                                              *(BYTE **)(*(BYTE **)((rule) + 8) + (i) * (stride) + (off))) >> 2))

/* ---- kind 0: block fill (SIMRCI 0x10026b01; 0x10020762 and copies with the transport test) */
static BYTE lg_block(int ri, BYTE *rule, const DWORD *rect, DWORD cls, int dem, int max) {
    BYTE grid[128];
    LG_BLOCK b;
    DWORD cell[2], nA, nB, pick = *g_lg_tune[ri][T_PICK], tr = g_lg_rules[ri].transport;
    int fi = lg_head(ri, rule, rect, cls, dem, max, 0x1c, &b);
    if (fi < 0) return 0;
    lg_zero(grid, ri);
    nA = LG_LEN(rule, fi, 0x1c, 4);
    nB = LG_LEN(rule, fi, 0x1c, 0x10);
    for (cell[0] = b.x0; cell[0] <= b.x1; cell[0]++)               /* ja (unsigned) */
        for (cell[1] = b.z0; cell[1] <= b.z1; cell[1]++) {
            DWORD dx = cell[0] - b.x0, dz = cell[1] - b.z0, r, n, z;
            BYTE *g = grid + dx * 10 + dz;
            void *a;
            if (*g) { *g = 1; continue; }
            if (tr && !lg_e6c(rule, cell, *(DWORD *)(rule + 0x30))) { *g = 1; continue; }   /* 0x10020a46: mark */
            r = lg_rand(rule, 100);
            if (r < pick) { r = lg_rand(rule, nA); a = LG_LIST(rule, 0, fi, 0x1c, 4)[r]; }
            else          { r = lg_rand(rule, nB); a = LG_LIST(rule, 0, fi, 0x1c, 0x10)[r]; }
            n = lg_sx(a);
            z = lg_member_z(ri, a, n, cell);
            if (z == n) {                                           /* stock path */
                if (n - 1 + dx < b.W && n - 1 + dz < b.D && lg_place(rule, a, cell) && n != 0) lg_fill(g, n, n);
            } else if (z && n - 1 + dx < b.W && z - 1 + dz < b.D && lg_free(g, n, z)) {
                BYTE ok = lg_place(rule, a, cell);
                lg_nsq_placed(ri, n, z, cell, ok);
                if (ok) lg_fill(g, n, z);
            }
        }
    return 1;
}

/* ---- kind 1: corner lots + strip + fill (SIMRCI 0x10027699, 0x1000dd1a). Variables named after 0x10027699:
   P = [ebp-0x14]/[ebp-0x10] (place cell, also the strip loop), strip box [ebp-0x1c..-8], flag [ebp+0xb]. */
static BYTE lg_corner(int ri, BYTE *rule, const DWORD *rect, DWORD cls, int dem, int max) {
    BYTE grid[128];
    LG_BLOCK b;
    DWORD e[4], P[2], nA, nB, nC, c, pick = *g_lg_tune[ri][T_PICK];
    int fi = lg_head(ri, rule, rect, cls, dem, max, 0x28, &b);
    if (fi < 0) return 0;
    e[0] = lg_e70(rule, b.x0, b.z0, b.x1, b.z0);
    e[1] = lg_e70(rule, b.x1, b.z0, b.x1, b.z1);
    e[2] = lg_e70(rule, b.x1, b.z1, b.x0, b.z1);
    e[3] = lg_e70(rule, b.x0, b.z1, b.x0, b.z0);
    lg_zero(grid, ri);
    nA = LG_LEN(rule, fi, 0x28, 4);
    nB = LG_LEN(rule, fi, 0x28, 0x10);
    nC = LG_LEN(rule, fi, 0x28, 0x1c);
    if (nB != 0 || !g_lg_rules[ri].transport)   /* 0x10027699: jbe 0x10027cb4 (flag 1); 0x1000dd1a: no guard */
        for (c = 0; c < 4; c++) {
            DWORD prev = c ? c - 1 : 3, wp, wc, n, X, Z, r, sx0 = 0, sz0 = 0, sx1 = 0, sz1 = 0, dx, dz;
            int strip = 0, refuse;
            void *a;
            wp = (c == 0 || c == 2) ? b.D : b.W;                    /* 0x10027916..0x1002793d */
            wc = (c == 0 || c == 2) ? b.W : b.D;
            if (e[prev] != wp || e[c] != wc) continue;
            r = lg_rand(rule, nB);
            a = LG_LIST(rule, 0, fi, 0x28, 0x10)[r];
            n = lg_sx(a);
            Z = lg_member_z(ri, a, n, NULL);
            X = n;
            refuse = Z == 0;
            if (refuse) Z = n;      /* a refused rectangle takes the n x n path (same RNG calls) and is not placed */
            switch (c) {
            case 0:                                                 /* 0x10027ada */
                P[0] = b.x0; P[1] = b.z0;
                r = lg_rand(rule, 100);
                if (r < 0x28) { if ((int)b.D > (int)Z) { sx0 = b.x0; sz0 = b.z0 + Z; sx1 = b.x0 + X - 1; sz1 = b.z0 + Z; strip = 1; } }
                else if (r < 0x50) { if ((int)b.W > (int)X) { sx0 = sx1 = b.x0 + X; sz0 = b.z0; sz1 = b.z0 + Z - 1; strip = 1; } }
                break;
            case 1:                                                 /* 0x10027a88 */
                if ((int)X > (int)b.W) continue;
                P[0] = b.x1 - X + 1; P[1] = b.z0;
                r = lg_rand(rule, 100);
                if (r < 0x28) { if ((int)b.D > (int)Z) { sx0 = b.x1 - X + 1; sz0 = b.z0 + Z; sx1 = b.x1; sz1 = b.z0 + Z; strip = 1; } }
                else if (r < 0x50) { if ((int)b.W > (int)X) { sx0 = sx1 = b.x1 - X; sz0 = b.z0; sz1 = b.z0 + Z - 1; strip = 1; } }
                break;
            case 2:                                                 /* 0x10027a04 */
                if ((int)X > (int)b.W || (int)Z > (int)b.D) continue;
                P[0] = b.x1 - X + 1; P[1] = b.z1 - Z + 1;
                r = lg_rand(rule, 100);
                if (r < 0x28) { if ((int)b.D > (int)Z) { sx0 = b.x1 - X + 1; sz0 = b.z1 - Z; sx1 = b.x1; sz1 = b.z1 - Z; strip = 1; } }
                else if (r < 0x50) { if ((int)b.W > (int)X) { sx0 = sx1 = b.x1 - X; sz0 = b.z1 - Z + 1; sz1 = b.z1; strip = 1; } }
                break;
            default:                                                /* c == 3, 0x10027980 */
                if ((int)Z > (int)b.D) continue;
                P[0] = b.x0; P[1] = b.z1 - Z + 1;
                r = lg_rand(rule, 100);
                if (r < 0x28) { if ((int)b.D > (int)Z) { sx0 = b.x0; sz0 = b.z1 - Z; sx1 = b.x0 + X - 1; sz1 = b.z1 - Z; strip = 1; } }
                else if (r < 0x50) { if ((int)b.W > (int)X) { sx0 = sx1 = b.x0 + X; sz0 = b.z1 - Z + 1; sz1 = b.z1; strip = 1; } }
                break;
            }
            if (P[0] + X - 1 > b.x1 || P[1] + Z - 1 > b.z1) continue;   /* 0x10027b37: ja */
            if (refuse) continue;
            dx = P[0] - b.x0; dz = P[1] - b.z0;
            if (X != Z) {
                BYTE ok;
                if (!lg_free(grid + dx * 10 + dz, X, Z)) continue;
                ok = lg_place(rule, a, P);
                lg_nsq_placed(ri, X, Z, P, ok);
                if (!ok) continue;
            } else if (!lg_place(rule, a, P)) continue;
            if ((int)X > 0) lg_fill(grid + dx * 10 + dz, X, Z);
            if (!strip) continue;
            r = lg_rand(rule, nC);
            a = LG_LIST(rule, 0, fi, 0x28, 0x1c)[r];
            for (P[0] = sx0; P[0] <= sx1; P[0]++)                   /* 0x10027be7.. */
                for (P[1] = sz0; P[1] <= sz1; P[1]++) {
                    DWORD m, mz;
                    BYTE *g;
                    dx = P[0] - b.x0; dz = P[1] - b.z0;
                    g = grid + dx * 10 + dz;
                    if (*g) continue;
                    m = lg_sx(a);
                    mz = lg_member_z(ri, a, m, P);
                    if (mz == m) {
                        if (m - 1 + dx >= b.W || m - 1 + dz >= b.D) continue;
                        if (!lg_place(rule, a, P) || (int)m <= 0) continue;
                        lg_fill(g, m, m);
                    } else if (mz && m - 1 + dx < b.W && mz - 1 + dz < b.D && lg_free(g, m, mz)) {
                        BYTE ok = lg_place(rule, a, P);
                        lg_nsq_placed(ri, m, mz, P, ok);
                        if (ok) lg_fill(g, m, mz);
                    }
                }
        }
    for (P[0] = b.x0; P[0] <= b.x1; P[0]++)                         /* 0x10027cb4 fill */
        for (P[1] = b.z0; P[1] <= b.z1; P[1]++) {
            DWORD dx = P[0] - b.x0, dz = P[1] - b.z0, r, m, mz;
            BYTE *g = grid + dx * 10 + dz;
            void *a;
            if (*g) continue;
            r = lg_rand(rule, 100);
            if (r < pick) { r = lg_rand(rule, nA); a = LG_LIST(rule, 0, fi, 0x28, 4)[r]; }
            else          { r = lg_rand(rule, nC); a = LG_LIST(rule, 0, fi, 0x28, 0x1c)[r]; }
            m = lg_sx(a);
            mz = lg_member_z(ri, a, m, P);
            if (mz == m) {
                if (m - 1 + dx < b.W && m - 1 + dz < b.D && lg_place(rule, a, P) && (int)m > 0) lg_fill(g, m, m);
            } else if (mz && m - 1 + dx < b.W && mz - 1 + dz < b.D && lg_free(g, m, mz)) {
                BYTE ok = lg_place(rule, a, P);
                lg_nsq_placed(ri, m, mz, P, ok);
                if (ok) lg_fill(g, m, mz);
            }
        }
    return 1;
}

/* ---- kind 2: commercial block (SIMRCI 0x1000cf87): one corner lot per road-lined corner, then the fill with the
   transport-weighted pick (vt+0x6c(&cell, 1): p = 100 - pick on a transport cell, else pick). */
static BYTE lg_comblock(int ri, BYTE *rule, const DWORD *rect, DWORD cls, int dem, int max) {
    BYTE grid[128];
    LG_BLOCK b;
    DWORD e[4], P[2], nA, nB, nC, c, pick = *g_lg_tune[ri][T_PICK];
    int fi = lg_head(ri, rule, rect, cls, dem, max, 0x28, &b);
    if (fi < 0) return 0;
    e[0] = lg_e70(rule, b.x0, b.z0, b.x1, b.z0);
    e[1] = lg_e70(rule, b.x1, b.z0, b.x1, b.z1);
    e[2] = lg_e70(rule, b.x1, b.z1, b.x0, b.z1);
    e[3] = lg_e70(rule, b.x0, b.z1, b.x0, b.z0);
    lg_zero(grid, ri);
    nA = LG_LEN(rule, fi, 0x28, 4);
    nB = LG_LEN(rule, fi, 0x28, 0x10);
    nC = LG_LEN(rule, fi, 0x28, 0x1c);
    for (c = 0; c < 4; c++) {                                       /* no nB guard in this body (0x1000d1fd) */
        DWORD prev = c ? c - 1 : 3, wp, wc, n, X, Z, r, dx, dz;
        void *a;
        wp = (c == 0 || c == 2) ? b.D : b.W;
        wc = (c == 0 || c == 2) ? b.W : b.D;
        if (e[prev] != wp || e[c] != wc) continue;
        r = lg_rand(rule, nB);
        a = LG_LIST(rule, 0, fi, 0x28, 0x10)[r];
        n = lg_sx(a);
        Z = lg_member_z(ri, a, n, NULL);
        X = n;
        if (!Z) continue;
        if ((int)X > (int)b.W || (int)Z > (int)b.D) continue;      /* jg, jg */
        switch (c) {
        case 0: P[0] = b.x0;         P[1] = b.z0;         break;
        case 1: P[0] = b.x1 - X + 1; P[1] = b.z0;         break;
        case 2: P[0] = b.x1 - X + 1; P[1] = b.z1 - Z + 1; break;
        default: P[0] = b.x0;        P[1] = b.z1 - Z + 1; break;
        }
        dx = P[0] - b.x0; dz = P[1] - b.z0;
        if (X != Z) {
            BYTE ok;
            if (!lg_free(grid + dx * 10 + dz, X, Z)) continue;
            ok = lg_place(rule, a, P);
            lg_nsq_placed(ri, X, Z, P, ok);
            if (!ok) continue;
        } else if (!lg_place(rule, a, P)) continue;
        if ((int)X > 0) lg_fill(grid + dx * 10 + dz, X, Z);
    }
    for (P[0] = b.x0; P[0] <= b.x1; P[0]++)                         /* 0x1000d32c fill */
        for (P[1] = b.z0; P[1] <= b.z1; P[1]++) {
            DWORD dx = P[0] - b.x0, dz = P[1] - b.z0, r, p, m, mz;
            BYTE *g = grid + dx * 10 + dz;
            void *a;
            if (*g) continue;
            p = lg_e6c(rule, P, 1) ? 100 - pick : pick;
            r = lg_rand(rule, 100);
            if (r < p) { r = lg_rand(rule, nA); a = LG_LIST(rule, 0, fi, 0x28, 4)[r]; }
            else       { r = lg_rand(rule, nC); a = LG_LIST(rule, 0, fi, 0x28, 0x1c)[r]; }
            m = lg_sx(a);
            mz = lg_member_z(ri, a, m, P);
            if (mz == m) {
                if (m - 1 + dx < b.W && m - 1 + dz < b.D && lg_place(rule, a, P) && (int)m > 0) lg_fill(g, m, m);
            } else if (mz && m - 1 + dx < b.W && mz - 1 + dz < b.D && lg_free(g, m, mz)) {
                BYTE ok = lg_place(rule, a, P);
                lg_nsq_placed(ri, m, mz, P, ok);
                if (ok) lg_fill(g, m, mz);
            }
        }
    return 1;
}

static BYTE lg_body(int ri, BYTE *rule, DWORD *rect, DWORD cls, int dem, int max) {
    switch (g_lg_rules[ri].kind) {
    case 0: return lg_block(ri, rule, rect, cls, dem, max);
    case 1: return lg_corner(ri, rule, rect, cls, dem, max);
    default: return lg_comblock(ri, rule, rect, cls, dem, max);
    }
}

/* ============ verify: record the C copy's ZoneLayer calls, replay them to the stock body */
typedef struct { DWORD slot, a[6], ret; } LG_CALL;
#define LG_MAXCALLS 4096
static LG_CALL g_lg_rec[LG_MAXCALLS];
static int g_lg_nrec, g_lg_rpos, g_lg_over, g_lg_bad, g_lg_badlogged;
static char g_lg_badmsg[256];
typedef struct { void **vt; void *real; } LG_PROXY;
static void *g_lg_vt_rec[64], *g_lg_vt_rep[64];

#define LG_FWD(n) static __declspec(naked) void lg_fwd_##n(void) { __asm mov ecx, [ecx + 4] __asm mov eax, [ecx] __asm jmp dword ptr [eax + n * 4] }
/* slots the stock bodies never call on the layer: forward to the real ZoneLayer (slot index = n) */
LG_FWD(0) LG_FWD(1) LG_FWD(2) LG_FWD(3) LG_FWD(4) LG_FWD(5) LG_FWD(6) LG_FWD(7)
LG_FWD(8) LG_FWD(9) LG_FWD(10) LG_FWD(11) LG_FWD(12) LG_FWD(13) LG_FWD(14) LG_FWD(15)
LG_FWD(16) LG_FWD(17) LG_FWD(18) LG_FWD(19) LG_FWD(20) LG_FWD(21) LG_FWD(22) LG_FWD(23)
LG_FWD(24) LG_FWD(25) LG_FWD(26) LG_FWD(27) LG_FWD(28) LG_FWD(29) LG_FWD(30) LG_FWD(31)
LG_FWD(32) LG_FWD(33) LG_FWD(34) LG_FWD(35) LG_FWD(36) LG_FWD(37) LG_FWD(38) LG_FWD(39)
LG_FWD(40) LG_FWD(41) LG_FWD(42) LG_FWD(43) LG_FWD(44) LG_FWD(45) LG_FWD(46) LG_FWD(47)
LG_FWD(48) LG_FWD(49) LG_FWD(50) LG_FWD(51) LG_FWD(52) LG_FWD(53) LG_FWD(54) LG_FWD(55)
LG_FWD(56) LG_FWD(57) LG_FWD(58) LG_FWD(59) LG_FWD(60) LG_FWD(61) LG_FWD(62) LG_FWD(63)
static void (*const g_lg_fwd[64])(void) = {
    lg_fwd_0, lg_fwd_1, lg_fwd_2, lg_fwd_3, lg_fwd_4, lg_fwd_5, lg_fwd_6, lg_fwd_7,
    lg_fwd_8, lg_fwd_9, lg_fwd_10, lg_fwd_11, lg_fwd_12, lg_fwd_13, lg_fwd_14, lg_fwd_15,
    lg_fwd_16, lg_fwd_17, lg_fwd_18, lg_fwd_19, lg_fwd_20, lg_fwd_21, lg_fwd_22, lg_fwd_23,
    lg_fwd_24, lg_fwd_25, lg_fwd_26, lg_fwd_27, lg_fwd_28, lg_fwd_29, lg_fwd_30, lg_fwd_31,
    lg_fwd_32, lg_fwd_33, lg_fwd_34, lg_fwd_35, lg_fwd_36, lg_fwd_37, lg_fwd_38, lg_fwd_39,
    lg_fwd_40, lg_fwd_41, lg_fwd_42, lg_fwd_43, lg_fwd_44, lg_fwd_45, lg_fwd_46, lg_fwd_47,
    lg_fwd_48, lg_fwd_49, lg_fwd_50, lg_fwd_51, lg_fwd_52, lg_fwd_53, lg_fwd_54, lg_fwd_55,
    lg_fwd_56, lg_fwd_57, lg_fwd_58, lg_fwd_59, lg_fwd_60, lg_fwd_61, lg_fwd_62, lg_fwd_63 };

static void lg_rec_add(DWORD slot, const DWORD *a, int na, DWORD ret) {
    LG_CALL *c;
    if (g_lg_nrec >= LG_MAXCALLS) { g_lg_over = 1; return; }
    c = &g_lg_rec[g_lg_nrec++];
    memset(c, 0, sizeof(*c));
    c->slot = slot; memcpy(c->a, a, na * sizeof(DWORD)); c->ret = ret;
}
static DWORD lg_rep_take(DWORD slot, const DWORD *a, int na) {
    LG_CALL *c;
    DWORD z[6];
    if (g_lg_rpos >= g_lg_nrec) {
        if (!g_lg_bad) _snprintf(g_lg_badmsg, sizeof(g_lg_badmsg) - 1, "stock made an extra call vt+0x%02lX after %d", slot, g_lg_nrec);
        g_lg_bad = 1;
        return 0;
    }
    c = &g_lg_rec[g_lg_rpos++];
    memset(z, 0, sizeof(z)); memcpy(z, a, na * sizeof(DWORD));
    if (c->slot != slot || memcmp(c->a, z, sizeof(z))) {
        if (!g_lg_bad)
            _snprintf(g_lg_badmsg, sizeof(g_lg_badmsg) - 1, "call %d: copy vt+0x%02lX (%lX %lX %lX %lX %lX), stock vt+0x%02lX (%lX %lX %lX %lX %lX)",
                      g_lg_rpos - 1, c->slot, c->a[0], c->a[1], c->a[2], c->a[3], c->a[4], slot, z[0], z[1], z[2], z[3], z[4]);
        g_lg_bad = 1;
    }
    return c->ret;
}
static DWORD __fastcall lg_rec68(LG_PROXY *p, void *edx, void *attrib, DWORD *cell, DWORD st, DWORD rot, DWORD chk) {
    DWORD a[6], r = ((PFN_L68)LG_VT(p->real, 0x68))(p->real, NULL, attrib, cell, st, rot, chk);
    (void)edx;
    a[0] = (DWORD)attrib; a[1] = cell[0]; a[2] = cell[1]; a[3] = st; a[4] = rot; a[5] = chk;
    lg_rec_add(0x68, a, 6, r & 0xff);
    return r;
}
static DWORD __fastcall lg_rec6c(LG_PROXY *p, void *edx, DWORD *cell, DWORD arg) {
    DWORD a[3], r = ((PFN_L6C)LG_VT(p->real, 0x6c))(p->real, NULL, cell, arg);
    (void)edx;
    a[0] = cell[0]; a[1] = cell[1]; a[2] = arg;
    lg_rec_add(0x6c, a, 3, r & 0xff);
    return r;
}
static DWORD __fastcall lg_rec70(LG_PROXY *p, void *edx, DWORD *pa, DWORD *pb) {
    DWORD a[4], r = ((PFN_L70)LG_VT(p->real, 0x70))(p->real, NULL, pa, pb);
    (void)edx;
    a[0] = pa[0]; a[1] = pa[1]; a[2] = pb[0]; a[3] = pb[1];
    lg_rec_add(0x70, a, 4, r);
    return r;
}
static DWORD __fastcall lg_rep68(LG_PROXY *p, void *edx, void *attrib, DWORD *cell, DWORD st, DWORD rot, DWORD chk) {
    DWORD a[6];
    (void)p; (void)edx;
    a[0] = (DWORD)attrib; a[1] = cell[0]; a[2] = cell[1]; a[3] = st; a[4] = rot; a[5] = chk;
    return lg_rep_take(0x68, a, 6);
}
static DWORD __fastcall lg_rep6c(LG_PROXY *p, void *edx, DWORD *cell, DWORD arg) {
    DWORD a[3];
    (void)p; (void)edx;
    a[0] = cell[0]; a[1] = cell[1]; a[2] = arg;
    return lg_rep_take(0x6c, a, 3);
}
static DWORD __fastcall lg_rep70(LG_PROXY *p, void *edx, DWORD *pa, DWORD *pb) {
    DWORD a[4];
    (void)p; (void)edx;
    a[0] = pa[0]; a[1] = pa[1]; a[2] = pb[0]; a[3] = pb[1];
    return lg_rep_take(0x70, a, 4);
}

static void lg_verify_init(void) {
    int i;
    for (i = 0; i < 64; i++) g_lg_vt_rec[i] = g_lg_vt_rep[i] = (void *)g_lg_fwd[i];
    g_lg_vt_rec[0x68 / 4] = (void *)lg_rec68; g_lg_vt_rec[0x6c / 4] = (void *)lg_rec6c; g_lg_vt_rec[0x70 / 4] = (void *)lg_rec70;
    g_lg_vt_rep[0x68 / 4] = (void *)lg_rep68; g_lg_vt_rep[0x6c / 4] = (void *)lg_rep6c; g_lg_vt_rep[0x70 / 4] = (void *)lg_rep70;
}

static void lg_summary(int force) {
    DWORD t = GetTickCount();
    int i;
    char buf[512];
    int k = 0;
    if (!force && t - g_lg_last_sum < 60000) return;
    g_lg_last_sum = t;
    for (i = 0; i < LG_NRULES; i++)
        k += _snprintf(buf + k, sizeof(buf) - 1 - k, "%s%s %ld", i ? ", " : "", g_lg_rules[i].name, g_lg_calls[i]);
    buf[sizeof(buf) - 1] = 0;
    logf("LOTGROW> Apply calls: %s", buf);
    k = 0;
    for (i = 0; i < LG_NRULES; i++)
        if (g_lg_nsq_try[i]) k += _snprintf(buf + k, sizeof(buf) - 1 - k, " %s %ld/%ld", g_lg_rules[i].name, g_lg_nsq_ok[i], g_lg_nsq_try[i]);
    buf[k] = 0;
    {   LONG n = 0;
        for (i = 0; i < LG_NRULES; i++) n += g_lg_calls[i];
        logf("LOTGROW> time in Apply: %.1f ms over %ld calls (%.4f ms per call, PlaceBuilding included)",
             (double)g_lg_qpc * 1000.0 / (double)g_freq.QuadPart, n,
             n ? (double)g_lg_qpc * 1000.0 / (double)g_freq.QuadPart / n : 0.0);
    }
    logf("LOTGROW> non-square placed/considered:%s%s (refused %ld)", k ? buf : " none", "", g_lg_nsq_refused);
    if (g_lg_verify)
        logf("LOTGROW> verify: %ld Apply calls compared, %ld identical, %ld different (%ld with a non-square member drawn, "
             "%ld UNEXPLAINED), %ld skipped, %ld layer calls checked",
             g_lg_v_cmp, g_lg_v_same, g_lg_v_diff, g_lg_v_diff_nsq, g_lg_v_diff - g_lg_v_diff_nsq, g_lg_v_skip, g_lg_v_calls);
}

static BYTE lg_verify_apply(int ri, BYTE *rule, DWORD *rect, DWORD cls, int dem, int max) {
    LG_PROXY px;
    void *layer = LG_LAYER(rule);
    DWORD seed0 = *(DWORD *)(rule + 0x18), seed1, seed2, rc[4];
    BYTE r1, r2;
    LONG nsq0 = 0, nsq1 = 0;
    int i, nsq;
    for (i = 0; i < LG_NRULES; i++) nsq0 += g_lg_nsq_try[i];
    memcpy(rc, rect, sizeof(rc));
    g_lg_nrec = 0; g_lg_over = 0;
    px.vt = g_lg_vt_rec; px.real = layer;
    LG_LAYER(rule) = &px;
    __try { r1 = lg_body(ri, rule, rect, cls, dem, max); }
    __finally { LG_LAYER(rule) = layer; }
    seed1 = *(DWORD *)(rule + 0x18);
    if (g_lg_over) { InterlockedIncrement(&g_lg_v_skip); return r1; }
    /* the stock body on the same input, seed put back, layer = replay */
    g_lg_rpos = 0; g_lg_bad = 0; g_lg_badmsg[0] = 0;
    *(DWORD *)(rule + 0x18) = seed0;
    px.vt = g_lg_vt_rep;
    LG_LAYER(rule) = &px;
    __try { r2 = ((PFN_Apply)g_lg_orig[ri])(rule, NULL, rc, cls, dem, max); }
    __finally { LG_LAYER(rule) = layer; seed2 = *(DWORD *)(rule + 0x18); *(DWORD *)(rule + 0x18) = seed1; }
    if (!g_lg_bad && g_lg_rpos != g_lg_nrec) {
        _snprintf(g_lg_badmsg, sizeof(g_lg_badmsg) - 1, "stock made %d of the copy's %d calls", g_lg_rpos, g_lg_nrec);
        g_lg_bad = 1;
    }
    if (!g_lg_bad && seed2 != seed1) {
        _snprintf(g_lg_badmsg, sizeof(g_lg_badmsg) - 1, "RNG seed after: copy %08lX, stock %08lX (start %08lX)", seed1, seed2, seed0);
        g_lg_bad = 1;
    }
    if (!g_lg_bad && r1 != r2) {
        _snprintf(g_lg_badmsg, sizeof(g_lg_badmsg) - 1, "result: copy %u, stock %u", r1, r2);
        g_lg_bad = 1;
    }
    for (i = 0; i < LG_NRULES; i++) nsq1 += g_lg_nsq_try[i];
    nsq = nsq1 != nsq0;                          /* a non-square member was drawn in this call: the paths may part */
    InterlockedIncrement(&g_lg_v_cmp);
    InterlockedExchangeAdd(&g_lg_v_calls, g_lg_nrec);
    if (g_lg_bad) {
        InterlockedIncrement(&g_lg_v_diff);
        if (nsq) InterlockedIncrement(&g_lg_v_diff_nsq);
        if ((!nsq && g_lg_badlogged < 500) || g_lg_badlogged < 20) {
            g_lg_badlogged++;
            logf("LOTGROW> VERIFY DIFF%s %s rect (%lu,%lu)-(%lu,%lu) class %lu dem %d max %d: %s",
                 nsq ? " (non-square drawn)" : " UNEXPLAINED", g_lg_rules[ri].name, rc[0], rc[1], rc[2], rc[3], cls, dem, max,
                 g_lg_badmsg);
        }
    } else InterlockedIncrement(&g_lg_v_same);
    return r1;
}

static BYTE lg_apply(int ri, BYTE *rule, DWORD *rect, DWORD cls, int dem, int max) {
    BYTE r;
    LARGE_INTEGER q0, q1;
    InterlockedIncrement(&g_lg_calls[ri]);
    QueryPerformanceCounter(&q0);
    r = g_lg_verify ? lg_verify_apply(ri, rule, rect, cls, dem, max) : lg_body(ri, rule, rect, cls, dem, max);
    QueryPerformanceCounter(&q1);
    g_lg_qpc += q1.QuadPart - q0.QuadPart;      /* game sim thread only */
    lg_summary(0);
    return r;
}

#define LG_THUNK(n) static BYTE __fastcall lg_apply_##n(BYTE *rule, void *edx, DWORD *rect, DWORD cls, int dem, int max) \
    { (void)edx; return lg_apply(n, rule, rect, cls, dem, max); }
LG_THUNK(0) LG_THUNK(1) LG_THUNK(2) LG_THUNK(3) LG_THUNK(4) LG_THUNK(5) LG_THUNK(6) LG_THUNK(7) LG_THUNK(8)
static void *const g_lg_thunk[LG_NRULES] = { (void *)lg_apply_0, (void *)lg_apply_1, (void *)lg_apply_2, (void *)lg_apply_3,
    (void *)lg_apply_4, (void *)lg_apply_5, (void *)lg_apply_6, (void *)lg_apply_7, (void *)lg_apply_8 };

static DWORD lg_hash(const BYTE *p, int n, const WORD *rel, int nrel) {
    DWORD h = 0x811c9dc5u;
    int i, k = 0;
    for (i = 0; i < n; i++) {
        BYTE c = p[i];
        while (k < nrel && i >= rel[k] + 4) k++;
        if (k < nrel && i >= rel[k]) c = 0;
        h = (h ^ c) * 0x01000193u;
    }
    return h;
}

/* all or nothing; returns the number of slots rewritten */
static int lotgrow_arm(HMODULE rci) {
    BYTE *m = (BYTE *)rci;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(m + ((IMAGE_DOS_HEADER *)m)->e_lfanew);
    int i, j, k, n = 0;
    DWORD old;
    g_lg_delta = (DWORD)rci - 0x10000000;
    if (nt->FileHeader.TimeDateStamp != LG_RCI_STAMP || nt->OptionalHeader.SizeOfImage != LG_RCI_SIZE) {
        logf("LOTGROW> SIMRCI.DLL is not the 2.0.949 build (timestamp/size differ): not installed");
        return 0;
    }
    for (i = 0; i < LG_NRULES; i++) {
        const LG_RULE *R = &g_lg_rules[i];
        BYTE *body = (BYTE *)(R->body + g_lg_delta);
        DWORD *slot = (DWORD *)(R->slot + g_lg_delta);
        if (IsBadReadPtr(slot, 4) || *slot != (DWORD)body) {
            logf("LOTGROW> %s: slot SIMRCI 0x%08lX holds 0x%08lX, expected 0x%08lX - not installed (no slot touched)",
                 R->name, R->slot, *slot - g_lg_delta, R->body);
            return 0;
        }
        if (IsBadReadPtr(body, R->len) || lg_hash(body, R->len, R->rel, R->nrel) != R->hash) {
            logf("LOTGROW> %s: body SIMRCI 0x%08lX differs from shipped - not installed (no slot touched)", R->name, R->body);
            return 0;
        }
        for (j = 0; j < 6; j++) {                    /* each tunable is one of the body's relocated operands */
            for (k = 0; k < R->nrel; k++) if (*(DWORD *)(body + R->rel[k]) == R->tune[j] + g_lg_delta) break;
            if (k == R->nrel) { logf("LOTGROW> %s: tunable 0x%08lX not referenced - not installed", R->name, R->tune[j]); return 0; }
            g_lg_tune[i][j] = (DWORD *)(R->tune[j] + g_lg_delta);
        }
        g_lg_orig[i] = (DWORD)body;
    }
    g_lg_rand = (PFN_LgRand)(LG_RAND + g_lg_delta);
    if (g_lg_verify) lg_verify_init();
    for (i = 0; i < LG_NRULES; i++) {
        DWORD *slot = (DWORD *)(g_lg_rules[i].slot + g_lg_delta);
        if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) { logf("LOTGROW> VirtualProtect failed on %s", g_lg_rules[i].name); continue; }
        *slot = (DWORD)g_lg_thunk[i];   /* no restore (task onramp): a restore can land mid-write in another mod */
        n++;
    }
    g_lg_armed = n == LG_NRULES;
    return n;
}

/* measurement: out[0..8] Apply calls per rule, out[9..17] non-square placed, out[18..26] non-square considered,
   out[27] refused, out[28] verify compared, out[29] identical, out[30] different, out[31] skipped, out[32] layer calls
   checked, out[33] armed, out[34] verify on, out[35] LOTRECT seen */
__declspec(dllexport) void __cdecl sc3simrun_lotgrow(DWORD *out) {
    int i;
    for (i = 0; i < LG_NRULES; i++) {
        out[i] = (DWORD)g_lg_calls[i]; out[9 + i] = (DWORD)g_lg_nsq_ok[i]; out[18 + i] = (DWORD)g_lg_nsq_try[i];
    }
    out[27] = (DWORD)g_lg_nsq_refused; out[28] = (DWORD)g_lg_v_cmp; out[29] = (DWORD)g_lg_v_same;
    out[30] = (DWORD)g_lg_v_diff; out[31] = (DWORD)g_lg_v_skip; out[32] = (DWORD)g_lg_v_calls;
    out[33] = (DWORD)g_lg_armed; out[34] = (DWORD)g_lg_verify; out[35] = (DWORD)g_lg_lotrect;
    lg_summary(1);
}
