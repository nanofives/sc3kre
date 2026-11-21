// chrome.mjs - task suitespeed (2026-11-20): the headless Chrome of the page tests (pagetest.mjs, fonts_inline.mjs,
// sc3pack_pagetest.mjs, check_roundtrip.py), started with one retry.
//
// The suite's one known flake was Chrome start-up: readFileSync of DevToolsActivePort threw EBUSY while Chrome was still
// writing the file (pagetest.mjs kenney on 2026-11-19, pagetest.mjs landmarks twice on 2026-11-20; each passed when run
// again with no change). Now an unreadable or half-written port file is read again on the next poll, and a Chrome that
// gives no debugging port or no page target in time is stopped (by its PID) and started once more, in a new profile.
// The checks themselves are unchanged: only the start-up is retried, never a test result.
//
//   const c = await startChrome(exe, flags, url, { prefix, findTarget: l => l.find(...), portMs, targetMs });
//   c.ch (the process), c.port, c.prof, c.target, c.stop()
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';

const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function startChrome(exe, flags, url, opt = {}) {
  const tries = opt.tries || 2, portMs = opt.portMs || 20000, targetMs = opt.targetMs || 10000;
  const log = opt.log || (s => console.log(s));
  let why = '';
  for (let a = 1; a <= tries; a++) {
    const prof = fs.mkdtempSync(path.join(os.tmpdir(), opt.prefix || 'chrome-'));
    const ch = spawn(exe, [...flags, '--user-data-dir=' + prof, url], { stdio: 'ignore' });
    let exited = null;
    ch.on('exit', c => { exited = c; });
    ch.on('error', e => { exited = String(e); });
    const stop = () => {
      try { execFileSync('taskkill', ['/PID', String(ch.pid), '/T', '/F'], { stdio: 'ignore' }); } catch (e) { /* already gone */ }
    };
    let port = null, target = null;
    const t0 = Date.now();
    while (!port && Date.now() - t0 < portMs && exited === null) {
      await sleep(200);
      try {
        const txt = fs.readFileSync(path.join(prof, 'DevToolsActivePort'), 'utf8');
        const p = txt.split('\n')[0].trim();
        if (/^\d+$/.test(p) && txt.includes('\n')) port = p;
      } catch (e) { /* not there yet, or EBUSY while Chrome writes it: read it again */ }
    }
    if (port) {
      const t1 = Date.now();
      while (!target && Date.now() - t1 < targetMs && exited === null) {
        await sleep(200);
        try {
          const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
          target = opt.findTarget ? opt.findTarget(l) : l.find(x => x.type === 'page');
        } catch (e) { /* the DevTools server is not answering yet */ }
      }
    }
    if (port && target) return { ch, port, prof, target, stop, attempt: a };
    why = exited !== null ? `Chrome exited (${exited})` : !port ? `no debugging port in ${portMs / 1000} s` : `no page target in ${targetMs / 1000} s`;
    stop();
    await sleep(500);
    try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* locked files of a closing chrome */ }
    if (a < tries) log(`  chrome start-up failed (${why}), starting it once more`);
  }
  throw new Error('chrome did not start: ' + why + ` (${tries} tries)`);
}
