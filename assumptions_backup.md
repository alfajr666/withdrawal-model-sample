# Assumptions Document — Crypto Exchange Liquidity Stress Testing
*Written before any code. All parameters trace back to this document.*

---

## Status
**Version:** 1.0  
**Date:** 2026-02-21  
**Author:** Model Architecture  
**Review Required Before:** Any parameter change in `config.py`  

---

## 1. User Base

| Parameter | Value | Rationale |
|---|---|---|
| Total users | 100,000 | Represents a mid-sized exchange. Large enough for law of large numbers; small enough to run on commodity hardware. |
| Retail share | 95% of accounts | Consistent with empirical distribution at major CEXs where institutional accounts are rare but highly concentrated. |
| Institutional share | 5% of accounts | Hedge funds, proprietary trading desks, OTC desks, crypto-native funds. |
| Institutional balance share | ~65% of total fiat | Heavy-tail Pareto dynamic: few actors hold most of the liquidity. Gini coefficient ~0.85–0.94. Industry observation: on most exchanges, the top 5% of accounts control >60% of assets. |
| Balance distribution | Log-normal (μ=8.5, σ=2.2 for retail; μ=13.5, σ=1.8 for institutional) | Log-normal is the standard distributional assumption for wealth. Heavy right tail. Parameterized to produce Gini ~0.85–0.94. |

**Key implication:** The institutional cohort is the primary tail risk driver even though they are 5% of accounts. Any stress test that focuses on retail withdrawal rates is modeling the wrong population.

---

## 2. Withdrawal Behavior

### Retail (Gamma Distribution)
| Parameter | Normal | Mild Stress | Severe Stress |
|---|---|---|---|
| Daily withdrawal rate (% of total fiat) | 1–3% | 5–8% | 20–40% |
| Distribution shape | Gamma | Gamma | Gamma |

**Rationale for Gamma:**
- Aggregate of many independent small decisions → Central Limit Theorem applies to the aggregate flow, but the distribution is bounded at zero (no negative withdrawals) and right-skewed (occasional burst days).
- Gamma is the maximum-entropy distribution given a positive constraint and known mean/variance.
- Under stress, mean shifts right and variance increases (panic is fat-tailed even at the retail level).

**Failure mode acknowledged:** Gamma assumes independence across retail users. Correlated panic (social media contagion, exchange outage rumors) is not modeled in v1. Named enhancement: add spatial correlation via copula in v2.

### Institutional (Poisson Jump Process)
| Parameter | Normal | Mild Stress | Severe Stress |
|---|---|---|---|
| Arrival rate (events/day) | 0.5 | 2.0 | 6.0 |
| Jump size distribution | Log-normal | Log-normal | Log-normal |
| Jump size μ (log scale) | 13.5 | 14.2 | 15.0 |
| Jump size σ (log scale) | 1.0 | 1.2 | 1.5 |
| Lead time vs retail | — | ~3–4 hrs | ~6–8 hrs |

**Rationale for Poisson + Log-normal:**
- Institutional withdrawals are rare, large, discrete events. Poisson governs arrival rate of such events.
- Jump sizes are log-normally distributed: most withdrawals are moderate; occasional withdrawals are catastrophic (right-tailed).
- The 12x arrival rate multiplier (0.5 → 6.0/day) from normal to severe stress is the **primary driver of tail risk** in this model, not retail flows.
- Informed institutional actors observe on-chain data, order flow, and market structure signals and move 6–8 hours ahead of retail panic. This lead time is operationally critical: it is the detection window for FinOps.

**Failure mode acknowledged:** Poisson assumes independent arrivals. In reality, one large fund exiting signals to others — herding causes clustering. A Hawkes (self-exciting) process would capture this. Named v2 enhancement.

---

## 3. Market Data

| Parameter | Normal Regime | Stressed Regime | Crisis Regime |
|---|---|---|---|
| BTC daily drift (μ) | +0.10% | -0.30% | -1.00% |
| BTC daily vol (σ) | 3.5% | 7.0% | 15.0% |
| ETH daily vol (σ) | 4.5% | 9.0% | 18.0% |
| ALT daily vol (σ) | 6.0% | 12.0% | 25.0% |
| BTC-ETH correlation | 0.82 | 0.90 | 0.95 |
| BTC-ALT correlation | 0.70 | 0.85 | 0.92 |
| Regime probability | 88% | 10% | 2% |

**Markov Transition Matrix:**
```
                  → Normal  → Stressed  → Crisis
From Normal:        0.98      0.018       0.002
From Stressed:      0.15      0.80        0.05
From Crisis:        0.05      0.25        0.70
```
**Calibration rationale:** Regime persistence is high (crisis regimes are autocorrelated). The 2% crisis unconditional probability matches rough empirical frequency of major crypto dislocations (roughly 7–10 days/year in extreme years like 2022). Transition probabilities set so mean regime duration: Normal ~50 days, Stressed ~20 days, Crisis ~3 days.

---

## 4. Parametric Scenario Shocks (VaR Overlay)

| Scenario | BTC Shock | ETH Shock | ALT Shock | Basis |
|---|---|---|---|---|
| Mild | -25% | -32% | -45% | Typical correction; 2021 May crash range |
| Severe | -50% | -60% | -75% | FTX collapse range; 2022 bear market lows |
| LUNA-style | -40% | -48% | -88% | UST/LUNA May 2022; altcoin contagion dominates |

---

## 5. Reserve Tiering

| Layer | Sized By | Instrument | Liquidity | Yield Assumption |
|---|---|---|---|---|
| Layer 1 — Instant | max(HS-VaR, FHS-VaR) | Fiat in payment gateways / bank accounts | Immediate | ~0% |
| Layer 2 — Fast | Gap between VaR and Gamma/Poisson p95 | Money market funds; stablecoins (secondary) | Hours | ~4–5% |
| Layer 3 — Liquid | Gap to Gamma/Poisson p99 + insurance fund obligations | T-bills | 1–2 business days | ~4–5% |

**Stablecoin caveat (critical):** Stablecoins are operationally near-cash but *systemically correlated* with crypto stress. USDC depegged to $0.87 during SVB failure (March 2023) — precisely during a crypto risk event. Layer 2 should hold stablecoins as a *minority* fast-access allocation, not the primary instrument. Money market funds and T-bills are preferred.

---

## 6. Reserve Optimization (Newsvendor)

| Parameter | Value | Rationale |
|---|---|---|
| Opportunity cost | 4–5% annualized | Yield available on T-bills / money market funds. Mid-2020s rate environment. |
| Emergency liquidity cost | 8–10% annualized | Cost of credit line draw or forced crypto liquidation at distressed prices. Conservative estimate. |
| Optimization objective | Minimize expected total cost = opportunity cost on excess reserve + shortfall cost on deficit | Standard newsvendor framework applied to liquidity management. |

**Key insight:** The newsvendor optimum is a specific quantile of the withdrawal distribution determined by the cost ratio: `q* = emergency_cost / (opportunity_cost + emergency_cost)`. With costs of 5% and 9%, q* ≈ 64th percentile. CVaR at 99th percentile gives the conservative upper bound.

---

## 7. VaR Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Historical lookback | 365 days | One full year captures normal and mildly stressed periods. |
| EWMA decay factor (λ) | 0.94 | RiskMetrics standard. Effective sample size = 1/(1-0.94) ≈ 17 obs; weights decay to near zero within ~55 days. |
| Stressed VaR window | 90 days (worst in dataset) | Basel III-inspired. Uses worst consecutive 90-day period to size the tail reserve. |
| VaR confidence level | 99% | Industry standard for regulatory VaR. |
| CVaR level | 99% | Expected shortfall beyond the 99th percentile. |

**EWMA diagnostic:** Report effective sample size (ESS = 1/(1-λ)) as a transparency metric. At λ=0.94, ESS ≈ 17 days — the model is almost entirely pricing current volatility, not historical. Appropriate for fast-moving crypto but loses memory of older tail events.

---

## 8. Derivatives / Insurance Fund

| Parameter | Value | Rationale |
|---|---|---|
| Open interest to AUM ratio | 1.5x | Moderate derivatives exchange. Aggressive exchanges exceed 3x. |
| Number of traders modeled | 5,000 | Statistically sufficient to model cascade dynamics. |
| Initial insurance fund | 0.5% of AUM | Industry norm for major exchanges (Binance, OKX range: 0.3–1%). |
| Retail leverage (typical) | 10–20x | High frequency, lower leverage: impulsive but smaller notional. |
| Institutional leverage (typical) | 5–15x | Higher capital, more disciplined, but larger notional per position. |
| CFD equity correlation (BTC-Stock) | 0.35 normal → 0.70 crisis | US stock CFDs via equity prime brokerage. Correlation spikes during risk-off episodes as all risk assets sell simultaneously. |
| Cascade steps | 5 | Each liquidation wave creates price pressure → triggers next wave. 5 steps generally sufficient to reach equilibrium in simulation. |

**Cascade mechanism:** Liquidated notional creates market sell pressure proportional to OI/AUM ratio. Each cascade step: (1) compute underwater positions, (2) force-close them, (3) calculate market impact, (4) apply additional price move, (5) recheck for further liquidations. Repeat 5x.

---

## 9. Simulation Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Monte Carlo paths | 10,000 | Sufficient for stable 99th percentile estimates. Standard in market risk. 95% CI on 99th pctile from 10K paths is approximately ±0.3%. |
| Weekend horizon | 64 hours | Friday 5PM to Monday 9AM. Bank rails offline during this window. |
| Seed | 42 | Reproducibility. |

---

## 10. Out of Scope (v1) — Named Limitations

| Item | Why Excluded | Planned Version |
|---|---|---|
| **Hawkes process** (self-exciting arrivals for institutional herding) | Adds significant complexity; calibration requires tick data. Named as the most material v1 limitation — institutional arrivals cluster in reality. | v2 |
| **Multi-currency fiat** (EUR, GBP) | Requires separate buffer per currency + FX risk layer | v2 |
| **Rehypothecation** | Requires off-balance-sheet data; standard PoR omits it | v2 |
| **Crypto-to-fiat liquidation dynamics** | Liquidation curve modeling | v2 |
| **Cross-exchange contagion** | Network effects; multi-entity model | v3 |
| **Intraday granularity (sub-hourly)** | Hourly resolution sufficient for weekend buffer | v2 |
| **Panic correlation across retail** | Copula-based dependency structure | v2 |

---

*End of assumptions document. All parameters above are replicated exactly in `config.py`. Any parameter change must update this document first.*
