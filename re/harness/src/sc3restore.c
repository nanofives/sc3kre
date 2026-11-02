/* sc3restore.c - restore an ageing building to new, for a price (task restore, 2026-11-02, re/analysis/RESTORE.md).
 *
 * Owner 2026-11-02: "en el menu de informacion de un edificio deberia haber un boton para restaurar (con costo acorde) el
 * edificio en cuestion si tiene vida util, luego agregar otro menu dentro de la seccion de reunirse". Owner calls: the
 * button exists only for buildings the game ages; cost = build price x fraction of life used; refused when funds are
 * short.
 *
 * STOCK MODEL. A building with a lifespan answers QueryInterface 0x43680ca9 (IBuildingMortal). Same slots in SIMUTIL
 * (power plants, water treatment) and SIMECO (incinerator, recycling) [CONFIRMED @ SIMUTIL vtable 0x10020c48, SIMECO
 * vtables 0x1001b160 / 0x1001b5d0]:
 *   +0x10 GetMaxAge (months)   +0x18 GetDeclineAge   +0x1c GetAge   +0x20 IsAging   +0x28 IsDefunct (byte)
 * GetAge = (year*12 + month) of the city date (city vt+0x1e4) minus that of the birthdate [CONFIRMED @ SIMUTIL 0x100120a1,
 * SIMECO 0x10001582]. The birthdate is a Julian day number (encode SIMUTIL 0x10016309, decode 0x10016432). The building
 * interface (QI 0xe0faadc7) reads and writes it: vt+0x40 GetBirthdate(date&) calls date vt+0x10(day number), vt+0x44
 * SetBirthdate(const date&) reads date vt+0x68() [CONFIRMED @ SIMUTIL 0x10006b73 / 0x10006b86, SIMECO 0x100013c9 /
 * 0x100013dc]. The game itself calls building vt+0x44 to hand a dead plant's date to its rubble (SIMUTIL 0x1000690c).
 * A plant dies when age > MaxAge (SIMUTIL 0x10007afb, -> rubble), an incinerator when age >= MaxAge (SIMECO
 * 0x1000234d); a plant's output falls linearly from DeclineAge to MaxAge and is recomputed every update
 * (SIMUTIL 0x100069fb), so a new birthdate also gives the output back.
 *
 * RESTORE. cost = price x clamp(age / MaxAge, 0, 1) x cost_percent / 100 (restore.ini, default 50), rounded, price = budget vt+0x54(type id) (the build price the building tool
 * charges, SIMGEOM 0x100072f6; budget = city vt+0x15c, SIMMISC vtable 0x1003c550). Funds = budget vt+0x10; refused
 * when short. Paid with budget vt+0x14 (Withdraw, the slot the building tool's commit uses). The new birthdate is the
 * first day of the current city month (age 0): today's year/month come from the game's own GetAge and the old
 * birthdate, so no date source of our own is involved. MaxAge / DeclineAge (the per-plant random variation is drawn
 * once, SIMUTIL 0x10006ba6) are kept.
 *
 * Exports (UI in sc3resize, RESTORE block): sc3restore_info, sc3restore_apply, sc3restore_list, sc3restore_apply_all,
 * sc3restore_funds. Off: SC3RESTORE=0 (every export refuses). Log: sc3restore.log beside the DLL.
 * Saves: only the stock birthdate changes, so a save loads the same without this mod.
 */

#include <windows.h>
#include "sc3mods_guard.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static CRITICAL_SECTION g_lock;
static HANDLE g_log = INVALID_HANDLE_VALUE;
static LARGE_INTEGER g_freq, g_t0;
static HMODULE g_self;
static int g_on;
/* COSTPCT (round restoreui 2026-11-02, owner: "restoring must be cheaper, keeping a building alive saves a rebuild"):
   the restore cost is this percent of price x fraction of life used. restore.ini beside the DLL, [restore]
   cost_percent=50 (default 50); SC3RESTORE_COSTPCT overrides; 100 = the 11-02 formula. Clamped to 0..1000. */
static LONG g_cost_pct = 50;

static void logf(const char *fmt, ...) {
    char buf[1536], line[1664];
    va_list ap;
    LARGE_INTEGER now;
    DWORD wrote;
    int n;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 1, fmt, ap);
    buf[sizeof(buf) - 1] = 0;
    va_end(ap);
    QueryPerformanceCounter(&now);
    n = _snprintf(line, sizeof(line) - 1, "[%9.3f ms][tid %04lx] %s\r\n",
                  (double)(now.QuadPart - g_t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart, GetCurrentThreadId(), buf);
    if (n < 0) return;
    EnterCriticalSection(&g_lock);
    if (g_log != INVALID_HANDLE_VALUE) WriteFile(g_log, line, (DWORD)n, &wrote, NULL);
    LeaveCriticalSection(&g_lock);
}

static void self_path(char *out, int cap, const char *leaf) {
    char *s;
    if (!GetModuleFileNameA(g_self, out, cap)) { out[0] = 0; return; }
    s = strrchr(out, '\\');
    if (s) s[1] = 0; else out[0] = 0;
    lstrcatA(out, leaf);
}

/* ============================================================ game calls */

static DWORD thiscall_n(void *self, void *fn, const DWORD *a, int n) {
    DWORD rv = 0;
    __asm {
        push ebx
        push esi
        push edi
        mov  ebx, esp
        mov  edi, a
        mov  ecx, n
        test ecx, ecx
        jz   tc_ready
    tc_push:
        mov  eax, [edi + ecx*4 - 4]
        push eax
        dec  ecx
        jnz  tc_push
    tc_ready:
        mov  ecx, self
        call [fn]
        mov  esp, ebx
        mov  rv, eax
        pop  edi
        pop  esi
        pop  ebx
    }
    return rv;
}

/* vtable call, slot byte offset, up to 4 args; 0 on a bad object */
static DWORD vc(void *o, DWORD slot, int n, DWORD a0, DWORD a1, DWORD a2, DWORD a3) {
    DWORD *vt, a[4];
    if (!o || IsBadReadPtr(o, 4)) return 0;
    vt = *(DWORD **)o;
    if (!vt || IsBadReadPtr((BYTE *)vt + slot, 4) || !vt[slot / 4]) return 0;
    a[0] = a0; a[1] = a1; a[2] = a2; a[3] = a3;
    return thiscall_n(o, (void *)vt[slot / 4], a, n);
}

/* the loaded city: *(SC3U.exe + 0xfa86c) + 0x48, vtable SIMCITY + 0x13260 (sc3simrun / sc3undo / sc3landfill) */
static BYTE *city_get(void) {
    BYTE *exe = (BYTE *)GetModuleHandleA(NULL), *app, *c;
    HMODULE sc = GetModuleHandleA("SIMCITY.DLL");
    if (!sc) return NULL;
    __try {
        app = *(BYTE **)(exe + 0xfa86c);
        if (!app) return NULL;
        c = *(BYTE **)(app + 0x48);
        if (!c || *(DWORD *)c != (DWORD)sc + 0x13260) return NULL;
        return c;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return NULL; }
}

/* budget: city vt+0x15c, vtable SIMMISC + 0x3c550 (sc3resize RELOCATE / PLOPOVER) */
static void *budget_get(void) {
    BYTE *c = city_get();
    HMODULE misc = GetModuleHandleA("SIMMISC.DLL");
    void *b;
    if (!c || !misc) return NULL;
    b = (void *)vc(c, 0x15c, 0, 0, 0, 0, 0);
    return b && !IsBadReadPtr(b, 4) && *(DWORD *)b == (DWORD)misc + 0x3c550 ? b : NULL;
}

/* A date object the game's Get/SetBirthdate can talk to: they only call vt+0x10 Set(day number) and vt+0x68 Get()
   [CONFIRMED @ SIMUTIL 0x10006b73, 0x10015fdd; SIMECO 0x100013c9, 0x10011313]. __fastcall with a dummy edx is the
   thiscall shape (this in ecx, callee pops the stack args). Every other slot is the 0-arg getter. */
typedef struct { const DWORD *vt; DWORD jdn; } FakeDate;
static DWORD __fastcall fdate_get(FakeDate *d, void *edx) { (void)edx; return d->jdn; }
static void __fastcall fdate_set(FakeDate *d, void *edx, DWORD j) { (void)edx; d->jdn = j; }
static DWORD g_fd_vt[48];
static void fd_init(FakeDate *d, DWORD jdn) {
    int i;
    if (!g_fd_vt[0]) {
        for (i = 0; i < 48; i++) g_fd_vt[i] = (DWORD)fdate_get;
        g_fd_vt[0x10 / 4] = (DWORD)fdate_set;
    }
    d->vt = g_fd_vt; d->jdn = jdn;
}

/* Julian day number, the game's own arithmetic (SIMUTIL 0x10016309 encode, 0x10016432 decode) */
static DWORD jdn_make(DWORD m, DWORD d, DWORD y) {
    DWORD mm, c;
    if (m < 3) { mm = m + 9; y -= 1; } else mm = m - 3;
    c = y / 100;
    return ((c * 0x23ab1) >> 2) + 0x1a431f + (mm * 0x99 + 2) / 5 + d + ((y * 0x5b5 - c * 0x23ab4) >> 2);
}
static void jdn_split(DWORD j, DWORD *m, DWORD *d, DWORD *y) {
    DWORD t = (j - 0x1a431f) * 4, c, u, yy, mm;
    c = (t - 1) / 0x23ab1;
    u = (t - c * 0x23ab1 - 1) & 0xfffffffc;
    yy = (u + 3) / 0x5b5;
    t = ((u - yy * 0x5b5 + 7) >> 2) * 5;
    mm = (t - 3) / 0x99;
    *d = (t - mm * 0x99 + 2) / 5;
    *y = c * 100 + yy;
    if (mm < 10) *m = mm + 3; else { *m = mm - 9; (*y)++; }
}

/* ============================================================ one building */

#define SC3R_NAME 64
typedef struct {
    DWORD size;                 /* sizeof(SC3R_INFO), checked */
    DWORD type;                 /* occupant vt+0x88 type id */
    LONG  age, max_age, decline, aging, defunct;
    LONG  price, cost;          /* build price, restore cost */
    LONG  x0, z0, x1, z1;       /* footprint, cells (occupant vt+0xd0) */
    LONG  birth_y, birth_m;
    char  name[SC3R_NAME];      /* occupant vt+0x7c, the query dialog's title */
} SC3R_INFO;

static void *qi(void *o, DWORD iid) {
    void *r = NULL;
    if (!(vc(o, 0x00, 2, iid, (DWORD)&r, 0, 0) & 0xff) || !r || IsBadReadPtr(r, 4)) return NULL;
    return r;
}
static void rel(void *o) { if (o) vc(o, 0x08, 0, 0, 0, 0, 0); }

static void occ_name(void *occ, char *out, int cap) {
    HMODULE sui = GetModuleHandleA("SIMUI.DLL");
    BYTE s[0x20];
    const char *t;
    out[0] = 0;
    if (!sui) return;
    memset(s, 0, sizeof(s));
    ((void (__fastcall *)(void *))((BYTE *)sui + 0x5eb6))(s);       /* SIMUI string ctor FUN_10005eb6 */
    vc(occ, 0x7c, 1, (DWORD)s, 0, 0, 0);
    t = (const char *)vc(s, 0x14, 0, 0, 0, 0, 0);
    if (t && !IsBadStringPtrA(t, 128)) lstrcpynA(out, t, cap);
    ((void (__fastcall *)(void *))((BYTE *)sui + 0x6057))(s);       /* dtor FUN_10006057 */
}

/* a SIMUTIL plant's current output and base capacity (mortal vt+0x3c = 0x10002563 returns +8, vt+0x38 = 0x10006b67
   returns +0xc; +8 is rewritten from +0xc by vt+0x74 = 0x10006c57 / derate 0x100069fb on every update). 0 = not one. */
static int plant_output(void *mortal, LONG *now, LONG *base) {
    BYTE *u = (BYTE *)GetModuleHandleA("SIMUTIL.DLL");
    DWORD *vt = *(DWORD **)mortal;
    if (!u || vt[0x3c / 4] != (DWORD)u + 0x2563 || vt[0x38 / 4] != (DWORD)u + 0x6b67) return 0;
    *now = *(LONG *)((BYTE *)mortal + 8); *base = *(LONG *)((BYTE *)mortal + 0xc);
    return 1;
}
static void log_output(void *occ, const char *tag) {
    void *mo = qi(occ, 0x43680ca9);
    LONG now, base;
    if (!mo) return;
    if (plant_output(mo, &now, &base))
        logf("OUTPUT> %s: output %ld of base %ld, age %ld, IsDefunct %lu", tag, now, base,
             (LONG)vc(mo, 0x1c, 0, 0, 0, 0, 0), vc(mo, 0x28, 0, 0, 0, 0, 0) & 0xff);
    rel(mo);
}

static void log_class_once(void *mortal, void *occ) {
    static DWORD seen[32];
    static int n;
    DWORD vt = *(DWORD *)mortal, ga = ((DWORD *)vt)[0x1c / 4];
    HMODULE m = NULL;
    char p[MAX_PATH] = "?", *s;
    int i;
    for (i = 0; i < n; i++) if (seen[i] == vt) return;
    if (n < 32) seen[n++] = vt;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)vt, &m);
    if (m) GetModuleFileNameA(m, p, sizeof(p));
    s = strrchr(p, '\\');
    logf("CLASS> mortal vtable %s+0x%lX (GetAge +0x%lX), occupant vtable +0x%lX, mortal = occupant %+ld",
         s ? s + 1 : p, vt - (DWORD)m, ga - (DWORD)m, *(DWORD *)occ - (DWORD)m, (LONG)((BYTE *)mortal - (BYTE *)occ));
}

/* 1 = occ has a lifespan; fills *o (defunct ones too, flagged) */
static int info_of(void *occ, SC3R_INFO *o) {
    void *mo = NULL, *bu = NULL, *bud;
    FakeDate fd;
    DWORD m = 0, d = 0, y = 0;
    LONG r[4];
    int ok = 0;
    memset(o, 0, sizeof(*o));
    o->size = sizeof(*o);
    __try {
        mo = qi(occ, 0x43680ca9);
        if (!mo) return 0;
        log_class_once(mo, occ);
        o->max_age = (LONG)vc(mo, 0x10, 0, 0, 0, 0, 0);
        o->decline = (LONG)vc(mo, 0x18, 0, 0, 0, 0, 0);
        o->age     = (LONG)vc(mo, 0x1c, 0, 0, 0, 0, 0);
        o->aging   = (LONG)(vc(mo, 0x20, 0, 0, 0, 0, 0) & 0xff);
        o->defunct = (LONG)(vc(mo, 0x28, 0, 0, 0, 0, 0) & 0xff);
        if (o->max_age <= 0 || o->max_age > 100000 || o->age < -1200 || o->age > 1000000) {
            logf("INFO> occupant 0x%08lX answers 0x43680ca9 but MaxAge %ld age %ld are out of range: ignored",
                 (DWORD)occ, o->max_age, o->age);
            rel(mo);
            return 0;
        }
        bu = qi(occ, 0xe0faadc7);
        if (bu) {
            fd_init(&fd, 0);
            vc(bu, 0x40, 1, (DWORD)&fd, 0, 0, 0);            /* GetBirthdate */
            if (fd.jdn) { jdn_split(fd.jdn, &m, &d, &y); o->birth_y = (LONG)y; o->birth_m = (LONG)m; }
            rel(bu);
        }
        o->type = vc(occ, 0x88, 0, 0, 0, 0, 0);
        memset(r, 0, sizeof(r));
        vc(occ, 0xd0, 1, (DWORD)r, 0, 0, 0);
        o->x0 = r[0]; o->z0 = r[1]; o->x1 = r[2]; o->z1 = r[3];
        occ_name(occ, o->name, sizeof(o->name));
        bud = budget_get();
        o->price = bud ? (LONG)vc(bud, 0x54, 1, o->type, 0, 0, 0) : 0;
        if (o->price < 0) o->price = 0;
        {   /* price x clamp(age / MaxAge, 0, 1) x cost_percent / 100, rounded half up (COSTPCT) */
            LONG used = o->age < 0 ? 0 : (o->age > o->max_age ? o->max_age : o->age);
            __int64 den = (__int64)o->max_age * 100;
            o->cost = (LONG)(((__int64)o->price * used * g_cost_pct * 2 + den) / (den * 2));
        }
        ok = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("INFO> fault reading occupant 0x%08lX", (DWORD)occ); ok = 0; }
    if (mo) rel(mo);
    return ok;
}

/* the new birthdate: first day of the city's current month, from GetAge and the old birthdate */
static int restore_one(void *occ, SC3R_INFO *before) {
    void *bu;
    FakeDate fd;
    LONG ym, age_after;
    DWORD y, m;
    SC3R_INFO after;
    int ok = 0;
    if (!before->birth_y) return 0;
    ym = before->birth_y * 12 + (before->birth_m - 1) + before->age;    /* the city's year*12 + month-1 now */
    y = (DWORD)(ym / 12); m = (DWORD)(ym % 12) + 1;
    bu = qi(occ, 0xe0faadc7);
    if (!bu) return 0;
    __try {
        fd_init(&fd, jdn_make(m, 1, y));
        vc(bu, 0x44, 1, (DWORD)&fd, 0, 0, 0);                    /* SetBirthdate */
        ok = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) { ok = 0; }
    rel(bu);
    if (ok && info_of(occ, &after)) {
        age_after = after.age;
        logf("RESTORE> %s (type %lu) at (%ld, %ld): age %ld -> %ld months, birthdate %ld-%02ld -> %ld-%02ld, MaxAge %ld, decline %ld, IsDefunct %ld",
             before->name, before->type, before->x0, before->z0, before->age, age_after, before->birth_y, before->birth_m,
             after.birth_y, after.birth_m, after.max_age, after.decline, after.defunct);
        log_output(occ, "right after the restore (the game recomputes it on its next update)");
        ok = age_after == 0 && !after.defunct;
    }
    return ok;
}

static LONG funds_get(void *bud) { return bud ? (LONG)vc(bud, 0x10, 0, 0, 0, 0, 0) : 0; }

static void fmt_money(char *out, int cap, LONG v) {    /* 1234567 -> "1,234,567", as the game's HUD and dialogs */
    char t[32];
    int n, i, j = 0, neg = v < 0;
    _snprintf(t, sizeof(t), "%ld", neg ? -v : v);
    n = (int)strlen(t);
    if (neg && j < cap - 1) out[j++] = '-';
    for (i = 0; i < n && j < cap - 1; i++) {
        out[j++] = t[i];
        if ((n - 1 - i) % 3 == 0 && i < n - 1 && j < cap - 1) out[j++] = ',';
    }
    out[j] = 0;
}

/* ============================================================ exports */

/* 1 = the occupant has a lifespan and is alive (the button applies). out may be NULL. */
__declspec(dllexport) int __cdecl sc3restore_info(void *occ, SC3R_INFO *out) {
    SC3R_INFO i;
    if (!g_on || !occ) return 0;
    if (out && out->size != sizeof(SC3R_INFO)) { logf("INFO> caller struct size %lu != %u", out->size, (unsigned)sizeof(SC3R_INFO)); return 0; }
    if (!info_of(occ, &i) || i.defunct) return 0;
    if (out) *out = i;
    return 1;
}

__declspec(dllexport) LONG __cdecl sc3restore_funds(void) { return g_on ? funds_get(budget_get()) : 0; }

/* 1 restored, 0 refused (msg says why). */
__declspec(dllexport) int __cdecl sc3restore_apply(void *occ, int es, char *msg, int cap) {
    SC3R_INFO i;
    void *bud = budget_get();
    LONG f0;
    char a[32], b[32];
    msg[0] = 0;
    if (!g_on || !occ) return 0;
    if (!info_of(occ, &i) || i.defunct) { _snprintf(msg, cap, es ? "Este edificio no envejece" : "This building does not age"); return 0; }
    if (i.age <= 0) { _snprintf(msg, cap, es ? "Ya est\xe1 como nuevo" : "Already as good as new"); return 0; }
    if (!bud) { _snprintf(msg, cap, es ? "Sin presupuesto" : "No budget"); return 0; }
    f0 = funds_get(bud);
    fmt_money(a, sizeof(a), i.cost); fmt_money(b, sizeof(b), f0);
    if (f0 < i.cost) {
        _snprintf(msg, cap, es ? "Fondos insuficientes: cuesta $%s, hay $%s" : "Not enough funds: costs $%s, you have $%s", a, b);
        logf("APPLY> refused, funds %ld < cost %ld (%s)", f0, i.cost, i.name);
        return 0;
    }
    log_output(occ, "before the restore");
    if (!restore_one(occ, &i)) { _snprintf(msg, cap, es ? "No se pudo restaurar" : "Could not restore"); return 0; }
    if (i.cost > 0) vc(bud, 0x14, 1, (DWORD)i.cost, 0, 0, 0);           /* Withdraw */
    logf("APPLY> %s restored: price %ld, used %ld of %ld months, cost %ld; funds %ld -> %ld", i.name, i.price, i.age,
         i.max_age, i.cost, f0, funds_get(bud));
    _snprintf(msg, cap, es ? "Restaurado por $%s" : "Restored for $%s", a);
    return 1;
}

/* Every building with a lifespan in the city, alive ones only, one row each (cell scan with the surface occupant
   manager: city vt+0x11c, GetCellsInX/Z vt+0x14/+0x18, GetOccupantAtCell vt+0x7c AddRefs [CONFIRMED @ SIMGEOM
   0x1000ec60]). Returns the row count (at most cap), *total = sum of costs. Ordered by life left, least first. */
typedef char (__fastcall *PFN_AT)(void *om, void *edx, DWORD x, DWORD z, void **occ);
typedef char (__fastcall *PFN_QI)(void *o, void *edx, DWORD iid, void **out);
typedef DWORD (__fastcall *PFN_REL)(void *o, void *edx);
static int cmp_left(const void *a, const void *b) {
    const SC3R_INFO *p = (const SC3R_INFO *)a, *q = (const SC3R_INFO *)b;
    LONG lp = p->max_age - p->age, lq = q->max_age - q->age;
    return lp < lq ? -1 : lp > lq ? 1 : 0;
}
__declspec(dllexport) int __cdecl sc3restore_list(SC3R_INFO *rows, int cap, LONG *total) {
    BYTE *c = city_get();
    void *om;
    PFN_AT at;
    int nx, nz, x = 0, z = 0, n = 0, ns = 0, k, cells = 0, ndef = 0;
    LARGE_INTEGER t0, t1;
    if (total) *total = 0;
    if (!g_on || !c || !rows || cap <= 0) return 0;
    if (rows[0].size != sizeof(SC3R_INFO)) { logf("LIST> caller struct size %lu != %u", rows[0].size, (unsigned)sizeof(SC3R_INFO)); return 0; }
    om = (void *)vc(c, 0x11c, 0, 0, 0, 0, 0);
    if (!om) return 0;
    nx = (int)vc(om, 0x14, 0, 0, 0, 0, 0);
    nz = (int)vc(om, 0x18, 0, 0, 0, 0, 0);
    if (nx <= 0 || nz <= 0 || nx > 4096 || nz > 4096) return 0;
    at = (PFN_AT)(*(DWORD **)om)[0x7c / 4];
    QueryPerformanceCounter(&t0);
    __try {
        for (z = 0; z < nz; z++) for (x = 0; x < nx; x++) {
            void *o = NULL, *mo = NULL;
            DWORD *vt;
            cells++;
            if (!(at(om, NULL, (DWORD)x, (DWORD)z, &o) & 0xff) || !o) continue;
            vt = *(DWORD **)o;   /* QI and Release called directly: two IsBadReadPtr per cell would dominate on 1024 maps */
            if ((((PFN_QI)vt[0])(o, NULL, 0x43680ca9, &mo) & 0xff) && mo) {
                LONG r[4];
                ((PFN_REL)(*(DWORD **)mo)[2])(mo, NULL);
                memset(r, 0, sizeof(r));
                vc(o, 0xd0, 1, (DWORD)r, 0, 0, 0);
                if (r[0] == x && r[1] == z) {          /* one row per building: only at its first cell */
                    SC3R_INFO i;
                    ns++;
                    if (info_of(o, &i)) {
                        if (!i.defunct) { if (n < cap) rows[n++] = i; }
                        else if (ndef++ < 8) logf("LIST>   defunct (no button): %s type %lu at (%ld, %ld) age %ld / %ld",
                                                  i.name, i.type, i.x0, i.z0, i.age, i.max_age);
                    }
                }
            }
            ((PFN_REL)vt[2])(o, NULL);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { logf("LIST> fault in the cell scan at (%d, %d)", x, z); }
    QueryPerformanceCounter(&t1);
    qsort(rows, n, sizeof(SC3R_INFO), cmp_left);
    if (total) for (k = 0; k < n; k++) *total += rows[k].cost;
    logf("LIST> %d building(s) with a lifespan alive (%d with one, defunct included), %d cells (%dx%d) in %.1f ms, total cost %ld", n, ns, cells,
         nx, nz, (double)(t1.QuadPart - t0.QuadPart) * 1000.0 / (double)g_freq.QuadPart, total ? *total : 0);
    for (k = 0; k < n && k < 40; k++)
        logf("LIST>   %s type %lu at (%ld, %ld) age %ld / %ld (decline %ld) born %ld-%02ld price %ld cost %ld",
             rows[k].name, rows[k].type, rows[k].x0, rows[k].z0, rows[k].age, rows[k].max_age, rows[k].decline,
             rows[k].birth_y, rows[k].birth_m, rows[k].price, rows[k].cost);
    return n;
}

/* the building whose footprint starts at (x0, z0), still of type `type`, AddRef'd */
static void *occ_at(DWORD x0, DWORD z0, DWORD type) {
    BYTE *c = city_get();
    void *om = c ? (void *)vc(c, 0x11c, 0, 0, 0, 0, 0) : NULL, *o = NULL;
    if (!om) return NULL;
    if (!(vc(om, 0x7c, 3, x0, z0, (DWORD)&o, 0) & 0xff) || !o) return NULL;
    if (vc(o, 0x88, 0, 0, 0, 0, 0) != type) { rel(o); return NULL; }
    return o;
}

/* One row of the list: the building at (x0, z0) of that type. 1 restored, 0 refused, 3 refused because the cost is now
   above max_cost (the price the player saw; the city ages while the list is open), max_cost < 0 = no ceiling. */
__declspec(dllexport) int __cdecl sc3restore_apply_at(LONG x0, LONG z0, DWORD type, LONG max_cost, int es, char *msg, int cap) {
    void *o;
    int r;
    SC3R_INFO i;
    msg[0] = 0;
    if (!g_on) return 0;
    o = occ_at((DWORD)x0, (DWORD)z0, type);
    if (!o) { _snprintf(msg, cap, es ? "El edificio ya no est\xe1" : "The building is gone"); return 0; }
    if (max_cost >= 0 && info_of(o, &i) && i.cost > max_cost) {
        char a[32];
        fmt_money(a, sizeof(a), i.cost);
        _snprintf(msg, cap, es ? "El costo subi\xf3 a $%s: puls\xe1 de nuevo" : "The cost is now $%s: click again", a);
        logf("APPLY> refused, cost %ld above the %ld shown (%s)", i.cost, max_cost, i.name);
        rel(o);
        return 3;
    }
    r = sc3restore_apply(o, es, msg, cap);
    rel(o);
    return r;
}

/* Every building in the list, all or nothing: refused when funds are short of the total, or (-1) when the total is now
   above max_total (the price the player saw), max_total < 0 = no ceiling. Returns how many restored. */
__declspec(dllexport) int __cdecl sc3restore_apply_all(LONG max_total, int es, char *msg, int cap) {
    static SC3R_INFO rows[512];
    void *bud = budget_get();
    LONG total = 0, f0, paid = 0;
    int n, k, done = 0;
    char a[32], b[32];
    msg[0] = 0;
    if (!g_on || !bud) return 0;
    rows[0].size = sizeof(SC3R_INFO);
    n = sc3restore_list(rows, 512, &total);
    f0 = funds_get(bud);
    fmt_money(a, sizeof(a), total); fmt_money(b, sizeof(b), f0);
    if (max_total >= 0 && total > max_total) {
        _snprintf(msg, cap, es ? "El costo subi\xf3 a $%s: puls\xe1 de nuevo" : "The cost is now $%s: click again", a);
        logf("ALL> refused, total %ld above the %ld shown", total, max_total);
        return -1;
    }
    if (f0 < total) {
        _snprintf(msg, cap, es ? "Fondos insuficientes: cuesta $%s, hay $%s" : "Not enough funds: costs $%s, you have $%s", a, b);
        logf("ALL> refused, funds %ld < total %ld", f0, total);
        return 0;
    }
    for (k = 0; k < n; k++) {
        void *o;
        if (rows[k].age <= 0) continue;
        o = occ_at((DWORD)rows[k].x0, (DWORD)rows[k].z0, rows[k].type);
        if (!o) continue;
        if (restore_one(o, &rows[k])) { done++; paid += rows[k].cost; }
        rel(o);
    }
    if (paid > 0) vc(bud, 0x14, 1, (DWORD)paid, 0, 0, 0);
    fmt_money(a, sizeof(a), paid);
    logf("ALL> %d of %d restored, paid %ld; funds %ld -> %ld", done, n, paid, f0, funds_get(bud));
    _snprintf(msg, cap, es ? "%d restaurado(s) por $%s" : "%d restored for $%s", done, a);
    return done;
}

/* TEST ONLY (restore_lab, WM_RZ_RESTORE 5): set the building at (x, z) to `left` months before its MaxAge, so a lab can
   put a plant past its decline age and watch the output fall and come back. Free, logged. */
__declspec(dllexport) int __cdecl sc3restore_test_left(LONG x, LONG z, LONG left) {
    BYTE *c = city_get();
    void *om = c ? (void *)vc(c, 0x11c, 0, 0, 0, 0, 0) : NULL, *o = NULL, *bu;
    SC3R_INFO i;
    FakeDate fd;
    LONG ym, want;
    if (!g_on || !om || !(vc(om, 0x7c, 3, (DWORD)x, (DWORD)z, (DWORD)&o, 0) & 0xff) || !o) return 0;
    if (!info_of(o, &i) || !i.birth_y) { rel(o); return 0; }
    log_output(o, "test: before ageing");
    want = i.max_age - left;
    ym = i.birth_y * 12 + (i.birth_m - 1) + i.age - want;   /* birth year*12 + month-1 that gives age `want` */
    bu = qi(o, 0xe0faadc7);
    if (bu) { fd_init(&fd, jdn_make((DWORD)(ym % 12) + 1, 1, (DWORD)(ym / 12))); vc(bu, 0x44, 1, (DWORD)&fd, 0, 0, 0); rel(bu); }
    info_of(o, &i);
    logf("TEST> %s at (%ld, %ld) aged to %ld of %ld months (decline %ld)", i.name, i.x0, i.z0, i.age, i.max_age, i.decline);
    log_output(o, "test: right after ageing");
    rel(o);
    return 1;
}
/* TEST ONLY: log the output of the plant at (x, z) */
__declspec(dllexport) int __cdecl sc3restore_test_output(LONG x, LONG z) {
    BYTE *c = city_get();
    void *om = c ? (void *)vc(c, 0x11c, 0, 0, 0, 0, 0) : NULL, *o = NULL;
    if (!g_on || !om || !(vc(om, 0x7c, 3, (DWORD)x, (DWORD)z, (DWORD)&o, 0) & 0xff) || !o) return 0;
    log_output(o, "test: now");
    rel(o);
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    char v[8];
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        if (!sc3mods_guard(inst, "sc3restore")) return TRUE;
        g_self = (HMODULE)inst;
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&g_lock);
        QueryPerformanceFrequency(&g_freq);
        QueryPerformanceCounter(&g_t0);
        {   char path[MAX_PATH];
            self_path(path, sizeof(path), "sc3restore.log");
            g_log = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        }
        if (GetEnvironmentVariableA("SC3RESTORE", v, sizeof(v)) && v[0] == '0') {
            logf("### sc3restore off (SC3RESTORE=0): every export refuses");
            return TRUE;
        }
        g_on = 1;
        {   char ini[MAX_PATH];
            self_path(ini, sizeof(ini), "restore.ini");
            g_cost_pct = (LONG)GetPrivateProfileIntA("restore", "cost_percent", 50, ini);
            if (GetEnvironmentVariableA("SC3RESTORE_COSTPCT", v, sizeof(v))) g_cost_pct = atol(v);
            if (g_cost_pct < 0) g_cost_pct = 0;
            if (g_cost_pct > 1000) g_cost_pct = 1000;
        }
        logf("### sc3restore loaded: nothing patched, exports for sc3resize's RESTORE block; cost = %ld%% of price x life used "
             "(restore.ini [restore] cost_percent, SC3RESTORE_COSTPCT)", g_cost_pct);
    }
    return TRUE;
}
