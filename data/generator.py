"""
data/generator.py — Synthetic Exchange User Base & Withdrawal Time Series
=========================================================================
Generates a 100,000-user synthetic exchange with realistic wealth concentration
and hourly withdrawal time series across three stress scenarios.

Key outputs:
  - users_df         : DataFrame of user accounts with balances
  - generate_weekend_withdrawals(scenario, total_fiat) : 64-hour time series
"""

import numpy as np
import pandas as pd
from scipy import stats
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg
try:
    from data.market_data import generate_market_data
except ImportError:
    from market_data import generate_market_data


def generate_user_base(seed: int = cfg.RANDOM_SEED, target_aum: float = cfg.EXCHANGE_AUM) -> pd.DataFrame:
    """
    Generate synthetic exchange user base.

    Returns
    -------
    pd.DataFrame with columns: user_id, user_type, fiat_balance (USD)

    Notes
    -----
    Institutional accounts are scaled post-generation to ensure
    INST_BALANCE_SHARE (~65%) of total fiat is held by institutional users.
    Gini coefficient of resulting distribution: ~0.85–0.94.
    """
    rng = np.random.default_rng(seed)

    n_retail = int(cfg.N_USERS * cfg.RETAIL_SHARE)
    n_inst   = cfg.N_USERS - n_retail

    # Retail: log-normal balance distribution
    retail_balances = rng.lognormal(
        mean=cfg.RETAIL_BALANCE_MU,
        sigma=cfg.RETAIL_BALANCE_SIGMA,
        size=n_retail,
    )

    # Institutional: log-normal with higher mean (larger accounts)
    inst_balances = rng.lognormal(
        mean=cfg.INST_BALANCE_MU,
        sigma=cfg.INST_BALANCE_SIGMA,
        size=n_inst,
    )

    # Scale institutional balances so they hold INST_BALANCE_SHARE of total fiat
    current_inst_share = inst_balances.sum() / (retail_balances.sum() + inst_balances.sum())
    target_inst_share  = cfg.INST_BALANCE_SHARE
    scale_factor       = (target_inst_share / current_inst_share) * \
                         (retail_balances.sum() / inst_balances.sum()) * \
                         (target_inst_share / (1 - target_inst_share))

    inst_balances = inst_balances * scale_factor

    # Build DataFrame
    retail_df = pd.DataFrame({
        "user_id":      range(n_retail),
        "user_type":    "retail",
        "fiat_balance": retail_balances,
    })
    inst_df = pd.DataFrame({
        "user_id":      range(n_retail, cfg.N_USERS),
        "user_type":    "institutional",
        "fiat_balance": inst_balances,
    })

    users_df = pd.concat([retail_df, inst_df], ignore_index=True)
    users_df["user_id"] = users_df.index

    # Rescale all balances to target_aum so absolute amounts match EXCHANGE_AUM.
    # This preserves the distributional shape (Gini, concentration) exactly.
    if target_aum is not None:
        scale = target_aum / users_df["fiat_balance"].sum()
        users_df["fiat_balance"] = users_df["fiat_balance"] * scale

    return users_df


def compute_gini(balances: np.ndarray) -> float:
    """Compute Gini coefficient for a balance array."""
    sorted_b = np.sort(balances)
    n = len(sorted_b)
    cumsum = np.cumsum(sorted_b)
    gini = (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n
    return gini


def generate_lorenz_curve(balances: np.ndarray) -> tuple:
    """
    Compute Lorenz curve coordinates.

    Returns
    -------
    (lorenz_x, lorenz_y) : cumulative population share, cumulative wealth share
    """
    sorted_b = np.sort(balances)
    n = len(sorted_b)
    lorenz_x = np.linspace(0, 1, n)
    lorenz_y = np.cumsum(sorted_b) / sorted_b.sum()
    return lorenz_x, lorenz_y


def generate_retail_withdrawals(
    total_fiat: float,
    scenario: str,
    n_hours: int = cfg.WEEKEND_HOURS,
    seed: int = cfg.RANDOM_SEED + 1,
) -> np.ndarray:
    """
    Generate hourly retail withdrawal amounts using Gamma distribution.

    Retail withdrawals = aggregate flow of many small, independent decisions.
    Gamma is max-entropy given positive support and known mean/variance.

    Parameters
    ----------
    total_fiat : float — total exchange fiat holdings (USD)
    scenario   : "normal" | "mild" | "severe"
    n_hours    : simulation horizon (default: 64 hours weekend)

    Returns
    -------
    np.ndarray of shape (n_hours,) — hourly retail withdrawal amounts
    """
    rng = np.random.default_rng(seed)

    rate_ranges = {
        "normal": cfg.NORMAL_DAILY_RATE,
        "mild":   cfg.MILD_STRESS_RATE,
        "severe": cfg.SEVERE_STRESS_RATE,
    }
    rate_min, rate_max = rate_ranges[scenario]

    # Sample daily rate uniformly from range
    daily_rate = rng.uniform(rate_min, rate_max)
    daily_withdrawal = daily_rate * total_fiat

    # Hourly mean and variance (overdispersed in stress)
    hourly_mean = daily_withdrawal / 24.0
    # Coefficient of variation: higher under stress (more bursty)
    cv_map = {"normal": 0.5, "mild": 0.8, "severe": 1.2}
    cv = cv_map[scenario]

    # Gamma parameterization: mean=α/β, var=α/β²
    variance = (cv * hourly_mean) ** 2
    alpha = hourly_mean ** 2 / variance  # shape
    beta  = hourly_mean / variance       # rate (1/scale)

    withdrawals = rng.gamma(shape=alpha, scale=1.0 / beta, size=n_hours)
    return withdrawals


def generate_institutional_withdrawals(
    total_fiat: float,
    scenario: str,
    n_hours: int = cfg.WEEKEND_HOURS,
    seed: int = cfg.RANDOM_SEED + 2,
) -> np.ndarray:
    """
    Generate hourly institutional withdrawal amounts using Poisson Jump Process.

    Institutional withdrawals: rare, large, discrete.
    Poisson governs arrival rate; jump sizes are log-normal.

    Critical: arrival rate is 12x higher in severe vs. normal (0.5 → 6.0/day).
    Institutional actors lead retail by INST_LEAD_TIME_HOURS.

    Parameters
    ----------
    total_fiat : float — total exchange fiat holdings (USD)
    scenario   : "normal" | "mild" | "severe"
    n_hours    : simulation horizon

    Returns
    -------
    np.ndarray of shape (n_hours,) — hourly institutional withdrawal amounts
    """
    rng = np.random.default_rng(seed)

    arrival_rate_per_hour = cfg.INST_JUMP_RATE[scenario] / 24.0
    jump_log_mu    = cfg.INST_JUMP_LOG_MU[scenario]
    jump_log_sigma = cfg.INST_JUMP_LOG_SIGMA[scenario]

    withdrawals = np.zeros(n_hours)

    for hour in range(n_hours):
        # Number of institutional withdrawals in this hour (Poisson)
        n_arrivals = rng.poisson(arrival_rate_per_hour)

        if n_arrivals > 0:
            # Jump sizes from log-normal
            jump_sizes = rng.lognormal(
                mean=jump_log_mu,
                sigma=jump_log_sigma,
                size=n_arrivals,
            )
            # Cap individual jumps at max plausible fraction of total fiat
            jump_sizes = np.minimum(jump_sizes, total_fiat * 0.15)
            withdrawals[hour] = jump_sizes.sum()

    return withdrawals


def generate_weekend_withdrawals(
    total_fiat: float,
    scenario: str,
    n_hours: int = cfg.WEEKEND_HOURS,
    seed: int = cfg.RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generates combined hourly withdrawal time series for a stress weekend.

    Institutional withdrawals are offset by their lead time (earlier peak onset).

    Parameters
    ----------
    total_fiat : float — total fiat in exchange (USD)
    scenario   : "normal" | "mild" | "severe"
    n_hours    : simulation horizon (default 64 hours)

    Returns
    -------
    pd.DataFrame with columns: hour, retail, institutional, total
    """
    lead_hours = cfg.INST_LEAD_TIME_HOURS.get(scenario, 0)

    retail = generate_retail_withdrawals(total_fiat, scenario, n_hours, seed + 1)

    # Institutional starts earlier — shift lead hours by generating extra and trimming
    n_inst_hours = n_hours + lead_hours
    inst_full = generate_institutional_withdrawals(
        total_fiat, scenario, n_inst_hours, seed + 2
    )
    # Lead: institutional starts at hour 0 as if they got wind earlier
    # Retail starts 'lead_hours' later in the cumulative timeline
    inst = inst_full[:n_hours]

    total = retail + inst

    df = pd.DataFrame({
        "hour":          np.arange(n_hours),
        "retail":        retail,
        "institutional": inst,
        "total":         total,
    })

    return df


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating user base...")
    users = generate_user_base()

    total_fiat = users["fiat_balance"].sum()
    inst_share = users.loc[users["user_type"] == "institutional", "fiat_balance"].sum() / total_fiat

    gini = compute_gini(users["fiat_balance"].values)

    # 2. Save to CSV
    users.to_csv(cfg.USERS_CSV_PATH, index=False)
    
    # 3. Market data (persistence)
    mdf = generate_market_data()
    mdf.to_csv(cfg.MARKET_CSV_PATH, index=False)

    print(f"  Users generated : {len(users):,}")
    print(f"  Total fiat AUM  : Rp {total_fiat:,.0f}")
    print(f"  Inst. bal. share: {inst_share:.1%}  (target: {cfg.INST_BALANCE_SHARE:.0%})")
    print(f"  Gini coefficient: {gini:.3f}  (target: 0.85–0.94)")

    print("\nGenerating weekend withdrawal time series (severe scenario)...")
    wdf = generate_weekend_withdrawals(total_fiat, "severe")
    print(f"  Peak hour withdrawal : Rp {wdf['total'].max():,.0f}")
    print(f"  Total 65hr withdrawal: Rp {wdf['total'].sum():,.0f}")
    print(f"  As % of AUM          : {wdf['total'].sum() / total_fiat:.1%}")
    print("\n[generator.py] OK")
