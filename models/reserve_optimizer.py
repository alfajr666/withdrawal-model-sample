"""
models/reserve_optimizer.py — Newsvendor Reserve Optimization
=============================================================
Applies the Newsvendor model to determine the cost-optimal fiat reserve level.

Objective: Minimize expected cost = opportunity cost on excess + shortfall cost on deficit.
Optimal quantile: q* = emergency_cost / (opportunity_cost + emergency_cost)

At mid-point costs (4.5% opp, 9% emergency): q* ≈ 0.667 (67th percentile).
"""

import numpy as np
import pandas as pd
from scipy import stats
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg


def newsvendor_optimal_reserve(
    withdrawal_distribution: np.ndarray,
    opportunity_cost: float = cfg.YIELD_MID,
    emergency_cost: float = cfg.EMERGENCY_COST_MID,
) -> dict:
    """
    Compute the Newsvendor optimal reserve for a given withdrawal distribution.

    The Newsvendor critical ratio:
        q* = emergency_cost / (opportunity_cost + emergency_cost)

    This is the quantile of the withdrawal distribution to hold as reserve.

    Parameters
    ----------
    withdrawal_distribution : np.ndarray — simulated total withdrawals (N_SIMULATIONS,)
    opportunity_cost        : float — annualized yield cost of holding idle fiat
    emergency_cost          : float — annualized cost of emergency funding (credit line, forced liquidation)

    Returns
    -------
    dict with keys: critical_ratio, optimal_reserve, cvar_99_reserve, annual_cost_optimal,
                    annual_cost_cvar, annual_cost_unhedged
    """
    critical_ratio = emergency_cost / (opportunity_cost + emergency_cost)

    # Newsvendor optimal
    optimal_reserve = float(np.percentile(withdrawal_distribution, critical_ratio * 100))
    # Conservative: CVaR 99%
    var_99  = float(np.percentile(withdrawal_distribution, 99))
    cvar_99 = float(withdrawal_distribution[withdrawal_distribution >= var_99].mean())

    # Annual costs (annualizing from weekend-horizon reserve)
    # Opportunity cost = reserve held (idle) * annual yield rate
    annual_cost_optimal = optimal_reserve * opportunity_cost
    annual_cost_cvar    = cvar_99 * opportunity_cost

    # Cost if unhedged: expected shortfall * emergency funding rate
    shortfall_optimal = np.mean(np.maximum(withdrawal_distribution - optimal_reserve, 0))
    annual_cost_unhedged_optimal = shortfall_optimal * emergency_cost * 52  # ~52 weekends/year

    return {
        "critical_ratio":            critical_ratio,
        "optimal_reserve":           optimal_reserve,
        "cvar_99_reserve":           cvar_99,
        "annual_cost_optimal_hold":  annual_cost_optimal,
        "annual_cost_cvar_hold":     annual_cost_cvar,
        "annual_cost_unhedged":      annual_cost_unhedged_optimal,
        "opportunity_cost_rate":     opportunity_cost,
        "emergency_cost_rate":       emergency_cost,
    }


def compute_cost_curve(
    withdrawal_distribution: np.ndarray,
    opportunity_cost: float = cfg.YIELD_MID,
    emergency_cost: float = cfg.EMERGENCY_COST_MID,
    n_points: int = 100,
) -> pd.DataFrame:
    """
    Compute the expected cost curve across all reserve levels.

    This generates the U-shaped cost curve showing the newsvendor optimum.

    Parameters
    ----------
    withdrawal_distribution : np.ndarray — simulated withdrawals
    n_points                : int — number of points along reserve axis

    Returns
    -------
    pd.DataFrame with columns: reserve_level, opportunity_cost, shortfall_cost, total_cost
    """
    max_reserve = float(np.percentile(withdrawal_distribution, 99.9))
    reserve_levels = np.linspace(0, max_reserve, n_points)

    rows = []
    for R in reserve_levels:
        # Opportunity cost: holding idle capital
        opp_cost = R * opportunity_cost

        # Shortfall cost: expected unmet withdrawals * emergency rate * frequency
        shortfall = np.mean(np.maximum(withdrawal_distribution - R, 0))
        shortage_cost = shortfall * emergency_cost * 52  # annualized over ~52 weekends

        rows.append({
            "reserve_level":    R,
            "opportunity_cost": opp_cost,
            "shortfall_cost":   shortage_cost,
            "total_cost":       opp_cost + shortage_cost,
        })

    return pd.DataFrame(rows)


def optimize_reserve(
    results_by_scenario: dict,
    total_fiat: float,
    opportunity_cost: float = cfg.YIELD_MID,
    emergency_cost: float = cfg.EMERGENCY_COST_MID,
) -> pd.DataFrame:
    """
    Run Newsvendor optimization across all three scenarios.

    Parameters
    ----------
    results_by_scenario : dict — output from withdrawal_forecast.run_all_scenarios()
    total_fiat          : float — exchange AUM for percentage calculations

    Returns
    -------
    pd.DataFrame — scenario × reserve metric table
    """
    rows = []
    for scenario, res in results_by_scenario.items():
        nv = newsvendor_optimal_reserve(
            res["total_withdrawals"], opportunity_cost, emergency_cost
        )
        rows.append({
            "Scenario":               scenario.capitalize(),
            "Newsvendor Reserve (Rp B)": nv["optimal_reserve"] / 1e9,
            "CVaR 99% Reserve (Rp B)":  nv["cvar_99_reserve"] / 1e9,
            "Newsvendor % AUM":        nv["optimal_reserve"] / total_fiat,
            "CVaR 99% % AUM":          nv["cvar_99_reserve"] / total_fiat,
            "Annual Cost - NV (Rp B)":   nv["annual_cost_optimal_hold"] / 1e9,
            "Annual Cost - CVaR (Rp B)": nv["annual_cost_cvar_hold"] / 1e9,
            "Annual Cost - Unhedged (Rp B)": nv["annual_cost_unhedged"] / 1e9,
        })

    return pd.DataFrame(rows).set_index("Scenario")


def tier_reserve(
    var_result: dict,
    withdrawal_p95: float,
    withdrawal_p99: float,
    insurance_fund_obligation: float = 0.0,
) -> pd.DataFrame:
    """
    Allocate the total reserve across three liquidity tiers.

    Layer 1 — Instant : max(HS-VaR, FHS-VaR)
    Layer 2 — Fast    : p95 withdrawal - Layer 1
    Layer 3 — Liquid  : p99 withdrawal + IF obligation - Layer 2

    Parameters
    ----------
    var_result              : dict from historical_var.compute_var_suite()
    withdrawal_p95          : float — 95th percentile of simulated withdrawals
    withdrawal_p99          : float — 99th percentile of simulated withdrawals
    insurance_fund_obligation : float — expected IF drawdown under stress

    Returns
    -------
    pd.DataFrame — tier-level reserve breakdown
    """
    tier1 = max(var_result["hs_var_99"], var_result["fhs_var_99"])
    tier2 = max(withdrawal_p95 - tier1, 0)
    tier3 = max(withdrawal_p99 + insurance_fund_obligation - tier1 - tier2, 0)

    rows = [
        {"Tier": "Layer 1 — Instant", "Instrument": "Fiat / Bank",           "Amount (Rp B)": tier1 / 1e9, "Yield": "~0%"},
        {"Tier": "Layer 2 — Fast",    "Instrument": "Money Market / Stables", "Amount (Rp B)": tier2 / 1e9, "Yield": "~6–7%"},
        {"Tier": "Layer 3 — Liquid",  "Instrument": "T-bills",                "Amount (Rp B)": tier3 / 1e9, "Yield": "~6–7%"},
    ]
    df = pd.DataFrame(rows).set_index("Tier")
    df.loc["TOTAL", :] = ["All instruments", df["Amount (Rp B)"].sum(), "Blended"]
    return df


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from data.generator import generate_user_base
    from models.withdrawal_forecast import run_all_scenarios

    AUM   = cfg.EXCHANGE_AUM
    print(f"Running reserve optimization on Rp {AUM/1e12:.1f}T AUM...")

    results = run_all_scenarios(AUM, n_simulations=2000)
    opt_table = optimize_reserve(results, AUM)

    print("\nReserve Optimization Summary:")
    print(opt_table.to_string())
    print("\n[reserve_optimizer.py] OK")
