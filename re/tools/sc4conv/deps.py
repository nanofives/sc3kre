#!/usr/bin/env python3
r"""deps.py - task sc4props (2026-11-19g): SimCity 4 dependency packs (lot props), read by streaming and indexed once.

A lot's props (lot object kind 1, catalog.buildings) name prop exemplars (type 0x1E) or prop families that live in
the player's dependency downloads, not in the building's own download. The biggest one, the BSC Common Dependencies
Pack V9e, is a 1.7 GB zip holding one 1.64 GB LEX jar (deflated) that holds 168 deflated .dat files
(re/analysis/SC4_FORMATS.md 8.5 and 9). The zip's reader cannot seek inside a deflated member, so this module reads
the jar front to back once, local header by local header (no member of the jar uses a data descriptor: the sizes
are in each local header), inflates one .dat at a time, and keeps only:

  - every prop exemplar and every cohort (their properties, as JSON),
  - where each S3D and FSH entry is: (type, group, instance) -> the .dat's number in the walk.

That index is cached (`<cache>/<pack name>-<size>-<mtime>.idx.json` + `.map.npy`). A conversion then names the
props it needs; `fetch` walks the jar again but inflates only the .dat files that hold their zoom-5 models and
textures, and stores those entries unpacked in `<cache>/entries/` so the next run reads nothing from the pack.

Inputs: an SC4 dependency download as a .zip (holding .jar files and / or .dat files), a .jar, a .dat or a folder of
them (several, separated by os.pathsep or given as a list). SC4 loads plugins in name order and a later file wins on
the same TGI; the walk keeps that rule over the sorted member paths of each input, inputs in the order given.

  py -3.12 re/tools/sc4conv/deps.py index <pack> [--cache DIR]          build / show the index
  py -3.12 re/tools/sc4conv/deps.py find <pack> <prop id hex> ...       what an id resolves to
"""
import json
import os
import struct
import sys
import time
import zipfile
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import exemplar as X  # noqa: E402

DAT_EXT = ('.dat', '.sc4desc', '.sc4lot', '.sc4model')
INDEX_VERSION = 1
T_PROP = 0x1E                                  # exemplar type of a prop
P_TYPE, P_NAME, P_SIZE, P_FAMILY = 0x10, 0x20, 0x27812810, 0x27812870
P_RKT = (0x27812820, 0x27812821, 0x27812822, 0x27812823, 0x27812824, 0x27812825)   # resource key types 0-5
MAP_TYPES = {D.T_S3D: 0, D.T_FSH: 1}
CHUNK = 1 << 22


def default_cache():
    base = os.environ.get('SC4CONV_CACHE') or os.path.join(
        os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.cache'), 'sc4conv')
    return base


# ---------------------------------------------------------------------------------------------- walking a pack
class _Stream:
    """A forward-only byte reader over a file-like object (a deflated zip member read by zipfile)."""

    def __init__(self, f):
        self.f, self.buf, self.pos = f, b'', 0

    def take(self, n):
        parts, have = [], 0
        if self.buf:
            parts.append(self.buf[:n])
            have = len(parts[0])
            self.buf = self.buf[n:]
        while have < n:
            c = self.f.read(max(CHUNK, n - have))
            if not c:
                break
            k = n - have
            parts.append(c[:k])
            have += min(len(c), k)
            if len(c) > k:
                self.buf = c[k:]
        self.pos += have
        return b''.join(parts)

    def skip(self, n):
        if len(self.buf) >= n:
            self.buf = self.buf[n:]
            self.pos += n
            return
        n -= len(self.buf)
        self.pos += len(self.buf)
        self.buf = b''
        while n > 0:
            c = self.f.read(min(CHUNK, n))
            if not c:
                break
            n -= len(c)
            self.pos += len(c)


def _walk_jar_stream(f, label, want=None):
    """Yield (member path, bytes or None) for each DBPF member of a zip read front to back (local headers).
    want(path) -> False skips the member without inflating it (yields None)."""
    s = _Stream(f)
    while True:
        h = s.take(30)
        if len(h) < 30 or h[:4] != b'PK\x03\x04':
            return                                         # central directory (PK\x01\x02) or end
        _v, flag, meth, _t, _d, _crc, cs, us, nl, el = struct.unpack('<HHHHHIIIHH', h[4:30])
        name = s.take(nl).decode('utf-8' if flag & 0x800 else 'cp437')
        s.skip(el)
        if flag & 8:
            raise ValueError('%s: member %s uses a data descriptor, the streaming reader needs sizes in the '
                             'local header' % (label, name))
        if not name.lower().endswith(DAT_EXT) or (want is not None and not want(name)):
            s.skip(cs)
            if name.lower().endswith(DAT_EXT):
                yield name, None
            continue
        raw = s.take(cs)
        if meth == 8:
            data = zlib.decompress(raw, -15)
        elif meth == 0:
            data = raw
        else:
            raise ValueError('%s: member %s compression %d' % (label, name, meth))
        if len(data) != us:
            raise ValueError('%s: member %s inflated to %d bytes, header says %d' % (label, name, len(data), us))
        yield name, data


def _members(src):
    """-> list of (label, kind, opener) units in walk order: each unit yields (path, bytes|None) via walk(unit, want)."""
    out = []
    if isinstance(src, (list, tuple)):
        for s in src:
            out += _members(s)
        return out
    if os.path.isdir(src):
        files = []
        for dp, dn, fn in os.walk(src):
            dn.sort()
            for n in sorted(fn):
                p = os.path.join(dp, n)
                if n.lower().endswith(DAT_EXT + ('.jar', '.zip')):
                    files.append(p)
        for p in files:
            out += _members(p)
        return out
    low = src.lower()
    if low.endswith(DAT_EXT):
        out.append(('file', src, None))
    elif low.endswith(('.zip', '.jar')):
        z = zipfile.ZipFile(src)
        names = sorted(i.filename for i in z.infolist())
        for n in names:
            if n.lower().endswith('.jar'):
                out.append(('zipjar', src, n))
        if any(n.lower().endswith(DAT_EXT) for n in names):
            out.append(('zipdat', src, None))
        z.close()
    return out


def walk(src, want=None):
    """Yield (path, bytes or None) for every DBPF file of the input(s), in load order."""
    for kind, path, inner in _members(src):
        if kind == 'file':
            if want is None or want(path):
                yield path, open(path, 'rb').read()
            else:
                yield path, None
        elif kind == 'zipdat':
            z = zipfile.ZipFile(path)
            for n in sorted(i.filename for i in z.infolist()):
                if n.lower().endswith(DAT_EXT):
                    lab = path + '!' + n
                    yield lab, (z.read(n) if want is None or want(lab) else None)
            z.close()
        else:
            z = zipfile.ZipFile(path)
            with z.open(inner) as f:
                for n, data in _walk_jar_stream(f, path + '!' + inner,
                                               None if want is None else (lambda m: want(path + '!' + inner + '!' + m))):
                    yield path + '!' + inner + '!' + n, data
            z.close()


def _stamp(src):
    srcs = src if isinstance(src, (list, tuple)) else [src]
    parts = []
    for s in srcs:
        st = os.stat(s)
        parts.append('%s-%d-%d' % (os.path.basename(s.rstrip('/\\')), st.st_size, int(st.st_mtime)))
    import hashlib
    return parts[0] if len(parts) == 1 else hashlib.sha1('|'.join(parts).encode()).hexdigest()[:16]


def _jsonable(v):
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, bytes):
        return v.decode('latin-1')
    return v


# ---------------------------------------------------------------------------------------------- the index
class DepsIndex:
    """Prop exemplars + cohorts + entry locations of one or more dependency packs; a TGI store for views.load_views
    (has / read) over the fetched entries."""

    def __init__(self, src, cache=None, log=print):
        self.src = src
        self.cache = cache or default_cache()
        self.log = log
        os.makedirs(self.cache, exist_ok=True)
        self.stem = os.path.join(self.cache, _stamp(src))
        self.entries_dir = os.path.join(self.cache, 'entries')
        if not self._load():
            self._build()
        self._props_by_family = None

    # -- build / load
    def _load(self):
        try:
            j = json.load(open(self.stem + '.idx.json', encoding='utf-8'))
            if j.get('version') != INDEX_VERSION:
                return False
            m = np.load(self.stem + '.map.npy')
        except (OSError, ValueError):
            return False
        self._set(j, m)
        self.log('deps: index %s (%d prop exemplars, %d cohorts, %d DBPF files, cached)'
                 % (os.path.basename(self.stem), len(self.props), len(self.cohorts), len(self.dats)))
        return True

    def _set(self, j, m):
        self.dats = j['dats']
        self.props = {int(k, 16): v for k, v in j['props'].items()}
        self.cohorts = {tuple(int(x, 16) for x in k.split('-')): v for k, v in j['cohorts'].items()}
        self.map = {}
        for t, g, i, d in m.tolist():
            self.map[((D.T_S3D, D.T_FSH)[t], g, i)] = d

    def _build(self):
        t0 = time.time()
        dats, props, cohorts, rows = [], {}, {}, []
        for path, data in walk(self.src):
            di = len(dats)
            dats.append(path)
            try:
                f = D.DBPF(path, data)
            except (ValueError, struct.error) as e:
                self.log('  deps: skip %s: %s' % (path, e))
                continue
            for e in f.entries:
                if e.type in MAP_TYPES:
                    rows.append((MAP_TYPES[e.type], e.group, e.instance, di))
                elif e.type in (D.T_EXEMPLAR, D.T_COHORT):
                    try:
                        ex = X.parse_exemplar(f.read(e))
                    except (ValueError, KeyError, struct.error, IndexError):
                        continue
                    pr = {'%08X' % k: _jsonable(v[1]) for k, v in ex['props'].items()}
                    rec = {'g': e.group, 'parent': list(ex['parent']), 'dat': di, 'p': pr}
                    if e.type == D.T_COHORT:
                        cohorts['%08X-%08X-%08X' % e.tgi] = rec
                    else:
                        t = ex['props'].get(P_TYPE)
                        t = t[1] if t else None
                        t = t[0] if isinstance(t, list) and len(t) == 1 else t
                        if t == T_PROP:
                            props['%08X' % e.instance] = rec      # later file wins, as SC4 loads plugins
            del data
        m = np.array(rows, dtype=np.uint32).reshape(-1, 4)
        j = {'version': INDEX_VERSION, 'src': self.src if isinstance(self.src, str) else list(self.src),
             'dats': dats, 'props': props, 'cohorts': cohorts}
        with open(self.stem + '.idx.json', 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(j, fh)
        np.save(self.stem + '.map.npy', m)
        self._set(j, m)
        self.log('deps: indexed %d DBPF files, %d prop exemplars, %d cohorts, %d S3D / FSH entries in %.0f s -> %s'
                 % (len(dats), len(props), len(cohorts), len(m), time.time() - t0, self.stem + '.idx.json'))

    # -- exemplar properties (with cohort inheritance)
    def prop_value(self, inst, pid, default=None):
        rec = self.props.get(inst)
        seen = 0
        while rec is not None and seen < 8:
            v = rec['p'].get('%08X' % pid)
            if v is not None:
                return v
            par = tuple(rec['parent'])
            rec = self.cohorts.get(par) if any(par) else None
            seen += 1
        return default

    def family_members(self, fam):
        if self._props_by_family is None:
            self._props_by_family = {}
            for inst in self.props:
                v = self.prop_value(inst, P_FAMILY)
                for f in (v if isinstance(v, list) else [v] if v is not None else []):
                    self._props_by_family.setdefault(f & 0xFFFFFFFF, []).append(inst)
            for v in self._props_by_family.values():
                v.sort()
        return self._props_by_family.get(fam, [])

    # -- entries (TGI store)
    def _entry_path(self, tgi):
        return os.path.join(self.entries_dir, '%08X-%08X-%08X' % tgi)

    def has(self, tgi):
        return tgi in self.map

    def located(self, tgi):
        return os.path.isfile(self._entry_path(tgi))

    def read(self, tgi):
        p = self._entry_path(tgi)
        if not os.path.isfile(p):
            raise KeyError('%08X-%08X-%08X not fetched' % tgi)
        return open(p, 'rb').read()

    def fetch(self, tgis, textures=True):
        """Copy the given S3D (and, with textures, every FSH their meshes name) out of the pack into the entry
        cache. -> number of entries written. Walks the pack once per round; a texture in a .dat the walk had
        already passed takes one more round."""
        from s3d import S3D
        want = {t for t in tgis if t in self.map and not self.located(t)}
        os.makedirs(self.entries_dir, exist_ok=True)
        wrote = 0
        rounds = 0
        while want and rounds < 3:
            rounds += 1
            t0 = time.time()
            dset = {self.map[t] for t in want}
            names = {self.dats[d]: d for d in dset}
            more = set()
            for path, data in walk(self.src, want=lambda p: p in names):
                if data is None:
                    continue
                f = D.DBPF(path, data)
                di = names[path]
                here = [t for t in want if self.map[t] == di]
                for t in here:
                    e = f.by_tgi.get(t)
                    if e is None:
                        continue
                    b = f.read(e)
                    with open(self._entry_path(t), 'wb') as fh:
                        fh.write(b)
                    wrote += 1
                    if textures and t[0] == D.T_S3D:
                        try:
                            ms = S3D(b).meshes()
                        except (ValueError, KeyError, IndexError, struct.error):
                            ms = []
                        for m in ms:
                            for tx in m[3]['tex']:
                                k = (D.T_FSH, t[1], tx['id'])
                                if k in self.map and not self.located(k):
                                    e2 = f.by_tgi.get(k) if self.map[k] == di else None
                                    if e2 is not None:
                                        with open(self._entry_path(k), 'wb') as fh:
                                            fh.write(f.read(e2))
                                        wrote += 1
                                    else:
                                        more.add(k)
                del data, f
            self.log('deps: fetch round %d: %d DBPF files read, %d entries cached, %.0f s'
                     % (rounds, len(dset), wrote, time.time() - t0))
            want = {t for t in more if not self.located(t)}
        return wrote


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=('index', 'find'))
    ap.add_argument('pack')
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--cache')
    a = ap.parse_args(argv[1:])
    di = DepsIndex(a.pack, a.cache)
    if a.cmd == 'index':
        from collections import Counter
        c = Counter()
        for inst in di.props:
            for k in P_RKT:
                if di.prop_value(inst, k) is not None:
                    c['%08X' % k] += 1
        print('model key properties over prop exemplars:', dict(c))
        return 0
    for s in a.ids:
        i = int(s, 16)
        if i in di.props:
            r = di.props[i]
            print('%08X prop %s group %08X dat %s' % (i, r['p'].get('00000020'), r['g'], di.dats[r['dat']]))
            for k, v in sorted(r['p'].items()):
                print('   ', k, X.PROP_NAMES.get(int(k, 16), ''), str(v)[:100])
        ms = di.family_members(i)
        if ms:
            print('%08X family of %d: %s' % (i, len(ms), ', '.join('%08X %s' % (m, di.prop_value(m, P_NAME))
                                                                 for m in ms[:12])))
        if i not in di.props and not ms:
            print('%08X not found' % i)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
