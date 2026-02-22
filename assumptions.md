# Assumptions

**Crypto Exchange Liquidity Stress Testing Model**
*Last updated: February 2026 | Version: 1.1*
*Regulatory framework: POJK No. 27 of 2024 (OJK) — PT Pedagang Aset Keuangan Digital*

---

## Philosophy

This document is a first-class artifact. Every parameter in this model traces back to an explicit assumption recorded here. Practitioners substituting real exchange data should update these values first — the model is intentionally assumption-driven so that inputs, not code, drive the results.

When assumptions are uncertain, this document says so. A model that hides its uncertainty is more dangerous than one that quantifies it.

---

## 1. User Base

| Parameter | Value | Rationale |
|---|---|---|
| Retail share of accounts | 95% | Typical crypto exchange composition |
| Institutional share of accounts | 5% | Hedge funds, OTC desks, corporate treasuries |
| Institutional share of fiat balances | 60–70% | Heavy-tail balance distribution; consistent with empirical bank data and crypto exchange public disclosures |
| Balance distribution | Log-normal | Captures long right tail of large accounts; standard in financial modeling |

**AUM Scaling:** The model is calibrated to a **Rp 795 Billion (~$50M) Target AUM**, with mean retail balances of ~Rp 800k and institutional balances of ~Rp 80M.


**Key insight:** Average-based planning is dangerous. The top 1% of accounts by balance may represent 40–50%+ of total fiat exposure. The model treats institutional accounts as a separate jump process, not a scaling of retail behavior.

---

## 2. Withdrawal Behavior

### 2.1 Baseline (Normal Conditions)

| Parameter | Value |
|---|---|
| Daily fiat withdrawal rate | 1–3% of total fiat balances |
| Withdrawal size distribution | Log-normal |
| Retail withdrawal frequency | High (multiple events/day), small amounts |
| Institutional withdrawal frequency | Low (weekly or event-driven), large amounts |

### 2.2 Temporal Patterns

- Weekday baseline follows the 1–3% daily rate above
- Weekend baseline is slightly *lower* in normal conditions (reduced retail activity)
- **Critical:** Weekend tail risk is *higher* — crypto market stress events disproportionately occur on weekends, when bank rails are offline. The model treats this as a correlated risk factor, not independence

### 2.3 Institutional Withdrawal Modeling

Institutional withdrawals are modeled as a **Poisson jump process** layered on top of the retail baseline:

- Arrival rate: low in normal conditions (~0.5 events/day), rising sharply under stress
- Jump size: drawn from a separate log-normal distribution with higher mean and variance than retail
- Correlation: institutional jump arrival rate is positively correlated with market stress indicator

---

## 3. Stress Scenarios

Three scenarios are defined. These are not point estimates — each generates a distribution of outcomes via Monte Carlo simulation.

| Scenario | Trigger | Withdrawal Volume | Key Driver |
|---|---|---|---|
| **Normal Operations** | Baseline weekend, no market event | 1–3% of balances over 48–72 hrs | Retail, stochastic |
| **Mild Stress** | 20–30% crypto market drawdown | 5–8% of balances; some institutional movement | Retail amplification + early institutional |
| **Severe Stress (FTX-style)** | Contagion event or exchange-specific loss of confidence | 20–40% of balances in 48–72 hrs | Institutional leads, retail follows with lag |

### Scenario Construction Notes

- Severe stress is calibrated to the FTX collapse (November 2022), where approximately $6B was withdrawn in 72 hours before the exchange halted withdrawals
- The 20–40% range reflects uncertainty — the model samples across this range in simulation
- Institutional withdrawals lead retail by approximately 6–12 hours in severe scenarios (informed actors move first)

---

## 4. Fiat Reserve and Regulatory Floor

### 4.0 Capital Source and Regulatory Minimum (POJK No. 27/2024)

Under POJK No. 27/2024, **100% of consumer fiat is segregated** at the Clearing and Settlement Institution (Lembaga Kliring). The reserve modeled here is therefore **firm-owned operational capital only** — not consumer funds.

| Regulatory Requirement | OJK Threshold | Model Treatment |
|---|---|---|
| Minimum paid-up capital | Rp 100 billion | Exchange entry requirement — not modeled |
| **Maintained equity floor** | **Rp 50 billion** | **Hard floor — overrides newsvendor result if lower** |
| Consumer fiat segregation | 100% at clearing institution | Reserve = firm capital only |
| Hot wallet ceiling | ≤9% of consumer crypto (30% internal × 30% hot) | Limits crypto-to-fiat conversion speed under stress |

The stress model fills the gap OJK does not prescribe: **how much firm capital above Rp 50 billion is needed to survive a withdrawal run without breaching the equity floor?** CVaR 99% is that answer. Rp 50B is the regulatory minimum; the model output is the operationally sufficient minimum.

**Currency:** All outputs denominated in IDR (primary), USD shown as reference. FX rate: USD/IDR 15,900 (configurable in `config.py`).

### 4.1 Yield on Deployed Fiat

| Asset Class | Assumed Yield (Annualized) |
|---|---|
| Bank Indonesia overnight deposit (PUAB) | 5.5–6.0% |
| SBI / SBN (short-duration government securities) | 6.0–6.8% |
| Money market funds (reksa dana pasar uang) | 5.5–6.5% |
| **Model assumption** | **6–7% blended (IDR-denominated)** |

This yield represents the **opportunity cost** of holding an idle fiat reserve. The model converts this to a dollar-per-day cost figure so management has a concrete cost to weigh against safety.

### 4.2 Emergency Liquidity Cost

If the fiat buffer is exhausted and the exchange must source liquidity:

| Source | Assumed Cost |
|---|---|
| Bank credit line drawdown | 10–13% annualized (Indonesian corporate lending rates) |
| Crypto-to-fiat liquidation | Execution friction 0.5–2% of notional; constrained by 9% hot wallet ceiling |
| **Model assumption** | **10–12% annualized all-in cost** |

The spread between 6–7% opportunity cost and 10–12% emergency cost defines the **economic incentive to hold a buffer** — roughly 4–5 percentage points annualized, consistent with previous version despite higher absolute rates.

### 4.3 Bank Rail Availability

| Period | Status |
|---|---|
| Monday 8AM – Friday 4PM (WIB, Jakarta) | Rails available — BI-FAST and RTGS operational |
| Friday 4PM – Monday 8AM | **Rails offline** |
| Indonesian public holidays | **Rails offline** |
| Large transfers (>Rp 500 million) via RTGS | Cut-off 3PM WIB — 1 hour earlier than standard |
| Internal processing lag (large withdrawals) | 2–4 hours additional buffer |

The model's primary risk window is the **Friday-to-Monday gap** — approximately 65 hours (WIB). Indonesia's high density of public holidays (national + regional) means this window occurs more frequently than in Western markets. The BI-FAST system supports near-real-time retail transfers but large institutional transfers remain RTGS-dependent with hard cut-offs.


### 4.4 Reserve Policy Output

The model outputs a recommended minimum reserve expressed as:
1. **Dollar amount** — minimum fiat to hold entering a weekend
2. **% of total fiat liabilities** — normalized metric for policy comparison
3. **Cost of policy** — annualized yield foregone at the recommended buffer level
4. **VaR and CVaR** — Value at Risk and Conditional Value at Risk at 95% and 99% confidence for the weekend period

---

## 5. Scope Boundaries (v1)

The following are **intentionally excluded** from version 1. They are real risks but would bloat the model before the core mechanics are validated.

| Excluded Item | Why Excluded | Future Version? |
|---|---|---|
| Multi-currency fiat (EUR, GBP, etc.) | Adds FX risk and separate buffer optimization per currency | v2 |
| Rehypothecation modeling | Requires off-balance-sheet data not typically in PoR reports | v2 |
| Crypto-to-fiat conversion dynamics under stress | Liquidation curves and market impact modeling add significant complexity | v2 |
| Contagion across exchanges | Network effects require multi-entity model | v3 |
| Intraday withdrawal timing | Hourly granularity requires different data; daily is sufficient for weekend buffer planning | v2 |

---

## 6. Data Generation Assumptions

The model uses synthetic data rather than proprietary exchange data. This is intentional: it makes the model transparent, reproducible, and accessible to practitioners without access to real data.

Where real Proof of Reserve data is available (Binance, OKX, and others publish Merkle tree attestations), the model is designed to accept it as a direct input to run live stress tests against actual balance sheets.

### 6.1 Synthetic User Base

- Number of users: **100,000** (configurable)
- Balance distribution: log-normal with parameters calibrated to produce a realistic Gini coefficient (~0.85, consistent with observed crypto wealth concentration)
- Institutional accounts: flagged separately, balances drawn from a higher-mean log-normal

### 6.2 Synthetic Time Series

- Simulation period: **52 weekends** (1 year of weekend risk windows)
- Each weekend: 64-hour simulation with hourly withdrawal draws
- Market stress flag: injected probabilistically (mild stress ~10% of weekends, severe stress ~2%)

---

## 7. Parameters Quick Reference

All parameters below are configurable in `config.py`. Change them there, not in individual modules.

```python
# User base
N_USERS = 100_000
RETAIL_SHARE = 0.95
INST_BALANCE_SHARE = 0.65        # institutional share of total fiat balances

# Withdrawal rates (% of total fiat per day)
NORMAL_DAILY_RATE_LOW  = 0.01
NORMAL_DAILY_RATE_HIGH = 0.03
MILD_STRESS_RATE_LOW   = 0.05
MILD_STRESS_RATE_HIGH  = 0.08
SEVERE_STRESS_RATE_LOW = 0.20
SEVERE_STRESS_RATE_HIGH= 0.40

# Opportunity cost and emergency cost (IDR-denominated, updated for Indonesian market)
YIELD_LOW  = 0.06
YIELD_HIGH = 0.07
EMERGENCY_COST_LOW  = 0.10
EMERGENCY_COST_HIGH = 0.12

# OJK regulatory floor (POJK No. 27/2024)
OJK_MIN_EQUITY_IDR = 50_000_000_000   # Rp 50 billion — hard floor
USD_IDR_FX_RATE    = 15_900            # USD/IDR reference rate (update periodically)

# Simulation
N_SIMULATIONS = 10_000
WEEKEND_HOURS = 65
CONFIDENCE_LEVELS = [0.95, 0.99]
```

---

*This document should be updated whenever assumptions change. Model outputs are only as good as these inputs.*
