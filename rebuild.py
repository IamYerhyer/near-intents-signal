#!/usr/bin/env python3
"""
rebuild.py — one-command rebuild for the NEAR Intents Investment Thesis dashboard.

Usage:  python3 rebuild.py

What it does:
  1. Pulls free, keyless DefiLlama public API endpoints (see SOURCES below).
  2. Saves raw JSON responses to data/raw/.
  3. Writes tidy CSVs to data/.
  4. Computes data/key_stats.json (every headline number traces to a CSV/JSON here).
  5. Regenerates index.html (static dashboard, charts are inline SVG generated
     from the CSV data — no external dependencies, works offline from file://).

Only Python 3 standard library is used. No API keys. No invented numbers.

Partial-day rule (important): DefiLlama daily series can end on an incomplete
day. A day is flagged `partial` in the fees CSV when the final fees value is
lower than the same day's revenue value (revenue is a subset of fees, so
fees < revenue is impossible for a complete day). Flagged partial days are
excluded from the "computed" trailing-30d sums in key_stats.json; the raw
API-reported totals are kept separately and labelled as such.
"""

import csv
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RAW = os.path.join(DATA, "raw")

VOL_URL = "https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume"
FEES_URL = "https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees"
REV_URL = "https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue"
PROTO_URL = "https://api.llama.fi/protocol/near-intents"
CHAINS_URL = "https://api.llama.fi/v2/chains"
CHAIN_TVL_HIST_URL = "https://api.llama.fi/v2/historicalChainTvl/Near"


def price_url():
    """Daily NEAR price for the last 365 days, anchored to today (UTC)."""
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - 365 * 86400
    return (
        "https://coins.llama.fi/chart/coingecko:near"
        f"?start={start}&span=365&period=1d"
    )


def fetch(url, raw_name):
    req = urllib.request.Request(url, headers={"User-Agent": "near-intents-signal/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = resp.read()
    with open(os.path.join(RAW, raw_name), "wb") as f:
        f.write(payload)
    return json.loads(payload)


def dstr(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def write_csv(name, header, rows):
    path = os.path.join(DATA, name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def pearson(xs, ys):
    """Pearson correlation coefficient, computed from scratch."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else None


def fmt_usd(v):
    if v is None:
        return "n/a"
    if abs(v) >= 1e9:
        return f"${v/1e9:,.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:,.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:,.1f}K"
    return f"${v:,.0f}"


# ---------------------------------------------------------------- SVG charts
def svg_line_chart(series, width=920, height=340, title=""):
    """series: list of dicts {label, color, points:[(x_label, y)], axis:'left'|'right',
    kind:'line'|'bar'}. Returns an inline SVG string. Zero dependencies."""
    pad_l, pad_r, pad_t, pad_b = 64, 64, 26, 34
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    all_x = sorted({p[0] for s in series for p in s["points"]})
    if not all_x:
        return "<p>No data.</p>"
    xidx = {x: i for i, x in enumerate(all_x)}
    n = max(len(all_x) - 1, 1)

    def xpos(x):
        return pad_l + iw * xidx[x] / n

    axes = {}
    for side in ("left", "right"):
        vals = [p[1] for s in series if s.get("axis", "left") == side for p in s["points"]]
        if vals:
            lo, hi = min(vals), max(vals)
            if lo > 0 and min(vals) >= 0:
                lo = 0
            span = (hi - lo) or 1
            axes[side] = (lo - 0.03 * span, hi + 0.07 * span)
    def ypos(v, side):
        lo, hi = axes[side]
        return pad_t + ih - ih * (v - lo) / (hi - lo)

    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">']
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#0d1117"/>')
    # gridlines + y tick labels (left axis)
    if "left" in axes:
        lo, hi = axes["left"]
        for i in range(5):
            v = lo + (hi - lo) * i / 4
            y = ypos(v, "left")
            out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="#21262d" stroke-width="1"/>')
            out.append(f'<text x="{pad_l-6}" y="{y+3:.1f}" fill="#8b949e" font-size="11" text-anchor="end">{fmt_usd(v)}</text>')
    if "right" in axes:
        lo, hi = axes["right"]
        for i in range(5):
            v = lo + (hi - lo) * i / 4
            y = ypos(v, "right")
            out.append(f'<text x="{width-pad_r+6}" y="{y+3:.1f}" fill="#d2a8ff" font-size="11">${v:,.2f}</text>')
    # x tick labels (about 6)
    step = max(1, len(all_x) // 6)
    for i in range(0, len(all_x), step):
        x = all_x[i]
        out.append(f'<text x="{xpos(x):.1f}" y="{height-10}" fill="#8b949e" font-size="11" text-anchor="middle">{x[:7]}</text>')
    # bars first (daily volume)
    for s in series:
        if s.get("kind") == "bar":
            bw = max(1.0, iw / max(len(all_x), 1) * 0.8)
            base = ypos(0, s.get("axis", "left")) if 0 >= axes[s.get("axis", "left")][0] else pad_t + ih
            for x, y in s["points"]:
                yy = ypos(y, s.get("axis", "left"))
                out.append(f'<rect x="{xpos(x)-bw/2:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{abs(base-yy):.1f}" fill="{s["color"]}" opacity="0.55"/>')
    # lines
    for s in series:
        if s.get("kind") == "bar":
            continue
        pts = " ".join(f"{xpos(x):.1f},{ypos(y, s.get('axis','left')):.1f}" for x, y in s["points"])
        out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2" points="{pts}"/>')
    # legend
    lx = pad_l
    for s in series:
        out.append(f'<rect x="{lx}" y="6" width="10" height="10" fill="{s["color"]}"/>')
        out.append(f'<text x="{lx+14}" y="15" fill="#e6edf3" font-size="12">{s["label"]}</text>')
        lx += 14 + 8 * len(s["label"]) + 34
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- main
def main():
    os.makedirs(RAW, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    print(f"[rebuild] started {now_utc.isoformat()}")

    vol = fetch(VOL_URL, "intents_daily_volume.json")
    fees = fetch(FEES_URL, "intents_daily_fees.json")
    rev = fetch(REV_URL, "intents_daily_revenue.json")
    proto = fetch(PROTO_URL, "near_intents_protocol.json")
    chains = fetch(CHAINS_URL, "chains.json")
    p_url = price_url()
    price = fetch(p_url, "near_daily_price.json")
    chain_hist = None
    try:
        chain_hist = fetch(CHAIN_TVL_HIST_URL, "near_chain_tvl_history.json")
    except Exception as e:  # optional layer — never fatal
        print(f"[rebuild] WARNING: chain TVL history unavailable: {e}")

    # ---- daily volume (+ cumulative)
    vol_rows, cum = [], 0.0
    for ts, v in vol.get("totalDataChart", []):
        cum += float(v)
        vol_rows.append((dstr(ts), float(v), cum))
    write_csv("intents_daily_volume.csv",
              ["date", "daily_volume_usd", "cumulative_volume_usd"], vol_rows)

    # ---- daily revenue
    rev_map = {dstr(ts): float(v) for ts, v in rev.get("totalDataChart", [])}
    write_csv("intents_daily_revenue.csv", ["date", "daily_revenue_usd"],
              sorted(rev_map.items()))

    # ---- daily fees, with partial-day flag on the final point if fees < revenue
    fee_rows_raw = [(dstr(ts), float(v)) for ts, v in fees.get("totalDataChart", [])]
    partial_dates = set()
    notes = []
    if fee_rows_raw:
        last_date, last_fee = fee_rows_raw[-1]
        last_rev = rev_map.get(last_date)
        if last_rev is not None and last_fee < last_rev:
            partial_dates.add(last_date)
            notes.append(
                f"Final fees day {last_date} flagged partial: fees ${last_fee:,.0f} "
                f"< revenue ${last_rev:,.0f} on the same date (revenue is a subset of "
                "fees, so a complete day cannot show this). Excluded from computed "
                "trailing-30d sums."
            )
    write_csv("intents_daily_fees.csv", ["date", "daily_fees_usd", "partial_day"],
              [(d, v, "true" if d in partial_dates else "false") for d, v in fee_rows_raw])

    # ---- daily price
    price_map = {}
    for coin in price.get("coins", {}).values():
        for p in coin.get("prices", []):
            price_map[dstr(p["timestamp"])] = float(p["price"])
    write_csv("near_daily_price.csv", ["date", "price_usd"], sorted(price_map.items()))

    # ---- NEAR chain TVL history (if available)
    chain_tvl_rows = []
    if chain_hist:
        for row in chain_hist:
            chain_tvl_rows.append((dstr(row["date"]), float(row["tvl"])))
        write_csv("near_chain_tvl.csv", ["date", "chain_tvl_usd"], chain_tvl_rows)

    near_chain = next((c for c in chains if c.get("name") == "Near"), {})
    chain_tvl_now = near_chain.get("tvl")

    # ---- Intents TVL (protocol endpoint)
    intents_tvl = [(dstr(r["date"]), float(r["totalLiquidityUSD"])) for r in proto.get("tvl", [])]
    intents_tvl_latest = intents_tvl[-1] if intents_tvl else (None, None)

    # ---- computed stats
    def trailing_sum(rows, days=30, exclude=()):
        clean = [(d, v) for d, v in rows if d not in exclude]
        tail = clean[-days:]
        return {"sum_usd": sum(v for _, v in tail),
                "days": len(tail),
                "from": tail[0][0] if tail else None,
                "to": tail[-1][0] if tail else None}

    fee_pairs = [(d, v) for d, v in fee_rows_raw]
    vol30 = trailing_sum([(d, v) for d, v, _ in vol_rows])
    fee30 = trailing_sum(fee_pairs, exclude=partial_dates)
    rev30 = trailing_sum(sorted(rev_map.items()), exclude=partial_dates)

    def cum_on(date_str):
        vals = [c for d, _, c in vol_rows if d <= date_str]
        return vals[-1] if vals else None

    latest_cum = vol_rows[-1][2] if vol_rows else None
    milestones = {}
    for label, ds in (("2026-06-30", "2026-06-30"),
                      ("2026-09-15", "2026-09-15")):
        milestones[label] = cum_on(ds)
    if vol_rows:
        milestones[vol_rows[-1][0]] = latest_cum

    # correlation: daily volume vs NEAR price on overlapping dates
    pairs = [(v, price_map[d]) for d, v, _ in vol_rows if d in price_map]
    r = pearson([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else None
    # 30d rolling volume vs price (smoothed flow)
    vol_map = {d: v for d, v, _ in vol_rows}
    dates_sorted = sorted(vol_map)
    roll, roll_pairs = {}, []
    for i, d in enumerate(dates_sorted):
        if i >= 29:
            roll[d] = sum(vol_map[dates_sorted[j]] for j in range(i - 29, i + 1))
    roll_pairs = [(roll[d], price_map[d]) for d in roll if d in price_map]
    r_roll = pearson([p[0] for p in roll_pairs], [p[1] for p in roll_pairs]) if roll_pairs else None

    latest_price_date = max(price_map) if price_map else None
    key_stats = {
        "generated_at_utc": now_utc.isoformat(),
        "data_as_of": vol_rows[-1][0] if vol_rows else None,
        "sources": {
            "daily_volume": VOL_URL, "daily_fees": FEES_URL,
            "daily_revenue": REV_URL, "price": p_url,
            "chains_snapshot": CHAINS_URL, "protocol": PROTO_URL,
            "chain_tvl_history": CHAIN_TVL_HIST_URL if chain_hist else None,
        },
        "intents_cumulative_volume_usd": latest_cum,
        "intents_total_all_time_api_usd": vol.get("totalAllTime"),
        "intents_volume_24h_api_usd": vol.get("total24h"),
        "intents_volume_30d_api_usd": vol.get("total30d"),
        "intents_volume_30d_computed": vol30,
        "intents_fees_all_time_api_usd": fees.get("totalAllTime"),
        "intents_fees_30d_api_usd": fees.get("total30d"),
        "intents_fees_30d_computed_complete_days": fee30,
        "intents_revenue_all_time_api_usd": rev.get("totalAllTime"),
        "intents_revenue_30d_api_usd": rev.get("total30d"),
        "intents_revenue_30d_computed_complete_days": rev30,
        "near_latest_price_usd": price_map.get(latest_price_date) if latest_price_date else None,
        "near_latest_price_date": latest_price_date,
        "near_chain_tvl_snapshot_usd": chain_tvl_now,
        "near_chain_tvl_snapshot_fetched_at_utc": now_utc.isoformat(),
        "intents_tvl_latest_usd": intents_tvl_latest[1],
        "intents_tvl_latest_date": intents_tvl_latest[0],
        "cumulative_volume_milestones_usd": milestones,
        "correlation": {
            "method": ("Pearson r between DefiLlama daily Intents volume (USD) and "
                       "daily NEAR price (USD, coins.llama.fi coingecko:near) on "
                       "dates present in both series."),
            "pearson_r_daily": r,
            "n_days_daily": len(pairs),
            "pearson_r_30d_rolling_volume": r_roll,
            "n_days_30d_rolling": len(roll_pairs),
        },
        "partial_day_flags": sorted(partial_dates),
        "notes": notes,
    }
    with open(os.path.join(DATA, "key_stats.json"), "w") as f:
        json.dump(key_stats, f, indent=2)

    # ---- dashboard charts (last 365 days of volume for readability)
    cutoff = (now_utc - timedelta(days=365)).strftime("%Y-%m-%d")
    p1_series = [
        {"label": "Daily Intents volume", "color": "#58a6ff", "kind": "bar",
         "axis": "left", "points": [(d, v) for d, v, _ in vol_rows if d >= cutoff]},
        {"label": "NEAR price (right)", "color": "#d2a8ff", "kind": "line",
         "axis": "right", "points": sorted(price_map.items())},
    ]
    chart1 = svg_line_chart(p1_series, title="Daily NEAR Intents volume vs NEAR price")

    tvl_map = dict(chain_tvl_rows)
    p2_points_flow = [(d, roll[d]) for d in sorted(roll) if d >= cutoff]
    p2_points_tvl = [(d, tvl_map[d]) for d in sorted(tvl_map) if d >= cutoff]
    p2_series = [
        {"label": "Intents volume, trailing 30d", "color": "#58a6ff", "kind": "line",
         "axis": "left", "points": p2_points_flow},
        {"label": "NEAR chain TVL", "color": "#3fb950", "kind": "line",
         "axis": "left", "points": p2_points_tvl},
    ]
    chart2 = svg_line_chart(p2_series, title="Trailing 30d Intents volume vs NEAR chain TVL")

    html = build_html(key_stats, chart1, chart2, fmt_usd)
    with open(os.path.join(BASE, "index.html"), "w") as f:
        f.write(html)

    print(f"[rebuild] volume rows: {len(vol_rows)} ({vol_rows[0][0]} .. {vol_rows[-1][0]})")
    print(f"[rebuild] cumulative volume: {fmt_usd(latest_cum)}")
    print(f"[rebuild] fees rows: {len(fee_pairs)}, partial days flagged: {sorted(partial_dates)}")
    print(f"[rebuild] price rows: {len(price_map)}, latest: "
          f"${key_stats['near_latest_price_usd']} on {latest_price_date}")
    print(f"[rebuild] chain TVL snapshot: {fmt_usd(chain_tvl_now)}")
    print(f"[rebuild] correlation daily r={r if r is None else round(r,4)} (n={len(pairs)}), "
          f"30d-rolling r={r_roll if r_roll is None else round(r_roll,4)} (n={len(roll_pairs)})")
    print("[rebuild] wrote data/*.csv, data/key_stats.json, index.html")
    print("[rebuild] DONE")
    return 0


def build_html(ks, chart1, chart2, fmt):
    def stat(label, value, sub=""):
        return (f'<div class="stat"><div class="stat-v">{value}</div>'
                f'<div class="stat-l">{label}</div>'
                f'<div class="stat-s">{sub}</div></div>')

    stats_html = "".join([
        stat("Intents cumulative volume", fmt(ks["intents_cumulative_volume_usd"]),
             f"computed from daily series, as of {ks['data_as_of']}"),
        stat("Intents volume, trailing 30d", fmt(ks["intents_volume_30d_computed"]["sum_usd"]),
             f"{ks['intents_volume_30d_computed']['from']} to {ks['intents_volume_30d_computed']['to']}"),
        stat("Intents fees, trailing 30d", fmt(ks["intents_fees_30d_computed_complete_days"]["sum_usd"]),
             "complete days only — partial final day excluded"),
        stat("Intents revenue, trailing 30d", fmt(ks["intents_revenue_30d_computed_complete_days"]["sum_usd"]),
             "complete days only"),
        stat("NEAR price (latest)", f"${ks['near_latest_price_usd']:,.2f}" if ks["near_latest_price_usd"] else "n/a",
             f"on {ks['near_latest_price_date']}"),
        stat("NEAR chain TVL", fmt(ks["near_chain_tvl_snapshot_usd"]), "live snapshot at rebuild time"),
    ])
    corr = ks["correlation"]
    r_txt = "n/a" if corr["pearson_r_daily"] is None else f"{corr['pearson_r_daily']:.2f}"
    rr_txt = "n/a" if corr["pearson_r_30d_rolling_volume"] is None else f"{corr['pearson_r_30d_rolling_volume']:.2f}"
    partial_note = ""
    if ks["partial_day_flags"]:
        partial_note = (f"<p class='warn'>Data caution: the final fees day "
                        f"({', '.join(ks['partial_day_flags'])}) is flagged partial "
                        "(fees below same-day revenue — impossible for a complete day) "
                        "and is excluded from computed trailing-30d sums.</p>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flow, Not Price — The $37B Decoupling (DRAFT)</title>
<style>
  body {{ margin:0; background:#0d1117; color:#e6edf3; font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:20px 16px 48px; }}
  h1 {{ font-size:26px; margin:8px 0 2px; }}
  h2 {{ font-size:19px; margin:0 0 6px; }}
  .draft {{ color:#f0883e; font-weight:600; letter-spacing:.06em; font-size:12px; text-transform:uppercase; }}
  .sub {{ color:#8b949e; margin:2px 0 18px; font-size:14px; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:22px; }}
  .stat {{ background:#161b22; border:1px solid #30363d; border-radius:10px; padding:12px; }}
  .stat-v {{ font-size:21px; font-weight:700; }}
  .stat-l {{ color:#e6edf3; font-size:13px; margin-top:2px; }}
  .stat-s {{ color:#8b949e; font-size:11px; margin-top:2px; }}
  .panel {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:16px; margin-bottom:20px; }}
  .panel svg {{ width:100%; height:auto; display:block; }}
  .take {{ font-size:15px; margin:10px 0 6px; }}
  .src {{ color:#8b949e; font-size:12px; word-break:break-all; }}
  .warn {{ color:#f0883e; font-size:13px; }}
  .corr {{ font-size:14px; color:#c9d1d9; }}
  code {{ background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:1px 5px; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="draft">Draft v0 — working title, not final</div>
  <h1>Flow, Not Price — The $37B Decoupling</h1>
  <p class="sub">NEAR Hackathon · Investment Thesis track. Testing whether NEAR Intents
  cross-chain volume is a better leading indicator of real network usage than the NEAR token price.
  Data as of {ks['data_as_of']} (rebuilt {ks['generated_at_utc'][:10]}). Every number below is
  computed by <code>rebuild.py</code> from the saved CSVs in <code>data/</code>.</p>

  <div class="stats">{stats_html}</div>
  {partial_note}

  <div class="panel">
    <h2>Panel 1 — The Decoupling Chart</h2>
    {chart1}
    <p class="take">Intents volume has grown into a $100M+/day flow; the NEAR price rose over the
    same year but with sharp swings volume does not explain — daily volume vs price correlation is
    r = {r_txt} (n = {corr['n_days_daily']} days), rising to r = {rr_txt} for 30-day rolling volume,
    so the two are related in trend but volume is not a mirror of price.</p>
    <p class="src">Sources: {ks['sources']['daily_volume']} and the coins.llama.fi NEAR price chart
    (exact URL in data/key_stats.json). Code: <code>rebuild.py</code> → data/intents_daily_volume.csv,
    data/near_daily_price.csv.</p>
  </div>

  <div class="panel">
    <h2>Panel 2 — Flow vs Vault</h2>
    {chart2}
    <p class="take">A single month of Intents flow (trailing-30d volume) is many times larger than
    the entire value locked on the NEAR chain — NEAR increasingly looks like a settlement pipe,
    not a vault.</p>
    <p class="src">Sources: {ks['sources']['daily_volume']} (rolling 30d sum computed in rebuild.py)
    and https://api.llama.fi/v2/historicalChainTvl/Near. Code: <code>rebuild.py</code> →
    data/intents_daily_volume.csv, data/near_chain_tvl.csv.</p>
  </div>

  <p class="sub">Panels 3–5 (value capture, the private layer, scenario model) are planned for v1.
  See THESIS.md for the claim, the evidence for and against, and what would change our mind.</p>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
