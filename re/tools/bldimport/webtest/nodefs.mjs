// nodefs.mjs - task bldweb (2026-11-18d): the File System Access API surface bldweb.js uses, over node's fs.
// FileSystemDirectoryHandle: getDirectoryHandle, getFileHandle, entries, removeEntry. FileSystemFileHandle: getFile
// (size, arrayBuffer, slice), createWritable (write to a swap file, rename on close, as Chrome does), move.
// So the page's own install / restore code runs here unchanged against a real folder.
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';

class NotFound extends Error { constructor(m) { super(m); this.name = 'NotFoundError'; } }
class TypeMismatch extends Error { constructor(m) { super(m); this.name = 'TypeMismatchError'; } }

function fileObj(p) {
  const st = fs.statSync(p);
  const slice = (a = 0, b = st.size) => ({
    size: Math.max(0, Math.min(b, st.size) - Math.max(0, a)),
    async arrayBuffer() {
      const s = Math.max(0, a), e = Math.min(b, st.size), n = Math.max(0, e - s);
      const buf = Buffer.alloc(n);
      if (n) { const fd = await fsp.open(p, 'r'); try { await fd.read(buf, 0, n, s); } finally { await fd.close(); } }
      return buf.buffer.slice(buf.byteOffset, buf.byteOffset + n);
    },
  });
  const all = slice();
  return { name: path.basename(p), size: st.size, arrayBuffer: all.arrayBuffer, slice };
}

export class FileHandle {
  constructor(p) { this.p = p; this.kind = 'file'; this.name = path.basename(p); }
  async getFile() { return fileObj(this.p); }
  async createWritable() {
    const swap = this.p + '.crswap', parts = [];
    return {
      async write(d) { parts.push(Buffer.from(d.buffer ? new Uint8Array(d.buffer, d.byteOffset, d.byteLength) : d)); },
      close: async () => { await fsp.writeFile(swap, Buffer.concat(parts)); await fsp.rename(swap, this.p); },
    };
  }
  async move(newName) { const np = path.join(path.dirname(this.p), newName); await fsp.rename(this.p, np); this.p = np; this.name = newName; }
}

export class DirHandle {
  constructor(p) { this.p = p; this.kind = 'directory'; this.name = path.basename(p); }
  async getDirectoryHandle(name, opt = {}) {
    const p = path.join(this.p, name);
    if (fs.existsSync(p)) { if (!fs.statSync(p).isDirectory()) throw new TypeMismatch(name); return new DirHandle(p); }
    if (!opt.create) throw new NotFound(name);
    await fsp.mkdir(p); return new DirHandle(p);
  }
  async getFileHandle(name, opt = {}) {
    const p = path.join(this.p, name);
    if (fs.existsSync(p)) { if (!fs.statSync(p).isFile()) throw new TypeMismatch(name); return new FileHandle(p); }
    if (!opt.create) throw new NotFound(name);
    await fsp.writeFile(p, Buffer.alloc(0)); return new FileHandle(p);
  }
  async removeEntry(name) {
    const p = path.join(this.p, name);
    if (!fs.existsSync(p)) throw new NotFound(name);
    await fsp.rm(p, { recursive: false });
  }
  async *entries() {
    for (const d of await fsp.readdir(this.p, { withFileTypes: true }))
      yield [d.name, d.isDirectory() ? new DirHandle(path.join(this.p, d.name)) : new FileHandle(path.join(this.p, d.name))];
  }
}
