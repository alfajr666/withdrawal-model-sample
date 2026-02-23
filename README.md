# Liquidity Sentinel: Crypto Exchange Withdrawal & Solvency Model

**Portfolio Project by Gilang Fajar Wijayanto**  
Senior Treasury & Finance Operations Specialist | CFA Level I | FRM Part I  
[delomite.com](https://delomite.com) | [LinkedIn](https://www.linkedin.com/in/gilang-fajar-6973119a/)

---

## 📋 Overview

This repository features **Liquidity Sentinel**, a stress testing framework that models the fiat liquidity and solvency of a crypto exchange under realistic withdrawal scenarios. It addresses a structural gap in standard Proof of Reserve (PoR) frameworks by quantifying the fiat dimension and the impact of banking infrastructure limits.

**[Live Dashboard →](https://alfajr666.github.io/withdrawal-model-sample/dashboard/)**  
**[Detailed Analysis & Methodology →](https://delomite.com/post/withdrawal-model)**

### Business Context
Proof of Reserve (PoR) confirms crypto asset backing but leaves crucial operational risks invisible:
1. **Fiat Liquidity**: Can the exchange process IDR withdrawals during a 65-hour weekend when BI-FAST/SKN-BI rails are offline?
2. **Asset Quality**: At what withdrawal velocity does the asset portfolio become insufficient?
3. **Derivatives Liability**: How does a liquidation cascade impact exchange solvency?

### Key Features
- ✅ **Two-Process Withdrawal Engine**: Models retail (Gamma) and institutional (Poisson) behaviors separately.
- ✅ **Newsvendor Optimization**: Calculates the optimal fiat reserve to balance opportunity cost vs. emergency funding cost.
- ✅ **Three-Tier Reserve Structure**: Allocates reserves across Instant (Gateway), Fast (Stablecoins/Repo), and Liquid (SBN) layers.
- ✅ **Hybrid VaR Modeling**: Combines Historical Simulation, EWMA-filtered, and Stressed VaR.
- ✅ **Regulatory Alignment**: Fully integrated with OJK POJK No. 27/2024 constraints (Rp 50B equity floor, 30/70 storage rule).
- ✅ **Insurance Fund Cascade**: Models socialized losses and feedback loops in derivatives stress.

---

## 📊 System Metrics (Synthetic Baseline)

| Metric | Value |
|--------|-------|
| **Total Assets (AUM)** | IDR 795B (~$50M USD) |
| **Fiat Liabilities** | IDR 636B (~$40M USD) |
| **User Base** | 100,000 (95% Retail, 5% institutional) |
| **Simulation Paths** | 10,000 Monte Carlo iterations |
| **Weekend Window** | 65-hour bank rail downtime |
| **Regulatory Floor** | IDR 50B (OJK Min. Equity) |
| **Insurance Fund** | 0.5% of AUM (Industry norm) |

### Scenario Calibration
| Scenario | Trigger | Withdrawal Rate | Institutional Events |
|-----------|---------|-----------------|----------------------|
| **Normal** | Baseline weekend | 1–3% / day | 0.5 / day |
| **Mild** | 30% Crypto drawdown | 5–8% / day | 2.0 / day |
| **Severe** | FTX-level contagion | 20–40% / day | 6.0 / day |

---

## 🗂️ Project Structure

```
liquidity-sentinel/
├── data/                          # Synthetic datasets & generators
│   ├── generator.py               # Log-normal user base & withdrawal series
│   └── market_data.py             # Regime-switching price history (GBM)
│
├── models/                        # Core simulation modules
│   ├── withdrawal_forecast.py     # Monte Carlo Gamma/Poisson engine
│   ├── historical_var.py          # Hybrid VaR (HS, EWMA, Stressed)
│   ├── reserve_optimizer.py       # Newsvendor cost minimization
│   ├── insurance_fund.py          # Derivatives cascade & socialized loss
│   └── solvency.py                # Unified stressed balance sheet integrator
│
├── dashboard/                     # Interactive FinOps dashboard
│   └── index.html                 # Premium Delomite design (USD/IDR toggle)
│
├── notebooks/                     # Analytical walkthroughs
│   └── analysis.ipynb             # Full simulation & visualization path
│
├── assumptions.md                 # Detailed theoretical rationale
├── config.py                      # Central parameter store
└── README.md                      # This file
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Pip (Python Package Manager)

### 1. Installation
```bash
git clone https://github.com/alfajr666/withdrawal-model-sample.git
cd withdrawal-model-sample
pip install -r requirements.txt
```

### 2. Run Solvency Assessment
```python
from models.solvency import run_full_solvency_assessment, summarize_solvency

# Run assessment with config.py defaults
assessment = run_full_solvency_assessment()
print(summarize_solvency(assessment))
```

### 3. Explore the Dashboard
Visit the [Live Dashboard](https://alfajr666.github.io/withdrawal-model-sample/dashboard/) to interact with simulation results, toggle currency between USD/IDR, and explore the safety frontier.

---

## 📈 Business Logic & Regulatory Compliance

This model operationalizes **OJK's POJK No. 27 of 2024** requirements as quantitative constraints:

- **Equity Floor**: Maintains a hard Rp 50 billion lower bound for solvency verdicts.
- **Storage Ratios**: Implements the 30/70 custody rule and 9% hot wallet ceiling.
- **Fund Segregation**: Strictly models reserves from proprietary capital, excluding segregated consumer IDR.
- **Reserve Tiers**: Maps statistical risk quantiles to specific Indonesian treasury instruments (SBN, Reksa Dana Pasar Uang).

---

## 🎯 Use Cases
- **Treasury Managers**: Sizing weekend fiat buffers to optimize capital efficiency.
- **Risk Officers**: Stress testing institutional withdrawal arrival rates.
- **Compliance Teams**: Ensuring adherence to OJK equity and storage thresholds.
- **C-Suite**: Quantifying the cost of "Fortress Balance Sheet" conservatism.

---

## 📝 License
This project is for **portfolio demonstration purposes**. The data is synthetic and does not represent any real entity.

---

## 🤝 Contact
**Gilang Fajar Wijayanto**  
Senior Treasury & Finance Operations Specialist  
📧 gilang.f@delomite.com  
🌐 [delomite.com](https://delomite.com)  
💼 [LinkedIn](https://www.linkedin.com/in/gilang-fajar-6973119a/)

**Certifications:**
- CFA Level I
- FRM Part I
- WMI & WPPE (OJK Indonesia)

---

**Built with:** Python, Pandas, SciPy, NumPy, Chart.js  
**Designed for:** Treasury Operations, Risk Management, Digital Asset Exchanges
