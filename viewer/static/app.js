'use strict';
// Data-health dashboard. Plain JS, no libraries, talks only to the local server. Data is inserted with
// textContent (never innerHTML). Money stays the exact decimal string the server sends.

const S = { hmeta: null, rmeta: null, view: 'overview', g: null, rows: null, colIndex: {}, values: {}, seq: 0 };
const VIEWS = ['overview', 'completeness', 'columns', 'flags', 'rows', 'decisions', 'glossary'];
const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids) if (k !== null && k !== undefined && k !== false) e.append(k);
  return e;
};

// ------------------------------------------------------------------ formatting
function fmtMoney(s) {
  if (s === null || s === undefined || s === '') return '';
  s = String(s);
  const neg = s.startsWith('-');
  if (neg) s = s.slice(1);
  let [i, f = ''] = s.split('.');
  i = i.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  if (f.length < 2) f = (f + '00').slice(0, 2);
  return (neg ? '-' : '') + '$' + i + '.' + f;
}
function fmtBig(s) {   // display-only short form; the exact value is in the title
  if (s === null || s === undefined) return '';
  const x = Number(s);
  const a = Math.abs(x);
  const t = a >= 1e9 ? (x / 1e9).toFixed(2) + 'B' : a >= 1e6 ? (x / 1e6).toFixed(1) + 'M' : a >= 1e3 ? (x / 1e3).toFixed(0) + 'K' : x.toFixed(0);
  return (x < 0 ? '-$' + t.slice(1) : '$' + t);
}
const fmtInt = (n) => (n === null || n === undefined || n === '') ? '' : Number(n).toLocaleString('en-US');
const isNeg = (s) => typeof s === 'string' && s.startsWith('-') && /[1-9]/.test(s);
const pct = (num, den) => den ? (100 * num / den) : null;
const fmtPct = (p) => p === null ? '' : (p < 0.01 && p > 0 ? '<0.01%' : p.toFixed(p < 10 ? 2 : 1) + '%');
function shade(p) {   // 0..100 -> background color (display only)
  if (p === null) return '';
  const t = Math.min(1, Math.sqrt(p / 100));
  return `hsl(${210 - 210 * t}, 70%, ${92 - 45 * t}%)`;
}

// ------------------------------------------------------------------ server
async function api(path, params) {
  const res = await fetch(path + (params ? '?' + params.toString() : ''));
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}
async function post(path, body) {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const out = await res.json();
  if (!res.ok) throw new Error(out.error || res.statusText);
  return out;
}
function showError(msg) { const b = $('error'); b.textContent = msg ? 'Error: ' + msg : ''; b.hidden = !msg; }
function setStatus(msg) { $('status').textContent = msg || ''; }
const gParam = () => JSON.stringify(S.g);
const gQS = (extra = {}) => new URLSearchParams({ g: gParam(), ...extra });

// ------------------------------------------------------------------ URL state
function readURL() {
  const p = new URLSearchParams(location.search);
  S.view = VIEWS.includes(p.get('view')) ? p.get('view') : 'overview';
  const def = { fy: [S.hmeta.first_fy, S.hmeta.last_fy], agency: [], subagency: [], award_type: [], psc_cat: [] };
  try { S.g = { ...def, ...(p.get('g') ? JSON.parse(p.get('g')) : {}) }; } catch { S.g = def; }
  S.rows = rowsStateFromParams(p);
  S.colDetail = p.get('col') || null;
  S.decTarget = p.get('dt') ? { type: p.get('dtt') || 'flag', target: p.get('dt') } : null;
}
function writeURL(push = true) {
  const p = new URLSearchParams();
  if (S.view !== 'overview') p.set('view', S.view);
  const def = S.g.fy[0] === S.hmeta.first_fy && S.g.fy[1] === S.hmeta.last_fy && !['agency', 'subagency', 'award_type', 'psc_cat'].some((d) => S.g[d].length);
  if (!def) p.set('g', gParam());
  if (S.view === 'rows') for (const [k, v] of rowsAddress(S.rows)) p.set(k, v);
  const qs = p.toString();
  if (push) history.pushState(null, '', qs ? '?' + qs : location.pathname);
}
function go(view, patch = {}) {
  S.view = view;
  Object.assign(S, patch);
  writeURL();
  render();
}

// ------------------------------------------------------------------ global filters
function fillGlobal() {
  const m = S.hmeta;
  for (const id of ['g-lo', 'g-hi']) {
    $(id).replaceChildren(...m.years_in_scope.map((y) => el('option', { value: String(y),
      text: `FY${y}${m.years_pending.includes(y) ? ' (pending)' : ''}` })));
  }
  const opt = (v, label) => el('option', { value: v, text: label });
  $('g-agency').replaceChildren(...m.agencies.map((a) => opt(a.value, `${a.value || '(blank)'} ${a.label || ''}`)));
  $('g-subagency').replaceChildren(...m.subagencies.map((a) => opt(a.value, `${a.value || '(blank)'} ${a.label || ''}`)));
  $('g-award_type').replaceChildren(...m.award_types.map((a) => opt(a.value, `${a.value || '(blank)'}  (${fmtInt(a.rows)})`)));
  $('g-psc_cat').replaceChildren(...m.psc_cats.map((a) => opt(a.value, `${a.value || '(blank)'}  (${fmtInt(a.rows)})`)));
}
function syncGlobal() {
  $('g-lo').value = String(S.g.fy[0]);
  $('g-hi').value = String(S.g.fy[1]);
  for (const d of ['agency', 'subagency', 'award_type', 'psc_cat']) {
    const chosen = new Set(S.g[d]);
    for (const o of $('g-' + d).options) o.selected = chosen.has(o.value);
  }
  const parts = [`FY${S.g.fy[0]}–FY${S.g.fy[1]}`];
  for (const d of ['agency', 'subagency', 'award_type', 'psc_cat']) if (S.g[d].length) parts.push(`${d}: ${S.g[d].join(', ')}`);
  const pend = S.hmeta.years_pending.filter((y) => y >= S.g.fy[0] && y <= S.g.fy[1]);
  $('g-note').textContent = 'Showing ' + parts.join(' · ')
    + (pend.length ? ` · ${pend.map((y) => 'FY' + y).join(', ')} pending (not yet downloaded), shown as pending, not as a gap.` : '');
}
function readGlobal() {
  let lo = parseInt($('g-lo').value, 10), hi = parseInt($('g-hi').value, 10);
  if (lo > hi) [lo, hi] = [hi, lo];
  const g = { fy: [lo, hi] };
  for (const d of ['agency', 'subagency', 'award_type', 'psc_cat']) g[d] = [...$('g-' + d).selectedOptions].map((o) => o.value);
  return g;
}

// ------------------------------------------------------------------ markdown (safe: textContent only)
function inline(text) {
  const frag = document.createDocumentFragment();
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|<https?:[^>]+>)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) frag.append(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith('**')) frag.append(el('strong', { text: t.slice(2, -2) }));
    else if (t.startsWith('`')) frag.append(el('code', { text: t.slice(1, -1) }));
    else if (t.startsWith('<')) { const u = t.slice(1, -1); frag.append(el('a', { href: u, target: '_blank', rel: 'noopener noreferrer', text: u })); }
    else { const mm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(t); const u = mm[2];
      frag.append(/^https?:\/\//.test(u) ? el('a', { href: u, target: '_blank', rel: 'noopener noreferrer', text: mm[1] }) : el('span', { text: mm[1] })); }
    last = m.index + t.length;
  }
  if (last < text.length) frag.append(text.slice(last));
  return frag;
}
function mdToDom(md) {
  const root = el('div', { class: 'md' });
  const lines = md.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    if (/^#{1,3} /.test(ln)) { const n = ln.indexOf(' '); root.append(el('h' + Math.min(3, n), {}, inline(ln.slice(n + 1)))); continue; }
    if (ln.startsWith('|')) {
      const t = el('table');
      for (; i < lines.length && lines[i].startsWith('|'); i++) {
        if (/^\|[-| ]+\|$/.test(lines[i])) continue;
        const cells = lines[i].slice(1, -1).split(' | ').map((c) => c.trim());
        t.append(el('tr', {}, ...cells.map((c) => el('td', {}, inline(c)))));
      }
      i--; root.append(t); continue;
    }
    if (/^\s*- /.test(ln)) {
      const ul = el('ul');
      for (; i < lines.length && /^\s*- /.test(lines[i]); i++) ul.append(el('li', {}, inline(lines[i].replace(/^\s*- /, ''))));
      i--; root.append(ul); continue;
    }
    if (ln.trim()) root.append(el('p', {}, inline(ln)));
  }
  return root;
}

// ------------------------------------------------------------------ render dispatcher
async function render() {
  const seq = ++S.seq;
  showError('');
  syncGlobal();
  document.querySelectorAll('.tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === S.view)));
  const view = $('view');
  view.replaceChildren(el('p', { class: 'muted', text: 'Loading…' }));
  const t0 = performance.now();
  try {
    const fn = { overview: viewOverview, completeness: viewCompleteness, columns: viewColumns, flags: viewFlags,
                 rows: viewRows, decisions: viewDecisions, glossary: viewGlossary }[S.view];
    const node = await fn(seq);
    if (seq !== S.seq) return;
    if (node) view.replaceChildren(node);
    setStatus(`${S.view} loaded in ${Math.round(performance.now() - t0)} ms`);
  } catch (e) {
    if (seq === S.seq) { view.replaceChildren(); showError(e.message); }
  }
}

// ------------------------------------------------------------------ overview
async function viewOverview() {
  const d = await api('/api/h/overview', gQS());
  const cards = el('div', { class: 'cards' });
  for (const c of d.cards) {
    if (c.status === 'not profiled') {
      cards.append(el('div', { class: 'card pending' }, el('h3', { text: `FY${c.fiscal_year}` }), el('p', { text: c.note })));
      continue;
    }
    if (c.status === 'pending') {
      cards.append(el('div', { class: 'card pending' }, el('h3', { text: `FY${c.fiscal_year}` }),
        el('p', { text: 'Pending: not yet downloaded. Not a gap in the data.' }),
        ...c.benchmarks.map((b) => el('div', { class: 'kv' }, el('span', { text: b.id }), el('span', { class: 'badge pending', text: 'pending' })))));
      continue;
    }
    const sev = c.flags;
    cards.append(el('div', { class: 'card' },
      el('h3', { text: `FY${c.fiscal_year}` }),
      el('div', { class: 'kv' }, el('span', { text: 'Rows' }), el('span', { class: 'v', text: fmtInt(c.rows) })),
      el('div', { class: 'kv' }, el('span', { text: 'Net obligations' }), el('span', { class: 'v', title: fmtMoney(c.net), text: fmtBig(c.net) })),
      el('div', { class: 'kv' }, el('span', { text: 'Release' }), el('span', { class: 'v', text: c.release })),
      el('div', { class: 'kv' }, el('span', { text: 'Stage 1 proof' }), el('span', { class: 'badge ' + (c.proof || ''), text: c.proof || '?' })),
      ...(c.benchmarks.length ? c.benchmarks.map((b) => el('div', { class: 'kv' },
        el('a', { href: b.url, target: '_blank', rel: 'noopener noreferrer', text: b.id }),
        el('span', { class: 'badge ' + b.status.replace(' ', '-'), title: b.gap_pct ? `gap ${b.gap_pct}%` : '', text: b.status + (b.gap_pct ? ` ${b.gap_pct}%` : '') })))
        : [el('div', { class: 'kv' }, el('span', { class: 'muted', text: 'No independent benchmark' }))]),
      el('div', { class: 'sevbar' },
        el('span', { class: 'badge serious', title: 'flagged rows, serious flags', text: `serious ${fmtInt(sev.serious)}` }),
        el('span', { class: 'badge review', title: 'flagged rows, review flags', text: `review ${fmtInt(sev.review)}` }),
        el('span', { class: 'badge info', title: 'flagged rows, info flags', text: `info ${fmtInt(sev.info)}` }))));
  }
  const findings = el('div', {}, ...d.findings.map((f) => el('div', { class: 'finding' },
    el('span', { class: 'badge ' + f.severity, text: f.severity }),
    el('a', { href: '#', text: `${f.flag_id} ${f.name}`, onclick: (e) => { e.preventDefault(); go('rows', { rows: { ...defaultRows(), flag: f.flag_id } }); } }),
    el('span', { class: 'num', text: `${fmtInt(f.rows)} rows · ${fmtBig(f.gross)} gross · ${f.years} yrs`, title: fmtMoney(f.gross) }),
    el('span', { class: 'why', text: f.why }))));
  return el('div', {},
    el('section', { class: 'panel' }, el('h2', { text: 'Fiscal years' }),
      el('p', { class: 'hint', text: 'Row counts, net obligations and flag counts respect the global filters. Flag counts are flagged rows (row-level flags), by severity.' }), cards),
    el('div', { class: 'two' },
      el('section', { class: 'panel' }, el('h2', { text: 'What jumps off the page' }),
        el('p', { class: 'hint', text: 'Row-level flags with hits, serious first, then by gross dollars affected. Click to see the rows.' }), findings),
      el('section', { class: 'panel' }, el('h2', { text: 'Integrity summary (reports/integrity/integrity_summary.md)' }),
        d.filtered ? el('p', { class: 'hint', text: 'This summary covers all present years and is not filtered.' }) : null,
        el('div', { class: 'scroll' }, mdToDom(d.summary_md)))));
}

// ------------------------------------------------------------------ completeness
async function viewCompleteness() {
  const d = await api('/api/h/completeness', gQS());
  const bm = el('table', { class: 'plain' }, el('thead', {}, el('tr', {}, ...['FY', 'Benchmark', 'Scope', 'Status', 'Ours', 'Published', 'Gap', 'Gap %', 'Source data as of']
    .map((h) => el('th', { class: ['Ours', 'Published', 'Gap', 'Gap %'].includes(h) ? 'num' : '', text: h })))));
  const tb = el('tbody');
  for (const r of d.benchmarks) {
    tb.append(el('tr', {},
      el('td', { text: r.fiscal_year }),
      el('td', {}, el('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer', title: r.title, text: r.benchmark_id })),
      el('td', { text: r.agency || 'government-wide' }),
      el('td', {}, el('span', { class: 'badge ' + r.status.replace(' ', '-'), text: r.status })),
      el('td', { class: 'num', text: fmtMoney(r.ours) }), el('td', { class: 'num', text: fmtMoney(r.figure) }),
      el('td', { class: 'num' + (isNeg(r.gap_dollars) ? ' neg' : ''), text: fmtMoney(r.gap_dollars) }),
      el('td', { class: 'num', text: r.gap_pct ? r.gap_pct + '%' : '' }), el('td', { text: r.source_data_as_of })));
  }
  bm.append(tb);
  const metric = S.compMetric || 'rows';
  const years = d.years;
  const monthsByKey = new Map(d.months.map((m) => [m.fiscal_year + '|' + m.month, m]));
  const heat = el('table', { class: 'heat' });
  const fyMonths = ['10', '11', '12', '01', '02', '03', '04', '05', '06', '07', '08', '09'];
  heat.append(el('tr', {}, el('th', { class: 'rowh', text: 'FY \\ month' }), ...fyMonths.map((mm) => el('th', { text: ['Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep'][fyMonths.indexOf(mm)] }))));
  for (const fy of years) {
    const tr = el('tr', {}, el('th', { class: 'rowh', text: 'FY' + fy }));
    const vals = fyMonths.map((mm) => monthsByKey.get(fy + '|' + `${mm >= '10' ? fy - 1 : fy}-${mm}`));
    const nums = vals.map((v) => v ? Math.abs(Number(metric === 'rows' ? v.rows : v.net)) : 0);
    const max = Math.max(1, ...nums);
    vals.forEach((v, i) => {
      if (d.pending.includes(fy)) { tr.append(el('td', { class: 'pending', title: 'pending - not yet downloaded', text: '' })); return; }
      if (!v) { tr.append(el('td', { class: 'empty', text: '0' })); return; }
      const flagged = metric === 'rows' ? v.thin_rows : v.thin_dollars;
      const td = el('td', { class: flagged ? 'flagged' : '', title: `${v.month}: ${fmtInt(v.rows)} rows, ${fmtMoney(v.net)}${flagged ? ' — thin month (H01/H02)' : ''}`,
        text: metric === 'rows' ? (v.rows >= 1e6 ? (v.rows / 1e6).toFixed(1) + 'M' : Math.round(v.rows / 1e3) + 'K') : fmtBig(v.net) });
      td.style.background = shade(100 * nums[i] / max);
      tr.append(td);
    });
    heat.append(tr);
  }
  // agency x year matrix
  const names = {}; const cells = {};
  for (const a of d.agency_matrix) { names[a.agency] = a.name; (cells[a.agency] ||= {})[a.fiscal_year] = a; }
  const aflag = {}; for (const f of d.agency_flags) (aflag[f.agency + '|' + f.fiscal_year] ||= []).push(`${f.flag_id}: ${f.detail}`);
  const agencies = Object.keys(cells).sort((x, y) => Object.values(cells[y]).reduce((s, c) => s + c.rows, 0) - Object.values(cells[x]).reduce((s, c) => s + c.rows, 0));
  const mat = el('table', { class: 'heat' });
  mat.append(el('tr', {}, el('th', { class: 'rowh', text: 'Awarding agency' }), ...years.map((y) => el('th', { text: String(y).slice(2) }))));
  for (const a of agencies) {
    const tr = el('tr', {}, el('th', { class: 'rowh', title: `${a} ${names[a]}`, text: `${a || '(blank)'} ${names[a] || ''}` }));
    const maxRows = Math.max(1, ...Object.values(cells[a]).map((c) => c.rows));
    for (const y of years) {
      if (d.pending.includes(y)) { tr.append(el('td', { class: 'pending', title: 'pending - not yet downloaded' })); continue; }
      const c = cells[a][y];
      const fl = aflag[a + '|' + y];
      if (!c) { tr.append(el('td', { class: 'empty' + (fl ? ' flagged' : ''), title: fl ? fl.join('\n') : 'no rows', text: '–' })); continue; }
      const td = el('td', { class: fl ? 'flagged' : '', title: `FY${y} ${a}: ${fmtInt(c.rows)} rows, ${fmtMoney(c.net)}${fl ? '\n' + fl.join('\n') : ''}`,
        text: c.rows >= 1e6 ? (c.rows / 1e6).toFixed(1) + 'M' : c.rows >= 1e3 ? Math.round(c.rows / 1e3) + 'K' : String(c.rows) });
      td.style.background = shade(100 * c.rows / maxRows);
      td.addEventListener('click', () => go('rows', { g: { ...S.g, fy: [y, y], agency: [a] }, rows: defaultRows() }));
      tr.append(td);
    }
    mat.append(tr);
  }
  const sel = el('select', { onchange: (e) => { S.compMetric = e.target.value; render(); } },
    el('option', { value: 'rows', text: 'rows' }), el('option', { value: 'net', text: 'net obligations' }));
  sel.value = metric;
  return el('div', {},
    el('section', { class: 'panel' }, el('h2', { text: 'Our totals against published benchmarks' }),
      el('p', { class: 'hint', text: 'Thresholds fixed before comparing (flag catalog I01/I02): PASS within 2%, WARN within 10%, FAIL beyond. Benchmark rows are government-wide and are never filtered.' }),
      el('div', { class: 'scroll' }, bm),
      el('details', {}, el('summary', { text: 'Full completeness report with citations' }), mdToDom(d.benchmark_md))),
    el('section', { class: 'panel' }, el('div', { class: 'panel-head' }, el('h2', { text: 'Month × year' }), el('label', { class: 'field' }, el('span', { text: 'Show' }), sel)),
      el('p', { class: 'hint', text: 'Shading is relative to each year’s largest month. Red outline = thin month (below 50% of that year’s median; H01 rows, H02 dollars), computed on unfiltered data. September is the usual year-end spike.' }),
      el('div', { class: 'scroll' }, heat)),
    el('section', { class: 'panel' }, el('h2', { text: 'Agency × year (rows)' }),
      el('p', { class: 'hint', text: 'Shading is relative to each agency’s largest year. Red outline = H03 missing middle year or H04/H05 drop that recovers. Striped = pending year. Click a cell to see its rows.' }),
      el('div', { class: 'scroll' }, mat)));
}

// ------------------------------------------------------------------ column quality
async function viewColumns() {
  const metric = S.colMetric || 'blank';
  const d = await api('/api/h/columns', gQS({ metric }));
  const t = el('table', { class: 'heat' });
  t.append(el('tr', {}, el('th', { class: 'rowh', text: `column (${d.columns.length})` }), el('th', { text: 'guide' }),
    ...d.years.map((y) => el('th', { text: String(y).slice(2) }))));
  const verdictFilter = S.colVerdict || '';
  for (const c of d.columns) {
    if (verdictFilter && c.verdict !== verdictFilter) continue;
    const tr = el('tr', {}, el('th', { class: 'rowh', title: `${c.position}. ${c.name}\n${c.group}`, text: c.name }),
      el('td', { class: 'empty', title: c.verdict, text: c.verdict ? c.verdict[0] : '' }));
    for (const y of d.years) {
      if (d.pending.includes(y)) { tr.append(el('td', { class: 'pending', title: 'pending - not yet downloaded' })); continue; }
      const cell = c.cells[y];
      if (!cell || !cell.rows) { tr.append(el('td', { class: 'empty', text: '' })); continue; }
      const p = pct(cell.count, cell.rows);
      const td = el('td', { title: `${c.name}, FY${y}: ${fmtInt(cell.count)} of ${fmtInt(cell.rows)} rows (${fmtPct(p)}) ${metric}`,
        text: p >= 99.95 ? '100' : p >= 1 ? Math.round(p) : p > 0 ? '·' : '' });
      td.style.background = shade(p);
      td.addEventListener('click', () => openColumn(c.name, y));
      tr.append(td);
    }
    t.append(tr);
  }
  const msel = el('select', { onchange: (e) => { S.colMetric = e.target.value; render(); } },
    ...['blank', 'zero', 'placeholder'].map((m) => el('option', { value: m, text: `% ${m}` })));
  msel.value = metric;
  const vsel = el('select', { onchange: (e) => { S.colVerdict = e.target.value; render(); } },
    el('option', { value: '', text: 'all columns' }), ...['Core', 'Useful', 'Skip'].map((v) => el('option', { value: v, text: v + ' only' })));
  vsel.value = verdictFilter;
  return el('section', { class: 'panel' },
    el('div', { class: 'panel-head' }, el('h2', { text: 'Column × year' }),
      el('label', { class: 'field' }, el('span', { text: 'Metric' }), msel),
      el('label', { class: 'field' }, el('span', { text: 'Column guide rating' }), vsel)),
    el('p', { class: 'hint', text: 'Cell = percent of rows (whole number; · = under 1%). Blank = empty or whitespace only. Placeholder = UNKNOWN, N/A, NONE, MULTIPLE RECIPIENTS and similar (flag catalog E03). Respects all global filters. Click a cell for top values, placeholders and the column’s meaning.' }),
    el('div', { class: 'scroll' }, t));
}

async function openColumn(name, fy) {
  const d = await api('/api/h/column', new URLSearchParams({ name, fy: String(fy), g: gParam() }));
  const g = d.guide || {};
  const prof = el('table', { class: 'plain' }, el('tr', {}, ...['FY', 'rows', 'blank', 'zero', 'placeholder', 'distinct', 'min', 'max', 'lead/trail space', 'case variants', 'max length']
    .map((h) => el('th', { text: h }))),
    ...d.profile.map((p) => el('tr', { class: p.fiscal_year === fy ? 'click' : '' },
      el('td', { text: p.fiscal_year }), el('td', { class: 'num', text: fmtInt(p.rows) }),
      el('td', { class: 'num', text: fmtPct(pct(p.blank, p.rows)) }), el('td', { class: 'num', text: fmtPct(pct(p.zero, p.rows)) }),
      el('td', { class: 'num', text: fmtPct(pct(p.placeholder, p.rows)) }), el('td', { class: 'num', text: fmtInt(p.distinct_nonblank) }),
      el('td', { text: (p.min_value || '').slice(0, 30) }), el('td', { text: (p.max_value || '').slice(0, 30) }),
      el('td', { class: 'num', text: fmtInt(p.lead_trail_space) }), el('td', { class: 'num', text: fmtInt(p.case_variant_values) }),
      el('td', { class: 'num', text: fmtInt(p.max_length) }))));
  const tops = el('table', { class: 'plain' }, el('tr', {}, el('th', { text: '#' }), el('th', { text: `top values, FY${fy}` }), el('th', { class: 'num', text: 'rows' })),
    ...d.top_values.map((t) => el('tr', {}, el('td', { text: t.rank }), el('td', { text: t.value === '' ? '(blank)' : t.value }), el('td', { class: 'num', text: fmtInt(t.n) }))));
  const phs = d.placeholders.length ? el('table', { class: 'plain' }, el('tr', {}, el('th', { text: 'placeholder-looking value' }), el('th', { class: 'num', text: 'rows' })),
    ...d.placeholders.map((t) => el('tr', {}, el('td', { text: JSON.stringify(t.value) }), el('td', { class: 'num', text: fmtInt(t.n) }))))
    : el('p', { class: 'muted', text: 'No placeholder-looking values this year.' });
  $('detail-h').textContent = `${name} — FY${fy}`;
  $('detail-body').replaceChildren(
    el('p', {}, el('strong', { text: g.verdict ? `${g.verdict}. ` : '' }), g.meaning || '(not in the column guide)'),
    g.why ? el('p', { class: 'hint', text: g.why }) : null,
    el('p', { class: 'hint', text: g.group || '' }),
    el('div', { class: 'detail-actions' },
      el('button', { class: 'primary', text: 'Record a decision about this column', onclick: () => { $('detail').close(); go('decisions', { decTarget: { type: 'column', target: name } }); } }),
      el('button', { text: `Browse FY${fy} rows where this column is blank`, onclick: () => { $('detail').close(); go('rows', { g: { ...S.g, fy: [fy, fy] }, rows: { ...defaultRows(), f: [[name, 'blank']] } }); } })),
    el('h3', { text: 'Profile by year (unfiltered)' }), el('div', { class: 'scroll' }, prof),
    el('div', { class: 'two' }, el('div', {}, tops), el('div', {}, phs)));
  if (!$('detail').open) $('detail').showModal();
}

// ------------------------------------------------------------------ flags
async function viewFlags() {
  const d = await api('/api/h/flags', gQS());
  const years = d.years;
  const t = el('table', { class: 'plain' });
  t.append(el('thead', {}, el('tr', {}, el('th', { text: 'Flag' }), el('th', { text: 'Severity' }), el('th', { text: 'Name / rule' }),
    el('th', { class: 'num', text: 'Total' }), ...years.map((y) => el('th', { class: 'num', text: String(y).slice(2) })), el('th', { text: '' }))));
  const tb = el('tbody');
  const sev = { serious: 0, review: 1, info: 2 };
  const flags = d.flags.slice().sort((a, b) => sev[a.severity] - sev[b.severity] || b.total - a.total);
  for (const f of flags) {
    const tr = el('tr', {},
      el('td', { text: f.flag_id }), el('td', {}, el('span', { class: 'badge ' + f.severity, text: f.severity })),
      el('td', {}, el('div', { text: f.name }), el('div', { class: 'hint', text: f.rule }),
        f.fy2015_handling ? el('div', { class: 'hint', text: f.fy2015_handling }) : null,
        !f.filter_applies && d.filtered ? el('div', { class: 'hint', text: '(not a row-level flag: counts are unfiltered)' }) : null),
      el('td', { class: 'num', text: fmtInt(f.total) }));
    for (const y of years) {
      const c = f.by_year[String(y)];
      if (d.pending.includes(y)) { tr.append(el('td', { class: 'num muted', title: 'pending - not yet downloaded', text: '—' })); continue; }
      tr.append(el('td', { class: 'num', title: c && c.net ? `net ${fmtMoney(c.net)}, gross ${fmtMoney(c.gross)}` : (c && c.unit) || '',
        // the flag cube holds only flags with hits, so a row-level flag missing for a present year fired 0 times
        text: c ? fmtInt(c.count) : (f.level === 'row' ? '0' : '') }));
    }
    tr.append(el('td', {},
      f.level === 'row' && f.total ? el('button', { class: 'quiet', text: 'rows', onclick: () => go('rows', { rows: { ...defaultRows(), flag: f.flag_id } }) }) : null,
      el('button', { class: 'quiet', text: 'decide', onclick: () => go('decisions', { decTarget: { type: 'flag', target: f.flag_id } }) })));
    tb.append(tr);
  }
  t.append(tb);
  return el('section', { class: 'panel' }, el('h2', { text: 'Every flag (config/flag_catalog.csv)' }),
    el('p', { class: 'hint', text: 'Row-level flags count flagged transaction rows and respect every global filter; hover a cell for dollars. Other flags count items (codes, IDs, agency-years, months) and are not filtered by agency, award type or PSC. Outliers (J01-J04) are review lists: every outlier stays in the data, and round amounts can be legitimate.' }),
    el('div', { class: 'scroll' }, t));
}

// ------------------------------------------------------------------ rows
function defaultRows() {
  return { f: [], flag: '', sort: 'action_date', dir: 'desc', cols: [...S.rmeta.default_cols], page: 1, gb: '', gbo: 'rows' };
}
function rowsStateFromParams(p) {
  const st = defaultRows();
  try { if (p.get('f')) st.f = JSON.parse(p.get('f')); } catch { st.f = []; }
  if (!Array.isArray(st.f)) st.f = [];
  st.f = st.f.filter((x) => Array.isArray(x) && S.colIndex[x[0]]);
  if (p.get('flag')) st.flag = p.get('flag');
  if (S.colIndex[p.get('sort')]) st.sort = p.get('sort');
  if (['asc', 'desc'].includes(p.get('dir'))) st.dir = p.get('dir');
  if (p.get('cols')) { const c = p.get('cols').split(',').filter((x) => S.colIndex[x]); if (c.length) st.cols = c; }
  st.page = Math.max(1, parseInt(p.get('page') || '1', 10) || 1);
  if (S.colIndex[p.get('gb')]) st.gb = p.get('gb');
  if (p.get('gbo') === 'net') st.gbo = 'net';
  return st;
}
function rowsAddress(st) {
  const out = [];
  if (st.f.length) out.push(['f', JSON.stringify(st.f)]);
  if (st.flag) out.push(['flag', st.flag]);
  if (st.sort !== 'action_date' || st.dir !== 'desc') { out.push(['sort', st.sort]); out.push(['dir', st.dir]); }
  if (st.cols.join(',') !== S.rmeta.default_cols.join(',')) out.push(['cols', st.cols.join(',')]);
  if (st.page !== 1) out.push(['page', String(st.page)]);
  if (st.gb) { out.push(['gb', st.gb]); if (st.gbo !== 'rows') out.push(['gbo', st.gbo]); }
  return out;
}
function rowsParams(st, extra = {}) {
  const p = new URLSearchParams({ g: gParam(), sort: st.sort, dir: st.dir, cols: st.cols.join(','), page: String(st.page) });
  if (st.f.length) p.set('f', JSON.stringify(st.f));
  if (st.flag) p.set('flag', st.flag);
  if (st.gb) { p.set('gb', st.gb); p.set('gbo', st.gbo); }
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p;
}
function setRows(patch, resetPage = true) {
  S.rows = { ...S.rows, ...patch };
  if (resetPage && !('page' in patch)) S.rows.page = 1;
  writeURL();
  render();
}
async function getValues(col) {
  if (!S.values[col]) S.values[col] = await api('/api/values', new URLSearchParams({ column: col }));
  return S.values[col];
}

async function viewRows() {
  const st = S.rows;
  const [r, t, gbr] = await Promise.all([
    api('/api/rows', rowsParams(st)), api('/api/totals', rowsParams(st)),
    st.gb ? api('/api/groupby', rowsParams(st)) : Promise.resolve(null)]);
  const kinds = r.kinds;
  // chips
  const chips = el('div', { class: 'chips' });
  if (st.flag) chips.append(el('span', { class: 'chip' }, el('span', { class: 'text', text: `flag ${st.flag}` }),
    el('button', { type: 'button', text: '✕', onclick: () => setRows({ flag: '' }) })));
  st.f.forEach((f, i) => chips.append(el('span', { class: 'chip' }, el('span', { class: 'text', text: f[1] === 'blank' ? `${f[0]} is blank` : `${f[0]} ${f[1]} ${f[2]}` }),
    el('button', { type: 'button', text: '✕', onclick: () => setRows({ f: st.f.filter((_, j) => j !== i) }) }))));
  if (!st.flag && !st.f.length) chips.append(el('span', { class: 'muted', text: 'No row filters (global filters still apply).' }));
  // add filter
  const colIn = el('input', { list: 'col-list', placeholder: 'column…', spellcheck: 'false', size: '28' });
  const opSel = el('select', {}, ...['is', 'contains', 'eq', 'blank', 'min', 'max'].map((o) => el('option', { value: o, text: o })));
  const valIn = el('input', { placeholder: 'value', size: '24' });
  const flagSel = el('select', { onchange: (e) => setRows({ flag: e.target.value }) }, el('option', { value: '', text: '(any)' }),
    ...S.hmeta.catalog.filter((f) => f.level === 'row').map((f) => el('option', { value: f.flag_id, text: `${f.flag_id} ${f.name}` })));
  flagSel.value = st.flag || '';
  const form = el('form', { class: 'add-filter', onsubmit: (e) => {
    e.preventDefault();
    const c = colIn.value.trim();
    if (!S.colIndex[c]) return showError('pick a column from the list');
    const op = opSel.value;
    setRows({ f: [...st.f, op === 'blank' ? [c, 'blank'] : [c, op, valIn.value]] });
  } }, el('label', { class: 'field' }, el('span', { text: 'Column' }), colIn), el('label', { class: 'field' }, el('span', { text: 'Operator' }), opSel),
    el('label', { class: 'field' }, el('span', { text: 'Value' }), valIn), el('button', { type: 'submit', class: 'primary', text: 'Add filter' }),
    el('label', { class: 'field' }, el('span', { text: 'Flag' }), flagSel));
  // totals
  const ref = t.reference;
  const recon = !t.filtered ? (t.matches_reference
    ? el('p', { class: 'recon ok', text: `✓ No filters: equals the Stage 1 proof totals for FY${ref.years[0]}–FY${ref.years[ref.years.length - 1]} (${fmtInt(ref.rows)} rows; ${fmtMoney(ref.net)}).` })
    : el('p', { class: 'recon bad', text: `✗ No filters, but this does NOT equal the Stage 1 proof totals (${fmtInt(ref.rows)} rows; ${fmtMoney(ref.net)}).` }))
    : el('p', { class: 'recon info', text: 'Filtered view.' });
  // grid
  const head = el('tr', {}, ...st.cols.map((c) => el('th', { title: `${c} (${kinds[c]})`, text: c + (st.sort === c ? (st.dir === 'desc' ? ' ▼' : ' ▲') : ''),
    onclick: () => setRows(st.sort === c ? { dir: st.dir === 'desc' ? 'asc' : 'desc' } : { sort: c, dir: kinds[c] === 'text' ? 'asc' : 'desc' }) })));
  const body = el('tbody');
  if (!r.rows.length) body.append(el('tr', { class: 'empty' }, el('td', { colspan: String(st.cols.length), text: 'No rows.' })));
  r.rows.forEach((row, i) => {
    const [key, y, m, n] = r.keys[i];
    const tr = el('tr', { title: key, onclick: () => openRow(y, m, n) });
    row.forEach((v, j) => {
      const k = kinds[st.cols[j]];
      tr.append(v === null ? el('td', { class: 'null' }) : k === 'decimal' ? el('td', { class: 'num' + (isNeg(v) ? ' neg' : ''), text: fmtMoney(v) })
        : el('td', { class: k === 'int' ? 'num' : '', title: String(v), text: String(v) }));
    });
    body.append(tr);
  });
  const pages = Math.max(1, Math.ceil(t.rows / r.page_size));
  const pager = el('nav', { class: 'pager' },
    el('button', { text: '«', disabled: st.page <= 1, onclick: () => setRows({ page: 1 }, false) }),
    el('button', { text: '‹', disabled: st.page <= 1, onclick: () => setRows({ page: st.page - 1 }, false) }),
    el('span', { class: 'pageinfo', text: `page ${fmtInt(st.page)} of ${fmtInt(pages)}` }),
    el('button', { text: '›', disabled: st.page >= pages, onclick: () => setRows({ page: st.page + 1 }, false) }),
    el('a', { class: 'button', href: '/api/export.csv?' + rowsParams(st).toString(), download: true, text: 'Export CSV' }),
    el('span', { class: 'hint', text: t.rows > S.rmeta.export_cap ? `export capped at ${fmtInt(S.rmeta.export_cap)} rows` : '' }));
  // columns picker (compact)
  const pick = el('select', { multiple: true, size: '8', onchange: (e) => { const c = [...e.target.selectedOptions].map((o) => o.value); if (c.length) setRows({ cols: c }, false); } },
    ...S.rmeta.columns.map((c) => el('option', { value: c.name, selected: st.cols.includes(c.name), text: `${c.position}. ${c.name}` })));
  // group-by
  const gbIn = el('input', { list: 'col-list', placeholder: 'group by column…', value: st.gb, size: '30',
    onchange: (e) => { if (S.colIndex[e.target.value]) setRows({ gb: e.target.value }, false); } });
  let gbBody = el('p', { class: 'muted', text: 'Pick a column to see its top 50 values under the current filters.' });
  if (gbr) {
    gbBody = el('table', { class: 'gb-table' }, el('tr', {}, ...['#', gbr.column, 'Rows', 'Net', '% net', '% rows'].map((h) => el('th', { text: h }))),
      ...gbr.values.map((v) => el('tr', { class: 'click', onclick: () => setRows({ f: [...st.f, v.blank ? [gbr.column, 'blank'] : [gbr.column, 'is', String(v.value)]] }) },
        el('td', { class: 'num', text: v.rank }), el('td', { class: 'value', text: v.blank ? '(blank)' : String(v.value) }),
        el('td', { class: 'num', text: fmtInt(v.rows) }), el('td', { class: 'num' + (isNeg(v.net) ? ' neg' : ''), text: fmtMoney(v.net) }),
        el('td', { class: 'num', text: v.pct_net ? v.pct_net + '%' : '' }), el('td', { class: 'num', text: v.pct_rows ? v.pct_rows + '%' : '' }))),
      gbr.other ? el('tr', { class: 'other' }, el('td'), el('td', { text: `all other ${fmtInt(gbr.other.distinct_values)} values` }),
        el('td', { class: 'num', text: fmtInt(gbr.other.rows) }), el('td', { class: 'num', text: fmtMoney(gbr.other.net) }), el('td'), el('td')) : null);
  }
  const dl = el('datalist', { id: 'col-list' }, ...S.rmeta.columns.map((c) => el('option', { value: c.name })));
  return el('div', {}, dl,
    el('section', { class: 'panel' }, el('div', { class: 'panel-head' }, el('h2', { text: 'Rows' }),
      el('span', { class: 'stat' }, el('span', { class: 'label', text: 'Matching rows' }), el('span', { class: 'value', text: fmtInt(t.rows) })),
      el('span', { class: 'stat' }, el('span', { class: 'label', text: 'Net obligations' }), el('span', { class: 'value', text: fmtMoney(t.net) }))),
      recon, chips, form),
    el('section', { class: 'toolbar' }, pager, el('span', { class: 'hint', text: `sorted by ${st.sort} ${st.dir}, then transaction key · page ${r.ms} ms · totals ${t.ms} ms` })),
    el('div', { class: 'table-wrap' }, el('table', { id: 'grid' }, el('thead', {}, head), body)),
    el('div', { class: 'two' },
      el('section', { class: 'panel' }, el('div', { class: 'panel-head' }, el('h2', { text: 'Group-by' }), gbIn,
        st.gb ? el('button', { class: 'quiet', text: 'remove', onclick: () => setRows({ gb: '' }, false) }) : null), gbBody),
      el('section', { class: 'panel' }, el('h2', { text: 'Columns shown' }), pick,
        el('button', { class: 'quiet', text: 'defaults', onclick: () => setRows({ cols: [...S.rmeta.default_cols] }, false) }))),
    el('details', { class: 'panel' }, el('summary', { text: 'Show the SQL' }),
      el('h3', { text: 'Views' }), el('pre', { text: Object.values(S.rmeta.view_sql).join('\n') }),
      el('h3', { text: 'Page' }), el('pre', { text: r.sql }), el('h3', { text: 'Totals' }), el('pre', { text: t.sql }),
      gbr ? el('h3', { text: 'Group-by' }) : null, gbr ? el('pre', { text: gbr.sql }) : null));
}

async function openRow(y, m, n) {
  const d = await api('/api/row', new URLSearchParams({ y: String(y), m: String(m), r: String(n) }));
  const tbl = el('table', { id: 'detail-table' }, ...d.fields.map(([k, v]) => el('tr', { class: k.startsWith('_source') ? 'lineage' : '' },
    el('td', { class: 'k', text: k }), el('td', { class: 'v' }, v === '' || v === null ? el('span', { class: 'null-mark', text: '(empty)' }) : String(v)))));
  $('detail-h').textContent = `Transaction, FY${y}`;
  $('detail-body').replaceChildren(el('p', { class: 'mono', text: d.key }),
    el('p', {}, 'Flags on this row: ', d.flags.length ? d.flags.join(', ') : 'none'),
    el('div', { class: 'detail-actions' }, el('button', { class: 'primary', text: 'All transactions of this award (all years)', onclick: () => {
      $('detail').close(); go('rows', { g: { ...S.g, fy: [S.hmeta.first_fy, S.hmeta.last_fy] }, rows: { ...defaultRows(), f: [['contract_award_unique_key', 'is', d.award_key]] } }); } })),
    el('div', { class: 'detail-scroll' }, tbl));
  if (!$('detail').open) $('detail').showModal();
}

// ------------------------------------------------------------------ decisions
async function viewDecisions() {
  const d = await api('/api/h/decisions');
  const m = S.hmeta;
  const tt = el('select', { name: 'target_type' }, ...m.target_types.map((x) => el('option', { value: x, text: x })));
  const target = el('input', { name: 'target', list: 'dec-targets', placeholder: 'flag id, column, or pattern', size: '28' });
  const status = el('select', { name: 'status' }, ...m.statuses.map((x) => el('option', { value: x, text: x })));
  const scope = el('input', { name: 'scope', placeholder: 'e.g. FY2008-FY2025, all agencies', size: '28' });
  const by = el('input', { name: 'decided_by', placeholder: 'your name', size: '20' });
  const dt = el('input', { name: 'decided_date', placeholder: 'YYYY-MM-DD (default today)', size: '16' });
  const why = el('textarea', { name: 'rationale', placeholder: 'Rationale: why this decision, what rule, what ledger reason code…' });
  const idIn = el('input', { type: 'hidden', name: 'decision_id' });
  const msg = el('p', { class: 'hint' });
  if (S.decTarget) { tt.value = S.decTarget.type; target.value = S.decTarget.target; }
  const dl = el('datalist', { id: 'dec-targets' }, ...m.catalog.map((f) => el('option', { value: f.flag_id, label: f.name })),
    ...m.columns.map((c) => el('option', { value: c.name })));
  const form = el('form', { class: 'decision', onsubmit: async (e) => {
    e.preventDefault();
    try {
      const saved = await post('/api/h/decisions', { decision_id: idIn.value, target_type: tt.value, target: target.value.trim(), scope: scope.value,
        status: status.value, rationale: why.value, decided_by: by.value, decided_date: dt.value });
      msg.textContent = `Saved ${saved.decision_id} to config/decisions.csv. Commit it so the team sees it.`;
      S.decTarget = null;
      render();
    } catch (err) { msg.textContent = 'Not saved: ' + err.message; }
  } }, dl, idIn,
    el('label', { class: 'field' }, el('span', { text: 'About a' }), tt), el('label', { class: 'field' }, el('span', { text: 'Target' }), target),
    el('label', { class: 'field' }, el('span', { text: 'Status' }), status), el('label', { class: 'field' }, el('span', { text: 'Scope' }), scope),
    el('label', { class: 'field' }, el('span', { text: 'Decided by' }), by), el('label', { class: 'field' }, el('span', { text: 'Date' }), dt),
    why, el('button', { type: 'submit', class: 'primary', text: 'Save decision' }));
  const t = el('table', { class: 'plain' }, el('tr', {}, ...['ID', 'About', 'Target', 'Status', 'Scope', 'Rationale', 'Decided by', 'Date', ''].map((h) => el('th', { text: h }))),
    ...d.decisions.map((r) => el('tr', {}, el('td', { text: r.decision_id }), el('td', { text: r.target_type }), el('td', { text: r.target }),
      el('td', {}, el('span', { class: 'badge ' + (r.status === 'proposed' ? 'review' : r.status === 'investigate' ? 'WARN' : 'ok'), text: r.status })),
      el('td', { text: r.scope }), el('td', { text: r.rationale }), el('td', { text: r.decided_by }), el('td', { text: r.decided_date }),
      el('td', {}, el('button', { class: 'quiet', text: 'edit', onclick: () => {
        idIn.value = r.decision_id; tt.value = r.target_type; target.value = r.target; status.value = r.status; scope.value = r.scope;
        why.value = r.rationale; by.value = r.decided_by === '(not yet decided)' ? '' : r.decided_by; dt.value = r.decided_date;
        msg.textContent = `Editing ${r.decision_id}`; form.scrollIntoView(); } })))));
  return el('div', {},
    el('section', { class: 'panel' }, el('h2', { text: 'Record a decision' }),
      el('p', { class: 'hint', text: 'Decisions are saved to config/decisions.csv (committed with git so the whole team sees them). Saving never changes any data: cleaning and exclusions happen later, as documented rules, with every excluded row in a ledger.' }),
      form, msg),
    el('section', { class: 'panel' }, el('h2', { text: `Decision log (${d.decisions.length})` }), el('div', { class: 'scroll' }, t)));
}

// ------------------------------------------------------------------ glossary
// Reads config/glossary.csv through /api/h/glossary. Typing filters the list without rebuilding the search box.
function glossaryEntry(t) {
  const kids = [el('h3', { text: t.term }),
    el('p', { class: 'gl-meta' }, el('span', { class: 'badge', text: t.category }),
      t.also_called ? el('span', { class: 'muted', text: ' Also called: ' + t.also_called }) : null),
    el('p', { text: t.plain_summary })];
  if (t.why_it_matters_here) kids.push(el('p', {}, el('strong', { text: 'Why it matters here. ' }), t.why_it_matters_here));
  if (t.where_it_shows_up) kids.push(el('p', {}, el('strong', { text: 'Shows up in. ' }), el('code', { text: t.where_it_shows_up })));
  if (t.official_definition) kids.push(el('blockquote', { text: t.official_definition }));
  const src = [];
  if (t.source_url) src.push(el('a', { href: t.source_url, target: '_blank', rel: 'noopener noreferrer', text: t.source_title || t.source_id }));
  else if (t.source_id) src.push(document.createTextNode(t.source_id));
  if (t.pinpoint) src.push(document.createTextNode(' · ' + t.pinpoint));
  if (t.learn_more_url && t.learn_more_url !== t.source_url) {
    src.push(document.createTextNode(' · '), el('a', { href: t.learn_more_url, target: '_blank', rel: 'noopener noreferrer', text: 'Read more' }));
  }
  if (src.length) kids.push(el('p', { class: 'hint' }, el('strong', { text: 'Source. ' }), ...src));
  if (t.related_terms) kids.push(el('p', { class: 'hint' }, el('strong', { text: 'Related. ' }), t.related_terms));
  return el('article', { class: 'gl-entry', id: 'gl-' + t.term.toLowerCase().replace(/[^a-z0-9]+/g, '-') }, ...kids);
}
async function viewGlossary() {
  const first = await api('/api/h/glossary');
  const q = el('input', { type: 'search', id: 'gl-q', placeholder: 'Search terms, other names and summaries', size: '40', 'aria-label': 'Search the glossary' });
  const cat = el('select', { id: 'gl-cat', 'aria-label': 'Category' }, el('option', { value: '', text: `All categories (${first.total})` }),
    ...first.categories.map((c) => el('option', { value: c, text: `${c} (${first.counts[c] || 0})` })));
  const count = el('p', { class: 'hint', id: 'gl-count' });
  const list = el('div', { class: 'gl-list', id: 'gl-list' });
  const show = (d) => {
    count.textContent = `${d.terms.length} of ${d.total} terms`;
    list.replaceChildren(...(d.terms.length ? d.terms.map(glossaryEntry) : [el('p', { class: 'muted', text: 'No term matches.' })]));
  };
  let timer = null; let seq = 0;
  const refresh = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const mine = ++seq;
      try {
        const d = await api('/api/h/glossary', new URLSearchParams({ q: q.value, category: cat.value }));
        if (mine === seq) { showError(''); show(d); }
      } catch (e) { showError(e.message); }
    }, 150);
  };
  q.addEventListener('input', refresh);
  cat.addEventListener('change', refresh);
  show(first);
  return el('section', { class: 'panel' }, el('h2', { text: 'Glossary' }),
    el('p', { class: 'hint', text: 'Plain definitions of the terms this project uses, why each matters to the concentration measure, and a source to read more. Edit config/glossary.csv to change an entry.' }),
    el('div', { class: 'gl-controls' }, el('label', { class: 'field grow' }, el('span', { text: 'Search' }), q),
      el('label', { class: 'field' }, el('span', { text: 'Category' }), cat)), count, list);
}

// ------------------------------------------------------------------ start
async function init() {
  try {
    [S.hmeta, S.rmeta] = await Promise.all([api('/api/h/meta'), api('/api/meta')]);
  } catch (e) { showError('could not start: ' + e.message); return; }
  for (const c of S.rmeta.columns) S.colIndex[c.name] = c;
  $('sub').textContent = `Release ${S.hmeta.release} · ${S.hmeta.years_present.length} of ${S.hmeta.years_in_scope.length} fiscal years present`
    + (S.hmeta.years_pending.length ? ` · pending: ${S.hmeta.years_pending.map((y) => 'FY' + y).join(', ')}` : '') + ' · local, read-only';
  fillGlobal();
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => go(b.dataset.view)));
  $('g-apply').addEventListener('click', () => { S.g = readGlobal(); if (S.view === 'rows') S.rows.page = 1; writeURL(); render(); });
  $('g-reset').addEventListener('click', () => { S.g = { fy: [S.hmeta.first_fy, S.hmeta.last_fy], agency: [], subagency: [], award_type: [], psc_cat: [] }; writeURL(); render(); });
  $('detail-close').addEventListener('click', () => $('detail').close());
  window.addEventListener('popstate', () => { readURL(); render(); });
  readURL();
  render();
}
document.addEventListener('DOMContentLoaded', init);
