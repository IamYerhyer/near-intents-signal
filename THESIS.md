# THESIS — Flow, Not Price (DRAFT)

**Status: DRAFT for NEAR HACKATHON, Investment Thesis track.**
All numbers below were computed by `rebuild.py` (v1) on 2026-11-04 from the
DefiLlama public APIs listed in README.md (plus CoinGecko for market cap).
Data as of **2026-11-03** (the last day in the daily series). Re-run
`python3 rebuild.py` to refresh them — do not hand-edit numbers here
without re-running.

## The claim

Cross-chain volume through NEAR Intents is a better leading indicator of
real network usage than the NEAR token price. (Hypothesis taken from the
official track prompt; we test it, we do not assume it.)

Working interpretation: NEAR's economic centre of gravity is shifting from
"an L1 you hold" to "a settlement pipe agents and users route through" —
and flow through that pipe (Intents volume, fees, revenue) shows it earlier
and more clearly than price or TVL do.

**v1 headline result:** the lead–lag test (Panel 3) does **not** support
the strong version of this claim for price. Volume is best described as a
*coincident* indicator alongside price, not a leading one. The sections
below report that honestly; the claim survives, if at all, in a weaker
form — volume as a real-time usage gauge, where price is a noisy one.

## Evidence for

- **The flow is real and large, on independent data.** Cumulative Intents
  volume computed from the DefiLlama daily series is **$36,386,550,029
  ($36.39B)** as of 2026-11-03, and it exactly matches DefiLlama's own
  reported all-time total — two ways of adding the same series agree.
  (Source: `data/intents_daily_volume.csv`, `data/key_stats.json`.)
- **Growth is steep and recent.** Cumulative volume milestones computed
  from the series: **$22.24B by 2026-06-30 → $29.28B by 2026-09-15 →
  $36.39B by 2026-11-03**. Roughly $14.1B of flow arrived in ~4 months.
- **Current run-rate is high.** Trailing-30d volume (2026-10-05 →
  2026-11-03): **$3,970,607,022 ($3.97B)**; latest full day in the series
  printed **$137,911,779**. Annualised, the current run-rate is ~$48.3B.
- **The flow pays, and recent capture is stronger than the historical
  average.** Trailing-30d fees on complete days (2026-10-04 → 2026-11-02):
  **$6,149,985**; trailing-30d revenue on complete days: **$2,100,314**;
  all-time fees **$58,417,651**, all-time revenue **$9,392,806**
  (API-reported). The capture ratio (revenue ÷ fees) is **34.2%** over the
  trailing 30 complete days versus **16.1%** all-time — we report the fact
  and do not assert a cause from this data alone. Annualised revenue
  run-rate at the trailing-30d pace: **~$25.6M**. Since 2026-02-23, per
  the DefiLlama NEAR Intents methodology, NEAR's captured Intents revenue
  is used to buy back $NEAR on the open market (not burned) — a direct
  pipe from usage to token demand. *(Mechanism per DefiLlama's published
  methodology; amounts are DefiLlama's data.)*
- **The footprint is verifiable and multi-chain.** Intents TVL by chain
  (protocol endpoint, latest points, 2026-11-04): **$202.1M across 26
  chains**, largest on NEAR itself (**$109.0M**) and Ethereum
  (**$58.8M**). This part of the "settlement pipe" story is reproducible
  from public data, not a press release.
- **Price does not simply mirror flow day-to-day.** Pearson correlation
  between daily Intents volume and daily NEAR price over the overlapping
  365 days is **r = 0.50** (n = 365); with 30-day rolling volume it is
  **r = 0.78**. Day-to-day price moves are mostly not volume moves — which
  is what "price is a noisy indicator of usage" predicts. (Method in
  `data/key_stats.json`.)

## Evidence against

- **The lead–lag test fails the strong claim (new in v1).** Cross-
  correlation of volume with price over lags −30…+30 days peaks at
  **lag +3 days for raw daily volume (r = 0.54)** and **lag +2 days for
  7-day rolling volume (r = 0.70)** — i.e. essentially at lag 0, not at a
  meaningful lead. Worse for the claim, the robustness check that avoids
  trend-inflation — 7-day % change in rolling volume vs *forward* price
  returns — shows no predictive content beyond a day: **r = +0.11 at 1d,
  −0.01 at 7d, +0.03 at 14d, +0.05 at 30d**. Volume growth does not
  forecast price. Anyone selling this thesis as "volume leads price"
  would be contradicted by our own dashboard (Panel 3,
  `data/leadlag.csv`).
- **Flow dwarfs the vault — value capture per dollar is thin.** NEAR chain
  TVL is only **~$187M** (live snapshot at the v1 rebuild, 2026-11-04;
  snapshots move intraday — it read ~$191M at the v0 rebuild) and Intents
  TVL **$202.1M** (2026-11-04) against $36.39B of cumulative flow and
  ~$3.97B of monthly flow. A single month of flow is ~20× the entire chain
  TVL. The effective takes are small: gross fees are **0.158%** of volume
  and captured revenue is **0.054%** of volume (trailing 30d). Even in the
  Panel 6 Bull scenario (4× volume at today's take rates), captured
  revenue — the buyback budget — is **~$104M/yr, about 2.0% of NEAR's
  market cap** (CoinGecko market cap $5.26B at rebuild); Base is ~$52M
  (1.0%), Bear ~$26M (0.5%). Scenario arithmetic, not a prediction — but
  it sizes the value-capture link honestly: currently weak.
- **The correlation cuts both ways.** r = 0.78 for rolling volume vs price
  means price is *not* blind to usage over this window; a sceptic can say
  the market already prices flow growth in trend terms, and the
  "decoupling" is mostly short-horizon noise. Our own numbers support
  that reading about as well as the claim.
- **Price fell on the milestone.** NEAR-reported $37B volume headlines
  (3 Nov) coincided with a weak price (latest in our series: **~$3.86 on
  2026-11-03**). Decoupling in the *down* direction is evidence that flow
  growth alone does not support price — the thesis needs the buyback/
  value-capture link to actually bind, and at ~$2.1M revenue per month it
  is currently small next to NEAR's market value.
- **Volume ≠ unique users.** DEX volume can be repeat, arbitrage, or
  solver-internal flow. We have not yet shown active-account growth to
  match volume growth; that cross-check needs the planned BigQuery layer.
- **Some headline NEAR figures are first-party only.** "37M+ swaps",
  Confidential Intents TVL (~$145M), the 1M+ NEAR staked for confidential
  AI inference and similar figures could not be reproduced from the
  public APIs used here. They appear on the dashboard only in Panel 5's
  clearly labelled attributed-claims box and are **not** used as evidence
  above.

## What would change my mind

- **(Partially triggered in v1.)** The lead–lag criterion: we said the
  "leading indicator" claim fails if volume lags or merely coincides with
  price. The v1 test shows coincidence (peak at lag +2/+3 days, no
  forward-return predictive content), so the *price* version of the claim
  is falsified on this data. What remains testable is whether volume leads
  *usage* metrics (fees, active accounts) rather than price — not yet
  tested.
- If daily active accounts / unique Intents users (BigQuery layer) are
  flat or falling while volume rises → volume is churn, not usage; the
  remaining claim fails too.
- If fees/revenue per $ of volume keeps compressing toward zero → the
  pipe grows but the token captures nothing; the investment version of
  the thesis fails even if the usage version holds.
- If Intents volume concentrates into a handful of solver/affiliate
  routes that can be switched off or migrate → flow is rented, not owned.

## Open questions

1. Does volume lead *usage* (fees, active accounts) even though it does
   not lead price? Same lead–lag machinery, different target series.
2. Active accounts and contract usage from NEAR BigQuery public dataset —
   do they corroborate the volume story? (Planned `/queries` layer.)
3. Who generates the volume? Concentration by chain pair / asset /
   integrator from DefiLlama breakdown data.
4. Confidential Intents: can any part of the private-layer growth be
   verified independently, or does it stay an attributed claim?
5. Buyback tracking: can on-chain buyback wallet flows be tied to the
   revenue series to close the value-capture loop with primary data?
6. Why is the trailing-30d capture ratio (34.2%) so far above the
   all-time ratio (16.1%) — mechanism change, mix shift, or a DefiLlama
   methodology artefact? Needs primary-source checking before use.
