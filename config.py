"""
config.py — Central Parameter Store
====================================
All hardcoded values for the Crypto Exchange Liquidity Stress Testing model
live here and only here. Every module imports from this file.

When assumptions change, update assumptions.md FIRST, then this file.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# User Base
# ---------------------------------------------------------------------------
N_USERS             = 100_000        # Total synthetic users
RETAIL_SHARE        = 0.95           # 95% of accounts are retail
INST_SHARE          = 0.05           # 5% institutional
INST_BALANCE_SHARE  = 0.65           # Institutional holds ~65% of total fiat

# Log-normal balance distribution parameters (log of USD balance)
RETAIL_LOG_MU       = 8.5            # retail mean: ~$4,900 median
RETAIL_LOG_SIGMA    = 2.2            # retail std  (Gini ~0.85–0.94)
INST_LOG_MU         = 13.5           # institutional mean: ~$730K median
INST_LOG_SIGMA      = 1.8            # institutional std

# ---------------------------------------------------------------------------
# Withdrawal Rates (fraction of total fiat, per day)
# ---------------------------------------------------------------------------
# Each tuple: (min_rate, max_rate) — sampled uniformly each simulation day
NORMAL_DAILY_RATE       = (0.01, 0.03)   # 1–3%
MILD_STRESS_RATE        = (0.05, 0.08)   # 5–8%
SEVERE_STRESS_RATE      = (0.20, 0.40)   # 20–40%

# ---------------------------------------------------------------------------
# Institutional Jump Process — Poisson arrival + Log-normal jump size
# ---------------------------------------------------------------------------
# Arrival rate (events / day) by scenario
INST_JUMP_RATE = {
    "normal": 0.5,
    "mild":   2.0,
    "severe": 6.0,
}

# Log-normal jump size parameters (log of USD amount) by scenario
INST_JUMP_LOG_MU = {
    "normal": 13.5,
    "mild":   14.2,
    "severe": 15.0,
}
INST_JUMP_LOG_SIGMA = {
    "normal": 1.0,
    "mild":   1.2,
    "severe": 1.5,
}

# Lead time of institutional withdrawals ahead of retail (hours) under stress
INST_LEAD_TIME_HOURS = {
    "normal":  0,
    "mild":    3,
    "severe":  6,
}

# ---------------------------------------------------------------------------
# Reserve Optimization (Newsvendor)
# ---------------------------------------------------------------------------
YIELD_RANGE         = (0.04, 0.05)   # Opportunity cost: 4–5% annualized
EMERGENCY_COST      = (0.08, 0.10)   # Emergency liquidity: 8–10% annualized

YIELD_MID           = 0.045          # Mid-point for optimization
EMERGENCY_COST_MID  = 0.09           # Mid-point for optimization

# Newsvendor critical ratio: q* = emergency / (opportunity + emergency)
# At (4.5%, 9%): q* ≈ 0.667 — reserve to the 2/3 quantile
NEWSVENDOR_CRITICAL_RATIO = EMERGENCY_COST_MID / (YIELD_MID + EMERGENCY_COST_MID)

# ---------------------------------------------------------------------------
# Bank Rail Availability
# ---------------------------------------------------------------------------
WEEKEND_HOURS   = 64    # Friday 5PM → Monday 9AM (hours with no bank settlement)

# ---------------------------------------------------------------------------
# VaR Parameters
# ---------------------------------------------------------------------------
VAR_LOOKBACK_DAYS       = 365        # Historical lookback for HS-VaR
EWMA_LAMBDA             = 0.94       # RiskMetrics decay factor
EWMA_ESS                = 1 / (1 - EWMA_LAMBDA)   # ~17 days effective sample size
STRESSED_VAR_WINDOW     = 90         # Worst 90-day window for Stressed VaR
VAR_CONFIDENCE          = 0.99       # 99th percentile VaR
CVAR_CONFIDENCE         = 0.99       # 99th percentile CVaR / Expected Shortfall

# Parametric scenario shocks (fractional price decline)
SCENARIO_SHOCKS = {
    "mild": {
        "BTC": -0.25,
        "ETH": -0.32,
        "ALT": -0.45,
    },
    "severe": {
        "BTC": -0.50,
        "ETH": -0.60,
        "ALT": -0.75,
    },
    "luna": {
        "BTC": -0.40,
        "ETH": -0.48,
        "ALT": -0.88,
    },
}

# ---------------------------------------------------------------------------
# Market Data — Regime-Switching GBM
# ---------------------------------------------------------------------------
REGIMES = ["normal", "stressed", "crisis"]

# Stationary probabilities ≈ [0.88, 0.10, 0.02]
REGIME_TRANSITION_MATRIX = {
    "normal":   {"normal": 0.980, "stressed": 0.018, "crisis": 0.002},
    "stressed": {"normal": 0.150, "stressed": 0.800, "crisis": 0.050},
    "crisis":   {"normal": 0.050, "stressed": 0.250, "crisis": 0.700},
}

# Daily GBM parameters per regime
REGIME_PARAMS = {
    "normal":   {"mu": 0.001,  "sigma_btc": 0.035, "sigma_eth": 0.045, "sigma_alt": 0.060},
    "stressed": {"mu": -0.003, "sigma_btc": 0.070, "sigma_eth": 0.090, "sigma_alt": 0.120},
    "crisis":   {"mu": -0.010, "sigma_btc": 0.150, "sigma_eth": 0.180, "sigma_alt": 0.250},
}

# Cross-asset correlations (BTC-ETH / BTC-ALT) per regime
REGIME_CORRELATIONS = {
    "normal":   {"btc_eth": 0.82, "btc_alt": 0.70},
    "stressed": {"btc_eth": 0.90, "btc_alt": 0.85},
    "crisis":   {"btc_eth": 0.95, "btc_alt": 0.92},
}

# ---------------------------------------------------------------------------
# Derivatives / Insurance Fund
# ---------------------------------------------------------------------------
OI_TO_AUM_RATIO         = 1.5        # Open interest to AUM ratio
N_TRADERS               = 5_000      # Synthetic trader population
INSURANCE_FUND_INITIAL  = 0.005      # 0.5% of AUM (industry norm)
CASCADE_STEPS           = 5          # Liquidation cascade iterations

# Retail trader leverage distribution (mean, std truncated normal)
RETAIL_LEVERAGE_MEAN    = 15.0
RETAIL_LEVERAGE_STD     = 5.0
RETAIL_LEVERAGE_MIN     = 2.0
RETAIL_LEVERAGE_MAX     = 50.0

# Institutional trader leverage distribution
INST_LEVERAGE_MEAN      = 8.0
INST_LEVERAGE_STD       = 3.0
INST_LEVERAGE_MIN       = 2.0
INST_LEVERAGE_MAX       = 20.0

# Institutional share of traders and notional
INST_TRADER_SHARE       = 0.10       # 10% of trader accounts
INST_NOTIONAL_SHARE     = 0.60       # Institutional holds ~60% of OI notional

# CFD equity correlation with BTC (normal → crisis)
CFD_CORR_NORMAL         = 0.35
CFD_CORR_CRISIS         = 0.70

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Data Persistence Paths & Simulation
# ---------------------------------------------------------------------------
import os
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR    = os.path.join(BASE_DIR, "data", "raw")
USERS_CSV_PATH  = os.path.join(RAW_DATA_DIR, "synthetic_users_scaled.csv")
MARKET_CSV_PATH = os.path.join(RAW_DATA_DIR, "market_history_365d.csv")

N_SIMULATIONS   = 10_000    # Monte Carlo paths
N_DAYS_HISTORY  = 365       # Days of synthetic market data history

# ---------------------------------------------------------------------------
# Reserve Tier Thresholds (used in solvency.py)
# ---------------------------------------------------------------------------
TIER1_QUANTILE  = None   # max(HS-VaR, FHS-VaR) — computed dynamically
TIER2_QUANTILE  = 0.95   # Gamma/Poisson p95
TIER3_QUANTILE  = 0.99   # Gamma/Poisson p99

# ---------------------------------------------------------------------------
# Proprietary Capital (exchange equity buffer)
# Assumed as % of AUM — conservatively low to stress-test
# ---------------------------------------------------------------------------
PROP_CAPITAL_RATIO = 0.02   # 2% of AUM as exchange equity buffer

# ---------------------------------------------------------------------------
# Portfolio / Exchange AUM (synthetic baseline, in USD)
# ---------------------------------------------------------------------------
# Total Assets (including crypto)
TOTAL_ASSETS_AUM       = 2_900_000_000   

# Fiat portion (customer liabilities)
FIAT_LIABILITIES_TARGET = 2_230_000_000   # $2.23B baseline from brief

# Keep for compatibility where specifically used for scaling
EXCHANGE_AUM    = TOTAL_ASSETS_AUM
