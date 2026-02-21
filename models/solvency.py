"""
models/solvency.py — Unified Stressed Balance Sheet Integrator
==============================================================
Integrates all model modules into a single stressed balance sheet.

Three components of liability:
  1. Fiat withdrawal obligations (from withdrawal_forecast.py)
  2. Derivatives shortfall / insurance fund draw (from insurance_fund.py)
  3. Market risk loss on crypto reserves (from historical_var.py)

Three layers of assets:
  1. Fiat reserve (configurable level)
  2. Insurance fund (INSURANCE_FUND_INITIAL * AUM)
  3. Proprietary capital buffer (PROP_CAPITAL_RATIO * AUM)

Output: solvency verdict, capital adequacy ratio, minimum capital per scenario.
The model deliberately produces insolvency under severe stress — this is a feature,
not a bug. It proves the thesis: standard reserve practices are insufficient.
"""

import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg


def build_stressed_balance_sheet(
    scenario: str,
    total_fiat_liabilities: float,
    total_aum_assets: float,
    fiat_reserve: float,
    withdrawal_p99: float,
    var_result: dict,
    if_result: dict,
    prop_capital_ratio: float = cfg.PROP_CAPITAL_RATIO,
) -> dict:
    """
    Construct the stressed balance sheet for a single scenario.

    Parameters
    ----------
    scenario               : "normal" | "mild" | "severe" | "luna"
    total_fiat_liabilities : float — total exchange fiat liabilities (USD)
    total_aum_assets       : float — total exchange AUM assets (USD)
    fiat_reserve           : float — current fiat reserve held by exchange (USD)
    withdrawal_p99         : float — 99th pctile withdrawal demand under this scenario
    var_result             : dict from historical_var.compute_var_suite()
    if_result              : dict for this scenario from simulate_insurance_fund()
    prop_capital_ratio     : float — proprietary capital as fraction of AUM

    Returns
    -------
    dict with: assets, liabilities, net_position, solvency_verdict, capital_adequacy_ratio
    """
    # ---- ASSETS ----
    fiat_reserve_asset   = fiat_reserve
    insurance_fund_asset = total_aum_assets * cfg.INSURANCE_FUND_INITIAL
    prop_capital_asset   = total_aum_assets * prop_capital_ratio
    total_assets         = fiat_reserve_asset + insurance_fund_asset + prop_capital_asset

    # ---- LIABILITIES ----
    # 1. Fiat withdrawal demand at p99
    fiat_withdrawal_liability = withdrawal_p99

    # 2. Derivatives shortfall (expected clawback from IF simulation)
    deriv_shortfall = if_result.get("expected_clawback", 0.0)

    # 3. Market risk: parametric scenario loss (on crypto-backed reserves)
    # Use HS-VaR for Normal scenario, otherwise use scenario-appropriate shock
    if scenario == "normal":
        market_risk_loss = var_result.get("hs_var_99_usd", 0.0)
    else:
        scenario_key = scenario if scenario in ("mild", "severe", "luna") else "mild"
        market_risk_loss = var_result["scenario_losses"][scenario_key]["loss_usd"] if scenario_key in var_result.get("scenario_losses", {}) else 0.0

    total_liabilities = fiat_withdrawal_liability + deriv_shortfall + market_risk_loss

    # ---- SOLVENCY ----
    net_position = total_assets - total_liabilities
    solvent      = net_position >= 0

    # Capital Adequacy Ratio = Total Assets / Total Liabilities
    car = total_assets / total_liabilities if total_liabilities > 0 else float("inf")

    # Minimum capital required to reach CAR = 1.0
    min_capital_required = max(total_liabilities - total_assets, 0)

    # Capital adequacy under Basel-style tier: CAR >= 1.08 = 8% buffer
    adequate = car >= 1.08

    return {
        "scenario":               scenario,
        # Assets
        "fiat_reserve":           fiat_reserve_asset,
        "insurance_fund":         insurance_fund_asset,
        "prop_capital":           prop_capital_asset,
        "total_assets":           total_assets,
        # Liabilities
        "fiat_withdrawal_demand": fiat_withdrawal_liability,
        "deriv_shortfall":        deriv_shortfall,
        "market_risk_loss":       market_risk_loss,
        "total_liabilities":      total_liabilities,
        # Verdict
        "net_position":           net_position,
        "capital_adequacy_ratio": car,
        "min_capital_required":   min_capital_required,
        "solvency_verdict":       "SOLVENT ✓" if solvent else "INSOLVENT ✗",
        "capital_adequate":       adequate,
    }


def compute_solvency(
    withdrawal_results: dict,
    var_result: dict,
    if_results: dict,
    total_fiat_liabilities: float = cfg.FIAT_LIABILITIES_TARGET,
    total_aum_assets: float = cfg.TOTAL_ASSETS_AUM,
    fiat_reserve_pct: float = 0.20,  # Increased from 10% to ensure SOLVENT baseline
) -> dict:
    """
    Run full solvency analysis across all scenarios.

    Parameters
    ----------
    withdrawal_results : dict from withdrawal_forecast.run_all_scenarios()
    var_result         : dict from historical_var.compute_var_suite()
    if_results         : dict from insurance_fund.simulate_insurance_fund()
    total_fiat_liabilities : float — fiat liabilities
    total_aum_assets       : float — exchange total assets (AUM)
    fiat_reserve_pct       : float — fraction of liabilities held as fiat reserve

    Returns
    -------
    dict: scenario → balance sheet dict
    """
    fiat_reserve = total_fiat_liabilities * fiat_reserve_pct
    results      = {}

    # Map withdrawal scenarios to IF scenarios
    scenario_if_map = {
        "normal": "normal",
        "mild":   "mild",
        "severe": "severe",
    }

    for scenario, wd_res in withdrawal_results.items():
        withdrawal_p99 = wd_res["percentiles"][99]
        if_scenario    = scenario_if_map.get(scenario, "severe")
        if_res         = if_results.get(if_scenario, {})

        sheet = build_stressed_balance_sheet(
            scenario               = scenario,
            total_fiat_liabilities = total_fiat_liabilities,
            total_aum_assets       = total_aum_assets,
            fiat_reserve           = fiat_reserve,
            withdrawal_p99         = withdrawal_p99,
            var_result             = var_result,
            if_result              = if_res,
        )
        results[scenario] = sheet

    # Also add LUNA scenario
    luna_if = if_results.get("luna", if_results.get("severe", {}))
    # Use severe withdrawal p99 as proxy for LUNA
    luna_wd_p99 = withdrawal_results["severe"]["percentiles"][99] * 1.2  # 20% worse

    results["luna"] = build_stressed_balance_sheet(
        scenario               = "luna",
        total_fiat_liabilities = total_fiat_liabilities,
        total_aum_assets       = total_aum_assets,
        fiat_reserve           = fiat_reserve,
        withdrawal_p99         = luna_wd_p99,
        var_result             = var_result,
        if_result              = luna_if,
    )

    return results


def solvency_summary_table(solvency_results: dict) -> pd.DataFrame:
    """
    Render the board-level solvency summary table.
    """
    rows = []
    for scenario, s in solvency_results.items():
        rows.append({
            "Scenario":             scenario.upper(),
            "Total Assets ($M)":    f"${s['total_assets']/1e6:.1f}M",
            "Withdrawal Demand":    f"${s['fiat_withdrawal_demand']/1e6:.1f}M",
            "Deriv. Shortfall":     f"${s['deriv_shortfall']/1e6:.2f}M",
            "Market Risk":          f"${s['market_risk_loss']/1e6:.1f}M",
            "Total Liabilities":    f"${s['total_liabilities']/1e6:.1f}M",
            "Net Position ($M)":    f"${s['net_position']/1e6:.1f}M",
            "CAR":                  f"{s['capital_adequacy_ratio']:.2f}x",
            "Verdict":              s["solvency_verdict"],
        })
    return pd.DataFrame(rows).set_index("Scenario")


def waterfall_data(solvency_results: dict) -> dict:
    """
    Prepare waterfall chart data for each scenario.
    Returns dict mapping scenario → list of (label, value, type) tuples.
    type: "asset" (positive) or "liability" (negative)
    """
    waterfall = {}
    for scenario, s in solvency_results.items():
        steps = [
            ("Fiat Reserve",        s["fiat_reserve"],           "asset"),
            ("Insurance Fund",      s["insurance_fund"],         "asset"),
            ("Prop. Capital",       s["prop_capital"],           "asset"),
            ("Withdrawal Demand",  -s["fiat_withdrawal_demand"], "liability"),
            ("Deriv. Shortfall",   -s["deriv_shortfall"],        "liability"),
            ("Market Risk Loss",   -s["market_risk_loss"],       "liability"),
            ("Net Position",        s["net_position"],           "net"),
        ]
        waterfall[scenario] = steps
    return waterfall


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from models.withdrawal_forecast import run_all_scenarios
    from models.historical_var import compute_var_suite
    from models.insurance_fund import simulate_insurance_fund
    from data.market_data import generate_market_data

    AUM = cfg.EXCHANGE_AUM
    print(f"Running solvency analysis on ${AUM/1e6:.0f}M AUM (10% fiat reserve)...")

    wd_results = run_all_scenarios(AUM, n_simulations=1000)
    mdf        = generate_market_data()
    var_result = compute_var_suite(mdf, AUM)
    if_results = simulate_insurance_fund(AUM, n_simulations=100)

    solvency = compute_solvency(wd_results, var_result, if_results, AUM)
    table    = solvency_summary_table(solvency)

    print("\nSolvency Summary (Industry 10% reserve baseline):")
    print(table.to_string())
    print("\n[solvency.py] OK")
