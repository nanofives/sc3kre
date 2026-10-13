#!/usr/bin/env python3
r"""ixf_insert.py - write new .IXF containers and append records to existing ones (netmod, 2026-10-12).

Two operations the shipped tools lacked (NETMOD_CAPABILITY_MAP section 7, gap 2):

  new_container(records)   a fresh container in the shipped shape
  append(data, records)    add records to an existing container, every old byte kept

Shipped shape, measured on OccupantAttribs_2/_German, CSAttrib_2, TrBlkAtt, Roads_2.DAT (2026-10-12):
the index reserves 0x5000 bytes (1,024 twenty-byte slots) after the 4-byte magic, so the first payload
sits at 0x5004; the live slots are followed by one all-zero terminator slot (the reader stops on a zero
key triple, GZResourceD 0x1000ca78 via ixf_parse). A record is (group, instance, type, payload); the
game's key {type, group, instance} is an index lookup on those three fields.

append() writes the new slots where the terminator was, a new terminator after them, and the payloads at
the end of the file. It refuses when the reserved index has no room (it never moves old payloads), so
every pre-existing payload keeps its offset and its bytes. check_append() proves that on the result.

  py -3.12 re/tools/netmod/ixf_insert.py --selftest <file.IXF> [...]   # append 2 copies to each, verify
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ixf_parse  # noqa: E402

MAGIC = ixf_parse.MAGIC
REC = ixf_parse.REC
FIRST_PAYLOAD = 0x5004           # shipped containers: 4-byte magic + 0x5000 reserved index bytes


class IxfInsertError(Exception):
    pass


def new_container(records):
    """records: [(group, instance, type, payload_bytes)] -> container bytes in the shipped shape."""
    n = len(records)
    first = FIRST_PAYLOAD if 4 + (n + 1) * REC <= FIRST_PAYLOAD else 4 + (n + 1) * REC
    out = bytearray(struct.pack("<I", MAGIC))
    off = first
    slots = []
    for g, i, t, p in records:
        slots.append((g, i, t, off, len(p)))
        off += len(p)
    for s in slots:
        out += struct.pack("<5I", *s)
    out += b"\x00" * (first - len(out))           # terminator slot + reserved, all zero
    for _, _, _, p in records:
        out += p
    return bytes(out)


def append(d, records):
    """-> new container bytes: d with `records` appended. Old payloads keep offset and bytes."""
    d = bytes(d)
    if struct.unpack_from("<I", d, 0)[0] != MAGIC:
        raise IxfInsertError("not an IXF container")
    slots = ixf_parse.read_index_slots(d)
    if slots[-1][:3] != (0, 0, 0):
        raise IxfInsertError("index has no terminator slot")
    term_at = 4 + (len(slots) - 1) * REC
    live = [s for s in slots[:-1] if s[3] != 0xFFFFFFFF and s[4] != 0xFFFFFFFF]
    first = min(s[3] for s in live) if live else len(d)
    need_end = term_at + (len(records) + 1) * REC
    if need_end > first:
        raise IxfInsertError("reserved index full: %d new slots need up to 0x%x, first payload at 0x%x"
                             % (len(records), need_end, first))
    keys = {s[:3] for s in live}
    out = bytearray(d)
    off = len(out)
    new_slots = []
    for g, i, t, p in records:
        if (g, i, t) in keys:
            raise IxfInsertError("key group 0x%08X instance 0x%08X type 0x%08X already present" % (g, i, t))
        keys.add((g, i, t))
        new_slots.append(struct.pack("<5I", g, i, t, off, len(p)))
        off += len(p)
    blob = b"".join(new_slots) + b"\x00" * REC
    if any(out[term_at:term_at + len(blob)]):
        raise IxfInsertError("bytes after the terminator slot are not zero; refusing to overwrite")
    out[term_at:term_at + len(blob)] = blob
    for _, _, _, p in records:
        out += p
    return bytes(out)


def check_append(old, new, records):
    """-> list of problems (empty = ok): every old record identical, every new one readable."""
    probs = []
    ro, do = _parse(old)
    rn, dn = _parse(new)
    idx = {(r["group"], r["instance"], r["type"]): r for r in rn}
    for r in ro:
        k = (r["group"], r["instance"], r["type"])
        q = idx.get(k)
        if q is None:
            probs.append("old record %r missing" % (k,))
        elif (q["offset"], q["size"]) != (r["offset"], r["size"]) or \
                dn[q["offset"]:q["offset"] + q["size"]] != do[r["offset"]:r["offset"] + r["size"]]:
            probs.append("old record %r changed" % (k,))
    for g, i, t, p in records:
        q = idx.get((g, i, t))
        if q is None:
            probs.append("new record %r not readable" % ((g, i, t),))
        elif dn[q["offset"]:q["offset"] + q["size"]] != p:
            probs.append("new record %r payload differs" % ((g, i, t),))
    if len(rn) != len(ro) + len(records):
        probs.append("record count %d != %d + %d" % (len(rn), len(ro), len(records)))
    return probs


def _parse(d):
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".ixf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(d)
        return ixf_parse.parse(tmp)
    finally:
        os.remove(tmp)


def cmd_selftest(paths):
    fails = 0
    for p in paths:
        with open(p, "rb") as fh:
            d = fh.read()
        recs, _ = ixf_parse.parse(p)
        r0 = recs[0]
        payload = d[r0["offset"]:r0["offset"] + r0["size"]]
        add = [(0x4E3D4E3D, 0x7FFF0000 + k, r0["type"], payload + bytes([k])) for k in range(2)]
        full = len(ixf_parse.read_index_slots(d)) * REC + 4 >= FIRST_PAYLOAD
        try:
            new = append(d, add)
            probs = check_append(d, new, add)
        except IxfInsertError as e:
            probs = [] if full else ["append refused: %s" % e]
            if full:
                print("%-60s refused as designed (index past the 1,024-slot reserve: %s)" % (os.path.basename(p), e))
        fresh = new_container(add)
        rf, df = _parse(fresh)
        if [(r["group"], r["instance"], r["type"], df[r["offset"]:r["offset"] + r["size"]]) for r in rf] != add:
            probs.append("new_container does not read back")
        if not (full and not probs):
            print("%-60s %s" % (os.path.basename(p), "ok" if not probs else "; ".join(probs)))
        fails += bool(probs)
    print("ixf_insert selftest: %d/%d ok" % (len(paths) - fails, len(paths)))
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        sys.exit(cmd_selftest(sys.argv[2:]))
    print(__doc__)
    sys.exit(2)
