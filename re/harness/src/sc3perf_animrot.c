/* ---------------------------------------------------------------- ANIMROT (child animrot, round 2026-11-27)
   Player report (Simtropolis, 2026-11-26): a rotated Spaceport or Science Center (sc3resize ROTPLACE, or any save with
   occupant rotation 1-3) turns, except "the portion of the image that contains the animations": rectangles of another
   view's art, and of empty sky, sit on the turned building. Evidence: verify/animrot/RESULTS.md,
   re/analysis/BUILDING_ROTATION.md section 7.

   Cause [CONFIRMED, SIMSPR static + live]. Buildings with extra image layers use the sprite class
   cSC3CitySpriteInstAnim (vtable 0x10062a5c, second vtable 0x10062a44 at +0xc; Linux names). Its base frame comes from
   the shared frame getter (slot 0x68, 0x1005aeab) = ((state + rot) & 3) + zoom * 4, state = +4 bits 30-31 = the
   occupant's rotation, so the base art turns. Every per-rotation layer table is indexed with the RAW (zoom, rot) the
   caller passes: the attribute's RegRect vectors attrib + 0xc / 0x48 / 0x84 + zoom * 0x30 + rot * 0xc (no anim machine,
   +0x10 == 0) and the machine's vectors machine + 0x3c0 / 0x5a0 / 0x690 + zoom * 0x30 + rot * 0xc (frames, x, y). So
   the layers come from slot `view` while the base comes from slot `view + state`. The methods doing that (Windows
   slot, body, stack args):
     0x0c 0x100141c7 GetW(zoom, rot)                     0x30 0x10014546 IsPixelOpaque(x, y, zoom, rot)
     0x10 0x100143f0 GetH(zoom, rot)                     0x34 0x10014695 Prepare(zoom, rot, bool) (masks +0x14/+0x18
     0x14 0x10014444 GetAllSpans(zoom, rot, rect)                        bit rot + zoom * 4, keyed on the raw rot)
     0x18 0x1001421b GetAreaFromPt(zoom, rot, rect, x, y) 0x38 0x100148da Unprepare(zoom, rot)
     0x3c 0x10014c28 Draw(buf, rect, zoom, rot, clip)    0x40 0x10014a10 Draw(buf, x, y, zoom, rot, clip)
     0x44 0x10014df9 Tick(dt): runs the machine's script for its own [+0x780 zoom][+0x784 rot]; when +0x780 is out of
          0..4 it seeds both from the cell map (SL::CSCM 0x1005a952, GetZoom vt+0x34, GetRotate vt+0x44 = raw view) and
          calls ViewChange 0x100155bf(zoom, rot), which also spawns the child sprites listed at machine + 0x1e0.
   Each body is reached only through this vtable (one .rdata reference each, no direct call in SIMSPR).

   Fix: the ten slots are replaced by wrappers. For a sprite with state s != 0 and rot 0..3 a wrapper calls the original
   with rot' = (rot + s) & 3, so every table index, the prepared masks, the hit test and the bounds use slot rot'. To
   keep the base frame from turning twice, the wrapper marks the sprite in a TLS slot while the original runs, and the
   getter slot 0x68 of THIS vtable (the other 13 users of 0x1005aeab keep the shipped getter) returns (rot & 3) +
   zoom * 4 for the marked sprite, i.e. the shipped ((s + raw) & 3) + zoom * 4. A wrapper turns the argument also when
   the sprite is already marked (callers outside SIMSPR's class bodies pass the raw view, see AR_GO), except Tick's own
   GetAllSpans call, whose argument is the machine's already turned slot. Tick: same mark, and when the machine's
   +0x780 is out of 0..4 the wrapper seeds +0x780 = GetZoom, +0x784 = (GetRotate + s) & 3 and calls ViewChange with them
   (the shipped seeding with rot'), so the script runs for the slot the draw reads. Machines are made by the game for
   powered buildings in view at zoom 2+ (SIMGEOM sc3_geom_reconcile_visible_set 0x1000f630 -> cISC3Occupant::AnimStart
   -> StartAnimation) and rebuilt on every camera turn or zoom change (AnimStop then AnimStart), so they re-seed.
   Child sprites (power plant smoke): see ar_setmachine / ar_start below.
   Threads: the mark is per thread (draw, hit test and tick each mark on the thread they run on), set and cleared
   around one call in __try/__finally. State 0 (every unrotated building, every stock growable with rotation 0) takes
   the shipped call with no TLS access. animrot=0 (SC3PERF_ANIMROT=0) keeps the shipped vtable. */
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)
static int g_animrot = 1;
static DWORD g_ar_tls = TLS_OUT_OF_INDEXES;
static DWORD g_ar_vt;                       /* SIMSPR 0x10062a5c */
static DWORD g_ar_o[0x6c / 4];              /* shipped slot targets, by slot index */
static DWORD g_ar_cscm, g_ar_viewchange;    /* 0x1005a952, 0x100155bf */
static volatile LONG g_ar_n, g_ar_seed;

#define AR_STATE(self) (*(volatile DWORD *)((BYTE *)(self) + 4) >> 30)

/* mark self on this thread; returns the previous mark (keeps GetLastError: TlsGetValue / TlsSetValue clear it) */
static void *ar_enter(void *self) {
    DWORD e = GetLastError();
    void *prev = TlsGetValue(g_ar_tls);
    TlsSetValue(g_ar_tls, self);
    SetLastError(e);
    return prev;
}
static void ar_leave(void *prev) {
    DWORD e = GetLastError();
    TlsSetValue(g_ar_tls, prev);
    SetLastError(e);
}
static int ar_marked(void *self) {
    DWORD e = GetLastError();
    int r = TlsGetValue(g_ar_tls) == self;
    SetLastError(e);
    return r;
}
static void ar_count(void *self, DWORD s) {
    LONG n = InterlockedIncrement(&g_ar_n);
    if (n == 1 || n == 1000 || n == 100000)
        logf("ANIMROT> #%ld: animated sprite 0x%08lX with rotation %lu draws its layers from slot view + %lu", n, (DWORD)self, s, s);
}

typedef DWORD (__fastcall *AR_F1)(void *, void *, DWORD);
typedef DWORD (__fastcall *AR_F2)(void *, void *, DWORD, DWORD);
typedef DWORD (__fastcall *AR_F3)(void *, void *, DWORD, DWORD, DWORD);
typedef DWORD (__fastcall *AR_F4)(void *, void *, DWORD, DWORD, DWORD, DWORD);
typedef DWORD (__fastcall *AR_F5)(void *, void *, DWORD, DWORD, DWORD, DWORD, DWORD);
typedef DWORD (__fastcall *AR_F6)(void *, void *, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD);

/* The rotation argument is the caller's view slot for every caller but one, so it is turned whenever s != 0 and it is
   0..3, also when the sprite is already marked: inside a child's Tick the sprite manager's ChangeUnalignedSpriteInst ->
   0x1000e4ce calls GetAllSpans with the cell map's raw view (+0x2c), measured (a pass-through there read an unprepared
   slot: NULL at SIMSPR+0x14478). The one exception is Tick's own call vt+0x14(machine +0x780, machine +0x784) at
   0x10014f56 (returns to 0x10014f59): +0x784 is already the turned slot, so ar_spans passes it on unchanged. */
#define AR_ADJ(rot, s) (((rot) + (s)) & 3)
#define AR_GO(self, s, rot) ((s) && (rot) <= 3)
static DWORD g_ar_tickcall;   /* SIMSPR 0x10014f59 */

/* slots with (zoom, rot) first: 0x0c GetW, 0x10 GetH, 0x38 Unprepare */
#define AR_W2(name, slot) \
static DWORD __fastcall name(void *self, void *edx, DWORD zoom, DWORD rot) { \
    DWORD s = AR_STATE(self), r; void *prev; \
    if (!AR_GO(self, s, rot)) return ((AR_F2)g_ar_o[(slot) / 4])(self, edx, zoom, rot); \
    prev = ar_enter(self); ar_count(self, s); \
    __try { r = ((AR_F2)g_ar_o[(slot) / 4])(self, edx, zoom, AR_ADJ(rot, s)); } __finally { ar_leave(prev); } \
    return r; }
AR_W2(ar_getw, 0x0c)
AR_W2(ar_geth, 0x10)
AR_W2(ar_unprepare, 0x38)

/* 0x14 GetAllSpans(zoom, rot, rect), 0x34 Prepare(zoom, rot, bool) */
#define AR_W3(name, slot) \
static DWORD __fastcall name(void *self, void *edx, DWORD zoom, DWORD rot, DWORD a3) { \
    DWORD s = AR_STATE(self), r; void *prev; \
    if (!AR_GO(self, s, rot)) return ((AR_F3)g_ar_o[(slot) / 4])(self, edx, zoom, rot, a3); \
    prev = ar_enter(self); ar_count(self, s); \
    __try { r = ((AR_F3)g_ar_o[(slot) / 4])(self, edx, zoom, AR_ADJ(rot, s), a3); } __finally { ar_leave(prev); } \
    return r; }
AR_W3(ar_prepare, 0x34)
static DWORD __fastcall ar_spans(void *self, void *edx, DWORD zoom, DWORD rot, DWORD rc) {   /* 0x14 GetAllSpans */
    DWORD s = AR_STATE(self), r; void *prev;
    if (!AR_GO(self, s, rot) || (DWORD)_ReturnAddress() == g_ar_tickcall) return ((AR_F3)g_ar_o[0x14 / 4])(self, edx, zoom, rot, rc);
    prev = ar_enter(self); ar_count(self, s);
    __try { r = ((AR_F3)g_ar_o[0x14 / 4])(self, edx, zoom, AR_ADJ(rot, s), rc); } __finally { ar_leave(prev); }
    return r;
}

/* 0x18 GetAreaFromPt(zoom, rot, rect, x, y) */
static DWORD __fastcall ar_area(void *self, void *edx, DWORD zoom, DWORD rot, DWORD rc, DWORD x, DWORD y) {
    DWORD s = AR_STATE(self), r; void *prev;
    if (!AR_GO(self, s, rot)) return ((AR_F5)g_ar_o[0x18 / 4])(self, edx, zoom, rot, rc, x, y);
    prev = ar_enter(self); ar_count(self, s);
    __try { r = ((AR_F5)g_ar_o[0x18 / 4])(self, edx, zoom, AR_ADJ(rot, s), rc, x, y); } __finally { ar_leave(prev); }
    return r;
}
/* 0x30 IsPixelOpaque(x, y, zoom, rot) */
static DWORD __fastcall ar_opaque(void *self, void *edx, DWORD x, DWORD y, DWORD zoom, DWORD rot) {
    DWORD s = AR_STATE(self), r; void *prev;
    if (!AR_GO(self, s, rot)) return ((AR_F4)g_ar_o[0x30 / 4])(self, edx, x, y, zoom, rot);
    prev = ar_enter(self); ar_count(self, s);
    __try { r = ((AR_F4)g_ar_o[0x30 / 4])(self, edx, x, y, zoom, AR_ADJ(rot, s)); } __finally { ar_leave(prev); }
    return r;
}
/* 0x3c Draw(buf, rect, zoom, rot, clip) */
static DWORD __fastcall ar_draw_rc(void *self, void *edx, DWORD buf, DWORD rc, DWORD zoom, DWORD rot, DWORD clip) {
    DWORD s = AR_STATE(self), r; void *prev;
    if (!AR_GO(self, s, rot)) return ((AR_F5)g_ar_o[0x3c / 4])(self, edx, buf, rc, zoom, rot, clip);
    prev = ar_enter(self); ar_count(self, s);
    __try { r = ((AR_F5)g_ar_o[0x3c / 4])(self, edx, buf, rc, zoom, AR_ADJ(rot, s), clip); } __finally { ar_leave(prev); }
    return r;
}
/* 0x40 Draw(buf, x, y, zoom, rot, clip) */
static DWORD __fastcall ar_draw_xy(void *self, void *edx, DWORD buf, DWORD x, DWORD y, DWORD zoom, DWORD rot, DWORD clip) {
    DWORD s = AR_STATE(self), r; void *prev;
    if (!AR_GO(self, s, rot)) return ((AR_F6)g_ar_o[0x40 / 4])(self, edx, buf, x, y, zoom, rot, clip);
    prev = ar_enter(self); ar_count(self, s);
    __try { r = ((AR_F6)g_ar_o[0x40 / 4])(self, edx, buf, x, y, zoom, AR_ADJ(rot, s), clip); } __finally { ar_leave(prev); }
    return r;
}
/* 0x68 frame getter of this class: the marked sprite already got rot' = (raw + s) & 3, so do not add s again */
static DWORD __fastcall ar_frame(void *self, void *edx, DWORD zoom, DWORD rot) {
    if (AR_STATE(self) && ar_marked(self)) return (rot & 3) + zoom * 4;
    return ((AR_F2)g_ar_o[0x68 / 4])(self, edx, zoom, rot);
}

/* 0x44 Tick(dt) */
typedef BYTE *(__cdecl *AR_CSCM)(void);
typedef int (__fastcall *AR_GETI)(void *, void *);
static void ar_seed(BYTE *self, BYTE *m, DWORD s) {
    BYTE *cm = ((AR_CSCM)g_ar_cscm)();
    int zoom, rot, rr;
    if (!cm) return;   /* the shipped Tick then calls through the NULL cell map, as before */
    zoom = ((AR_GETI)(*(DWORD **)cm)[0x34 / 4])(cm, NULL);
    *(int *)(m + 0x780) = zoom;
    rot = ((AR_GETI)(*(DWORD **)cm)[0x44 / 4])(cm, NULL);
    rr = (rot >= 0 && rot <= 3) ? (int)AR_ADJ((DWORD)rot, s) : rot;
    *(int *)(m + 0x784) = rr;
    ((AR_F2)g_ar_viewchange)(self, NULL, (DWORD)zoom, (DWORD)rr);
    if (InterlockedIncrement(&g_ar_seed) <= 5)
        logf("ANIMROT> anim machine of sprite 0x%08lX (rotation %lu) starts at zoom %d slot %d (view %d)", (DWORD)self, s,
             zoom, rr, rot);
}
static DWORD __fastcall ar_tick(void *self, void *edx, DWORD dt) {
    DWORD s = AR_STATE(self), r;
    BYTE *m = *(BYTE **)((BYTE *)self + 0x10);
    void *prev;
    if (!s || !m || ar_marked(self)) return ((AR_F1)g_ar_o[0x44 / 4])(self, edx, dt);
    prev = ar_enter(self);
    __try {
        int z = *(int *)(m + 0x780);
        if (z < 0 || z >= 5) ar_seed((BYTE *)self, m, s);
        r = ((AR_F1)g_ar_o[0x44 / 4])(self, edx, dt);
    } __finally { ar_leave(prev); }
    return r;
}

/* Child sprites (ViewChange 0x100155bf: smoke of a power plant, 4 per slot). (a) Their machine gets the parent's slot
   +0x784 = rr, and the sprite manager prepares them at insertion (vt+0x84, after SetLocation) for the view it passes:
   a child with state 0 is prepared for slot `view` and its Tick then reads slot rr, never prepared (empty frame vector,
   NULL read at SIMSPR+0x14478, measured with a TAB-rotated coal plant). So the child takes the parent's state before
   it is inserted: ViewChange's only call to SetAnimMachine 0x10014083 (0x10015758, ecx = child) goes through
   ar_setmachine, which copies the state of the sprite marked on this thread (the parent, inside ar_tick) to the child.
   (b) Their world offsets (entry + 8 / + 0xc, added to machine +0x788 / +0x78c, the lot's minimum corner) are the same
   world positions in every slot: the chimneys of the unturned plant. StartAnimation (second vtable +0xc, 0x1001531f,
   (x, y, z, size) with size = the occupant's SizeInCellsX from its AnimStart) builds a new machine whose child entries
   are its own copies (factory 0x10003f2b, operator new per entry), so ar_start turns each entry's x / z once, by the
   state, about the lot centre (size * 128), before any ViewChange uses them. */
typedef DWORD (__fastcall *AR_F4S)(void *, void *, DWORD, DWORD, DWORD, DWORD);
static DWORD g_ar_start, g_ar_setmachine;
static volatile LONG g_ar_turned;
static DWORD __fastcall ar_setmachine(void *child, void *edx, DWORD machine) {
    void *parent;
    DWORD s, e = GetLastError();
    parent = TlsGetValue(g_ar_tls);
    SetLastError(e);
    if (parent && child && *(DWORD *)parent == g_ar_vt && (s = AR_STATE(parent)) != 0 && *(DWORD *)child == g_ar_vt) {
        volatile DWORD *w = (volatile DWORD *)((BYTE *)child + 4);
        *w = (*w & 0x3fffffff) | (s << 30);
    }
    return ((AR_F1)g_ar_setmachine)(child, edx, machine);
}
static void ar_turn(int *x, int *z, DWORD s, int span) {   /* one quarter turn per state step, about the lot centre */
    while (s--) { int t = *x; *x = span - *z; *z = t; }
}
static DWORD __fastcall ar_start(void *self2, void *edx, DWORD x, DWORD y, DWORD z, DWORD size) {
    BYTE *inst = (BYTE *)self2 - 0xc, *m, *had = *(BYTE **)(inst + 0x10);   /* the shipped body keeps an existing machine */
    DWORD r = ((AR_F4S)g_ar_start)(self2, edx, x, y, z, size);
    DWORD s = AR_STATE(inst);
    int zz, q, n = 0, span = (int)(size & 0xff) * 256;
    if (!s || had || span <= 0 || span > 16 * 256 || !(m = *(BYTE **)(inst + 0x10))) return r;   /* turn new machines only */
    for (zz = 0; zz < 5; zz++)
        for (q = 0; q < 4; q++) {
            BYTE **b = (BYTE **)*(BYTE **)(m + 0x1e0 + zz * 0x30 + q * 0xc), **e = (BYTE **)*(BYTE **)(m + 0x1e4 + zz * 0x30 + q * 0xc);
            for (; b && b < e; b++)
                if (*b) { ar_turn((int *)(*b + 8), (int *)(*b + 0xc), s, span); n++; }
        }
    if (n && InterlockedIncrement(&g_ar_turned) <= 5)
        logf("ANIMROT> anim machine of sprite 0x%08lX (rotation %lu, lot %lu cells): %d child offsets turned", (DWORD)inst, s,
             size & 0xff, n);
    return r;
}

static void patch_animrot(DWORD spr) {
    static const struct { DWORD slot, rva; void *fn; } k[] = {
        {0x0c, 0x141c7, (void *)ar_getw},  {0x10, 0x143f0, (void *)ar_geth},    {0x14, 0x14444, (void *)ar_spans},
        {0x18, 0x1421b, (void *)ar_area},  {0x30, 0x14546, (void *)ar_opaque},  {0x34, 0x14695, (void *)ar_prepare},
        {0x38, 0x148da, (void *)ar_unprepare}, {0x3c, 0x14c28, (void *)ar_draw_rc}, {0x40, 0x14a10, (void *)ar_draw_xy},
        {0x44, 0x14df9, (void *)ar_tick},  {0x68, 0x5aeab, (void *)ar_frame}};
    static const BYTE getter[] = {0x8b, 0x41, 0x04, 0x8b, 0x4c, 0x24, 0x04, 0xc1, 0xe8, 0x1e, 0x03, 0x44, 0x24, 0x08,
                                  0x83, 0xe0, 0x03, 0x8d, 0x04, 0x88, 0xc2, 0x08, 0x00};
    static const BYTE seedsite[] = {0xff, 0x50, 0x44, 0x8b, 0x4b, 0x10, 0x89, 0x81, 0x84, 0x07, 0x00, 0x00};
    static const BYTE tickspans[] = {0xff, 0x50, 0x14};   /* Tick's own call vt+0x14 at 0x10014f56, returns to 0x10014f59 */
    DWORD *vt = (DWORD *)(spr + 0x62a5c), old;
    int i, n = (int)(sizeof(k) / sizeof(k[0]));
    for (i = 0; i < n; i++)
        if (vt[k[i].slot / 4] != spr + k[i].rva) {
            logf("ANIMROT> SIMSPR vtable 0x10062a5c +0x%02lX = 0x%08lX, shipped 0x%08lX - not patched", k[i].slot,
                 vt[k[i].slot / 4] - spr + 0x10000000, 0x10000000 + k[i].rva);
            return;
        }
    if (*(DWORD *)(spr + 0x62a50) != spr + 0x1531f || memcmp((BYTE *)spr + 0x5aeab, getter, sizeof(getter)) ||
        memcmp((BYTE *)spr + 0x14e5d, seedsite, sizeof(seedsite)) ||
        spr + 0x5a952 != spr + 0x14e3b + *(DWORD *)(spr + 0x14e37) || spr + 0x155bf != spr + 0x14e7e + *(DWORD *)(spr + 0x14e7a) ||
        *(BYTE *)(spr + 0x15758) != 0xe8 || memcmp((BYTE *)spr + 0x14f56, tickspans, sizeof(tickspans)) || spr + 0x14083 != spr + 0x1575d + *(DWORD *)(spr + 0x15759)) {
        logf("ANIMROT> SIMSPR anim sprite class differs from shipped - not patched");
        return;
    }
    if ((g_ar_tls = TlsAlloc()) == TLS_OUT_OF_INDEXES) { logf("ANIMROT> no TLS index - not patched"); return; }
    g_ar_vt = spr + 0x62a5c;
    g_ar_cscm = spr + 0x5a952;
    g_ar_viewchange = spr + 0x155bf;
    for (i = 0; i < n; i++) g_ar_o[k[i].slot / 4] = vt[k[i].slot / 4];
    /* .rdata page left RWX: never restore protection (memory project-mod-startup-races) */
    if (!VirtualProtect(vt - 6, 0x6c + 6 * 4, PAGE_EXECUTE_READWRITE, &old)) { logf("ANIMROT> VirtualProtect failed (%lu)", GetLastError()); return; }
    g_ar_tickcall = spr + 0x14f59;
    g_ar_start = spr + 0x1531f;
    g_ar_setmachine = spr + 0x14083;
    if (!VirtualProtect((BYTE *)spr + 0x15759, 4, PAGE_EXECUTE_READWRITE, &old)) { logf("ANIMROT> VirtualProtect failed (%lu)", GetLastError()); return; }
    for (i = 0; i < n; i++) InterlockedExchange((volatile LONG *)&vt[k[i].slot / 4], (LONG)k[i].fn);
    InterlockedExchange((volatile LONG *)(spr + 0x62a50), (LONG)ar_start);           /* second vtable +0xc StartAnimation */
    InterlockedExchange((volatile LONG *)(spr + 0x15759), (LONG)((DWORD)ar_setmachine - (spr + 0x1575d)));
    FlushInstructionCache(GetCurrentProcess(), (BYTE *)spr + 0x15758, 5);
    logf("ANIMROT> animated building sprites (SIMSPR class vtable 0x10062a5c, 11 slots + StartAnimation, ViewChange's "
         "SetAnimMachine call) draw, prepare, hit-test and tick their image layers and child sprites from slot view + rotation");
}
