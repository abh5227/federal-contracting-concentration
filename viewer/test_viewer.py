"""Rerunnable checks for the data-health dashboard, through its HTTP API.

    .venv/bin/python -m viewer.test_viewer                    # checks + timings + headless-Chrome screenshots
    .venv/bin/python -m viewer.test_viewer --no-browser       # skip screenshots
    .venv/bin/python -m viewer.test_viewer --out /tmp/dash    # where screenshots / results.json go

Starts the dashboard on a free port on 127.0.0.1 and checks, among others:
  - totals by year (overview cards and the Rows page) equal the Stage 1 proof totals exactly;
  - every flag count the dashboard shows equals reports/integrity/flag_counts.csv;
  - a saved decision appears in the decisions file and no data file changed (the save goes to a copy of
    config/decisions.csv, so the real log is untouched by the test);
  - bad input is rejected with 400, foreign Host / Origin with 403, and the page loads nothing external.
Writes nothing in the repo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

import duckdb

from src import config, stage1, stage2
from src.report_pdf import find_chrome

from . import health
from .server import make_server

FLAG_COUNTS = config.INTEGRITY_REPORTS_DIR / "flag_counts.csv"


class Client:
    def __init__(self, base: str):
        self.base = base

    def req(self, path: str, params: dict | None = None, headers: dict | None = None, body: bytes | None = None,
            method: str = "GET"):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        r = urllib.request.Request(url, headers=headers or {}, data=body, method=method)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(r, timeout=600) as resp:
                out = resp.read(), resp.status, dict(resp.headers)
        except urllib.error.HTTPError as e:
            out = e.read(), e.code, dict(e.headers)
        return out[1], out[0], out[2], round((time.perf_counter() - t0) * 1000, 1)

    def json(self, path: str, params: dict | None = None):
        s, body, _, ms = self.req(path, params)
        return s, json.loads(body, parse_float=Decimal), ms


class Results:
    def __init__(self):
        self.rows = []

    def add(self, name: str, ok: bool, detail: str):
        self.rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)

    @property
    def failed(self) -> int:
        return sum(r["status"] == "FAIL" for r in self.rows)


def data_fingerprint() -> str:
    """Name, size and mtime of every Stage 0 zip, Stage 1 file and Stage 2 row-flag file: changes if any is written."""
    paths = sorted([*config.RELEASE_DIR.glob("*.zip"), *config.PARQUET_DIR.glob("layer_a/fy*/*/*"),
                    *(config.INTEGRITY_DIR / "row_flags").glob("*.parquet")])
    h = hashlib.sha256()
    for p in paths:
        st = p.stat()
        h.update(f"{p}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return f"{len(paths)} files, {h.hexdigest()[:16]}"


def proof_totals() -> dict[int, tuple[int, Decimal]]:
    out = {}
    for fy in stage2.present_years():          # proven in Stage 1 and profiled in Stage 2 (what the dashboard shows)
        ms = stage1.load_progress(fy)["members"].values()
        out[fy] = (sum(m["raw_records"] for m in ms), sum(Decimal(m["raw_dollars"]) for m in ms))
    return out


def run_checks(c: Client, res: Results, hdb) -> None:
    proof = proof_totals()
    g_all = json.dumps({"fy": [config.FIRST_FY, config.LAST_FY]})

    # 1. Overview cards: per-year totals = Stage 1 proof
    s, ov, ms = c.json("/api/h/overview", {"g": g_all})
    bad = []
    for card in ov["cards"]:
        fy = card["fiscal_year"]
        if card["status"] == "pending":
            if fy not in config.years_pending():
                bad.append(f"FY{fy} pending but present")
            continue
        if fy not in proof:                      # in Stage 0 but not yet profiled (partial run)
            continue
        n, net = proof[fy]
        if card["rows"] != n or Decimal(card["net"]) != net or card["proof"] != "PASS":
            bad.append(f"FY{fy}: {card['rows']}/{card['net']} vs {n}/{net}")
    res.add("overview: totals by year = Stage 1 proof", s == 200 and not bad,
            f"{len(ov['cards'])} cards; pending shown as pending: {[c_['fiscal_year'] for c_ in ov['cards'] if c_['status'] == 'pending']}; "
            f"mismatches: {bad[:3]}; {ms:.0f} ms")

    # 2. Rows page totals: each year and all years = proof (independent of the summaries)
    for fy in (min(proof), max(proof)):
        s, t, ms = c.json("/api/totals", {"g": json.dumps({"fy": [fy, fy]})})
        res.add(f"rows page FY{fy} totals = Stage 1 proof", s == 200 and t["rows"] == proof[fy][0]
                and Decimal(t["net"]) == proof[fy][1] and t["matches_reference"] is True,
                f"{t['rows']:,} rows, {t['net']} ({ms:.0f} ms)")
    s, t, ms = c.json("/api/totals", {"g": g_all})
    all_n, all_net = sum(v[0] for v in proof.values()), sum((v[1] for v in proof.values()), Decimal(0))
    res.add("rows page all years totals = Stage 1 proof", s == 200 and t["rows"] == all_n and Decimal(t["net"]) == all_net,
            f"{t['rows']:,} rows, {t['net']} (proof {all_n:,}, {all_net}); {ms:.0f} ms")
    # Totals without row filters come from Stage 2's keys_dims; a row filter sends them through Layer A instead.
    # A filter every row passes (fiscal_year >= the first year) checks that second path against the proof too.
    s, t, ms = c.json("/api/totals", {"g": g_all, "f": json.dumps([["fiscal_year", "min", str(min(proof))]])})
    res.add("rows page all years totals via Layer A (row-filter path) = Stage 1 proof",
            s == 200 and t["rows"] == all_n and Decimal(t["net"]) == all_net and "FROM a " in t["sql"],
            f"{t['rows']:,} rows, {t['net']}; {ms:.0f} ms")

    # 3. Every flag count on the dashboard = flag_counts.csv
    s, fl, ms = c.json("/api/h/flags", {"g": g_all})
    want = {}
    for r in csv.DictReader(open(FLAG_COUNTS, encoding="utf-8")):
        if r["count"] not in ("", None):
            want[(r["flag_id"], int(r["fiscal_year"]))] = int(r["count"])
    got = {(f["flag_id"], int(y)): v["count"] for f in fl["flags"] for y, v in f["by_year"].items()}
    diffs = [(k, got.get(k), v) for k, v in want.items() if got.get(k, 0) != v]
    extra = [k for k in got if k not in want and got[k]]
    res.add("flags page counts = flag_counts.csv", s == 200 and not diffs and not extra,
            f"{len(want)} flag-year counts compared; differences: {diffs[:3]} extra: {extra[:3]}; {ms:.0f} ms")

    # 4. Overview flag cards add up to the flag cube
    sev = {f["flag_id"]: f["severity"] for f in hdb.catalog}
    by = {}
    for (fid, fy), n in want.items():
        if any(f["flag_id"] == fid and f["level"] == "row" for f in hdb.catalog):
            by.setdefault(fy, {"serious": 0, "review": 0, "info": 0})[sev[fid]] += n
    mism = [card["fiscal_year"] for card in ov["cards"] if card["status"] == "present" and card["flags"] != by.get(card["fiscal_year"], card["flags"])]
    res.add("overview flag counts by severity = flag_counts.csv", not mism, f"years differing: {mism}")

    # 5. A filter applies consistently: agency 097 cards = Rows page totals for 097
    g97 = json.dumps({"fy": [config.FIRST_FY, config.LAST_FY], "agency": ["097"]})
    s1, ov97, _ = c.json("/api/h/overview", {"g": g97})
    s2, t97, ms = c.json("/api/totals", {"g": g97})
    card_n = sum(x.get("rows", 0) for x in ov97["cards"])
    card_net = sum((Decimal(x["net"]) for x in ov97["cards"] if x.get("net")), Decimal(0))
    res.add("agency filter: overview = rows page", s1 == s2 == 200 and card_n == t97["rows"] and card_net == Decimal(t97["net"]),
            f"agency 097: {card_n:,} rows / {card_net} vs {t97['rows']:,} / {t97['net']}; {ms:.0f} ms")

    # 6. Column-quality cube = column profile (blank counts, unfiltered)
    s, cq, ms = c.json("/api/h/columns", {"g": g_all, "metric": "blank"})
    con = duckdb.connect()
    prof = {(col, fy): b for col, fy, b in con.execute(
        "SELECT column_name, fiscal_year, blank FROM read_parquet(?)",
        [[str(p) for p in sorted(config.INTEGRITY_DIR.glob("fy*/column_profile.parquet"))]]).fetchall()}
    cq_bad = [(col["name"], y) for col in cq["columns"] for y, cell in col["cells"].items() if prof.get((col["name"], int(y))) != cell["count"]]
    res.add("column quality page = column profile", s == 200 and not cq_bad, f"{len(prof)} column-years; differences {cq_bad[:3]}; {ms:.0f} ms")

    # 7. Rows: pages disjoint; page contents = independent query
    gy = json.dumps({"fy": [max(proof), max(proof)]})
    s1, p1, _ = c.json("/api/rows", {"g": gy, "page": "1"})
    s2, p2, _ = c.json("/api/rows", {"g": gy, "page": "2"})
    k1, k2 = {k[0] for k in p1["keys"]}, {k[0] for k in p2["keys"]}
    res.add("rows pages 1 and 2 disjoint", s1 == s2 == 200 and len(k1) == len(k2) == 100 and not k1 & k2, f"overlap {len(k1 & k2)}")
    files = stage1.layer_a_files(max(proof))
    direct = duckdb.connect().execute(
        f"""SELECT contract_transaction_unique_key FROM read_parquet({[str(p) for p in files]!r}) WHERE awarding_agency_code = '036'
            ORDER BY recipient_name ASC NULLS LAST, contract_transaction_unique_key ASC LIMIT 100 OFFSET 100""").fetchall()
    s, r, _ = c.json("/api/rows", {"g": gy, "f": json.dumps([["awarding_agency_code", "is", "036"]]), "sort": "recipient_name",
                                   "dir": "asc", "page": "2"})
    # Two empty lists are equal, so the check also needs keys on both sides: an empty page proves nothing.
    res.add("rows page contents = independent query", s == 200 and len(direct) > 0 and
            [k[0] for k in r["keys"]] == [d[0] for d in direct], f"{len(r['keys'])} keys compared, {len(direct)} expected")

    # 8. Flag click-through: rows with flag J02 = flag_counts.csv J02 total (0 = 0 would prove nothing, so J02 must fire)
    j02 = sum(v for (f, _), v in want.items() if f == "J02")
    s, t, ms = c.json("/api/totals", {"g": g_all, "flag": "J02"})
    res.add("flag filter J02 rows = flag_counts.csv", s == 200 and j02 > 0 and t["rows"] == j02,
            f"{t['rows']:,} vs {j02:,}{'' if j02 else ' (no J02 rows to compare)'}; {ms:.0f} ms")

    # 9. Decision save: appears in the decisions file; data unchanged
    before = data_fingerprint()
    body = json.dumps({"target_type": "flag", "target": "J02", "status": "investigate", "scope": "test",
                       "rationale": "dashboard test - safe to ignore", "decided_by": "viewer.test_viewer", "decided_date": ""}).encode()
    origin = c.base
    s, out, _, _ = c.req("/api/h/decisions", headers={"Content-Type": "application/json", "Origin": origin}, body=body, method="POST")
    saved = json.loads(out)
    rows = list(csv.DictReader(open(health.DECISIONS, encoding="utf-8")))
    after = data_fingerprint()
    res.add("decision saved to decisions file", s == 200 and any(r["decision_id"] == saved.get("decision_id") and r["status"] == "investigate" for r in rows),
            f"{saved.get('decision_id')} in {health.DECISIONS.name} ({len(rows)} rows)")
    res.add("data unchanged by saving a decision", before == after, f"before {before} / after {after}")
    s, _, _, _ = c.req("/api/h/decisions", headers={"Content-Type": "application/json", "Origin": "http://evil.example"}, body=body, method="POST")
    res.add("decision POST from another origin refused", s == 403, f"HTTP {s}")
    bad_body = json.dumps({"target_type": "flag", "target": "ZZZ", "status": "deleted", "decided_by": "x"}).encode()
    s, _, _, _ = c.req("/api/h/decisions", headers={"Content-Type": "application/json", "Origin": origin}, body=bad_body, method="POST")
    res.add("invalid decision rejected", s == 400, f"HTTP {s}")

    # 10. Glossary: every row of config/glossary.csv is served; search and category match an independent filter of the CSV
    gl = list(csv.DictReader(open(config.GLOSSARY_CSV, encoding="utf-8"))) if config.GLOSSARY_CSV.exists() else []
    s, d, ms = c.json("/api/h/glossary")
    res.add("glossary: every term served", s == 200 and d["total"] == len(gl) and len(gl) > 0
            and sorted(t["term"] for t in d["terms"]) == sorted(g["term"] for g in gl),
            f"{len(d['terms'])} served, {len(gl)} in {config.GLOSSARY_CSV.name}; {ms:.0f} ms")
    word = "obligation"
    want = sorted(g["term"] for g in gl if word in " ".join((g["term"], g["also_called"], g["plain_summary"])).lower())
    s, d, _ = c.json("/api/h/glossary", {"q": word.upper()})
    res.add("glossary: search = independent filter", s == 200 and bool(want) and sorted(t["term"] for t in d["terms"]) == want,
            f"{len(d['terms'])} terms match {word!r} (expected {len(want)})")
    cat = "Money"
    want = sorted(g["term"] for g in gl if g["category"] == cat)
    s, d, _ = c.json("/api/h/glossary", {"category": cat})
    res.add("glossary: category filter = independent filter", s == 200 and bool(want) and sorted(t["term"] for t in d["terms"]) == want,
            f"{len(d['terms'])} terms in {cat!r} (expected {len(want)})")
    links = [u for t in c.json("/api/h/glossary")[1]["terms"] for u in (t["source_url"], t["learn_more_url"]) if u]
    res.add("glossary: source links are https", bool(links) and all(u.startswith("https://") for u in links),
            f"{len(links)} links; not https: {[u for u in links if not u.startswith('https://')][:2]}")

    # 11. Bad input and local-only safeguards
    bad = [("unknown agency", "/api/h/overview", {"g": json.dumps({"agency": ["'; DROP TABLE x; --"]})}),
           ("bad fy range", "/api/h/flags", {"g": json.dumps({"fy": [1999, 2030]})}),
           ("unknown column", "/api/h/column", {"name": "nope"}),
           ("unknown filter column", "/api/totals", {"f": json.dumps([['x"; DROP', "eq", "1"]])}),
           ("unknown flag", "/api/totals", {"flag": "Z99"}),
           ("bad metric", "/api/h/columns", {"metric": "evil"}),
           ("unknown glossary category", "/api/h/glossary", {"category": "x\"; DROP"})]
    for label, path, params in bad:
        s, body, _, _ = c.req(path, params)
        res.add(f"rejected with 400: {label}", s == 400, f"HTTP {s}: {json.loads(body).get('error', '')[:60]}")
    s, _, _, _ = c.req("/api/h/meta", headers={"Host": "evil.example:80"})
    res.add("foreign Host header refused", s == 403, f"HTTP {s}")
    s, body, hdr, _ = c.req("/")
    static = body.decode() + c.req("/static/app.js")[1].decode() + c.req("/static/app.css")[1].decode()
    external = [w for w in static.split() if ("http://" in w or "https://" in w) and "127.0.0.1" not in w and "/^https?" not in w]
    res.add("page loads nothing external", not external and "default-src 'self'" in hdr.get("Content-Security-Policy", ""),
            f"external URLs in assets: {external[:3]}")


def run_timings(c: Client) -> list[dict]:
    out = []
    g_all = json.dumps({"fy": [config.FIRST_FY, config.LAST_FY]})
    calls = [("overview (all years)", "/api/h/overview", {"g": g_all}),
             ("completeness (all years)", "/api/h/completeness", {"g": g_all}),
             ("column quality, blank (all years)", "/api/h/columns", {"g": g_all, "metric": "blank"}),
             ("column quality, agency 097", "/api/h/columns", {"g": json.dumps({"agency": ["097"]}), "metric": "placeholder"}),
             ("flags (all years)", "/api/h/flags", {"g": g_all}),
             ("rows page 1 (all years)", "/api/rows", {"g": g_all}),
             ("rows totals (all years)", "/api/totals", {"g": json.dumps({"fy": [2009, 2025]})}),
             ("rows totals with a row filter (Layer A), all years", "/api/totals",
              {"g": g_all, "f": json.dumps([["recipient_name", "contains", "boeing"]])}),
             ("rows page 1, one year", "/api/rows", {"g": json.dumps({"fy": [2020, 2020]})}),
             ("rows contains 'lockheed', all years", "/api/rows", {"g": g_all, "f": json.dumps([["recipient_name", "contains", "lockheed"]])}),
             ("group-by awarding agency, all years", "/api/groupby", {"g": g_all, "gb": "awarding_agency_code"}),
             ("rows with flag J04, all years", "/api/rows", {"g": g_all, "flag": "J04"})]
    for label, path, params in calls:
        s, body, _, ms = c.req(path, params)
        out.append({"what": label, "http_status": s, "round_trip_ms": ms})
        print(f"  {ms:8.0f} ms  {label}  (HTTP {s})", flush=True)
    return out


def run_render(base: str, out_dir: Path) -> list[dict]:
    chrome = find_chrome()
    if chrome is None:
        return [{"check": "render", "status": "SKIP", "detail": "Chrome not found (set CHROME_PATH to its program file)"}]
    results = []
    # Each expected text is produced only by app.js (never in index.html), so it proves the page rendered.
    views = [("overview", "/", "What jumps off the page"), ("completeness", "/?view=completeness", "Month × year"),
             ("columns", "/?view=columns", "Column × year"), ("flags", "/?view=flags", "Every flag"),
             ("rows", "/?view=rows", "Matching rows"), ("decisions", "/?view=decisions", "Record a decision"),
             ("glossary", "/?view=glossary", "terms this project uses")]
    profile = Path(tempfile.mkdtemp(prefix="dash_chrome_"))
    flags = ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
             "--disable-component-update", "--disable-sync", "--disable-extensions", "--disable-default-apps",
             f"--user-data-dir={profile}", "--window-size=1600,1300", "--virtual-time-budget=60000"]
    try:
        for name, path, expect in views:
            png = out_dir / f"dashboard_{name}.png"
            subprocess.run([str(chrome), *flags, f"--screenshot={png}", base + path], capture_output=True, timeout=300)
            dom = subprocess.run([str(chrome), *flags, "--dump-dom", base + path], capture_output=True, timeout=300, text=True).stdout
            ok = (png.exists() and png.stat().st_size > 10_000 and expect in dom and "Error:" not in dom
                  and "FY2008" in dom)                       # the global filter lists were filled by the script
            results.append({"check": f"render: {name}", "status": "PASS" if ok else "FAIL",
                            "detail": f"{png} ({png.stat().st_size // 1024 if png.exists() else 0} KB); contains {expect!r}: {expect in dom}"})
            print(f"  {results[-1]['status']}  render {name}: {results[-1]['detail']}", flush=True)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args(argv)
    t0 = time.perf_counter()
    try:
        server, hdb, _ = make_server(0, quiet=True)
    except health.NoData as e:                      # a fresh clone: nothing to check yet, which is not a failure
        print(f"SKIPPED: every dashboard check, because there is no data to check. {e}")
        return 0
    out_dir = a.out or Path(tempfile.mkdtemp(prefix="dashboard_test_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    # Decisions go to a copy, so the test never touches the team's real log. The server reads the
    # module-level path only when a decision is saved, so switching it here, before serving, is enough.
    tmp_dec = out_dir / "decisions_copy.csv"
    if health.DECISIONS.exists():
        shutil.copy(health.DECISIONS, tmp_dec)
    health.DECISIONS = tmp_dec
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Dashboard started for testing at {base} in {time.perf_counter() - t0:.1f}s\n")
    c = Client(base)
    try:
        print("Timings:")
        timings = run_timings(c)
        print("\nChecks:")
        res = Results()
        run_checks(c, res, hdb)
        print("\nRendering:")
        render = [] if a.no_browser else run_render(base, out_dir)
    finally:
        server.shutdown()
        server.server_close()
    failed = res.failed + sum(r["status"] == "FAIL" for r in render)
    (out_dir / "results.json").write_text(json.dumps({"checks": res.rows, "render": render, "timings": timings,
                                                       "failed": failed}, indent=1), encoding="utf-8")
    print(f"\n{len(res.rows) - res.failed}/{len(res.rows)} API checks passed; render: "
          f"{', '.join(r['status'] for r in render) or 'skipped'}. Results: {out_dir / 'results.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
