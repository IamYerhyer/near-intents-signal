# Flow, Not Price: What NEAR Intents Volume Actually Tells Us (DRAFT)

**Status: DRAFT — for NEAR HACKATHON, Investment Thesis track.**
**Author: Shuaibu Yahaya — independent Web3 research and content specialist
since 2020, based in Nigeria.**
Every figure is computed by `rebuild.py` from the appendix sources
(data as of 2026-11-03 unless stated).

## 1. Summary

I tested whether cross-chain volume through NEAR Intents is a better
leading indicator of real network usage than the NEAR token price. The
data says no — not for price: volume and price move together, and
volume growth predicts nothing at any horizon I tested. What the
data does support is narrower and more useful: Intents volume is a
large, fast-growing, independently verifiable measure of real economic
flow, and the share of its fees that NEAR captures has roughly doubled,
to 34.2% over the last 30 complete days against 16.1% all-time. NEAR
captures very little per dollar of flow — 0.054% — but the mechanism
exists, is documented in primary sources, and is improving.
That is the case the evidence supports.

## 2. The claim I tested — and the one that survives

The original claim, from the official track prompt: cross-chain volume
through NEAR Intents is a better *leading* indicator of real network
usage than token price. Behind it is an interpretation I wanted to
check: NEAR's centre of gravity is shifting from "an L1 you hold"
to "a settlement pipe users and agents route through" — and that flow
would show the shift before price did.

The revised claim that survives my own tests is weaker, in two parts.
First, Intents volume is a *coincident*, real-time gauge of usage — it
measures settlement that has actually happened, where daily price is
mostly noise — even though it does not lead price. Second, the long-term
case rests not on volume but on value capture: whether the fee switch
keeps converting flow into captured revenue at a rising share.

## 3. How I tested it

Sources: DefiLlama's public APIs (daily Intents volume, fees, revenue,
TVL by chain, NEAR chain TVL, daily price) and CoinGecko (market-cap
snapshot). One command
(`python3 rebuild.py`, standard library only, no keys) rebuilds every
figure from raw responses saved in `data/raw/`.

Two data-quality decisions are worth stating. First, the final fees day
(2026-11-03) is incomplete: it shows fees of $9,319 against same-day
revenue of $44,928 — impossible for a complete day, since revenue is a
subset of fees. The script flags it as partial and excludes it from
computed trailing-30-day sums (API totals stored separately,
labelled). Second, on method: I report correlations in
levels, but levels of two rising series are inflated by their shared
trend, so the lead–lag verdict rests on a robustness check in changes —
whether volume growth predicts *forward* price returns. Figures I
could not compute from these sources are not used; unreproducible
claims sit in the appendix, labelled and unverified.

## 4. Evidence for

- **The flow is real, and the arithmetic checks out two ways.**
  Cumulative Intents volume computed from the daily series is
  $36,386,550,029 ($36.39B) as of 2026-11-03 — exactly DefiLlama's own
  reported all-time total.
- **Growth is steep and recent.** Cumulative milestones from the
  series: $22,239,779,942 by 2026-06-30, $29,281,035,154 by 2026-09-15,
  $36,386,550,029 by 2026-11-03. Trailing-30-day volume was
  $3,970,607,022 (annualised run-rate $48,309,052,101).
- **Volume tells you something price does not, day to day.** Daily
  volume against daily price over 365 overlapping days gives r = 0.50:
  much of daily price is noise relative to settled flow. As a
  coincident gauge, volume is the cleaner instrument.
- **Capture is improving.** The capture ratio (revenue ÷ fees) is
  34.2% over the trailing 30 complete days against 16.1% all-time.
  Section 6 sets out the primary-source check on why.
- **The footprint is verifiable and multi-chain.** Intents TVL by
  chain, from the public protocol endpoint (2026-11-04), is $202,140,501
  across 26 chains, largest on NEAR itself ($109,017,683) and Ethereum
  ($58,839,325). Public data, not a press release.

## 5. Evidence against

- **The lead–lag test fails the strong claim.** Cross-correlation over
  lags of −30 to +30 days peaks at +3 days for raw daily volume
  (r = 0.54) and +2 days for 7-day rolling volume (r = 0.70) — at zero,
  in practice. The robustness check is worse: 7-day volume growth
  against forward price returns gives r = +0.11 at 1 day, −0.01 at
  7 days, +0.03 at 14 days and +0.05 at 30 days. Volume growth has no
  predictive content for price; "volume leads price" is contradicted
  by this data.
- **The trend correlation cuts the other way.** With 30-day rolling
  volume, correlation with price is r = 0.78. A sceptic can fairly say
  the market already prices flow growth in trend terms, and the
  "decoupling" is mostly short-horizon noise. My numbers support that
  reading about as well as mine.
- **Flow is not the vault, and the take is thin.** NEAR chain TVL was
  $186,509,946 in the snapshot taken at the v1 rebuild (2026-11-04)
  against $36.39B of cumulative flow; one month of flow is roughly
  twenty times the entire chain TVL. Gross fees are 0.158% of volume,
  captured revenue 0.054% (trailing 30 days). High-velocity flow, not
  locked capital — and the token's slice of it is small.
- **Volume is not users.** DEX volume can be repeat, arbitrage or
  solver-internal flow. I have not yet matched volume growth to
  active-account growth — that cross-check needs the BigQuery layer
  (question 2). Until then, "usage" here means settled flow, not people.

## 6. The value-capture case

All-time, Intents has generated $58,417,651 in gross fees and
$9,392,806 in captured revenue — a 16.1% capture ratio. Over
the trailing 30 complete days (2026-10-04 to 2026-11-02), fees were
$6,149,985 and captured revenue $2,100,314 — the 34.2% ratio, which
annualises to $25,553,820. The mechanism, per DefiLlama's methodology:
captured revenue is NEAR or wNEAR swept into NEAR's revenue wallets
(reconciling with revenue.near.org), and since 2026-02-23 it is used to
buy back NEAR on the open market. It is not burned.

**Why did the ratio jump? Primary sources confirm a mechanism, not a
data error.** On 2026-02-23 NEAR Intents
activated its fee switch. DefiLlama's own adapter code
(dimension-adapters PR #7738, merged 19 June 2026) defines revenue as
the protocol fee plus NEAR's own frontends' affiliate fees — third-party
affiliate fees are supply-side, not revenue — and attributes captured
revenue to buybacks only from 2026-02-23, to treasury before that date.
Its monthly series shows captured revenue at or near zero from May to
October 2025 while gross fees were already in the millions: the all-time
ratio averages a pre-capture era with the current one. Nansen's Q3 2026
report shows the same shape in NEAR's own reported figures — lifetime
capture of 16.4% (update dated 6 October) against trailing-30-day
capture of 28.4%. One documented but unquantified contributor: NEAR's
own frontends' affiliate fees count as revenue, so growth in near.com's
share of flow (about a quarter of Q3 volume, per Nansen) lifts the
ratio mechanically.

**Scenario arithmetic** (from `data/model_outputs.json`; assumptions in
`model_config.json`). Holding the observed take rate (0.158%) and
capture ratio (34.2%) constant, and scaling only volume against the
$48,309,052,101 run-rate and the $5,262,407,956 market cap (CoinGecko
snapshot at the v1 rebuild):

| Scenario | Annual volume | Gross fees | Captured revenue (= buyback) | % of market cap |
| --- | --- | --- | --- | --- |
| Bear (1.0×) | $48,309,052,101 | $76,237,150 | $26,036,154 | 0.49% |
| Base (2.0×) | $96,618,104,202 | $152,474,300 | $52,072,307 | 0.99% |
| Bull (4.0×) | $193,236,208,404 | $304,948,600 | $104,144,614 | 1.98% |

This is arithmetic, not a forecast, and makes no price prediction:
the buyback is real and scales with flow, but even at 4× volume it
reaches only ~2% of market cap per year — a slow compounding claim,
not a repricing claim.

## 7. What would change my mind

- **Already partially triggered:** the lead–lag criterion. The
  "leading indicator" claim fails if volume merely coincides with
  price. It does, so the price version is falsified on this data. What
  remains testable is whether volume leads *usage* metrics, not price.
- If active accounts or unique users (BigQuery layer) are flat or
  falling while volume rises, the flow is churn, not usage, and the
  revised claim fails too.
- If the capture ratio falls back toward the all-time 16.1%, or the fee
  take rate compresses toward zero, the token captures nothing and the
  value-capture leg fails.
- If on-chain buyback wallet flows cannot be tied to the revenue
  series, the mechanism is accounting, not demand, and the capture
  case falls.
- If volume concentrates into a few switchable integrator routes, the
  flow is rented, not owned, and the durability assumption behind
  Section 6 fails.

## 8. Open questions

1. Does volume lead *usage* — fees and active accounts — even though
   it does not lead price? Same machinery, different target series.
2. Active accounts and unique users from the NEAR BigQuery public
   dataset: do they corroborate the volume story? (Planned `/queries`
   layer; the dashboard does not depend on it.)
3. Who generates the volume — concentration by chain pair, asset and
   integrator?
4. Confidential Intents: can any of the private-layer growth be
   verified independently, or does it stay an attributed claim?
5. Can on-chain buyback wallet flows be tied to the revenue series,
   closing the value-capture loop with primary data?
6. **The capture-ratio jump — checked against primary sources on
   2026-11-04: CONFIRMED mechanism.** The 2026-02-23 fee switch is the
   structural break (Section 6): buyback attribution in DefiLlama's
   adapter starts on that date, treasury before it, and captured
   revenue was near zero through October 2025 while fees were in the
   millions, dragging the all-time ratio to 16.1%. Still
   open: how much of the rise since is mix shift (own-frontends' share)
   versus fee schedule. One caveat: DefiLlama rewrote this adapter in
   June 2026 (revenue source moved from the then-dead revenue.near.org
   API to a Dune query), so cross-era comparison rests on the current
   backfilled methodology.

## 9. Appendix

**Attributed first-party claims — labelled, unverified, not used as
evidence anywhere above.** From NEAR Protocol communications
(dashboard Panel 5): NEAR reported cumulative Intents
volume of $37B and 37M+ swaps on 3 November 2026; Confidential Intents
TVL of roughly $145M; more than 1M NEAR staked for confidential AI
inference; and Brave Leo private inference on NEAR AI Cloud from
15 October 2026. None of these could be reproduced from the public
APIs used here: claims, not findings.

**Sources.**

- DefiLlama daily volume / fees / revenue —
  https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume ;
  https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees ;
  https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue
- DefiLlama daily price — https://coins.llama.fi/chart/coingecko:near
  (exact per-run URL in `data/key_stats.json`)
- DefiLlama chain TVL; Intents TVL by chain —
  https://api.llama.fi/v2/chains ;
  https://api.llama.fi/v2/historicalChainTvl/Near ;
  https://api.llama.fi/protocol/near-intents
- DefiLlama Intents page, methodology (buyback since 2026-02-23) —
  https://defillama.com/protocol/near-intents
- DefiLlama dimension-adapters PR #7738 (revenue definition; buyback
  attribution from 2026-02-23, treasury before) —
  https://github.com/DefiLlama/dimension-adapters/pull/7738
- Nansen, *NEAR Q3 2026 Report*, 20 Oct 2026 (lifetime capture 16.4%
  vs trailing-30-day 28.4%; near.com ~a quarter of Q3 volume) —
  https://nansen.ai/post/near-q3-2026-report
- CoinGecko markets API (market cap) —
  https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=near
