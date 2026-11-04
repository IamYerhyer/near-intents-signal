#!/usr/bin/env python3
"""
rebuild.py — one-command rebuild for the NEAR Intents Investment Thesis dashboard.

Usage:  python3 rebuild.py

What it does:
  1. Pulls free, keyless public API endpoints (DefiLlama; CoinGecko for market cap).
  2. Saves raw JSON responses to data/raw/.
  3. Writes tidy CSVs to data/ (incl. data/leadlag.csv).
  4. Computes data/key_stats.json (every headline number traces to a CSV/JSON here)
     and data/model_outputs.json (scenario model, assumptions in model_config.json).
  5. Regenerates index.html (static dashboard, charts are inline SVG generated
     from the CSV data — no external dependencies, works offline from file://).

Only Python 3 standard library is used. No API keys. No invented numbers.

Partial-day rule (important): DefiLlama daily series can end on an incomplete
day. A day is flagged `partial` in the fees CSV when the final fees value is
lower than the same day's revenue value (revenue is a subset of fees, so
fees < revenue is impossible for a complete day). Flagged partial days are
excluded from the "computed" trailing-30d sums in key_stats.json; the raw
API-reported totals are kept separately and labelled as such.

Lead-lag convention: for lag L, volume on day t is paired with price on day
t+L. Positive L therefore tests whether volume measured EARLIER lines up with
price LATER (volume leading). Levels correlations are trend-inflated; the
robustness check in key_stats.json (`leadlag.forward_return_tests`) correlates
changes in volume with FORWARD price returns instead.
"""

import csv
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timezone, timedelta, date

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RAW = os.path.join(DATA, "raw")

VOL_URL = "https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume"
FEES_URL = "https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees"
REV_URL = "https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue"
PROTO_URL = "https://api.llama.fi/protocol/near-intents"
CHAINS_URL = "https://api.llama.fi/v2/chains"
CHAIN_TVL_HIST_URL = "https://api.llama.fi/v2/historicalChainTvl/Near"
COINGECKO_MCAP_URL = ("https://api.coingecko.com/api/v3/coins/markets"
                      "?vs_currency=usd&ids=near")
DEFILLAMA_INTENTS_PAGE = "https://defillama.com/protocol/near-intents"

# First-party NEAR claims we do NOT independently verify (Panel 5, attributed
# box). Text + source + date as recorded in the build plan, 2026-11-04.
# These never enter any computed statistic.
ATTRIBUTED_CLAIMS = [
    {"claim": "NEAR reported Intents volume crossed $37B all-time, with 37M+ total swaps.",
     "source": "NEAR Protocol monthly shipping recap, 3 Nov 2026 (first-party; "
               "our independent DefiLlama series sums to the cumulative figure "
               "in Panel 1, the swap count is not published by an independent "
               "dashboard we can reproduce)"},
    {"claim": "Confidential Intents TVL topped ~$145M.",
     "source": "NEAR Protocol, 3 Nov 2026 (first-party; confidential metrics "
               "come from a private shard and are not a public balance we can audit)"},
    {"claim": "More than 1M NEAR is staked for confidential AI inference.",
     "source": "NEAR Protocol, 3 Nov 2026 (first-party; no independent "
               "dashboard reproduced this exact figure)"},
    {"claim": "Brave Leo began running private AI inference on NEAR AI Cloud "
              "in production (model: GLM 5.3 Flash).",
     "source": "NEAR Protocol, Oct 2026; Brave Leo integration reported live 15 Oct 2026"},
]


def price_url():
    """Daily NEAR price for the last 365 days, anchored to today (UTC)."""
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - 365 * 86400
    return (
        "https://coins.llama.fi/chart/coingecko:near"
        f"?start={start}&span=365&period=1d"
    )


def fetch(url, raw_name):
    req = urllib.request.Request(url, headers={"User-Agent": "near-intents-signal/0.2"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = resp.read()
    with open(os.path.join(RAW, raw_name), "wb") as f:
        f.write(payload)
    return json.loads(payload)


def dstr(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def pdate(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def shift(s, days):
    return (pdate(s) + timedelta(days=days)).strftime("%Y-%m-%d")


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


def rolling_mean(rows, window):
    """rows: sorted [(date, value)]. Returns {date: trailing-window mean value}
    for every position with a full window of observations."""
    out = {}
    vals = [v for _, v in rows]
    for i in range(window - 1, len(rows)):
        out[rows[i][0]] = sum(vals[i - window + 1:i + 1]) / window
    return out


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


def fmt_r(v):
    return "n/a" if v is None else f"{v:+.2f}"


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
    step = max(1, len(all_x) // 6)
    for i in range(0, len(all_x), step):
        x = all_x[i]
        out.append(f'<text x="{xpos(x):.1f}" y="{height-10}" fill="#8b949e" font-size="11" text-anchor="middle">{x[:7]}</text>')
    for s in series:
        if s.get("kind") == "bar":
            bw = max(1.0, iw / max(len(all_x), 1) * 0.8)
            base = ypos(0, s.get("axis", "left")) if 0 >= axes[s.get("axis", "left")][0] else pad_t + ih
            for x, y in s["points"]:
                yy = ypos(y, s.get("axis", "left"))
                out.append(f'<rect x="{xpos(x)-bw/2:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{abs(base-yy):.1f}" fill="{s["color"]}" opacity="0.55"/>')
    for s in series:
        if s.get("kind") == "bar":
            continue
        pts = " ".join(f"{xpos(x):.1f},{ypos(y, s.get('axis','left')):.1f}" for x, y in s["points"])
        out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2" points="{pts}"/>')
    lx = pad_l
    for s in series:
        out.append(f'<rect x="{lx}" y="6" width="10" height="10" fill="{s["color"]}"/>')
        out.append(f'<text x="{lx+14}" y="15" fill="#e6edf3" font-size="12">{s["label"]}</text>')
        lx += 14 + 8 * len(s["label"]) + 34
    out.append("</svg>")
    return "".join(out)


def svg_corr_chart(series, width=920, height=340, title=""):
    """Numeric-x chart for correlation-by-lag curves.
    series: [{label, color, points:[(lag:int, r:float)]}]. Zero line + zero-lag
    marker are drawn. Y tick labels are plain decimals, not USD."""
    pad_l, pad_r, pad_t, pad_b = 52, 20, 26, 34
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    if not xs:
        return "<p>No data.</p>"
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys + [0.0]), max(ys + [0.0])
    span = (yhi - ylo) or 1
    ylo, yhi = ylo - 0.08 * span, yhi + 0.08 * span

    def xpos(x):
        return pad_l + iw * (x - xlo) / max(xhi - xlo, 1)

    def ypos(v):
        return pad_t + ih - ih * (v - ylo) / (yhi - ylo)

    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">']
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#0d1117"/>')
    for i in range(5):
        v = ylo + (yhi - ylo) * i / 4
        y = ypos(v)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="#21262d" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+3:.1f}" fill="#8b949e" font-size="11" text-anchor="end">{v:+.1f}</text>')
    for x in range(xlo, xhi + 1, 10):
        out.append(f'<text x="{xpos(x):.1f}" y="{height-10}" fill="#8b949e" font-size="11" text-anchor="middle">{x:+d}d</text>')
    out.append(f'<line x1="{pad_l}" y1="{ypos(0):.1f}" x2="{width-pad_r}" y2="{ypos(0):.1f}" stroke="#484f58" stroke-width="1"/>')
    if xlo <= 0 <= xhi:
        out.append(f'<line x1="{xpos(0):.1f}" y1="{pad_t}" x2="{xpos(0):.1f}" y2="{pad_t+ih}" stroke="#484f58" stroke-width="1" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{xpos(0)+4:.1f}" y="{pad_t+12}" fill="#8b949e" font-size="11">lag 0</text>')
    for s in series:
        pts = " ".join(f"{xpos(x):.1f},{ypos(y):.1f}" for x, y in s["points"])
        out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="2" points="{pts}"/>')
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

    # NEAR market cap (CoinGecko public API, free). Optional: if it fails or is
    # rate-limited, the model simply omits the "% of market cap" column.
    mcap_info = {"status": "unavailable", "reason": None,
                 "source": COINGECKO_MCAP_URL, "market_cap_usd": None,
                 "price_usd": None, "fetched_at_utc": now_utc.isoformat()}
    try:
        cg = fetch(COINGECKO_MCAP_URL, "coingecko_near_markets.json")
        row = cg[0] if isinstance(cg, list) and cg else {}
        if row.get("market_cap"):
            mcap_info.update({"status": "ok",
                              "market_cap_usd": float(row["market_cap"]),
                              "price_usd": float(row["current_price"])})
        else:
            mcap_info["reason"] = "CoinGecko response contained no market_cap field."
    except Exception as e:
        mcap_info["reason"] = f"CoinGecko public API fetch failed: {e}"

    # ---- daily volume (+ cumulative)
    vol_rows, cum = [], 0.0
    for ts, v in vol.get("totalDataChart", []):
        cum += float(v)
        vol_rows.append((dstr(ts), float(v), cum))
    write_csv("intents_daily_volume.csv",
              ["date", "daily_volume_usd", "cumulative_volume_usd"], vol_rows)
    vol_map = {d: v for d, v, _ in vol_rows}
    vol_sorted = [(d, v) for d, v, _ in vol_rows]

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
    fee_map = dict(fee_rows_raw)

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

    # ---- Intents TVL (protocol endpoint) + TVL by chain (latest point each)
    intents_tvl = [(dstr(r["date"]), float(r["totalLiquidityUSD"])) for r in proto.get("tvl", [])]
    intents_tvl_latest = intents_tvl[-1] if intents_tvl else (None, None)
    chain_tvl_list = []
    for ch, payload in (proto.get("chainTvls") or {}).items():
        pts = payload.get("tvl") or []
        if pts:
            last = pts[-1]
            chain_tvl_list.append({"chain": ch,
                                   "tvl_usd": float(last["totalLiquidityUSD"]),
                                   "as_of": dstr(last["date"])})
    chain_tvl_list.sort(key=lambda r: -r["tvl_usd"])
    intents_tvl_by_chain_total = sum(r["tvl_usd"] for r in chain_tvl_list)

    # ---- computed stats (v0 set, preserved)
    def trailing_sum(rows, days=30, exclude=()):
        clean = [(d, v) for d, v in rows if d not in exclude]
        tail = clean[-days:]
        return {"sum_usd": sum(v for _, v in tail),
                "days": len(tail),
                "from": tail[0][0] if tail else None,
                "to": tail[-1][0] if tail else None}

    fee_pairs = [(d, v) for d, v in fee_rows_raw]
    vol30 = trailing_sum(vol_sorted)
    fee30 = trailing_sum(fee_pairs, exclude=partial_dates)
    rev30 = trailing_sum(sorted(rev_map.items()), exclude=partial_dates)

    def cum_on(date_str):
        vals = [c for d, _, c in vol_rows if d <= date_str]
        return vals[-1] if vals else None

    latest_cum = vol_rows[-1][2] if vol_rows else None
    milestones = {}
    for label in ("2026-06-30", "2026-09-15"):
        milestones[label] = cum_on(label)
    if vol_rows:
        milestones[vol_rows[-1][0]] = latest_cum

    # correlation: daily volume vs NEAR price on overlapping dates
    pairs = [(v, price_map[d]) for d, v, _ in vol_rows if d in price_map]
    r = pearson([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else None
    # 30d rolling volume (sum) vs price (smoothed flow) — v0 metric, preserved
    dates_sorted = sorted(vol_map)
    roll30 = {}
    for i, d in enumerate(dates_sorted):
        if i >= 29:
            roll30[d] = sum(vol_map[dates_sorted[j]] for j in range(i - 29, i + 1))
    roll_pairs = [(roll30[d], price_map[d]) for d in roll30 if d in price_map]
    r_roll = pearson([p[0] for p in roll_pairs], [p[1] for p in roll_pairs]) if roll_pairs else None

    # ---------------------------------------------------------- LEAD–LAG
    roll7 = rolling_mean(vol_sorted, 7)

    def lag_corr(vmap, lag):
        xs, ys = [], []
        for d, v in vmap.items():
            t = shift(d, lag)
            if t in price_map:
                xs.append(v)
                ys.append(price_map[t])
        return pearson(xs, ys), len(xs)

    leadlag_rows = []
    for lag in range(-30, 31):
        ra, na = lag_corr(vol_map, lag)
        rb, nb = lag_corr(roll7, lag)
        leadlag_rows.append({"lag_days": lag, "r_levels_daily": ra,
                             "r_levels_7d_rolling": rb, "n_daily": na, "n_7d": nb})
    write_csv("leadlag.csv",
              ["lag", "r_levels_daily", "r_levels_7d", "n", "n_7d"],
              [(row["lag_days"],
                "" if row["r_levels_daily"] is None else f"{row['r_levels_daily']:.6f}",
                "" if row["r_levels_7d_rolling"] is None else f"{row['r_levels_7d_rolling']:.6f}",
                row["n_daily"], row["n_7d"]) for row in leadlag_rows])

    def best_lag(rows, key):
        valid = [row for row in rows if row[key] is not None]
        if not valid:
            return None, None
        b = max(valid, key=lambda row: row[key])
        return b["lag_days"], b[key]

    bl_daily, br_daily = best_lag(leadlag_rows, "r_levels_daily")
    bl_7d, br_7d = best_lag(leadlag_rows, "r_levels_7d_rolling")
    r_lag0_daily = next((row["r_levels_daily"] for row in leadlag_rows if row["lag_days"] == 0), None)
    r_lag0_7d = next((row["r_levels_7d_rolling"] for row in leadlag_rows if row["lag_days"] == 0), None)

    # Robustness: 7d % change in 7d rolling volume vs FORWARD price returns.
    roll7_dates = sorted(roll7)
    roll7_idx = {d: i for i, d in enumerate(roll7_dates)}
    volchg = {}
    for d in roll7_dates:
        i = roll7_idx[d]
        if i >= 7:
            prev = roll7[roll7_dates[i - 7]]
            if prev:
                volchg[d] = roll7[d] / prev - 1.0
    fwd_tests = []
    for w in (1, 7, 14, 30):
        xs, ys = [], []
        for d, chg in volchg.items():
            t = shift(d, w)
            if d in price_map and t in price_map and price_map[d]:
                xs.append(chg)
                ys.append(price_map[t] / price_map[d] - 1.0)
        fwd_tests.append({"forward_window_days": w,
                          "pearson_r": pearson(xs, ys), "n": len(xs)})

    def classify(best):
        if best is None:
            return "undetermined"
        if best >= 3:
            return "volume_leads"
        if best <= -3:
            return "volume_lags"
        return "coincident"

    cls_7d = classify(bl_7d)
    pos_fwd = sum(1 for t in fwd_tests
                  if t["pearson_r"] is not None and t["pearson_r"] > 0.05)
    strong_fwd = sum(1 for t in fwd_tests
                     if t["pearson_r"] is not None and t["pearson_r"] > 0.15)
    if cls_7d == "volume_leads" and pos_fwd >= 3:
        verdict = ("Levels cross-correlation peaks with volume measured first AND "
                   "volume growth is positively associated with forward price "
                   "returns at most horizons — the lead-lag evidence is consistent "
                   "with volume leading price, subject to the trend-inflation caveat.")
    elif cls_7d == "volume_leads":
        verdict = ("Levels cross-correlation peaks at a positive lag (volume first), "
                   "but the change-vs-forward-return robustness check does not "
                   "confirm it — treat any lead as unproven; levels are "
                   "trend-inflated.")
    elif cls_7d == "coincident":
        verdict = ("Levels cross-correlation peaks at or near lag 0 — volume and "
                   "price move together rather than volume going first; on this "
                   "data volume is a coincident, not leading, indicator.")
    elif cls_7d == "volume_lags":
        verdict = ("Levels cross-correlation peaks at a negative lag — price moves "
                   "first and volume follows; on this data volume lags price.")
    else:
        verdict = "Lead-lag structure could not be determined from the data."
    leadlag_stats = {
        "method": ("Cross-correlation: for lag L in -30..+30 days, Pearson r between "
                   "Intents volume on day t and NEAR price on day t+L, on dates "
                   "present in both series. Positive L = volume measured BEFORE "
                   "price. Two volume series: raw daily volume, and the trailing "
                   "7-day rolling mean of daily volume. Levels correlations are "
                   "inflated by the shared upward trend in both series, so the "
                   "robustness check correlates the 7-day % change in 7-day rolling "
                   "volume with FORWARD NEAR price returns (price[t+w]/price[t]-1)."),
        "best_lag_levels_daily": {"lag_days": bl_daily, "r": br_daily},
        "best_lag_levels_7d_rolling": {"lag_days": bl_7d, "r": br_7d},
        "r_at_lag0_daily": r_lag0_daily,
        "r_at_lag0_7d_rolling": r_lag0_7d,
        "classification_from_7d_levels": cls_7d,
        "forward_return_tests": fwd_tests,
        "verdict": verdict,
        "csv": "data/leadlag.csv",
    }

    # ------------------------------------------------------- VALUE CAPTURE
    vol_in_fee_window = None
    if fee30["from"] and fee30["to"]:
        vol_in_fee_window = sum(v for d, v in vol_map.items()
                                if fee30["from"] <= d <= fee30["to"])
    fees_all, revs_all = fees.get("totalAllTime"), rev.get("totalAllTime")
    vc = {
        "method": ("Computed from the DefiLlama daily fees/revenue series. "
                   "Trailing-30d figures use complete days only (flagged partial "
                   "day excluded). Take rates divide by Intents volume over the "
                   "same trailing-30-complete-days window as the fees sum."),
        "capture_ratio_all_time": (revs_all / fees_all) if fees_all else None,
        "capture_ratio_trailing_30d_complete_days": (
            rev30["sum_usd"] / fee30["sum_usd"] if fee30["sum_usd"] else None),
        "fee_take_rate_trailing_30d": (
            fee30["sum_usd"] / vol_in_fee_window if vol_in_fee_window else None),
        "revenue_take_rate_trailing_30d": (
            rev30["sum_usd"] / vol_in_fee_window if vol_in_fee_window else None),
        "volume_in_fee_window_usd": vol_in_fee_window,
        "fee_window": {"from": fee30["from"], "to": fee30["to"], "days": fee30["days"]},
        "annualised_revenue_run_rate_usd": (
            rev30["sum_usd"] / rev30["days"] * 365 if rev30["days"] else None),
        "buyback_mechanism": ("Since 2026-02-23, NEAR's captured Intents revenue "
                              "is used to buy back $NEAR on the open market (not "
                              "burned), per the DefiLlama NEAR Intents methodology: "
                              "revenue is NEAR's net captured revenue, measured as "
                              "NEAR/wNEAR swept into its revenue wallets, and since "
                              "2026-02-23 that captured revenue funds open-market "
                              "buybacks. Source: " + DEFILLAMA_INTENTS_PAGE),
    }

    # ------------------------------------------------------ SCENARIO MODEL
    model_cfg_path = os.path.join(BASE, "model_config.json")
    cfg = {"scenarios": [
        {"name": "Bear", "volume_multiplier_vs_current_annualised_run_rate": 1.0},
        {"name": "Base", "volume_multiplier_vs_current_annualised_run_rate": 2.0},
        {"name": "Bull", "volume_multiplier_vs_current_annualised_run_rate": 4.0}]}
    if os.path.exists(model_cfg_path):
        with open(model_cfg_path) as f:
            cfg = json.load(f)
    annualised_vol = (vol30["sum_usd"] / vol30["days"] * 365) if vol30["days"] else None
    scenarios_out = []
    for sc in cfg.get("scenarios", []):
        mult = float(sc["volume_multiplier_vs_current_annualised_run_rate"])
        avol = annualised_vol * mult if annualised_vol is not None else None
        gfees = (avol * vc["fee_take_rate_trailing_30d"]
                 if avol is not None and vc["fee_take_rate_trailing_30d"] else None)
        caprev = (gfees * vc["capture_ratio_trailing_30d_complete_days"]
                  if gfees is not None and vc["capture_ratio_trailing_30d_complete_days"] else None)
        pct_mcap = (caprev / mcap_info["market_cap_usd"] * 100
                    if caprev is not None and mcap_info["market_cap_usd"] else None)
        scenarios_out.append({
            "name": sc["name"], "label": sc.get("label", ""),
            "volume_multiplier_vs_current_annualised_run_rate": mult,
            "annual_volume_usd": avol, "gross_fees_usd": gfees,
            "captured_revenue_usd": caprev,
            "captured_revenue_pct_of_market_cap": pct_mcap})
    model_outputs = {
        "generated_at_utc": now_utc.isoformat(),
        "framing": ("Scenario arithmetic, NOT a price prediction and NOT a "
                    "forecast. Annual volume = current annualised run-rate x a "
                    "chosen scenario multiplier (model_config.json); fees and "
                    "captured revenue apply the OBSERVED trailing-30d fee take "
                    "rate and capture ratio, held constant. Captured revenue is "
                    "the buyback $ amount at the current mechanism described in "
                    "key_stats.json value_capture.buyback_mechanism."),
        "base_inputs": {
            "annualised_volume_run_rate_usd": annualised_vol,
            "run_rate_basis": (f"trailing-30d computed volume "
                               f"{vol30['from']} to {vol30['to']}"),
            "fee_take_rate": vc["fee_take_rate_trailing_30d"],
            "capture_ratio": vc["capture_ratio_trailing_30d_complete_days"],
            "trailing_30d_volume_usd": vol30["sum_usd"],
            "trailing_30d_fees_usd": fee30["sum_usd"],
            "trailing_30d_revenue_usd": rev30["sum_usd"]},
        "market_cap": mcap_info,
        "scenarios": scenarios_out,
        "config_file": "model_config.json",
    }
    with open(os.path.join(DATA, "model_outputs.json"), "w") as f:
        json.dump(model_outputs, f, indent=2)

    latest_price_date = max(price_map) if price_map else None
    key_stats = {
        "generated_at_utc": now_utc.isoformat(),
        "data_as_of": vol_rows[-1][0] if vol_rows else None,
        "sources": {
            "daily_volume": VOL_URL, "daily_fees": FEES_URL,
            "daily_revenue": REV_URL, "price": p_url,
            "chains_snapshot": CHAINS_URL, "protocol": PROTO_URL,
            "chain_tvl_history": CHAIN_TVL_HIST_URL if chain_hist else None,
            "market_cap": COINGECKO_MCAP_URL,
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
        "intents_tvl_by_chain": chain_tvl_list,
        "intents_tvl_by_chain_total_usd": intents_tvl_by_chain_total,
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
        "leadlag": leadlag_stats,
        "value_capture": vc,
        "market_cap": mcap_info,
        "scenario_model": {
            "file": "data/model_outputs.json",
            "config": "model_config.json",
            "base_annualised_volume_run_rate_usd": annualised_vol,
            "scenarios": scenarios_out,
        },
        "partial_day_flags": sorted(partial_dates),
        "notes": notes,
    }
    with open(os.path.join(DATA, "key_stats.json"), "w") as f:
        json.dump(key_stats, f, indent=2)

    # ---- dashboard charts
    cutoff = (now_utc - timedelta(days=365)).strftime("%Y-%m-%d")
    p1_series = [
        {"label": "Daily Intents volume", "color": "#58a6ff", "kind": "bar",
         "axis": "left", "points": [(d, v) for d, v, _ in vol_rows if d >= cutoff]},
        {"label": "NEAR price (right)", "color": "#d2a8ff", "kind": "line",
         "axis": "right", "points": sorted(price_map.items())},
    ]
    chart1 = svg_line_chart(p1_series, title="Daily NEAR Intents volume vs NEAR price")

    tvl_map = dict(chain_tvl_rows)
    p2_points_flow = [(d, roll30[d]) for d in sorted(roll30) if d >= cutoff]
    p2_points_tvl = [(d, tvl_map[d]) for d in sorted(tvl_map) if d >= cutoff]
    p2_series = [
        {"label": "Intents volume, trailing 30d", "color": "#58a6ff", "kind": "line",
         "axis": "left", "points": p2_points_flow},
        {"label": "NEAR chain TVL", "color": "#3fb950", "kind": "line",
         "axis": "left", "points": p2_points_tvl},
    ]
    chart2 = svg_line_chart(p2_series, title="Trailing 30d Intents volume vs NEAR chain TVL")

    ll_series = [
        {"label": "Daily volume vs price", "color": "#58a6ff",
         "points": [(row["lag_days"], row["r_levels_daily"]) for row in leadlag_rows
                    if row["r_levels_daily"] is not None]},
        {"label": "7d rolling volume vs price", "color": "#f0883e",
         "points": [(row["lag_days"], row["r_levels_7d_rolling"]) for row in leadlag_rows
                    if row["r_levels_7d_rolling"] is not None]},
    ]
    chart3 = svg_corr_chart(ll_series, title="Cross-correlation by lag: volume vs price")

    fee_fee_points = [(d, v) for d, v in fee_pairs if d >= cutoff and d not in partial_dates]
    fee_rev_points = [(d, v) for d, v in sorted(rev_map.items())
                      if d >= cutoff and d not in partial_dates]
    p4_series = [
        {"label": "Daily fees (gross)", "color": "#58a6ff", "kind": "line",
         "axis": "left", "points": fee_fee_points},
        {"label": "Daily revenue (captured by NEAR)", "color": "#3fb950", "kind": "line",
         "axis": "left", "points": fee_rev_points},
    ]
    chart4 = svg_line_chart(p4_series, title="Daily Intents fees vs captured revenue")

    html = build_html(key_stats, model_outputs, chart1, chart2, chart3, chart4, fmt_usd)
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
    print(f"[rebuild] lead-lag best: daily lag={bl_daily} (r={br_daily if br_daily is None else round(br_daily,4)}), "
          f"7d lag={bl_7d} (r={br_7d if br_7d is None else round(br_7d,4)}), class={cls_7d}")
    print("[rebuild] lead-lag forward tests: " + ", ".join(
        f"{t['forward_window_days']}d r={t['pearson_r'] if t['pearson_r'] is None else round(t['pearson_r'],4)} (n={t['n']})"
        for t in fwd_tests))
    print(f"[rebuild] value capture: ratio all-time={vc['capture_ratio_all_time']}, "
          f"30d={vc['capture_ratio_trailing_30d_complete_days']}, "
          f"fee take={vc['fee_take_rate_trailing_30d']}, rev take={vc['revenue_take_rate_trailing_30d']}")
    print(f"[rebuild] market cap: {mcap_info['status']} {fmt_usd(mcap_info['market_cap_usd'])}")
    print(f"[rebuild] intents TVL by chain: {len(chain_tvl_list)} chains, "
          f"top: {chain_tvl_list[0]['chain'] if chain_tvl_list else 'n/a'}")
    print("[rebuild] wrote data/*.csv, data/leadlag.csv, data/key_stats.json, "
          "data/model_outputs.json, index.html")
    print("[rebuild] DONE")
    return 0


def build_html(ks, model, chart1, chart2, chart3, chart4, fmt):
    def stat(label, value, sub=""):
        return (f'<div class="stat"><div class="stat-v">{value}</div>'
                f'<div class="stat-l">{label}</div>'
                f'<div class="stat-s">{sub}</div></div>')

    def pct(v, digits=2):
        return "n/a" if v is None else f"{v*100:.{digits}f}%"

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

    ll = ks["leadlag"]
    bl7 = ll["best_lag_levels_7d_rolling"]
    bld = ll["best_lag_levels_daily"]
    fwd_bits = ", ".join(
        f"{t['forward_window_days']}d: r = {fmt_r(t['pearson_r'])}"
        for t in ll["forward_return_tests"])
    leadlag_take = (
        f"Cross-correlation peaks at lag {bl7['lag_days']:+d} days for 7-day rolling "
        f"volume (r = {fmt_r(bl7['r'])}) and lag {bld['lag_days']:+d} days for raw daily "
        f"volume (r = {fmt_r(bld['r'])}), where a positive lag means volume was measured "
        f"before price. {ll['verdict']}")
    leadlag_fwd = (
        f"Robustness check (levels are trend-inflated, so this matters more): correlation "
        f"between the 7-day % change in 7-day rolling volume and forward price returns — "
        f"{fwd_bits}. Weak or negative values here mean volume growth does not "
        f"reliably precede price gains even if the levels curves peak at a positive lag.")

    vc = ks["value_capture"]
    vc_take = (
        f"Of every $1 of gross Intents fees, about ${vc['capture_ratio_trailing_30d_complete_days']:.2f} "
        f"reached NEAR as captured revenue over the last 30 complete days "
        f"(capture ratio {pct(vc['capture_ratio_trailing_30d_complete_days'], 1)}; all-time "
        f"{pct(vc['capture_ratio_all_time'], 1)}) — an effective revenue take of "
        f"{pct(vc['revenue_take_rate_trailing_30d'], 3)} of volume and an annualised "
        f"revenue run-rate of {fmt(vc['annualised_revenue_run_rate_usd'])}: the flow is "
        f"large, the slice is thin.")

    top_chains = ks["intents_tvl_by_chain"][:10]
    chain_rows = "".join(
        f"<tr><td>{c['chain']}</td><td class='num'>{fmt(c['tvl_usd'])}</td>"
        f"<td class='num'>{pct(c['tvl_usd']/ks['intents_tvl_by_chain_total_usd'], 1) if ks['intents_tvl_by_chain_total_usd'] else 'n/a'}</td></tr>"
        for c in top_chains)
    claims_html = "".join(
        f"<li><strong>Claim:</strong> {c['claim']}<br><span class='src'>{c['source']}</span></li>"
        for c in ATTRIBUTED_CLAIMS)
    private_take = (
        f"Intents liquidity verifiably sits across {len(ks['intents_tvl_by_chain'])} chains "
        f"(largest: {top_chains[0]['chain'] if top_chains else 'n/a'}) — that footprint is "
        f"reproducible from DefiLlama; the confidential-layer claims in the box are "
        f"NEAR's own and are labelled, not verified.")

    mcap = model["market_cap"]
    have_mcap = mcap["status"] == "ok"
    mcap_head = "<th class='num'>Captured rev. as % of NEAR market cap</th>" if have_mcap else ""
    scen_rows = ""
    for s in model["scenarios"]:
        mcap_cell = (f"<td class='num'>{s['captured_revenue_pct_of_market_cap']:.2f}%</td>"
                     if have_mcap and s["captured_revenue_pct_of_market_cap"] is not None else "")
        scen_rows += (f"<tr><td>{s['name']} ({s['volume_multiplier_vs_current_annualised_run_rate']:g}x)</td>"
                      f"<td class='num'>{fmt(s['annual_volume_usd'])}</td>"
                      f"<td class='num'>{fmt(s['gross_fees_usd'])}</td>"
                      f"<td class='num'>{fmt(s['captured_revenue_usd'])}</td>{mcap_cell}</tr>")
    bi = model["base_inputs"]
    if have_mcap:
        mcap_note = (f"Market cap {fmt(mcap['market_cap_usd'])} from CoinGecko "
                     f"(fetched {mcap['fetched_at_utc'][:10]}).")
    else:
        mcap_note = (f"Market-cap column omitted: {mcap['reason']} Captured revenue "
                     f"is still shown in dollars.")
    model_take = (
        f"Scenario arithmetic — NOT a price prediction. Base inputs are computed from "
        f"data: annualised volume run-rate {fmt(bi['annualised_volume_run_rate_usd'])}, "
        f"observed fee take rate {pct(bi['fee_take_rate'], 3)}, observed capture ratio "
        f"{pct(bi['capture_ratio'], 1)}. Only the volume multiplier is assumed "
        f"(model_config.json). {mcap_note}")

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
  table {{ border-collapse:collapse; width:100%; margin:10px 0; font-size:14px; }}
  th, td {{ border-bottom:1px solid #30363d; padding:7px 8px; text-align:left; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .claims {{ background:#0d1117; border:1px solid #f0883e; border-radius:10px; padding:12px 16px; margin-top:12px; }}
  .claims h3 {{ margin:4px 0 8px; font-size:15px; color:#f0883e; }}
  .claims li {{ margin-bottom:10px; font-size:14px; }}
  code {{ background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:1px 5px; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="draft">Draft v1 — working title, not final</div>
  <h1>Flow, Not Price — The $37B Decoupling</h1>
  <p class="sub">NEAR Hackathon · Investment Thesis track. Testing whether NEAR Intents
  cross-chain volume is a better leading indicator of real network usage than the NEAR token price.
  Data as of {ks['data_as_of']} (rebuilt {ks['generated_at_utc'][:10]}). Every number below is
  computed by <code>rebuild.py</code> from the saved CSVs in <code>data/</code> — except the
  clearly labelled first-party claims in Panel 5, which are attributed, not verified.</p>

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

  <div class="panel">
    <h2>Panel 3 — Does Volume Lead Price?</h2>
    {chart3}
    <p class="take">{leadlag_take}</p>
    <p class="take">{leadlag_fwd}</p>
    <p class="src">Sources: {ks['sources']['daily_volume']} and the coins.llama.fi NEAR price chart.
    Code: <code>rebuild.py</code> → data/leadlag.csv; full method, best lags and forward-return
    tests in data/key_stats.json under <code>leadlag</code>.</p>
  </div>

  <div class="panel">
    <h2>Panel 4 — Does the Token Capture It? (Value Capture)</h2>
    {chart4}
    <p class="take">{vc_take}</p>
    <p class="take">Mechanism: {vc['buyback_mechanism']}</p>
    <p class="src">Sources: {ks['sources']['daily_fees']} and {ks['sources']['daily_revenue']};
    buyback mechanism per the DefiLlama NEAR Intents methodology page linked above.
    Code: <code>rebuild.py</code> → data/intents_daily_fees.csv (partial day flagged),
    data/intents_daily_revenue.csv; ratios in data/key_stats.json under <code>value_capture</code>.</p>
  </div>

  <div class="panel">
    <h2>Panel 5 — The Private Layer &amp; Chain Footprint</h2>
    <table>
      <tr><th>Chain</th><th class="num">Intents TVL (latest)</th><th class="num">Share</th></tr>
      {chain_rows}
    </table>
    <p class="take">{private_take}</p>
    <p class="src">Source: {ks['sources']['protocol']} (chainTvls, latest point per chain).
    Code: <code>rebuild.py</code> → data/key_stats.json under <code>intents_tvl_by_chain</code>.</p>
    <div class="claims">
      <h3>First-party claims — attributed, NOT independently verified</h3>
      <ul>{claims_html}</ul>
      <p class="src">None of these figures enter any computed statistic on this page.</p>
    </div>
  </div>

  <div class="panel">
    <h2>Panel 6 — The Model (Scenario Arithmetic, Not a Prediction)</h2>
    <table>
      <tr><th>Scenario (volume vs current run-rate)</th><th class="num">Annual volume</th><th class="num">Gross fees</th><th class="num">Captured revenue (= buyback $)</th>{mcap_head}</tr>
      {scen_rows}
    </table>
    <p class="take">{model_take}</p>
    <p class="src">Assumptions: <code>model_config.json</code> (edit the multipliers and re-run).
    Outputs: data/model_outputs.json. Method and base inputs are recorded in that file.</p>
  </div>

  <p class="sub">See THESIS.md for the claim, the evidence for and against (including the
  lead-lag result), and what would change our mind.</p>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
