/* ---------------------------------------------------------------- LOTRECT (child lotdraw, round 2026-11-20e)
   Owner 2026-11-20: "True 2x3, patch drawing". A building whose footprint is X x Z with X != Z (prop 0x66 values 1
   and 3) places, saves, moves and bulldozes correctly, but the sprite cell map is square (re/analysis/LOT_SHAPES.md,
   verify/lot2x3/RESULTS.md): InsertCellAlignedSprite (SIMSPR 0x100192aa) reads only SizeInCellsX (0x10019341) and the
   0x14-byte cell record keeps one size byte n (+0xa). A 2x3 drew as 2x2 with its far end cut, a 3x2 claimed a 3x3 block
   (hid a neighbour, left a ghost after a bulldoze).

   Cell record (SIMSPR cell map +0x24 = column pointers, record = col[x] + z * 0x14): +0 sprite, +4/+6 sprite pixel
   top/bottom, +8/+9 registration cell (x0 + n - 1, z0), +0xa n, +0xb altitude, +0xc dynamic sprite list, +0x10 flags
   (ushort), +0x12/+0x13 the registration cell's high bytes when sc3bigcity's ANCHOR16 runs (stock: never touched).
   The record has no free byte, so:
     - flag bit 0x400 of +0x10 marks every cell of a non-square sprite. No SIMSPR instruction sets or tests 0x200 or
       0x400 (flags: bits 0-3 Insert argument, 0x10..0x100 per-zoom "prepared" masks DAT_100624f0, 0x800..0x4000
       corners, 0x8000 visited); Remove / Init / the registration write clear the word.
     - Z sits in a side grid (one byte per cell, keyed by the 16-bit registration cell rec[8] | rec[0x12] << 8,
       rec[9] | rec[0x13] << 8). Without sc3bigcity +0x12/+0x13 stay 0: Remove and Init clear them (their
       `mov word [rec+0x10], 0` becomes a dword store, the same bytes bigcity's own caves clear).
   A record without 0x400 takes the shipped path in every site below, so square buildings read and compute exactly as
   before.

   Sites (verified byte for byte first; nothing is patched unless every site matches; none overlaps a bigcity ANCHOR16
   site and no branch lands inside one):
   A  0x10019341  InsertCellAlignedSprite: X = vt+0xd4, Z = vt+0xd8; the pre-insert removal covers X x Z; the size
                  passed to Insert (both calls, [ebp-0x20]) is X, or X | Z << 8 | 0x5A3C0000 when Z != X.
   B  Insert 0x10007b4d: 0x10007b58 decodes the size (the size byte stays X; Z - 1, marker, longest side, X go to the
                  unused high bytes of the altitude / flag arguments [ebp+0x15..0x17], [ebp+0x1d]); z loop bound
                  0x10007c52 and +z corners 0x10007d02 use Z; multi-cell flag 2 test 0x10007c9d reads the longest side;
                  0x10007d27 (after the corners, before the bucket registration 0x10007da5 and the dirty rect
                  0x10007dbe) sets 0x400 on the X x Z cells and stores Z in the side grid.
   C  Remove 0x10007fea, Init 0x10005ed9: dword clear of +0x10..+0x13.
   D  0x1000c678 (registration view cell for the draw lists) and 0x1000f6f4 (the same for pick, pixel rect, highzoom)
                  replaced by C copies with 16-bit anchors: per view rotation the left vertex of the X x Z lot.
                  r1 vz += 1 - X, r2 vx += X - 1 and vz += 1 - Z, r3 vx += Z - 1 (stock: n everywhere).
   E  display-list depth boxes, z end = z0 + Z: lowzoom 0x1000c15d, highzoom 0x1000d64c.
   K  display-list sort key (+0x14 = -(vx + vz) * 0x4000 - (alt >> 2) * 0x100 + 0x3fffc000 of the registration view
                  cell; the comparator 0x1000c7a6 orders two cell sprites by it alone). For a square that cell is the
                  block's centre depth; for an A x B view block (A = vx extent, B = vz extent) the centre is (B - A) / 2
                  cells further, so 0x400 records get key - (B - A) * 0x2000: lowzoom 0x1000c14b, highzoom 0x1000d63f.
                  B - A = Z - X in view rotations 0 and 2, X - Z in 1 and 3. Exact against neighbours for |X - Z| = 1;
                  for |X - Z| >= 2 one neighbour cell at each end shares the centre depth (no single key orders both).
   F  pixel widths (n << shift): lowzoom 0x1000bffb, highzoom 0x1000d506, dirty pass 0x1000cadc, picks 0x100092e5,
                  0x10009433, 0x100099a6, 0x10009bd9, GetPixelSizeOfSprite 0x1000ae86, GetCityPixelRectForSprite
                  0x1000f7ec use the longest side. The lot is (X + Z) / 2 cells wide on screen; max(X, Z) is never
                  smaller, and the art (draw) and the sprite's own pixel test (pick) bound what is drawn or hit.
   G  "single cell?" tests `cmp byte [rec + 0xa], 1` take the multi-cell path for 0x400 records (a 1 x Z lot):
                  lowzoom 0x1000bf8d, highzoom 0x1000d4aa, dirty pass 0x1000ca88.
   H  do_pick world box 0x10009afd (z end with Z), GetHeightOfSprite 0x1000b303 (diamond height (X + Z) / 2 cells),
                  sprite pixel bounds fill 0x10008116 (z loop with Z).
   S  save footprint: the occupant descriptor filler (SIMGEOM 0x1001cd38, one copy per module, 9 modules) passes
                  SizeInCellsX twice to SetSizeInCells (0x1001cdb4 -> 0x1001dd82: bits 0-5 = first argument = the
                  0x1001cda8 call, bits 6-11 = second = the 0x1001cd9a call); the 0x1001cd9a call now reads SizeInCellsZ
                  (vt+0xd8) in every copy, so bits 6-11 hold Z. Load ignores that field (0x1000320c), so in game
                  nothing changes; offline readers see the true footprint.
   Not touched (static): GetCellSizeOfSprite 0x10008f8a returns X; the placeholder sprite this+0x48c + n * 4 uses X;
   ChangeSprite 0x1000f2c2's block loop rewrites the registration record only (stock), so it needs no Z; effect anchors
   that centre on the occupant with SizeInCellsX only (0x10032e3e, 0x10039850, 0x1003ccbd, 0x1002249b).
   lot_rect=0 (SC3PERF_LOT_RECT=0) keeps the shipped code. */
static int g_lotrect = 1;
static DWORD g_lr_spr;
static DWORD g_lrA_ret, g_lrB1_ret, g_lrB2_ret, g_lrB4_ret, g_lrB5_ret;
static DWORD g_lrK1_ret, g_lrK2_ret, g_lrE1_ret, g_lrE2_ret, g_lrH1_ret, g_lrH2_ret, g_lrH3_ret;
static DWORD g_lrW1_ret, g_lrW2_ret, g_lrW3_ret, g_lrW4_ret, g_lrW5_ret, g_lrW6_ret, g_lrW7_ret, g_lrW8_ret, g_lrW9_ret;
static DWORD g_lrS1_one, g_lrS1_multi, g_lrS2_one, g_lrS2_multi, g_lrS3_one, g_lrS3_multi;
typedef void (__fastcall *LR_A62C)(BYTE *self, int edx, DWORD x, DWORD z, int *vx, int *vz);
static LR_A62C g_lr_a62c;
static BYTE *g_lr_grid;                 /* Z per registration cell, index x * nz + z */
static DWORD g_lr_cap, g_lr_nz;
static volatile LONG g_lr_marked;

/* side grid: cell map `cm` (+0x14 cells in x, +0x18 in z), lot x0..x0+X-1, z0..z0+Z-1 (game thread, from Insert) */
static void __stdcall lr_mark(BYTE *cm, DWORD x0, DWORD z0, DWORD X, DWORD Z) {
    DWORD nx = *(DWORD *)(cm + 0x14), nz = *(DWORD *)(cm + 0x18), x, z, rx = x0 + X - 1;
    BYTE **col = *(BYTE ***)(cm + 0x24);
    if (nx * nz > g_lr_cap) {
        BYTE *g = (BYTE *)VirtualAlloc(NULL, nx * nz, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (!g) { logf("LOTRECT> side grid %lu x %lu: no memory, lot at (%lu, %lu) stays square", nx, nz, x0, z0); return; }
        g_lr_grid = g; g_lr_cap = nx * nz;            /* a smaller old grid is kept: a draw may still read it */
    }
    g_lr_nz = nz;
    if (rx >= nx || z0 >= nz) return;
    g_lr_grid[rx * nz + z0] = (BYTE)Z;
    for (x = x0; x <= rx && x < nx; x++)
        for (z = z0; z < z0 + Z && z < nz; z++)
            *(WORD *)(col[x] + z * 0x14 + 0x10) |= 0x400;
    if (InterlockedIncrement(&g_lr_marked) <= 20)
        logf("LOTRECT> sprite %lu x %lu at (%lu, %lu) registered as X x Z (reg cell (%lu, %lu))", X, Z, x0, z0, rx, z0);
}
/* Z of the sprite that owns record `rec` (a 0x400 record); n if the side grid has nothing for it */
static int __fastcall lr_zof(const BYTE *rec) {
    DWORD rx = rec[8] | (DWORD)rec[0x12] << 8, rz = rec[9] | (DWORD)rec[0x13] << 8, i = rx * g_lr_nz + rz;
    BYTE z;
    if (!g_lr_grid || i >= g_lr_cap) return rec[0xa];
    z = g_lr_grid[i];
    return z ? z : rec[0xa];
}
static int __fastcall lr_maxof(const BYTE *rec) {
    int z = lr_zof(rec), n = rec[0xa];
    return z > n ? z : n;
}
/* sort-key correction for a 0x400 record: (B - A) * 0x2000, cell map rotation +0x2c */
static int __fastcall lr_keyadj(const BYTE *cm, const BYTE *rec) {
    int x = rec[0xa], z = lr_zof(rec);
    return ((*(int *)(cm + 0x2c) & 1) ? x - z : z - x) * 0x2000;
}
/* ecx = record -> eax = Z / longest side; every other register kept */
static __declspec(naked) void lr_getz(void) { __asm { push ecx
    push edx
    call lr_zof
    pop edx
    pop ecx
    ret } }
static __declspec(naked) void lr_getmax(void) { __asm { push ecx
    push edx
    call lr_maxof
    pop edx
    pop ecx
    ret } }

/* A: InsertCellAlignedSprite 0x10019341..0x1001935f (ecx = occupant, eax = its vtable, edi = x0, ebx = z0) */
static __declspec(naked) void lr_stubA(void) {
    __asm {
        call dword ptr [eax + 0xd4]
        movzx eax, al
        push eax
        mov ecx, dword ptr [ebp + 8]
        mov edx, dword ptr [ecx]
        call dword ptr [edx + 0xd8]
        movzx edx, al
        pop eax
        test edx, edx
        jnz a_hasz
        mov edx, eax
    a_hasz:
        mov dword ptr [ebp + 0xc], edi
        lea ecx, [eax + edi - 1]
        mov dword ptr [ebp - 0x24], ecx
        push ecx
        lea ecx, [edx + ebx - 1]
        mov dword ptr [ebp - 0x1c], ecx
        cmp eax, edx
        je a_sq
        shl edx, 8
        or edx, eax
        or edx, 0x5A3C0000
        mov dword ptr [ebp - 0x20], edx
        jmp a_done
    a_sq:
        mov dword ptr [ebp - 0x20], eax
    a_done:
        pop ecx
        cmp edi, ecx
        jmp dword ptr [g_lrA_ret]
    }
}

/* B1: Insert entry 0x10007b58 (movzx edi,[ebp+0x18]; dec edi). eax, edx are free here. Writes [ebp+0x15] = Z - 1,
   [ebp+0x16] = Z if Z != X else 0, [ebp+0x17] = max(X, Z), [ebp+0x1d] = X. */
static __declspec(naked) void lr_stubB1(void) {
    __asm {
        mov eax, dword ptr [ebp + 0x18]
        and eax, 0xFFFF0000
        cmp eax, 0x5A3C0000
        jne b1_plain
        movzx eax, byte ptr [ebp + 0x19]
        movzx edi, byte ptr [ebp + 0x18]
        jmp b1_have
    b1_plain:
        movzx edi, byte ptr [ebp + 0x18]
        mov eax, edi
    b1_have:
        mov edx, edi
        mov byte ptr [ebp + 0x1d], dl
        lea edx, [eax - 1]
        mov byte ptr [ebp + 0x15], dl
        xor edx, edx
        cmp eax, edi
        je b1_m0
        mov edx, eax
    b1_m0:
        mov byte ptr [ebp + 0x16], dl
        mov edx, eax
        cmp edx, edi
        jae b1_m1
        mov edx, edi
    b1_m1:
        mov byte ptr [ebp + 0x17], dl
        dec edi
        jmp dword ptr [g_lrB1_ret]
    }
}
/* B2: 0x10007c52 (mov eax,[ebp-0x10]; add eax,ebx): z end of the cell loop */
static __declspec(naked) void lr_stubB2(void) {
    __asm {
        cmp byte ptr [ebp + 0x16], 0
        jne b2_rect
        mov eax, dword ptr [ebp - 0x10]
        add eax, ebx
        jmp dword ptr [g_lrB2_ret]
    b2_rect:
        movzx eax, byte ptr [ebp + 0x15]
        add eax, ebx
        jmp dword ptr [g_lrB2_ret]
    }
}
/* B4: 0x10007d02 (mov eax,[ebp-0x10]; mov ecx,[edx+ecx*4]): the two +z corner flags */
static __declspec(naked) void lr_stubB4(void) {
    __asm {
        cmp byte ptr [ebp + 0x16], 0
        jne b4_rect
        mov eax, dword ptr [ebp - 0x10]
        jmp b4_done
    b4_rect:
        movzx eax, byte ptr [ebp + 0x15]
    b4_done:
        mov ecx, dword ptr [edx + ecx * 4]
        jmp dword ptr [g_lrB4_ret]
    }
}
/* B5: 0x10007d27 (inc dword [esi+0x110]): mark a non-square sprite's cells (esi = cell map, [ebp+0xc] = x0, ebx = z0) */
static __declspec(naked) void lr_stubB5(void) {
    __asm {
        cmp byte ptr [ebp + 0x16], 0
        je b5_go
        pushad
        movzx eax, byte ptr [ebp + 0x16]
        push eax
        movzx eax, byte ptr [ebp + 0x1d]
        push eax
        push ebx
        push dword ptr [ebp + 0xc]
        push esi
        call lr_mark
        popad
    b5_go:
        inc dword ptr [esi + 0x110]
        jmp dword ptr [g_lrB5_ret]
    }
}
/* K1: lowzoom 0x1000c14b (mov [eax+0x14],edi; mov ecx,[ebp-4]): edi = key, eax = entry, esi = cell map */
static __declspec(naked) void lr_stubK1(void) {
    __asm {
        mov ecx, dword ptr [ebp - 4]
        test word ptr [ecx + 0x10], 0x400
        jz k1_done
        push eax
        mov edx, ecx
        mov ecx, esi
        call lr_keyadj
        sub edi, eax
        pop eax
        mov ecx, dword ptr [ebp - 4]
    k1_done:
        mov dword ptr [eax + 0x14], edi
        jmp dword ptr [g_lrK1_ret]
    }
}
/* K2: highzoom 0x1000d63f (mov [eax+0x14],ecx; movzx ecx,[edi+0xa]): ecx = key, edi = record, esi = cell map */
static __declspec(naked) void lr_stubK2(void) {
    __asm {
        test word ptr [edi + 0x10], 0x400
        jz k2_done
        push eax
        push edx
        push ecx
        mov ecx, esi
        mov edx, edi
        call lr_keyadj
        pop ecx
        sub ecx, eax
        pop edx
        pop eax
    k2_done:
        mov dword ptr [eax + 0x14], ecx
        movzx ecx, byte ptr [edi + 0xa]
        jmp dword ptr [g_lrK2_ret]
    }
}
/* E1: lowzoom 0x1000c15d (mov [ebp-0x50],edi; add edi,edx): edi = z0 + Z. [ebp-4] = record, eax = list entry (live) */
static __declspec(naked) void lr_stubE1(void) {
    __asm {
        mov dword ptr [ebp - 0x50], edi
        mov ebx, dword ptr [ebp - 4]
        test word ptr [ebx + 0x10], 0x400
        jz e1_sq
        push eax
        push ecx
        mov ecx, ebx
        call lr_getz
        mov edi, eax
        pop ecx
        pop eax
    e1_sq:
        add edi, edx
        jmp dword ptr [g_lrE1_ret]
    }
}
/* E2: highzoom 0x1000d64c (shl ecx,8; mov [ebp-4],ecx), ecx = n + z0, edi = record: ecx = z0 + Z first */
static __declspec(naked) void lr_stubE2(void) {
    __asm {
        test word ptr [edi + 0x10], 0x400
        jz e2_sq
        push eax
        push ecx
        mov ecx, edi
        call lr_getz
        pop ecx
        push edx
        movzx edx, byte ptr [edi + 0xa]
        sub ecx, edx
        add ecx, eax
        pop edx
        pop eax
    e2_sq:
        shl ecx, 8
        mov dword ptr [ebp - 4], ecx
        jmp dword ptr [g_lrE2_ret]
    }
}
/* H1: do_pick 0x10009afd..0x10009b12, eax = record, edx = x0 * 256: pushes the altitude, eax = z0 * 256 + Z * 256,
   ecx = x0 * 256 + X * 256 */
static __declspec(naked) void lr_stubH1(void) {
    __asm {
        movzx ecx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz h1_sq
        push eax
        mov ecx, eax
        call lr_getz
        mov ecx, eax
        pop eax
    h1_sq:
        shl ecx, 8
        push ecx
        movzx ecx, byte ptr [eax + 0xa]
        movzx eax, byte ptr [eax + 0xb]
        xchg eax, dword ptr [esp]
        add eax, dword ptr [ebp - 0xe0]
        shl ecx, 8
        add ecx, edx
        jmp dword ptr [g_lrH1_ret]
    }
}
/* H2: GetHeightOfSprite 0x1000b303..0x1000b30a, esi = record, edi = cell height, ecx = zoom (live) */
static __declspec(naked) void lr_stubH2(void) {
    __asm {
        test word ptr [esi + 0x10], 0x400
        jz h2_sq
        push ecx
        mov ecx, esi
        call lr_getz
        pop ecx
        push edx
        movzx edx, byte ptr [esi + 0xa]
        add eax, edx
        pop edx
        imul eax, edi
        cdq
        sub eax, edx
        sar eax, 1
        jmp dword ptr [g_lrH2_ret]
    h2_sq:
        movzx eax, byte ptr [esi + 0xa]
        imul eax, edi
        jmp dword ptr [g_lrH2_ret]
    }
}
/* H3: 0x10008116..0x1000811c, esi = record: eax = z0 + Z */
static __declspec(naked) void lr_stubH3(void) {
    __asm {
        test word ptr [esi + 0x10], 0x400
        jz h3_sq
        push ecx
        mov ecx, esi
        call lr_getz
        pop ecx
        jmp h3_add
    h3_sq:
        movzx eax, byte ptr [esi + 0xa]
    h3_add:
        add eax, dword ptr [ebp + 0xc]
        jmp dword ptr [g_lrH3_ret]
    }
}
/* F: widths, the longest side for 0x400 records */
static __declspec(naked) void lr_stubW1(void) {   /* lowzoom 0x1000bffb: movzx edx,[eax+0xa]; add ecx,3 */
    __asm {
        movzx edx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w1_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edx, eax
        pop ecx
        pop eax
    w1_d:
        add ecx, 3
        jmp dword ptr [g_lrW1_ret]
    }
}
static __declspec(naked) void lr_stubW2(void) {   /* highzoom 0x1000d506: movzx eax,[edi+0xa]; add ecx,3 */
    __asm {
        test word ptr [edi + 0x10], 0x400
        jz w2_sq
        push ecx
        mov ecx, edi
        call lr_getmax
        pop ecx
        jmp w2_d
    w2_sq:
        movzx eax, byte ptr [edi + 0xa]
    w2_d:
        add ecx, 3
        jmp dword ptr [g_lrW2_ret]
    }
}
static __declspec(naked) void lr_stubW3(void) {   /* dirty pass 0x1000cadc: movzx ebx,[eax+0xa]; mov [edx],ecx */
    __asm {
        movzx ebx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w3_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov ebx, eax
        pop ecx
        pop eax
    w3_d:
        mov dword ptr [edx], ecx
        jmp dword ptr [g_lrW3_ret]
    }
}
/* picks 0x100092e5 / 0x10009433: movzx edi,[eax+0xa]; movsx eax,word [eax+6] */
static __declspec(naked) void lr_stubW4(void) {
    __asm {
        movzx edi, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w4_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edi, eax
        pop ecx
        pop eax
    w4_d:
        movsx eax, word ptr [eax + 6]
        jmp dword ptr [g_lrW4_ret]
    }
}
static __declspec(naked) void lr_stubW5(void) {
    __asm {
        movzx edi, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w5_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edi, eax
        pop ecx
        pop eax
    w5_d:
        movsx eax, word ptr [eax + 6]
        jmp dword ptr [g_lrW5_ret]
    }
}
/* do_pick 0x100099a6 / 0x10009bd9: movzx edx,[eax+0xa]; movsx eax,word [eax+6] */
static __declspec(naked) void lr_stubW6(void) {
    __asm {
        movzx edx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w6_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edx, eax
        pop ecx
        pop eax
    w6_d:
        movsx eax, word ptr [eax + 6]
        jmp dword ptr [g_lrW6_ret]
    }
}
static __declspec(naked) void lr_stubW7(void) {
    __asm {
        movzx edx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w7_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edx, eax
        pop ecx
        pop eax
    w7_d:
        movsx eax, word ptr [eax + 6]
        jmp dword ptr [g_lrW7_ret]
    }
}
static __declspec(naked) void lr_stubW8(void) {   /* GetPixelSizeOfSprite 0x1000ae86: movzx edx,[eax+0xa]; shl edx,cl */
    __asm {
        movzx edx, byte ptr [eax + 0xa]
        test word ptr [eax + 0x10], 0x400
        jz w8_d
        push eax
        push ecx
        mov ecx, eax
        call lr_getmax
        mov edx, eax
        pop ecx
        pop eax
    w8_d:
        shl edx, cl
        jmp dword ptr [g_lrW8_ret]
    }
}
static __declspec(naked) void lr_stubW9(void) {   /* GetCityPixelRectForSprite 0x1000f7ec: movzx edx,[edi+0xa]; shl edx,cl */
    __asm {
        movzx edx, byte ptr [edi + 0xa]
        test word ptr [edi + 0x10], 0x400
        jz w9_d
        push eax
        push ecx
        mov ecx, edi
        call lr_getmax
        mov edx, eax
        pop ecx
        pop eax
    w9_d:
        shl edx, cl
        jmp dword ptr [g_lrW9_ret]
    }
}
/* G: single-cell tests. Stock jbe / ja on `cmp byte [rec+0xa], 1`; a 0x400 record is multi-cell. */
static __declspec(naked) void lr_stubS1(void) {   /* lowzoom 0x1000bf8d..0x1000bf99, record = ecx + eax*4 */
    __asm {
        lea edx, [ecx + eax * 4]
        mov dword ptr [ebp - 0x30], edx
        cmp byte ptr [edx + 0xa], 1
        ja s1_m
        test word ptr [edx + 0x10], 0x400
        jnz s1_m
        jmp dword ptr [g_lrS1_one]
    s1_m:
        jmp dword ptr [g_lrS1_multi]
    }
}
static __declspec(naked) void lr_stubS2(void) {   /* highzoom 0x1000d4aa..0x1000d4b1, record = edi */
    __asm {
        mov dword ptr [eax], edi
        cmp byte ptr [edi + 0xa], 1
        ja s2_m
        test word ptr [edi + 0x10], 0x400
        jnz s2_m
        jmp dword ptr [g_lrS2_one]
    s2_m:
        jmp dword ptr [g_lrS2_multi]
    }
}
static __declspec(naked) void lr_stubS3(void) {   /* dirty pass 0x1000ca88..0x1000ca91, record = ecx + eax*4 */
    __asm {
        lea ecx, [ecx + eax * 4]
        cmp byte ptr [ecx + 0xa], 1
        ja s3_m
        test word ptr [ecx + 0x10], 0x400
        jnz s3_m
        jmp dword ptr [g_lrS3_one]
    s3_m:
        jmp dword ptr [g_lrS3_multi]
    }
}

/* D: 0x1000c678 (thiscall, ret 0x10): *out_rec = registration record, (vx, vz) = view cell of the lot's left vertex */
static void __fastcall lr_c678(BYTE *self, int unused, BYTE *rec, DWORD *out_rec, int *vx, int *vz) {
    DWORD rx = rec[8] | (DWORD)rec[0x12] << 8, rz = rec[9] | (DWORD)rec[0x13] << 8;
    int n = rec[0xa], zz = (*(WORD *)(rec + 0x10) & 0x400) ? lr_zof(rec) : n;
    (void)unused;
    *out_rec = (*(DWORD **)(self + 0x24))[rx] + rz * 0x14;
    g_lr_a62c(self, 0, rx, rz, vx, vz);
    switch (*(int *)(self + 0x2c)) {
    case 1: *vz += 1 - n; break;
    case 2: *vx += n - 1; *vz += 1 - zz; break;
    case 3: *vx += zz - 1; break;
    }
}
/* D: 0x1000f6f4 (thiscall, ret 0x10): view cell of the left vertex of the sprite at cell (x, z) */
static void __fastcall lr_f6f4(BYTE *self, int unused, DWORD x, DWORD z, DWORD *ovx, DWORD *ovz) {
    BYTE *rec = (BYTE *)(*(DWORD **)(self + 0x24))[x] + z * 0x14;
    DWORD rx = rec[8] | (DWORD)rec[0x12] << 8, rz = rec[9] | (DWORD)rec[0x13] << 8, n = rec[0xa];
    DWORD zz = (*(WORD *)(rec + 0x10) & 0x400) ? (DWORD)lr_zof(rec) : n;
    DWORD nx = *(DWORD *)(self + 0x14), nz = *(DWORD *)(self + 0x18);
    (void)unused;
    *ovx = rx;
    *ovz = rz;
    switch (*(int *)(self + 0x2c)) {
    case 1: *ovx = nz - rz - 1; *ovz = rx - n + 1; break;
    case 2: *ovx = nx + n - rx - 2; *ovz = nz - zz - rz; break;
    case 3: *ovx = rz + zz - 1; *ovz = nx - rx - 1; break;
    }
}

typedef struct { DWORD rva; BYTE len; BYTE want[32]; } LR_SITE;
/* shipped bytes of every site (SIMSPR 0x10000000 base) */
static const LR_SITE k_lr_sites[] = {
    {0x19341, 31, {0xff,0x90,0xd4,0,0,0, 0x0f,0xb6,0xc0, 0x89,0x45,0xe0, 0x89,0x7d,0x0c, 0x8d,0x4c,0x38,0xff,
                   0x8d,0x44,0x18,0xff, 0x3b,0xf9, 0x89,0x4d,0xdc, 0x89,0x45,0xe4}},
    {0x07b58, 5, {0x0f,0xb6,0x7d,0x18, 0x4f}},
    {0x07c52, 5, {0x8b,0x45,0xf0, 0x03,0xc3}},
    {0x07c9d, 4, {0x80,0x7d,0x18,0x02}},
    {0x07d02, 6, {0x8b,0x45,0xf0, 0x8b,0x0c,0x8a}},
    {0x07d27, 6, {0xff,0x86,0x10,0x01,0x00,0x00}},
    {0x07fea, 4, {0x66,0x89,0x47,0x10}},
    {0x05ed9, 4, {0x66,0x89,0x70,0x10}},
    {0x0c678, 6, {0x55, 0x8b,0xec, 0x53, 0x56, 0x8b}},
    {0x0f6f4, 6, {0x8b,0x51,0x24, 0x8b,0x44,0x24}},
    {0x0c15d, 5, {0x89,0x7d,0xb0, 0x03,0xfa}},
    {0x0c14b, 6, {0x89,0x78,0x14, 0x8b,0x4d,0xfc}},
    {0x0d63f, 7, {0x89,0x48,0x14, 0x0f,0xb6,0x4f,0x0a}},
    {0x0d64c, 6, {0xc1,0xe1,0x08, 0x89,0x4d,0xfc}},
    {0x09afd, 22, {0x0f,0xb6,0x48,0x0a, 0x0f,0xb6,0x40,0x0b, 0x50, 0x8b,0x85,0x20,0xff,0xff,0xff, 0xc1,0xe1,0x08,
                   0x03,0xc1, 0x03,0xca}},
    {0x0b303, 8, {0x0f,0xb6,0x44,0x82,0x0a, 0x0f,0xaf,0xc7}},
    {0x08116, 7, {0x0f,0xb6,0x46,0x0a, 0x03,0x45,0x0c}},
    {0x0bffb, 7, {0x0f,0xb6,0x50,0x0a, 0x83,0xc1,0x03}},
    {0x0d506, 7, {0x0f,0xb6,0x47,0x0a, 0x83,0xc1,0x03}},
    {0x0cadc, 6, {0x0f,0xb6,0x58,0x0a, 0x89,0x0a}},
    {0x092e5, 8, {0x0f,0xb6,0x78,0x0a, 0x0f,0xbf,0x40,0x06}},
    {0x09433, 8, {0x0f,0xb6,0x78,0x0a, 0x0f,0xbf,0x40,0x06}},
    {0x099a6, 8, {0x0f,0xb6,0x50,0x0a, 0x0f,0xbf,0x40,0x06}},
    {0x09bd9, 8, {0x0f,0xb6,0x50,0x0a, 0x0f,0xbf,0x40,0x06}},
    {0x0ae86, 6, {0x0f,0xb6,0x50,0x0a, 0xd3,0xe2}},
    {0x0f7ec, 6, {0x0f,0xb6,0x57,0x0a, 0xd3,0xe2}},
    {0x0bf8d, 13, {0x80,0x7c,0x81,0x0a,0x01, 0x8d,0x14,0x81, 0x89,0x55,0xd0, 0x76,0x19}},
    {0x0d4aa, 8, {0x80,0x7f,0x0a,0x01, 0x89,0x38, 0x77,0x16}},
    {0x0ca88, 10, {0x80,0x7c,0x81,0x0a,0x01, 0x8d,0x0c,0x81, 0x76,0x19}},
};
#define LR_NSITES ((int)(sizeof(k_lr_sites) / sizeof(k_lr_sites[0])))

static void lr_jmp(BYTE *at, int len, void *to) {
    int i;
    at[0] = 0xE9; *(DWORD *)(at + 1) = (DWORD)to - (DWORD)(at + 5);
    for (i = 5; i < len; i++) at[i] = 0x90;
}
static void patch_lotrect(DWORD spr) {
    BYTE *s = (BYTE *)spr;
    DWORD old;
    int i;
    for (i = 0; i < LR_NSITES; i++)
        if (memcmp(s + k_lr_sites[i].rva, k_lr_sites[i].want, k_lr_sites[i].len)) {
            logf("LOTRECT> SIMSPR+0x%05lX differs from shipped - not patched (no site touched)", k_lr_sites[i].rva);
            return;
        }
    if ((DWORD)(s + 0xc6b4) + *(DWORD *)(s + 0xc6b0) != spr + 0xa62c) { logf("LOTRECT> 0x1000c6af target differs - not patched"); return; }
    g_lr_spr = spr;
    g_lr_a62c = (LR_A62C)(spr + 0xa62c);
    g_lrA_ret = spr + 0x19360;
    g_lrB1_ret = spr + 0x7b5d; g_lrB2_ret = spr + 0x7c57; g_lrB4_ret = spr + 0x7d08; g_lrB5_ret = spr + 0x7d2d;
    g_lrK1_ret = spr + 0xc151; g_lrK2_ret = spr + 0xd646;
    g_lrE1_ret = spr + 0xc162; g_lrE2_ret = spr + 0xd652;
    g_lrH1_ret = spr + 0x9b13; g_lrH2_ret = spr + 0xb30b; g_lrH3_ret = spr + 0x811d;
    g_lrW1_ret = spr + 0xc002; g_lrW2_ret = spr + 0xd50d; g_lrW3_ret = spr + 0xcae2; g_lrW4_ret = spr + 0x92ed;
    g_lrW5_ret = spr + 0x943b; g_lrW6_ret = spr + 0x99ae; g_lrW7_ret = spr + 0x9be1; g_lrW8_ret = spr + 0xae8c;
    g_lrW9_ret = spr + 0xf7f2;
    g_lrS1_one = spr + 0xbfb3; g_lrS1_multi = spr + 0xbf9a;
    g_lrS2_one = spr + 0xd4b2; g_lrS2_multi = spr + 0xd4c8;
    g_lrS3_one = spr + 0xcaab; g_lrS3_multi = spr + 0xca92;
    /* one protection change over the whole span, never restored (memory project-mod-startup-races) */
    if (!VirtualProtect(s + 0x5000, 0x15000, PAGE_EXECUTE_READWRITE, &old)) { logf("LOTRECT> VirtualProtect failed (%lu)", GetLastError()); return; }
    s[0x05ed9] = 0x89; s[0x05eda] = 0x70; s[0x05edb] = 0x10; s[0x05edc] = 0x90;   /* Init: dword clear */
    s[0x07fea] = 0x89; s[0x07feb] = 0x47; s[0x07fec] = 0x10; s[0x07fed] = 0x90;   /* Remove: dword clear */
    lr_jmp(s + 0x0c678, 5, (void *)lr_c678);
    lr_jmp(s + 0x0f6f4, 5, (void *)lr_f6f4);
    lr_jmp(s + 0x0c14b, 6, (void *)lr_stubK1);
    lr_jmp(s + 0x0d63f, 7, (void *)lr_stubK2);
    lr_jmp(s + 0x0c15d, 5, (void *)lr_stubE1);
    lr_jmp(s + 0x0d64c, 6, (void *)lr_stubE2);
    lr_jmp(s + 0x09afd, 22, (void *)lr_stubH1);
    lr_jmp(s + 0x0b303, 8, (void *)lr_stubH2);
    lr_jmp(s + 0x08116, 7, (void *)lr_stubH3);
    lr_jmp(s + 0x0bffb, 7, (void *)lr_stubW1);
    lr_jmp(s + 0x0d506, 7, (void *)lr_stubW2);
    lr_jmp(s + 0x0cadc, 6, (void *)lr_stubW3);
    lr_jmp(s + 0x092e5, 8, (void *)lr_stubW4);
    lr_jmp(s + 0x09433, 8, (void *)lr_stubW5);
    lr_jmp(s + 0x099a6, 8, (void *)lr_stubW6);
    lr_jmp(s + 0x09bd9, 8, (void *)lr_stubW7);
    lr_jmp(s + 0x0ae86, 6, (void *)lr_stubW8);
    lr_jmp(s + 0x0f7ec, 6, (void *)lr_stubW9);
    lr_jmp(s + 0x0bf8d, 13, (void *)lr_stubS1);
    lr_jmp(s + 0x0d4aa, 8, (void *)lr_stubS2);
    lr_jmp(s + 0x0ca88, 10, (void *)lr_stubS3);
    s[0x07c9f] = 0x17;                                         /* cmp byte [ebp+0x17], 2: the longest side */
    lr_jmp(s + 0x07c52, 5, (void *)lr_stubB2);
    lr_jmp(s + 0x07d02, 6, (void *)lr_stubB4);
    lr_jmp(s + 0x07d27, 6, (void *)lr_stubB5);
    lr_jmp(s + 0x07b58, 5, (void *)lr_stubB1);                  /* Insert decodes the packed size from here on */
    lr_jmp(s + 0x19341, 31, (void *)lr_stubA);                  /* last: the sprite manager starts passing Z */
    FlushInstructionCache(GetCurrentProcess(), s + 0x5000, 0x15000);
    logf("LOTRECT> %d SIMSPR sites patched: sprites of X x Z buildings register, draw, clip, pick and sort as X x Z "
         "(record flag 0x400 + side grid of Z by registration cell)", LR_NSITES);
}

/* S: every module's copy of the occupant descriptor filler (the framework's sc3_record_fill_descriptor, SIMGEOM
   0x1001cd38). Each occupant class saves through ITS module's copy (vtable slot 0x24): a landmark is a SIMMISC class
   (vtable SIMMISC 0x100405e8, slot 0x24 0x1000c1df -> the copy at 0x100359f6), not SIMGEOM's. Byte +8 of the pattern
   is the disp of the first `call [eax+0xd4]`, whose value becomes SetSizeInCells' second argument (bits 6-11). */
typedef struct { const char *mod; DWORD rva; } LR_SAVESITE;
static const LR_SAVESITE k_lr_save[] = {
    {"SIMGEOM.DLL", 0x1cd94}, {"SIMMISC.DLL", 0x359f6}, {"SIMRCI.DLL", 0x3d498}, {"SIMNTWRK.DLL", 0x23b96},
    {"SIMDSTR.DLL", 0x2dfa9}, {"SIMECO.DLL", 0x14b7c}, {"SIMSERV.DLL", 0x14f14}, {"SIMUTIL.DLL", 0x199b4},
    {"SimTransit.dll", 0x15e04}};
#define LR_NSAVE ((int)(sizeof(k_lr_save) / sizeof(k_lr_save[0])))
static DWORD WINAPI lr_geom_watcher(LPVOID p) {
    static const BYTE want[] = {0x8b, 0x07, 0x8b, 0x1e, 0x8b, 0xcf, 0xff, 0x90, 0xd4, 0, 0, 0, 0x0f, 0xb6, 0xc0, 0x50,
                                0x8b, 0x07, 0x8b, 0xcf, 0xff, 0x90, 0xd4, 0, 0, 0};
    int done[LR_NSAVE] = {0}, left = LR_NSAVE, ms, i, ok = 0;
    DWORD old;
    (void)p;
    for (ms = 0; left && ms < 300000; ms++) {
        for (i = 0; i < LR_NSAVE; i++) {
            BYTE *m;
            if (done[i] || !(m = (BYTE *)GetModuleHandleA(k_lr_save[i].mod))) continue;
            done[i] = 1; left--;
            if (memcmp(m + k_lr_save[i].rva, want, sizeof(want))) {
                logf("LOTRECT> %s+0x%05lX differs from shipped - its occupants save X x X", k_lr_save[i].mod, k_lr_save[i].rva);
                continue;
            }
            if (!VirtualProtect(m + k_lr_save[i].rva + 8, 1, PAGE_EXECUTE_READWRITE, &old)) continue;
            m[k_lr_save[i].rva + 8] = 0xd8;
            FlushInstructionCache(GetCurrentProcess(), m + k_lr_save[i].rva + 8, 1);
            ok++;
        }
        if (left) Sleep(1);
    }
    logf("LOTRECT> save footprint: %d of %d occupant descriptor fillers call SizeInCellsZ for bits 6-11 "
         "(SIMGEOM 0x1001cd9a and its copies)", ok, LR_NSAVE);
    return 0;
}
