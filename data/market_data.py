"""
data/market_data.py — Regime-Switching GBM Price Data
======================================================
Generates synthetic daily price return series for BTC, ETH, and ALTs
using a Hidden Markov / Regime-Switching GBM framework.

Three regimes:
  - normal   : 88% unconditional probability
  - stressed : 10%
  - crisis   :  2%

Correlations rise in crisis (BTC-ETH: 0.82 → 0.95).
"""

import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg


def _regime_transition(current_regime: str, rng: np.random.Generator) -> str:
    """Advance regime by one step using the Markov transition matrix."""
    probs = cfg.REGIME_TRANSITION_MATRIX[current_regime]
    regimes = list(probs.keys())
    weights = list(probs.values())
    return rng.choice(regimes, p=weights)


def _cholesky_from_corr(corr_btc_eth: float, corr_btc_alt: float) -> np.ndarray:
    """
    Build a 3x3 Cholesky factor from pairwise BTC-ETH and BTC-ALT correlations.
    ETH-ALT correlation is inferred as corr_btc_eth * corr_btc_alt (factor model).
    """
    corr_eth_alt = corr_btc_eth * corr_btc_alt  # factor model approximation

    corr_matrix = np.array([
        [1.0,          corr_btc_eth, corr_btc_alt],
        [corr_btc_eth, 1.0,          corr_eth_alt],
        [corr_btc_alt, corr_eth_alt, 1.0         ],
    ])
    # Ensure PSD (clip eigenvalues if necessary)
    eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)
    eigenvalues = np.maximum(eigenvalues, 1e-8)
    corr_matrix = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T

    return np.linalg.cholesky(corr_matrix)


def generate_market_data(
    n_days: int = cfg.N_DAYS_HISTORY,
    seed: int = cfg.RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generate synthetic daily returns for BTC, ETH, ALT under regime-switching GBM.

    Parameters
    ----------
    n_days : int — number of daily observations
    seed   : int — RNG seed for reproducibility

    Returns
    -------
    pd.DataFrame with columns:
        date, regime, btc_return, eth_return, alt_return,
        btc_price, eth_price, alt_price
    """
    rng = np.random.default_rng(seed)

    regimes       = []
    btc_returns   = []
    eth_returns   = []
    alt_returns   = []

    current_regime = "normal"

    for _ in range(n_days):
        regime = current_regime
        regimes.append(regime)

        params = cfg.REGIME_PARAMS[regime]
        corrs  = cfg.REGIME_CORRELATIONS[regime]

        # Cholesky decomposition for correlated normals
        L = _cholesky_from_corr(corrs["btc_eth"], corrs["btc_alt"])

        # Independent standard normals
        z = rng.standard_normal(3)
        # Correlated normals
        eps = L @ z

        # GBM daily returns: r = mu - 0.5*sigma^2 + sigma*eps  (Ito correction)
        r_btc = params["mu"] - 0.5 * params["sigma_btc"]**2 + params["sigma_btc"] * eps[0]
        r_eth = params["mu"] - 0.5 * params["sigma_eth"]**2 + params["sigma_eth"] * eps[1]
        r_alt = params["mu"] - 0.5 * params["sigma_alt"]**2 + params["sigma_alt"] * eps[2]

        btc_returns.append(r_btc)
        eth_returns.append(r_eth)
        alt_returns.append(r_alt)

        # Advance regime
        current_regime = _regime_transition(current_regime, rng)

    # Build price series from returns (base = 100)
    btc_returns = np.array(btc_returns)
    eth_returns = np.array(eth_returns)
    alt_returns = np.array(alt_returns)

    btc_prices = 100 * np.cumprod(1 + btc_returns)
    eth_prices = 100 * np.cumprod(1 + eth_returns)
    alt_prices = 100 * np.cumprod(1 + alt_returns)

    dates = pd.date_range(end="2026-02-21", periods=n_days, freq="B")

    df = pd.DataFrame({
        "date":       dates,
        "regime":     regimes,
        "btc_return": btc_returns,
        "eth_return": eth_returns,
        "alt_return": alt_returns,
        "btc_price":  btc_prices,
        "eth_price":  eth_prices,
        "alt_price":  alt_prices,
    })

    return df


def generate_intraweekend_paths(
    n_hours: int = cfg.WEEKEND_HOURS,
    n_paths: int = 500,
    regime: str = "crisis",
    seed: int = cfg.RANDOM_SEED + 10,
) -> pd.DataFrame:
    """
    Generate intra-weekend (hourly) price shock paths for stress scenarios.

    Parameters
    ----------
    n_hours  : hours in simulation (64 for standard weekend)
    n_paths  : number of Monte Carlo paths
    regime   : which regime parameters to use

    Returns
    -------
    pd.DataFrame of shape (n_hours, n_paths+1) — columns: hour, path_0..path_N
    """
    rng = np.random.default_rng(seed)

    params = cfg.REGIME_PARAMS[regime]
    # Scale daily vol to hourly
    sigma_hourly = params["sigma_btc"] / np.sqrt(24)
    mu_hourly    = params["mu"] / 24.0

    shocks = rng.normal(
        loc=mu_hourly - 0.5 * sigma_hourly**2,
        scale=sigma_hourly,
        size=(n_hours, n_paths),
    )

    # Cumulative price paths (normalized start = 1.0)
    price_paths = np.cumprod(1 + shocks, axis=0)
    price_paths = np.vstack([np.ones(n_paths), price_paths])

    df = pd.DataFrame(
        price_paths,
        columns=[f"path_{i}" for i in range(n_paths)],
    )
    df.insert(0, "hour", range(n_hours + 1))

    return df


def get_worst_stress_window(market_df: pd.DataFrame, window: int = cfg.STRESSED_VAR_WINDOW) -> pd.DataFrame:
    """
    Identify the worst consecutive 'window'-day return window for Stressed VaR.

    Returns the sub-DataFrame corresponding to the worst BTC drawdown window.
    """
    btc_cum = (1 + market_df["btc_return"]).cumprod()
    rolling_drawdown = btc_cum.rolling(window).apply(
        lambda x: (x[-1] / x[0]) - 1, raw=True
    )
    worst_end_idx = rolling_drawdown.idxmin()
    worst_start_idx = worst_end_idx - window + 1

    return market_df.iloc[worst_start_idx:worst_end_idx + 1].copy()


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating regime-switching market data...")
    df = generate_market_data()

    regime_counts = df["regime"].value_counts(normalize=True)
    print("\nRegime distribution:")
    for r, p in regime_counts.items():
        print(f"  {r:9s}: {p:.1%}")

    print(f"\nBTC total return (365 days): {(df['btc_price'].iloc[-1] / 100 - 1):.1%}")
    print(f"BTC return std (daily)     : {df['btc_return'].std():.3%}")

    worst = get_worst_stress_window(df)
    worst_drawdown = (1 + worst["btc_return"]).prod() - 1
    print(f"\nWorst 90-day BTC drawdown  : {worst_drawdown:.1%}")
    print("\n[market_data.py] OK")
