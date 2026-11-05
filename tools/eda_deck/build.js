// Builds the EDA deck for the team and the class (docs/eda/eda_plan.md, "The presentation").
//
//   cd tools/eda_deck && npm install && node build.js
//
// The story: why concentration matters, the question, the data and how it was processed, how concentration is
// measured (with a worked HHI), the findings, why the markets concentrated, and what comes next. Every number comes
// from a committed table (reports/eda/, reports/integrity/, config/), so a rerun of src/eda updates the deck. Slide
// titles, plain-language text, captions and speaker notes live in messages.json and are written only after the results
// have been read. The build stops while any message says TBD and on any number it cannot find.

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const REPO = path.resolve(__dirname, "..", "..");
const EDA = process.env.EDA_DIR || path.join(REPO, "reports", "eda");
const OUT = process.env.DECK_OUT || path.join(REPO, "reports", "eda", "eda_presentation.pptx");
const MSG = JSON.parse(fs.readFileSync(process.env.DECK_MESSAGES || path.join(__dirname, "messages.json"), "utf8"));

// ------------------------------------------------------------------ data

function parseCsv(text) {
  text = text.replace(/^﻿/, "");
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') q = false;
      else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some((c) => c !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, k) => [h, r[k]])));
}
const readCsv = (name) => parseCsv(fs.readFileSync(path.join(EDA, `${name}.csv`), "utf8"));
const readRepoCsv = (rel) => parseCsv(fs.readFileSync(path.join(REPO, rel), "utf8"));

const num = (x) => (x === undefined || x === "" ? null : Number(x));
const need = (x, what) => {
  const v = num(x);
  if (v === null || Number.isNaN(v)) throw new Error(`a number the deck needs is missing: ${what}`);
  return v;
};
const pct = (x, d = 0, what = "a percentage") => `${need(x, what).toFixed(d)}%`;
const big = (x, what = "a dollar amount") => {
  const v = need(x, what), a = Math.abs(v);
  const s = a >= 1e12 ? `$${(a / 1e12).toFixed(1)} trillion` : a >= 1e11 ? `$${(a / 1e9).toFixed(0)} billion`
    : a >= 1e9 ? `$${(a / 1e9).toFixed(1)} billion` : `$${(a / 1e6).toFixed(0)} million`;
  return v < 0 ? `-${s}` : s;
};
const bigShort = (x, what) => big(x, what).replace(" trillion", "T").replace(" billion", "B").replace(" million", "M");
const count = (x) => Math.round(num(x)).toLocaleString("en-US");
const sentence = (t) => t.toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
// A display name from messages.json, used only when its first word appears in the vendor's name in the data.
const checkedName = (display, inData) => {
  const key = display.replace(/[^A-Za-z ]/g, " ").trim().split(/\s+/)[0].toLowerCase();
  if (!String(inData).toLowerCase().includes(key)) throw new Error(`display name "${display}" does not match "${inData}" in the data`);
  return display;
};

for (const [k, v] of Object.entries(MSG)) {
  if (JSON.stringify(v).includes("TBD")) throw new Error(`messages.json: "${k}" still says TBD. Write it after reading the results.`);
}

const byYear = readCsv("concentration_by_year");
const v0 = byYear.filter((r) => r.variant === "V0");
const civ = readCsv("civilian_by_year");
const years = civ.map((r) => r.fiscal_year);
const FIRST = years[0], LAST = years[years.length - 1], PREV = String(Number(LAST) - 1);
const civFirst = civ[0], civLast = civ[civ.length - 1];
const series = readCsv("trend_civilian_series");
const tests = readCsv("trend_yearly_tests");
const decompAgency = readCsv("trend_decomposition_by_agency");
const decompSummary = readCsv("trend_decomposition_summary");
const decompBreadth = readCsv("trend_decomposition_breadth")[0];
const civTop = readCsv("civilian_top_segments");
const civComp = readCsv("civilian_competition_by_year");
const civCompAgency = readCsv("civilian_competition_by_agency");
const exSeg = readCsv("example_segment");
const worked = readCsv("hhi_worked_example");
const linesChance = readCsv("trend_lines_chance");
const linesTested = readCsv("trend_lines_tested")[0];
const civKind = readCsv("civilian_by_kind");
const dodCiv = readCsv("concentration_dod_civilian");
const eras = readCsv("psc_era_patterns");
const bands = readCsv("band_changes");
const cover = readCsv("feature_coverage");
const spend = readCsv("spending_by_year");
const example = readCsv("example_row")[0];
const checks = readCsv("base_checks");
const inventory = readRepoCsv("reports/integrity/stage0_inventory.csv").filter((r) => r.status === "stage 0");
const flagCatalog = readRepoCsv("config/flag_catalog.csv");
const pairCells = readRepoCsv("reports/integrity/v2/reversal_pair_cells.csv");
const gao = readRepoCsv("reports/integrity/completeness_check.csv").filter((r) => /GAO/.test(r.publisher || "") && num(r.fiscal_year) >= 2022);
if (!gao.length) throw new Error("no GAO rows for FY2022 to FY2025 in completeness_check.csv");

const rowsAll = spend.reduce((a, r) => a + need(r.rows, "rows"), 0);
const netAll = spend.reduce((a, r) => a + need(r.net, "net"), 0);
const lastSpend = spend[spend.length - 1];
const zipGB = inventory.reduce((a, r) => a + need(r.size_bytes, "zip size"), 0) / 1e9;
const textGB = inventory.reduce((a, r) => a + need(r.uncompressed_bytes, "unzipped size"), 0) / 1e9;
const segments = v0.reduce((a, r) => a + need(r.cells, "segments"), 0);
const vendorSegments = checks.filter((r) => r.check === "vendor-cells equal integrity report").reduce((a, r) => a + need(r.ours, "vendor-cells"), 0);
const checksPassed = checks.filter((r) => r.status === "PASS").length;
const gaoGap = Math.max(...gao.map((r) => Math.abs(need(r.gap_pct, "GAO gap"))));
const emerson = pairCells.find((r) => /Emerson/.test(r.pair) && r.fiscal_year === "2008");
if (!emerson) throw new Error("reversal_pair_cells.csv has no FY2008 Emerson row");
const exFirst = exSeg.find((r) => r.fiscal_year === "2019"), exLast = exSeg[exSeg.length - 1];
if (!exFirst) throw new Error("example_segment.csv has no FY2019 row");
const test = (s) => tests.find((r) => r.series.startsWith(s)) || {};
const tAll = test("civilian, share of dollars"), tNoVA = test("civilian without Veterans Affairs");
const chance500 = linesChance.find((r) => r.cutoff === "500") || {};
const shortYear = (y) => `'${y.slice(2)}`;

// ------------------------------------------------------------------ theme and layouts

const THEME = {
  name: "Concentration", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2430", lt1: "FFFFFF", dk2: "4A5568", lt2: "EEF0F3",
    accent1: "C2410C",   // burnt orange: highly concentrated
    accent2: "2E3A4D",   // slate: the rest of the market
    accent3: "8A94A6",   // grey: comparison
    accent4: "D9911F",   // amber: moderately concentrated, and cautions
    accent5: "4D7C6F",   // green: competitive, and checks that pass
    accent6: "C9CED8",
  },
};
const H = THEME.colors;
const C = { text1: H.dk1, text2: H.dk2, bg1: H.lt1, bg2: H.lt2, a1: H.accent1, a2: H.accent2, a3: H.accent3, a4: H.accent4,
            a5: H.accent5, a6: H.accent6 };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";   // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Is federal contract money going to fewer companies?";
pres.author = "Suchitra Hole, Shivram Nekkanti, Andy Hannah";

const footer = { text: { text: "Vendor concentration in federal contracting, FY2008 to FY2025  |  Source: USAspending.gov Award Data Archive",
  options: { x: 0.5, y: 5.3, w: 7.5, h: 0.2, fontSize: 8, color: C.text2 } } };
const slideNo = { x: 9.0, y: 5.3, w: 0.5, h: 0.2, fontSize: 8, color: C.text2, align: "right" };
const titlePh = (size) => ({ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.25, w: 9.0, h: 0.7,
  fontSize: size, bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle", align: "left" }, text: "" } });

pres.defineSlideMaster({
  title: "TITLE", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.1, w: 8.8, h: 1.9, fontSize: 38, bold: true,
      color: C.bg1, fontFace: THEME.headFontFace, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "sub", type: "body", x: 0.6, y: 3.25, w: 8.8, h: 1.2, fontSize: 16, color: "D5DAE1",
      valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.bg1 }, objects: [titlePh(24), footer], slideNumber: slideNo });
pres.defineSlideMaster({ title: "BACKUP", background: { color: C.bg2 }, objects: [titlePh(22), footer], slideNumber: slideNo });

const axis = {
  catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", valGridLine: { color: "E2E5EA", size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false, legendFontSize: 10, legendColor: H.dk2, titleFontSize: 11, titleColor: H.dk1,
  valAxisTitleFontSize: 10, valAxisTitleColor: H.dk2, catAxisTitleFontSize: 10, catAxisTitleColor: H.dk2,
  valAxisTitleFontFace: "+mn-lt", catAxisTitleFontFace: "+mn-lt",
};

const text = (s, t, o) => s.addText(t, { margin: 0, isTextBox: true, color: C.text1, fontSize: 14, valign: "top", ...o });
const card = (s, x, y, w, h, name, color = C.bg2) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color }, line: { type: "none" }, objectName: name });
const dot = (s, x, y, d, color, glyph, name) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { type: "none" }, objectName: `${name} dot` });
  if (glyph) text(s, glyph, { x, y, w: d, h: d, fontSize: Math.round(d * 30), bold: true, color: C.bg1, align: "center", valign: "middle",
    objectName: `${name} glyph` });
};
let FIG = 0;
// A numbered caption under a figure, as the rubric asks: "Figure N. What it shows."
function caption(s, t, x, y, w) {
  FIG += 1;
  text(s, [{ text: `Figure ${FIG}. `, options: { bold: true } }, { text: t }], { x, y, w, h: 0.26, fontSize: 10, color: C.text2,
    objectName: `figure ${FIG} caption` });
}
function stat(s, x, y, w, value, label, color, name, size = 30) {
  text(s, value, { x, y, w, h: 0.58, fontSize: size, bold: true, color, fontFace: THEME.headFontFace, valign: "bottom", objectName: `${name} value` });
  text(s, label, { x, y: y + 0.62, w, h: 0.5, fontSize: 12, color: C.text2, objectName: `${name} label` });
}
function takeaway(s, msg, y = 4.62, h = 0.58) {
  card(s, 0.5, y, 9.0, h, "takeaway box");
  text(s, [{ text: "What this means   ", options: { bold: true, color: C.a1 } }, { text: msg, options: { color: C.text1 } }],
    { x: 0.7, y, w: 8.6, h, fontSize: 13, valign: "middle", objectName: "takeaway" });
}
function content(section, msg) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(msg.title, { placeholder: "title" });
  s.addNotes(msg.notes);
  return s;
}
function hhiBar(s, x, y, w, shares, color, name) {   // one segment as a bar split by company share
  let cx = x;
  shares.forEach((sh, k) => {
    const bw = (w * sh) / 100;
    s.addShape(pres.shapes.RECTANGLE, { x: cx + 0.01, y, w: Math.max(bw - 0.02, 0.01), h: 0.3, line: { type: "none" },
      fill: { color: k === 0 ? color : [C.a3, C.a6][k % 2] }, objectName: `${name} company ${k + 1}` });
    if (bw >= 0.45) text(s, `${sh}%`, { x: cx, y, w: bw, h: 0.3, fontSize: 10, bold: true, color: C.bg1, align: "center", valign: "middle",
      objectName: `${name} share ${k + 1}` });
    cx += bw;
  });
}

// ================================================================== the talk

pres.addSection({ title: "Talk" });

// 1. title
{
  const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Talk" });
  s.addText(MSG.title.title, { placeholder: "title" });
  s.addText(MSG.title.subtitle, { placeholder: "sub" });
  s.addNotes(MSG.title.notes);
}

// 2. what concentration is, and why it matters
{
  const s = content("Talk", MSG.why);
  const markets = [["Competitive", "The money is shared", C.a2,
                    [[0.6, 0.4, 0.55], [0.6, 1.3, 0.55], [0.6, 0.4, 1.2], [0.6, 1.3, 1.2], [0.6, 0.85, 1.85]], "20% each"],
                   ["Concentrated", "One company wins most", C.a1,
                    [[1.35, 0.2, 0.7], [0.3, 1.75, 0.65], [0.3, 1.75, 1.08], [0.3, 1.75, 1.51], [0.3, 1.75, 1.94]], "80% to one"]];
  markets.forEach(([head, sub, color, circles, note], m) => {
    const x0 = 0.5 + m * 2.3, y0 = 1.05;
    card(s, x0, y0, 2.15, 2.95, `market ${m + 1}`);
    text(s, [{ text: head, options: { bold: true, color, breakLine: true } }, { text: sub, options: { fontSize: 11, color: C.text2 } }],
      { x: x0 + 0.1, y: y0 + 0.1, w: 1.95, h: 0.55, fontSize: 14, align: "center", objectName: `market ${m + 1} head` });
    circles.forEach(([d, cx, cy], k) => s.addShape(pres.shapes.OVAL, { x: x0 + cx, y: y0 + cy, w: d, h: d,
      fill: { color: k === 0 || m === 0 ? color : C.a3 }, line: { color: C.bg2, width: 1 }, objectName: `market ${m + 1} company ${k + 1}` }));
    text(s, note, { x: x0, y: y0 + 2.55, w: 2.15, h: 0.3, fontSize: 12, bold: true, color, align: "center", objectName: `market ${m + 1} note` });
  });
  caption(s, "Two markets with the same budget and five companies each.", 0.5, 4.05, 4.45);
  text(s, "Why it matters when a few companies win", { x: 5.25, y: 1.05, w: 4.25, h: 0.3, fontSize: 14, bold: true, objectName: "why head" });
  MSG.why.risks.forEach(([glyph, head, body], i) => {
    const y = 1.45 + i * 0.75;
    dot(s, 5.25, y, 0.48, [C.a1, C.a4, C.a2, C.a3][i], glyph, `risk ${i + 1}`);
    text(s, [{ text: head, options: { bold: true, breakLine: true } }, { text: body, options: { fontSize: 11, color: C.text2 } }],
      { x: 5.88, y: y - 0.04, w: 3.62, h: 0.66, fontSize: 13, objectName: `risk ${i + 1} text` });
  });
  takeaway(s, MSG.why.takeaway);
}

// 3. the question and scope
{
  const s = content("Talk", MSG.question);
  s.addChart(pres.charts.BAR, [{ name: `Contract dollars, FY${LAST}`, labels: ["Defense", "Civilian agencies"],
      values: [need(lastSpend.net_v1_dod, "dod") / 1e9, need(civLast.net, "civ") / 1e9] }],
    { ...axis, x: 0.4, y: 1.0, w: 4.4, h: 3.0, barDir: "bar", chartColors: [H.accent3, H.accent1], invertedColors: [H.accent3, H.accent1],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '"$"0"B"', dataLabelFontSize: 12, dataLabelColor: H.dk1,
      valAxisHidden: true, valGridLine: { style: "none" }, showLegend: false, showTitle: true, catAxisLabelFontSize: 12, barGapWidthPct: 45,
      title: `Federal contract dollars, FY${LAST} ($ billion)`, objectName: "scope chart" });
  caption(s, "Civilian agencies are everything except the Department of Defense.", 0.5, 4.05, 4.4);
  const items = MSG.question.points;
  items.forEach(([head, body], i) => {
    const y = 1.1 + i * 0.85;
    dot(s, 5.2, y + 0.02, 0.42, [C.a1, C.a2, C.a5][i], String(i + 1), `point ${i + 1}`);
    text(s, [{ text: head, options: { bold: true, breakLine: true } }, { text: body, options: { fontSize: 12, color: C.text2 } }],
      { x: 5.75, y, w: 3.75, h: 0.78, fontSize: 14, objectName: `point ${i + 1} text` });
  });
  takeaway(s, MSG.question.takeaway);
}

// 3b. key terms, before the data
{
  const s = content("Talk", MSG.terms);
  MSG.terms.cards.forEach(([term, full, body], i) => {
    const col = i % 4, row = Math.floor(i / 4), x = 0.5 + col * 2.28, y = 1.0 + row * 1.78, w = 2.13;
    card(s, x, y, w, 1.63, `term ${i + 1}`);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: 0.06, fill: { color: [C.a1, C.a2, C.a5, C.a4][col] }, line: { type: "none" }, objectName: `term ${i + 1} band` });
    text(s, [{ text: term, options: { bold: true, fontSize: 15, breakLine: true } }, { text: full, options: { fontSize: 10, italic: true, color: C.text2, breakLine: true } },
             { text: body, options: { fontSize: 11, color: C.text1 } }],
      { x: x + 0.14, y: y + 0.16, w: w - 0.28, h: 1.4, paraSpaceAfter: 3, objectName: `term ${i + 1} text` });
  });
  takeaway(s, MSG.terms.takeaway);
}

// 4. the data
{
  const s = content("Talk", MSG.data);
  const stats = [[`${inventory.length}`, `yearly files, FY${FIRST} to FY${LAST}`, C.a2], [`${(rowsAll / 1e6).toFixed(1)}M`, "contract actions (rows)", C.a1],
                 [`${zipGB.toFixed(0)} GB`, `zipped, ${textGB.toFixed(0)} GB unzipped`, C.a2], [bigShort(netAll, "18-year net"), "obligated in 18 years", C.a2]];
  stats.forEach(([v, l, c], k) => stat(s, 0.5 + (k % 2) * 2.1, 1.0 + Math.floor(k / 2) * 1.35, 1.95, v, l, c, `data stat ${k + 1}`, 28));
  text(s, MSG.data.source, { x: 0.5, y: 3.8, w: 4.1, h: 0.5, fontSize: 10, italic: true, color: C.text2, objectName: "source" });
  const x0 = 4.85, y0 = 1.0, w = 4.65;
  card(s, x0, y0, w, 3.25, "row card");
  text(s, "One row = one contract action. A real one:", { x: x0 + 0.2, y: y0 + 0.12, w: w - 0.4, h: 0.3, fontSize: 13, bold: true, objectName: "row heading" });
  [["When", example.action_date], ["Who bought", example.awarding_agency_name],
   ["What", `${example.product_or_service_code}  ${sentence(example.product_or_service_code_description.replace("MEDICAL- ", ""))}`],
   ["From whom", checkedName(MSG.data.vendorDisplay, example.recipient_parent_name)], ["How much", big(example.federal_action_obligation, "example amount")],
   ["Competed?", sentence(example.extent_competed)]].forEach(([k, v], i) => {
    const y = y0 + 0.52 + i * 0.44;
    text(s, k, { x: x0 + 0.2, y, w: 1.2, h: 0.38, fontSize: 12, color: C.text2, valign: "middle", objectName: `field ${i + 1} name` });
    text(s, v, { x: x0 + 1.4, y, w: w - 1.6, h: 0.38, fontSize: 13, bold: k === "How much", color: k === "How much" ? C.a1 : C.text1,
      valign: "middle", objectName: `field ${i + 1} value` });
  });
  caption(s, "The fields in every row that the measure uses: buyer, product, company, dollars.", 4.85, 4.3, 4.65);
  takeaway(s, MSG.data.takeaway);
}

// 5. how we processed it
{
  const s = content("Talk", MSG.process);
  const steps = [["1", "Download and lock", `${inventory.length} zips checked against their digital fingerprints, then made read-only`],
                 ["2", "Convert and prove", `${(rowsAll / 1e6).toFixed(1)}M rows copied to a fast format. Two programs agree on rows, dollars to the cent, every field`],
                 ["3", "Check quality", `${flagCatalog.length} rules run on every row: duplicates, bad dates, placeholder names, outliers`],
                 ["4", "Build tables", `${(vendorSegments / 1e6).toFixed(2)}M company-by-segment totals. ${checksPassed} checks confirm they add up`]];
  const w = 2.04, gap = 0.28;
  steps.forEach(([n, headline, body], k) => {
    const x = 0.5 + k * (w + gap), dark = k === 3;
    card(s, x, 1.05, w, 2.55, `step ${n}`, dark ? C.a2 : C.bg2);
    dot(s, x + 0.18, 1.22, 0.46, C.a1, n, `step ${n}`);
    text(s, headline, { x: x + 0.18, y: 1.8, w: w - 0.36, h: 0.36, fontSize: 15, bold: true, color: dark ? C.bg1 : C.text1, objectName: `step ${n} head` });
    text(s, body, { x: x + 0.18, y: 2.22, w: w - 0.36, h: 1.3, fontSize: 12, color: dark ? "E2E5EA" : C.text2, objectName: `step ${n} body` });
    if (k < 3) s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: x + w + 0.06, y: 2.2, w: 0.16, h: 0.24, rotate: 90, fill: { color: C.a3 },
      line: { type: "none" }, objectName: `arrow ${n}` });
  });
  caption(s, "The pipeline. Nothing is deleted: problems are flagged beside the data.", 0.5, 3.65, 9.0);
  dot(s, 0.5, 4.0, 0.42, C.a5, "✓", "gao");
  text(s, [{ text: `Our yearly totals match GAO's official figures within ${gaoGap.toFixed(1)}%`, options: { bold: true } },
           { text: "  (FY2022 to FY2025)", options: { color: C.text2 } }],
    { x: 1.05, y: 4.0, w: 8.45, h: 0.42, fontSize: 13, valign: "middle", objectName: "gao check" });
  takeaway(s, MSG.process.takeaway, 4.62, 0.58);
}

// 6. before and after: one cleaning step
{
  const s = content("Talk", MSG.cleaning);
  const before = [100 * need(emerson.vendor_net, "emerson net") / need(emerson.cell_net, "cell net"), need(emerson.cell_hhi, "hhi before")];
  const after = [100 * need(emerson.vendor_net_without_pair, "emerson net after") / need(emerson.cell_net_without_pair, "cell net after"),
                 need(emerson.cell_hhi_without_pair, "hhi after")];
  [["Before cleaning", before, C.a1, `A $${(need(emerson.amount, "entry") / 1e9).toFixed(1)}B entry, reversed the next year`],
   ["After cleaning", after, C.a5, "The entry and its reversal netted to their real sum"]].forEach(([head, [share, hhi], color, sub], k) => {
    const x0 = 0.5 + k * 3.0;
    card(s, x0, 1.0, 2.8, 2.95, `cleaning ${k + 1}`);
    text(s, [{ text: head, options: { bold: true, color, breakLine: true } }, { text: sub, options: { fontSize: 11, color: C.text2 } }],
      { x: x0 + 0.2, y: 1.1, w: 2.4, h: 0.62, fontSize: 15, objectName: `cleaning ${k + 1} head` });
    text(s, [{ text: `${share < 1 ? share.toFixed(1) : share.toFixed(0)}%`, options: { bold: true, fontSize: 30, color, breakLine: true, fontFace: THEME.headFontFace } },
             { text: "one company's share of the market", options: { fontSize: 11, color: C.text2 } }],
      { x: x0 + 0.2, y: 1.85, w: 2.4, h: 0.85, objectName: `cleaning ${k + 1} share` });
    text(s, [{ text: count(hhi), options: { bold: true, fontSize: 30, color, breakLine: true, fontFace: THEME.headFontFace } },
             { text: "HHI of the market", options: { fontSize: 11, color: C.text2 } }],
      { x: x0 + 0.2, y: 2.85, w: 2.4, h: 0.85, objectName: `cleaning ${k + 1} hhi` });
  });
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 3.36, y: 2.35, w: 0.2, h: 0.28, rotate: 90, fill: { color: C.a3 }, line: { type: "none" }, objectName: "cleaning arrow" });
  caption(s, `Army construction, FY2008 (${count(emerson.vendors_in_cell)} companies): Emerson's share, and the HHI.`, 0.5, 4.0, 5.8);
  text(s, "Five issues like this were found", { x: 6.55, y: 1.0, w: 2.95, h: 0.3, fontSize: 13, bold: true, objectName: "issues head" });
  MSG.cleaning.issues.forEach((t, i) => {
    dot(s, 6.55, 1.42 + i * 0.52, 0.3, C.a4, String(i + 1), `issue ${i + 1}`);
    text(s, t, { x: 6.95, y: 1.38 + i * 0.52, w: 2.55, h: 0.45, fontSize: 11, valign: "middle", objectName: `issue ${i + 1}` });
  });
  takeaway(s, MSG.cleaning.takeaway);
}

// 7. what a segment is, and the scale
{
  const s = content("Talk", MSG.segment);
  [["Agency", "Veterans Affairs"], ["Product", "Managed healthcare"], ["Year", `FY${LAST}`]].forEach(([k, v], i) => {
    const x = 0.5 + i * 1.55;
    card(s, x, 1.05, 1.4, 0.95, `segment part ${i + 1}`);
    text(s, [{ text: k, options: { fontSize: 11, color: C.text2, breakLine: true } }, { text: v, options: { fontSize: 13, bold: true } }],
      { x: x + 0.08, y: 1.1, w: 1.24, h: 0.85, align: "center", valign: "middle", objectName: `segment part ${i + 1} text` });
    if (i < 2) text(s, "+", { x: x + 1.4, y: 1.05, w: 0.15, h: 0.95, fontSize: 18, bold: true, color: C.a3, align: "center", valign: "middle", objectName: `plus ${i + 1}` });
  });
  text(s, "=", { x: 5.15, y: 1.05, w: 0.3, h: 0.95, fontSize: 22, bold: true, color: C.a3, align: "center", valign: "middle", objectName: "equals" });
  card(s, 5.5, 1.05, 4.0, 0.95, "segment result", C.a2);
  text(s, [{ text: "One segment: one market", options: { bold: true, color: C.bg1, breakLine: true } },
           { text: `${count(exLast.positive_vendors)} companies shared ${bigShort(exLast.net, "ex net")}`, options: { fontSize: 12, color: "E2E5EA" } }],
    { x: 5.7, y: 1.1, w: 3.7, h: 0.85, fontSize: 14, valign: "middle", objectName: "segment result text" });
  text(s, `${Math.round(segments / 1000)}K segments in 18 years. Every segment gets a concentration score, the HHI (Herfindahl–Hirschman Index), from 0 to 10,000.`,
    { x: 0.5, y: 2.2, w: 9.0, h: 0.32, fontSize: 13, color: C.text2, objectName: "segment count" });
  const sx = 0.5, sw = 9.0, sy = 3.05, toX = (v) => sx + (sw * v) / 10000;
  [[0, 1500, C.a5, "Competitive"], [1500, 2500, C.a4, "Moderate"], [2500, 10000, C.a1, "Highly concentrated: above 2,500"]].forEach(([a, b, color, label], k) => {
    s.addShape(pres.shapes.RECTANGLE, { x: toX(a), y: sy, w: toX(b) - toX(a), h: 0.4, fill: { color }, line: { type: "none" }, objectName: `band ${k + 1}` });
    text(s, label, { x: toX(a) + 0.08, y: sy, w: toX(b) - toX(a) - 0.12, h: 0.4, fontSize: 11, bold: true, color: C.bg1, valign: "middle",
      align: k === 2 ? "left" : "center", objectName: `band ${k + 1} label` });
  });
  const exX = toX(need(exLast.hhi, "example hhi"));
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: exX - 0.09, y: sy - 0.2, w: 0.18, h: 0.16, rotate: 180, fill: { color: C.text1 }, line: { type: "none" }, objectName: "marker" });
  text(s, `This segment: ${count(exLast.hhi)}`, { x: exX - 2.6, y: sy - 0.44, w: 2.5, h: 0.24, fontSize: 11, bold: true, align: "right", objectName: "marker label" });
  [[0, "0"], [1500, "1,500"], [2500, "2,500"], [10000, "10,000 = one company has all"]].forEach(([v, l], k) => {
    text(s, l, { x: k === 3 ? toX(v) - 2.2 : toX(v) - (k ? 0.2 : 0), y: sy + 0.44, w: 2.2, h: 0.22, fontSize: 10, color: C.text2,
      align: k === 3 ? "right" : "left", objectName: `tick ${k + 1}` });
  });
  caption(s, "The HHI scale. Bands from the 2010 U.S. Department of Justice and Federal Trade Commission merger guidelines.", 0.5, 3.85, 9.0);
  takeaway(s, MSG.segment.takeaway);
}

// 8. the HHI, worked through
{
  const s = content("Talk", MSG.hhi);
  text(s, "1. Take each company's share of the money   2. Square it   3. Add them up", { x: 0.5, y: 0.95, w: 9.0, h: 0.32, fontSize: 14,
    bold: true, color: C.a2, objectName: "hhi steps" });
  // the textbook examples
  card(s, 0.5, 1.4, 3.9, 2.55, "simple examples");
  text(s, "Two simple markets", { x: 0.7, y: 1.5, w: 3.5, h: 0.28, fontSize: 13, bold: true, objectName: "simple head" });
  [["Five equal companies", [20, 20, 20, 20, 20], "20² + 20² + 20² + 20² + 20²", "2,000", C.a2],
   ["One company with 80%", [80, 5, 5, 5, 5], "80² + 5² + 5² + 5² + 5²", "6,500", C.a1]].forEach(([label, shares, sum, score, color], r) => {
    const y = 1.95 + r * 0.95;
    text(s, label, { x: 0.7, y, w: 3.5, h: 0.24, fontSize: 11, color: C.text2, objectName: `simple ${r + 1} label` });
    hhiBar(s, 0.7, y + 0.26, 3.5, shares, color, `simple ${r + 1}`);
    text(s, [{ text: `${sum} = `, options: { color: C.text2 } }, { text: score, options: { bold: true, color } }],
      { x: 0.7, y: y + 0.6, w: 3.5, h: 0.26, fontSize: 12, objectName: `simple ${r + 1} sum` });
  });
  // the real segment
  const rows = worked.filter((r) => r.rank !== "total"), tot = worked.find((r) => r.rank === "total");
  const tbl = [[{ text: "VA managed healthcare, FY" + LAST, options: { bold: true, color: H.lt1, fill: { color: H.accent2 } } },
                { text: "Share", options: { bold: true, color: H.lt1, fill: { color: H.accent2 }, align: "right" } },
                { text: "Share²", options: { bold: true, color: H.lt1, fill: { color: H.accent2 }, align: "right" } }]];
  rows.forEach((r, i) => tbl.push([r.rank === "rest" ? r.company.replace("all other", "All other") : (MSG.hhi.companies[i] ? checkedName(MSG.hhi.companies[i], r.company) : r.company),
    { text: `${need(r.share_pct, "share").toFixed(2)}%`, options: { align: "right" } },
    { text: need(r.share_squared, "sq").toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), options: { align: "right" } }]));
  tbl.push([{ text: "HHI (the sum)", options: { bold: true } }, { text: "100%", options: { align: "right", bold: true } },
            { text: count(tot.share_squared), options: { align: "right", bold: true, color: H.accent1 } }]);
  s.addTable(tbl, { x: 4.65, y: 1.4, w: 4.85, colW: [2.75, 1.0, 1.1], fontSize: 12, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DAE1" },
    fill: { color: H.lt1 }, margin: 0.06, rowH: 0.4, autoPage: false });
  caption(s, "HHI worked through: two simple markets, and a real one from the data.", 0.5, 4.05, 9.0);
  takeaway(s, MSG.hhi.takeaway);
}

// 9. from segments to one number per year
{
  const s = content("Talk", MSG.measure);
  const conc = need(civLast.net_above_2500, "civ conc"), all = need(civLast.net, "civ all");
  s.addChart(pres.charts.BAR, [{ name: "In highly concentrated segments", labels: [`FY${LAST}`], values: [conc / 1e9] },
                               { name: "In all other segments", labels: [`FY${LAST}`], values: [(all - conc) / 1e9] }],
    { ...axis, x: 0.4, y: 1.05, w: 9.2, h: 1.6, barDir: "bar", barGrouping: "percentStacked", chartColors: [H.accent1, H.accent6],
      showValue: true, dataLabelPosition: "ctr", dataLabelFormatCode: '"$"0"B"', dataLabelFontSize: 13, dataLabelColor: H.dk1,
      valAxisHidden: true, catAxisHidden: true, valGridLine: { style: "none" }, showLegend: true, legendPos: "b", barGapWidthPct: 20,
      showTitle: true, title: `All civilian contract dollars, FY${LAST} (${bigShort(all, "all")})`, objectName: "measure chart" });
  caption(s, `FY${LAST} civilian dollars, split by whether their segment scores above 2,500.`, 0.5, 2.7, 9.0);
  const eq = [[bigShort(conc, "conc"), "in segments above 2,500", C.a1], ["÷", "", C.a3], [bigShort(all, "all"), "all civilian contract dollars", C.a2],
              ["=", "", C.a3], [pct(civLast.above_2500_pct_of_net, 0, "share"), `of FY${LAST} money is highly concentrated`, C.a1]];
  let x = 0.8;
  eq.forEach(([v, l, c], k) => {
    const w = l ? 2.2 : 0.4;
    text(s, v, { x, y: 3.15, w, h: 0.55, fontSize: l ? 28 : 24, bold: true, color: c, fontFace: THEME.headFontFace, align: "center", valign: "bottom", objectName: `eq ${k + 1}` });
    if (l) text(s, l, { x, y: 3.72, w, h: 0.45, fontSize: 11, color: C.text2, align: "center", objectName: `eq ${k + 1} label` });
    x += w + 0.1;
  });
  takeaway(s, MSG.measure.takeaway);
}

// "How we found it": three numbered steps in one strip under the title, the same on every finding slide.
function methodStrip(s, steps, y = 0.98) {
  text(s, "How we found it", { x: 0.5, y, w: 1.3, h: 0.44, fontSize: 11, bold: true, color: C.a1, valign: "middle", objectName: "method label" });
  steps.forEach((t, i) => {
    const x = 1.8 + i * 2.58;
    card(s, x, y, 2.48, 0.44, `method ${i + 1}`);
    dot(s, x + 0.07, y + 0.08, 0.28, C.a2, String(i + 1), `method ${i + 1}`);
    text(s, t, { x: x + 0.42, y, w: 2.0, h: 0.44, fontSize: 10, valign: "middle", objectName: `method ${i + 1} text` });
  });
}

// 10a. how each finding was tested
{
  const s = content("Talk", MSG.methods);
  [["The question", 1.05], ["The method", 3.55], ["In plain words", 5.9]].forEach(([h, x]) =>
    text(s, h, { x, y: 0.98, w: 2.4, h: 0.3, fontSize: 11, bold: true, color: C.text2, objectName: `method head ${h}` }));
  MSG.methods.rows.forEach(([q, method, plain], i) => {
    const y = 1.32 + i * 0.52;
    card(s, 0.5, y, 9.0, 0.47, `method row ${i + 1}`, i % 2 ? C.bg1 : C.bg2);
    dot(s, 0.6, y + 0.07, 0.33, [C.a1, C.a1, C.a2, C.a2, C.a5, C.a4][i], String(i + 1), `method row ${i + 1}`);
    text(s, q, { x: 1.05, y, w: 2.45, h: 0.47, fontSize: 12, bold: true, valign: "middle", objectName: `method row ${i + 1} question` });
    text(s, method, { x: 3.55, y, w: 2.3, h: 0.47, fontSize: 12, bold: true, color: C.a1, valign: "middle", objectName: `method row ${i + 1} method` });
    text(s, plain, { x: 5.9, y, w: 3.5, h: 0.47, fontSize: 11, color: C.text2, valign: "middle", objectName: `method row ${i + 1} plain` });
  });
  takeaway(s, MSG.methods.takeaway);
}

// 11. finding 1: the rise is real, and it is Veterans Affairs
{
  const s = content("Talk", MSG.finding1);
  methodStrip(s, MSG.finding1.method);
  const keyAll = "civilian_share_of_dollars", keyNoVA = "civilian_without_Veterans_Affairs_share_of_dollars";
  s.addChart(pres.charts.LINE, [
    { name: "All civilian agencies", labels: years.map(shortYear), values: series.map((r) => need(r[keyAll], "series")) },
    { name: "Civilian agencies without Veterans Affairs", labels: years.map(shortYear), values: series.map((r) => need(r[keyNoVA], "series no va")) },
  ], { ...axis, x: 0.4, y: 1.5, w: 6.1, h: 2.85, chartColors: [H.accent1, H.accent3], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 5,
    valAxisMinVal: 20, valAxisMaxVal: 60, valAxisMajorUnit: 10, valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b",
    showValAxisTitle: true, valAxisTitle: "% of dollars, HHI above 2,500", showCatAxisTitle: true, catAxisTitle: "Fiscal year", objectName: "finding1 chart" });
  caption(s, "Share of civilian contract dollars in highly concentrated segments, each year.", 0.5, 4.33, 6.0);
  [[tAll, "All civilian agencies", "FBEDE7", C.a1, "A real rise", `Only ${(100 * need(tAll.slope_p_one_sided, "p")).toFixed(1)}% of shuffled orders give a trend this steep`],
   [tNoVA, "Without Veterans Affairs", C.bg2, C.text2, "No real trend", `${(100 * need(tNoVA.slope_p_one_sided, "p")).toFixed(0)}% of shuffled orders give a trend this steep`]].forEach(([t, head, fill, color, verdict, body], k) => {
    const y = 1.55 + k * 1.42;
    card(s, 6.75, y, 2.75, 1.3, `test ${k + 1}`, fill);
    text(s, [{ text: head, options: { bold: true, color, breakLine: true } },
             { text: `${pct(t.first_value_pct, 0)} → ${pct(t.last_value_pct, 0)}  ${verdict}`, options: { bold: true, fontSize: 14, breakLine: true } },
             { text: body, options: { fontSize: 10, color: C.text2 } }], { x: 6.88, y: y + 0.06, w: 2.5, h: 1.2, fontSize: 12, objectName: `test ${k + 1} text` });
  });
  takeaway(s, MSG.finding1.takeaway);
}

// 12. finding 2: a few markets, not a broad shift
{
  const s = content("Talk", MSG.finding2);
  methodStrip(s, MSG.finding2.method);
  const sum = decompSummary[0];
  const show = decompAgency.slice(0, 7);
  const vals = show.map((r) => need(r.contribution_points, "contrib"));
  s.addChart(pres.charts.BAR, [{ name: "Points", labels: show.map((r) => MSG.finding2.agencyLabels[r.agency] || r.agency), values: vals }],
    { ...axis, x: 0.4, y: 1.5, w: 5.9, h: 2.85, barDir: "bar", catAxisOrientation: "maxMin", chartColors: vals.map((v) => (v >= 0 ? H.accent1 : H.accent3)),
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.0;-0.0", dataLabelFontSize: 11, dataLabelColor: H.dk1, showLegend: false,
      showValAxisTitle: true, valAxisTitle: "Percentage points added to (or taken from) the civilian share", valAxisMinVal: -4, valAxisMaxVal: 14, catAxisLabelPos: "low",
      objectName: "finding2 chart" });
  caption(s, "Each agency's part of the change in the civilian share. Orange adds to it, grey takes away.", 0.5, 4.33, 6.0);
  card(s, 6.55, 1.55, 2.95, 1.25, "points card", "FBEDE7");
  text(s, [{ text: "What a point is", options: { bold: true, color: C.a1, breakLine: true } },
           { text: `${pct(sum.share_early_pct, 1)} → ${pct(sum.share_late_pct, 1)} = +${need(sum.change_points, "chg").toFixed(1)} points`, options: { bold: true, fontSize: 14, breakLine: true } },
           { text: "One point = one percentage point of the civilian share", options: { fontSize: 10, color: C.text2 } }],
    { x: 6.68, y: 1.6, w: 2.75, h: 1.15, fontSize: 12, objectName: "points text" });
  stat(s, 6.55, 2.9, 1.45, `+${need(decompAgency[0].contribution_points, "va").toFixed(1)}`, "points from VA alone", C.a1, "va", 26);
  stat(s, 8.05, 2.9, 1.45, `${decompBreadth.segments_for_half_of_positive_contribution}`, "markets make half of all the rise", C.a1, "breadth", 26);
  takeaway(s, MSG.finding2.takeaway);
}

// 13. finding 3: who holds the concentrated markets
{
  const s = content("Talk", MSG.finding3);
  methodStrip(s, MSG.finding3.method);
  const top = civTop.slice(0, 6);
  s.addChart(pres.charts.BAR, [{ name: "Largest company's share", labels: top.map((r, i) => `${MSG.finding3.segments[i]}  (${bigShort(r.net, "seg net")})`),
      values: top.map((r) => need(r.largest_share_pct, "share")) }],
    { ...axis, x: 0.4, y: 1.5, w: 5.6, h: 2.85, barDir: "bar", catAxisOrientation: "maxMin", chartColors: [H.accent1], valAxisMinVal: 0, valAxisMaxVal: 100,
      showValue: true, dataLabelPosition: "inEnd", dataLabelFormatCode: '0"%"', dataLabelFontSize: 11, dataLabelColor: H.lt1, showLegend: false,
      showValAxisTitle: true, valAxisTitle: "Largest company's share of the market (%)", catAxisLabelFontSize: 10, objectName: "finding3 chart" });
  caption(s, `The six largest highly concentrated civilian markets in FY${LAST}, with their size.`, 0.5, 4.33, 5.6);
  card(s, 6.25, 1.5, 3.25, 3.0, "companies card");
  top.forEach((r, i) => {
    const y = 1.6 + i * 0.48;
    dot(s, 6.4, y + 0.04, 0.28, i < 3 ? C.a1 : C.a3, String(i + 1), `company ${i + 1}`);
    text(s, [{ text: checkedName(MSG.finding3.companies[i], r.largest_vendor_name), options: { bold: true, breakLine: true } },
             { text: MSG.finding3.roles[i], options: { fontSize: 10, color: C.text2 } }], { x: 6.78, y, w: 2.67, h: 0.46, fontSize: 11, objectName: `company ${i + 1} text` });
  });
  takeaway(s, MSG.finding3.takeaway);
}

// 14. finding 4: why VA managed healthcare concentrated
{
  const s = content("Talk", MSG.finding4);
  methodStrip(s, MSG.finding4.method);
  const yrs = exSeg.filter((r) => num(r.fiscal_year) >= 2016);
  s.addChart([
    { type: pres.charts.BAR, data: [{ name: "Money spent ($ billion)", labels: yrs.map((r) => r.fiscal_year), values: yrs.map((r) => need(r.net, "ex net") / 1e9) }],
      options: { chartColors: [H.accent6], barGapWidthPct: 40 } },
    { type: pres.charts.LINE, data: [{ name: "Largest company's share (%)", labels: yrs.map((r) => r.fiscal_year), values: yrs.map((r) => need(r.largest_share_pct, "ex share")) }],
      options: { chartColors: [H.accent1], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 6, secondaryValAxis: true, secondaryCatAxis: true } },
  ], { ...axis, x: 0.4, y: 1.5, w: 5.7, h: 2.8, showLegend: true, legendPos: "b",
    valAxes: [{ showValAxisTitle: true, valAxisTitle: "$ billion", valAxisMinVal: 0 },
              { showValAxisTitle: true, valAxisTitle: "largest share %", valAxisMinVal: 0, valAxisMaxVal: 100, valGridLine: { style: "none" } }],
    catAxes: [{ catAxisTitle: "" }, { catAxisHidden: true }], objectName: "finding4 chart" });
  caption(s, "VA managed healthcare: money spent (bars) and the largest company's share (line).", 0.5, 4.33, 5.7);
  card(s, 6.35, 1.5, 3.15, 3.0, "why card");
  MSG.finding4.facts.forEach(([glyph, t], i) => {
    const y = 1.62 + i * 0.72;
    dot(s, 6.5, y + 0.02, 0.34, [C.a2, C.a5, C.a1, C.a4][i], glyph, `fact ${i + 1}`);
    text(s, t, { x: 6.95, y, w: 2.45, h: 0.66, fontSize: 11, objectName: `fact ${i + 1} text` });
  });
  takeaway(s, MSG.finding4.takeaway);
}

// 15. finding 5: concentrated, but competed
{
  const s = content("Talk", MSG.finding5);
  methodStrip(s, MSG.finding5.method);
  const rowOf = (g) => civComp.find((r) => r.fiscal_year === LAST && r.segments === g) || {};
  const groups = [["Highly concentrated markets", rowOf("concentrated")], ["All other markets", rowOf("rest")]];
  s.addChart(pres.charts.BAR, [{ name: "Competed", labels: groups.map((g) => g[0]), values: groups.map(([, r]) => need(r.competed_pct, "competed")) },
                               { name: "Sole source", labels: groups.map((g) => g[0]), values: groups.map(([, r]) => need(r.sole_source_pct, "sole")) }],
    { ...axis, x: 0.4, y: 1.5, w: 5.8, h: 2.85, barDir: "bar", barGrouping: "percentStacked", chartColors: [H.accent5, H.accent4], catAxisOrientation: "maxMin",
      showValue: true, dataLabelPosition: "ctr", dataLabelFormatCode: '0"%"', dataLabelFontSize: 13, dataLabelColor: H.lt1, showLegend: true, legendPos: "b",
      showValAxisTitle: true, valAxisTitle: "% of the dollars", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFormatCode: "0%", barGapWidthPct: 50,
      catAxisLabelFontSize: 12, objectName: "finding5 chart" });
  caption(s, `How civilian contract dollars were awarded, FY${LAST}.`, 0.5, 4.33, 5.8);
  const nasa = civCompAgency.find((r) => /Aeronautics/.test(r.agency)) || {};
  card(s, 6.45, 1.55, 3.05, 1.35, "same card");
  text(s, [{ text: "The same rate", options: { bold: true, color: C.a5, breakLine: true } }, { text: MSG.finding5.same, options: { fontSize: 11, color: C.text2 } }],
    { x: 6.6, y: 1.62, w: 2.8, h: 1.22, fontSize: 14, objectName: "same text" });
  card(s, 6.45, 3.0, 3.05, 1.35, "exception card");
  text(s, [{ text: `Exception: NASA, ${pct(nasa.sole_source_pct, 0, "nasa")} sole source`, options: { bold: true, color: C.a4, breakLine: true } },
           { text: MSG.finding5.exception, options: { fontSize: 11, color: C.text2 } }], { x: 6.6, y: 3.07, w: 2.8, h: 1.22, fontSize: 13, objectName: "exception text" });
  takeaway(s, MSG.finding5.takeaway);
}

// 16. what "rising" means, on a real market
{
  const s = content("Talk", MSG.rising);
  const rows = exSeg.filter((r) => r.hhi !== "");
  const f3 = rows.slice(0, 3), l3 = rows.slice(-3);
  const mean = (rs) => rs.reduce((a, r) => a + need(r.hhi, "hhi"), 0) / rs.length;
  const m1 = mean(f3), m2 = mean(l3);
  s.addChart(pres.charts.LINE, [
    { name: "HHI each year", labels: rows.map((r) => shortYear(r.fiscal_year)), values: rows.map((r) => need(r.hhi, "hhi")) },
    { name: "Average of the first 3 years", labels: rows.map((r) => shortYear(r.fiscal_year)), values: rows.map((r, i) => (i < 3 ? m1 : null)) },
    { name: "Average of the last 3 years", labels: rows.map((r) => shortYear(r.fiscal_year)), values: rows.map((r, i) => (i >= rows.length - 3 ? m2 : null)) },
  ], { ...axis, x: 0.4, y: 1.0, w: 6.0, h: 3.35, chartColors: [H.accent6, H.accent2, H.accent1], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 5,
    valAxisMinVal: 0, valAxisMaxVal: 10000, valAxisMajorUnit: 2500, showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "HHI",
    showCatAxisTitle: true, catAxisTitle: "Fiscal year", objectName: "rising chart" });
  caption(s, "One trend line: VA managed healthcare, FY2008 to FY2025.", 0.5, 4.33, 6.0);
  card(s, 6.65, 1.0, 2.85, 3.35, "rule card");
  text(s, [{ text: "The rule", options: { bold: true, color: C.a1, breakLine: true } }, { text: MSG.rising.rule, options: { fontSize: 12, breakLine: true } }],
    { x: 6.8, y: 1.08, w: 2.6, h: 1.2, fontSize: 14, paraSpaceAfter: 4, objectName: "rule text" });
  text(s, [{ text: `${count(m1)} → ${count(m2)}`, options: { bold: true, fontSize: 20, color: C.a1, breakLine: true, fontFace: THEME.headFontFace } },
           { text: `A gain of ${count(m2 - m1)} points: this market is rising`, options: { fontSize: 11, color: C.text2 } }],
    { x: 6.8, y: 2.35, w: 2.6, h: 0.85, objectName: "rule example" });
  text(s, MSG.rising.why, { x: 6.8, y: 3.25, w: 2.6, h: 1.0, fontSize: 11, color: C.text2, objectName: "rule why" });
  takeaway(s, MSG.rising.takeaway);
}

// 17. the shuffle test: is a market's rise real?
{
  const s = content("Talk", MSG.lines);
  const n = need(linesTested.lines, "lines");
  const vals = [need(chance500.rising_pct, "rising"), need(chance500.rising_pct_shuffled, "shuffled"), need(linesTested.tested_risers_pct_of_lines, "tested")];
  s.addChart(pres.charts.BAR, [{ name: "% of markets", labels: ["A. Pass the 500-point rule", "B. Would pass by luck (shuffled)", "C. Pass the shuffle test"], values: vals }],
    { ...axis, x: 0.4, y: 1.0, w: 5.4, h: 3.35, barDir: "col", chartColors: [H.accent3, H.accent6, H.accent1], valAxisMinVal: 0, valAxisMaxVal: 60,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"', dataLabelFontSize: 12, dataLabelColor: H.dk1, showLegend: false,
      showValAxisTitle: true, valAxisTitle: `% of ${count(n)} civilian trend lines`, barGapWidthPct: 45, catAxisLabelFontSize: 10, objectName: "lines chart" });
  caption(s, "Civilian trend lines (one agency, one product) with 6+ years and $10M+.", 0.5, 4.33, 5.4);
  MSG.lines.steps.forEach(([glyph, head, body], i) => {
    const y = 1.0 + i * 1.12;
    dot(s, 6.05, y, 0.42, [C.a3, C.a6, C.a1][i], glyph, `lines step ${i + 1}`);
    text(s, [{ text: head, options: { bold: true, breakLine: true } }, { text: body, options: { fontSize: 11, color: C.text2 } }],
      { x: 6.6, y: y - 0.04, w: 2.9, h: 1.08, fontSize: 13, objectName: `lines step ${i + 1} text` });
  });
  takeaway(s, MSG.lines.takeaway);
}

// 16. what it means, and what is next
{
  const s = content("Talk", MSG.next);
  [["What we found", C.a1, MSG.next.found], ["Keep in mind", C.a4, MSG.next.careful], ["What we do next", C.a5, MSG.next.steps]].forEach(([headline, color, items], k) => {
    const x = 0.5 + k * 3.08, w = 2.86;
    card(s, x, 1.05, w, 3.35, `column ${k + 1}`);
    dot(s, x + 0.22, 1.25, 0.32, color, "", `column ${k + 1}`);
    text(s, headline, { x: x + 0.65, y: 1.21, w: w - 0.8, h: 0.4, fontSize: 17, bold: true, valign: "middle", objectName: `column ${k + 1} head` });
    text(s, items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
      { x: x + 0.22, y: 1.8, w: w - 0.44, h: 2.5, fontSize: 13, paraSpaceAfter: 8, objectName: `column ${k + 1} items` });
  });
  takeaway(s, MSG.next.takeaway);
}

// ================================================================== backup

pres.addSection({ title: "Backup" });
const backup = (msg) => {
  const s = pres.addSlide({ masterName: "BACKUP", sectionTitle: "Backup" });
  s.addText(msg.title, { placeholder: "title" });
  s.addNotes(msg.notes);
  return s;
};
const head = (t) => ({ text: t, options: { bold: true, color: H.lt1, fill: { color: H.accent2 } } });
const tableOpts = (x, y, w, colW) => ({ x, y, w, colW, fontSize: 11, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DAE1" },
  fill: { color: H.lt1 }, margin: 0.06, autoPage: false });

{   // B1. the data decisions, in plain words
  const s = backup(MSG.backup_decisions);
  const rows = [[head("The issue"), head("What we do (as proposed)"), head("Why")]];
  MSG.backup_decisions.rows.forEach((r) => rows.push(r));
  s.addTable(rows, { ...tableOpts(0.5, 1.0, 9.0, [2.6, 3.4, 3.0]), fontSize: 10, rowH: 0.42 });
  const b = bands.filter((r) => r.variant === "V1");
  const changed = b.reduce((a, r) => a + need(r.cells_changing_band, "chg"), 0), all = b.reduce((a, r) => a + need(r.cells_in_both, "all"), 0);
  text(s, `With these rules, ${count(changed)} of ${count(all)} segments (${(100 * changed / all).toFixed(1)}%) change concentration band. Every rule is still to be confirmed by the team.`,
    { x: 0.5, y: 4.6, w: 9.0, h: 0.5, fontSize: 12, color: C.text2, objectName: "decisions note" });
}
{   // B2. Defense and civilian
  const s = backup(MSG.backup_defense);
  const ser = (g) => years.map((y) => need((dodCiv.find((r) => r.group === g && r.fiscal_year === y) || {}).above_2500_pct_of_net, `${g} ${y}`));
  s.addChart(pres.charts.LINE, [{ name: "Civilian agencies", labels: years.map(shortYear), values: ser("civilian") }, { name: "Defense", labels: years.map(shortYear), values: ser("DoD") }],
    { ...axis, x: 0.4, y: 1.0, w: 9.2, h: 3.3, chartColors: [H.accent1, H.accent3], lineSize: 2.5, lineDataSymbol: "none", valAxisMinVal: 0, valAxisMaxVal: 60,
      valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "% of dollars above HHI 2,500",
      showCatAxisTitle: true, catAxisTitle: "Fiscal year", objectName: "defense chart" });
  caption(s, "Share of dollars in highly concentrated segments, Defense and civilian.", 0.5, 4.35, 9.0);
}
{   // B3. civilian products, services and research
  const s = backup(MSG.backup_kind);
  const pick = (k, fy) => civKind.find((r) => r.kind === k && r.fiscal_year === fy) || {};
  const groups = [["Services", "service"], ["Products", "product"], ["Research", "research"]];
  s.addChart(pres.charts.BAR, [
    { name: `FY${FIRST}`, labels: groups.map((g) => g[0]), values: groups.map((g) => need(pick(g[1], FIRST).above_2500_pct_of_net, "kind first")) },
    { name: `FY${LAST}`, labels: groups.map((g) => g[0]), values: groups.map((g) => need(pick(g[1], LAST).above_2500_pct_of_net, "kind last")) },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.4, h: 3.3, barDir: "col", chartColors: [H.accent3, H.accent1], valAxisMinVal: 0, valAxisMaxVal: 100,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"', dataLabelFontSize: 10, dataLabelColor: H.dk1, showLegend: true, legendPos: "b",
    showValAxisTitle: true, valAxisTitle: "% of dollars above HHI 2,500", objectName: "kind chart" });
  caption(s, "Civilian dollars in highly concentrated segments, by kind of purchase.", 0.5, 4.35, 5.4);
  const rows = [[head("Civilian dollars"), head(`FY${FIRST}`), head(`FY${LAST}`)]];
  groups.forEach(([label, k]) => rows.push([label, bigShort(pick(k, FIRST).net, "kn"), bigShort(pick(k, LAST).net, "kn")]));
  s.addTable(rows, tableOpts(6.0, 1.2, 3.5, [1.4, 1.05, 1.05]));
}
{   // B4. product codes
  const s = backup(MSG.backup_codes);
  const all3 = eras.find((r) => r.eras_present.split(" + ").length === 3) || {};
  const inAll = need(all3.pct_of_net, "all eras");
  s.addChart(pres.charts.BAR, [{ name: "Codes used in all three periods", labels: ["All 18 years"], values: [inAll] }, { name: "Codes used in one or two periods", labels: ["All 18 years"], values: [100 - inAll] }],
    { ...axis, x: 0.4, y: 1.0, w: 9.2, h: 1.5, barDir: "bar", barGrouping: "percentStacked", chartColors: [H.accent3, H.accent6], showValue: true, dataLabelPosition: "ctr",
      dataLabelFormatCode: '0.0"%"', dataLabelFontSize: 13, dataLabelColor: H.dk1, valAxisHidden: true, catAxisHidden: true, valGridLine: { style: "none" }, showLegend: true, legendPos: "b",
      barGapWidthPct: 20, showTitle: true, title: "Share of all contract dollars, FY2008 to FY2025, by product code", objectName: "codes chart" });
  caption(s, "Product codes and the two code changes, FY2012 and FY2021.", 0.5, 2.55, 9.0);
  text(s, MSG.backup_codes.note, { x: 0.5, y: 3.0, w: 9.0, h: 1.2, fontSize: 13, color: C.text2, objectName: "codes note" });
}
{   // B5. feature coverage
  const s = backup(MSG.backup_features);
  const pickYears = ["2008", "2012", "2018", "2025"];
  const cols = [["Sole source", "umbrella competition: sole_source pct"], ["Order competition field blank", "order competition: order_blank pct"],
                ["Set-aside field blank", "set-aside: set_aside_blank pct"], ["Offers reported (of competed)", "offers reported, pct of competed"]];
  const rows = [[head("Share of dollars, all agencies"), ...pickYears.map((y) => head(`FY${y}`))]];
  cols.forEach(([label, k]) => rows.push([label, ...pickYears.map((y) => pct((cover.find((r) => r.fiscal_year === y) || {})[k], 1, k))]));
  s.addTable(rows, tableOpts(0.5, 1.1, 9.0, [3.4, 1.4, 1.4, 1.4, 1.4]));
  text(s, MSG.backup_features.note, { x: 0.5, y: 3.4, w: 9.0, h: 0.9, fontSize: 12, color: C.text2, objectName: "features note" });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log(`deck -> ${OUT} (${FIG} figures)`);
})();
