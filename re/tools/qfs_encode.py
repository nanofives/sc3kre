#!/usr/bin/env python3
"""qfs_encode.py - QFS token disassembler, encoder-behaviour probe, and compressor.

The decompressor is pinned byte-for-byte in re/tools/qfs.py (sc3_qfs_decompress
SIMSPR.DLL 0x10050d09). THE COMPRESSOR IS ALSO IN A SHIPPED BINARY and `compress` below is
a transcription of it, not an inference:

  GZResourceD.dll  FUN_100168cb  (82 B)   header: 0x10FB big-endian + 3-byte size, then ->
                   FUN_1001694d  (906 B)  the encoder            [CONFIRMED @0x1001694d]
                   FUN_10016cd7  (40 B)   byte-wise match length [CONFIRMED @0x10016cd7]
                   FUN_1001691d  (48 B)   big-endian n-byte store

This was nearly written up the wrong way round. A probe of the shipped streams (--probe)
showed the encoder picks the longest available match only ~82% of the time and the nearest
such offset ~68%, which looks exactly like an unreproducible search heuristic. It is not:
FUN_1001694d selects by NET GAIN, `matchLen - tokenCost` against the best so far
[CONFIRMED @0x1001694d], so a shorter match in a cheaper token legitimately wins. The
"deviation" was the measurement lacking the cost model, not the encoder being unknowable.
The game writes .sc3 files, so a compressor had to exist; looking for it beat inferring it.

  --tokens   disassemble a stream into its control tokens (pure decode, no inference)
  --probe    measure the original encoder's choices against an exhaustive longest-match
  --compress transcribed encoder -> diff against the shipped stream, byte for byte

Usage:
  py -3.12 re/tools/qfs_encode.py <file.sc3> --tokens [--limit N]
  py -3.12 re/tools/qfs_encode.py <file.sc3> --probe [--limit N] [--verify N]
  py -3.12 re/tools/qfs_encode.py <dir> --selftest [--limit N]   # city AND sprite streams
  py -3.12 re/tools/qfs_encode.py <file-or-dir> --compress
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_parse
import ixf_parse
import qfs

MAX_OFF_2, MAX_LEN_2 = 0x400, 10          # 2-byte form: off <= 1024, len 3..10
MAX_OFF_3, MAX_LEN_3 = 0x4000, 67         # 3-byte form: off <= 16384, len 4..67
MAX_OFF_4, MAX_LEN_4 = 0x20000, 1028      # 4-byte form: off <= 131072, len 5..1028


def tokens(buf, pos=0):
    """Disassemble a QFS stream -> list of dicts. Pure transcription of qfs.decompress.

    Each token: {at, form, lit, off, len, outpos}. `outpos` is the output position where
    the token's literals begin, so a probe can look at the plaintext the encoder saw.
    """
    p = pos + (5 if buf[pos] & 1 else 2)
    p += 3
    out = bytearray()
    toks = []
    while True:
        b0 = buf[p]
        at, outpos = p, len(out)
        if b0 & 0x80 == 0:
            b1 = buf[p + 1]
            lit, off, ln, form, p = b0 & 3, ((b0 & 0x60) << 3) + b1 + 1, ((b0 >> 2) & 7) + 3, 2, p + 2
        elif b0 & 0x40 == 0:
            b1, b2 = buf[p + 1], buf[p + 2]
            lit, off, ln, form, p = b1 >> 6, ((b1 & 0x3F) << 8) + b2 + 1, (b0 & 0x3F) + 4, 3, p + 3
        elif b0 & 0x20 == 0:
            b1, b2, b3 = buf[p + 1], buf[p + 2], buf[p + 3]
            lit = b0 & 3
            off = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
            ln = ((b0 & 0x0C) << 6) + b3 + 5
            form, p = 4, p + 4
        else:
            n = (b0 & 0x1F) * 4 + 4
            if n > 0x70:
                lit, off, ln, form, p = b0 & 3, 0, 0, "end", p + 1
            else:
                lit, off, ln, form, p = n, 0, 0, "run", p + 1
        out.extend(buf[p:p + lit])
        p += lit
        if ln:
            src = len(out) - off
            for _ in range(ln):
                out.append(out[src])
                src += 1
        toks.append({"at": at, "form": form, "lit": lit, "off": off, "len": ln, "outpos": outpos})
        if form == "end":
            break
    return toks, bytes(out)


def encodable(off, ln):
    """True if some control form can encode this (offset, length) pair.

    Derived from the four forms in qfs.py, which are transcribed from the shipped
    decompressor -- so this is a property of the FORMAT, not an assumption about the
    encoder. A probe that ignores it will score the encoder as "missed a longer match"
    when the longer match was simply not expressible.
    """
    if off <= MAX_OFF_2 and 3 <= ln <= MAX_LEN_2:
        return True
    if off <= MAX_OFF_3 and 4 <= ln <= MAX_LEN_3:
        return True
    return off <= MAX_OFF_4 and 5 <= ln <= MAX_LEN_4


def longest_match(data, pos, max_off=MAX_OFF_4, cap=MAX_LEN_4):
    """-> (best_len, best_off, n_equal): the longest ENCODABLE match at `pos`.

    Among matches of the best length, returns the SMALLEST offset (nearest), plus how many
    distinct offsets achieve it -- so the probe can tell whether the original encoder's
    offset choice was forced or a preference. Exhaustive on purpose: a reference has to be
    free of the very search heuristic it is being used to detect.
    """
    lo = max(0, pos - max_off)
    best_len, best_off, n_equal = 0, 0, 0
    limit = min(len(data) - pos, cap)
    for start in range(pos - 1, lo - 1, -1):
        n = 0
        while n < limit and data[start + n] == data[pos + n]:
            n += 1
        if not encodable(pos - start, n):
            continue
        if n > best_len:
            best_len, best_off, n_equal = n, pos - start, 1
        elif n == best_len:
            n_equal += 1
    return best_len, best_off, n_equal


def longest_match_fast(data, pos, max_off=MAX_OFF_4, cap=MAX_LEN_4):
    """Same contract as longest_match, using bytes.rfind so whole files can be probed.

    Grows the probe prefix one byte at a time; rfind's search window is allowed to run
    past `pos`, which is exactly the overlapping-copy semantics the decompressor has
    (offset < length repeats the tail). Cross-checked against the exhaustive version by
    --probe --verify, which is the only reason it is trusted.
    """
    lo = max(0, pos - max_off)
    limit = min(len(data) - pos, cap)
    if limit < 3:
        return 0, 0, 0
    best_len, best_off = 0, 0
    ln = 3
    while ln <= limit:
        i = data.rfind(data[pos:pos + ln], lo, pos + ln - 1)
        if i == -1:
            break
        if encodable(pos - i, ln):
            best_len, best_off = ln, pos - i
        ln += 1
    if not best_len:
        return 0, 0, 0
    # nearest offset achieving best_len: rfind already returns the rightmost start.
    i = data.rfind(data[pos:pos + best_len], lo, pos + best_len - 1)
    return best_len, pos - i, 1


def compress(src, quick=1):
    """QFS-compress `src` -> the payload after the 5-byte header.

    Transcription of GZResourceD FUN_1001694d [CONFIRMED @0x1001694d]. Variable names keep
    the decompiler's roles: `pending` = local_8 (unflushed literals), `best_len` = local_c,
    `best_cost` = local_18 (2/3/4, the token size), `best_off_m1` = local_30 (offset - 1).

    Structures, exactly as the original allocates them:
      hash table  malloc(0x40000) = 65,536 u32 slots, all 0xFFFFFFFF
      chain       malloc(0x80000) = 131,072 u32 slots, indexed by position & 0x1FFFF
      hash        (p[1] << 4) ^ ((p[0] << 8) | p[2])        -- 3 bytes, naturally < 0x10000
      window      pos - 0x1FFFF, floored at 0

    `quick` is the original's param_5, set by FUN_100168cb from its param_4 flag:
      0 -> insert EVERY position covered by an emitted match into the chain
      1 -> insert only the match's first position (faster, finds fewer matches later)

    Selection is by NET GAIN, not by length: a candidate wins only when
    `matchLen - tokenCost > bestLen - bestCost`, starting from bestLen = bestCost = 2.
    """
    n = len(src)
    pad = bytes(src) + b"\x00\x00"        # the original hashes 2 bytes past `pos`; at the
    hashtab = [-1] * 0x10000              # last 2 positions no match can be accepted
    chain = [-1] * 0x20000                # (cap <= remaining <= 2 < 3), so the values it
    out = bytearray()                     # reads there cannot change the output.

    pos = lit_start = pending = 0
    remaining = n

    def flush_runs():
        nonlocal pending, lit_start, out
        while pending > 3:
            k = pending & 0xFFFFFFFC
            if k > 0x70:
                k = 0x70
            pending -= k
            out.append(((k >> 2) - 0x21) & 0xFF)
            out += src[lit_start:lit_start + k]
            lit_start += k

    while remaining > 0:
        best_off_m1, best_cost, best_len = 0, 2, 2
        cap = min(0x404, remaining)
        hv = (pad[pos + 1] << 4) ^ ((pad[pos] << 8) | pad[pos + 2])
        lo = pos - 0x1FFFF
        if lo < 1:
            lo = 0
        cand = hashtab[hv]

        if cand >= lo:
            while True:
                if pad[pos + best_len] == pad[cand + best_len]:
                    m = 0
                    while m < cap and src[pos + m] == src[cand + m]:
                        m += 1
                    if m > best_len:
                        off_m1 = pos - cand - 1
                        if off_m1 < 0x400 and m < 0xB:
                            cost = 2
                        elif off_m1 > 0x3FFF:
                            cost = 4
                        else:
                            cost = 4 if m > 0x43 else 3
                        if best_len - best_cost < m - cost:
                            best_cost, best_off_m1, best_len = cost, off_m1, m
                            if m > 0x403:
                                break
                cand = chain[cand & 0x1FFFF]
                if cand < lo:
                    break

        if best_len <= best_cost:                       # LAB_10016afc -- emit as literal
            pending += 1
            remaining -= 1
            chain[pos & 0x1FFFF] = hashtab[hv]
            hashtab[hv] = pos
            pos += 1
            continue

        flush_runs()
        if best_cost == 2:
            out.append((((best_off_m1 >> 3) & 0xE0) + ((best_len + 0x3D) * 4) + pending) & 0xFF)
            out.append(best_off_m1 & 0xFF)
        elif best_cost == 3:
            out.append((best_len + 0x7C) & 0xFF)
            out.append(((best_off_m1 >> 8) + pending * 0x40) & 0xFF)
            out.append(best_off_m1 & 0xFF)
        else:
            out.append(((((best_len - 5) >> 6) & 0xFC) + ((best_off_m1 >> 12) & 0xF0)
                        + pending - 0x40) & 0xFF)
            out.append((best_off_m1 >> 8) & 0xFF)
            out.append(best_off_m1 & 0xFF)
            out.append((best_len - 5) & 0xFF)
        if pending:
            out += src[lit_start:lit_start + pending]
            pending = 0

        if quick == 0:
            for q in range(pos, pos + best_len):
                hq = (pad[q + 1] << 4) ^ ((pad[q] << 8) | pad[q + 2])
                chain[q & 0x1FFFF] = hashtab[hq]
                hashtab[hq] = q
            pos += best_len
        else:
            chain[pos & 0x1FFFF] = hashtab[hv]
            hashtab[hv] = pos
            pos += best_len
        remaining -= best_len
        lit_start = pos

    flush_runs()
    out.append((pending - 4) & 0xFF)
    if pending:
        out += src[lit_start:lit_start + pending]
    return bytes(out)


def compress_stream(src, quick=1):
    """The full QFS stream: 2-byte 0x10FB + 3-byte big-endian size + payload.

    Transcription of FUN_100168cb: FUN_1001691d(dst, 0x10FB, 2) then
    FUN_1001691d(dst + 2, size, 3), both big-endian [CONFIRMED @0x100168cb].
    """
    return (b"\x10\xfb" + len(src).to_bytes(3, "big")) + compress(src, quick)


def city_stream(path):
    """-> (qfs stream bytes, plaintext) for a city-family file."""
    recs, d = ixf_parse.parse(path)
    for r in recs:
        body = d[r["offset"]:r["offset"] + r["size"]]
        if city_parse.is_compressed_payload(body):
            plain, _info = city_parse.parse_payload(body)
            return body[city_parse.HDR:], plain
    raise SystemExit("%s: no compressed payload" % path)


def cmd_tokens(path, limit):
    stream, plain = city_stream(path)
    toks, out = tokens(stream)
    assert out == plain, "tokenizer disagrees with qfs.decompress"
    print("%s: %d stream bytes -> %d plaintext, %d tokens"
          % (os.path.basename(path), len(stream), len(out), len(toks)))
    hist = {}
    for t in toks:
        hist[t["form"]] = hist.get(t["form"], 0) + 1
    print("forms: %s" % hist)
    for t in toks[:limit]:
        print("  +%-8d form %-3s lit %-3d off %-7d len %-5d" %
              (t["at"], t["form"], t["lit"], t["off"], t["len"]))
    return 0


def cmd_probe(path, limit, verify=0):
    """Measure the original encoder's choices against an exhaustive search."""
    stream, plain = city_stream(path)
    toks, out = tokens(stream)
    assert out == plain

    matches = [t for t in toks if t["len"]]
    if verify:
        # The fast matcher is the instrument; check it against the exhaustive one before
        # trusting a single number it produces.
        bad = 0
        for t in matches[:verify]:
            pos = t["outpos"] + t["lit"]
            a = longest_match(plain, pos)[:2]
            b = longest_match_fast(plain, pos)[:2]
            if a != b:
                bad += 1
                if bad <= 5:
                    print("  MATCHER DISAGREES @%d: exhaustive %s, fast %s" % (pos, a, b))
        print("  matcher cross-check: %d of %d positions disagree" % (bad, min(verify, len(matches))))
        if bad:
            return 1

    # Sample across the WHOLE stream, not just its head: the first tokens all sit in the
    # first section (SIMDIRT terrain) and are not representative of the file.
    step = max(1, len(matches) // limit)
    sample = matches[::step][:limit]

    n = greedy = nearest = lazy_better = far = 0
    shortfall, miss_off = {}, []
    for t in sample:
        pos = t["outpos"] + t["lit"]
        best, boff, _eq = longest_match_fast(plain, pos)
        n += 1
        if t["len"] == best:
            greedy += 1
            if t["off"] == boff:
                nearest += 1
            elif len(miss_off) < 8:
                miss_off.append((t["len"], t["off"], boff))
        else:
            shortfall[best - t["len"]] = shortfall.get(best - t["len"], 0) + 1
        if t["off"] > MAX_OFF_3:
            far += 1
        nxt, _o, _e = longest_match_fast(plain, pos + 1)
        if nxt > t["len"] + 1:
            lazy_better += 1

    print("%s -- %d matches probed (longest ENCODABLE match as the reference)"
          % (os.path.basename(path), n))
    print("  chose the LONGEST encodable match : %d (%.1f%%)" % (greedy, 100.0 * greedy / max(n, 1)))
    print("  ...and the NEAREST such offset    : %d (%.1f%%)" % (nearest, 100.0 * nearest / max(n, 1)))
    print("  a longer match existed 1 byte on  : %d (%.1f%%)" % (lazy_better, 100.0 * lazy_better / max(n, 1)))
    print("  used an offset > %d (form 4 only) : %d" % (MAX_OFF_3, far))
    if shortfall:
        print("  shortfall (bytes missed -> count): %s"
              % sorted(shortfall.items(), key=lambda kv: -kv[1])[:8])
    if miss_off:
        print("  longest but NOT nearest (len, chosen off, nearest off): %s" % miss_off)
    return 0


def cmd_compress(path, quick=1):
    """Re-encode every city-family file's payload and diff against the shipped stream."""
    ok = bad = 0
    for f in city_parse.walk(path):
        stream, plain = city_stream(f)
        got = compress_stream(plain, quick)
        same = got == stream
        ok += same
        bad += not same
        note = "IDENTICAL" if same else "DIFFERS (%d vs %d bytes)" % (len(got), len(stream))
        print("%-36s %10d -> %9d  %s" % (os.path.basename(f)[:36], len(plain), len(got), note))
    print()
    print("QFS re-encode: %d/%d byte-identical (quick=%d)" % (ok, ok + bad, quick))
    return 1 if bad else 0


def cmd_selftest(target, limit=None, quick=1):
    """Re-encode every QFS stream under `target` and diff against the shipped bytes.

    Roadmap gate T2 asks each proven-write format for a `--selftest` that round-trips the shipped
    corpus and reports `N/N`. For QFS that corpus is TWO populations, and only one of them had
    ever been tested:

      - **city payloads** — 59 streams, already known byte-identical at `quick = 1`
      - **sprite records** — tens of thousands of streams inside the `.DAT` archives, which this
        project had only ever DECOMPRESSED

    They are reported separately on purpose. If the sprite streams disagree, that is a real
    finding about the shipped data (a different encoder mode, or a different tool) and not a bug
    to average away into one number.
    """
    import city_parse                                        # noqa: PLC0415 - CLI path only
    tot = {"city_ok": 0, "city_bad": 0, "spr_ok": 0, "spr_bad": 0}
    diffs = []

    for p in city_parse.walk(os.path.join(target, "Cities") if os.path.isdir(
            os.path.join(target, "Cities")) else target):
        try:
            stream, plain = city_stream(p)
        except SystemExit:
            continue
        got = compress_stream(plain, quick)
        if got == stream:
            tot["city_ok"] += 1
        else:
            tot["city_bad"] += 1
            diffs.append(("city", os.path.basename(p), len(got), len(stream)))

    for path in qfs.archives(target):
        try:
            records, d = ixf_parse.parse(path)
        except ixf_parse.IxfError:
            continue
        for idx, r in enumerate(records):
            if r["type"] != qfs.TYPE_PIXELS:
                continue
            if limit is not None and tot["spr_ok"] + tot["spr_bad"] >= limit:
                break
            pay = d[r["offset"]:r["offset"] + r["size"]]
            try:
                kind, out, info = qfs.decode_record(pay)
            except Exception:                                # noqa: BLE001 - skip, not mask
                continue
            if kind != "qfs" or out is None:
                continue
            orig = pay[info["stream_at"]:info["stream_at"] + info["consumed"]]
            got = compress_stream(out, quick)
            if got == orig:
                tot["spr_ok"] += 1
            else:
                tot["spr_bad"] += 1
                if len(diffs) < 12:
                    diffs.append(("sprite", "%s rec %d" % (os.path.basename(path), idx),
                                  len(got), len(orig)))

    print("QFS re-encode selftest (quick=%d)" % quick)
    print("  city payloads : %d/%d byte-identical"
          % (tot["city_ok"], tot["city_ok"] + tot["city_bad"]))
    print("  sprite streams: %d/%d byte-identical"
          % (tot["spr_ok"], tot["spr_ok"] + tot["spr_bad"]))
    if diffs:
        print()
        print("  first differences (kind, where, ours vs shipped bytes):")
        for k, w, a, b in diffs[:12]:
            print("    %-7s %-44s %d vs %d" % (k, w[:44], a, b))
    return 1 if (tot["city_bad"] or tot["spr_bad"]) else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 40
    verify = int(argv[argv.index("--verify") + 1]) if "--verify" in argv else 0
    if "--selftest" in argv:
        lim = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
        return cmd_selftest(path, lim, 0 if "--full" in argv else 1)
    if "--compress" in argv:
        return cmd_compress(path, 0 if "--full" in argv else 1)
    if "--probe" in argv:
        return cmd_probe(path, limit, verify)
    return cmd_tokens(path, limit)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
