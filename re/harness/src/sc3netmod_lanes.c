/* sc3netmod_lanes.c - the LANEDENSITY block of sc3netmod.dll (task lanedensity, 2026-10-13). #included by sc3netmod.c
 * above its "arming" section; it reads the variant table (g_base) and uses the patch helpers (write_code,
 * retarget_call, bytes_are). Evidence: re/analysis/LANE_DENSITY.md, verify/lanedensity/.
 *
 * Road traffic density follows the trip router SimTransit FUN_100070d0 (DFS, deposits on the final path only). Its
 * step FUN_1000755e asks the piece's turn matrix (exemplar props 310..312) for highway / bus nodes (types 2, 3,
 * 0x42, 0x43), but a ROAD node (type 1, bus 0x41) takes the ring scan at 0x10007a63: any road cell beside it is a
 * candidate, whatever the piece's lanes [CONFIRMED @ SimTransit 0x1000755e]. This block makes road nodes on an
 * HONOURED piece obey the same matrix, asked the same way the game asks it for highways
 * (piece vt+0x4c(0, *(u8 *)(layer+0x54), entry side) -> 4 exits).
 *
 *   SELECT (entry of FUN_1000755e, 6 bytes -> jmp ld_select): for a 1x1 road node on an honoured piece,
 *     allowed exits = matrix row of the entry side (node+0x1c, world frame) when the node was entered from a network
 *     node (node+0x15 = 1, 2, 3, 0x41..0x43), else (start lot 0x80, stations) the union of the four rows.
 *     - row empty (entered against the lanes): the step fails (the DFS backtracks) and the node's own visited mark,
 *       set by the step that chose it, is cleared, so the cell can still be entered later through a legal side.
 *     - else each road neighbour (+0x5c flags & 0x11 == 1) on a forbidden side gets the node type's bits in the
 *       visited grid (+0x78) for this one call, so the ring scan skips it; the bits this block added are cleared
 *       again after the call. Station neighbours (flag 0x10) stay candidates (a mode change is not a lane).
 *   ARRIVE (call FUN_10008a94 at 0x100071eb): a road node entered against the lanes does not count as arrived.
 * A piece whose matrix half is all zero has no lane data and stays unconstrained.
 *
 * Honoured pieces: variant ids of the netmod tables (g_base != 0). SC3NETMOD_LANEDENSITY=all honours every piece,
 * =count honours nothing but counts, per piece id, the router steps the matrix would forbid (stock check),
 * =0 turns the block off. The visited grid and the node are per trip (sc3perf traffic_mt workers each route on their
 * own shadow layer and marker grid), the caches below are written with interlocked ops, so workers are safe.
 */

#include <tlhelp32.h>
#define LD_MAXTH 1024
static volatile LONG g_ld_on = 1, g_ld_alt_busy, g_ld_n_toggle, g_ld_n_toggle_retry;
static BYTE g_ld_jmp_e[6], g_ld_call_a[5], g_ld_orig_a[5];
static HANDLE g_ld_th[LD_MAXTH];
static int   g_ld_mode;                  /* 0 off, 1 variants, 2 all, 3 count */
static DWORD g_ld_st;                    /* SimTransit base */
static BYTE *g_ld_tramp;                 /* original FUN_1000755e: its 6 entry bytes + jmp +0x7564 */
static DWORD g_ld_arrive_orig;           /* FUN_10008a94 */
static volatile LONG g_ld_nvt;
static volatile LONG g_ld_rows[2][65536 * 4];   /* [half][id*4+state]: bit 31 valid, bits 4e+t = entry e -> exit t */

typedef BYTE  (__fastcall *LD_SEL)(BYTE *layer, void *edx, BYTE *node, BYTE *out, DWORD budget, DWORD p4, DWORD p5, DWORD p6);
typedef DWORD (__fastcall *LD_ARR)(BYTE *layer, void *edx, BYTE *node, DWORD kind);
typedef char  (__fastcall *LD_QI)(void *self, void *edx, DWORD iid, void **out);
typedef void  (__fastcall *LD_REL)(void *self, void *edx);
typedef void  (__fastcall *LD_CONN)(void *self, void *edx, DWORD sel, DWORD half, DWORD dir, BYTE *o0, BYTE *o1, BYTE *o2, BYTE *o3);

/* counters */
static volatile LONG g_ld_n_eval, g_ld_n_hon, g_ld_n_wrong, g_ld_n_premark, g_ld_n_arrblock;
static volatile LONG g_ld_n_slowqi;
static volatile LONG *g_ld_c_steps, *g_ld_c_forbid, *g_ld_c_wrong;   /* count mode, per piece id */

/* per honoured cell: steps by (entry 0..3, 4 = not from the network) x exit, wrong-way entries */
#define LD_NCELL 1024
typedef struct { volatile LONG key; DWORD id; volatile LONG step[5][4]; volatile LONG wrong, arrblock; } LdCell;
static LdCell *g_ld_cells;

static int ld_is_net(BYTE t) { return t == 1 || t == 2 || t == 3 || t == 0x41 || t == 0x42 || t == 0x43; }

static LdCell *ld_cell(DWORD x, DWORD z, DWORD id) {
    LONG key = (LONG)(((x & 0x7fff) << 16) | (z & 0xffff)) | 0x40000000;
    DWORD h = ((x * 2654435761u) ^ (z * 40503u)) & (LD_NCELL - 1), i;
    if (!g_ld_cells) return NULL;
    for (i = 0; i < LD_NCELL; i++) {
        LdCell *c = &g_ld_cells[(h + i) & (LD_NCELL - 1)];
        LONG k = c->key;
        if (k == key) return c;
        if (!k) {
            if (InterlockedCompareExchange(&c->key, key, 0) == 0) { c->id = id; return c; }
            if (c->key == key) return c;
        }
    }
    return NULL;
}

/* The piece object behind a road node's occupant (node+0), or NULL. The occupant is an interface of the piece, not
   its primary object (measured: QI(0x41658d28) never returned the occupant itself), so the fast path caches, per
   occupant vtable, the offset QI returned. A vtable is trusted after 16 identical offsets and dropped for good
   (always QI) if one ever differs. The node holds a reference to the occupant while it is on the DFS stack, so the
   piece stays alive without the QI's reference. */
typedef struct { volatile LONG vt, delta, seen; } LdVt;   /* seen < 0: offsets differed, never trusted */
static LdVt g_ld_vtc[32];

/* Fast path (ld_stub): everything a road step needs to be passed straight to the game without a C call. */
static BYTE  g_ld_hon[65536];            /* 1 = honoured piece id */
static volatile LONG g_ld_fvt[8];         /* trusted occupant vtables ... */
static volatile LONG g_ld_fdl[8];         /* ... and the offset from the occupant to the piece */
static volatile LONG g_ld_ntact;          /* threads whose trip holds refused transitions */
static volatile LONG g_ld_force;          /* 1 = every call takes the C path (count mode) */

static void ld_fast_add(DWORD vt, LONG d) {
    int k;
    EnterCriticalSection(&g_lock);
    for (k = 0; k < 8; k++) {
        if ((DWORD)g_ld_fvt[k] == vt) break;
        if (!g_ld_fvt[k]) { g_ld_fdl[k] = d; MemoryBarrier(); InterlockedExchange(&g_ld_fvt[k], (LONG)vt); break; }
    }
    LeaveCriticalSection(&g_lock);
}

static BYTE *ld_piece(BYTE *occ) {
    DWORD vt, i;
    void *p = NULL;
    LONG d;
    if (!occ) return NULL;
    vt = *(DWORD *)occ;
    for (i = 0; i < 32 && g_ld_vtc[i].vt; i++)
        if ((DWORD)g_ld_vtc[i].vt == vt) {
            if (g_ld_vtc[i].seen >= 16) return occ + g_ld_vtc[i].delta;
            break;
        }
    InterlockedIncrement(&g_ld_n_slowqi);
    if (!((LD_QI)(*(DWORD **)occ)[0])(occ, NULL, 0x41658d28, &p) || !p) return NULL;
    ((LD_REL)(*(DWORD **)p)[2])(p, NULL);
    d = (LONG)((BYTE *)p - occ);
    for (i = 0; i < 32; i++) {
        LdVt *c = &g_ld_vtc[i];
        if (!c->vt && InterlockedCompareExchange(&c->vt, (LONG)vt, 0) == 0) { c->delta = d; InterlockedExchange(&c->seen, 1); break; }
        if ((DWORD)c->vt == vt) {
            if (c->seen < 0) break;
            if (c->delta != d) { InterlockedExchange(&c->seen, -1000000); logf("lanedensity: vtable 0x%08lX: QI offsets differ (%ld, %ld), not cached", vt, c->delta, d); }
            else if (InterlockedIncrement(&c->seen) == 16) { InterlockedIncrement(&g_ld_nvt); ld_fast_add(vt, d); logf("lanedensity: vtable 0x%08lX -> piece at %+ld (cached)", vt, d); }
            break;
        }
    }
    return (BYTE *)p;
}

/* rows of piece (id, state) in the world frame, the half the router uses: bit 4*e + t = entry e -> exit t */
static DWORD ld_rows(BYTE *piece, DWORD id, DWORD state, DWORD half) {
    volatile LONG *slot = &g_ld_rows[half ? 1 : 0][id * 4 + state];
    LONG r = *slot;
    DWORD e, m = 0;
    if (r < 0) return (DWORD)r & 0xffff;
    for (e = 0; e < 4; e++) {
        BYTE o[4] = {0, 0, 0, 0};
        ((LD_CONN)(*(DWORD **)piece)[0x4c / 4])(piece, NULL, 0, half, e, &o[0], &o[1], &o[2], &o[3]);
        m |= (DWORD)((o[0] ? 1 : 0) | (o[1] ? 2 : 0) | (o[2] ? 4 : 0) | (o[3] ? 8 : 0)) << (4 * e);
    }
    InterlockedExchange(slot, (LONG)(0x80000000u | m));
    return m;
}

/* Evaluate a road node. Returns 0 = not constrained (allow all), else 0x100 | allowed exits (bits 0..3), with
   0x200 set when it was entered against the lanes. *pid gets the piece id (or 0). count != 0: evaluate any piece. */
static DWORD ld_eval(BYTE *layer, BYTE *node, DWORD *pid, int any) {
    BYTE t = node[0x14], prev = node[0x15];
    BYTE *piece;
    DWORD id, state, rows, allow;
    *pid = 0;
    if (g_ld_mode == 4) return 0;                                  /* task hwtrips: ramp-first only, no lane rules */
    if (t != 1 && t != 0x41) return 0;
    if (*(DWORD *)(node + 4) != *(DWORD *)(node + 0xc) || *(DWORD *)(node + 8) != *(DWORD *)(node + 0x10)) return 0;
    piece = ld_piece(*(BYTE **)node);
    if (!piece) return 0;
    id = *(DWORD *)(piece + 0x18) & 0xffff;
    *pid = id;
    if (!any && !(g_ld_mode == 2 || g_base[id])) return 0;
    InterlockedIncrement(&g_ld_n_eval);
    state = *(DWORD *)(piece + 0x14) >> 30;
    rows = ld_rows(piece, id, state, layer[0x54]);
    if (!rows) return 0;                                           /* no lane data: unconstrained */
    if (ld_is_net(prev)) {
        allow = (rows >> (4 * (node[0x1c] & 3))) & 0xf;
        if (!allow) return 0x300;
    } else
        allow = (rows | rows >> 4 | rows >> 8 | rows >> 12) & 0xf;
    return 0x100 | allow;
}

/* count mode: re-evaluate a node as if entered from a lot (union of the rows) */
static DWORD ld_eval_union(BYTE *layer, BYTE *node) {
    BYTE p = node[0x15];
    DWORD id, ev;
    node[0x15] = 0x80;
    ev = ld_eval(layer, node, &id, 1);
    node[0x15] = p;
    return ev;
}

static BYTE *ld_mark(BYTE *layer, DWORD x, DWORD z) {
    return *(BYTE **)(*(BYTE **)(*(BYTE **)(layer + 0x78) + 0xc) + x * 4) + z;
}
static WORD ld_flags(BYTE *layer, DWORD x, DWORD z) {
    return *(WORD *)(*(BYTE **)(*(BYTE **)(*(BYTE **)(layer + 0x5c) + 0xc) + x * 4) + z * 2);
}

static const int g_ld_dx[4] = {-1, 0, 1, 0}, g_ld_dz[4] = {0, -1, 0, 1};

/* Refused transitions of the trip being routed on this thread. A wrong-way entry into B from A fails and clears B's
   visited mark (so B stays reachable through a legal side); without this list the DFS retries A, which picks B
   again, for ever (measured: 6e8 refusals, the trip never ended). With it, every later scan from A in the same trip
   treats B as visited. Cleared when the trip's start node (type 0x80) is scanned: the DFS never re-pushes a cell it
   has visited, so A cannot come back after its stack frame is gone. Full list: B simply stays visited. */
#define LD_TRIPMAX 128     /* task avcore: 32 overflowed 26,224 times with one-way avenue halves (verify/avlanes M1) */
typedef struct { int n; DWORD from[LD_TRIPMAX], to[LD_TRIPMAX]; DWORD selfkey; } LdTrip;
static DWORD g_ld_tls = TLS_OUT_OF_INDEXES;
static volatile LONG g_ld_n_tripfull, g_ld_n_tripmark;

static LdTrip *ld_trip(int create) {
    LdTrip *t = (LdTrip *)TlsGetValue(g_ld_tls);
    if (!t && create) {
        t = (LdTrip *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(LdTrip));
        TlsSetValue(g_ld_tls, t);
    }
    return t;
}

#define LD_KEY(x, z) ((((x) & 0xffff) << 16) | ((z) & 0xffff))

/* give cell (x, z) the type bits t in the visited grid for this call, if it is a road cell not yet visited by t */
static void ld_close(BYTE *layer, DWORD x, DWORD z, BYTE t, BYTE **added, BYTE *addb, int *nadd) {
    BYTE *m;
    if (x >= *(DWORD *)(layer + 0x14) || z >= *(DWORD *)(layer + 0x18)) return;   /* unsigned: also catches -1 */
    if ((ld_flags(layer, x, z) & 0x11) != 0x01) return;
    m = ld_mark(layer, x, z);
    if ((*m & t) == t) return;
    added[*nadd] = m; addb[*nadd] = (BYTE)(t & ~*m); (*nadd)++;
    *m |= t;
}

#include "sc3netmod_rampfirst.c"   /* task hwtrips: road / bus steps take an offered on-ramp first (SC3NETMOD_RAMPFIRST) */
#include "sc3netmod_avflow.c"      /* task avflow: AVFIRST + AVDEPOSIT (SC3NETMOD_AVFIRST, SC3NETMOD_AVDEPOSIT) */

static BYTE __fastcall ld_select(BYTE *layer, void *edx, BYTE *node, BYTE *out, DWORD budget, DWORD p4, DWORD p5, DWORD p6) {
    DWORD id, ev, x, z, s;
    BYTE *added[16 + LD_TRIPMAX], addb[16 + LD_TRIPMAX], t = node[0x14], r;   /* task hwtrips: +6 for rf_close, task avflow: +5 avf_close */
    int nadd = 0, k, honoured, selfcopy = 0;
    LdCell *c = NULL;
    LdTrip *tr;
    (void)edx;
    if (t == 0x80) {                                               /* a trip (re)starts at its lot */
        if ((tr = ld_trip(0)) != NULL) {
            if (tr->n) InterlockedDecrement(&g_ld_ntact);
            tr->n = 0; tr->selfkey = 0;
        }
        if (g_avs_on) {                                            /* task bventry: AVSTART */
            AvsBuf *ab = avs_buf();
            int ns = 0;
            if (ab) avs_close(layer, node, ab->a, ab->b, &ns);
            r = ((LD_SEL)g_ld_tramp)(layer, NULL, node, out, budget, p4, p5, p6);
            for (k = 0; k < ns; k++) *ab->a[k] &= (BYTE)~ab->b[k];
            return r;
        }
        return ((LD_SEL)g_ld_tramp)(layer, NULL, node, out, budget, p4, p5, p6);
    }
    x = *(DWORD *)(node + 4); z = *(DWORD *)(node + 8);
    ev = ld_eval(layer, node, &id, g_ld_mode == 3);
    if (g_ld_mode == 3 && (ev & 0x200) && (tr = ld_trip(0)) != NULL && tr->selfkey == LD_KEY(x, z) + 1) {
        ev = ld_eval_union(layer, node);                           /* a self-step copy (count mode), not an entry */
        tr->selfkey = 0;
        selfcopy = 1;
    }
    tr = ld_is_net(t) ? ld_trip(0) : NULL;              /* highway nodes check the same visited grid (FUN_100086e7) */
    if (tr && tr->n) {                                             /* transitions refused earlier in this trip */
        DWORD key = LD_KEY(x, z);
        for (k = 0; k < tr->n; k++)
            if (tr->from[k] == key) {
                ld_close(layer, tr->to[k] >> 16, tr->to[k] & 0xffff, t, added, addb, &nadd);
                InterlockedIncrement(&g_ld_n_tripmark);
            }
    }
    if (!ev) rf_close(layer, node, added, addb, &nadd);            /* task hwtrips */
    if (!ev) avf_close(layer, node, added, addb, &nadd);           /* task avflow: after the ramp */
    if (!ev && !nadd) {
        r = ((LD_SEL)g_ld_tramp)(layer, NULL, node, out, budget, p4, p5, p6);
        avc_adjust(node, out, r);                                  /* task bventry */
        return r;
    }
    honoured = g_ld_mode != 3;
    if (ev && id < 65536 && g_base[id]) c = ld_cell(x, z, id);
    if (ev & 0x200) {                                              /* entered against the lanes */
        if (g_ld_mode == 3) InterlockedIncrement(&g_ld_c_wrong[id]);
        if (c) InterlockedIncrement(&c->wrong);
        if (honoured) {
            DWORD e = node[0x1c] & 3;
            for (k = 0; k < nadd; k++) *added[k] &= (BYTE)~addb[k];
            InterlockedIncrement(&g_ld_n_wrong);
            tr = ld_trip(1);
            if (tr && tr->n < LD_TRIPMAX) {
                tr->from[tr->n] = LD_KEY(x + g_ld_dx[e], z + g_ld_dz[e]);   /* the node we came from */
                tr->to[tr->n] = LD_KEY(x, z);
                if (tr->n++ == 0) InterlockedIncrement(&g_ld_ntact);
                *ld_mark(layer, x, z) &= (BYTE)~node[0x15];         /* set by the step that chose this node */
            } else
                InterlockedIncrement(&g_ld_n_tripfull);
            *(DWORD *)out = 0;
            node[0x1d] = 0;
            out[0x1d] = 0;
            return 0;
        }
    } else if (ev && honoured) {
        int before = nadd;
        InterlockedIncrement(&g_ld_n_hon);
        for (s = 0; s < 4; s++)
            if (!(ev & (1u << s))) ld_close(layer, x + g_ld_dx[s], z + g_ld_dz[s], t, added, addb, &nadd);
        /* A node entered from a lot has its own cell marked with the lot's bits (0x80), not its own type, so the ring
           scan (which includes the centre) can step from the cell to itself; the copy then claims entry side x+
           (the else branch at SimTransit 0x100083e4 sets 2 for a same rect) and would read as a wrong-way entry. Close the centre. */
        ld_close(layer, x, z, t, added, addb, &nadd);
        if (nadd > before) InterlockedExchangeAdd(&g_ld_n_premark, nadd - before);
        rf_close(layer, node, added, addb, &nadd);                 /* task hwtrips: after the lane closes */
        avf_close(layer, node, added, addb, &nadd);                /* task avflow: after the ramp */
    }
    r = ((LD_SEL)g_ld_tramp)(layer, NULL, node, out, budget, p4, p5, p6);
    for (k = 0; k < nadd; k++) *added[k] &= (BYTE)~addb[k];
    avc_adjust(node, out, r);                                      /* task bventry */
    if (g_ld_mode == 3 && r && *(DWORD *)(out + 4) == x && *(DWORD *)(out + 8) == z && (tr = ld_trip(1)) != NULL)
        tr->selfkey = LD_KEY(x, z) + 1;
    if (ev && r && (out[0x14] == 1 || out[0x14] == 3 || out[0x14] == 0x41) &&
        (*(DWORD *)(out + 4) != x || *(DWORD *)(out + 8) != z)) {            /* not a step onto its own cell */
        DWORD exitside = (out[0x1c] + 2) & 3, entry = (ld_is_net(node[0x15]) && !selfcopy) ? (node[0x1c] & 3) : 4;
        if (c) InterlockedIncrement(&c->step[entry][exitside]);
        if (honoured && !(ev & 0x200) && !(ev & (1u << exitside))) {
            static volatile LONG nlog;
            if (InterlockedIncrement(&nlog) <= 20)
                logf("lanedensity: ### step through a closed side: node t=%02x prev=%02x entry=%u rect=(%lu,%lu)-(%lu,%lu) ev=%03lx nadd=%d -> out t=%02x entry=%u rect=(%lu,%lu)-(%lu,%lu) flags=%04x mark=%02x",
                     t, node[0x15], node[0x1c], x, z, *(DWORD *)(node + 0xc), *(DWORD *)(node + 0x10), ev, nadd,
                     out[0x14], out[0x1c], *(DWORD *)(out + 4), *(DWORD *)(out + 8), *(DWORD *)(out + 0xc), *(DWORD *)(out + 0x10),
                     ld_flags(layer, *(DWORD *)(out + 4), *(DWORD *)(out + 8)), *ld_mark(layer, *(DWORD *)(out + 4), *(DWORD *)(out + 8)));
        }
        if (g_ld_mode == 3 && id < 65536) {
            InterlockedIncrement(&g_ld_c_steps[id]);
            if (!(ev & (1u << exitside)) && !(ev & 0x200)) InterlockedIncrement(&g_ld_c_forbid[id]);
        }
    }
    return r;
}

/* Entry of FUN_1000755e. Passes the call to the game (trampoline) unless the node is a road / bus node on an
   honoured piece, or some thread holds refused transitions, or count mode: then the C path ld_select. Uses only
   eax / edx; ecx (the layer) and the stack are untouched, so both targets see the game's own call. */
static __declspec(naked) void ld_stub(void) {
    __asm {
        cmp  g_ld_force, 0
        jne  slow
        cmp  g_ld_ntact, 0
        jne  slow
        mov  eax, [esp + 4]
        mov  dl, byte ptr [eax + 0x14]
        cmp  dl, 1
        je   road
        cmp  dl, 0x41
        je   road
        cmp  dl, 0x80            /* task bventry: AVSTART looks at trip starts */
        jne  pass
        cmp  g_avs_on, 0
        jne  slow
        jmp  dword ptr [g_ld_tramp]
    road:
        cmp  g_rf_on, 0          /* task hwtrips: ramp-first looks at every road / bus step */
        jne  slow
        cmp  g_avf_on, 0         /* task avflow: avenue-first too */
        jne  slow
        cmp  g_avc_on, 0         /* task bventry: BVCOST adjusts the step after the call */
        jne  slow
        cmp  g_avc_av_on, 0
        jne  slow
        mov  eax, [eax]
        test eax, eax
        jz   pass
        mov  edx, [eax]
        cmp  edx, dword ptr [g_ld_fvt]
        je   v0
        cmp  edx, dword ptr [g_ld_fvt + 4]
        je   v1
        cmp  edx, dword ptr [g_ld_fvt + 8]
        je   v2
        cmp  edx, dword ptr [g_ld_fvt + 12]
        je   v3
        cmp  edx, dword ptr [g_ld_fvt + 16]
        je   v4
        cmp  edx, dword ptr [g_ld_fvt + 20]
        je   v5
        cmp  edx, dword ptr [g_ld_fvt + 24]
        je   v6
        cmp  edx, dword ptr [g_ld_fvt + 28]
        je   v7
        jmp  slow
    v0: add  eax, dword ptr [g_ld_fdl]
        jmp  got
    v1: add  eax, dword ptr [g_ld_fdl + 4]
        jmp  got
    v2: add  eax, dword ptr [g_ld_fdl + 8]
        jmp  got
    v3: add  eax, dword ptr [g_ld_fdl + 12]
        jmp  got
    v4: add  eax, dword ptr [g_ld_fdl + 16]
        jmp  got
    v5: add  eax, dword ptr [g_ld_fdl + 20]
        jmp  got
    v6: add  eax, dword ptr [g_ld_fdl + 24]
        jmp  got
    v7: add  eax, dword ptr [g_ld_fdl + 28]
    got:
        movzx eax, word ptr [eax + 0x18]
        cmp  byte ptr [g_ld_hon + eax], 0
        jne  slow
    pass:
        jmp  dword ptr [g_ld_tramp]
    slow:
        jmp  ld_select
    }
}

static DWORD __fastcall ld_arrive(BYTE *layer, void *edx, BYTE *node, DWORD kind) {
    DWORD r = ((LD_ARR)g_ld_arrive_orig)(layer, NULL, node, kind), id, ev;
    (void)edx;
    if (!(r & 0xff) || g_ld_mode == 3) return r;
    ev = ld_eval(layer, node, &id, 0);
    if (ev & 0x200) {
        LdCell *c = (id < 65536 && g_base[id]) ? ld_cell(*(DWORD *)(node + 4), *(DWORD *)(node + 8), id) : NULL;
        InterlockedIncrement(&g_ld_n_arrblock);
        if (c) InterlockedIncrement(&c->arrblock);
        return r & 0xffffff00;
    }
    return r;
}

static const BYTE g_ld_entry[6] = {0x55, 0x8b, 0xec, 0x83, 0xec, 0x68};   /* push ebp; mov ebp,esp; sub esp,0x68 */

static void lanedensity_install(void) {
    char v[16];
    BYTE *st, *e, jmp[6];
    DWORD got = GetEnvironmentVariableA("SC3NETMOD_LANEDENSITY", v, sizeof(v));
    int ms = 0;
    g_ld_mode = 1;
    if (got && v[0] == '0') g_ld_mode = 0;
    else if (got && !lstrcmpiA(v, "all")) g_ld_mode = 2;
    else if (got && !lstrcmpiA(v, "count")) g_ld_mode = 3;
    rf_init();                                                     /* task hwtrips */
    avf_init();                                                    /* task avflow */
    if ((g_rf_on || g_avf_on || g_avc_on || g_avc_av_on || g_avs_on) && (!g_ld_mode || (g_ld_mode == 1 && !g_nvariants))) g_ld_mode = 4;   /* task hwtrips: ramp-first only */
    if (!g_ld_mode) { logf("lanedensity: off (SC3NETMOD_LANEDENSITY=0)"); return; }
    if (g_ld_mode == 1 && !g_nvariants) { logf("lanedensity: no variants, nothing to honour - not patched"); g_ld_mode = 0; return; }
    while (!(st = (BYTE *)GetModuleHandleA("SimTransit.dll")) && ms++ < 300000) Sleep(1);
    if (!st) { logf("lanedensity: SimTransit.dll never loaded"); g_ld_mode = 0; return; }
    avd_install(st);                                               /* task avflow: its own call site, any ld mode */
    e = st + 0x755e;
    if (!bytes_are(e, g_ld_entry, 6) || st[0x71eb] != 0xE8 || (DWORD)(st + 0x71f0) + *(DWORD *)(st + 0x71ec) != (DWORD)st + 0x8a94) {
        logf("lanedensity: SimTransit+0x755e / +0x71eb differ from shipped - not patched");
        g_ld_mode = 0;
        return;
    }
    g_ld_tls = TlsAlloc();
    if (g_ld_tls == TLS_OUT_OF_INDEXES) { logf("lanedensity: no TLS slot"); g_ld_mode = 0; return; }
    g_ld_cells = (LdCell *)VirtualAlloc(NULL, sizeof(LdCell) * LD_NCELL, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (g_ld_mode == 3) {
        g_ld_c_steps = (volatile LONG *)VirtualAlloc(NULL, 3 * 65536 * sizeof(LONG), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g_ld_c_steps) { logf("lanedensity: no memory"); g_ld_mode = 0; return; }
        g_ld_c_forbid = g_ld_c_steps + 65536;
        g_ld_c_wrong = g_ld_c_steps + 2 * 65536;
    }
    g_ld_tramp = (BYTE *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_ld_tramp) { logf("lanedensity: no memory"); g_ld_mode = 0; return; }
    memcpy(g_ld_tramp, g_ld_entry, 6);
    g_ld_tramp[6] = 0xE9;
    *(DWORD *)(g_ld_tramp + 7) = (DWORD)(e + 6) - (DWORD)(g_ld_tramp + 11);
    FlushInstructionCache(GetCurrentProcess(), g_ld_tramp, 16);
    {   DWORD i;
        for (i = 0; i < 65536; i++) g_ld_hon[i] = (BYTE)(g_ld_mode == 2 || (g_ld_mode != 4 && g_base[i]));   /* task hwtrips: != 4 */
        g_ld_force = g_ld_mode == 3;
    }
    g_ld_st = (DWORD)st;
    g_ld_arrive_orig = g_ld_st + 0x8a94;
    if (g_ld_mode != 3 && !retarget_call(st, 0x71eb, 0x8a94, (void *)ld_arrive)) {
        logf("lanedensity: arrival call not patched");
        g_ld_mode = 0;
        return;
    }
    jmp[0] = 0xE9;
    *(DWORD *)(jmp + 1) = (DWORD)ld_stub - (DWORD)(e + 5);
    jmp[5] = 0x90;
    memcpy(g_ld_jmp_e, jmp, 6);                                    /* ALT: the two patched sites, both ways */
    memcpy(g_ld_call_a, st + 0x71eb, 5);
    g_ld_orig_a[0] = 0xE8;
    *(DWORD *)(g_ld_orig_a + 1) = (st + 0x8a94) - (st + 0x71f0);
    if (!write_code(e, jmp, 6)) { logf("lanedensity: entry not patched"); g_ld_mode = 0; return; }
    logf("lanedensity: ON, mode %s (SimTransit at 0x%08lX: step 0x1000755e, arrival call 0x100071eb)",
         g_ld_mode == 1 ? "variants" : g_ld_mode == 2 ? "all pieces" : g_ld_mode == 4 ? "ramp-first only (no lane rules)" /* task hwtrips */
         : "count only (nothing filtered)", (DWORD)st);
}

/* ALT (perf measurement, verify/lanedensity PRE addendum 7): sc3netmod_ld_set(0) puts both patch sites back to the
   shipped bytes, sc3netmod_ld_set(1) re-installs the detours, so one game can alternate stock and patched routing.
   Every other thread of the process is suspended while the bytes change, and the write is retried until none of them
   sits inside the bytes being written or the trampoline. Nothing that takes a lock runs while they are suspended.
   Returns the previous state, or -1 when the block is not installed. */

static int ld_in(DWORD ip, DWORD at, DWORD n) { return ip >= at && ip < at + n; }

__declspec(dllexport) int __cdecl sc3netmod_ld_set(int on) {
    BYTE *e = (BYTE *)g_ld_st + 0x755e, *a = (BYTE *)g_ld_st + 0x71eb;
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId(), olde, olda;
    HANDLE snap;
    THREADENTRY32 te;
    int n = 0, k, tries, prev, busy;
    on = on ? 1 : 0;
    if (!g_ld_st || !g_ld_tramp || (g_ld_mode != 1 && g_ld_mode != 2)) return -1;
    if (InterlockedCompareExchange(&g_ld_alt_busy, 1, 0)) return -1;
    prev = g_ld_on;
    if (prev == on) { g_ld_alt_busy = 0; return prev; }
    snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    te.dwSize = sizeof(te);
    if (snap != INVALID_HANDLE_VALUE && Thread32First(snap, &te)) do {
        if (te.th32OwnerProcessID == pid && te.th32ThreadID != me && n < LD_MAXTH) {
            HANDLE h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID);
            if (h) g_ld_th[n++] = h;
        }
        te.dwSize = sizeof(te);
    } while (Thread32Next(snap, &te));
    if (snap != INVALID_HANDLE_VALUE) CloseHandle(snap);
    VirtualProtect(e, 6, PAGE_EXECUTE_READWRITE, &olde);
    VirtualProtect(a, 5, PAGE_EXECUTE_READWRITE, &olda);
    for (tries = 0; tries < 200; tries++) {
        busy = 0;
        for (k = 0; k < n; k++) SuspendThread(g_ld_th[k]);
        for (k = 0; k < n && !busy; k++) {
            CONTEXT c;
            c.ContextFlags = CONTEXT_CONTROL;
            if (GetThreadContext(g_ld_th[k], &c) &&
                (ld_in(c.Eip, (DWORD)e, 6) || ld_in(c.Eip, (DWORD)a, 5) || ld_in(c.Eip, (DWORD)g_ld_tramp, 11)))
                busy = 1;
        }
        if (!busy) {
            if (on) { memcpy(e, g_ld_jmp_e, 6); memcpy(a, g_ld_call_a, 5); }
            else    { memcpy(e, g_ld_entry, 6); memcpy(a, g_ld_orig_a, 5); }
            FlushInstructionCache(GetCurrentProcess(), e, 6);
            FlushInstructionCache(GetCurrentProcess(), a, 5);
            g_ld_on = on;
        }
        for (k = 0; k < n; k++) ResumeThread(g_ld_th[k]);
        if (!busy) break;
        InterlockedIncrement(&g_ld_n_toggle_retry);
        Sleep(1);
    }
    VirtualProtect(e, 6, olde, &olde);
    VirtualProtect(a, 5, olda, &olda);
    for (k = 0; k < n; k++) CloseHandle(g_ld_th[k]);
    if (g_ld_on == on) InterlockedIncrement(&g_ld_n_toggle);
    logf("lanedensity: ALT %s (%d thread(s) suspended, %d retr%s)%s", on ? "ON" : "OFF (shipped bytes)", n, tries,
         tries == 1 ? "y" : "ies", g_ld_on == on ? "" : " - NOT switched");
    g_ld_alt_busy = 0;
    return prev;
}

static void lanedensity_stats(void) {
    int i, j, n = 0;
    if (!g_ld_mode) return;
    rampfirst_stats();                                             /* task hwtrips */
    avflow_stats();                                                /* task avflow */
    if (g_ld_n_toggle) logf("lanedensity: ALT state %s, %ld switch(es), %ld retr(ies)", g_ld_on ? "ON" : "OFF", g_ld_n_toggle, g_ld_n_toggle_retry);
    logf("lanedensity: evals=%ld honoured steps=%ld neighbours closed=%ld wrong-way fails=%ld arrivals refused=%ld slow QI=%ld vtables=%ld refused-transition closes=%ld trip list full=%ld",
         g_ld_n_eval, g_ld_n_hon, g_ld_n_premark, g_ld_n_wrong, g_ld_n_arrblock, g_ld_n_slowqi, g_ld_nvt, g_ld_n_tripmark, g_ld_n_tripfull);
    if (g_ld_cells)
        for (i = 0; i < LD_NCELL; i++) {
            LdCell *c = &g_ld_cells[i];
            char buf[400];
            int p = 0;
            if (!c->key) continue;
            for (j = 0; j < 20; j++) p += _snprintf(buf + p, sizeof(buf) - p, "%s%ld", j ? "," : "", c->step[j / 4][j % 4]);
            logf("lanedensity: cell (%ld,%ld) id %lu wrong=%ld arrblock=%ld steps[entry x-,z-,x+,z+,start][exit]=%s",
                 (c->key >> 16) & 0x3fff, c->key & 0xffff, c->id, c->wrong, c->arrblock, buf);
            if (++n >= 64) break;
        }
    if (g_ld_mode == 3) {
        LONG tot = 0, forb = 0, wr = 0;
        for (i = 0; i < 65536; i++) { tot += g_ld_c_steps[i]; forb += g_ld_c_forbid[i]; wr += g_ld_c_wrong[i]; }
        logf("lanedensity: count: road steps on pieces with lane data=%ld, forbidden by their matrix=%ld, entered against it=%ld",
             tot, forb, wr);
        for (i = 0; i < 65536; i++)
            if (g_ld_c_forbid[i] || g_ld_c_wrong[i])
                logf("lanedensity: count: id %d steps=%ld forbidden=%ld against=%ld", i, g_ld_c_steps[i], g_ld_c_forbid[i], g_ld_c_wrong[i]);
    }
}

/* own thread: SimTransit may map after SIMNTWRK, and the other blocks must not wait for it */
static DWORD WINAPI lanedensity_thread(LPVOID param) {
    (void)param;
    lanedensity_install();
    while (g_ld_mode) { Sleep(10000); lanedensity_stats(); }
    return 0;
}
