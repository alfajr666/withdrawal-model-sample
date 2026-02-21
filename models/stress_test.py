"""
models/stress_test.py — Hour-by-Hour Stress Engine
===================================================
Tracks cumulative withdrawals against a given reserve level across all
Monte Carlo paths. Identifies:
  - Failure rate (% of paths that exhaust reserves)
  - Time-to-Insolvency (TTI) distribution conditional on failure
  - Safety frontier: failure rate as a function of reserve level
"""

import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg


def run_stress_test(
    hourly_paths: np.ndarray,
    reserve_level: float,
) -> dict:
    """
    Hour-by-hour cumulative withdrawal tracking against a fixed reserve.

    Parameters
    ----------
    hourly_paths  : np.ndarray of shape (n_hours, n_simulations)
    reserve_level : float — available fiat reserve (USD)

    Returns
    -------
    dict with keys:
        failure_rate      : float — fraction of paths that exhaust reserve
        tti_distribution  : np.ndarray — time-to-insolvency in hours for failed paths
        tti_mean          : float — mean TTI conditional on failure
        tti_p25, tti_p50, tti_p75 : float — TTI percentiles conditional on failure
        survive_rate      : float — 1 - failure_rate
        n_simulations     : int
    """
    n_hours, n_sims = hourly_paths.shape

    # Cumulative withdrawals per path (n_hours x n_sims)
    cumulative = hourly_paths.cumsum(axis=0)

    # Breach: first hour cumulative > reserve
    # Shape: (n_sims,) — -1 if no breach
    tti_array = np.full(n_sims, -1, dtype=int)

    for sim in range(n_sims):
        breach_hours = np.where(cumulative[:, sim] > reserve_level)[0]
        if len(breach_hours) > 0:
            tti_array[sim] = breach_hours[0]

    failed_mask  = tti_array >= 0
    failure_rate = float(failed_mask.mean())

    tti_distribution = tti_array[failed_mask].astype(float)

    result = {
        "failure_rate":    failure_rate,
        "survive_rate":    1.0 - failure_rate,
        "tti_distribution": tti_distribution,
        "tti_mean":         float(tti_distribution.mean()) if len(tti_distribution) > 0 else np.nan,
        "tti_p25":          float(np.percentile(tti_distribution, 25)) if len(tti_distribution) > 0 else np.nan,
        "tti_p50":          float(np.percentile(tti_distribution, 50)) if len(tti_distribution) > 0 else np.nan,
        "tti_p75":          float(np.percentile(tti_distribution, 75)) if len(tti_distribution) > 0 else np.nan,
        "n_simulations":   n_sims,
        "reserve_level":   reserve_level,
    }
    return result


def compute_safety_frontier(
    hourly_paths: np.ndarray,
    total_fiat: float,
    n_points: int = 50,
) -> pd.DataFrame:
    """
    Compute the safety frontier: failure rate as a function of reserve level.

    Sweeps from 0% to 60% of AUM as reserve.

    Parameters
    ----------
    hourly_paths : np.ndarray (n_hours, n_sims)
    total_fiat   : float — AUM baseline (USD)
    n_points     : int — number of reserve levels to evaluate

    Returns
    -------
    pd.DataFrame with columns: reserve_level, reserve_pct_aum, failure_rate
    """
    reserve_levels = np.linspace(0, total_fiat * 0.60, n_points)
    rows = []

    for R in reserve_levels:
        test = run_stress_test(hourly_paths, R)
        rows.append({
            "reserve_level":    R,
            "reserve_pct_aum":  R / total_fiat,
            "failure_rate":     test["failure_rate"],
        })

    return pd.DataFrame(rows)


def run_all_stress_tests(
    withdrawal_results: dict,
    total_fiat: float,
) -> dict:
    """
    Run stress tests across all scenarios for three reserve levels:
      - Newsvendor optimal (p67)
      - Conservative (p95)
      - Industry baseline (10% AUM)

    Parameters
    ----------
    withdrawal_results : dict from withdrawal_forecast.run_all_scenarios()
    total_fiat         : float

    Returns
    -------
    dict: scenario → dict of stress test results per reserve level
    """
    industry_baseline = total_fiat * 0.10  # standard 10% rule of thumb

    output = {}
    for scenario, res in withdrawal_results.items():
        hourly_paths = res["hourly_paths"]

        nv_reserve   = float(np.percentile(res["total_withdrawals"], cfg.NEWSVENDOR_CRITICAL_RATIO * 100))
        cvar_reserve = res["cvar_99"]

        output[scenario] = {
            "newsvendor":   run_stress_test(hourly_paths, nv_reserve),
            "conservative": run_stress_test(hourly_paths, cvar_reserve),
            "industry_10pct": run_stress_test(hourly_paths, industry_baseline),
        }

    return output


def stress_summary_table(stress_results: dict) -> pd.DataFrame:
    """
    Render a summary table of failure rates and TTI across scenarios and reserve levels.
    """
    rows = []
    for scenario, level_results in stress_results.items():
        for level_name, res in level_results.items():
            rows.append({
                "Scenario":          scenario.capitalize(),
                "Reserve Level":     level_name.replace("_", " ").title(),
                "Failure Rate":      f"{res['failure_rate']:.1%}",
                "TTI Median (hrs)":  f"{res['tti_p50']:.0f}" if not np.isnan(res['tti_p50']) else "—",
                "TTI Mean (hrs)":    f"{res['tti_mean']:.0f}" if not np.isnan(res['tti_mean']) else "—",
            })
    return pd.DataFrame(rows).set_index(["Scenario", "Reserve Level"])


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from models.withdrawal_forecast import run_all_scenarios

    AUM = cfg.EXCHANGE_AUM
    print(f"Running stress tests on ${AUM/1e6:.0f}M AUM...")

    results = run_all_scenarios(AUM, n_simulations=2000)
    stress  = run_all_stress_tests(results, AUM)
    table   = stress_summary_table(stress)

    print("\nStress Test Summary:")
    print(table.to_string())
    print("\n[stress_test.py] OK")
