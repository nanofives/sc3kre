// pagetest.js - task bldweb (2026-11-18d): loaded by classifier.html?bldtest=<manifest url> (webtest/pagetest.mjs).
// Builds File System Access stand-ins whose files are fetched from disk (chrome --allow-file-access-from-files) and
// whose writes stay in memory, then runs the page's own install (window.bc.installWith: Web Worker renderer, the same
// call the Install button makes). The sha256 of every written file goes into <pre id="bldtest"> for the driver.
(async () => {
  const out = document.getElementById('bldtest');
  const done = (res) => { out.textContent = JSON.stringify(res); document.title = 'SC3 Model Classifier [bldtest done]'; };
  try {
    const qs = new URLSearchParams(location.search);
    const man = await (await fetch(qs.get('bldtest'))).json();
    class MemFile {
      constructor(name, url) { this.kind = 'file'; this.name = name; this.url = url; this.data = null; this.blob = null; }
      async getFile() {
        if (this.data) return new File([this.data], this.name);
        if (!this.blob) { const r = await fetch(this.url); if (!r.ok) throw new Error('fetch ' + this.url); this.blob = await r.blob(); }
        return new File([this.blob], this.name);
      }
      async createWritable() { const parts = []; return { write: async d => { parts.push(d); }, close: async () => { this.data = new Uint8Array(await new Blob(parts).arrayBuffer()); this.blob = null; this.written = true; } }; }
      async move(n) { this.parent.kids.delete(this.name.toLowerCase()); this.name = n; this.parent.kids.set(n.toLowerCase(), this); }
    }
    class MemDir {
      constructor(name) { this.kind = 'directory'; this.name = name; this.kids = new Map(); }
      async getDirectoryHandle(n, o = {}) { let d = this.kids.get(n.toLowerCase()); if (d && d.kind !== 'directory') throw new DOMException(n, 'TypeMismatchError'); if (!d) { if (!o.create) throw new DOMException(n, 'NotFoundError'); d = new MemDir(n); this.kids.set(n.toLowerCase(), d); } return d; }
      async getFileHandle(n, o = {}) { let f = this.kids.get(n.toLowerCase()); if (f && f.kind !== 'file') throw new DOMException(n, 'TypeMismatchError'); if (!f) { if (!o.create) throw new DOMException(n, 'NotFoundError'); f = new MemFile(n, null); f.data = new Uint8Array(0); f.parent = this; this.kids.set(n.toLowerCase(), f); } return f; }
      async removeEntry(n) { if (!this.kids.delete(n.toLowerCase())) throw new DOMException(n, 'NotFoundError'); }
      async *entries() { for (const k of [...this.kids.values()]) yield [k.name, k]; }
    }
    function tree(base, files) {
      const root = new MemDir('root');
      for (const rel of files) {
        const parts = rel.split('/'); let d = root;
        for (const p of parts.slice(0, -1)) { let c = d.kids.get(p.toLowerCase()); if (!c) { c = new MemDir(p); d.kids.set(p.toLowerCase(), c); } d = c; }
        const name = parts[parts.length - 1], f = new MemFile(name, base + rel.split('/').map(encodeURIComponent).join('/'));
        f.parent = d; d.kids.set(name.toLowerCase(), f);
      }
      return root;
    }
    const written = (root, pre = '') => {
      const res = [];
      for (const k of root.kids.values()) {
        const p = pre ? pre + '/' + k.name : k.name;
        if (k.kind === 'directory') res.push(...written(k, p)); else if (k.data) res.push([p, k.data]);
      }
      return res;
    };
    const models = tree(man.models.base, man.models.files), game = tree(man.game.base, man.game.files);
    const B = window.BLDWEB, t0 = performance.now();
    let rep, sc4 = null, mfs = null;
    if (man.sc4) {
      // task sc4web: the SC4 download as the player picks it (Open SC4 .zip): the page converts it, the grid fills,
      // and Install reads the converted files from the page's in-memory models folder
      const files = [];
      for (const f of man.sc4.files) { const r = await fetch(man.sc4.base + encodeURIComponent(f)); if (!r.ok) throw new Error('fetch ' + f); files.push(new File([await r.blob()], f)); }
      for (const d of man.sc4.deps || []) {   // task sc4props: the dependency pack (a Blob the page slices and streams)
        const r = await fetch(d.base + encodeURIComponent(d.file)); if (!r.ok) throw new Error('fetch ' + d.file); files.push(new File([await r.blob()], d.file));
      }
      const t1 = performance.now();
      await window.bc.openSc4(window.SC4WEB.fileInputs(files), { name: man.sc4.files.join(', ') });
      const S = window.bc.S;
      await new Promise(res => setTimeout(res, 0));   // task sc4diag: the badge observer runs after the grid is built
      const diagCards = [...document.querySelectorAll('#grid .card')].filter(c => c.querySelector('.b.diag'));
      sc4 = { diag: diagCards.length, diagTitle: diagCards.length ? diagCards[0].querySelector('.b.diag').title : '',
        diagFiles: diagCards.map(c => c.dataset.file), seconds: (performance.now() - t1) / 1000, recs: S.recs.length, enabled: S.recs.filter(r => r.meta.enabled).length,
        errors: S.recs.filter(r => r.err).map(r => r.file + ': ' + r.err).slice(0, 5), groups: document.querySelectorAll('#grid .grp').length,
        cards: document.querySelectorAll('#grid .card').length, note: document.getElementById('sc4Note').textContent, status: document.getElementById('status').textContent,
        withProps: S.recs.filter(r => r.meta && r.meta.x_sc4 && r.meta.x_sc4.props && r.meta.x_sc4.props.on).length };
      mfs = window.bc.modelsFolder();
    }
    if (man.action === 'open' && sc4 && !window.bc.S.recs.length) {   // task sc4pass2: a lot-only download converts to nothing
      await new Promise(r => setTimeout(r, 0));   // the note / status observer of sc4web.js runs
      sc4.note = document.getElementById('sc4Note').textContent; sc4.status = document.getElementById('status').textContent;
      sc4.noteShown = !document.getElementById('sc4Note').hidden;
      sc4.buttons = Object.fromEntries(['btnInstall', 'btnZipInstall', 'btnSave'].map(id => [id, document.getElementById(id).disabled]));
      done({ pass: true, action: 'open', seconds: 0, rep: [], files: {}, models: {}, deleted: [], sc4, empty: true });
      return;
    }
    if (man.action === 'open' && sc4) {      // task sc4civ: an SC4 install opened in the grid (no install)
      const S = window.bc.S;
      sc4.noteShown = !document.getElementById('sc4Note').hidden;
      sc4.install = !!(S.sc4 && S.sc4.install); sc4.dirHandle = !!S.dirHandle; sc4.folderName = S.folderName;
      sc4.kinds = {}; for (const r of S.recs) { const k = r.meta.kind + (r.meta.base ? ':' + r.meta.base : ''); sc4.kinds[k] = (sc4.kinds[k] || 0) + 1; }
      const mh = S.recs.find(r => r.raw && r.raw.x_sc4 && r.raw.x_sc4.exemplar === 'RW16x14_MayorsHouse_031F');
      sc4.mayor = mh ? { kind: mh.meta.kind, population: mh.meta.population, year: mh.meta.year, enabled: mh.meta.enabled } : null;
      sc4.buttons = Object.fromEntries(['btnInstall', 'btnZipInstall', 'btnSave'].map(id => [id, document.getElementById(id).disabled]));
      done({ pass: true, action: 'open', seconds: 0, rep: [], files: {}, models: {}, deleted: [], sc4 });
      return;
    }
    if ((man.action === 'open' || man.editDesc) && !man.sc4) {   // sc3compat-a: a models folder opened in the grid as Open folder does
      const files = [];
      for (const rel of man.models.files) {
        if (rel.includes('/')) continue;
        const r = await fetch(man.models.base + encodeURIComponent(rel)); if (!r.ok) throw new Error('fetch ' + rel);
        files.push(new File([await r.blob()], rel));
      }
      window.bc.S.dirHandle = null; window.bc.S.folderName = 'test folder'; window.bc.S.allFiles = files;
      await window.bc.openFiles({ all: files, models: files.filter(f => /\.(obj|bld|gltf|glb|fbx)$/i.test(f.name)) },
        files.find(f => f.name.toLowerCase() === 'models.json') || null);
    }
    let editDesc = null;
    if (man.editDesc) {
      // plop2 (2026-11-19): the landmark Description field. The entry's description is blanked, the card selected, the
      // value typed into the panel's Description box (a change event, as the player's typing), and the install reads
      // the page's own models.json (modelsFolder(), as Install does for a folder opened read-only).
      const S = window.bc.S, ed = man.editDesc, rec = S.recs.find(r => r.file === ed.file);
      if (!rec) throw new Error('editDesc: no card for ' + ed.file);
      const rowOf = () => [...document.querySelectorAll('#form .row')].find(r => r.querySelector('label').textContent === 'Description');
      const card = f => document.getElementById('grid').querySelector('.card[data-file="' + f + '"]');
      editDesc = { before: rec.meta.description };
      // civmod: civic looks and rewards have a Description too, so the check card is a kind without one
      const other = S.recs.find(r => !['landmark', 'civic', 'reward'].includes(r.meta.kind));
      if (other) { card(other.file).click(); await new Promise(r => setTimeout(r, 0)); editDesc.hiddenFor = [other.file, other.meta.kind, rowOf().hidden]; }
      rec.meta.description = ''; if (rec.raw) delete rec.raw.description;
      editDesc.blankSaved = 'description' in (JSON.parse(window.bc.toJSONText()).models.find(m => m.file === ed.file) || {});
      card(ed.file).click(); await new Promise(r => setTimeout(r, 0));
      const row = rowOf(), inp = row.querySelector('input');
      editDesc.shown = !row.hidden; editDesc.boxBefore = inp.value;
      inp.value = ed.text; inp.dispatchEvent(new Event('change'));
      const saved = JSON.parse(window.bc.toJSONText()).models.find(m => m.file === ed.file);
      editDesc.saved = saved && saved.description; editDesc.meta = rec.meta.description;
      mfs = window.bc.modelsFolder();
    }
    if (man.action === 'open') {           // task sc4web: open only (pictures of the grid and the preview)
      const S = window.bc.S, pick = S.recs.find(r => r.meta.enabled) || S.recs[0];
      document.getElementById('grid').querySelector('.card[data-file="' + pick.file + '"]').click();
      await new Promise(r => setTimeout(r, +(qs.get('wait') || 3000)));
      const meshes = []; if (pick.obj) pick.obj.traverse(n => { if (n.isMesh) meshes.push([n.name, n.visible, [].concat(n.material).map(m => m.type + (m.map ? ' map ' + (m.map.image ? m.map.image.width + 'x' + m.map.image.height : 'no image') : ' no map')).join('|')]); });
      done({ pass: true, action: 'open', seconds: 0, rep: [], files: {}, models: {}, deleted: [], sc4, focus: pick.file, err: pick.err, meshes, thumb: (pick.thumb || '').length,
        side: S.recs.filter(r => r.side).length, recs: S.recs.length, status: document.getElementById('status').textContent });
      return;
    }
    if ((man.action || 'install') === 'remove') rep = ['restored ' + await B.restore(B.handleFS(game), () => {}) + ' file(s)'];
    else rep = (await window.bc.installWith(mfs || B.handleFS(models), B.handleFS(game), { style: 'stock' })).rep;
    const res = { pass: true, action: man.action || 'install', seconds: (performance.now() - t0) / 1000, rep, files: {}, models: {}, deleted: [],
      worker: B.lastWorkerMode || null, sc4, editDesc };
    const b64 = d => { let s = ''; for (let k = 0; k < d.length; k += 8192) s += String.fromCharCode.apply(null, d.subarray(k, k + 8192)); return btoa(s); };
    for (const [p, d] of written(game)) res.files[p] = { sha: B.sha256(d), size: d.length, b64: man.apply ? b64(d) : undefined };
    for (const [p, d] of written(models)) res.models[p] = { sha: B.sha256(d), size: d.length, b64: man.apply ? b64(d) : undefined };
    if (mfs) for (const [p, d] of mfs.written) res.models[p] = { sha: B.sha256(d), size: d.length, b64: man.apply ? b64(d) : undefined };
    const live = new Set(); (function walk(dd, pre) { for (const k of dd.kids.values()) { const q = pre ? pre + '/' + k.name : k.name; if (k.kind === 'directory') walk(k, q); else live.add(q.toLowerCase()); } })(game, '');
    res.deleted = man.game.files.filter(f => !live.has(f.toLowerCase()));
    res.progressShown = document.getElementById('progText').textContent;
    res.resultRows = document.querySelectorAll('#results .res').length;
    done(res);
  } catch (e) { done({ pass: false, error: String(e && e.stack || e) }); }
})();
