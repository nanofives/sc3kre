#!/usr/bin/env python3
r"""network_layer.py - reader AND writer for the SIMNTWRK network layer of a saved SimCity 3000 city.

The auto-tiled road/rail/etc. networks are persisted in GZCOM save group 0x2147c2dd as a
*sparse* list of occupied tiles. This decodes them to per-tile (x, y, z, pieceId, state,
network) so a tiling-rule edit can be scored on the SAVED FILE, camera- and pixel-independent
(the piece id at occupant +8 is the rule-resolved render piece, baked at build time).

Format spec (all little-endian), decoded and validated 2026-08-25:
  group 0x2147c2dd, one IXF record per network keyed by IXF *instance*:
    instance 0 = header : 4x u32 (count_net0, count_net1, count_net2, version=1)   [save FUN_10012dff]
    instance 1 = road   : count0 tile records                                       [save FUN_10012fc3]
    instance 2 = rail   : count1 tile records
    instance 3 = net[2] : count2 tile records (omitted if 0 tiles)
  each section is preceded by the 8-byte SIMCITY object frame (u16 ver, u8 flags, u8 extra,
  u32 0xDEADBEEF); the header/tile bytes follow it. Measured across all 68 shipped city-family
  files: the frame is ALWAYS the 8 bytes `04 00 02 00 ef be ad de` (ver 4, flags 2, extra 0),
  the tile payload is ALWAYS an exact multiple of 8 (no trailing bytes), and the header counts
  ALWAYS equal the decoded tile counts. Section type is 0x206c6e7c.
  tile record = 8 bytes = two u32:
    word0 (occupant +4, coord)  [CONFIRMED @0x1000d44f]:
      x = w0 & 0x7ff ; y = (w0>>11) & 0x7ff ; z = (w0>>22) & 0xff ; flg = (w0>>30) & 3
    word1 (occupant +8, piece)  [CONFIRMED @0x1000d594]:
      pieceId = w1 & 0xffff  (prop 0x6355941d) ; state = w1 >> 16 (orientation/variant bits)
  road vs rail is the IXF instance index only; nothing inside a record distinguishes them.

  ⚠️ `z` (bits 22..29 of word0) is the tile's TERRAIN ELEVATION, not zero: measured z=69 for
  Farmsville roads, z=32 for Berlin. A planted tile whose z does not match the ground height at
  (x,y) will not sit on the terrain. `flg` (bits 30..31) takes values 0..3 across shipped tiles
  (slope/orientation). Neither has a decoded per-value meaning yet, so the writer NEVER guesses
  them: add_tile() requires z explicitly and defaults flg to 0, and every writer path preserves
  the exact z/flg of a tile it did not create.

Validation target: Cities\Farmsville.sc3 (N=192) -> road 2232 tiles (1041x id29 straight,
37x id11203 curve), rail 545 tiles. Cross-checked against Apps\Res\TilingRules\*_Set.txt.

--- WRITER (NetworkEditor) ------------------------------------------------------------------
The writer stands on city_write.City, whose whole-file re-emit is proven byte-identical on all
59 shipped city files (city_write --selftest) and L0-L4 by city_roundtrip. The network sections
are carried by City as raw section bytes; the editor decodes those, mutates the tile list, then
re-packs `frame (verbatim) + packed tiles` and updates the header counts. A no-op edit therefore
reproduces every section byte-for-byte and the whole file byte-for-byte -- which is provable with
ZERO game runs (network_layer.py --selftest). See the HONEST LIMITS on NetworkEditor.

Usage:
  py -3.12 network_layer.py <city.sc3>                 # per-network tile count + piece histogram
  py -3.12 network_layer.py <city.sc3> --tiles [--net road|rail|2]   # per-tile CSV to stdout
  py -3.12 network_layer.py --diff <baseline.sc3> <after.sc3>        # tiles added/removed/changed
  py -3.12 network_layer.py --selftest [<dir>]         # byte-identical no-op round-trip (no game)
  py -3.12 network_layer.py --selftest-edit [<file>]   # edit -> save -> reload consistency (no game)
  py -3.12 network_layer.py <city.sc3> --set-piece NET,X,Y=PIECE[,STATE] [...] -o <out>
  py -3.12 network_layer.py <city.sc3> --remove-tile NET,X,Y [...] -o <out>
  py -3.12 network_layer.py <city.sc3> --add-tile NET,X,Y,PIECE,STATE,Z[,FLG] [...] -o <out>
"""
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse
import city_parse

NET_GROUP = 0x2147c2dd
NET_NAME = {1: "road", 2: "rail", 3: "net2"}
NAME_NET = {v: k for k, v in NET_NAME.items()}


def _decode_tiles(body, ent):
    """-> list of (x, y, z, flg, pieceId, state) for one network section entry."""
    s = ent["abs"] + ent["frame"]["len"]
    end = ent["abs"] + ent["size"]
    n = (end - s) // 8
    out = []
    for i in range(n):
        w0, w1 = struct.unpack_from("<II", body, s + 8 * i)
        x = w0 & 0x7ff
        y = (w0 >> 11) & 0x7ff
        z = (w0 >> 22) & 0xff
        flg = (w0 >> 30) & 3
        piece = w1 & 0xffff
        state = w1 >> 16
        out.append((x, y, z, flg, piece, state))
    return out


def read_networks(path):
    """-> {instance: [(x,y,z,flg,pieceId,state), ...]} for instances 1/2/3, plus 'header'."""
    records, d = ixf_parse.parse(path)
    nets = {}
    header = None
    for r in records:
        raw = d[r["offset"]:r["offset"] + r["size"]]
        if not city_parse.is_compressed_payload(raw):
            continue
        try:
            body, _ = city_parse.parse_payload(raw)
        except city_parse.CityError:
            continue
        _, ents = city_parse.parse_sections(body)
        got = [e for e in ents if e["group"] == NET_GROUP]
        if not got:
            continue
        for e in got:
            inst = e["instance"]
            if inst == 0:
                s = e["abs"] + (e["frame"]["len"] if e["frame"] else 0)
                header = struct.unpack_from("<4I", body, s)
            elif e["frame"]:
                nets[inst] = _decode_tiles(body, e)
    return nets, header


# 4-neighbour mask, final.txt convention: W=bit0, N=bit1, E=bit2, S=bit3.
# World dirs = SIMNTWRK offset table 0x10032134: 0=(-1,0)W 1=(0,-1)N 2=(+1,0)E 3=(0,+1)S
# (state_facing.py:26). Straight positions: 5 = W+E, 10 = N+S.
_DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]
STRAIGHT_MASKS = {5, 10}


def tile_masks(tiles):
    """-> {(x,y): mask} over a road tile set (same-network 4-neighbour occupancy)."""
    occ = {(t[0], t[1]) for t in tiles}
    masks = {}
    for (x, y) in occ:
        m = 0
        for i, (dx, dy) in enumerate(_DIRS):
            if (x + dx, y + dy) in occ:
                m |= (1 << i)
        masks[(x, y)] = m
    return masks


def mask_piece_xtab(tiles):
    """-> {mask: Counter(pieceId)} for a road tile set."""
    masks = tile_masks(tiles)
    piece = {(t[0], t[1]): t[4] for t in tiles}
    xtab = {}
    for xy, m in masks.items():
        xtab.setdefault(m, Counter())[piece[xy]] += 1
    return xtab


def cmd_masks(path, net="road"):
    nets, _ = read_networks(path)
    inst = NAME_NET.get(net, 1)
    tiles = nets.get(inst, [])
    xtab = mask_piece_xtab(tiles)
    print(f"# {path}  [{net}]  mask -> pieceId histogram (straight masks 5,10 flagged)")
    for m in sorted(xtab):
        tag = "  <-- STRAIGHT" if m in STRAIGHT_MASKS else ""
        top = ", ".join(f"{p}x{c}" for p, c in xtab[m].most_common(4))
        print(f"  mask {m:>2} (0b{m:04b}): {top}{tag}")


def _fmt_hist(tiles, top=None):
    h = Counter(t[4] for t in tiles)
    items = sorted(h.items(), key=lambda kv: -kv[1])
    if top:
        items = items[:top]
    return h, items


def cmd_summary(path):
    nets, header = read_networks(path)
    print(f"# {path}")
    print(f"header (count_road, count_rail, count_net2, version) = {header}")
    for inst in sorted(nets):
        tiles = nets[inst]
        name = NET_NAME.get(inst, f"inst{inst}")
        xs = [t[0] for t in tiles]; ys = [t[1] for t in tiles]
        uniq = len({(t[0], t[1]) for t in tiles})
        _, items = _fmt_hist(tiles, top=12)
        print(f"\n== {name} (instance {inst}): {len(tiles)} tiles, "
              f"{uniq} unique (x,y), x[{min(xs)}..{max(xs)}] y[{min(ys)}..{max(ys)}] ==")
        for pid, c in items:
            print(f"   piece {pid:>6} (0x{pid:04x}) : {c}")


def cmd_tiles(path, net=None):
    nets, _ = read_networks(path)
    print("net,x,y,z,pieceId,state")
    for inst in sorted(nets):
        name = NET_NAME.get(inst, f"inst{inst}")
        if net and name != net:
            continue
        for (x, y, z, flg, piece, state) in sorted(nets[inst]):
            print(f"{name},{x},{y},{z},{piece},{state}")


def cmd_diff(base_path, after_path):
    nb, _ = read_networks(base_path)
    na, _ = read_networks(after_path)
    for inst in sorted(set(nb) | set(na)):
        name = NET_NAME.get(inst, f"inst{inst}")
        base = {(t[0], t[1]): t for t in nb.get(inst, [])}
        after = {(t[0], t[1]): t for t in na.get(inst, [])}
        added = sorted(set(after) - set(base))
        removed = sorted(set(base) - set(after))
        changed = sorted(k for k in (set(after) & set(base))
                         if after[k][4] != base[k][4] or after[k][5] != base[k][5])
        if not (added or removed or changed):
            continue
        print(f"\n== {name} (instance {inst}) : +{len(added)} -{len(removed)} ~{len(changed)} ==")
        if added:
            ph = Counter(after[k][4] for k in added)
            print(f"  ADDED tiles piece histogram: {dict(sorted(ph.items()))}")
            # classify each added tile by its 4-neighbour mask over the AFTER road set,
            # so straight-position tiles (mask 5/10) can be checked against their piece
            masks = tile_masks(na.get(inst, []))
            straight = [(k, after[k][4]) for k in added if masks.get(k) in STRAIGHT_MASKS]
            if straight:
                sph = Counter(p for _, p in straight)
                print(f"  ADDED STRAIGHT-mask (5/10) tiles: {len(straight)}, "
                      f"piece histogram {dict(sorted(sph.items()))}")
            for k in added:
                x, y, z, flg, piece, state = after[k]
                m = masks.get(k)
                st = " STRAIGHT" if m in STRAIGHT_MASKS else ""
                print(f"    +({x:>3},{y:>3}) mask {m:>2}{st:9} piece {piece:>6} (0x{piece:04x}) "
                      f"state 0x{state:x} z{z}")
        for k in changed:
            x, y = k
            print(f"    ~({x:>3},{y:>3}) piece {base[k][4]} -> {after[k][4]}")
        if removed:
            print(f"  REMOVED {len(removed)} tiles")


# --- WRITER ---------------------------------------------------------------------------------
import city_write  # noqa: E402  (kept next to the writer it depends on)

SECTION_TYPE = 0x206c6e7c          # every network section carries this type [measured 68/68]
HEADER_VERSION = 1                 # header 4th u32, == 1 in every shipped file
FRAME_BYTES = bytes.fromhex("04000200efbeadde")   # ver 4, flags 2, extra 0, DEADBEEF (68/68)
COORD_MAX = 0x7ff                  # x,y are 11 bits -> 0..2047 (covers every supported map size)
Z_MAX = 0xff                       # z is 8 bits
PIECE_MAX = 0xffff                 # pieceId is 16 bits
STATE_MAX = 0xffff                 # state is the high 16 bits of word1


class NetworkError(Exception):
    pass


class Tile:
    """One occupied network cell. Mirrors the 8-byte record exactly; nothing is derived."""

    __slots__ = ("x", "y", "z", "flg", "piece", "state")

    def __init__(self, x, y, z, flg, piece, state):
        self.x, self.y, self.z, self.flg = x, y, z, flg
        self.piece, self.state = piece, state

    def key(self):
        return (self.x, self.y)

    def pack(self):
        w0 = ((self.x & COORD_MAX) | ((self.y & COORD_MAX) << 11)
              | ((self.z & Z_MAX) << 22) | ((self.flg & 3) << 30))
        w1 = (self.piece & PIECE_MAX) | ((self.state & STATE_MAX) << 16)
        return struct.pack("<II", w0, w1)

    def __repr__(self):
        return ("Tile(x=%d, y=%d, z=%d, flg=%d, piece=%d(0x%04x), state=0x%x)"
                % (self.x, self.y, self.z, self.flg, self.piece, self.piece, self.state))


def _frame_len(data):
    """Length of the SIMCITY object frame at the start of a network section's bytes."""
    fr = city_parse.read_frame(data, 0)
    if fr is None:
        raise NetworkError("network section has no valid object frame (no 0xDEADBEEF)")
    return fr["len"]


class NetworkEditor:
    r"""Edit the road/rail/net2 tiles of a saved city, then write a valid file back.

    Built on city_write.City, so the container/QFS/header machinery is the same code proven
    byte-identical on all 59 shipped cities. This class only touches the network sections
    (group 0x2147c2dd); everything else in the file rides through City untouched.

        e = NetworkEditor.load("Cities/Farmsville.sc3")
        e.tiles("road")                       # list[Tile], in file order
        e.get("road", 146, 160)               # the Tile at (146,160) or None
        e.set_piece("road", 146, 160, 11203)  # re-skin an existing tile (keeps z/flg/state)
        e.add_tile("road", 146, 173, piece=29, state=0, z=69)   # plant a new tile
        e.remove_tile("road", 146, 172)
        e.save("out.sc3")

    HONEST LIMITS -- read before trusting an edited file in the game:
      1. A modified network layer has NEVER been loaded by the game. The no-op round-trip is
         proven byte-identical offline (--selftest); that is a statement about the container and
         the record encoding, NOT about whether the sim accepts edited tiles.
      2. `z` (terrain elevation) is NOT guessed. add_tile() requires it. Planting road at (x,y)
         with the wrong z puts the tile off the ground surface. bigcities must read the ground
         height from the terrain layer; this tool will not invent it.
      3. `flg` and `state` have no fully decoded per-value meaning. add_tile() defaults flg=0 and
         requires state; set_piece() preserves the existing state unless you pass one. A drawn
         road's piece/state is normally chosen by the SimpleRules tiler at build time
         [CONFIRMED @0x1001547b]; writing a raw (piece,state) here BYPASSES that tiler, so a
         hand-planted run of tiles will not auto-tile its neighbours -- you are placing exact
         pieces, not asking the game to re-tile.
      4. Adjacency/validity is not enforced against the *_Set.txt allowed-piece list. Writing a
         piece a network does not allow will (per T1) fail the render validity scan
         [CONFIRMED @0x1001a7f7] and not draw. Use a piece the target network already uses.
      5. Creating the FIRST tile of a previously-empty network (no instance section on disk)
         synthesises a new section from the header's own frame bytes. This is structurally valid
         and re-reads correctly (--selftest-edit), but has the same "never loaded by the game"
         caveat as everything else here.
    """

    def __init__(self, city):
        self.city = city
        self._header = city.section(NET_GROUP, 0, SECTION_TYPE)
        if self._header is None:
            raise NetworkError("no network header section {0x206c6e7c, 0x2147c2dd, inst 0}")
        hflen = _frame_len(self._header.data)
        counts = struct.unpack_from("<4I", self._header.data, hflen)
        self._version = counts[3]
        self._frame = bytes(self._header.data[:hflen])   # reused for any new tile section
        # decode existing tile sections; instances 1,2,3 map to net indices 1,2,3
        self._nets = {}      # inst -> list[Tile]
        for inst in (1, 2, 3):
            sec = city.section(NET_GROUP, inst, SECTION_TYPE)
            if sec is None:
                self._nets[inst] = []
                continue
            flen = _frame_len(sec.data)
            body = sec.data[flen:]
            if len(body) % 8 != 0:
                raise NetworkError("network inst %d payload %d bytes, not a multiple of 8"
                                   % (inst, len(body)))
            tiles = []
            for i in range(len(body) // 8):
                w0, w1 = struct.unpack_from("<II", body, 8 * i)
                tiles.append(Tile(w0 & 0x7ff, (w0 >> 11) & 0x7ff, (w0 >> 22) & 0xff,
                                  (w0 >> 30) & 3, w1 & 0xffff, w1 >> 16))
            # cross-check against the declared header count -- the invariant the writer relies on
            if counts[inst - 1] != len(tiles):
                raise NetworkError("header count[%d]=%d disagrees with %d decoded tiles"
                                   % (inst - 1, counts[inst - 1], len(tiles)))
            self._nets[inst] = tiles

    @classmethod
    def load(cls, path):
        return cls(city_write.City.load(path))

    # --- addressing --------------------------------------------------------------------
    @staticmethod
    def _inst(net):
        if isinstance(net, int):
            if net in (1, 2, 3):
                return net
            raise NetworkError("network index %d is not 1/2/3" % net)
        key = str(net).lower()
        if key in NAME_NET:
            return NAME_NET[key]
        raise NetworkError("unknown network %r (use road/rail/net2 or 1/2/3)" % net)

    def tiles(self, net):
        return self._nets[self._inst(net)]

    def _index(self, net):
        """(inst, {(x,y): position}) for the current tile list of a network."""
        inst = self._inst(net)
        return inst, {t.key(): i for i, t in enumerate(self._nets[inst])}

    def get(self, net, x, y):
        inst, idx = self._index(net)
        pos = idx.get((x, y))
        return self._nets[inst][pos] if pos is not None else None

    # --- edits -------------------------------------------------------------------------
    def set_piece(self, net, x, y, piece, state=None):
        """Change an existing tile's piece (and optionally state). Keeps x/y/z/flg."""
        t = self.get(net, x, y)
        if t is None:
            raise NetworkError("no %s tile at (%d,%d) to re-skin" % (net, x, y))
        _check_piece(piece)
        t.piece = piece
        if state is not None:
            _check_state(state)
            t.state = state
        return t

    def add_tile(self, net, x, y, piece, state, z, flg=0):
        """Plant a new tile. z is REQUIRED (terrain elevation) and is never guessed."""
        _check_xy(x, y)
        _check_piece(piece)
        _check_state(state)
        if not (0 <= z <= Z_MAX):
            raise NetworkError("z %d outside 0..%d" % (z, Z_MAX))
        if not (0 <= flg <= 3):
            raise NetworkError("flg %d outside 0..3" % flg)
        inst, idx = self._index(net)
        if (x, y) in idx:
            raise NetworkError("%s tile already exists at (%d,%d); use set_piece" % (net, x, y))
        t = Tile(x, y, z, flg, piece, state)
        self._nets[inst].append(t)
        return t

    def remove_tile(self, net, x, y):
        inst, idx = self._index(net)
        pos = idx.get((x, y))
        if pos is None:
            raise NetworkError("no %s tile at (%d,%d) to remove" % (net, x, y))
        return self._nets[inst].pop(pos)

    # --- emit --------------------------------------------------------------------------
    def flush(self):
        """Write the current tile lists back into the City's network sections + header.

        A network with tiles gets `frame + packed records`; one that drops to zero tiles has
        its section removed, matching the shipped format (empty networks omit the tile section).
        The header's three counts are rewritten from the live tile-list lengths.
        """
        for inst in (1, 2, 3):
            tiles = self._nets[inst]
            sec = self.city.section(NET_GROUP, inst, SECTION_TYPE)
            if tiles:
                data = bytearray(self._frame)
                for t in tiles:
                    data += t.pack()
                if sec is None:
                    order = max((s.order for s in self.city.sections), default=-1) + 1
                    sec = city_write.Section(SECTION_TYPE, NET_GROUP, inst, data, order)
                    self.city.sections.append(sec)
                else:
                    sec.data = data
            elif sec is not None:
                self.city.sections.remove(sec)
        hflen = len(self._frame)
        hdr = bytearray(self._header.data[:hflen])
        hdr += struct.pack("<4I", len(self._nets[1]), len(self._nets[2]),
                           len(self._nets[3]), self._version)
        self._header.data = hdr

    def to_bytes(self):
        self.flush()
        return self.city.to_bytes()

    def save(self, path):
        self.flush()
        return self.city.save(path)

    def roundtrip_identical(self):
        """True if flush()+re-emit reproduces the original file byte-for-byte (no-op check)."""
        return self.to_bytes() == self.city._raw


def _check_xy(x, y):
    if not (0 <= x <= COORD_MAX and 0 <= y <= COORD_MAX):
        raise NetworkError("(%d,%d) outside 0..%d" % (x, y, COORD_MAX))


def _check_piece(piece):
    if not (0 <= piece <= PIECE_MAX):
        raise NetworkError("piece %d outside 0..%d" % (piece, PIECE_MAX))


def _check_state(state):
    if not (0 <= state <= STATE_MAX):
        raise NetworkError("state %d outside 0..%d" % (state, STATE_MAX))


# --- offline verification (no game runs) ----------------------------------------------------

def cmd_selftest(target):
    """Load -> flush with NO edits -> re-emit; assert byte-identical whole file, all cities."""
    ok = bad = skip = 0
    for p in city_parse.walk(target):
        name = os.path.basename(p)[:36]
        try:
            city = city_write.City.load(p)
        except Exception as e:                                        # noqa: BLE001
            print("%-36s SKIP (city load: %s)" % (name, e))
            skip += 1
            continue
        if city.section(NET_GROUP, 0, SECTION_TYPE) is None:
            print("%-36s SKIP (no network layer)" % name)
            skip += 1
            continue
        try:
            e = NetworkEditor(city)
            same = e.roundtrip_identical()
        except Exception as ex:                                       # noqa: BLE001
            print("%-36s ERROR %s: %s" % (name, type(ex).__name__, ex))
            bad += 1
            continue
        ok += same
        bad += not same
        print("%-36s %s" % (name, "identical" if same else "DIFFERS"))
    print()
    print("network no-op round-trip: %d/%d byte-identical (%d skipped)" % (ok, ok + bad, skip))
    print("Proves the writer reproduces the container AND the network encoding exactly. It does")
    print("NOT prove the game accepts an EDITED network -- that has never been tested.")
    return 1 if bad else 0


def cmd_selftest_edit(target):
    """Edit -> save -> reload consistency, in memory, no game. Exercises every writer path."""
    fails = 0
    for p in city_parse.walk(target):
        name = os.path.basename(p)[:36]
        try:
            base = city_write.City.load(p)
        except Exception:                                             # noqa: BLE001
            continue
        if base.section(NET_GROUP, 0, SECTION_TYPE) is None:
            continue
        e0 = NetworkEditor(city_write.City.load(p))
        # pick a network that actually has tiles to test set/remove; road preferred
        net = next((n for n in (1, 2, 3) if e0.tiles(n)), None)
        if net is None:
            # empty city: exercise section CREATION only
            fails += _check_case(name + " [create]", p, _edit_create)
            continue
        fails += _check_case(name + " [set]", p, lambda e: _edit_setpiece(e, net))
        fails += _check_case(name + " [add]", p, lambda e: _edit_add(e, net))
        fails += _check_case(name + " [remove]", p, lambda e: _edit_remove(e, net))
    print()
    print("edit -> save -> reload: %d failure(s)" % fails)
    return 1 if fails else 0


def _reload_editor(data):
    """Parse an in-memory .sc3 byte string back into a NetworkEditor (no temp file)."""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".sc3")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return NetworkEditor.load(tmp), read_networks(tmp)
    finally:
        os.remove(tmp)


def _check_case(label, path, mutate):
    try:
        e = NetworkEditor.load(path)
        expect = mutate(e)                       # returns (net, verify-fn taking reloaded tiles)
        data = e.to_bytes()
        # container must still be valid: re-parse whole file
        re_edit, (nets, header) = _reload_editor(data)
        ok, why = expect(nets, header)
        print("  %-46s %s" % (label, "ok" if ok else "MISMATCH: " + why))
        return 0 if ok else 1
    except Exception as ex:                                           # noqa: BLE001
        print("  %-46s ERROR %s: %s" % (label, type(ex).__name__, ex))
        return 1


def _edit_setpiece(e, net):
    t = e.tiles(net)[0]
    x, y, z, flg, state = t.x, t.y, t.z, t.flg, t.state
    newpiece = (t.piece + 1) & 0xffff
    e.set_piece(net, x, y, newpiece)
    n0 = len(e.tiles(net))

    def verify(nets, header):
        got = {(u[0], u[1]): u for u in nets[net]}
        if (x, y) not in got:
            return False, "edited tile vanished"
        u = got[(x, y)]
        if u[4] != newpiece:
            return False, "piece %d != %d" % (u[4], newpiece)
        if (u[2], u[3], u[5]) != (z, flg, state):
            return False, "z/flg/state changed by a set_piece"
        if len(nets[net]) != n0:
            return False, "tile count changed by a set_piece"
        return True, ""
    return verify


def _edit_add(e, net):
    # plant at the max-coord corner + a bit, guaranteed empty
    tiles = e.tiles(net)
    x = min(2047, max(t.x for t in tiles) + 1)
    y = max(t.y for t in tiles)
    z = tiles[0].z
    n0 = len(tiles)
    e.add_tile(net, x, y, piece=tiles[0].piece, state=0, z=z, flg=0)

    def verify(nets, header):
        if len(nets[net]) != n0 + 1:
            return False, "count %d != %d" % (len(nets[net]), n0 + 1)
        got = {(u[0], u[1]): u for u in nets[net]}
        if (x, y) not in got:
            return False, "planted tile missing"
        if header[net - 1] != n0 + 1:
            return False, "header count not incremented"
        return True, ""
    return verify


def _edit_remove(e, net):
    t = e.tiles(net)[len(e.tiles(net)) // 2]
    x, y = t.x, t.y
    n0 = len(e.tiles(net))
    e.remove_tile(net, x, y)

    def verify(nets, header):
        if len(nets[net]) != n0 - 1:
            return False, "count %d != %d" % (len(nets[net]), n0 - 1)
        got = {(u[0], u[1]) for u in nets[net]}
        if (x, y) in got:
            return False, "removed tile still present"
        if header[net - 1] != n0 - 1:
            return False, "header count not decremented"
        return True, ""
    return verify


def _edit_create(e):
    # a city whose road/rail/net2 are all empty: create the first road tile
    e.add_tile(1, 5, 5, piece=29, state=0, z=32, flg=0)

    def verify(nets, header):
        if header[0] != 1:
            return False, "header road count %d != 1" % header[0]
        if len(nets.get(1, [])) != 1:
            return False, "road section not created"
        u = nets[1][0]
        if (u[0], u[1], u[4]) != (5, 5, 29):
            return False, "created tile wrong: %r" % (u,)
        return True, ""
    return verify


def _apply_edits(e, argv):
    n = 0
    for spec in _multi(argv, "--set-piece"):
        lhs, _, rhs = spec.partition("=")
        net, x, y = lhs.split(",")
        parts = rhs.split(",")
        piece = int(parts[0], 0)
        state = int(parts[1], 0) if len(parts) > 1 else None
        e.set_piece(net.strip(), int(x), int(y), piece, state)
        n += 1
    for spec in _multi(argv, "--remove-tile"):
        net, x, y = spec.split(",")
        e.remove_tile(net.strip(), int(x), int(y))
        n += 1
    for spec in _multi(argv, "--add-tile"):
        f = spec.split(",")
        net, x, y, piece, state, z = f[0], f[1], f[2], f[3], f[4], f[5]
        flg = int(f[6], 0) if len(f) > 6 else 0
        e.add_tile(net.strip(), int(x), int(y), int(piece, 0), int(state, 0), int(z, 0), flg)
        n += 1
    return n


def _multi(argv, flag):
    """All comma-bearing tokens after each occurrence of `flag`, up to the next --option."""
    out = []
    i = 0
    while i < len(argv):
        if argv[i] == flag:
            j = i + 1
            while j < len(argv) and not argv[j].startswith("--") and argv[j] != "-o":
                if "," in argv[j]:
                    out.append(argv[j])
                j += 1
            i = j
        else:
            i += 1
    return out


def main(argv):
    if "--selftest" in argv:
        i = argv.index("--selftest")
        target = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "Cities"
        return cmd_selftest(target)
    if "--selftest-edit" in argv:
        i = argv.index("--selftest-edit")
        target = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "Cities"
        return cmd_selftest_edit(target)
    if "--diff" in argv:
        i = argv.index("--diff")
        cmd_diff(argv[i + 1], argv[i + 2])
        return 0
    if any(f in argv for f in ("--set-piece", "--add-tile", "--remove-tile")):
        if "-o" not in argv:
            print("edits require -o <out>", file=sys.stderr)
            return 2
        path = argv[1]
        out = argv[argv.index("-o") + 1]
        e = NetworkEditor.load(path)
        n = _apply_edits(e, argv)
        size = e.save(out)
        print("%d edit(s) -> %s (%d bytes)" % (n, out, size))
        print("UNTESTED: no modified network layer has ever been loaded by the game.")
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    if "--tiles" in argv:
        net = argv[argv.index("--net") + 1] if "--net" in argv else None
        cmd_tiles(path, net)
    elif "--masks" in argv:
        net = argv[argv.index("--net") + 1] if "--net" in argv else "road"
        cmd_masks(path, net)
    else:
        cmd_summary(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
