// Builds the FY2025 column guide (Word + CSV) from colguide.json, optionally merged with a
// profile of real values computed from the dataset.
//
//   node build_column_guide.js --out <guide.docx> [--profile <profile.json>]
//
// colguide.json : 19 groups x 297 columns with meaning / verdict / why (written by hand).
// profile.json  : { "meta": {...}, "columns": { "<column>": {pct_filled, distinct, distinct_approx,
//                   kind, examples: [..], range} } }
// Writes <guide>.docx and <guide>.csv (same basename).

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LevelFormat,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, ExternalHyperlink,
  Footer, Header, PageNumber, PageOrientation,
} = require("docx");

// ---------- args ----------
const args = process.argv.slice(2);
function arg(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
}
const OUT = arg("--out");
const PROFILE = arg("--profile");
if (!OUT) {
  console.error("usage: node build_column_guide.js --out <guide.docx> [--profile <profile.json>]");
  process.exit(2);
}

// ---------- inputs ----------
const groups = JSON.parse(fs.readFileSync(path.join(__dirname, "colguide.json"), "utf8"));
const profile = PROFILE ? JSON.parse(fs.readFileSync(PROFILE, "utf8")) : null;
const meta = profile ? profile.meta || {} : null;
const prof = profile ? profile.columns || {} : {};

const all = groups.flatMap((g) => g.cols.map((c) => ({ ...c, group: g.name })));
if (all.length !== 297) throw new Error(`expected 297 columns in colguide.json, found ${all.length}`);
if (profile) {
  const missing = all.filter((c) => !prof[c.col]).map((c) => c.col);
  const extra = Object.keys(prof).filter((k) => !all.some((c) => c.col === k));
  if (missing.length) console.warn(`WARNING: profile has no entry for ${missing.length} columns: ${missing.join(", ")}`);
  if (extra.length) console.warn(`WARNING: profile has ${extra.length} columns not in the guide: ${extra.join(", ")}`);
}

const FONT = "Calibri";
const MONO = "Consolas";
const TEXT_W = 13680; // landscape Letter, 0.75" margins
const V = {
  Core: { color: "1E6B3A", fill: "E3F1E7" },
  Useful: { color: "1F4E99", fill: "E8EEF8" },
  Skip: { color: "6B6B6B", fill: null },
};
const LOW_FILL = 10; // percent

const tot = { Core: 0, Useful: 0, Skip: 0 };
all.forEach((c) => tot[c.verdict]++);
const usefulLabels = all.filter((c) => c.verdict === "Useful" && c.meaning.startsWith("Text label for")).length;

// ---------- formatting helpers ----------
function fmtInt(n) {
  return Number(n).toLocaleString("en-US");
}
function fmtPct(x) {
  if (x === null || x === undefined) return "";
  if (x > 0 && x < 0.1) return "<0.1%";
  if (x < 100 && x > 99.9) return ">99.9%";
  return `${Number(x).toFixed(1)}%`;
}
function fmtDistinct(n, approx) {
  if (n === null || n === undefined) return "";
  const a = approx ? "≈" : "";
  if (n >= 1e6) return `${a}${(n / 1e6).toFixed(1)}M values`;
  if (n >= 1e4) return `${a}${Math.round(n / 1e3)}K values`;
  return `${a}${fmtInt(n)} value${n === 1 ? "" : "s"}`;
}
function profileText(p) {
  if (!p) return null;
  if (p.kind === "withheld") return "Values withheld (personal or contact details).";
  if (p.kind === "blank" || !p.pct_filled) return "Blank in every FY2025 row.";
  let t = (p.examples || []).join("  ·  ");
  if (p.range) t += (t ? "  ·  " : "") + `Range: ${p.range}`;
  return t || null;
}

// ---------- docx helpers ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "C8C8C8" };
const borders = { top: border, bottom: border, left: border, right: border };

function runs(parts, base = {}) {
  return (Array.isArray(parts) ? parts : [parts]).map((x) =>
    typeof x === "string" ? new TextRun({ text: x, ...base }) : new TextRun({ ...base, ...x })
  );
}
function p(parts, opts = {}) {
  return new Paragraph({ children: runs(parts), spacing: { after: 120 }, ...opts });
}
function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [new TextRun(text)] });
}
function bullet(parts) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(parts), spacing: { after: 80 } });
}
function numbered(ref, parts) {
  return new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(parts), spacing: { after: 80 } });
}
function code(text, size = 19) {
  return { text, font: MONO, size, color: "333333" };
}
function link(text, url) {
  return new ExternalHyperlink({ link: url, children: [new TextRun({ text, color: "0563C1", underline: {} })] });
}
function cell(children, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill, color: "auto" } : undefined,
    children,
  });
}
function cp(parts, base = {}, opts = {}) {
  return new Paragraph({ children: runs(parts, { size: 18, ...base }), spacing: { after: 0 }, ...opts });
}
function headerRow(labels, widths) {
  return new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: labels.map((l, i) => cell([cp([{ text: l, bold: true }])], widths[i], { fill: "DCE6F2" })),
  });
}
function verdictCell(c, w) {
  const v = c.verdict;
  const kids = [cp([{ text: v, bold: v !== "Skip", color: V[v].color }])];
  const pr = prof[c.col];
  if (pr && pr.kind !== "withheld") {
    kids.push(cp([{ text: `${fmtPct(pr.pct_filled)} filled`, color: "595959", size: 15 }], {}, { spacing: { before: 40, after: 0 } }));
    if (pr.distinct !== undefined && pr.distinct !== null && pr.pct_filled)
      kids.push(cp([{ text: fmtDistinct(pr.distinct, pr.distinct_approx), color: "595959", size: 15 }]));
  } else if (pr && pr.kind === "withheld") {
    kids.push(cp([{ text: `${fmtPct(pr.pct_filled)} filled`, color: "595959", size: 15 }], {}, { spacing: { before: 40, after: 0 } }));
  }
  return cell(kids, w, { fill: V[v].fill });
}
function meaningCell(c, w) {
  const kids = [cp(c.meaning)];
  const t = profileText(prof[c.col]);
  if (t) {
    kids.push(
      cp([{ text: "In FY2025: ", bold: true, color: "595959", size: 16 }, { text: t, color: "404040", size: 16 }], {}, { spacing: { before: 60, after: 0 } })
    );
  }
  return cell(kids, w);
}

// ---------- at-a-glance table ----------
const GW = [7680, 1500, 1500, 1500, 1500];
const dash = "–";
const glanceTable = new Table({
  width: { size: TEXT_W, type: WidthType.DXA },
  columnWidths: GW,
  rows: [
    headerRow(["Group", "Columns", "Core", "Useful", "Skip"], GW),
    ...groups.map(
      (g) =>
        new TableRow({
          cantSplit: true,
          children: [
            cell([cp(g.name)], GW[0]),
            cell([cp(String(g.cols.length), {}, { alignment: AlignmentType.RIGHT })], GW[1]),
            cell([cp(g.counts.Core ? String(g.counts.Core) : dash, { color: V.Core.color, bold: !!g.counts.Core }, { alignment: AlignmentType.RIGHT })], GW[2]),
            cell([cp(g.counts.Useful ? String(g.counts.Useful) : dash, { color: V.Useful.color }, { alignment: AlignmentType.RIGHT })], GW[3]),
            cell([cp(g.counts.Skip ? String(g.counts.Skip) : dash, { color: V.Skip.color }, { alignment: AlignmentType.RIGHT })], GW[4]),
          ],
        })
    ),
    new TableRow({
      children: [
        cell([cp([{ text: "Total", bold: true }])], GW[0], { fill: "F2F2F2" }),
        cell([cp([{ text: String(all.length), bold: true }], {}, { alignment: AlignmentType.RIGHT })], GW[1], { fill: "F2F2F2" }),
        cell([cp([{ text: String(tot.Core), bold: true, color: V.Core.color }], {}, { alignment: AlignmentType.RIGHT })], GW[2], { fill: "F2F2F2" }),
        cell([cp([{ text: String(tot.Useful), bold: true, color: V.Useful.color }], {}, { alignment: AlignmentType.RIGHT })], GW[3], { fill: "F2F2F2" }),
        cell([cp([{ text: String(tot.Skip), bold: true, color: V.Skip.color }], {}, { alignment: AlignmentType.RIGHT })], GW[4], { fill: "F2F2F2" }),
      ],
    }),
  ],
});

// ---------- core table ----------
const coreCols = all.filter((c) => c.verdict === "Core").sort((a, b) => a.pos - b.pos);
const KW = profile ? [4000, 3300, 4980, 1400] : [4300, 3600, 5780];
const coreTable = new Table({
  width: { size: TEXT_W, type: WidthType.DXA },
  columnWidths: KW,
  rows: [
    headerRow(profile ? ["Column", "Group", "What it's for", "Filled"] : ["Column", "Group", "What it's for"], KW),
    ...coreCols.map((c) => {
      const kids = [cell([cp([code(c.col, 16)])], KW[0]), cell([cp(c.group)], KW[1]), cell([cp(c.why)], KW[2])];
      if (profile) kids.push(cell([cp(prof[c.col] ? fmtPct(prof[c.col].pct_filled) : "", {}, { alignment: AlignmentType.RIGHT })], KW[3]));
      return new TableRow({ cantSplit: true, children: kids });
    }),
  ],
});

// ---------- per-group tables ----------
const DW = [560, 3500, 4620, 1100, 3900];
function groupTable(g) {
  return new Table({
    width: { size: TEXT_W, type: WidthType.DXA },
    columnWidths: DW,
    rows: [
      headerRow(["#", "Column", profile ? "What it means, with FY2025 examples" : "What it means", "Verdict", "Why"], DW),
      ...g.cols.map(
        (c) =>
          new TableRow({
            cantSplit: true,
            children: [
              cell([cp(String(c.pos), { color: "7F7F7F" }, { alignment: AlignmentType.RIGHT })], DW[0]),
              cell([cp([code(c.col, 16)])], DW[1]),
              meaningCell(c, DW[2]),
              verdictCell(c, DW[3]),
              cell([cp(c.why)], DW[4]),
            ],
          })
      ),
    ],
  });
}
const groupSections = [];
groups.forEach((g, i) => {
  const n = g.cols.length;
  const parts = [];
  if (g.counts.Core) parts.push(`${g.counts.Core} core`);
  if (g.counts.Useful) parts.push(`${g.counts.Useful} useful`);
  if (g.counts.Skip) parts.push(`${g.counts.Skip} skip`);
  groupSections.push(h2(`${i + 1}. ${g.name}`));
  groupSections.push(
    new Paragraph({ keepNext: true, spacing: { after: 80 }, children: [new TextRun({ text: `${n} column${n === 1 ? "" : "s"}: ${parts.join(", ")}`, color: "7F7F7F", size: 19 })] })
  );
  groupSections.push(new Paragraph({ keepNext: true, spacing: { after: 120 }, children: [new TextRun(g.intro)] }));
  groupSections.push(groupTable(g));
});

// ---------- low-fill list (profile only) ----------
const lowFill = profile
  ? all.filter((c) => c.verdict !== "Skip" && prof[c.col] && prof[c.col].kind !== "withheld" && (prof[c.col].pct_filled || 0) < LOW_FILL).sort((a, b) => a.pos - b.pos)
  : [];

// ---------- body ----------
const dateLine = meta && meta.generated ? meta.generated : "October 2, 2026";
const children = [
  new Paragraph({ children: [new TextRun({ text: "FY2025 Contract File: Column Guide", bold: true, size: 40, color: "1F3864" })], spacing: { after: 80 } }),
  new Paragraph({
    children: [
      new TextRun({
        text: `All 297 columns in the USAspending Contracts Full archive, grouped, explained, and rated for the Federal Contracting Concentration capstone · ${dateLine}`,
        color: "595959",
        size: 21,
      }),
    ],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864", space: 6 } },
    spacing: { after: 240 },
  }),
  h1("Summary"),
  p([
    "Of the 297 columns, ",
    { text: `${tot.Core} are core`, bold: true, color: V.Core.color },
    ", ",
    { text: `${tot.Useful} are useful`, bold: true, color: V.Useful.color },
    ` (${usefulLabels} of those are text labels for codes), and `,
    { text: `${tot.Skip} can be skipped`, bold: true, color: V.Skip.color },
    ". The core columns are enough to build the concentration number and answer the pitch's three questions. The useful ones add robustness checks, hand-checks, and features for explaining the consolidating categories. Most of the skipped columns cover legal clauses, vendor ownership demographics, addresses, and entity types that don't bear on market share.",
    ...(meta
      ? [` Every column shows real examples and a fill rate from the FY2025 file itself (${fmtInt(meta.rows)} rows, data as of ${meta.data_as_of}).`]
      : []),
  ]),
  h1("How to read this"),
  bullet([{ text: "Core: ", bold: true, color: V.Core.color }, "needed to build the concentration number or to answer the pitch's questions directly."]),
  bullet([{ text: "Useful: ", bold: true, color: V.Useful.color }, "supports a robustness check, a hand-check of the top recipients, an RQ3 explanatory feature, or display."]),
  bullet([{ text: "Skip: ", bold: true, color: V.Skip.color }, "not needed for this project; the Why column says why."]),
  bullet([
    { text: "Code and label pairs. ", bold: true },
    "Many fields come as a code plus a text label. The rating goes on the code. Labels for kept codes are rated useful for display only; analyze on the code, because label wording can change across years.",
  ]),
  bullet([
    { text: "Ratings that depend on team decisions. ", bold: true },
    "The sub-agency code is core only if you measure below department level. The IDV flag and the umbrella-agreement fields matter because of the open decisions on IDV rows and on job-level versus umbrella-level measurement.",
  ]),
  ...(meta
    ? [
        bullet([
          { text: "Examples and fill rates. ", bold: true },
          `Computed from ${meta.source || "the FY2025 Parquet files"}. “Filled” is the share of all rows that are not blank. For codes and other columns with few distinct values, the examples are the most common values with their share of all rows. For IDs, names, amounts, dates, and free text, they are values from a fixed random sample of rows (seed ${meta.sample_seed}), with the range for dollar amounts and dates. Executive names and pay, and vendor street addresses and phone numbers, are withheld.`,
        ]),
        bullet([{ text: "Column names. ", bold: true }, meta.name_check || ""]),
      ]
    : [
        bullet([
          { text: "Where the column list came from. ", bold: true },
          "The list comes from USAspending's own download code (the contract-transaction column list in ",
          code("download_column_historical_lookups.py"),
          ", as of September 30, 2026), not from your ",
          code("reports/columns_fy2025.txt"),
          ". It produces exactly 297 columns, the same count as your file, and the # column gives each one's position in that list.",
        ]),
      ]),
  bullet([
    { text: "Definitions are plain-language summaries ", bold: true },
    "written from general knowledge of FPDS and USAspending, not copied from the official data dictionary. Check any you cite in the proposal (see the last section).",
  ]),
  h1("At a glance"),
  glanceTable,
  h1(`The ${tot.Core} core columns`),
  p("This is the minimum working set. It is close to the pilot's Layer B, minus the label columns and a few useful extras."),
  coreTable,
  h1("Columns by group"),
  p("Groups follow the order in which an analyst meets them: keys, money, time, buyer, vendor, contract structure, product, competition, then everything else. Within each group, columns are in file order."),
  ...groupSections,
  h1("Things to verify"),
];

if (meta) {
  if (lowFill.length) {
    children.push(
      numbered("verify", [
        { text: `Core or useful columns filled in under ${LOW_FILL}% of rows. `, bold: true },
        "Some are blank by design (for example, umbrella-only fields are blank on ordinary contracts, and order-only fields are blank on standalone contracts). Others may need their rating revisited. No ratings were changed automatically: ",
        ...lowFill.flatMap((c, i) => [code(c.col), ` (${fmtPct(prof[c.col].pct_filled)})${i < lowFill.length - 1 ? ", " : "."}`]),
      ])
    );
  } else {
    children.push(numbered("verify", [{ text: "Fill rates. ", bold: true }, `Every core and useful column is at least ${LOW_FILL}% filled.`]));
  }
} else {
  children.push(
    numbered("verify", [
      { text: "Match the names to your file. ", bold: true },
      "Compare ", code("reports/columns_fy2025.txt"), " with the column field of the companion CSV. They should match name for name and in order.",
    ]),
    numbered("verify", [
      { text: "Check fill rates before relying on a useful column. ", bold: true },
      "In particular: ", code("solicitation_date"), ", ", code("contract_bundling_code"), ", ", code("consolidated_contract_code"), ", ",
      code("program_acronym"), ", and ", code("dod_acquisition_program_code"), ". The viewer's group-by shows how often each is blank.",
    ])
  );
}
children.push(
  numbered("verify", [
    { text: "Confirm how extent_competed is coded on orders. ", bold: true },
    "I believe orders inherit it from their umbrella agreement, with fair_opportunity_limited_sources recording the order's own competition. Check this in the FPDS data dictionary, because it decides how the job-level and umbrella-level competition measures are built.",
  ]),
  numbered("verify", [
    { text: "Plan crosswalks for categories. ", bold: true },
    "The product and service code list and NAICS were both revised during 2008–2025, so categories need mapping before comparing years.",
  ]),
  numbered("verify", [
    { text: "Watch the parent IDs around 2022. ", bold: true },
    "The vendor ID switched from DUNS to UEI in April 2022, and the source of parent links changed with it. Once more years are downloaded, check whether parent coverage drops or jumps at that point.",
  ]),
  numbered("verify", [{ text: "Check definitions you cite. ", bold: true }, "Use USAspending's Data Dictionary for official wording."]),
  h1("Sources")
);
[
  ["usaspending-api: download_column_historical_lookups.py (contract transaction column list)", "https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/download/v2/download_column_historical_lookups.py"],
  ["USAspending Data Dictionary", "https://www.usaspending.gov/data-dictionary"],
  ["labordata/usaspending README (note on the August 2026 labor-standards column swap)", "https://github.com/labordata/usaspending"],
].forEach(([t, u]) => children.push(new Paragraph({ numbering: { reference: "sources", level: 0 }, children: [link(t, u)], spacing: { after: 60 } })));
children.push(
  new Paragraph({
    numbering: { reference: "sources", level: 0 },
    children: [new TextRun("Federal Contracting Concentration team pitch (project file), for the research questions the ratings are measured against")],
    spacing: { after: 60 },
  })
);
if (meta) {
  children.push(
    new Paragraph({
      numbering: { reference: "sources", level: 0 },
      children: [new TextRun(`FY2025 Contracts Full archive${meta.zip_file ? ` (${meta.zip_file})` : ""}, profiled locally for the examples and fill rates`)],
      spacing: { after: 60 },
    })
  );
}

// ---------- document ----------
const numLevel = (fmt, text) => ({ level: 0, format: fmt, text, alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } });
const doc = new Document({
  creator: "Andy Hannah",
  title: "FY2025 Contract File: Column Guide",
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 30, bold: true, color: "1F3864" }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 25, bold: true, color: "2E5597" }, paragraph: { spacing: { before: 320, after: 40 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [numLevel(LevelFormat.BULLET, "•")] },
      { reference: "verify", levels: [numLevel(LevelFormat.DECIMAL, "%1.")] },
      { reference: "sources", levels: [numLevel(LevelFormat.DECIMAL, "%1.")] },
    ],
  },
  sections: [
    {
      properties: { page: { size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "FY2025 Contract File: Column Guide", size: 16, color: "9A9A9A" })] })] }) },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Page ", size: 16, color: "7F7F7F" }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "7F7F7F" }),
                new TextRun({ text: " of ", size: 16, color: "7F7F7F" }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "7F7F7F" }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

// ---------- CSV ----------
function csvEsc(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
const csvHeader = ["position", "column", "group", "verdict", "what_it_means", "why"];
if (profile) csvHeader.push("pct_filled", "distinct_values", "distinct_is_approx", "examples", "range");
const csvRows = [...all].sort((a, b) => a.pos - b.pos).map((c) => {
  const r = [c.pos, c.col, c.group, c.verdict, c.meaning, c.why];
  if (profile) {
    const pr = prof[c.col] || {};
    const ex =
      pr.kind === "withheld" ? "withheld (personal or contact details)" : pr.kind === "blank" || !pr.pct_filled ? "blank in every row" : (pr.examples || []).join(" | ");
    r.push(pr.pct_filled ?? "", pr.distinct ?? "", pr.distinct_approx ? "yes" : "", ex, pr.range || "");
  }
  return r.map(csvEsc).join(",");
});
const csvPath = OUT.replace(/\.docx$/i, "") + ".csv";

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  fs.writeFileSync(csvPath, [csvHeader.join(","), ...csvRows].join("\n") + "\n");
  console.log(`wrote ${OUT} and ${csvPath}; core ${tot.Core}, useful ${tot.Useful}, skip ${tot.Skip}; profile: ${profile ? "yes" : "no"}; low-fill core/useful: ${lowFill.length}`);
});
