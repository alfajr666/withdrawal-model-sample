# Liquidity Sentinel
### Crypto Exchange Withdrawal & Solvency Stress Testing

A stress testing framework that models the fiat liquidity and solvency of a crypto exchange under realistic withdrawal scenarios — addressing a structural gap that standard Proof of Reserve (PoR) frameworks do not cover.

**[Live Dashboard →](https://alfajr666.github.io/withdrawal-model-sample/dashboard/)**

---

## The Problem with Proof of Reserve

Proof of Reserve attestations verify that an exchange holds crypto assets ≥ crypto liabilities at a point in time. The Merkle tree approach lets individual users verify their balance is included. This is useful — but incomplete in three ways that matter.

**The fiat dimension is invisible.** PoR confirms crypto asset backing. It says nothing about whether the exchange can process USD/EUR withdrawals over a weekend when bank transfer rails are offline (Friday 5PM – Monday 9AM). This is precisely when crypto market stress events cluster — the moment banks are unreachable is the same moment panic withdrawal demand peaks.

**Asset quality is not stress-tested.** Holding 100% of user funds in the exchange's own native token (e.g., FTT) passes a static PoR snapshot. It collapses under redemption pressure. A static check cannot answer: *at what withdrawal velocity does this portfolio become insufficient?*

**The 1:1 rule breaks for derivatives exchanges.** A spot-only exchange must hold user funds 1:1 — PoR is mostly sufficient. The moment an exchange introduces perpetual futures or CFD equity, it creates a socialized loss problem: when a user's margin is insufficient to cover their loss, the exchange absorbs the deficit from its insurance fund. This liability is invisible to PoR entirely.

This project builds the dynamic stress testing layer that sits on top of PoR data. The FTX collapse (November 2022, ~$6B withdrawn in 72 hours) is the canonical calibration case.

---

## What This Model Solves

The primary perspective is the **Financial Operations (FinOps) / Treasury team**. The core operational problem: *how much fiat must we hold entering a weekend to cover withdrawals, given that bank rails will be unavailable for 64 hours?*

This is a cash buffer optimization problem with a fundamental tension. Holding too much idle fiat is capital-inefficient — that capital could earn 4–5% annualized in T-bills or money market funds. Holding too little risks being unable to fulfill withdrawals, with emergency liquidity costing 8–10% annualized. The model quantifies both sides and finds the optimal balance.

For derivatives exchanges, a second problem runs in parallel: *how large does the insurance fund need to be to absorb the socialized losses from a liquidation cascade without requiring clawback from profitable traders?*

The model outputs concrete, actionable numbers: a dollar reserve recommendation, its annual opportunity cost, the probability of shortfall at each scenario, and the minimum capital required for solvency across all risk dimensions.

---

## Model Architecture

```
liquidity-sentinel/
├── assumptions.md              ← Start here. All parameters explicit and documented.
├── config.py                   ← Central parameter store. Change inputs here only.
├── data/
│   ├── generator.py            ← Synthetic user base + withdrawal time series
│   └── market_data.py          ← Regime-switching price history (GBM + Markov chain)
├── models/
│   ├── withdrawal_forecast.py  ← Monte Carlo withdrawal forecasting (Gamma + Poisson)
│   ├── historical_var.py       ← Hybrid VaR: HS + EWMA-filtered + stressed + scenarios
│   ├── reserve_optimizer.py    ← Newsvendor optimization + cost curve
│   ├── stress_test.py          ← Three-scenario engine + time-to-insolvency
│   ├── insurance_fund.py       ← Derivatives socialized loss + liquidation cascade
│   └── solvency.py             ← Unified stressed balance sheet integrator
├── notebooks/
│   └── analysis.ipynb          ← Full walkthrough with visualizations
└── dashboard/
    └── index.html              ← Interactive web dashboard
```

---

## Methodology

### 1. User Base and Balance Distribution

The synthetic exchange has 100,000 users with a **log-normal balance distribution** — the standard choice for financial wealth distributions, capturing the long right tail of large accounts. 5% of accounts are institutional (hedge funds, OTC desks, corporate treasuries), holding ~65% of total fiat balances.

This concentration is the central planning challenge. Average-based reserve sizing is dangerous when the top 1% of accounts controls the majority of exposure. The model treats retail and institutional accounts as structurally different processes — not just different sizes of the same behavior.

### 2. Two-Process Withdrawal Model

Retail and institutional withdrawals are modeled as fundamentally different types of random processes.

**Retail withdrawals → Gamma distribution.** Retail behavior is a continuous aggregate flow: thousands of small, independent decisions summing together each hour. No single decision matters. The result is smooth, always positive, and clusters around a mean — exactly what the Gamma distribution captures. It is the natural choice for aggregate flows because it handles the right-skew and positive support without forcing a normal approximation.

**Institutional withdrawals → Poisson jump process.** Institutional behavior is discrete and lumpy. A hedge fund doesn't gradually trickle out — it decides to withdraw $50M on a specific day, then nothing for weeks, then a large amount the moment something looks wrong. The right model is not a flow rate but a series of *events arriving at random times* with *random sizes*. Poisson governs the arrival of events; log-normal governs the size of each jump.

The critical parameter is the **Poisson arrival rate under stress**. In normal conditions: ~0.5 institutional events per day. In a severe scenario: ~6 events per day. That 12× increase in arrival rate — not the jump size — is the primary driver of tail risk. In severe scenarios, institutional withdrawals also lead retail by ~6–8 hours, giving FinOps a detection window before the retail panic peaks.

This two-process architecture matters because it proves a point about PoR: a point-in-time balance sheet snapshot cannot tell you anything about arrival rates. The gap between what PoR shows and what this model measures is precisely the jump process behavior.

### 3. Hybrid VaR — Three Layers

VaR is used for the market risk dimension and as an anchor for the operating reserve. The model implements three methods, each serving a different purpose, combined into a two-tier reserve recommendation.

**Historical Simulation (HS-VaR).** Purely empirical: sort the past 365 days of P&L and read off the quantile. No distributional assumption. Captures whatever fat-tailed, regime-switching behavior existed in the data. The limitation is structural — it can only see losses that already occurred in the lookback window. Every major crypto crisis (LUNA May 2022, FTX November 2022, COVID March 2020) was an out-of-sample event for HS-VaR at the time it happened.

**EWMA-Filtered Historical Simulation (FHS-VaR).** Weights recent observations more heavily using exponential decay (λ = 0.94, the RiskMetrics standard). Partially addresses the staleness problem by making the model more responsive to current volatility. The diagnostic to watch is the **effective sample size (ESS)** — at λ = 0.94, ESS ≈ 32 days. This means the model is almost entirely pricing current conditions, not history. It will give false comfort in a calm market.

**Stressed VaR.** Computes VaR using only the worst 90-day window in the return history, calibrated to the worst observed crypto drawdown period. Inspired by Basel III's stressed VaR requirement for banks. This is the forward-looking floor — sized to survive the worst period already observed, regardless of current conditions.

**Parametric scenario shocks** are layered on top as a ceiling: direct price shocks calibrated to LUNA (-40% BTC), FTX (-50% BTC), and a generic severe scenario (-50% BTC, -60% ETH, -75% ALT).

The output is a **two-tier reserve structure**:
- **Tier 1 (operating minimum):** `max(HS-VaR CVaR99, FHS-VaR CVaR99)` — the empirically-anchored floor
- **Tier 2 (crisis minimum):** `max(Stressed VaR CVaR99, worst parametric scenario)` — the forward-looking ceiling

The gap between Tier 1 and Tier 2 is the *cost of tail protection* — a concrete annual figure that management can debate and own.

### 4. Three-Layer Operational Reserve

The two statistical tiers map directly to real treasury instruments, because the *composition* of a reserve matters as much as its *size*.

| Layer | Sized By | Instrument | Liquidity | Yield |
|---|---|---|---|---|
| Layer 1 — Instant | Historical VaR (Tier 1) | Fiat in payment gateway | Zero delay | ~0% |
| Layer 2 — Fast | Gap to Gamma/Poisson p95 | Stablecoins, overnight repo | Hours | ~4–5% |
| Layer 3 — Liquid | Gap to Gamma/Poisson p99 | T-bills, money market funds | 1–2 business days | ~4–5% |

One important caveat on Layer 2: stablecoins are operationally near-cash but *systemically correlated* with crypto stress. USDC briefly depegged during the SVB collapse (March 2023) — precisely during a risk event. Layer 2 should be predominantly money market funds and short-duration T-bills, with stablecoins as a smaller fast-access component, not the other way around.

### 5. Reserve Optimization — Newsvendor Framework

The optimal reserve is found by minimizing the expected total cost:

```
E[Cost] = p_over × E[max(0, R - W)] + p_under × E[max(0, W - R)]
```

Where `p_over` is the opportunity cost of holding idle fiat (~4–5% annualized) and `p_under` is the emergency liquidity cost when the reserve is exhausted (~8–10% annualized, from credit line drawdown or forced crypto liquidation).

The closed-form solution — the **critical ratio** `p_under / (p_over + p_under)` — gives the cost-minimizing quantile of the withdrawal distribution. Intuitively: the higher the emergency cost relative to the opportunity cost, the more conservative the reserve should be.

For a risk-averse FinOps team, the model also outputs the **CVaR-based reserve** at p99 — the expected withdrawal given the worst 1% of scenarios. The difference between the newsvendor optimal and the CVaR reserve is the explicit cost of choosing conservatism over efficiency.

### 6. Insurance Fund and Liquidation Cascade

For exchanges offering perpetual futures or CFD equity, the solvency model adds a derivatives dimension.

A population of 5,000 traders is generated with segmented leverage distributions — retail traders averaging higher leverage than institutional. When a price shock occurs, positions are marked to market and accounts with insufficient margin are liquidated. The model computes whether the exchange's insurance fund covers the shortfall or whether clawback from profitable traders is required.

The cascade effect is explicitly modeled: liquidated notional exerts selling pressure, amplifying the initial price move, triggering more liquidations. This feedback loop — well-documented in the March 2020 and May 2021 crashes — can multiply the initial shock significantly. The model runs five cascade iterations per simulation path.

The insurance fund module outputs the probability of fund exhaustion and the expected clawback amount under each scenario. These feed directly into the unified solvency assessment.

### 7. Unified Stressed Balance Sheet

The top-level `solvency.py` module combines all risk dimensions into a single balance sheet:

**Liabilities (stressed):**
1. Fiat withdrawal demand (Gamma/Poisson p99)
2. Insurance fund drawdown (derivatives cascade p99)
3. Market risk VaR (Tier 1 or Tier 2 depending on scenario)

**Assets / Buffers:**
1. Fiat reserve (the operational buffer)
2. Insurance fund balance
3. Proprietary capital / exchange equity

The solvency verdict — solvent or insolvent — and the capital adequacy ratio are computed for each scenario. For a derivatives exchange under severe stress, the model typically shows insolvency at standard reserve levels. This is the intended result: it quantifies exactly how much additional capital is required to survive a tail event.

---

## Key Outputs

| Output | Module | Description |
|---|---|---|
| Withdrawal distribution by scenario | `withdrawal_forecast.py` | Monte Carlo P&L distribution, VaR and CVaR at p95/p99 |
| Optimal fiat reserve | `reserve_optimizer.py` | Dollar amount, % of fiat, annual opportunity cost |
| Safety frontier curve | `stress_test.py` | Failure rate vs. reserve level across the full range |
| Time to insolvency | `stress_test.py` | Hour of reserve breach, conditional on failure |
| Two-tier VaR reserve | `historical_var.py` | Operating minimum vs. crisis minimum with cost of gap |
| Insurance fund drawdown | `insurance_fund.py` | Distribution of IF drawdown, P(exhaustion), expected clawback |
| Stressed balance sheet | `solvency.py` | Full liability vs. asset breakdown, solvency verdict per scenario |

---

## Stress Scenarios

| Scenario | Trigger | Withdrawal Rate | Institutional Arrival Rate | Calibration |
|---|---|---|---|---|
| Normal Operations | Baseline weekend | 1–3% of balances/day | 0.5 events/day | Empirical baseline |
| Mild Stress | 20–30% crypto drawdown | 5–8% of balances/day | 2.0 events/day | May 2021 correction |
| Severe Stress | Contagion / confidence loss | 20–40% in 48–72 hrs | 6.0 events/day | FTX, November 2022 |

---

## Usage

### Installation

```bash
git clone https://github.com/alfajr666/withdrawal-model-sample.git
cd withdrawal-model-sample
pip install -r requirements.txt
```

### Run the full solvency assessment

```python
from data.generator import generate_user_base, describe_user_base
from models.withdrawal_forecast import forecast_all_scenarios
from models.reserve_optimizer import optimize_reserve
from models.solvency import run_full_solvency_assessment, summarize_solvency

users      = generate_user_base()
stats      = describe_user_base(users)
total_fiat = stats["total_fiat_balance"]
total_aum  = total_fiat * 1.3

assessment = run_full_solvency_assessment(total_fiat=total_fiat, total_aum=total_aum)
print(summarize_solvency(assessment).to_string(index=False))
```

### Run withdrawal stress test only

```python
from models.withdrawal_forecast import forecast_all_scenarios
from models.stress_test import run_full_stress_test, summarize_stress_test

forecasts = forecast_all_scenarios(total_fiat)
opt       = optimize_reserve(forecasts["severe"]["simulated_totals"], total_fiat)
results   = run_full_stress_test(reserve=opt["cvar_reserve"], total_fiat=total_fiat)
print(summarize_stress_test(results).to_string(index=False))
```

### Use real PoR data

The model is designed to accept real Proof of Reserve data. Binance, OKX, and others publish Merkle tree-based attestations publicly. Substitute the synthetic `total_fiat` with the real figure:

```python
REAL_TOTAL_FIAT = 4_800_000_000  # from published PoR report
assessment = run_full_solvency_assessment(
    total_fiat=REAL_TOTAL_FIAT,
    total_aum=REAL_TOTAL_FIAT * 1.3,
)
```

### Configure assumptions

All parameters live in `config.py`. See `assumptions.md` for the full rationale behind each value. Changing a parameter in `config.py` propagates through every module automatically — nothing is hardcoded in individual files.

---

## Known Limitations (v1)

These are real risks deliberately excluded from v1 to keep the core model clean and auditable. They are candidates for future versions, not oversights.

| Limitation | Impact | Planned |
|---|---|---|
| Poisson assumes independent arrivals | Underestimates herding behavior — when one institution exits, others accelerate. A Hawkes (self-exciting) process would be more accurate. | v2 |
| Single-currency fiat (USD only) | Multi-currency adds FX risk and separate buffer optimization per currency. USD on hand does not cover EUR demand. | v2 |
| No rehypothecation modeling | Off-balance-sheet exposure is invisible to this model, as it is to PoR. Requires internal data. | v2 |
| No crypto-to-fiat conversion dynamics | Forced liquidation curves and market impact during stress not modeled. | v2 |
| No cross-exchange contagion | Systemic stress spreads across venues. Network effects require a multi-entity model. | v3 |

The most important limitation to understand: **this model fails loudly, not silently.** Every assumption is written down in `assumptions.md`. When the model is wrong, it is wrong in a way that is visible, debatable, and fixable. That is a deliberate design choice.

---

## References

- Binance Proof of Reserve — [binance.com/en/proof-of-asset](https://www.binance.com/en/proof-of-asset)
- Duffie, D. (2010). *How Big Banks Fail and What to Do about It.* Princeton University Press.
- Porteus, E. (2002). *Foundations of Stochastic Inventory Theory.* Stanford University Press. *(Newsvendor model)*
- JP Morgan RiskMetrics (1996). *Technical Document, 4th Edition.* *(EWMA VaR methodology)*
- Basel Committee on Banking Supervision (2011). *Revisions to the Basel II market risk framework.* *(Stressed VaR)*

---

*All assumptions documented in [assumptions.md](assumptions.md). All parameters configurable in [config.py](config.py). Synthetic data only — no proprietary exchange data used.*
