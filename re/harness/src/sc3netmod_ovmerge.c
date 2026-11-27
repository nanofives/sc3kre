/* sc3netmod_ovmerge.c - OVMERGE (task overlaymerge 2026-11-21, verify/overlaymerge/RESULTS.md). Included by sc3netmod.c
 * inside the OVERLAY block, before ov_map.
 *
 * Simtropolis 2026-11-21: "I tried to install this agricultural mod ... it doesn't appear in-game ... doesn't throw any
 * errors when it installs". The OVERLAY block serves <root>\mods\netmod\overlay\X for every X the overlay holds, so a mod
 * that edits the stock <root>\X afterwards is never read. The files the overlay shadows depend on the installed packages
 * (34 in the 2026-11-20 LAN build: Apps\Res\BUILDFAM.IXF, TRBLKATT / VPATHATT in 7 languages, 18 TilingRules texts,
 * Apps\Sys\SYS.PAK; the full list is in RESULTS.md and `overlay_base.py --check` prints it for a tree).
 *
 * This block runs once in DllMain after ov_walk. For every overlay file that has a line in
 * <root>\mods\netmod\overlay_base.txt (stock SHA-256 + per-record / per-line FNV hashes, written by
 * re/tools/netmod/overlay_base.py when the overlay is built), it hashes the player's <root>\X:
 *   - same SHA-256 as stock: nothing happens, the overlay file is served as before (stock behaviour of this mod)
 *   - different: a three-way merge, base = stock (the hashes), ours = the overlay file as it is now (so the community
 *     patch and bat_growables, which edit the overlay copy, are kept), theirs = the player's file.
 *       IXF (BUILDFAM, TRBLKATT, VPATHATT, ...): per record {group, instance, type}. A record only the player changed,
 *         added or removed is taken from theirs. A "TXT!" record both sides changed (a farm mod and the style mix both
 *         add Key lines to the farm family) is merged line by line, "BuildingCount" by adding the two deltas.
 *       SYS.PAK: per member, then line by line inside the member ([section] key=value).
 *       anything else (the TilingRules texts): not merged, a warning.
 *     A line or record both sides changed differently keeps ours and is counted as a conflict.
 *     The merged file is written to %TEMP%\sc3netmod_merge_<pid>\ and served instead of the overlay file. When the
 *     merge changes nothing (the overlay already has the player's edit, as with the community patch) the overlay file
 *     is served.
 * Unmerged files and conflicts are logged with "### ovmerge" and counted for sc3netmod_ovmerge_status(), which sc3perf
 * reads to show a warning on screen (sc3perf OVWARN).
 * Off: SC3NETMOD_OVMERGE=0 (the overlay files are served as before, nothing is hashed). No base file = off, logged.
 *
 * Text line rules (keep in step with overlay_base.py): split on LF, one trailing CR dropped, trimmed of spaces/tabs;
 * "[x]" sets the section; ";", "#", "//" lines and lines with no '=' / ':' (or one at column 0) are structural and never
 * merged; else the first of '=' / ':' splits key (lower-cased) and value; skey = section 0x1F key, whole = skey "=" value.
 * A key that appears more than once in its section in any of the three versions (Default.ini [DBSegments], the
 * BUILDFAM "Key:" lines) is matched by its whole line instead of by its key. */

#define OM_DETAIL_MAX 40

static char **g_ovalt;                 /* parallel to g_ovfiles: the merged copy served instead, NULL = the overlay file */
static volatile LONG g_om_unmerged;    /* files with a change the served copy does not hold (conflicts or not mergeable) */
static char g_om_names[256];           /* their names, for the on-screen warning */
static int g_om_merged;
static char g_om_dir[MAX_PATH];        /* %TEMP%\sc3netmod_merge_<pid>\ */
static int g_om_detail;

typedef unsigned __int64 U64;

/* ---------------------------------------------------------------- hashes */
static U64 fnv_add(U64 h, const BYTE *p, DWORD n) {
    DWORD i;
    for (i = 0; i < n; i++) { h ^= p[i]; h *= 0x100000001B3ui64; }
    return h;
}
#define FNV0 0xCBF29CE484222325ui64

typedef struct { DWORD h[8]; U64 len; BYTE buf[64]; DWORD n; } SHA256C;
static const DWORD k_sha[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,
    0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
    0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
    0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,
    0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2 };
#define ROR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
static void sha_block(SHA256C *c, const BYTE *p) {
    DWORD w[64], a, b, d, e, f, g, h, cc, t1, t2;
    int i;
    for (i = 0; i < 16; i++) w[i] = ((DWORD)p[i * 4] << 24) | ((DWORD)p[i * 4 + 1] << 16) | ((DWORD)p[i * 4 + 2] << 8) | p[i * 4 + 3];
    for (i = 16; i < 64; i++) {
        DWORD s0 = ROR32(w[i - 15], 7) ^ ROR32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        DWORD s1 = ROR32(w[i - 2], 17) ^ ROR32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = c->h[0]; b = c->h[1]; cc = c->h[2]; d = c->h[3]; e = c->h[4]; f = c->h[5]; g = c->h[6]; h = c->h[7];
    for (i = 0; i < 64; i++) {
        t1 = h + (ROR32(e, 6) ^ ROR32(e, 11) ^ ROR32(e, 25)) + ((e & f) ^ (~e & g)) + k_sha[i] + w[i];
        t2 = (ROR32(a, 2) ^ ROR32(a, 13) ^ ROR32(a, 22)) + ((a & b) ^ (a & cc) ^ (b & cc));
        h = g; g = f; f = e; e = d + t1; d = cc; cc = b; b = a; a = t1 + t2;
    }
    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d; c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;
}
static void sha256_hex(const BYTE *p, DWORD n, char *hex65) {
    static const DWORD h0[8] = { 0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19 };
    SHA256C c;
    BYTE tail[128];
    DWORD i, full = n & ~63u, rest = n - full, tl;
    U64 bits = (U64)n * 8;
    memcpy(c.h, h0, sizeof(h0));
    for (i = 0; i < full; i += 64) sha_block(&c, p + i);
    memset(tail, 0, sizeof(tail));
    memcpy(tail, p + full, rest);
    tail[rest] = 0x80;
    tl = rest + 1 + 8 <= 64 ? 64 : 128;
    for (i = 0; i < 8; i++) tail[tl - 1 - i] = (BYTE)(bits >> (8 * i));
    sha_block(&c, tail);
    if (tl == 128) sha_block(&c, tail + 64);
    for (i = 0; i < 8; i++) _snprintf(hex65 + i * 8, 9, "%08lX", c.h[i]);
    hex65[64] = 0;
}

/* ---------------------------------------------------------------- files */
static BYTE *om_read(const char *path, DWORD *n) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD got = 0, sz;
    BYTE *b;
    *n = 0;
    if (h == INVALID_HANDLE_VALUE) return NULL;
    sz = GetFileSize(h, NULL);
    b = (sz != INVALID_FILE_SIZE && sz < (256u << 20)) ? (BYTE *)malloc(sz + 1) : NULL;
    if (b && !(ReadFile(h, b, sz, &got, NULL) && got == sz)) { free(b); b = NULL; }
    CloseHandle(h);
    if (b) { b[sz] = 0; *n = sz; }
    return b;
}

static int om_write(const char *path, const BYTE *b, DWORD n) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD w = 0;
    int ok;
    if (h == INVALID_HANDLE_VALUE) return 0;
    ok = WriteFile(h, b, n, &w, NULL) && w == n;
    CloseHandle(h);
    if (!ok) DeleteFileA(path);
    return ok;
}

/* growable byte buffer */
typedef struct { BYTE *p; DWORD n, cap; int bad; } OBuf;
static void ob_put(OBuf *o, const void *s, DWORD n) {
    if (o->bad) return;
    if (o->n + n > o->cap) {
        DWORD c = o->cap ? o->cap : 4096;
        BYTE *q;
        while (c < o->n + n) c *= 2;
        q = (BYTE *)realloc(o->p, c);
        if (!q) { o->bad = 1; return; }
        o->p = q; o->cap = c;
    }
    memcpy(o->p + o->n, s, n);
    o->n += n;
}
static void ob_u32(OBuf *o, DWORD v) { ob_put(o, &v, 4); }

/* ---------------------------------------------------------------- the base file */
typedef struct { const char *rel; char sha[65]; char kind; int l0, l1; } OmFile;   /* kind 'i' ixf, 'p' pak, 'f' file */
static char **g_bl;      /* base lines */
static int g_nbl;
static OmFile *g_bf;
static int g_nbf;

static int om_base_load(const char *path) {
    DWORD n, i;
    BYTE *b = om_read(path, &n);
    char *s;
    int cap = 0;
    if (!b) return 0;
    for (i = 0; i < n; i++) if (b[i] == '\n') cap++;
    g_bl = (char **)malloc((cap + 2) * sizeof(char *));
    if (!g_bl) { free(b); return 0; }
    s = (char *)b;
    while (*s) {
        char *e = strchr(s, '\n');
        if (e) { *e = 0; if (e > s && e[-1] == '\r') e[-1] = 0; }
        g_bl[g_nbl++] = s;
        if (!e) break;
        s = e + 1;
    }
    if (!g_nbl || strncmp(g_bl[0], "sc3netmod overlay base 1", 24)) { logf("### ovmerge: %s is not an overlay base file", path); return 0; }
    for (i = 1; i < (DWORD)g_nbl; i++) if (g_bl[i][0] == 'F') g_nbf++;
    g_bf = (OmFile *)calloc(g_nbf + 1, sizeof(OmFile));
    if (!g_bf) return 0;
    g_nbf = 0;
    for (i = 1; i < (DWORD)g_nbl; i++) {
        char *l = g_bl[i], *k, *r;
        if (l[0] != 'F' || l[1] != ' ') continue;
        if (g_nbf) g_bf[g_nbf - 1].l1 = i;
        if (strlen(l) < 2 + 64 + 1) continue;
        memcpy(g_bf[g_nbf].sha, l + 2, 64); g_bf[g_nbf].sha[64] = 0;
        k = l + 2 + 64 + 1;
        r = strchr(k, ' ');
        if (!r) continue;
        g_bf[g_nbf].kind = k[0] == 'i' ? 'i' : k[0] == 'p' ? 'p' : 'f';
        g_bf[g_nbf].rel = r + 1;
        g_bf[g_nbf].l0 = i + 1;
        g_bf[g_nbf].l1 = g_nbl;
        g_nbf++;
    }
    return 1;
}

static U64 hx64(const char *s) { return _strtoui64(s, NULL, 16); }

/* base view of one text record: lines [l0, l1) of g_bl that are L / C */
typedef struct { U64 skey, val, whole; } BEnt;
typedef struct { BEnt *e; int n; int count; int has_count; } BText;
static void btext_of(int l0, int l1, BText *t) {
    int i, n = 0;
    t->e = NULL; t->n = 0; t->count = 0; t->has_count = 0;
    for (i = l0; i < l1 && (g_bl[i][0] == 'L' || g_bl[i][0] == 'C'); i++) if (g_bl[i][0] == 'L') n++;
    t->e = (BEnt *)malloc((n + 1) * sizeof(BEnt));
    for (i = l0; i < l1 && t->e; i++) {
        char *l = g_bl[i];
        if (l[0] == 'L' && strlen(l) >= 2 + 16 * 3 + 2) {
            t->e[t->n].skey = hx64(l + 2); t->e[t->n].val = hx64(l + 19); t->e[t->n].whole = hx64(l + 36); t->n++;
        } else if (l[0] == 'C') { t->count = atoi(l + 2); t->has_count = 1; }
        else break;
    }
}

/* ---------------------------------------------------------------- text records */
typedef struct { const BYTE *p; DWORD n; } OLine;
typedef struct { OLine *l; int n, cap; } OLines;
static void ol_add(OLines *v, const BYTE *p, DWORD n) {
    if (v->n == v->cap) {
        int c = v->cap ? v->cap * 2 : 64;
        OLine *q = (OLine *)realloc(v->l, c * sizeof(OLine));
        if (!q) return;
        v->l = q; v->cap = c;
    }
    v->l[v->n].p = p; v->l[v->n].n = n; v->n++;
}
static void ol_split(OLines *v, const BYTE *p, DWORD n) {       /* IXF text payload -> lines */
    DWORD s = 0, i;
    for (i = 0; i <= n; i++) {
        if (i == n || p[i] == '\n') {
            DWORD e = i;
            if (i == n && s == n) break;                    /* final empty piece */
            if (e > s && p[e - 1] == '\r') e--;
            ol_add(v, p + s, e - s);
            s = i + 1;
        }
    }
}

typedef struct { U64 skey, val, whole, sec; int line, kind; } KEnt;     /* kind 1 keyed */
static int is_sp(BYTE c) { return c == ' ' || c == '\t'; }
static void trim(const BYTE **p, DWORD *n) {
    while (*n && is_sp((*p)[0])) { (*p)++; (*n)--; }
    while (*n && is_sp((*p)[*n - 1])) (*n)--;
}
static U64 fnv_lower(U64 h, const BYTE *p, DWORD n) {
    DWORD i;
    for (i = 0; i < n; i++) { BYTE c = p[i]; if (c >= 'A' && c <= 'Z') c += 32; h ^= c; h *= 0x100000001B3ui64; }
    return h;
}
/* keyed entries of lines; sections hashed so a missing one can be found */
typedef struct { KEnt *e; int n; } KList;
static void klist_of(const OLines *v, KList *k, U64 *secs /* per line: section hash */) {
    int i;
    const BYTE *sp = (const BYTE *)""; DWORD sn = 0;
    BYTE lowsec[512];
    k->e = (KEnt *)malloc((v->n + 1) * sizeof(KEnt)); k->n = 0;
    for (i = 0; i < v->n; i++) {
        const BYTE *s = v->l[i].p; DWORD n = v->l[i].n, j, sep = (DWORD)-1;
        trim(&s, &n);
        if (n >= 2 && s[0] == '[' && s[n - 1] == ']') {
            const BYTE *q = s + 1; DWORD qn = n - 2;
            trim(&q, &qn);
            if (qn > sizeof(lowsec)) qn = sizeof(lowsec);
            for (j = 0; j < qn; j++) lowsec[j] = (q[j] >= 'A' && q[j] <= 'Z') ? q[j] + 32 : q[j];
            sp = lowsec; sn = qn;
            if (secs) secs[i] = fnv_add(FNV0, sp, sn);
            continue;
        }
        if (secs) secs[i] = fnv_add(FNV0, sp, sn);
        if (!k->e || !n || s[0] == ';' || s[0] == '#' || (n >= 2 && s[0] == '/' && s[1] == '/')) continue;
        for (j = 0; j < n; j++) if (s[j] == '=' || s[j] == ':') { sep = j; break; }
        if (sep == (DWORD)-1 || sep == 0) continue;
        {
            const BYTE *kp = s, *vp = s + sep + 1; DWORD kn = sep, vn = n - sep - 1;
            U64 h;
            BYTE us = 0x1F, eq = '=';
            trim(&kp, &kn); trim(&vp, &vn);
            h = fnv_add(FNV0, sp, sn); h = fnv_add(h, &us, 1); h = fnv_lower(h, kp, kn);
            if (kn == 3 && fnv_lower(FNV0, kp, 3) == fnv_add(FNV0, (const BYTE *)"key", 3)) {
                /* BUILDFAM "Key: group,type,id,weight  name": key "key:group,type,id", value "weight  name" */
                DWORD c, commas = 0, digits = 1, run = 0;
                for (c = 0; c < vn && commas < 3; c++) {
                    if (vp[c] == ',') { if (!run) digits = 0; commas++; run = 0; }
                    else if (vp[c] >= '0' && vp[c] <= '9') run++;
                    else digits = 0;
                }
                if (commas == 3 && digits) {
                    BYTE colon = ':';
                    h = fnv_add(h, &colon, 1); h = fnv_add(h, vp, c - 1);
                    vp += c; vn -= c;
                    trim(&vp, &vn);
                }
            }
            k->e[k->n].skey = h;
            k->e[k->n].val = fnv_add(FNV0, vp, vn);
            h = fnv_add(h, &eq, 1); h = fnv_add(h, vp, vn);
            k->e[k->n].whole = h;
            k->e[k->n].sec = fnv_add(FNV0, sp, sn);
            k->e[k->n].line = i;
            k->e[k->n].kind = 1;
            k->n++;
        }
    }
}

static void om_note(const char *rel, const char *what, const BYTE *p, DWORD n) {
    char t[128];
    DWORD m = n < 100 ? n : 100, i;
    if (g_om_detail++ >= OM_DETAIL_MAX) return;
    for (i = 0; i < m; i++) t[i] = (p[i] >= 32 && p[i] < 127) ? p[i] : '?';
    t[m] = 0;
    logf("ovmerge:   %s: %s \"%s%s\"", rel, what, t, n > m ? "..." : "");
}

static U64 g_bc_skey;   /* skey of "<no section> 0x1F buildingcount" (BUILDFAM): merged as a count */

typedef struct { char **p; int n, cap; } OAlloc;    /* texts and payloads made by a merge, freed after the write */
static void *oa_keep(OAlloc *a, void *s) {
    if (!s) return NULL;
    if (a->n == a->cap) {
        int c = a->cap ? a->cap * 2 : 16;
        char **q = (char **)realloc(a->p, c * sizeof(char *));
        if (!q) { free(s); return NULL; }
        a->p = q; a->cap = c;
    }
    a->p[a->n++] = (char *)s;
    return s;
}
static void oa_free(OAlloc *a) { int i; for (i = 0; i < a->n; i++) free(a->p[i]); free(a->p); a->p = NULL; a->n = a->cap = 0; }

typedef struct { int changed, conflicts, added, replaced, removed; } OmStat;

static int dup_in(U64 skey, const U64 *s, int n) {
    int i, c = 0;
    for (i = 0; i < n; i++) if (s[i] == skey && ++c > 1) return 1;
    return 0;
}
static int find_id(const U64 *id, int n, U64 want, const int *skip) {
    int i;
    for (i = 0; i < n; i++) if (id[i] == want && !(skip && skip[i])) return i;
    return -1;
}

/* Three-way merge of one text record: b = stock (hashes), o = ours, p = theirs -> `out` lines (pointing into o, p or
   texts kept in `al`). Returns 1 when out differs from o. */
static int text_merge(const char *rel, const BText *b, const OLines *o, const OLines *p, OLines *out, OAlloc *al,
                      OmStat *st) {
    KList ko = { 0 }, kp = { 0 };
    U64 *osec = NULL, *psec = NULL, *bs = NULL, *os = NULL, *ps = NULL, *bi = NULL, *bv = NULL, *oi = NULL, *ov = NULL,
        *pi = NULL, *pv = NULL;
    int *odel = NULL, *ins_n = NULL, **ins = NULL, *ins_end = NULL, *pent = NULL, *bseen = NULL, *rep = NULL;
    const char **rept = NULL;
    int i, j, nb = b->n, ins_end_n = 0, changed = 0, pcount = -1, ocount = -1, ocount_line = -1;

    osec = (U64 *)calloc(o->n + 1, sizeof(U64)); psec = (U64 *)calloc(p->n + 1, sizeof(U64));
    klist_of(o, &ko, osec); klist_of(p, &kp, psec);
    bs = (U64 *)malloc((nb + 1) * 8); bi = (U64 *)malloc((nb + 1) * 8); bv = (U64 *)malloc((nb + 1) * 8);
    os = (U64 *)malloc((ko.n + 1) * 8); oi = (U64 *)malloc((ko.n + 1) * 8); ov = (U64 *)malloc((ko.n + 1) * 8);
    ps = (U64 *)malloc((kp.n + 1) * 8); pi = (U64 *)malloc((kp.n + 1) * 8); pv = (U64 *)malloc((kp.n + 1) * 8);
    odel = (int *)calloc(ko.n + 1, sizeof(int)); bseen = (int *)calloc(nb + 1, sizeof(int));
    rep = (int *)malloc((o->n + 1) * sizeof(int)); rept = (const char **)calloc(o->n + 1, sizeof(char *));
    ins_n = (int *)calloc(o->n + 1, sizeof(int)); ins = (int **)calloc(o->n + 1, sizeof(int *));
    ins_end = (int *)malloc((p->n + 1) * sizeof(int)); pent = (int *)malloc((p->n + 1) * sizeof(int));
    if (!osec || !psec || !ko.e || !kp.e || !bs || !bi || !bv || !os || !oi || !ov || !ps || !pi || !pv || !odel || !bseen
        || !rep || !rept || !ins_n || !ins || !ins_end || !pent) { st->conflicts++; logf("### ovmerge: %s: out of memory", rel); goto done; }
    for (i = 0; i < nb; i++) bs[i] = b->e[i].skey;
    for (i = 0; i < ko.n; i++) os[i] = ko.e[i].skey;
    for (i = 0; i < kp.n; i++) ps[i] = kp.e[i].skey;
#define LISTKEY(sk) (dup_in((sk), bs, nb) || dup_in((sk), os, ko.n) || dup_in((sk), ps, kp.n))
    for (i = 0; i < nb; i++) { int l = LISTKEY(bs[i]); bi[i] = l ? b->e[i].whole : b->e[i].skey; bv[i] = l ? 0 : b->e[i].val; }
    for (i = 0; i < ko.n; i++) { int l = LISTKEY(os[i]); oi[i] = l ? ko.e[i].whole : ko.e[i].skey; ov[i] = l ? 0 : ko.e[i].val; }
    for (i = 0; i < kp.n; i++) { int l = LISTKEY(ps[i]); pi[i] = l ? kp.e[i].whole : kp.e[i].skey; pv[i] = l ? 0 : kp.e[i].val; }
#undef LISTKEY
    for (i = 0; i < o->n; i++) rep[i] = -1;
    for (i = 0; i < p->n; i++) pent[i] = -1;
    for (i = 0; i < kp.n; i++) pent[kp.e[i].line] = i;

    for (i = 0; i < kp.n + nb; i++) {
        int ib, io, ip, pl = -1, ol;
        U64 id;
        if (i < kp.n) {
            ip = i;
            if (ps[ip] == g_bc_skey) {
                const BYTE *q = (const BYTE *)memchr(p->l[kp.e[ip].line].p, ':', p->l[kp.e[ip].line].n);
                if (q) pcount = atoi((const char *)q + 1);
                continue;
            }
            id = pi[ip]; pl = kp.e[ip].line;
            ib = find_id(bi, nb, id, bseen);
            if (ib >= 0) bseen[ib] = 1;
        } else {
            ib = i - kp.n;
            if (bseen[ib] || bs[ib] == g_bc_skey) continue;
            ip = -1; id = bi[ib];
        }
        io = find_id(oi, ko.n, id, odel);
        ol = io >= 0 ? ko.e[io].line : -1;
        if ((ip >= 0) == (ib >= 0) && (ip < 0 || pv[ip] == bv[ib])) continue;              /* theirs did not change it */
        if ((io >= 0) == (ib >= 0) && (io < 0 || ov[io] == bv[ib])) {                      /* ours did not: take theirs */
            if (ip < 0) { odel[io] = 1; rep[ol] = -3; st->removed++; om_note(rel, "line removed", o->l[ol].p, o->l[ol].n); }
            else if (io >= 0) { rep[ol] = pl; st->replaced++; om_note(rel, "line changed", p->l[pl].p, p->l[pl].n); }
            else {
                /* new line: after the nearest earlier line of theirs (same section) that ours has */
                int a = -1, k2;
                for (k2 = pl - 1; k2 >= 0 && a < 0; k2--) {
                    int e = pent[k2], x;
                    if (psec[k2] != psec[pl]) break;
                    if (e < 0) continue;
                    x = find_id(oi, ko.n, pi[e], odel);
                    if (x >= 0) a = ko.e[x].line;
                }
                if (a < 0) {                       /* first of its section: after ours' header of that section */
                    for (k2 = 0; k2 < o->n; k2++) {
                        const BYTE *s = o->l[k2].p; DWORD n = o->l[k2].n;
                        trim(&s, &n);
                        if (n >= 2 && s[0] == '[' && osec[k2] == psec[pl]) { a = k2; break; }
                    }
                    if (a < 0 && psec[pl] == FNV0 && o->n) a = ko.n ? ko.e[ko.n - 1].line : o->n - 1;
                }
                if (a >= 0) {
                    int *q = (int *)realloc(ins[a], (ins_n[a] + 1) * sizeof(int));
                    if (q) { ins[a] = q; q[ins_n[a]++] = pl; }
                } else ins_end[ins_end_n++] = pl;
                st->added++;
                om_note(rel, "line added", p->l[pl].p, p->l[pl].n);
            }
            changed = 1;
            continue;
        }
        if ((io >= 0) == (ip >= 0) && (io < 0 || ov[io] == pv[ip])) continue;            /* both made the same change */
        st->conflicts++;
        if (pl >= 0) om_note(rel, "### conflict, ours kept; theirs", p->l[pl].p, p->l[pl].n);
        else if (ol >= 0) om_note(rel, "### conflict (theirs removed the line, ours changed it), ours kept", o->l[ol].p, o->l[ol].n);
    }

    /* BuildingCount: ours + (theirs - stock) */
    for (j = 0; j < ko.n; j++) if (os[j] == g_bc_skey) {
        const BYTE *q = (const BYTE *)memchr(o->l[ko.e[j].line].p, ':', o->l[ko.e[j].line].n);
        ocount_line = ko.e[j].line;
        ocount = q ? atoi((const char *)q + 1) : -1;
        break;
    }
    if (b->has_count && pcount >= 0 && ocount >= 0 && pcount != b->count) {
        int nc = ocount + (pcount - b->count);
        char *t = (char *)oa_keep(al, malloc(48));
        if (nc < 0) nc = 0;
        if (t) {
            _snprintf(t, 48, "BuildingCount: %d", nc); t[47] = 0;
            rep[ocount_line] = -2; rept[ocount_line] = t;
            logf("ovmerge:   %s: BuildingCount %d -> %d (theirs %d, stock %d)", rel, ocount, nc, pcount, b->count);
            changed = 1;
        }
    }

    for (i = 0; i < o->n; i++) {
        if (rep[i] >= 0) ol_add(out, p->l[rep[i]].p, p->l[rep[i]].n);
        else if (rep[i] == -2) ol_add(out, (const BYTE *)rept[i], (DWORD)strlen(rept[i]));
        else if (rep[i] == -1) ol_add(out, o->l[i].p, o->l[i].n);
        for (j = 0; j < ins_n[i]; j++) ol_add(out, p->l[ins[i][j]].p, p->l[ins[i][j]].n);
    }
    {
        U64 lastsec = 0; int any = 0;
        for (j = 0; j < ins_end_n; j++) {
            int pl = ins_end[j];
            if (!any || psec[pl] != lastsec) {      /* a section ours lacks: its header from theirs */
                int k2;
                for (k2 = pl - 1; k2 >= 0; k2--) {
                    const BYTE *s = p->l[k2].p; DWORD n = p->l[k2].n;
                    trim(&s, &n);
                    if (n >= 2 && s[0] == '[') { ol_add(out, p->l[k2].p, p->l[k2].n); break; }
                }
                lastsec = psec[pl]; any = 1;
            }
            ol_add(out, p->l[pl].p, p->l[pl].n);
        }
    }
done:
    if (ins) for (i = 0; i < o->n; i++) free(ins[i]);
    free(ko.e); free(kp.e); free(osec); free(psec); free(bs); free(bi); free(bv); free(os); free(oi); free(ov); free(ps);
    free(pi); free(pv); free(odel); free(bseen); free(rep); free((void *)rept); free(ins_n); free(ins); free(ins_end); free(pent);
    if (changed) st->changed++;
    return changed;
}

static int is_text_payload(const BYTE *p, DWORD n) { return n >= 4 && !memcmp(p, "TXT!", 4); }

/* ---------------------------------------------------------------- IXF */
typedef struct { DWORD g, i, t; const BYTE *p; DWORD n; int del; } IRec;
typedef struct { IRec *r; int n, cap; DWORD slots; } IxfV;
static int irec_add(IxfV *v, DWORD g, DWORD i, DWORD t, const BYTE *p, DWORD n) {
    if (v->n == v->cap) {
        int c = v->cap ? v->cap * 2 : 256;
        IRec *q = (IRec *)realloc(v->r, c * sizeof(IRec));
        if (!q) return 0;
        v->r = q; v->cap = c;
    }
    v->r[v->n].g = g; v->r[v->n].i = i; v->r[v->n].t = t; v->r[v->n].p = p; v->r[v->n].n = n; v->r[v->n].del = 0;
    v->n++;
    return 1;
}
static int ixf_parse(const BYTE *d, DWORD n, IxfV *v) {
    DWORD k, minoff = n;
    memset(v, 0, sizeof(*v));
    if (n < 4 || *(const DWORD *)d != 0x80C381D7) return 0;
    for (k = 0; 4 + (k + 1) * 20 <= n; k++) {
        const DWORD *s = (const DWORD *)(d + 4 + k * 20);
        if (!s[0] && !s[1] && !s[2]) break;
        if (s[3] == 0xFFFFFFFF || s[4] == 0xFFFFFFFF) continue;
        if (s[3] > n || s[4] > n - s[3]) return 0;
        if (!irec_add(v, s[0], s[1], s[2], d + s[3], s[4])) return 0;
        if (s[3] < minoff) minoff = s[3];
    }
    v->slots = minoff > 4 ? (minoff - 4) / 20 : 0;
    return 1;
}
static int irec_find(const IxfV *v, DWORD g, DWORD i, DWORD t) {
    int k;
    for (k = 0; k < v->n; k++) if (!v->r[k].del && v->r[k].g == g && v->r[k].i == i && v->r[k].t == t) return k;
    return -1;
}
static BYTE *ixf_build(const IxfV *v, DWORD *outn) {
    OBuf o = { 0 };
    DWORD live = 0, slots, k, off;
    int i;
    for (i = 0; i < v->n; i++) if (!v->r[i].del) live++;
    slots = v->slots > live + 1 ? v->slots : live + 1;
    ob_u32(&o, 0x80C381D7);
    off = 4 + slots * 20;
    for (i = 0; i < v->n; i++) {
        if (v->r[i].del) continue;
        ob_u32(&o, v->r[i].g); ob_u32(&o, v->r[i].i); ob_u32(&o, v->r[i].t); ob_u32(&o, off); ob_u32(&o, v->r[i].n);
        off += v->r[i].n;
    }
    for (k = live; k < slots; k++) { DWORD z[5] = { 0, 0, 0, 0, 0 }; ob_put(&o, z, 20); }
    for (i = 0; i < v->n; i++) if (!v->r[i].del) ob_put(&o, v->r[i].p, v->r[i].n);
    if (o.bad) { free(o.p); return NULL; }
    *outn = o.n;
    return o.p;
}

typedef struct { DWORD g, i, t; U64 h; int l0, l1; } BRec;   /* base record + its L/C line range */

static BYTE *join_lines(const OLines *v, int crlf, int trailing, DWORD *n) {
    OBuf o = { 0 };
    int i;
    for (i = 0; i < v->n; i++) {
        ob_put(&o, v->l[i].p, v->l[i].n);
        if (i + 1 < v->n || trailing) ob_put(&o, crlf ? "\r\n" : "\n", crlf ? 2 : 1);
    }
    if (o.bad) { free(o.p); return NULL; }
    if (!o.p) { o.p = (BYTE *)malloc(1); o.n = 0; }
    *n = o.n;
    return o.p;
}

/* -> merged IXF (malloc) or NULL = serve ours unchanged */
static BYTE *ixf_merge(const char *rel, const OmFile *f, const BYTE *od, DWORD on, const BYTE *pd, DWORD pn, DWORD *outn,
                       OmStat *st, OAlloc *al) {
    IxfV O, P;
    BRec *br;
    int nbr = 0, l, k, changed = 0;
    BYTE *res = NULL;
    if (!ixf_parse(od, on, &O)) { logf("### ovmerge: %s: the overlay copy is not an IXF", rel); st->conflicts++; free(O.r); return NULL; }
    if (!ixf_parse(pd, pn, &P)) { logf("### ovmerge: %s: the game copy is not an IXF, not merged", rel); st->conflicts++; free(O.r); free(P.r); return NULL; }
    br = (BRec *)malloc((f->l1 - f->l0 + 1) * sizeof(BRec));
    if (!br) { free(O.r); free(P.r); st->conflicts++; return NULL; }
    for (l = f->l0; l < f->l1; l++) {
        const char *s = g_bl[l];
        if (s[0] == 'R' && strlen(s) >= 2 + 9 * 3 + 16) {
            if (nbr) br[nbr - 1].l1 = l;
            br[nbr].g = strtoul(s + 2, NULL, 16); br[nbr].i = strtoul(s + 11, NULL, 16); br[nbr].t = strtoul(s + 20, NULL, 16);
            br[nbr].h = hx64(s + 29); br[nbr].l0 = l + 1; br[nbr].l1 = f->l1;
            nbr++;
        }
    }
    {
        int *bseen = (int *)calloc(nbr + 1, sizeof(int));
        if (!bseen) { free(br); free(O.r); free(P.r); st->conflicts++; return NULL; }
        for (k = 0; k < P.n + nbr; k++) {
            const IRec *pr = k < P.n ? &P.r[k] : NULL;
            int ib = -1, io, j;
            DWORD g, i, t;
            U64 hp = 0, ho = 0;
            if (pr) {
                g = pr->g; i = pr->i; t = pr->t;
                hp = fnv_add(FNV0, pr->p, pr->n);
                for (j = 0; j < nbr; j++) if (!bseen[j] && br[j].g == g && br[j].i == i && br[j].t == t) { ib = j; bseen[j] = 1; break; }
                if (ib >= 0 && br[ib].h == hp) continue;                          /* theirs = stock */
            } else {
                ib = k - P.n;
                if (bseen[ib]) continue;
                g = br[ib].g; i = br[ib].i; t = br[ib].t;
            }
            io = irec_find(&O, g, i, t);
            if (io >= 0) ho = fnv_add(FNV0, O.r[io].p, O.r[io].n);
            if (pr && io >= 0 && ho == hp) continue;                              /* both the same */
            if (!pr) {                                                            /* theirs removed a stock record */
                if (io >= 0 && ho == br[ib].h) { O.r[io].del = 1; st->removed++; changed = 1;
                    logf("ovmerge:   %s: record %08lX/%08lX/%08lX removed (as theirs)", rel, g, i, t); }
                else if (io >= 0) { st->conflicts++; logf("ovmerge:   %s: ### record %08lX/%08lX/%08lX: theirs removed it, ours changed it - ours kept", rel, g, i, t); }
                continue;
            }
            if (io < 0 && ib < 0) {                                               /* theirs added it */
                if (irec_add(&O, g, i, t, pr->p, pr->n)) { st->added++; changed = 1;
                    logf("ovmerge:   %s: record %08lX/%08lX/%08lX added (%lu bytes)", rel, g, i, t, pr->n); }
                continue;
            }
            if (io >= 0 && ib >= 0 && ho == br[ib].h) {                           /* only theirs changed it */
                O.r[io].p = pr->p; O.r[io].n = pr->n; st->replaced++; changed = 1;
                logf("ovmerge:   %s: record %08lX/%08lX/%08lX taken from theirs (%lu bytes)", rel, g, i, t, pr->n);
                continue;
            }
            if (io >= 0 && is_text_payload(O.r[io].p, O.r[io].n) && is_text_payload(pr->p, pr->n)) {
                OLines lo = { 0 }, lp = { 0 }, out = { 0 };
                BText bt = { 0 };
                if (ib >= 0) btext_of(br[ib].l0, br[ib].l1, &bt);
                ol_split(&lo, O.r[io].p, O.r[io].n); ol_split(&lp, pr->p, pr->n);
                logf("ovmerge:   %s: record %08lX/%08lX/%08lX changed on both sides - merging its lines", rel, g, i, t);
                if (text_merge(rel, &bt, &lo, &lp, &out, al, st)) {
                    DWORD nn;
                    BYTE *np = join_lines(&out, 1, O.r[io].n && O.r[io].p[O.r[io].n - 1] == '\n', &nn);
                    if (oa_keep(al, np)) { O.r[io].p = np; O.r[io].n = nn; changed = 1; }
                }
                free(lo.l); free(lp.l); free(out.l); free(bt.e);
                continue;
            }
            st->conflicts++;
            logf("ovmerge:   %s: ### record %08lX/%08lX/%08lX changed on both sides (binary) - ours kept", rel, g, i, t);
        }
        free(bseen);
    }
    if (changed) res = ixf_build(&O, outn);
    free(br); free(O.r); free(P.r);
    return res;
}

/* ---------------------------------------------------------------- SYS.PAK */
typedef struct { char name[132]; OLines lines; int del; } PMem;
typedef struct { PMem *m; int n, cap; } PakV;
static PMem *pmem_add(PakV *v) {
    if (v->n == v->cap) {
        int c = v->cap ? v->cap * 2 : 64;
        PMem *q = (PMem *)realloc(v->m, c * sizeof(PMem));
        if (!q) return NULL;
        v->m = q; v->cap = c;
    }
    memset(&v->m[v->n], 0, sizeof(PMem));
    return &v->m[v->n++];
}
static void pak_free(PakV *v) { int i; for (i = 0; i < v->n; i++) free(v->m[i].lines.l); free(v->m); memset(v, 0, sizeof(*v)); }
static int pak_parse(const BYTE *d, DWORD n, PakV *v) {
    DWORD off = 0, k;
    memset(v, 0, sizeof(*v));
    while (off + 8 <= n) {
        DWORD nl = *(const DWORD *)(d + off + 4), j;
        PMem *m;
        if (nl == 0 || nl > 128 || off + 8 + nl > n) break;
        for (j = 0; j < nl; j++) if (d[off + 8 + j] < 32 || d[off + 8 + j] >= 127) break;
        if (j < nl) break;
        if (!(m = pmem_add(v))) return 0;
        memcpy(m->name, d + off + 8, nl); m->name[nl] = 0;
        off += 8 + nl;
    }
    if (!v->n || off + 4 > n) return 0;
    off += 4;
    for (k = 0; k < (DWORD)v->n; k++) {
        DWORD lc, j;
        if (off + 4 > n) return 0;
        lc = *(const DWORD *)(d + off); off += 4;
        for (j = 0; j < lc; j++) {
            DWORD ln;
            if (off + 4 > n) return 0;
            ln = *(const DWORD *)(d + off); off += 4;
            if (ln > n - off) return 0;
            ol_add(&v->m[k].lines, d + off, ln);
            off += ln;
        }
    }
    return off == n;
}
static U64 pmem_hash(const PMem *m) {
    U64 h = FNV0;
    int i;
    BYTE lf = '\n';
    for (i = 0; i < m->lines.n; i++) { if (i) h = fnv_add(h, &lf, 1); h = fnv_add(h, m->lines.l[i].p, m->lines.l[i].n); }
    return h;
}
static BYTE *pak_build(const PakV *v, DWORD *outn) {
    OBuf o = { 0 };
    DWORD *starts, toc = 0, pos;
    int i, j, live = 0, prev = -1;
    for (i = 0; i < v->n; i++) if (!v->m[i].del) { live++; toc += 8 + (DWORD)strlen(v->m[i].name); }
    starts = (DWORD *)malloc((v->n + 1) * sizeof(DWORD));
    if (!starts || !live) { free(starts); return NULL; }
    pos = toc + 4;
    for (i = 0; i < v->n; i++) {
        if (v->m[i].del) continue;
        starts[i] = pos;
        pos += 4;
        for (j = 0; j < v->m[i].lines.n; j++) pos += 4 + v->m[i].lines.l[j].n;
    }
    for (i = 0; i < v->n; i++) {                                   /* entry k holds the start of record k-1, entry 0 the
                                                                      count (syspak_parse.build) */
        DWORD nl;
        if (v->m[i].del) continue;
        nl = (DWORD)strlen(v->m[i].name);
        ob_u32(&o, prev < 0 ? (DWORD)live : starts[prev]);
        ob_u32(&o, nl); ob_put(&o, v->m[i].name, nl);
        prev = i;
    }
    ob_u32(&o, starts[prev]);
    for (i = 0; i < v->n; i++) {
        if (v->m[i].del) continue;
        ob_u32(&o, (DWORD)v->m[i].lines.n);
        for (j = 0; j < v->m[i].lines.n; j++) { ob_u32(&o, v->m[i].lines.l[j].n); ob_put(&o, v->m[i].lines.l[j].p, v->m[i].lines.l[j].n); }
    }
    free(starts);
    if (o.bad) { free(o.p); return NULL; }
    *outn = o.n;
    return o.p;
}

typedef struct { const char *name; U64 h; int l0, l1; } BMem;
static BYTE *pak_merge(const char *rel, const OmFile *f, const BYTE *od, DWORD on, const BYTE *pd, DWORD pn, DWORD *outn,
                       OmStat *st, OAlloc *al) {
    PakV O, P;
    BMem *bm;
    int nbm = 0, l, k, changed = 0, *bseen;
    BYTE *res = NULL;
    if (!pak_parse(od, on, &O)) { logf("### ovmerge: %s: the overlay copy does not parse as SYS.PAK", rel); st->conflicts++; pak_free(&O); return NULL; }
    if (!pak_parse(pd, pn, &P)) { logf("### ovmerge: %s: the game copy does not parse as SYS.PAK, not merged", rel); st->conflicts++; pak_free(&O); pak_free(&P); return NULL; }
    bm = (BMem *)malloc((f->l1 - f->l0 + 1) * sizeof(BMem));
    bseen = (int *)calloc(f->l1 - f->l0 + 1, sizeof(int));
    if (!bm || !bseen) { free(bm); free(bseen); pak_free(&O); pak_free(&P); st->conflicts++; return NULL; }
    for (l = f->l0; l < f->l1; l++) {
        const char *s = g_bl[l];
        if (s[0] == 'M' && strlen(s) >= 2 + 16 + 2) {
            if (nbm) bm[nbm - 1].l1 = l;
            bm[nbm].h = hx64(s + 2); bm[nbm].name = s + 19; bm[nbm].l0 = l + 1; bm[nbm].l1 = f->l1;
            nbm++;
        }
    }
    for (k = 0; k < P.n + nbm; k++) {
        PMem *pm = k < P.n ? &P.m[k] : NULL;
        const char *name;
        int ib = -1, io = -1, j;
        U64 hp = 0, ho = 0;
        if (pm) {
            name = pm->name;
            hp = pmem_hash(pm);
            for (j = 0; j < nbm; j++) if (!bseen[j] && !lstrcmpiA(bm[j].name, name)) { ib = j; bseen[j] = 1; break; }
            if (ib >= 0 && bm[ib].h == hp) continue;
        } else {
            ib = k - P.n;
            if (bseen[ib]) continue;
            name = bm[ib].name;
        }
        for (j = 0; j < O.n; j++) if (!O.m[j].del && !lstrcmpiA(O.m[j].name, name)) { io = j; break; }
        if (io >= 0) ho = pmem_hash(&O.m[io]);
        if (pm && io >= 0 && ho == hp) continue;
        if (!pm) {
            if (io >= 0 && ho == bm[ib].h) { O.m[io].del = 1; st->removed++; changed = 1; logf("ovmerge:   %s: member %s removed (as theirs)", rel, name); }
            else if (io >= 0) { st->conflicts++; logf("ovmerge:   %s: ### member %s: theirs removed it, ours changed it - ours kept", rel, name); }
            continue;
        }
        if (io < 0 && ib < 0) {
            PMem *nm = pmem_add(&O);
            if (nm) {
                lstrcpynA(nm->name, name, sizeof(nm->name));
                for (j = 0; j < pm->lines.n; j++) ol_add(&nm->lines, pm->lines.l[j].p, pm->lines.l[j].n);
                st->added++; changed = 1; logf("ovmerge:   %s: member %s added (%d lines)", rel, name, pm->lines.n);
            }
            continue;
        }
        if (io >= 0 && ib >= 0 && ho == bm[ib].h) {
            O.m[io].lines.n = 0;
            for (j = 0; j < pm->lines.n; j++) ol_add(&O.m[io].lines, pm->lines.l[j].p, pm->lines.l[j].n);
            st->replaced++; changed = 1; logf("ovmerge:   %s: member %s taken from theirs (%d lines)", rel, name, pm->lines.n);
            continue;
        }
        if (io >= 0) {
            OLines out = { 0 };
            BText bt = { 0 };
            char who[200];
            if (ib >= 0) btext_of(bm[ib].l0, bm[ib].l1, &bt);
            _snprintf(who, sizeof(who), "%s %s", rel, name); who[sizeof(who) - 1] = 0;
            logf("ovmerge:   %s: member %s changed on both sides - merging its lines", rel, name);
            if (text_merge(who, &bt, &O.m[io].lines, &pm->lines, &out, al, st)) {
                free(O.m[io].lines.l);
                O.m[io].lines = out;
                changed = 1;
            } else free(out.l);
            free(bt.e);
            continue;
        }
        st->conflicts++;
        logf("ovmerge:   %s: ### member %s: ours removed it, theirs changed it - not served", rel, name);
    }
    if (changed) res = pak_build(&O, outn);
    free(bm); free(bseen); pak_free(&O); pak_free(&P);
    return res;
}

/* ---------------------------------------------------------------- driver */
static void om_sweep(const char *tmp) {          /* delete merge folders whose process is gone */
    char pat[MAX_PATH], d[MAX_PATH], f[MAX_PATH], sub[MAX_PATH];
    WIN32_FIND_DATAA fd, fd2;
    HANDLE h, h2, p;
    DWORD pid;
    _snprintf(pat, sizeof(pat), "%ssc3netmod_merge_*", tmp); pat[sizeof(pat) - 1] = 0;
    h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        pid = strtoul(fd.cFileName + 16, NULL, 10);
        if (pid == GetCurrentProcessId()) continue;
        p = pid ? OpenProcess(SYNCHRONIZE, FALSE, pid) : NULL;
        if (p && WaitForSingleObject(p, 0) == WAIT_TIMEOUT) { CloseHandle(p); continue; }
        if (p) CloseHandle(p);
        _snprintf(d, sizeof(d), "%s%s\\", tmp, fd.cFileName); d[sizeof(d) - 1] = 0;
        _snprintf(sub, sizeof(sub), "%s*", d); sub[sizeof(sub) - 1] = 0;
        h2 = FindFirstFileA(sub, &fd2);
        if (h2 != INVALID_HANDLE_VALUE) {
            do {
                if (fd2.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
                _snprintf(f, sizeof(f), "%s%s", d, fd2.cFileName); f[sizeof(f) - 1] = 0;
                DeleteFileA(f);
            } while (FindNextFileA(h2, &fd2));
            FindClose(h2);
        }
        RemoveDirectoryA(d);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

static void om_unmerged(const char *rel) {
    const char *b = strrchr(rel, '\\');
    b = b ? b + 1 : rel;
    InterlockedIncrement(&g_om_unmerged);
    if (strlen(g_om_names) + strlen(b) + 3 < sizeof(g_om_names)) {
        if (g_om_names[0]) lstrcatA(g_om_names, ", ");
        lstrcatA(g_om_names, b);
    }
}

/* OVSTALE (task crash1127, 2026-11-27): an overlay file that shadows a game file but is not in overlay_base.txt did
 * not come from the overlay build that wrote that list (the release and netpack.py install both rebuild it with every
 * shadowing file). It is left over from an older release: the LAN updater deletes only with -Prune, unzipping never
 * deletes. Owner MARIANO-PC 11-27: the avenue_markings reskin Apps\Res\Sprites\CSATTRIB.IXF, removed in 11-09, still
 * pointed stock piece 11204's 40 frames at 4E3D0033_netpack.DAT instances that later builds no longer hold, so any
 * city with 11204 died at its first sprite insert (SIMSPR+0x15B9, image ref +8 = 0). Such a file is dropped from the
 * served set and named in the log. SC3NETMOD_OVSTALE=0 serves it anyway. */
static int g_ovstale_n;
static char g_ovstale_names[256];
static void ovstale_drop(void) {
    char path[MAX_PATH];
    int i, k, w = 0;
    DWORD a;
    if (env_off("SC3NETMOD_OVSTALE")) { logf("ovstale: off (SC3NETMOD_OVSTALE=0) - every overlay file is served"); return; }
    for (i = 0; i < g_novfiles; i++) {
        const char *rel = g_ovfiles[i];
        int listed = 0;
        for (k = 0; k < g_nbf; k++) if (g_bf[k].rel && !lstrcmpiA(g_bf[k].rel, rel)) { listed = 1; break; }
        if (!listed) {
            _snprintf(path, sizeof(path), "%s%s", g_root, rel); path[sizeof(path) - 1] = 0;
            a = GetFileAttributesA(path);
            if (a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY)) {
                const char *b = strrchr(rel, '\\');
                b = b ? b + 1 : rel;
                logf("### ovstale: %s%s shadows the game's %s but overlay_base.txt does not list it: left over from an "
                     "older release, NOT served (delete it, or run update.bat -Prune)", g_ovdir, rel, rel);
                if (strlen(g_ovstale_names) + strlen(b) + 3 < sizeof(g_ovstale_names)) {
                    if (g_ovstale_names[0]) lstrcatA(g_ovstale_names, ", ");
                    lstrcatA(g_ovstale_names, b);
                }
                g_ovstale_n++;
                free(g_ovfiles[i]);
                continue;
            }
        }
        g_ovfiles[w++] = g_ovfiles[i];
    }
    g_novfiles = w;
    logf("ovstale: %d stale overlay file(s) dropped%s%s", g_ovstale_n, g_ovstale_n ? ": " : "", g_ovstale_names);
}

/* after ov_walk, before nomix_init (DllMain: kernel32 + CRT only) */
static void ovmerge_init(void) {
    char base[MAX_PATH], tmp[MAX_PATH], path[MAX_PATH], hex[65];
    int k, i, stock = 0, checked = 0;
    DWORD t0 = GetTickCount(), n;
    static const BYTE bc[] = "\x1f" "buildingcount";
    g_ovalt = (char **)calloc(g_novfiles + 1, sizeof(char *));
    if (!g_ovalt) return;
    if (env_off("SC3NETMOD_OVMERGE")) { logf("ovmerge: off (SC3NETMOD_OVMERGE=0) - the overlay files are served whatever other mods changed"); return; }
    _snprintf(base, sizeof(base), "%smods\\netmod\\overlay_base.txt", g_root); base[sizeof(base) - 1] = 0;
    if (GetFileAttributesA(base) == INVALID_FILE_ATTRIBUTES) {
        logf("ovmerge: no %s - changes other mods make to the files the overlay shadows are not checked", base);
        return;
    }
    if (!om_base_load(base)) { logf("### ovmerge: cannot read %s - not checked", base); return; }
    ovstale_drop();                                          /* before anything indexes g_ovfiles (g_ovalt is all NULL) */
    g_bc_skey = fnv_add(FNV0, bc, sizeof(bc) - 1);
    n = GetTempPathA(sizeof(tmp), tmp);
    if (n && n < sizeof(tmp) - 40) om_sweep(tmp); else tmp[0] = 0;
    for (k = 0; k < g_nbf; k++) {
        const OmFile *f = &g_bf[k];
        BYTE *pd, *od, *res = NULL;
        DWORD pn, on, rn = 0;
        OmStat st;
        OAlloc al = { 0 };
        if (!f->rel) continue;
        for (i = 0; i < g_novfiles; i++) if (!lstrcmpiA(g_ovfiles[i], f->rel)) break;
        if (i == g_novfiles) continue;                       /* the base names a file this overlay no longer holds */
        checked++;
        _snprintf(path, sizeof(path), "%s%s", g_root, f->rel); path[sizeof(path) - 1] = 0;
        pd = om_read(path, &pn);
        if (!pd) { logf("ovmerge: %s missing from the game folder - the overlay copy is served", f->rel); continue; }
        sha256_hex(pd, pn, hex);
        if (!strcmp(hex, f->sha)) { free(pd); stock++; continue; }
        logf("ovmerge: %s is not the stock file (sha256 %.16s, stock %.16s): changed by another mod", f->rel, hex, f->sha);
        if (f->kind == 'f') {
            logf("### ovmerge: %s cannot be merged (plain text rules): the game reads the roads mod's copy, so the other "
                 "mod's change to it is not seen", f->rel);
            om_unmerged(f->rel); free(pd); continue;
        }
        _snprintf(path, sizeof(path), "%s%s", g_ovdir, g_ovfiles[i]); path[sizeof(path) - 1] = 0;
        od = om_read(path, &on);
        if (!od) { logf("### ovmerge: cannot read %s", path); free(pd); continue; }
        memset(&st, 0, sizeof(st));
        g_om_detail = 0;
        res = f->kind == 'i' ? ixf_merge(f->rel, f, od, on, pd, pn, &rn, &st, &al) : pak_merge(f->rel, f, od, on, pd, pn, &rn, &st, &al);
        if (res && tmp[0]) {
            if (!g_om_dir[0]) {
                _snprintf(g_om_dir, sizeof(g_om_dir), "%ssc3netmod_merge_%lu\\", tmp, GetCurrentProcessId());
                g_om_dir[sizeof(g_om_dir) - 1] = 0;
                CreateDirectoryA(g_om_dir, NULL);
            }
            {
                const char *b = strrchr(f->rel, '\\');
                _snprintf(path, sizeof(path), "%s%02d_%s", g_om_dir, k, b ? b + 1 : f->rel); path[sizeof(path) - 1] = 0;
            }
            if (om_write(path, res, rn)) { g_ovalt[i] = _strdup(path); g_om_merged++; }
            else { logf("### ovmerge: cannot write %s (%lu)", path, GetLastError()); st.conflicts++; }
        }
        logf("ovmerge: %s: %d added, %d replaced, %d removed from the other mod's copy, %d conflict(s) kept ours -> %s",
             f->rel, st.added, st.replaced, st.removed, st.conflicts,
             g_ovalt[i] ? g_ovalt[i] : (st.added + st.replaced + st.removed ? "NOT served (write failed)"
                                                                            : "nothing to merge, the overlay copy already has it"));
        if (st.conflicts || (res && !g_ovalt[i])) om_unmerged(f->rel);
        free(res); oa_free(&al); free(pd); free(od);
    }
    logf("ovmerge: %d shadowed file(s) checked in %lu ms: %d stock, %d merged, %ld with a change the game does not see%s%s",
         checked, GetTickCount() - t0, stock, g_om_merged, g_om_unmerged, g_om_names[0] ? ": " : "", g_om_names);
}

/* For sc3perf OVWARN: the number of files with a change the game does not see, their names in `names`. */
__declspec(dllexport) int sc3netmod_ovmerge_status(char *names, int cap) {
    if (names && cap > 0) lstrcpynA(names, g_om_names, cap);
    return (int)g_om_unmerged;
}
