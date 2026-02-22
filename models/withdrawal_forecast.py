"""
models/withdrawal_forecast.py — Monte Carlo Withdrawal Forecasting
==================================================================
Runs 10,000-path Monte Carlo simulation combining retail (Gamma) and
institutional (Poisson + Log-normal) withdrawal processes across three
stress scenarios. Outputs simulated distributions, VaR, and CVaR.
"""

import numpy as np
import pandas as pd
from scipy import stats
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg
from data.generator import generate_retail_withdrawals, generate_institutional_withdrawals


def run_withdrawal_monte_carlo(
    total_fiat: float,
    scenario: str,
    n_simulations: int = cfg.N_SIMULATIONS,
    n_hours: int = cfg.WEEKEND_HOURS,
    seed: int = cfg.RANDOM_SEED,
) -> dict:
    """
    Run Monte Carlo simulation of total withdrawals over WEEKEND_HOURS.

    Each simulation path generates independent retail (Gamma) +
    institutional (Poisson + Log-normal) withdrawal series and sums them.

    Parameters
    ----------
    total_fiat    : float — total exchange fiat AUM (USD)
    scenario      : "normal" | "mild" | "severe"
    n_simulations : int — number of Monte Carlo paths
    n_hours       : int — simulation horizon

    Returns
    -------
    dict with keys:
        total_withdrawals   : np.ndarray (n_simulations,) — total over horizon
        hourly_paths        : np.ndarray (n_hours, n_simulations) — hourly series
        var_99              : float — 99th percentile total withdrawal
        cvar_99             : float — CVaR (expected shortfall) at 99%
        percentiles         : dict — key quantiles {50, 75, 90, 95, 99, 99.9}
        scenario            : str
        total_fiat          : float
    """
    rng_base = np.random.default_rng(seed)

    total_withdrawals = np.zeros(n_simulations)
    hourly_paths      = np.zeros((n_hours, n_simulations))

    for i in range(n_simulations):
        sim_seed = int(rng_base.integers(0, 2**31))

        retail = generate_retail_withdrawals(total_fiat, scenario, n_hours, sim_seed)
        inst   = generate_institutional_withdrawals(total_fiat, scenario, n_hours, sim_seed + 1)

        path = retail + inst
        hourly_paths[:, i]  = path
        total_withdrawals[i] = path.sum()

    var_99  = float(np.percentile(total_withdrawals, 99))
    cvar_99 = float(total_withdrawals[total_withdrawals >= var_99].mean())

    percentiles = {
        p: float(np.percentile(total_withdrawals, p))
        for p in [50, 75, 90, 95, 99, 99.9]
    }

    return {
        "total_withdrawals": total_withdrawals,
        "hourly_paths":      hourly_paths,
        "var_99":            var_99,
        "cvar_99":           cvar_99,
        "percentiles":       percentiles,
        "scenario":          scenario,
        "total_fiat":        total_fiat,
    }


def run_all_scenarios(
    total_fiat: float,
    n_simulations: int = cfg.N_SIMULATIONS,
    n_hours: int = cfg.WEEKEND_HOURS,
    seed: int = cfg.RANDOM_SEED,
) -> dict:
    """
    Run Monte Carlo for all three scenarios.

    Returns
    -------
    dict mapping scenario → result dict from run_withdrawal_monte_carlo
    """
    results = {}
    for i, scenario in enumerate(["normal", "mild", "severe"]):
        results[scenario] = run_withdrawal_monte_carlo(
            total_fiat, scenario, n_simulations, n_hours, seed + i * 1000
        )
    return results


def summarize_results(results: dict, total_fiat: float) -> pd.DataFrame:
    """
    Build a summary table comparing scenarios across key risk metrics.

    Returns
    -------
    pd.DataFrame — scenario × metric comparison table
    """
    rows = []
    for scenario, res in results.items():
        rows.append({
            "Scenario":       scenario.capitalize(),
            "Median (Rp B)":    res["percentiles"][50] / 1e9,
            "p90 (Rp B)":       res["percentiles"][90] / 1e9,
            "p95 (Rp B)":       res["percentiles"][95] / 1e9,
            "VaR 99% (Rp B)":   res["var_99"] / 1e9,
            "CVaR 99% (Rp B)":  res["cvar_99"] / 1e9,
            "Median % AUM":   res["percentiles"][50] / total_fiat,
            "VaR 99% % AUM":  res["var_99"] / total_fiat,
        })
    df = pd.DataFrame(rows).set_index("Scenario")
    return df


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    AUM = cfg.EXCHANGE_AUM
    print(f"Running Monte Carlo withdrawal forecasting on Rp {AUM/1e12:.1f}T AUM...")

    results = run_all_scenarios(AUM, n_simulations=1000)  # fast smoke test

    summary = summarize_results(results, AUM)
    print("\n", summary.to_string())
    print("\n[withdrawal_forecast.py] OK")
