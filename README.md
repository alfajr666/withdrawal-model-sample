# Liquidity Sentinel: Crypto Exchange Withdrawal & Solvency Model

A heavy-tailed stress testing framework for crypto exchange liquidity risk management. This model simulates withdrawal cascades across retail and institutional cohorts and evaluates exchange solvency under various market stress regimes.

## Overview

Liquidity Sentinel is designed to help Treasury and Risk managers understand the true "tail risk" of an exchange's fiat liabilities. Unlike simple static models, it uses **Monte Carlo simulations** and **Regime-Switching market data** to identify when "industry rule-of-thumb" reserves (like 10%) fail.

### Core Features
- **Dual-Cohort Withdrawal Model**: Distinguishes between Retail (Gamma distribution) and Institutional (Poisson Jump process) actors.
- **Regime-Switching Market Risk**: Simulates Normal, Stressed, and Crisis volatility regimes with Markov transition matrices.
- **Insurance Fund Simulation**: Models derivative liquidations and potential IF shortfalls during crashes.
- **Solvency Integration**: Combines mark-to-market asset moves, withdrawal demand, and derivative clawbacks into a single solvency verdict.
- **Reserve Optimizer**: Uses a Newsvendor framework to balance the opportunity cost of holding cash vs. the emergency cost of shortfall.

## Project Structure

```bash
├── config.py              # Central parameter store (AUM, rates, shocks)
├── assumptions.md         # Technical documentation of model parameters
├── data/
│   └── generator.py       # Syntax data generation logic
├── models/
│   ├── withdrawal_forecast.py # Monte Carlo withdrawal engine
│   ├── historical_var.py      # Market risk (VaR/CVaR) calculations
│   ├── insurance_fund.py      # Derivatives stress simulation
│   ├── solvency.py            # Balance sheet integration
│   └── reserve_optimizer.py   # Newsvendor liquidity optimization
├── scripts/
│   ├── init_data.py       # Bootstraps the user base and market history
│   └── export_results.py  # Runs the full suite and exports dashboard data
└── dashboard/             # HTML/JS Visualization layer
```

## Methodology

### 1. Withdrawal Assumptions
The model assumes that institutional actors are the primary drivers of tail risk. 
- **Retail**: Highly frequent but small, modeled with a Gamma distribution.
- **Institutional**: Low frequency but high impact (65% of AUM), modeled as discrete jumps. They are assumed to have a 3-8 hour lead time on retail panic.

### 2. Solvency Scenarios
- **Normal**: Baseline behavior using Historical VaR (99%).
- **Mild Stress**: Corresponds to corrections like May 2021 (-25% BTC).
- **Severe Stress**: Corresponds to systemic collapses like FTX (-50% BTC).

## Getting Started

### Prerequisites
- Python 3.8+
- Requirements: `numpy`, `pandas`, `scipy`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/alfajr666/withdrawal-model-sample.git
   cd withdrawal-model-sample
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Simulation
1. **Initialize Data**: Generate the synthetic user base and market history.
   ```bash
   python3 scripts/init_data.py
   ```
2. **Execute Model**: Run the full Monte Carlo suite and export results.
   ```bash
   python3 scripts/export_results.py
   ```
3. **View Dashboard**: Open `index.html` in your browser to see the risk report.

## License
MIT License
