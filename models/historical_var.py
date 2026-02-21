"""
models/historical_var.py — Hybrid VaR Suite
============================================
Implements three complementary VaR methodologies using synthetic market data:

1. Historical Simulation VaR (HS-VaR)      — empirical floor, no distributional assumption
2. EWMA-Filtered HS VaR (FHS-VaR, λ=0.94) — recency-adjusted, current-vol weighted
3. Stressed VaR                             — worst 90-day BTC window, Basel III-inspired

Plus parametric scenario overlays: Mild / Severe / LUNA-style shocks.

Key insight: VaR fails silently. The generative model fails loudly. Both are needed.
"""

import numpy as np
import pandas as pd
from scipy import stats
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg
from data.market_data import generate_market_data, get_worst_stress_window


def compute_ewma_volatility(returns: np.ndarray, lam: float = cfg.EWMA_LAMBDA) -> np.ndarray:
    """
    Compute EWMA volatility for a return series (RiskMetrics approach).

    σ²_t = λ σ²_{t-1} + (1-λ) r²_{t-1}

    Parameters
    ----------
    returns : np.ndarray — daily return series
    lam     : float — decay factor (RiskMetrics default 0.94)

    Returns
    -------
    np.ndarray of same length — EWMA variance series (sigma²)
    """
    n = len(returns)
    ewma_var = np.zeros(n)
    ewma_var[0] = returns[0] ** 2

    for t in range(1, n):
        ewma_var[t] = lam * ewma_var[t - 1] + (1 - lam) * returns[t - 1] ** 2

    return ewma_var


def hs_var(
    returns: np.ndarray,
    confidence: float = cfg.VAR_CONFIDENCE,
    lookback: int = cfg.VAR_LOOKBACK_DAYS,
) -> float:
    """
    Historical Simulation VaR.
    Uses the worst `confidence`th percentile of the empirical return distribution.
    No distributional assumption. Fails silently.

    Returns VaR as a positive loss fraction (e.g., 0.082 = 8.2% loss).
    """
    recent = returns[-lookback:]
    return float(-np.percentile(recent, (1 - confidence) * 100))


def fhs_var(
    returns: np.ndarray,
    confidence: float = cfg.VAR_CONFIDENCE,
    lam: float = cfg.EWMA_LAMBDA,
    lookback: int = cfg.VAR_LOOKBACK_DAYS,
) -> float:
    """
    EWMA-Filtered Historical Simulation VaR (FHS-VaR).

    Standardizes historical returns by current EWMA volatility, then applies
    historical simulation on the standardized residuals.

    Effective sample size = 1/(1-λ) ≈ 17 days at λ=0.94.
    Almost entirely pricing current vol — appropriate for crypto's fast regime changes.
    """
    recent = returns[-lookback:]
    ewma_var = compute_ewma_volatility(recent, lam)

    current_vol = np.sqrt(ewma_var[-1])
    historical_vols = np.sqrt(ewma_var)

    # Standardized residuals
    standardized = recent / np.where(historical_vols > 0, historical_vols, 1e-8)

    # Rescale to current volatility
    rescaled = standardized * current_vol

    return float(-np.percentile(rescaled, (1 - confidence) * 100))


def stressed_var(
    full_returns: np.ndarray,
    market_df: pd.DataFrame,
    confidence: float = cfg.VAR_CONFIDENCE,
    window: int = cfg.STRESSED_VAR_WINDOW,
) -> float:
    """
    Stressed VaR: VaR computed using only the worst 90-day BTC drawdown window.

    Basel III-inspired: anchors Tier 2 reserve to the worst historical episode
    in our synthetic data. Only as bad as the worst period in the dataset.
    """
    worst_window_df = get_worst_stress_window(market_df, window)
    worst_returns   = worst_window_df["btc_return"].values
    return float(-np.percentile(worst_returns, (1 - confidence) * 100))


def parametric_scenario_var(
    portfolio_weights: dict,
    portfolio_value: float,
) -> dict:
    """
    Compute portfolio loss under parametric shock scenarios.

    Parameters
    ----------
    portfolio_weights : dict — {"BTC": 0.5, "ETH": 0.3, "ALT": 0.2}
    portfolio_value   : float — total value in USD

    Returns
    -------
    dict mapping scenario → {"loss_usd": float, "loss_pct": float}
    """
    results = {}
    for scenario, shocks in cfg.SCENARIO_SHOCKS.items():
        weighted_loss = 0.0
        for asset, shock in shocks.items():
            weight = portfolio_weights.get(asset, 0.0)
            weighted_loss += weight * abs(shock)

        results[scenario] = {
            "loss_pct":    weighted_loss,
            "loss_usd":    weighted_loss * portfolio_value,
        }
    return results


def compute_var_es(returns: np.ndarray, confidence: float) -> tuple:
    """Compute both VaR and Expected Shortfall (CVaR)."""
    var = float(-np.percentile(returns, (1 - confidence) * 100))
    es = float(-returns[returns <= -var].mean()) if any(returns <= -var) else var
    return var, es


def compute_var_suite(
    market_df: pd.DataFrame = None,
    portfolio_value: float = cfg.EXCHANGE_AUM,
    portfolio_weights: dict = None,
) -> dict:
    """
    Compute the full hybrid VaR suite: HS, FHS, Stressed, and Parametric scenarios.
    """
    if market_df is None:
        market_df = generate_market_data()

    if portfolio_weights is None:
        portfolio_weights = {"BTC": 0.50, "ETH": 0.30, "ALT": 0.20}

    btc_returns = market_df["btc_return"].values
    
    # HS metrics
    hs_99_v, hs_99_es = compute_var_es(btc_returns[-cfg.VAR_LOOKBACK_DAYS:], 0.99)
    hs_95_v, hs_95_es = compute_var_es(btc_returns[-cfg.VAR_LOOKBACK_DAYS:], 0.95)
    
    # FHS metrics (simplified CVaR for EWMA)
    fhs_v = fhs_var(btc_returns)
    fhs_es = fhs_v * 1.2 # Proxy for ES in EWMA context
    
    # Stressed metrics
    s_var = stressed_var(btc_returns, market_df)
    worst_returns = get_worst_stress_window(market_df, cfg.STRESSED_VAR_WINDOW)["btc_return"].values
    s_var, s_es = compute_var_es(worst_returns, 0.99)

    # Parametric scenario losses
    scenarios = parametric_scenario_var(portfolio_weights, portfolio_value)

    # Two-tier reserve
    tier1 = max(hs_99_v * portfolio_value, fhs_v * portfolio_value)
    tier2 = max(s_var * portfolio_value, max(s["loss_usd"] for s in scenarios.values()))

    return {
        "hs_var_99_pct":  hs_99_v,
        "hs_var_99_usd":  hs_99_v * portfolio_value,
        "hs_cvar_99_usd": hs_99_es * portfolio_value,
        "hs_var_95_usd":  hs_95_v * portfolio_value,
        "fhs_var_99_pct": fhs_v,
        "fhs_var_99_usd": fhs_v * portfolio_value,
        "fhs_cvar_99_usd": fhs_es * portfolio_value,
        "stressed_var_pct": s_var,
        "stressed_var_99_usd": s_var * portfolio_value,
        "stressed_cvar_99_usd": s_es * portfolio_value,
        "scenario_losses":  scenarios,
        "tier1_reserve":    tier1,
        "tier2_reserve":    tier2,
        "ewma_ess_days":    cfg.EWMA_ESS,
        "portfolio_value":  portfolio_value,
    }


def var_comparison_table(var_result: dict) -> pd.DataFrame:
    """Render a comparison table of all VaR methods."""
    pv = var_result["portfolio_value"]
    rows = [
        {
            "Method":        "HS-VaR (365d)",
            "VaR % (99%)":   f"{var_result['hs_var_pct']:.2%}",
            "VaR $M (99%)":  f"${var_result['hs_var_99']/1e6:.1f}M",
            "Failure Mode":  "Blind to new regimes. Fails silently.",
        },
        {
            "Method":        f"FHS-VaR (EWMA λ={cfg.EWMA_LAMBDA}, ESS~{cfg.EWMA_ESS:.0f}d)",
            "VaR % (99%)":   f"{var_result['fhs_var_pct']:.2%}",
            "VaR $M (99%)":  f"${var_result['fhs_var_99']/1e6:.1f}M",
            "Failure Mode":  "Prices current vol only. Loses memory of tail events.",
        },
        {
            "Method":        "Stressed VaR (worst 90-day window)",
            "VaR % (99%)":   f"{var_result['stressed_var_pct']:.2%}",
            "VaR $M (99%)":  f"${var_result['stressed_var_99']/1e6:.1f}M",
            "Failure Mode":  "Only as bad as worst period in data.",
        },
    ]
    for scen, loss in var_result["scenario_losses"].items():
        rows.append({
            "Method":        f"Parametric: {scen.upper()} shock",
            "VaR % (99%)":   f"{loss['loss_pct']:.2%}",
            "VaR $M (99%)":  f"${loss['loss_usd']/1e6:.1f}M",
            "Failure Mode":  "Point estimate; no distribution. Forward-looking overlay.",
        })
    return pd.DataFrame(rows).set_index("Method")


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Computing hybrid VaR suite...")
    mdf = generate_market_data()
    var = compute_var_suite(mdf)

    print(f"\n  HS-VaR 99%      : {var['hs_var_pct']:.2%}  (${var['hs_var_99']/1e6:.1f}M)")
    print(f"  FHS-VaR 99%     : {var['fhs_var_pct']:.2%}  (${var['fhs_var_99']/1e6:.1f}M)")
    print(f"  Stressed VaR    : {var['stressed_var_pct']:.2%}  (${var['stressed_var_99']/1e6:.1f}M)")
    print(f"  EWMA ESS        : {var['ewma_ess_days']:.0f} days")
    print(f"\n  Tier 1 Reserve  : ${var['tier1_reserve']/1e6:.1f}M")
    print(f"  Tier 2 Reserve  : ${var['tier2_reserve']/1e6:.1f}M")
    print("\n  Scenario losses:")
    for s, v in var["scenario_losses"].items():
        print(f"    {s:6s}: {v['loss_pct']:.1%}  (${v['loss_usd']/1e6:.1f}M)")
    print("\n[historical_var.py] OK")
