"""hook_audit.py - every hook the mods installed in a running game, with the original's `ret N` and the hook's (task
zoomcrash, 2026-10-25).

The bug class: a hook that returns on its own (a skip or early-out path, or a C replacement) must pop the same stack
bytes as the code it stands in for. A bare `ret` where the original is `ret 4` corrupted the caller's ESI / EBX and
killed the game silently (verify/zoomcrash/RESULTS.md). Reading the source for this cannot prove it found every hook
(helpers, arrays, chains), so this audits the process instead:

  1. Frida dumps every readable byte of every loaded module.
  2. Each non-mod module is compared with its disk file relocated to the runtime base (pefile). In the differences:
     - a rel32 `jmp` / `call` whose target is inside a mod's code = a code hook (at a function entry, a call site, or
       mid-function),
     - a dword that points into a mod's code where the disk had something else = a slot hook (vtable, IAT, pointer).
  3. The original is the disk function at that place (the entry, the disk call's callee, or the disk slot's value). Its
     `ret` forms come from a recursive-descent disassembly of the disk image.
  4. The hook's `ret` forms and tail jumps come from the same walk over the mod's memory (jmp [g_orig] is resolved
     through the dumped data, so a tail into the original or another mod's hook is followed).
  A hook whose own `ret N` differs from the original's is a MISMATCH. Mid-function patches that return on their own and
  indirect call sites are listed as CHECK.

Read-only (memory reads only). Do not attach while the game is paused (memory project-frida-paused-attach-deadlock).
    py re/tools/hook_audit.py --pid <SC3U pid> --out <report.txt> [--mods sc3resize.dll,...]
"""
import argparse
import pickle
import collections
import os
import struct
import sys
import time

import capstone
import frida
import numpy as np
import pefile

JS = r"""
var mods = Process.enumerateModules();
send({ t: 'mods', mods: mods.map(function (m) { return { name: m.name, base: m.base.toString(), size: m.size, path: m.path }; }) });
Process.enumerateRanges({ protection: 'r--', coalesce: false }).forEach(function (r) {
  var m = null;
  for (var i = 0; i < mods.length; i++) if (r.base.compare(mods[i].base) >= 0 && r.base.compare(mods[i].base.add(mods[i].size)) < 0) { m = mods[i]; break; }
  if (!m || m.size > 0x800000) return;   /* skip modules over 8 MB (GPU driver blobs) */
  for (var off = 0; off < r.size; off += 0x100000) {
    var n = Math.min(0x100000, r.size - off);
    try { send({ t: 'mem', mod: m.name, rva: r.base.add(off).sub(m.base).toInt32(), x: r.protection.indexOf('x') >= 0 }, r.base.add(off).readByteArray(n)); }
    catch (e) { send({ t: 'err', mod: m.name, rva: r.base.add(off).sub(m.base).toInt32(), e: '' + e }); }
  }
});
send({ t: 'done' });
"""

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True


class Img:
    """A module's bytes by RVA (memory dump or relocated disk image)."""
    def __init__(self, name, base, size, data=None):
        self.name, self.base, self.size = name, base, size
        self.data = data if data is not None else bytearray(size)
        self.have = bytearray(size) if data is None else bytearray(b'\x01' * size)
        self.xr = []                                       # executable rva ranges

    def rd(self, rva, n):
        if rva < 0 or rva + n > len(self.data):
            return None
        return bytes(self.data[rva:rva + n])

    def dword(self, rva):
        b = self.rd(rva, 4)
        return struct.unpack('<I', b)[0] if b else None

    def is_x(self, rva):
        return any(a <= rva < b for a, b in self.xr)


_exp = {}


def fix_path(p):
    """The game is a WoW64 process: Frida reports System32 paths, whose 32-bit files live in SysWOW64."""
    key = os.sep + 'windows' + os.sep + 'system32' + os.sep
    i = p.lower().find(key)
    if i >= 0 and sys.maxsize > 2 ** 32:
        return p[:i] + os.sep + 'Windows' + os.sep + 'SysWOW64' + os.sep + p[i + len(key):]
    return p


def export_va(imgs, dll, fn, depth=0):
    """Runtime address of dll!fn from the loaded module's export table (forwarders followed by name)."""
    em = next((x for x in imgs if x.lower() == dll.lower()), None)
    if not em or depth > 3:
        return None
    if em not in _exp:
        try:
            pe2 = pefile.PE(fix_path(imgs[em].path), fast_load=True)
            pe2.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
            _exp[em] = {e.name.decode(): (e.address, e.forwarder) for e in pe2.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        except Exception:
            _exp[em] = {}
    hit = _exp[em].get(fn)
    if not hit:
        return None
    addr, fwd = hit
    if fwd:
        d, _, f = fwd.decode().partition('.')
        return export_va(imgs, d + '.dll', f, depth + 1)
    return imgs[em].base + addr


def walk(imgs, start_mod, start_rva, limit=6000, any_module=False):
    """Recursive descent from start. Returns (rets set, tails list, notes list). Follows jumps into any mod image."""
    rets, tails, notes = set(), [], []
    seen = set()
    todo = [(start_mod, start_rva)]
    n = 0
    while todo and n < limit:
        mod, rva = todo.pop()
        img = imgs[mod]
        while n < limit:
            if (mod, rva) in seen:
                break
            seen.add((mod, rva))
            b = img.rd(rva, 16)
            if not b:
                notes.append('unreadable %s+0x%x' % (mod, rva)); break
            ins = next(md.disasm(b, img.base + rva, 1), None)
            if ins is None:
                notes.append('bad insn %s+0x%x' % (mod, rva)); break
            n += 1
            m = ins.mnemonic
            nxt = rva + ins.size
            if m.startswith('ret'):
                rets.add(int(ins.op_str, 0) if ins.op_str else 0); break
            if m in ('int3', 'hlt', 'ud2'):
                break
            if m == 'jmp' or (m.startswith('j') and m not in ('jmp',)):
                op = ins.operands[0]
                tgt = None
                if op.type == capstone.x86.X86_OP_IMM:
                    tgt = op.imm
                elif op.type == capstone.x86.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    tgt = resolve_ptr(imgs, op.mem.disp)
                    if tgt is None:
                        tails.append(('indirect', op.mem.disp));
                        if m == 'jmp': break
                        tgt = None
                elif op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_EDX and op.mem.disp:
                    tails.append(('vcall', '[edx+0x%x]' % op.mem.disp))
                    if m == 'jmp': break
                else:
                    tails.append(('indirect', ins.op_str))
                    if m == 'jmp': break
                if tgt is not None:
                    tm, tr = where(imgs, tgt)
                    if tm is None:
                        tails.append(('abs', tgt))
                    elif imgs[tm].is_mod or any_module:
                        todo.append((tm, tr))
                    else:
                        tails.append(('game', tm, tr))
                if m == 'jmp':
                    break
            rva = nxt
    if n >= limit:
        notes.append('walk limit')
    return rets, tails, notes


def where(imgs, va):
    for nm, im in imgs.items():
        if im.base <= va < im.base + im.size:
            return nm, va - im.base
    return None, None


def resolve_ptr(imgs, va):
    nm, r = where(imgs, va)
    if nm is None:
        return None
    return imgs[nm].dword(r)


def orig_rets(disk, rva):
    """ret forms of the disk function at rva (walk the relocated disk image, staying inside it)."""
    rets, seen, todo, n = set(), set(), [rva], 0
    while todo and n < 20000:
        r = todo.pop()
        while n < 20000:
            if r in seen:
                break
            seen.add(r)
            b = disk.rd(r, 16)
            ins = next(md.disasm(b, disk.base + r, 1), None) if b else None
            if ins is None:
                break
            n += 1
            m = ins.mnemonic
            if m.startswith('ret'):
                rets.add(int(ins.op_str, 0) if ins.op_str else 0); break
            if m in ('int3', 'hlt'):
                break
            if m.startswith('j'):
                op = ins.operands[0]
                if op.type == capstone.x86.X86_OP_IMM and disk.base <= op.imm < disk.base + disk.size:
                    tr = op.imm - disk.base
                    if m == 'jmp':
                        r = tr; continue
                    todo.append(tr)
                elif m == 'jmp':
                    break          # tail call / jump table
            r += ins.size
    return rets


def fmt_rets(s):
    return '/'.join(('ret %d' % x) if x else 'ret' for x in sorted(s)) if s else '-'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=0)
    ap.add_argument('--save', help='also write the raw dump here (pickle), for --load')
    ap.add_argument('--load', help='analyse a saved dump instead of attaching')
    ap.add_argument('--out', required=True)
    ap.add_argument('--mods', default='')
    ap.add_argument('--all', action='store_true', help='diff every module, not only the game folder + DirectDraw / CRT / USER / GDI / KERNEL32')
    a = ap.parse_args()
    msgs = []
    t0 = time.time()
    if a.load:
        with open(a.load, 'rb') as f:
            msgs = pickle.load(f)
    else:
        sess = frida.attach(a.pid)
        sc = sess.create_script(JS)
        sc.on('message', lambda m, d: msgs.append((m, d)))
        sc.load()
        while not any(m.get('payload', {}).get('t') == 'done' for m, _ in msgs if m.get('type') == 'send') and time.time() - t0 < 300:
            time.sleep(0.2)
        sess.detach()
        if a.save:
            with open(a.save, 'wb') as f:
                pickle.dump(msgs, f)
    print('dump: %d messages, %.1f MB in %.0f s' % (len(msgs), sum(len(d or b'') for _, d in msgs) / 1e6, time.time() - t0), flush=True)
    mods, imgs = None, {}
    for m, d in msgs:
        if m.get('type') != 'send':
            continue
        p = m['payload']
        if p['t'] == 'mods':
            mods = p['mods']
            for x in mods:
                imgs[x['name']] = Img(x['name'], int(x['base'], 16), x['size'])
                imgs[x['name']].path = x['path']
        elif p['t'] == 'mem':
            im = imgs[p['mod']]
            im.data[p['rva']:p['rva'] + len(d)] = d
            im.have[p['rva']:p['rva'] + len(d)] = b'\x01' * len(d)
            if p['x']:
                im.xr.append((p['rva'], p['rva'] + len(d)))
    modset = set(x.lower() for x in a.mods.split(',') if x) or \
        set(n.lower() for n in imgs if n.lower().startswith('sc3') and n.lower().endswith('.dll')) | {'version.dll'}
    for n, im in imgs.items():   # version.dll counts only when it is ours (beside SC3U.exe), not the system one
        im.is_mod = n.lower() in modset and (n.lower() != 'version.dll' or 'system' not in im.path.lower())
    modx = [(im.base + s, im.base + e, n) for n, im in imgs.items() if im.is_mod for s, e in im.xr]

    def in_mod(va):
        return any(s <= va < e for s, e, _ in modx)
    allx = [(im.base + s, im.base + e) for n, im in imgs.items() for s, e in im.xr]

    def code_ptr(va):
        return any(s <= va < e for s, e in allx)

    out = []
    hooks = []
    for n, im in sorted(imgs.items()):
        if im.is_mod:
            continue
        if not any(im.have):
            continue
        sysok = n.lower() in ('ddraw.dll', 'msvcrt.dll', 'user32.dll', 'gdi32.dll', 'kernel32.dll')
        sysmod = 'windows' in im.path.lower()
        if not (a.all or sysok or 'windows' not in im.path.lower()):
            continue
        try:
            pe = pefile.PE(fix_path(im.path))
            iat = {}
            for e in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
                for imp in e.imports:
                    iat[imp.address - pe.OPTIONAL_HEADER.ImageBase] = (e.dll.decode(errors='replace'),
                                                                       (imp.name or b'#%d' % imp.ordinal).decode(errors='replace'))
            pe.relocate_image(im.base)
            dimg = pe.get_memory_mapped_image()
        except Exception as e:
            out.append('# %s: disk image not usable (%s)' % (n, e)); continue
        disk = Img(n + '(disk)', im.base, im.size, bytearray(dimg) + bytearray(max(0, im.size - len(dimg))))
        for s in pe.sections:
            lo, hi = s.VirtualAddress, s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
            hi = min(hi, len(dimg), im.size)
            ex = bool(s.Characteristics & 0x20000000)
            if hi <= lo:
                continue
            ma = np.frombuffer(bytes(im.data[lo:hi]), np.uint8); da = np.frombuffer(bytes(dimg[lo:hi]), np.uint8)
            hv = np.frombuffer(bytes(im.have[lo:hi]), np.uint8)
            idx = np.nonzero((ma != da) & (hv != 0))[0]
            spans = []
            for k in idx.tolist():
                if spans and k <= spans[-1][1]:
                    spans[-1][1] = k + 1
                else:
                    spans.append([k, k + 1])
            for i, j in spans:
                i += lo; j += lo
                if True:
                    found = False
                    if ex:
                        for p in range(max(lo, i - 4), j):
                            op = im.data[p]
                            if op in (0xE8, 0xE9) and p + 5 <= len(im.data):
                                tgt = (im.base + p + 5 + struct.unpack_from('<i', im.data, p + 1)[0]) & 0xffffffff
                                if in_mod(tgt):
                                    hooks.append((n, p, 'call' if op == 0xE8 else 'jmp', tgt, disk, None))
                                    found = True
                    for p in range(i - i % 4, j, 4):
                        if p + 4 <= hi:
                            v = struct.unpack_from('<I', im.data, p)[0]
                            dv = struct.unpack_from('<I', dimg, p)[0]
                            if v != dv and in_mod(v) and not (ex and found):
                                if p in iat:
                                    hooks.append((n, p, 'iat', v, disk, iat.get(p)))
                                elif not sysmod and code_ptr(dv):
                                    hooks.append((n, p, 'slot', v, disk, None))
    seen = set()
    rows = []
    for n, p, kind, tgt, disk, imp in hooks:
        if (n, p, kind) in seen:
            continue
        seen.add((n, p, kind))
        hm, hr = where(imgs, tgt)
        hrets, tails, notes = walk(imgs, hm, hr)
        dins = next(md.disasm(disk.rd(p, 16) or b'', disk.base + p, 1), None)
        orig, orets, verdict = '', set(), ''
        if kind == 'iat':
            dll, fn = imp
            orig = 'IAT %s!%s' % (dll, fn)
            va = export_va(imgs, dll, fn)
            if va:
                om, orr = where(imgs, va)
                orets, _, _ = walk(imgs, om, orr, limit=20000, any_module=True)
                orig += ' = %s+0x%x' % (om, orr)
            else:
                orig += ' (export not resolved)'
        elif kind == 'slot':
            ov = disk.dword(p)
            om, orr = where(imgs, ov) if ov else (None, None)
            if om is None:
                orig = 'disk value 0x%08x (not code)' % (ov or 0)
            else:
                orig = '%s+0x%x' % (om, orr)
                od = disk if om == n else None
                if od is None:
                    try:
                        pe2 = pefile.PE(fix_path(imgs[om].path)); pe2.relocate_image(imgs[om].base)
                        od = Img(om, imgs[om].base, imgs[om].size, bytearray(pe2.get_memory_mapped_image()))
                    except Exception:
                        od = imgs[om]
                orets = orig_rets(od, orr)
        elif dins is not None and dins.mnemonic == 'call' and dins.operands[0].type == capstone.x86.X86_OP_IMM:
            om, orr = where(imgs, dins.operands[0].imm)
            orig = 'call site, callee %s+0x%x' % (om, orr) if om else 'call site, callee 0x%x' % dins.operands[0].imm
            if om == n:
                orets = orig_rets(disk, orr)
        elif dins is not None and dins.mnemonic == 'call':
            orig = 'indirect call site `%s %s`' % (dins.mnemonic, dins.op_str)
        else:
            orig = 'code at %s+0x%x `%s %s`' % (n, p, dins.mnemonic if dins else '?', dins.op_str if dins else '')
            orets = orig_rets(disk, p)
        own = hrets
        if kind == 'call' and orig.startswith('code at'):
            verdict = 'CALL-PATCH (balanced by its own call/ret)' if own <= {0} else 'CHECK (call patch with ret N)'
        elif orig.startswith('indirect'):
            verdict = 'CHECK (indirect call site: callee pops %s?)' % fmt_rets(own)
        elif not own:
            verdict = 'ok (no own return: passes to %s)' % (', '.join(fmt_tail(imgs, t) for t in tails[:3]) or '?')
        elif not orets:
            verdict = 'CHECK (original ret unknown)'
        elif own == orets or own <= orets:
            verdict = 'ok'
        else:
            verdict = 'MISMATCH'
        rows.append((verdict, '%s+0x%x\t%s\thook %s+0x%x\tours %s\toriginal %s (%s)\t%s%s' % (
            n, p, kind, hm, hr, fmt_rets(own), fmt_rets(orets), orig, verdict,
            ('\t' + '; '.join(notes)) if notes else '')))
    order = {'MISMATCH': 0, 'CHECK': 1}
    rows.sort(key=lambda r: (order.get(r[0].split(' ')[0], 2), r[1]))
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('# hook_audit pid %d: %d install points (mods: %s)\n' % (a.pid, len(rows), ', '.join(sorted(modset))))
        for line in out:
            f.write(line + '\n')
        for v, line in rows:
            f.write(line + '\n')
    c = collections.Counter(r[0].split(' ')[0] for r in rows)
    for i, (v, line) in enumerate(rows, 1):
        print('[%d/%d] %s' % (i, len(rows), line), flush=True)
    print('summary:', dict(c), flush=True)
    return 0


def fmt_tail(imgs, t):
    if t[0] == 'game':
        return '%s+0x%x' % (t[1], t[2])
    if t[0] == 'abs':
        nm, r = where(imgs, t[1])
        return '%s+0x%x' % (nm, r) if nm else '0x%x' % t[1]
    return '%s %s' % (t[0], t[1] if isinstance(t[1], str) else hex(t[1]))


if __name__ == '__main__':
    sys.exit(main())
