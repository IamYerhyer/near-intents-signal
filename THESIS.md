# THESIS — Flow, Not Price (DRAFT — SKELETON)

**Status: DRAFT skeleton for NEAR HACKATHON, Investment Thesis track.**
All numbers below were computed by `rebuild.py` on 2026-11-04 from the
DefiLlama public APIs listed in README.md. Data as of **2026-11-03** (the
last day in the daily series). Re-run `python3 rebuild.py` to refresh them —
do not hand-edit numbers here without re-running.

## The claim

Cross-chain volume through NEAR Intents is a better leading indicator of
real network usage than the NEAR token price. (Hypothesis taken from the
official track prompt; we test it, we do not assume it.)

Working interpretation: NEAR's economic centre of gravity is shifting from
"an L1 you hold" to "a settlement pipe agents and users route through" —
and flow through that pipe (Intents volume, fees, revenue) shows it earlier
and more clearly than price or TVL do.

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
  printed **$137,911,779**.
- **The flow pays.** Trailing-30d fees on complete days (2026-10-04 →
  2026-11-02): **$6,149,985**; trailing-30d revenue on complete days:
  **$2,100,314**; all-time fees **$58,417,651**, all-time revenue
  **$9,392,806** (API-reported). Per NEAR's published mechanism (Feb 2026),
  captured Intents revenue funds open-market NEAR buybacks — a direct pipe
  from usage to token demand. *(Mechanism statement is NEAR's; the fee and
  revenue amounts above are DefiLlama's.)*
- **Price does not simply mirror flow.** Pearson correlation between daily
  Intents volume and daily NEAR price over the overlapping 365 days is
  **r = 0.50** (n = 365); with 30-day rolling volume it is **r = 0.78**.
  Interpretation is deliberately cautious: trend-level association exists,
  but day-to-day price moves are mostly not volume moves — which is what
  "price is a noisy indicator of usage" predicts. (Method in
  `data/key_stats.json`.)

## Evidence against

- **Flow dwarfs the vault — value capture per dollar is thin.** NEAR chain
  TVL is only **$191,352,059** (live snapshot at rebuild, 2026-11-04) and
  Intents TVL **$203,364,435** (protocol endpoint, 2026-11-04) against
  $36.39B of cumulative flow and ~$3.97B of monthly flow. A single month of
  flow is ~20× the entire chain TVL. If users route through NEAR without
  capital staying, the token's claim on that flow rests on a fee take of
  roughly $6.15M per $3.97B of monthly volume (~0.15%).
- **The correlation cuts both ways.** r = 0.78 for rolling volume vs price
  means price is *not* blind to usage over this window; a sceptic can say
  the market already prices flow growth in trend terms, and the "decoupling"
  is mostly short-horizon noise. Our own v0 numbers support that reading
  about as well as the claim.
- **Price fell on the milestone.** NEAR-reported $37B volume headlines
  (3 Nov) coincided with a weak price (latest in our series: **$3.84 on
  2026-11-03**). Decoupling in the *down* direction is evidence that flow
  growth alone does not support price — the thesis needs the buyback/value-
  capture link to actually bind, and at ~$2.1M revenue per month it is
  currently small next to NEAR's market value.
- **Volume ≠ unique users.** DEX volume can be repeat, arbitrage, or
  solver-internal flow. We have not yet shown active-account growth to
  match volume growth; that cross-check needs the planned BigQuery layer.
- **Some headline NEAR figures are first-party only.** "37M+ swaps",
  Confidential Intents TVL (~$145M) and AI-inference staking figures could
  not be reproduced from the public APIs used here and are **not** used as
  evidence above.

## What would change my mind

- If daily active accounts / unique Intents users (BigQuery layer) are flat
  or falling while volume rises → volume is churn, not usage; claim fails.
- If a proper lead–lag test (volume changes vs *future* price/usage changes)
  shows volume lags or merely coincides with price → "leading indicator"
  fails even if correlation survives.
- If fees/revenue per $ of volume keeps compressing toward zero → the pipe
  grows but the token captures nothing; the investment version of the
  thesis fails even if the usage version holds.
- If Intents volume concentrates into a handful of solver/affiliate routes
  that can be switched off or migrate → flow is rented, not owned.

## Open questions

1. Lead–lag structure: does a volume shock precede changes in price, fees,
   or active accounts by days/weeks? (Planned for v1.)
2. Active accounts and contract usage from NEAR BigQuery public dataset —
   do they corroborate the volume story? (Planned `/queries` layer.)
3. Who generates the volume? Concentration by chain pair / asset /
   integrator from DefiLlama breakdown data.
4. Confidential Intents: can any part of the private-layer growth be
   verified independently, or does it stay an attributed claim?
5. Buyback tracking: can on-chain buyback wallet flows be tied to the
   revenue series to close the value-capture loop with primary data?
