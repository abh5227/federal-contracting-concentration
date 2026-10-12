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
const v1 = byYear.filter((r) => r.variant === "V1");
const v0 = byYear.filter((r) => r.variant === "V0");
const years = v1.map((r) => r.fiscal_year);
const LAST = years[years.length - 1], FIRST = years[0], PREV = String(Number(LAST) - 1);
const civ = readCsv("civilian_by_year");
const civFirst = civ[0], civLast = civ[civ.length - 1];
const civKind = readCsv("civilian_by_kind");
const civAgency = readCsv("civilian_by_agency");
const civTop = readCsv("civilian_top_segments");
const civDip = readCsv(`civilian_drivers_fy${PREV}`);
const exSeg = readCsv("example_segment");
const dodCiv = readCsv("concentration_dod_civilian");
const eras = readCsv("psc_era_patterns");
const brk12 = readCsv("psc_break_fy2012");
const brk21 = readCsv("psc_break_fy2021");
const noise = readCsv("noise_by_size");
const rising = readCsv("rising_counts");
const bands = readCsv("band_changes");
const top = readCsv("top100_vendors");
const cover = readCsv("feature_coverage");
const spend = readCsv("spending_by_year");
const example = readCsv("example_row")[0];
const checks = readCsv("base_checks");
const inventory = readRepoCsv("reports/integrity/stage0_inventory.csv").filter((r) => r.status === "stage 0");
const flagCatalog = readRepoCsv("config/flag_catalog.csv");
const gao = readRepoCsv("reports/integrity/completeness_check.csv")
  .filter((r) => /GAO/.test(r.publisher || "") && num(r.fiscal_year) >= 2022);
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
const dipTop = civDip[0];
const civYear = (fy) => civ.find((r) => r.fiscal_year === fy) || {};
const dipTotal = need(civYear(PREV).net_above_2500, "civ prev") - need(civYear(String(Number(PREV) - 1)).net_above_2500, "civ prev2");
const exFirst = exSeg.find((r) => r.fiscal_year === "2019"), exLast = exSeg[exSeg.length - 1];
if (!exFirst) throw new Error("example_segment.csv has no FY2019 row");
const KEY = "above 2,500 pct of net";
const short = (y) => `'${y.slice(2)}`;

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
  stat(s, 0.5, 1.1, 3.7, bigShort(civLast.net, "civilian net"), `spent through civilian agency contracts in FY${LAST}`, C.a1, "spend", 40);
  text(s, `Defense spent another ${bigShort(lastSpend.net_v1_dod, "dod net")}. It buys from a handful of large prime contractors and studies its own market, so our focus is the civilian agencies.`,
    { x: 0.5, y: 2.45, w: 3.7, h: 1.0, fontSize: 12, color: C.text2, objectName: "why civilian" });
  text(s, MSG.question.goal, { x: 0.5, y: 3.5, w: 3.7, h: 0.95, fontSize: 14, bold: true, objectName: "goal" });
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
  const stats = [[`${inventory.length}`, `yearly files, FY${FIRST} to FY${LAST}`, C.a2],
                 [`${(rowsAll / 1e6).toFixed(1)}M`, "contract actions (rows)", C.a1],
                 [`${zipGB.toFixed(0)} GB`, `zipped, ${textGB.toFixed(0)} GB once unzipped`, C.a2],
                 [bigShort(netAll, "18-year net"), "obligated over the 18 years", C.a2]];
  stats.forEach(([v, l, c], k) => stat(s, 0.5 + (k % 2) * 2.15, 1.05 + Math.floor(k / 2) * 1.4, 2.0, v, l, c, `data stat ${k + 1}`, 30));
  text(s, MSG.data.source, { x: 0.5, y: 3.95, w: 4.1, h: 0.5, fontSize: 11, italic: true, color: C.text2, objectName: "source" });
  const x0 = 4.85, y0 = 1.1, w = 4.65;
  card(s, x0, y0, w, 3.3, "row card");
  text(s, "One row = one contract action. A real one:", { x: x0 + 0.2, y: y0 + 0.13, w: w - 0.4, h: 0.32, fontSize: 13, bold: true,
    objectName: "row card heading" });
  const fields = [["When", example.action_date], ["Who bought", example.awarding_agency_name],
                  ["What", `${example.product_or_service_code}  ${sentence(example.product_or_service_code_description.replace("MEDICAL- ", ""))}`],
                  ["From whom", checkedName(MSG.data.vendorDisplay, example.recipient_parent_name)],
                  ["How much", big(example.federal_action_obligation, "example amount")],
                  ["Competed?", sentence(example.extent_competed)]];
  fields.forEach(([k, v], i) => {
    const y = y0 + 0.55 + i * 0.44;
    text(s, k, { x: x0 + 0.2, y, w: 1.2, h: 0.4, fontSize: 12, color: C.text2, valign: "middle", objectName: `field ${i + 1} name` });
    text(s, v, { x: x0 + 1.4, y, w: w - 1.6, h: 0.4, fontSize: 13, bold: k === "How much",
      color: k === "How much" ? C.a1 : C.text1, valign: "middle", objectName: `field ${i + 1} value` });
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

// ------------------------------------------------------------------ 5. what a segment is, and its score

{
  const s = content("Talk", MSG.segment);
  // the segment, built from three parts
  const parts = [["Agency", "Veterans Affairs"], ["Product", "Managed healthcare"], ["Year", `FY${LAST}`]];
  parts.forEach(([k, v], i) => {
    const x = 0.5 + i * 1.5;
    card(s, x, 1.1, 1.38, 0.95, `segment part ${i + 1}`);
    text(s, [{ text: k, options: { fontSize: 11, color: C.text2, breakLine: true } }, { text: v, options: { fontSize: 13, bold: true } }],
      { x: x + 0.1, y: 1.15, w: 1.18, h: 0.85, align: "center", valign: "middle", objectName: `segment part ${i + 1} text` });
    if (i < 2) text(s, "+", { x: x + 1.38, y: 1.1, w: 0.12, h: 0.95, fontSize: 16, bold: true, color: C.a3, align: "center", valign: "middle", objectName: `plus ${i + 1}` });
  });
  text(s, [{ text: "= one segment. ", options: { bold: true } },
           { text: `In it, ${count(exLast.positive_vendors)} companies shared ${bigShort(exLast.net, "example net")}, and the largest got ${pct(exLast.largest_share_pct, 0, "example share")}.`,
             options: { color: C.text2 } }],
    { x: 0.5, y: 2.15, w: 4.4, h: 0.65, fontSize: 13, objectName: "segment result" });
  text(s, `We cut 18 years of contracts into ${Math.round(segments / 1000)}K segments like this. A company counts once, under its parent.`,
    { x: 0.5, y: 2.85, w: 4.4, h: 0.5, fontSize: 12, color: C.text2, objectName: "segment count" });
  // HHI, with the two examples
  text(s, "Each segment gets a score, the HHI", { x: 5.2, y: 1.1, w: 4.3, h: 0.3, fontSize: 14, bold: true, objectName: "hhi heading" });
  text(s, "Square each company's % share, then add them up.", { x: 5.2, y: 1.42, w: 4.3, h: 0.28, fontSize: 12, color: C.text2, objectName: "hhi how" });
  const rowsHhi = [["Five equal companies", [20, 20, 20, 20, 20], "2,000", C.a2], ["One company with 80%", [80, 5, 5, 5, 5], "6,500", C.a1]];
  const barX = 5.2, barW = 3.2;
  rowsHhi.forEach(([label, shares, score, color], r) => {
    const y = 2.1 + r * 0.68;
    text(s, label, { x: barX, y: y - 0.27, w: barW, h: 0.25, fontSize: 11, color: C.text2, objectName: `hhi row ${r + 1} label` });
    let x = barX;
    shares.forEach((sh, k) => {
      const w = (barW * sh) / 100;
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.01, y, w: w - 0.02, h: 0.32, line: { type: "none" },
        fill: { color: k === 0 ? color : [C.a3, C.a6][k % 2] }, objectName: `hhi row ${r + 1} vendor ${k + 1}` });
      if (w >= 0.5) text(s, `${sh}%`, { x, y, w, h: 0.32, fontSize: 10, bold: true, color: C.bg1, align: "center", valign: "middle",
        objectName: `hhi row ${r + 1} share ${k + 1}` });
      x += w;
    });
    text(s, score, { x: 8.5, y, w: 1.0, h: 0.32, fontSize: 16, bold: true, color, valign: "middle", objectName: `hhi row ${r + 1} score` });
  });
  // the scale
  const sx = 0.5, sw = 9.0, sy = 3.72, toX = (v) => sx + (sw * v) / 10000;
  [[0, 1500, C.a5, "Competitive"], [1500, 2500, C.a4, "Moderate"], [2500, 10000, C.a1, "Highly concentrated: above 2,500"]].forEach(([a, b, color, label], k) => {
    s.addShape(pres.shapes.RECTANGLE, { x: toX(a), y: sy, w: toX(b) - toX(a), h: 0.32, fill: { color }, line: { type: "none" }, objectName: `band ${k + 1}` });
    text(s, label, { x: toX(a) + 0.08, y: sy, w: toX(b) - toX(a) - 0.12, h: 0.32, fontSize: 10, bold: true, color: C.bg1,
      valign: "middle", align: k === 2 ? "left" : "center", objectName: `band ${k + 1} label` });
  });
  const exX = toX(need(exLast.hhi, "example hhi"));
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: exX - 0.09, y: sy - 0.2, w: 0.18, h: 0.16, rotate: 180, fill: { color: C.text1 },
    line: { type: "none" }, objectName: "example marker" });
  text(s, `VA managed healthcare: ${count(exLast.hhi)}`, { x: exX - 2.6, y: sy - 0.45, w: 2.5, h: 0.24, fontSize: 10, bold: true, align: "right",
    objectName: "example marker label" });
  [[0, "0", "left"], [1500, "1,500", "left"], [2500, "2,500", "left"], [10000, "10,000 = one company", "right"]].forEach(([v, l, al], k) => {
    text(s, l, { x: al === "right" ? toX(v) - 2.0 : toX(v) - (k ? 0.2 : 0), y: sy + 0.36, w: 2.0, h: 0.22, fontSize: 10, color: C.text2,
      align: al, objectName: `scale tick ${k + 1}` });
  });
  takeaway(s, MSG.segment.takeaway);
}

// ------------------------------------------------------------------ 6. finding 1: the yearly measure and its trend

{
  const s = content("Talk", MSG.trend);
  // the measure, worked through for the latest year
  const eq = [[bigShort(civLast.net_above_2500, "civ above"), "in segments above 2,500", C.a1],
              ["÷", "", C.a3], [bigShort(civLast.net, "civ net"), `all civilian contract dollars, FY${LAST}`, C.a2],
              ["=", "", C.a3], [pct(civLast.above_2500_pct_of_net, 0, "civ share"), "highly concentrated", C.a1]];
  let x = 0.5;
  eq.forEach(([v, l, c], k) => {
    const w = l ? 2.05 : 0.35;
    text(s, v, { x, y: 1.0, w, h: 0.5, fontSize: l ? 24 : 22, bold: true, color: c, fontFace: THEME.headFontFace, align: "center",
      valign: "bottom", objectName: `measure ${k + 1}` });
    if (l) text(s, l, { x, y: 1.5, w, h: 0.32, fontSize: 11, color: C.text2, align: "center", objectName: `measure ${k + 1} label` });
    x += w + 0.1;
  });
  s.addChart(pres.charts.LINE, [{ name: "Civilian agencies", labels: years.map(short), values: civ.map((r) => need(r.above_2500_pct_of_net, "civ trend")) }],
    { ...axis, x: 0.4, y: 1.9, w: 6.0, h: 2.6, chartColors: [H.accent1], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 5,
      valAxisMinVal: 0, valAxisMaxVal: 60, valAxisMajorUnit: 20, valAxisLabelFormatCode: '0"%"', showLegend: false, showTitle: true,
      title: "Share of civilian contract dollars in highly concentrated segments, each year", objectName: "trend chart" });
  card(s, 6.65, 1.95, 2.85, 2.0, "dip card");
  text(s, [{ text: `Why the dip in FY${PREV}?`, options: { bold: true, breakLine: true } },
           { text: `One Department of Energy segment, ${MSG.trend.dipSegment} (${bigShort(dipTop.net_after, "dip net")}), fell below 2,500 that year. It explains ${bigShort(-need(dipTop.change_in_net_above_2500, "dip change"), "dip change")} of the ${bigShort(-dipTotal, "dip total")} drop.`,
             options: { color: C.text2, fontSize: 12 } }],
    { x: 6.85, y: 2.08, w: 2.5, h: 1.8, fontSize: 13, paraSpaceAfter: 6, objectName: "dip text" });
  takeaway(s, MSG.trend.takeaway);
}

// ------------------------------------------------------------------ 7. finding 2: which agencies and segments

{
  const s = content("Talk", MSG.where);
  const ag = (code, fy) => civAgency.find((r) => r.agency_code === code && r.fiscal_year === fy) || {};
  const codes = MSG.where.agencies.map((a) => a.code);
  s.addChart(pres.charts.BAR, [
    { name: `FY${FIRST}`, labels: MSG.where.agencies.map((a) => a.label), values: codes.map((c) => need(ag(c, FIRST).above_2500_pct_of_net, `agency ${c} first`)) },
    { name: `FY${LAST}`, labels: MSG.where.agencies.map((a) => a.label), values: codes.map((c) => need(ag(c, LAST).above_2500_pct_of_net, `agency ${c} last`)) },
  ], { ...axis, x: 0.4, y: 1.0, w: 4.7, h: 3.5, barDir: "bar", chartColors: [H.accent3, H.accent1], valAxisMinVal: 0, valAxisMaxVal: 100,
    valAxisLabelFormatCode: '0"%"', showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: H.dk1,
    dataLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true, barGapWidthPct: 50, catAxisOrientation: "maxMin",
    title: "Share of dollars in highly concentrated segments", objectName: "agency chart" });
  const x0 = 5.35, y0 = 1.05, w = 4.15;
  card(s, x0, y0, w, 3.4, "segments card");
  text(s, `The three biggest concentrated civilian segments, FY${LAST}`, { x: x0 + 0.2, y: y0 + 0.12, w: w - 0.4, h: 0.5, fontSize: 13, bold: true,
    objectName: "segments heading" });
  civTop.slice(0, 3).forEach((r, i) => {
    const y = y0 + 0.72 + i * 0.85;
    text(s, [{ text: `VA: ${MSG.where.segmentLabels[i]}`, options: { bold: true, breakLine: true } },
             { text: `${checkedName(MSG.where.segmentVendors[i], r.largest_vendor_name)} has ${pct(r.largest_share_pct, 0, "top share")}`, options: { color: C.text2, fontSize: 12 } }],
      { x: x0 + 0.2, y, w: 2.75, h: 0.75, fontSize: 13, objectName: `segment ${i + 1} text` });
    text(s, bigShort(r.net, "segment net"), { x: x0 + 2.95, y, w: 1.0, h: 0.45, fontSize: 18, bold: true, color: C.a1, align: "right",
      objectName: `segment ${i + 1} net` });
  });
  takeaway(s, MSG.where.takeaway);
}

// ------------------------------------------------------------------ 8. the example over time

{
  const s = content("Talk", MSG.example);
  const yrs = exSeg.filter((r) => num(r.fiscal_year) >= 2016);
  s.addChart([
    { type: pres.charts.BAR, data: [{ name: "Money spent ($B)", labels: yrs.map((r) => r.fiscal_year), values: yrs.map((r) => need(r.net, "ex net") / 1e9) }],
      options: { chartColors: [H.accent6], barGapWidthPct: 40 } },
    { type: pres.charts.LINE, data: [{ name: "Largest company's share (%)", labels: yrs.map((r) => r.fiscal_year), values: yrs.map((r) => need(r.largest_share_pct, "ex share")) }],
      options: { chartColors: [H.accent1], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 6, secondaryValAxis: true, secondaryCatAxis: true } },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.6, h: 3.5, showLegend: true, legendPos: "b", showTitle: true,
    title: "Veterans Affairs, managed healthcare", objectName: "example chart",
    valAxes: [{ showValAxisTitle: true, valAxisTitle: "$ billion", valAxisMinVal: 0, valAxisTitleFontSize: 10, valAxisTitleColor: H.dk2 },
              { showValAxisTitle: true, valAxisTitle: "largest share %", valAxisMinVal: 0, valAxisMaxVal: 100, valGridLine: { style: "none" },
                valAxisTitleFontSize: 10, valAxisTitleColor: H.dk2 }],
    catAxes: [{ catAxisTitle: "" }, { catAxisHidden: true }] });
  const cols = [[`FY${exFirst.fiscal_year}`, exFirst, C.a2], [`FY${exLast.fiscal_year}`, exLast, C.a1]];
  cols.forEach(([label, r, color], k) => {
    const x = 6.25 + k * 1.65;
    text(s, label, { x, y: 1.05, w: 1.5, h: 0.3, fontSize: 13, bold: true, color: C.text2, objectName: `example ${k + 1} year` });
    [[bigShort(r.net, "ex net"), "spent"], [count(r.positive_vendors), "companies"], [pct(r.largest_share_pct, 0, "ex share"), "to the largest"],
     [count(r.hhi), "HHI"]].forEach(([v, l], i) => {
      text(s, [{ text: v, options: { bold: true, fontSize: 20, color, breakLine: true } }, { text: l, options: { fontSize: 11, color: C.text2 } }],
        { x, y: 1.4 + i * 0.75, w: 1.5, h: 0.7, fontFace: THEME.headFontFace, objectName: `example ${k + 1} stat ${i + 1}` });
    });
  });
  takeaway(s, MSG.example.takeaway);
}

// ------------------------------------------------------------------ 9. what it means and what is next

{
  const s = content("Talk", MSG.next);
  const cols = [["We can trust it", C.a5, MSG.next.trust], ["Be careful", C.a4, MSG.next.careful], ["Next", C.a1, MSG.next.steps]];
  cols.forEach(([headline, color, items], k) => {
    const x = 0.5 + k * 3.08, w = 2.86;
    card(s, x, 1.15, w, 2.9, `column ${k + 1} card`);
    s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: 1.37, w: 0.32, h: 0.32, fill: { color }, line: { type: "none" }, objectName: `column ${k + 1} dot` });
    text(s, headline, { x: x + 0.65, y: 1.33, w: w - 0.8, h: 0.4, fontSize: 18, bold: true, valign: "middle", objectName: `column ${k + 1} head` });
    text(s, items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
      { x: x + 0.22, y: 1.95, w: w - 0.44, h: 2.0, fontSize: 15, paraSpaceAfter: 10, objectName: `column ${k + 1} items` });
  });
  takeaway(s, MSG.next.takeaway, 4.3, 0.7);
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

{   // B1. Defense and civilian, for context
  const s = backup(MSG.backup_defense);
  const series = (g) => years.map((y) => need((dodCiv.find((r) => r.group === g && r.fiscal_year === y) || {}).above_2500_pct_of_net, `${g} ${y}`));
  s.addChart(pres.charts.LINE, [{ name: "Civilian agencies", labels: years.map(short), values: series("civilian") },
                                { name: "Defense", labels: years.map(short), values: series("DoD") }],
    { ...axis, x: 0.4, y: 1.0, w: 9.2, h: 3.35, chartColors: [H.accent1, H.accent3], lineSize: 2.5, lineDataSymbol: "none", valAxisMinVal: 0,
      valAxisMaxVal: 60, valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true,
      title: "Share of dollars in highly concentrated segments", objectName: "defense chart" });
}
{   // B2. civilian products, services and research
  const s = backup(MSG.backup_kind);
  const pick = (k, fy) => civKind.find((r) => r.kind === k && r.fiscal_year === fy) || {};
  const groups = [["Services", "service"], ["Products", "product"], ["Research", "research"]];
  s.addChart(pres.charts.BAR, [
    { name: `FY${FIRST}`, labels: groups.map((g) => g[0]), values: groups.map((g) => need(pick(g[1], FIRST).above_2500_pct_of_net, "kind first")) },
    { name: `FY${LAST}`, labels: groups.map((g) => g[0]), values: groups.map((g) => need(pick(g[1], LAST).above_2500_pct_of_net, "kind last")) },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.2, h: 3.35, barDir: "col", chartColors: [H.accent3, H.accent1], valAxisMinVal: 0, valAxisMaxVal: 100,
    valAxisLabelFormatCode: '0"%"', showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: H.dk1,
    dataLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true, title: "Civilian: share of dollars in highly concentrated segments",
    objectName: "kind chart" });
  const rows = [[head("Civilian dollars"), head(`FY${FIRST}`), head(`FY${LAST}`)]];
  groups.forEach(([label, k]) => rows.push([label, bigShort(pick(k, FIRST).net, "kind net"), bigShort(pick(k, LAST).net, "kind net")]));
  s.addTable(rows, tableOpts(5.9, 1.2, 3.6, [1.4, 1.1, 1.1]));
}
{   // B3. the data decisions
  const s = backup(MSG.backup_decisions);
  s.addChart(pres.charts.LINE, [
    { name: "As recorded (V0)", labels: years.map(short), values: v0.map((r) => need(r[KEY], "v0")) },
    { name: "Decisions as proposed (V1)", labels: years.map(short), values: v1.map((r) => need(r[KEY], "v1")) },
  ], { ...axis, x: 0.4, y: 1.0, w: 5.0, h: 3.35, chartColors: [H.accent3, H.accent1], lineSize: 2.5, lineDataSymbol: "none",
    valAxisMinVal: 0, valAxisMaxVal: 60, valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true,
    title: "All agencies: share of dollars above HHI 2,500", objectName: "decisions chart" });
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
{   // B4. product code changes
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
{   // B5. noise
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
{   // B6. features
  const s = backup(MSG.backup_features);
  const pickYears = ["2008", "2012", "2018", "2025"];
  const colsF = [["Sole source on the umbrella", "umbrella competition: sole_source pct"], ["Order field blank", "order competition: order_blank pct"],
                 ["Set-aside field blank", "set-aside: set_aside_blank pct"], ["Offers reported, share of competed", "offers reported, pct of competed"]];
  const rows = [[head("Share of dollars, all agencies"), ...pickYears.map((y) => head(`FY${y}`))]];
  colsF.forEach(([label, k]) => rows.push([label, ...pickYears.map((y) => pct((cover.find((r) => r.fiscal_year === y) || {})[k], 1, k))]));
  s.addTable(rows, tableOpts(0.5, 1.25, 9.0, [3.4, 1.4, 1.4, 1.4, 1.4]));
}

// ------------------------------------------------------------------ write

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log(`deck -> ${OUT}`);
})();
