// Builds the 5-minute EDA deck for the team and the class (docs/eda/eda_plan.md, "The presentation").
//
//   cd tools/eda_deck && npm install && node build.js
//
// The story: the question, the data we downloaded, how we processed it, how we measure concentration, the first
// findings, and what they mean. Every number comes from a committed table (reports/eda/, reports/integrity/,
// config/), so a rerun of src/eda updates the deck. Slide titles, plain-language text and speaker notes live in
// messages.json and are written only after the results have been read. The build stops while any message says TBD
// and on any number it cannot find.

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
const titleCase = (t) => t.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

for (const [k, v] of Object.entries(MSG)) {
  if (JSON.stringify(v).includes("TBD")) throw new Error(`messages.json: "${k}" still says TBD. Write it after reading the results.`);
}

const byYear = readCsv("concentration_by_year");
const v1 = byYear.filter((r) => r.variant === "V1");
const v0 = byYear.filter((r) => r.variant === "V0");
const years = v1.map((r) => r.fiscal_year);
const first = v1[0], last = v1[v1.length - 1];
const kind = readCsv("concentration_by_kind");
const eras = readCsv("psc_era_patterns");
const brk12 = readCsv("psc_break_fy2012");
const brk21 = readCsv("psc_break_fy2021");
const noise = readCsv("noise_by_size");
const rising = readCsv("rising_counts");
const bands = readCsv("band_changes");
const top = readCsv("top100_vendors");
const cover = readCsv("feature_coverage");
const spend = readCsv("spending_by_year");
const drivers = readCsv("drivers_above_2500");
const example = readCsv("example_row")[0];
const checks = readCsv("base_checks");
const inventory = readRepoCsv("reports/integrity/stage0_inventory.csv").filter((r) => r.status === "stage 0");
const flagCatalog = readRepoCsv("config/flag_catalog.csv");
const gao = readRepoCsv("reports/integrity/completeness_check.csv")
  .filter((r) => /GAO/.test(r.publisher || "") && num(r.fiscal_year) >= 2022);
if (!gao.length) throw new Error("no GAO rows for FY2022 to FY2025 in completeness_check.csv");

const rowsAll = spend.reduce((a, r) => a + need(r.rows, "rows"), 0);
const netAll = spend.reduce((a, r) => a + need(r.net, "net"), 0);
const netLast = spend[spend.length - 1].net;
const zipGB = inventory.reduce((a, r) => a + need(r.size_bytes, "zip size"), 0) / 1e9;
const textGB = inventory.reduce((a, r) => a + need(r.uncompressed_bytes, "unzipped size"), 0) / 1e9;
const segments = v0.reduce((a, r) => a + need(r.cells, "segments"), 0);
const vendorSegments = checks.filter((r) => r.check === "vendor-cells equal integrity report").reduce((a, r) => a + need(r.ours, "vendor-cells"), 0);
const checksPassed = checks.filter((r) => r.status === "PASS").length;
const gaoGap = Math.max(...gao.map((r) => Math.abs(need(r.gap_pct, "GAO gap"))));
const wing = drivers.find((r) => r.fiscal_year === last.fiscal_year && r.psc === "1510");
if (!wing) throw new Error("drivers_above_2500.csv has no FY2025 row for product code 1510");
const KEY = "above 2,500 pct of net";

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

const footer = { text: { text: "Vendor concentration in federal contracting, FY2008 to FY2025  |  First look, October 2026",
  options: { x: 0.5, y: 5.28, w: 7.5, h: 0.22, fontSize: 9, color: C.text2 } } };
const slideNo = { x: 9.0, y: 5.28, w: 0.5, h: 0.22, fontSize: 9, color: C.text2, align: "right" };
const titlePh = (size) => ({ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28, w: 9.0, h: 0.72,
  fontSize: size, bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle", align: "left" }, text: "" } });

pres.defineSlideMaster({
  title: "TITLE", background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 8.8, h: 1.9, fontSize: 38, bold: true,
      color: C.bg1, fontFace: THEME.headFontFace, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "sub", type: "body", x: 0.6, y: 3.35, w: 8.8, h: 1.1, fontSize: 16, color: "D5DAE1",
      valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.bg1 }, objects: [titlePh(26), footer], slideNumber: slideNo });
pres.defineSlideMaster({ title: "BACKUP", background: { color: C.bg2 }, objects: [titlePh(22), footer], slideNumber: slideNo });

const axis = {
  catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", valGridLine: { color: "E2E5EA", size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false, legendFontSize: 10, legendColor: H.dk2, titleFontSize: 11, titleColor: H.dk2,
};

const text = (s, t, o) => s.addText(t, { margin: 0, isTextBox: true, color: C.text1, fontSize: 14, valign: "top", ...o });
const card = (s, x, y, w, h, name, color = C.bg2) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color }, line: { type: "none" }, objectName: name });
function stat(s, x, y, w, value, label, color, name, size = 32) {
  text(s, value, { x, y, w, h: 0.62, fontSize: size, bold: true, color, fontFace: THEME.headFontFace, valign: "bottom",
    objectName: `${name} value` });
  text(s, label, { x, y: y + 0.66, w, h: 0.5, fontSize: 12, color: C.text2, objectName: `${name} label` });
}
function takeaway(s, msg, y = 4.55, h = 0.62) {   // the plain-language line, in the same place on every main slide
  card(s, 0.5, y, 9.0, h, "takeaway box");
  text(s, [{ text: "What this means   ", options: { bold: true, color: C.a1 } }, { text: msg, options: { color: C.text1 } }],
    { x: 0.7, y, w: 8.6, h, fontSize: 14, valign: "middle", objectName: "takeaway" });
}
function content(section, msg) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(msg.title, { placeholder: "title" });
  s.addNotes(msg.notes);
  return s;
}

// ------------------------------------------------------------------ 1. title

pres.addSection({ title: "Talk" });
{
  const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Talk" });
  s.addText(MSG.title.title, { placeholder: "title" });
  s.addText(MSG.title.subtitle, { placeholder: "sub" });
  s.addNotes(MSG.title.notes);
}

// ------------------------------------------------------------------ 2. the question

{
  const s = content("Talk", MSG.question);
  stat(s, 0.5, 1.1, 3.6, bigShort(netLast, "FY2025 net"), `spent through federal contracts in FY${last.fiscal_year}`, C.a1, "spend", 40);
  text(s, MSG.question.goal, { x: 0.5, y: 2.45, w: 3.7, h: 1.9, fontSize: 15, objectName: "goal" });
  // two small markets, with vendors drawn as circles sized by their share of the money
  const markets = [["Many share the money", "HHI 2,000", C.a2,
                    [[20, 0.6, 0.42, 0.6], [20, 0.6, 1.33, 0.6], [20, 0.6, 0.42, 1.27], [20, 0.6, 1.33, 1.27], [20, 0.6, 0.875, 1.94]]],
                   ["One wins most of it", "HHI 6,500", C.a1,
                    [[80, 1.45, 0.18, 0.75], [5, 0.32, 1.8, 0.72], [5, 0.32, 1.8, 1.17], [5, 0.32, 1.8, 1.62], [5, 0.32, 1.8, 2.07]]]];
  markets.forEach(([label, score, color, circles], m) => {
    const x0 = 4.55 + m * 2.5, y0 = 1.15;
    card(s, x0, y0, 2.35, 3.15, `market ${m + 1} card`);
    text(s, label, { x: x0 + 0.1, y: y0 + 0.15, w: 2.15, h: 0.3, fontSize: 13, bold: true, align: "center", objectName: `market ${m + 1} label` });
    circles.forEach(([sh, d, cx, cy], k) => {
      s.addShape(pres.shapes.OVAL, { x: x0 + cx, y: y0 + cy, w: d, h: d, fill: { color: k === 0 || m === 0 ? color : C.a3 },
        line: { color: C.bg2, width: 1 }, objectName: `market ${m + 1} vendor ${k + 1}` });
      if (d >= 0.6) text(s, `${sh}%`, { x: x0 + cx, y: y0 + cy, w: d, h: d, fontSize: 12, bold: true, color: C.bg1, align: "center",
        valign: "middle", objectName: `market ${m + 1} share ${k + 1}` });
    });
    text(s, score, { x: x0, y: y0 + 2.72, w: 2.35, h: 0.32, fontSize: 14, bold: true, color, align: "center", objectName: `market ${m + 1} score` });
  });
  takeaway(s, MSG.question.takeaway);
}

// ------------------------------------------------------------------ 3. the data

{
  const s = content("Talk", MSG.data);
  const stats = [[`${inventory.length}`, "yearly files, FY2008 to FY2025", C.a2],
                 [`${(rowsAll / 1e6).toFixed(1)}M`, "contract actions (rows)", C.a1],
                 [`${zipGB.toFixed(0)} GB`, `zipped, ${textGB.toFixed(0)} GB once unzipped`, C.a2],
                 [bigShort(netAll, "18-year net"), "obligated over the 18 years", C.a2]];
  stats.forEach(([v, l, c], k) => stat(s, 0.5 + (k % 2) * 2.15, 1.05 + Math.floor(k / 2) * 1.4, 2.0, v, l, c, `data stat ${k + 1}`, 30));
  text(s, MSG.data.source, { x: 0.5, y: 3.95, w: 4.1, h: 0.5, fontSize: 11, italic: true, color: C.text2, objectName: "source" });
  // one real row, as a record card
  const x0 = 4.85, y0 = 1.1, w = 4.65;
  card(s, x0, y0, w, 3.3, "row card");
  text(s, "One row = one contract action. A real one:", { x: x0 + 0.2, y: y0 + 0.13, w: w - 0.4, h: 0.32, fontSize: 13, bold: true,
    objectName: "row card heading" });
  const fields = [["When", example.action_date],
                  ["Who bought", `${example.awarding_agency_name} (${example.awarding_sub_agency_name.replace("Department of the ", "")})`],
                  ["What", `${example.product_or_service_code}  ${sentence(example.product_or_service_code_description)}`],
                  ["From whom", titleCase(example.recipient_parent_name)], ["How much", big(example.federal_action_obligation, "example amount")],
                  ["Competed?", sentence(example.extent_competed)]];
  fields.forEach(([k, v], i) => {
    const y = y0 + 0.55 + i * 0.44;
    text(s, k, { x: x0 + 0.2, y, w: 1.2, h: 0.38, fontSize: 12, color: C.text2, valign: "middle", objectName: `field ${i + 1} name` });
    text(s, v, { x: x0 + 1.4, y, w: w - 1.6, h: 0.38, fontSize: 13, bold: k === "How much", color: k === "How much" ? C.a1 : C.text1,
      valign: "middle", objectName: `field ${i + 1} value` });
  });
  takeaway(s, MSG.data.takeaway);
}

// ------------------------------------------------------------------ 4. how we processed it

{
  const s = content("Talk", MSG.process);
  const steps = [["1", "Download and lock", `${inventory.length} zip files checked against their checksums, then made read-only`],
                 ["2", "Convert and prove", `A fast copy of all ${(rowsAll / 1e6).toFixed(1)}M rows, proven exact: counts, dollars to the cent, every field`],
                 ["3", "Check quality", `${flagCatalog.length} rule checks on every row, which found the records that would distort the score`],
                 ["4", "Analysis tables", `${(vendorSegments / 1e6).toFixed(2)}M vendor-by-segment totals, all ${checksPassed} checks passed`]];
  const w = 2.04, gap = 0.28;
  steps.forEach(([n, headline, body], k) => {
    const x = 0.5 + k * (w + gap), dark = k === 3;
    card(s, x, 1.1, w, 2.55, `step ${n} card`, dark ? C.a2 : C.bg2);
    s.addShape(pres.shapes.OVAL, { x: x + 0.18, y: 1.27, w: 0.46, h: 0.46, fill: { color: C.a1 }, line: { type: "none" }, objectName: `step ${n} badge` });
    text(s, n, { x: x + 0.18, y: 1.27, w: 0.46, h: 0.46, fontSize: 16, bold: true, color: C.bg1, align: "center", valign: "middle", objectName: `step ${n} number` });
    text(s, headline, { x: x + 0.18, y: 1.85, w: w - 0.36, h: 0.4, fontSize: 15, bold: true, color: dark ? C.bg1 : C.text1, objectName: `step ${n} head` });
    text(s, body, { x: x + 0.18, y: 2.3, w: w - 0.36, h: 1.25, fontSize: 12, color: dark ? "E2E5EA" : C.text2, objectName: `step ${n} body` });
    if (k < 3) s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: x + w + 0.06, y: 2.25, w: 0.16, h: 0.24, rotate: 90,
      fill: { color: C.a3 }, line: { type: "none" }, objectName: `arrow ${n}` });
  });
  s.addShape(pres.shapes.OVAL, { x: 0.5, y: 3.88, w: 0.42, h: 0.42, fill: { color: C.a5 }, line: { type: "none" }, objectName: "gao badge" });
  text(s, "✓", { x: 0.5, y: 3.88, w: 0.42, h: 0.42, fontSize: 16, bold: true, color: C.bg1, align: "center", valign: "middle", objectName: "gao tick" });
  text(s, [{ text: `Our yearly totals match GAO's within ${gaoGap.toFixed(1)}%`, options: { bold: true } },
           { text: "  for FY2022 to FY2025, the years GAO publishes exact figures.", options: { color: C.text2 } }],
    { x: 1.05, y: 3.88, w: 8.45, h: 0.42, fontSize: 14, valign: "middle", objectName: "gao check" });
  takeaway(s, MSG.process.takeaway);
}

// ------------------------------------------------------------------ 5. how we measure concentration

{
  const s = content("Talk", MSG.method);
  card(s, 0.5, 1.1, 3.3, 1.55, "segment card");
  text(s, [{ text: "A segment", options: { bold: true, fontSize: 15, breakLine: true } },
           { text: "one agency, buying one product, in one year", options: { color: C.text2, breakLine: true } },
           { text: `e.g. Defense buying fixed-wing aircraft in FY${last.fiscal_year}`, options: { italic: true, color: C.a2, fontSize: 12 } }],
    { x: 0.7, y: 1.22, w: 2.95, h: 1.35, fontSize: 14, paraSpaceAfter: 4, objectName: "segment text" });
  text(s, `${Math.round(segments / 1000)}K segments over 18 years. A vendor is a parent company.`,
    { x: 0.5, y: 2.75, w: 3.3, h: 0.5, fontSize: 12, color: C.text2, objectName: "segment count" });
  text(s, "HHI: add up each vendor's % share, squared", { x: 4.15, y: 1.1, w: 5.35, h: 0.32, fontSize: 14, bold: true, objectName: "hhi heading" });
  const rowsHhi = [["Five equal vendors:  20² × 5", [20, 20, 20, 20, 20], "2,000", C.a2], ["One vendor with 80%:  80² + 5² × 4", [80, 5, 5, 5, 5], "6,500", C.a1]];
  const barX = 4.15, barW = 4.0;
  rowsHhi.forEach(([label, shares, score, color], r) => {
    const y = 1.85 + r * 0.75;
    text(s, label, { x: barX, y: y - 0.3, w: barW, h: 0.26, fontSize: 11, color: C.text2, objectName: `hhi row ${r + 1} label` });
    let x = barX;
    shares.forEach((sh, k) => {
      const w = (barW * sh) / 100;
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.01, y, w: w - 0.02, h: 0.36, line: { type: "none" },
        fill: { color: k === 0 ? color : [C.a3, C.a6][k % 2] }, objectName: `hhi row ${r + 1} vendor ${k + 1}` });
      if (w >= 0.5) text(s, `${sh}%`, { x, y, w, h: 0.36, fontSize: 11, bold: true, color: C.bg1, align: "center", valign: "middle",
        objectName: `hhi row ${r + 1} share ${k + 1}` });
      x += w;
    });
    text(s, score, { x: 8.3, y, w: 1.2, h: 0.36, fontSize: 18, bold: true, color, valign: "middle", objectName: `hhi row ${r + 1} score` });
  });
  // the scale, 0 to 10,000, with the bands of the 2010 merger guidelines
  const sx = 0.5, sw = 9.0, sy = 3.5, toX = (v) => sx + (sw * v) / 10000;
  [[0, 1500, C.a5, "Competitive"], [1500, 2500, C.a4, "Moderate"], [2500, 10000, C.a1, "Highly concentrated: above 2,500"]].forEach(([a, b, color, label], k) => {
    s.addShape(pres.shapes.RECTANGLE, { x: toX(a), y: sy, w: toX(b) - toX(a), h: 0.34, fill: { color }, line: { type: "none" }, objectName: `band ${k + 1}` });
    text(s, label, { x: toX(a) + 0.08, y: sy, w: toX(b) - toX(a) - 0.12, h: 0.34, fontSize: 10, bold: true, color: C.bg1,
      valign: "middle", align: k === 2 ? "left" : "center", objectName: `band ${k + 1} label` });
  });
  [[0, "0", "left"], [1500, "1,500", "left"], [2500, "2,500", "left"], [10000, "10,000 = one vendor has everything", "right"]].forEach(([v, l, al], k) => {
    text(s, l, { x: al === "right" ? toX(v) - 3.0 : toX(v) - (k ? 0.2 : 0), y: sy + 0.38, w: 3.0, h: 0.25, fontSize: 10, color: C.text2,
      align: al, objectName: `scale tick ${k + 1}` });
  });
  takeaway(s, MSG.method.takeaway);
}

// ------------------------------------------------------------------ 6. finding 1: the trend

{
  const s = content("Talk", MSG.trend);
  s.addChart(pres.charts.LINE, [{ name: "Share of dollars in highly concentrated segments", labels: years, values: v1.map((r) => need(r[KEY], "trend")) }],
    { ...axis, x: 0.4, y: 1.0, w: 6.3, h: 3.45, chartColors: [H.accent1], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 5,
      valAxisMinVal: 0, valAxisMaxVal: 60, valAxisLabelFormatCode: '0"%"', showLegend: false, showTitle: true,
      title: "Share of each year's contract dollars in segments with HHI above 2,500", objectName: "trend chart" });
  stat(s, 7.0, 1.05, 2.5, pct(first[KEY], 0, "first year"), `of dollars in FY${first.fiscal_year}`, C.a2, "first year", 34);
  stat(s, 7.0, 2.2, 2.5, pct(last[KEY], 0, "last year"), `of dollars in FY${last.fiscal_year}`, C.a1, "last year", 34);
  text(s, MSG.trend.dip, { x: 7.0, y: 3.4, w: 2.5, h: 1.05, fontSize: 11, color: C.text2, objectName: "dip note" });
  takeaway(s, MSG.trend.takeaway);
}

// ------------------------------------------------------------------ 7. finding 2: where it sits

{
  const s = content("Talk", MSG.where);
  const pick = (g, fy) => need((kind.find((r) => r.group === g && r.fiscal_year === fy) || {}).above_2500_pct_of_net, `kind ${g} ${fy}`);
  const groups = [["Products", "product"], ["Services", "service"], ["Research", "research"]];
  s.addChart(pres.charts.BAR, [
    { name: `FY${first.fiscal_year}`, labels: groups.map((g) => g[0]), values: groups.map((g) => pick(g[1], first.fiscal_year)) },
    { name: `FY${last.fiscal_year}`, labels: groups.map((g) => g[0]), values: groups.map((g) => pick(g[1], last.fiscal_year)) },
  ], { ...axis, x: 0.4, y: 1.0, w: 4.6, h: 3.45, barDir: "col", chartColors: [H.accent3, H.accent1], valAxisMinVal: 0, valAxisMaxVal: 80,
    valAxisLabelFormatCode: '0"%"', showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: H.dk1,
    dataLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true, barGapWidthPct: 60,
    title: "Share of dollars in highly concentrated segments", objectName: "kind chart" });
  const x0 = 5.3, y0 = 1.05, w = 4.2, prev = String(Number(last.fiscal_year) - 1);
  card(s, x0, y0, w, 3.4, "example card");
  text(s, "Example: Defense buying fixed-wing aircraft", { x: x0 + 0.2, y: y0 + 0.13, w: w - 0.4, h: 0.32, fontSize: 14, bold: true, objectName: "example heading" });
  text(s, `FY${prev}`, { x: x0 + 2.15, y: y0 + 0.55, w: 0.9, h: 0.28, fontSize: 11, color: C.text2, align: "right", objectName: "example col 1" });
  text(s, `FY${last.fiscal_year}`, { x: x0 + 3.1, y: y0 + 0.55, w: 0.9, h: 0.28, fontSize: 11, color: C.text2, align: "right", objectName: "example col 2" });
  [["Money spent", bigShort(wing.net_before, "wing before"), bigShort(wing.net_after, "wing after")],
   ["Largest vendor's share", pct(wing.largest_share_before, 0, "share before"), pct(wing.largest_share_after, 0, "share after")],
   ["HHI", count(wing.hhi_before), count(wing.hhi_after)]].forEach(([k, a, b], i) => {
    const y = y0 + 0.9 + i * 0.5;
    text(s, k, { x: x0 + 0.2, y, w: 1.95, h: 0.4, fontSize: 13, valign: "middle", objectName: `example row ${i + 1} name` });
    text(s, a, { x: x0 + 2.15, y, w: 0.9, h: 0.4, fontSize: 15, color: C.a2, bold: true, align: "right", valign: "middle", objectName: `example row ${i + 1} before` });
    text(s, b, { x: x0 + 3.1, y, w: 0.9, h: 0.4, fontSize: 15, color: C.a1, bold: true, align: "right", valign: "middle", objectName: `example row ${i + 1} after` });
  });
  const oneShare = (100 * need(last.one_positive_vendor_cells, "single cells")) / need(last.cells, "cells");
  text(s, [{ text: `${oneShare.toFixed(0)}% of segments have a single vendor,`, options: { bold: true, breakLine: true } },
           { text: `but they hold only ${pct(last.one_positive_vendor_pct_of_net, 1, "single dollars")} of the money.`, options: { color: C.text2 } }],
    { x: x0 + 0.2, y: y0 + 2.55, w: w - 0.4, h: 0.75, fontSize: 13, objectName: "single vendor note" });
  takeaway(s, MSG.where.takeaway);
}

// ------------------------------------------------------------------ 8. what it means and what is next

{
  const s = content("Talk", MSG.next);
  const all3 = eras.find((r) => r.eras_present.split(" + ").length === 3) || {};
  const r500 = rising.find((r) => r.cutoff === "500") || {};
  const cols = [
    ["What we can trust", C.a5, [`The copy is exact, and totals match GAO within ${gaoGap.toFixed(1)}%`,
      `Product codes mostly carry across the FY2012 and FY2021 changes (${pct(all3.pct_of_net, 0, "all eras")} of dollars)`,
      "So most segments can be followed for all 18 years"]],
    ["Be careful about", C.a4, ["Scores swing from year to year with single large awards",
      `${pct(r500.rising_pct, 0, "rising")} of trend lines "rise" 500 points, but ${pct(r500.rising_pct_after_shuffle, 0, "shuffled")} still do with their years shuffled`,
      "So a rise has to beat chance before it counts"]],
    ["What we do next", C.a1, MSG.next.steps],
  ];
  cols.forEach(([headline, color, items], k) => {
    const x = 0.5 + k * 3.08, w = 2.86;
    card(s, x, 1.1, w, 3.55, `column ${k + 1} card`);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 1.3, w: 0.3, h: 0.3, fill: { color }, line: { type: "none" }, objectName: `column ${k + 1} dot` });
    text(s, headline, { x: x + 0.6, y: 1.27, w: w - 0.75, h: 0.36, fontSize: 15, bold: true, valign: "middle", objectName: `column ${k + 1} head` });
    text(s, items.map((t, i) => ({ text: t, options: { bullet: { indent: 12 }, breakLine: i < items.length - 1 } })),
      { x: x + 0.2, y: 1.8, w: w - 0.4, h: 2.75, fontSize: 13, paraSpaceAfter: 9, objectName: `column ${k + 1} items` });
  });
}

// ------------------------------------------------------------------ backup slides

pres.addSection({ title: "Backup" });
const backup = (msg) => {
  const s = pres.addSlide({ masterName: "BACKUP", sectionTitle: "Backup" });
  s.addText(msg.title, { placeholder: "title" });
  s.addNotes(msg.notes);
  if (msg.note) text(s, msg.note, { x: 0.5, y: 4.45, w: 9.0, h: 0.75, fontSize: 12, color: C.text2, objectName: "backup note" });
  return s;
};
const head = (t) => ({ text: t, options: { bold: true, color: H.lt1, fill: { color: H.accent2 } } });
const tableOpts = (x, y, w, colW) => ({ x, y, w, colW, fontSize: 11, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DAE1" },
  fill: { color: H.lt1 }, margin: 0.05, autoPage: false });

{   // B1. the data decisions
  const s = backup(MSG.backup_decisions);
  s.addChart(pres.charts.LINE, [
    { name: "As recorded (V0)", labels: years.map((y) => `'${y.slice(2)}`), values: v0.map((r) => need(r[KEY], "v0")) },
    { name: "Decisions as proposed (V1)", labels: years.map((y) => `'${y.slice(2)}`), values: v1.map((r) => need(r[KEY], "v1")) },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.0, h: 3.35, chartColors: [H.accent3, H.accent1], lineSize: 2.5, lineDataSymbol: "none",
    valAxisMinVal: 0, valAxisMaxVal: 60, valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true,
    title: "Share of dollars above HHI 2,500", objectName: "decisions chart" });
  const rows = [[head("Against V0"), head("Segments changing band"), head("Into above 2,500"), head("Out of above 2,500")]];
  for (const v of ["V1", "V8b"]) {
    const b = bands.filter((r) => r.variant === v);
    if (!b.length) { rows.push([v, { text: "Pending: needs Stage 2 flags for every year", options: { colspan: 3, italic: true, color: H.dk2 } }]); continue; }
    const sum = (k) => b.reduce((a, r) => a + need(r[k], k), 0);
    rows.push([v, `${count(sum("cells_changing_band"))} of ${count(sum("cells_in_both"))} (${((100 * sum("cells_changing_band")) / sum("cells_in_both")).toFixed(1)}%)`,
      count(sum("into_above_2500")), count(sum("out_of_above_2500"))]);
  }
  s.addTable(rows, { ...tableOpts(5.6, 1.15, 3.9, [0.55, 1.55, 0.9, 0.9]), fontSize: 10 });
}
{   // B2. product code changes
  const s = backup(MSG.backup_codes);
  const cw = 9.0 / 18;
  [["FY2008 to FY2011", 0, 4, C.a3], ["FY2012 to FY2020", 4, 9, C.a2], ["FY2021 to FY2025", 13, 5, C.a3]].forEach(([span, start, n, color], k) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5 + start * cw + 0.03, y: 1.15, w: n * cw - 0.06, h: 0.5, fill: { color }, line: { type: "none" }, objectName: `era ${k + 1}` });
    text(s, `${n} years, ${span}`, { x: 0.5 + start * cw, y: 1.15, w: n * cw, h: 0.5, fontSize: 11, bold: true, color: C.bg1, align: "center",
      valign: "middle", objectName: `era ${k + 1} label` });
  });
  const all3 = eras.find((r) => r.eras_present.split(" + ").length === 3) || {};
  const s12 = brk12.find((r) => r.status === "starts") || {}, s21 = brk21.find((r) => r.status === "starts") || {};
  stat(s, 0.5, 2.0, 2.8, pct(all3.pct_of_net, 1, "all eras"), "of all dollars are on codes used in every era", C.a2, "codes all");
  stat(s, 3.6, 2.0, 2.8, pct(s12.pct_of_fy2012, 1, "new 2012"), "of FY2012 dollars went to codes new that year", C.a1, "codes 2012");
  stat(s, 6.7, 2.0, 2.8, pct(s21.pct_of_fy2021, 1, "new 2021"), "of FY2021 dollars went to codes new that year", C.a1, "codes 2021");
}
{   // B3. noise
  const s = backup(MSG.backup_noise);
  const labels = noise.map((r) => `D${r.decile}`);
  s.addChart([
    { type: pres.charts.BAR, data: [{ name: "Median yearly change", labels, values: noise.map((r) => need(r.change_median, "median")) },
                                    { name: "90th percentile", labels, values: noise.map((r) => need(r.change_p90, "p90")) }],
      options: { chartColors: [H.accent2, H.accent6], barGapWidthPct: 40 } },
    { type: pres.charts.LINE, data: [{ name: "500-point cutoff", labels, values: noise.map(() => 500) }],
      options: { chartColors: [H.accent1], lineSize: 2, lineDataSymbol: "none", lineDash: "dash" } },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.6, h: 3.35, valAxisMinVal: 0, showLegend: true, legendPos: "b", showTitle: true,
    title: "Yearly change in HHI by segment size, smallest (D1) to largest (D10)", objectName: "noise chart" });
  const rows = [[head("Cutoff"), head("Lines rising"), head("Years shuffled")]];
  rising.forEach((r) => rows.push([count(r.cutoff), pct(r.rising_pct, 1, "rising"), pct(r.rising_pct_after_shuffle, 1, "shuffled")]));
  s.addTable(rows, tableOpts(6.25, 1.2, 3.25, [0.9, 1.1, 1.25]));
}
{   // B4. vendors
  const s = backup(MSG.backup_vendors);
  const rows = [[head("Rank"), head("Parent ID, by its name on the most dollars"), head("Net, FY2008 to FY2025")]];
  top.slice(0, 10).forEach((r) => rows.push([r.rank, r.name_most_dollars, bigShort(r.net_all_years, "vendor net")]));
  s.addTable(rows, { ...tableOpts(0.5, 1.1, 9.0, [0.8, 6.0, 2.2]), fontSize: 10, rowH: 0.27 });
}
{   // B5. features
  const s = backup(MSG.backup_features);
  const pickYears = ["2008", "2012", "2018", "2025"];
  const colsF = [["Sole source on the umbrella", "umbrella competition: sole_source pct"], ["Order field blank", "order competition: order_blank pct"],
                 ["Set-aside field blank", "set-aside: set_aside_blank pct"], ["Offers reported, share of competed", "offers reported, pct of competed"]];
  const rows = [[head("Share of dollars"), ...pickYears.map((y) => head(`FY${y}`))]];
  colsF.forEach(([label, k]) => rows.push([label, ...pickYears.map((y) => pct((cover.find((r) => r.fiscal_year === y) || {})[k], 1, k))]));
  s.addTable(rows, tableOpts(0.5, 1.25, 9.0, [3.4, 1.4, 1.4, 1.4, 1.4]));
}

// ------------------------------------------------------------------ write

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log(`deck -> ${OUT}`);
})();
