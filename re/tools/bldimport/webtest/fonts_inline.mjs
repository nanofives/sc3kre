// fonts_inline.mjs - gamefont (round 2026-11-19d): the importer page draws the game's fonts from its own copy of
// sc3ui.css (data: URIs inlined by sync_css.py), with no game folder and no font file next to it, and keeps the light
// look when the OS asks for dark (owner 2026-11-19: light theme only).
//
//   node re/tools/bldimport/webtest/fonts_inline.mjs [--chrome <exe>]
//
// Opens classifier.html?demo=1 from disk in a headless Chrome of its own (stopped by the PID this script started),
// with prefers-color-scheme emulated as dark. Prints "[N/M] name PASS|FAIL".
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const chrome = arg('chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe');
const page = pathToFileURL(path.join(here, '..', 'classifier.html')).href + '?demo=1';
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'gf-chrome-'));
const ch = spawn(chrome, ['--headless=new', '--window-size=1280,1000', '--allow-file-access-from-files', '--remote-debugging-port=0', '--user-data-dir=' + prof,
  '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--blink-settings=preferredColorScheme=0', 'about:blank'], { stdio: 'ignore' });
const stop = () => { try { execFileSync('taskkill', ['/PID', String(ch.pid), '/T', '/F'], { stdio: 'ignore' }); } catch (e) { /* already gone */ } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const FAMS = ['SC3 Main', 'SC3 Text', 'SC3 System', 'SC3 Name', 'SC3 Title', 'SC3 Button'];
const checks = [];
try {
  let port = null;
  for (let t = 0; t < 100 && !port; t++) { await sleep(200); const f = path.join(prof, 'DevToolsActivePort'); if (fs.existsSync(f)) port = fs.readFileSync(f, 'utf8').split('\n')[0].trim(); }
  if (!port) throw new Error('chrome did not open a debugging port');
  let target = null;
  for (let t = 0; t < 50 && !target; t++) { await sleep(200); const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); target = l.find(x => x.type === 'page'); }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const waiters = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); } };
  const send = (method, params) => new Promise(res => { const id = ++seq; waiters.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => { const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); return m.result && m.result.result && m.result.result.value; };
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
  await send('Page.navigate', { url: page });
  for (let t = 0; t < 60; t++) { await sleep(250); if (await evalJs("document.readyState === 'complete'")) break; }
  const r = await evalJs(`(async () => {
    const fams = ${JSON.stringify(FAMS)}, st = {};
    for (const f of fams) { try { const l = await document.fonts.load('400 12px "' + f + '"', 'Aa'); st[f] = l.length && l.every(x => x.status === 'loaded') ? 'loaded' : 'none'; } catch (e) { st[f] = 'error'; } }
    await document.fonts.ready;
    const res = performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\.woff2?($|\\?)/.test(n) && !/fonts\\.gstatic/.test(n));
    const cs = getComputedStyle(document.body);
    return { st, res, body: cs.fontFamily, bg: cs.backgroundColor, scheme: getComputedStyle(document.documentElement).colorScheme,
      dark: matchMedia('(prefers-color-scheme: dark)').matches, theme: !!document.getElementById('btnTheme'),
      inline: [...document.styleSheets].some(s => { try { return [...s.cssRules].some(r => r.cssText.includes('data:font/woff2')); } catch (e) { return false; } }),
      published: await SC3Font.publishedLoaded() };
  })()`);
  checks.push(['the six game font families load in the importer', FAMS.every(f => r.st[f] === 'loaded'), JSON.stringify(r.st)]);
  checks.push(['they come from the page itself (data: URIs, no font file fetched)', r.inline && r.res.length === 0, 'fetched: ' + JSON.stringify(r.res)]);
  checks.push(['body text uses the game font first', /^"SC3 Text"/.test(r.body), r.body]);
  checks.push(['run-time builder stands by (published faces loaded)', r.published === true, String(r.published)]);
  checks.push(['no Theme button', !r.theme, '']);
  checks.push(['OS dark mode: the page keeps the light look', r.dark && r.bg === 'rgb(216, 217, 255)' && r.scheme === 'light', `prefers dark ${r.dark}, background ${r.bg}, color-scheme ${r.scheme}`]);
  ws.close();
} catch (e) { checks.push(['fonts_inline', false, String(e.stack || e)]); }
finally { stop(); try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* locked files of a closing chrome */ } }
let bad = 0;
checks.forEach(([n, ok, d], i) => { bad += !ok; console.log(`[${i + 1}/${checks.length}] ${n} ${ok ? 'PASS' : 'FAIL'}${d ? '\n      ' + d : ''}`); });
console.log(`${checks.length - bad} of ${checks.length} passed`);
process.exit(bad ? 1 : 0);
