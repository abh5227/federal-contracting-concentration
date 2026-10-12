// Builds the 5-minute EDA deck for the team and the class (docs/eda/eda_plan.md, "The presentation").
//
//   cd tools/eda_deck && npm install && node build.js
//
// Every chart and number comes from the summary tables in reports/eda/, so a rerun of src/eda updates the deck.
// Slide titles and speaker notes state findings, so they live in messages.json and are written only after the
// results have been read. The build stops while any message still says TBD.

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const REPO = path.resolve(__dirname, "..", "..");
const EDA = process.env.EDA_DIR || path.join(REPO, "reports", "eda");
const OUT = process.env.DECK_OUT || path.join(REPO, "reports", "eda", "eda_presentation.pptx");
const MSG = JSON.parse(fs.readFileSync(process.env.DECK_MESSAGES || path.join(__dirname, "messages.json"), "utf8"));

// ------------------------------------------------------------------ data

function readCsv(name) {
  const text = fs.readFileSync(path.join(EDA, `${name}.csv`), "utf8").replace(/^﻿/, "");
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

const num = (x) => (x === undefined || x === "" ? null : Number(x));
const need = (x) => { if (num(x) === null || Number.isNaN(num(x))) throw new Error("a number the deck needs is missing from reports/eda/"); return num(x); };
const pct = (x, d = 0) => `${need(x).toFixed(d)}%`;
const big = (x) => {
  const v = Math.abs(num(x));
  const s = v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`;
  return num(x) < 0 ? `-${s}` : s;
};
const count = (x) => Math.round(num(x)).toLocaleString("en-US");

for (const [k, v] of Object.entries(MSG)) {
  if (JSON.stringify(v).includes("TBD")) throw new Error(`messages.json: "${k}" still says TBD. Write it after reading the results.`);
}

const byYear = readCsv("concentration_by_year");
const v1 = byYear.filter((r) => r.variant === "V1");
const v0 = byYear.filter((r) => r.variant === "V0");
const years = v1.map((r) => r.fiscal_year);
const first = v1[0], last = v1[v1.length - 1];
const dodCiv = readCsv("concentration_dod_civilian");
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

// ------------------------------------------------------------------ theme and layouts

const THEME = {
  name: "Concentration",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2430", lt1: "FFFFFF", dk2: "2E3A4D", lt2: "EEF0F3",
    accent1: "C2410C",   // burnt orange: highly concentrated
    accent2: "2E3A4D",   // slate: the rest of the market
    accent3: "8A94A6",   // muted grey: comparison series
    accent4: "E9A23B",   // amber: moderately concentrated
    accent5: "4D7C6F",   // muted green: civilian
    accent6: "B9C0CC",
    hlink: "C2410C", folHlink: "8A94A6",
  },
};
const H = THEME.colors;   // hex values, for chart options that take hex only

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";   // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Vendor concentration in federal contracting: first look at 18 years";
pres.author = "Suchitra Hole, Shivram Nekkanti, Andy Hannah";
// Fixed colors, so anyone can rebuild the deck with npm install alone.
const C = { text1: H.dk1, text2: H.dk2, background1: H.lt1, background2: H.lt2, accent1: H.accent1, accent2: H.accent2,
  accent3: H.accent3, accent4: H.accent4, accent5: H.accent5, accent6: H.accent6 };

const footer = { text: { text: "Federal contracting concentration, FY2008 to FY2025  |  EDA, October 2026",
  options: { x: 0.5, y: 5.25, w: 7.5, h: 0.25, fontSize: 9, color: C.text2 } } };
const slideNo = { x: 9.0, y: 5.25, w: 0.5, h: 0.25, fontSize: 9, color: C.text2, align: "right" };

pres.defineSlideMaster({
  title: "TITLE", background: { color: C.text1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.6, fontSize: 36,
    bold: true, color: C.background1, fontFace: THEME.headFontFace, valign: "bottom" }, text: "" } },
  { placeholder: { options: { name: "sub", type: "body", x: 0.6, y: 3.3, w: 8.8, h: 1.0, fontSize: 16,
    color: C.background2, valign: "top" }, text: "" } }],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: C.background1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontSize: 26,
    bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle" }, text: "" } }, footer],
  slideNumber: slideNo,
});
pres.defineSlideMaster({
  title: "BACKUP", background: { color: C.background2 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontSize: 22,
    bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle" }, text: "" } }, footer],
  slideNumber: slideNo,
});

const axis = {
  catAxisLabelColor: H.dk2, valAxisLabelColor: H.dk2, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", valGridLine: { color: "DDE1E7", size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false, legendFontSize: 10, legendColor: H.dk2, titleFontSize: 11, titleColor: H.dk2,
};

function stat(slide, x, y, w, value, label, color, name) {
  slide.addText(value, { x, y, w, h: 0.75, fontSize: 36, bold: true, color, fontFace: THEME.headFontFace, margin: 0,
    isTextBox: true, objectName: `${name} value` });
  slide.addText(label, { x, y: y + 0.75, w, h: 0.6, fontSize: 12, color: C.text2, margin: 0, valign: "top",
    isTextBox: true, objectName: `${name} label` });
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

// ------------------------------------------------------------------ 2. the project in one slide

{
  const s = content("Talk", MSG.project);
  const rows = spend.reduce((a, r) => a + num(r.rows), 0);
  const cells = v0.reduce((a, r) => a + num(r.cells), 0);   // as recorded, the count the integrity report gives
  stat(s, 0.5, 1.45, 2.0, `${(rows / 1e6).toFixed(1)}M`, "contract transactions, FY2008 to FY2025", C.accent1, "rows");
  stat(s, 0.5, 2.85, 2.0, `${Math.round(cells / 1000)}K`, "segments: one agency, one product code, one year", C.accent2, "segments");
  stat(s, 0.5, 4.0, 2.0, "0.2%", "largest gap to GAO's totals, FY2022 to FY2025", C.accent2, "gao");
  s.addText("HHI: the sum of each vendor's squared percentage share", { x: 3.0, y: 1.4, w: 6.5, h: 0.35, fontSize: 14,
    bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: "hhi heading" });
  const rowsHhi = [["Five equal vendors", [20, 20, 20, 20, 20], "2,000", "20² × 5", C.accent2],
                   ["One vendor with 80%", [80, 5, 5, 5, 5], "6,500", "80² + 5² × 4", C.accent1]];
  const barX = 3.0, barW = 4.4, shades = [C.accent3, C.accent6];
  rowsHhi.forEach(([label, shares, score, sum, color], r) => {
    const y = 2.05 + r * 1.15;
    s.addText(label, { x: barX, y: y - 0.32, w: barW, h: 0.28, fontSize: 12, color: C.text2, margin: 0, isTextBox: true,
      objectName: `hhi row ${r + 1} label` });
    let x = barX;
    shares.forEach((sh, k) => {
      const w = (barW * sh) / 100;
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.01, y, w: w - 0.02, h: 0.5, line: { type: "none" },
        fill: { color: k === 0 ? color : shades[k % 2] }, objectName: `hhi row ${r + 1} vendor ${k + 1}` });
      if (w >= 0.55) s.addText(`${sh}%`, { x, y, w, h: 0.5, fontSize: 11, bold: true, color: C.background1, align: "center",
        valign: "middle", margin: 0, isTextBox: true, objectName: `hhi row ${r + 1} share ${k + 1}` });
      x += w;
    });
    s.addText([{ text: score, options: { bold: true, fontSize: 22, color, breakLine: true } },
               { text: sum, options: { fontSize: 12, color: C.text2 } }],
      { x: 7.65, y: y - 0.12, w: 1.85, h: 0.8, margin: 0, valign: "middle", isTextBox: true, objectName: `hhi row ${r + 1} score` });
  });
  s.addText("Above 2,500 is highly concentrated under the 2010 merger guidelines.", { x: 3.0, y: 4.5, w: 6.5, h: 0.4,
    fontSize: 12, italic: true, color: C.text2, margin: 0, isTextBox: true, objectName: "hhi note" });
}

// ------------------------------------------------------------------ 3. concentration over 18 years

{
  const s = content("Talk", MSG.trend);
  const key = "above 2,500 pct of net";
  s.addChart(pres.charts.LINE, [
    { name: "As recorded (V0)", labels: years, values: v0.map((r) => num(r[key])) },
    { name: "Decisions as proposed (V1)", labels: years, values: v1.map((r) => num(r[key])) },
  ], { ...axis, x: 0.5, y: 1.3, w: 6.3, h: 3.75, chartColors: [H.accent3, H.accent1], lineSize: 2.5, lineDataSymbol: "none",
    valAxisMinVal: 0, valAxisLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true,
    title: "Share of each year's dollars in segments with HHI above 2,500", objectName: "trend chart" });
  stat(s, 7.1, 1.5, 2.4, pct(first[key]), `of dollars in FY${first.fiscal_year}`, C.accent2, "first year");
  stat(s, 7.1, 3.0, 2.4, pct(last[key]), `of dollars in FY${last.fiscal_year}`, C.accent1, "last year");
}

// ------------------------------------------------------------------ 4. the location of concentration

{
  const s = content("Talk", MSG.location);
  const pick = (rows, g, fy) => num((rows.find((r) => r.group === g && r.fiscal_year === fy) || {}).above_2500_pct_of_net);
  const groups = [["DoD", dodCiv, "DoD"], ["Civilian", dodCiv, "civilian"], ["Products", kind, "product"],
                  ["Services", kind, "service"], ["Research", kind, "research"]];
  s.addChart(pres.charts.BAR, [
    { name: `FY${first.fiscal_year}`, labels: groups.map((g) => g[0]), values: groups.map((g) => pick(g[1], g[2], first.fiscal_year)) },
    { name: `FY${last.fiscal_year}`, labels: groups.map((g) => g[0]), values: groups.map((g) => pick(g[1], g[2], last.fiscal_year)) },
  ], { ...axis, x: 0.5, y: 1.3, w: 6.0, h: 3.75, barDir: "col", chartColors: [H.accent3, H.accent1], valAxisMinVal: 0,
    valAxisLabelFormatCode: '0"%"', showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: H.dk2,
    dataLabelFormatCode: '0"%"', showLegend: true, legendPos: "b", showTitle: true, barGapWidthPct: 70,
    title: "Share of dollars in segments with HHI above 2,500", objectName: "location chart" });
  const cellsPct = (100 * num(last.one_positive_vendor_cells)) / num(last.cells);
  stat(s, 6.9, 1.5, 2.6, `${cellsPct.toFixed(0)}%`, `of FY${last.fiscal_year} segments have one vendor`, C.accent2, "single cells");
  stat(s, 6.9, 3.0, 2.6, pct(last.one_positive_vendor_pct_of_net, 1), "of that year's dollars sit in them", C.accent1, "single dollars");
}

// ------------------------------------------------------------------ 5. the product code problem

{
  const s = content("Talk", MSG.codes);
  const cw = 9.0 / 18;
  [["FY2008 to FY2011", "4 years", 0, 4, C.accent3], ["FY2012 to FY2020", "9 years", 4, 9, C.accent2],
   ["FY2021 to FY2025", "5 years", 13, 5, C.accent3]].forEach(([span, len, start, n, color], k) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5 + start * cw + 0.03, y: 1.45, w: n * cw - 0.06, h: 0.55, fill: { color },
      line: { type: "none" }, objectName: `era ${k + 1} bar` });
    s.addText([{ text: len, options: { bold: true, fontSize: 14, breakLine: true } }, { text: span, options: { fontSize: 10 } }],
      { x: 0.5 + start * cw, y: 1.45, w: n * cw, h: 0.55, color: C.background1, align: "center", valign: "middle", margin: 0,
        isTextBox: true, objectName: `era ${k + 1} label` });
  });
  s.addText("Product code manuals changed on 2011-10-01 and 2020-10-01. Codes that stopped at either change held almost no dollars.",
    { x: 0.5, y: 2.05, w: 9.0, h: 0.3, fontSize: 11, italic: true, color: C.text2, margin: 0, isTextBox: true, objectName: "era note" });
  const starts12 = brk12.find((r) => r.status === "starts") || {};
  const starts21 = brk21.find((r) => r.status === "starts") || {};
  const all3 = eras.find((r) => r.eras_present.split(" + ").length === 3) || {};
  stat(s, 0.5, 2.6, 2.8, pct(all3.pct_of_net, 1), "of all 18 years' dollars are on codes used in every era", C.accent2, "all eras");
  stat(s, 3.6, 2.6, 2.8, pct(starts12.pct_of_fy2012, 1), "of FY2012 dollars moved to codes new that year", C.accent1, "new 2012");
  stat(s, 6.7, 2.6, 2.8, pct(starts21.pct_of_fy2021, 1), "of FY2021 dollars moved to codes new that year", C.accent1, "new 2021");
  s.addText(MSG.codes.callout, { x: 0.5, y: 4.25, w: 9.0, h: 0.75, fontSize: 14, color: C.text1, margin: 0.1,
    fill: { color: C.background2 }, isTextBox: true, objectName: "codes callout" });
}

// ------------------------------------------------------------------ 6. what is next

{
  const s = content("Talk", MSG.next);
  const labels = noise.map((r) => `D${r.decile}`);
  s.addChart([
    { type: pres.charts.BAR, data: [{ name: "Median yearly change", labels, values: noise.map((r) => num(r.change_median)) },
             { name: "90th percentile", labels, values: noise.map((r) => num(r.change_p90)) }],
      options: { chartColors: [H.accent2, H.accent6], barGapWidthPct: 40 } },
    { type: pres.charts.LINE, data: [{ name: "500-point cutoff", labels, values: noise.map(() => 500) }],
      options: { chartColors: [H.accent1], lineSize: 2, lineDataSymbol: "none", lineDash: "dash" } },
  ], { ...axis, x: 0.5, y: 1.3, w: 5.4, h: 3.75, valAxisMinVal: 0, showLegend: true, legendPos: "b", showTitle: true,
    title: "Yearly change in HHI by segment size, smallest (D1) to largest (D10)", objectName: "noise chart" });
  const r500 = rising.find((r) => r.cutoff === "500") || {};
  stat(s, 6.2, 1.4, 1.6, pct(r500.rising_pct, 0), "of lines rise by 500 or more", C.accent1, "rising");
  stat(s, 7.9, 1.4, 1.6, pct(r500.rising_pct_after_shuffle, 0), "after shuffling their years", C.accent3, "shuffled");
  s.addText(MSG.next.decisions.map((d, i) => ({ text: d, options: { bullet: true, breakLine: i < MSG.next.decisions.length - 1 } })),
    { x: 6.2, y: 2.95, w: 3.3, h: 2.1, fontSize: 13, color: C.text1, paraSpaceAfter: 6, margin: 0, valign: "top",
      isTextBox: true, objectName: "next decisions" });
}

// ------------------------------------------------------------------ backup slides

pres.addSection({ title: "Backup" });
const backup = (msg) => {
  const s = pres.addSlide({ masterName: "BACKUP", sectionTitle: "Backup" });
  s.addText(msg.title, { placeholder: "title" });
  s.addNotes(msg.notes);
  if (msg.note) s.addText(msg.note, { x: 0.5, y: 4.45, w: 9.0, h: 0.7, fontSize: 12, color: C.text2, margin: 0, valign: "top",
    isTextBox: true, objectName: "backup note" });
  return s;
};
const head = (t) => ({ text: t, options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } });
const tableOpts = (x, y, w, colW) => ({ x, y, w, colW, fontSize: 11, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DAE1" },
  fill: { color: H.lt1 }, margin: 0.05, autoPage: false });

{
  const s = backup(MSG.backup_bands);
  const rows = [[head("Variant against V0"), head("Segments in both"), head("Change band"), head("Into above 2,500"), head("Out of above 2,500")]];
  for (const v of ["V1", "V8b"]) {
    const b = bands.filter((r) => r.variant === v);
    if (!b.length) { rows.push([v === "V1" ? "V1, decisions as proposed" : "V8b, V1 without J03 deobligations",
      { text: "Pending: needs the Stage 2 flags for every year", options: { colspan: 4, italic: true, color: H.dk2 } }]); continue; }
    const sum = (k) => b.reduce((a, r) => a + num(r[k]), 0);
    rows.push([v === "V1" ? "V1, decisions as proposed" : "V8b, V1 without J03 deobligations", count(sum("cells_in_both")),
      `${count(sum("cells_changing_band"))} (${((100 * sum("cells_changing_band")) / sum("cells_in_both")).toFixed(1)}%)`,
      count(sum("into_above_2500")), count(sum("out_of_above_2500"))]);
  }
  s.addTable(rows, tableOpts(0.5, 1.4, 9.0, [3.0, 1.5, 1.6, 1.45, 1.45]));
}
{
  const s = backup(MSG.backup_vendors);
  const rows = [[head("Rank"), head("Parent ID, by its name on the most dollars"), head("Net, FY2008 to FY2025")]];
  top.slice(0, 10).forEach((r) => rows.push([r.rank, r.name_most_dollars, big(r.net_all_years)]));
  s.addTable(rows, { ...tableOpts(0.5, 1.2, 9.0, [0.8, 6.0, 2.2]), fontSize: 10, rowH: 0.27 });
}
{
  const s = backup(MSG.backup_features);
  const pickYears = ["2008", "2012", "2018", "2025"];
  const cols = [["Sole source on the umbrella", "umbrella competition: sole_source pct"],
                ["Order field blank", "order competition: order_blank pct"],
                ["Set-aside field blank", "set-aside: set_aside_blank pct"],
                ["Offers reported, share of competed", "offers reported, pct of competed"]];
  const rows = [[head("Share of V1 dollars"), ...pickYears.map((y) => head(`FY${y}`))]];
  cols.forEach(([label, k]) => rows.push([label, ...pickYears.map((y) => pct((cover.find((r) => r.fiscal_year === y) || {})[k], 1))]));
  s.addTable(rows, tableOpts(0.5, 1.4, 9.0, [3.4, 1.4, 1.4, 1.4, 1.4]));
}

// ------------------------------------------------------------------ write

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log(`deck -> ${OUT}`);
})();
