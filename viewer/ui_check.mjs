// Optional interactive check of the viewer page in headless Chrome, via the Chrome DevTools Protocol.
// Needs Google Chrome and Node 22+ (built-in WebSocket); installs nothing.
//
//   .venv/bin/python -m viewer.server &        # the viewer must be running on 127.0.0.1:8765
//   node viewer/ui_check.mjs [output-folder]   # screenshots + ui_results.json (default: a temp folder)
//
// Opens every page of the dashboard, then clicks through the Rows page (a row filter, header sort, row detail,
// group-by click-to-filter, bookmark reload, paging) and the Glossary (search, category filter, source links).
// Fails on any JS error, failed request, or request to anything other than the local server. Displayed totals are
// compared with the API's own answer for the same state. Rewritten 2026-10-06 for the seven-page dashboard
// (the earlier version tested the single-page FY2025 viewer and could not pass after the dashboard rework).
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const OUT = process.argv[2] || mkdtempSync(join(tmpdir(), 'viewer_ui_'));
mkdirSync(OUT, { recursive: true });
const BASE = 'http://127.0.0.1:8765';
const CDP_PORT = 9333;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--disable-gpu', '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking', '--disable-component-update',
  '--disable-sync', '--disable-extensions', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'cdp_'))}`, 'about:blank'],
  { stdio: 'ignore' });

let target;
for (let i = 0; i < 50; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()).find((t) => t.type === 'page'); if (target) break; } catch {}
  await sleep(200);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map(); const problems = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); return; }
  if (d.method === 'Runtime.exceptionThrown') problems.push('exception: ' + JSON.stringify(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text));
  if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') problems.push('console.error: ' + JSON.stringify(d.params.args.map((a) => a.value || a.description)));
  if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error') problems.push('log: ' + d.params.entry.text + ' ' + (d.params.entry.url || ''));
  if (d.method === 'Network.requestWillBeSent' && !d.params.request.url.startsWith(BASE) && !d.params.request.url.startsWith('data:')) problems.push('external request: ' + d.params.request.url);
};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error('eval failed: ' + expr + ' -> ' + JSON.stringify(r.result.exceptionDetails.exception?.description));
  return r.result.result.value;
};
const waitFor = async (expr, label, timeout = 20000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { if (await js(expr)) return Date.now() - t0; await sleep(150); }
  throw new Error('timeout waiting for: ' + label);
};
const shot = async (name) => {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64'));
};
const results = [];
const ok = (name, cond, detail = '') => { results.push([cond ? 'PASS' : 'FAIL', name, detail]); console.log(`${cond ? 'PASS' : 'FAIL'}  ${name} ${detail}`); };
const loaded = (name) => `document.getElementById('status').textContent.startsWith('${name} loaded') && document.getElementById('error').hidden`;
const reset = () => js(`document.getElementById('status').textContent = ''`);
const stat = () => js(`document.querySelector('.stat .value').textContent`);
const api = (path) => js(`fetch(${JSON.stringify(path)}).then(r => r.json())`);
const rowsQS = () => js(`new URL(document.querySelector('.pager a.button').href).search`);

try {
  for (const m of ['Runtime.enable', 'Page.enable', 'Log.enable', 'Network.enable']) await send(m);
  await send('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1100, deviceScaleFactor: 1, mobile: false });

  // 1. every page renders without an error
  const pages = [['overview', 'What jumps off the page'], ['completeness', 'Month × year'], ['columns', 'Column × year'],
                 ['flags', 'Every flag'], ['rows', 'Matching rows'], ['decisions', 'Record a decision'], ['glossary', 'Glossary']];
  for (const [name, text] of pages) {
    await send('Page.navigate', { url: BASE + (name === 'overview' ? '/' : '/?view=' + name) });
    const ms = await waitFor(loaded(name), name + ' page', 120000);
    ok(`page renders: ${name}`, await js(`document.getElementById('view').textContent.includes(${JSON.stringify(text)})`), `${ms} ms`);
  }

  // 2. Rows: default page and totals equal the API's answer
  await send('Page.navigate', { url: BASE + '/?view=rows' });
  await waitFor(loaded('rows'), 'rows', 120000);
  let t = await api('/api/totals' + await rowsQS());
  ok('rows: 100 rows shown, matching rows = API totals', (await js(`document.querySelectorAll('#grid tbody tr').length`)) === 100
     && (await stat()) === t.rows.toLocaleString('en-US') && (await js(`!!document.querySelector('.recon.ok')`)), `${t.rows.toLocaleString('en-US')} rows`);

  // 3. a row filter through the form, limited to FY2025 by the global filter
  await send('Page.navigate', { url: BASE + '/?view=rows&g=' + encodeURIComponent(JSON.stringify({ fy: [2025, 2025] })) });
  await waitFor(loaded('rows'), 'rows FY2025', 120000);
  await reset();
  await js(`(() => { const f = document.querySelector('form.add-filter'); f.querySelector('input[list="col-list"]').value = 'awarding_agency_code';
    f.querySelector('select').value = 'is'; f.querySelector('input:not([list])').value = '097'; f.requestSubmit(); })()`);
  await waitFor(`(document.querySelector('.chips')?.textContent || '').includes('awarding_agency_code is 097') && ${loaded('rows')}`, 'filter chip', 120000);
  t = await api('/api/totals' + await rowsQS());
  ok('rows: filter through the form, totals = API', (await stat()) === t.rows.toLocaleString('en-US') && t.filtered === true,
     `${t.rows.toLocaleString('en-US')} rows; URL ${decodeURIComponent(await js('location.search')).slice(0, 120)}`);

  // 4. sort by clicking a header
  await reset();
  await js(`[...document.querySelectorAll('#grid thead th')].find(th => th.textContent.startsWith('federal_action_obligation')).click()`);
  await waitFor(`location.search.includes('federal_action_obligation') && ${loaded('rows')}`, 'sort', 120000);
  const firstTwo = await js(`(() => { const ths = [...document.querySelectorAll('#grid thead th')]; const i = ths.findIndex(th => th.textContent.startsWith('federal_action_obligation'));
    return [...document.querySelectorAll('#grid tbody tr')].slice(0, 2).map(tr => Number(tr.cells[i].textContent.replace(/[$,]/g, ''))); })()`);
  ok('rows: header click sorts descending', firstTwo.length === 2 && firstTwo[0] >= firstTwo[1], firstTwo.join(' >= '));

  // 5. row detail
  await js(`document.querySelector('#grid tbody tr').click()`);
  await waitFor(`document.getElementById('detail').open && document.querySelectorAll('#detail-table tr').length > 290`, 'detail', 60000);
  ok('rows: row detail lists every field', true, `${await js(`document.querySelectorAll('#detail-table tr').length`)} fields; ${await js(`document.getElementById('detail-h').textContent`)}`);
  await shot('ui_detail.png');
  await js(`document.getElementById('detail').close()`);

  // 6. group-by, then click a value to filter
  await reset();
  await js(`(() => { const g = document.querySelector('input[placeholder^="group by"]'); g.value = 'awarding_sub_agency_code'; g.dispatchEvent(new Event('change')); })()`);
  await waitFor(`!!document.querySelector('.gb-table tr.click') && ${loaded('rows')}`, 'group-by', 120000);
  const second = await js(`[...document.querySelectorAll('.gb-table tr.click')[1].cells].map(c => c.textContent)`);
  await reset();
  await js(`document.querySelectorAll('.gb-table tr.click')[1].click()`);
  await waitFor(`(document.querySelector('.chips')?.textContent || '').includes('awarding_sub_agency_code is ${second[1]}') && ${loaded('rows')}`, 'group-by click', 120000);
  ok('rows: clicking a group-by value filters to that group', (await stat()) === second[2], second.slice(1, 4).join(' | '));
  await shot('ui_rows_groupby.png');

  // 7. bookmark round trip
  const href = await js('location.href');
  await reset();
  await send('Page.navigate', { url: href });
  await waitFor(`${loaded('rows')} && !!document.querySelector('.gb-table')`, 'reload', 120000);
  ok('rows: bookmarked URL restores filters and group-by', (await stat()) === second[2], decodeURIComponent(href.split('?')[1] || '').slice(0, 140));

  // 8. pager
  await reset();
  await js(`[...document.querySelectorAll('.pager button')].find(b => b.textContent === '›').click()`);
  await waitFor(`(document.querySelector('.pager .pageinfo')?.textContent || '').startsWith('page 2 of') && ${loaded('rows')}`, 'page 2', 120000);
  ok('rows: next page', true, await js(`document.querySelector('.pager .pageinfo').textContent`));

  // 9. glossary: search, category filter and source links, each checked against the API
  await send('Page.navigate', { url: BASE + '/?view=glossary' });
  await waitFor(loaded('glossary'), 'glossary', 60000);
  const all = await api('/api/h/glossary');
  ok('glossary: every term listed', (await js(`document.querySelectorAll('.gl-entry').length`)) === all.total && all.total > 0,
     await js(`document.getElementById('gl-count').textContent`));
  await js(`(() => { const q = document.getElementById('gl-q'); q.value = 'obligation'; q.dispatchEvent(new Event('input')); })()`);
  const hit = await api('/api/h/glossary?q=obligation');
  await waitFor(`document.getElementById('gl-count').textContent === '${hit.terms.length} of ${all.total} terms'`, 'glossary search');
  ok('glossary: search narrows the list', hit.terms.length > 0 && hit.terms.length < all.total
     && (await js(`document.querySelectorAll('.gl-entry').length`)) === hit.terms.length, await js(`document.getElementById('gl-count').textContent`));
  await js(`(() => { const q = document.getElementById('gl-q'); q.value = ''; q.dispatchEvent(new Event('input'));
    const c = document.getElementById('gl-cat'); c.value = 'Money'; c.dispatchEvent(new Event('change')); })()`);
  const money = await api('/api/h/glossary?category=Money');
  await waitFor(`document.getElementById('gl-count').textContent === '${money.terms.length} of ${all.total} terms'`, 'glossary category');
  const links = await js(`[...document.querySelectorAll('.gl-entry a')].map(a => [a.getAttribute('href'), a.target, a.rel])`);
  ok('glossary: category filter and source links', links.length > 0 && links.every(([h, tg, rel]) => h.startsWith('https://') && tg === '_blank' && rel.includes('noopener')),
     `${money.terms.length} Money terms; ${links.length} links`);
  await js(`(() => { const c = document.getElementById('gl-cat'); c.value = ''; const q = document.getElementById('gl-q'); q.value = 'zzqqxx'; q.dispatchEvent(new Event('input')); })()`);
  await waitFor(`document.getElementById('gl-list').textContent.includes('No term matches.')`, 'glossary empty');
  ok('glossary: no match says so', true, await js(`document.getElementById('gl-count').textContent`));

  // 10. light mode screenshot of the glossary
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  await send('Page.navigate', { url: BASE + '/?view=glossary' });
  await waitFor(loaded('glossary'), 'glossary light', 60000);
  await shot('ui_glossary.png');
} catch (e) {
  ok('script', false, e.message);
} finally {
  ok('no JS errors, failed requests, or external requests', problems.length === 0, problems.join(' ; ').slice(0, 400));
  ws.close();
  chrome.kill();
  writeFileSync(join(OUT, 'ui_results.json'), JSON.stringify(results, null, 1));
  const passed = results.filter((r) => r[0] === 'PASS').length;
  console.log(`\n${passed}/${results.length} passed. Screenshots and ui_results.json in ${OUT}`);
  process.exitCode = passed === results.length ? 0 : 1;
}
