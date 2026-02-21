"""
models/insurance_fund.py — Derivatives Socialized Loss & Liquidation Cascade
=============================================================================
Models the exchange insurance fund lifecycle under market stress for
derivatives (perps/CFD equity) products.

Key mechanics:
  1. Generate synthetic trader population (retail + institutional leverage)
  2. Apply price shock → identify underwater positions
  3. Compute per-position margin shortfall
  4. Simulate 5-step liquidation cascade (liquidations create further price pressure)
  5. Track insurance fund drawdown → probability of exhaustion → expected clawback

CFD equity note: US stock CFDs correlation with BTC rises from 0.35 (normal) to
0.70 (crisis). They are NOT a diversifier when you need one.
"""

import numpy as np
import pandas as pd
from scipy import stats
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg


def generate_trader_population(
    aum: float,
    seed: int = cfg.RANDOM_SEED + 100,
) -> pd.DataFrame:
    """
    Generate synthetic trader population for a derivatives exchange.

    Parameters
    ----------
    aum  : float — exchange total fiat AUM (USD)
    seed : int

    Returns
    -------
    pd.DataFrame with columns:
        trader_id, trader_type, margin (USD), leverage, notional (USD), position (long/short)
    """
    rng = np.random.default_rng(seed)

    n_traders = cfg.N_TRADERS
    n_inst    = int(n_traders * cfg.INST_TRADER_SHARE)
    n_retail  = n_traders - n_inst

    # Total open interest = AUM * OI_TO_AUM_RATIO
    total_oi = aum * cfg.OI_TO_AUM_RATIO

    # Institutional share of OI notional
    inst_notional_total   = total_oi * cfg.INST_NOTIONAL_SHARE
    retail_notional_total = total_oi * (1 - cfg.INST_NOTIONAL_SHARE)

    def trucated_normal_leverage(mean, std, low, high, size, rng):
        a = (low - mean) / std
        b = (high - mean) / std
        return stats.truncnorm.rvs(a, b, loc=mean, scale=std, size=size, random_state=rng.integers(0, 2**31))

    # Retail traders: high freq, higher leverage, smaller notional
    retail_leverage = trucated_normal_leverage(
        cfg.RETAIL_LEVERAGE_MEAN, cfg.RETAIL_LEVERAGE_STD,
        cfg.RETAIL_LEVERAGE_MIN, cfg.RETAIL_LEVERAGE_MAX,
        n_retail, rng,
    )
    # Log-normal notional distribution (retail)
    retail_notional = rng.lognormal(
        mean=np.log(retail_notional_total / n_retail) - 0.5,
        sigma=1.0, size=n_retail
    )
    # Rescale to sum to target
    retail_notional = retail_notional / retail_notional.sum() * retail_notional_total

    # Institutional traders: rare, lower leverage, larger notional
    inst_leverage = trucated_normal_leverage(
        cfg.INST_LEVERAGE_MEAN, cfg.INST_LEVERAGE_STD,
        cfg.INST_LEVERAGE_MIN, cfg.INST_LEVERAGE_MAX,
        n_inst, rng,
    )
    inst_notional = rng.lognormal(
        mean=np.log(inst_notional_total / n_inst) - 0.5,
        sigma=0.8, size=n_inst
    )
    inst_notional = inst_notional / inst_notional.sum() * inst_notional_total

    # Margin = Notional / Leverage
    retail_margin = retail_notional / retail_leverage
    inst_margin   = inst_notional / inst_leverage

    # Random long/short positions
    retail_side = rng.choice([-1, 1], size=n_retail)  # -1=short, 1=long
    inst_side   = rng.choice([-1, 1], size=n_inst)

    retail_df = pd.DataFrame({
        "trader_id":   range(n_retail),
        "trader_type": "retail",
        "margin":      retail_margin,
        "leverage":    retail_leverage,
        "notional":    retail_notional,
        "position":    retail_side,
    })
    inst_df = pd.DataFrame({
        "trader_id":   range(n_retail, n_traders),
        "trader_type": "institutional",
        "margin":      inst_margin,
        "leverage":    inst_leverage,
        "notional":    inst_notional,
        "position":    inst_side,
    })

    traders = pd.concat([retail_df, inst_df], ignore_index=True)
    traders["trader_id"] = traders.index
    return traders


def compute_liquidations(
    traders: pd.DataFrame,
    price_shock: float,
) -> pd.DataFrame:
    """
    Compute per-position P&L and identify underwater/liquidated positions.

    Parameters
    ----------
    traders     : pd.DataFrame from generate_trader_population()
    price_shock : float — fractional price change (negative = price drop, e.g., -0.35)

    Returns
    -------
    pd.DataFrame with additional columns: pnl, net_margin, shortfall, liquidated
    """
    traders = traders.copy()

    # P&L for each position
    # Long positions lose when price drops; short positions gain
    traders["pnl"] = traders["position"] * price_shock * traders["notional"]

    # Net margin after P&L
    traders["net_margin"] = traders["margin"] + traders["pnl"]

    # Liquidation occurs when net_margin <= 0
    traders["liquidated"] = traders["net_margin"] <= 0

    # Shortfall = amount the insurance fund must absorb (negative net_margin)
    traders["shortfall"] = np.where(
        traders["liquidated"],
        -traders["net_margin"],  # positive amount of deficit
        0.0,
    )

    return traders


def simulate_liquidation_cascade(
    traders: pd.DataFrame,
    initial_shock: float,
    aum: float,
    insurance_fund_initial: float,
    n_steps: int = cfg.CASCADE_STEPS,
    seed: int = cfg.RANDOM_SEED + 200,
) -> dict:
    """
    Simulate multi-step liquidation cascade.

    Each step:
      1. Compute underwater positions given current price
      2. Force-close them → market sell pressure
      3. Market impact = (liquidated notional / total OI) * price_move_factor
      4. Apply additional price move proportional to sell pressure
      5. Recheck for further liquidations

    Parameters
    ----------
    traders                : pd.DataFrame
    initial_shock          : float — initial price drop (e.g., -0.35)
    aum                    : float — exchange AUM baseline
    insurance_fund_initial : float — starting IF balance (USD)
    n_steps                : int — cascade iterations

    Returns
    -------
    dict with: cascade_history, total_shortfall, if_drawdown, if_exhausted,
               clawback_required, final_price_shock
    """
    rng = np.random.default_rng(seed)

    total_oi         = aum * cfg.OI_TO_AUM_RATIO
    insurance_fund   = insurance_fund_initial
    cumulative_shock = initial_shock
    cascade_history  = []

    current_traders = traders.copy()
    # Track which traders have been liquidated already
    already_liquidated = np.zeros(len(current_traders), dtype=bool)

    for step in range(n_steps):
        # Apply current cumulative shock to non-yet-liquidated traders
        result = compute_liquidations(current_traders, cumulative_shock)

        # New liquidations this step (not previously liquidated)
        new_liq_mask = result["liquidated"] & ~already_liquidated

        step_shortfall     = result.loc[new_liq_mask, "shortfall"].sum()
        step_liq_notional  = result.loc[new_liq_mask, "notional"].sum()
        step_n_liquidated  = new_liq_mask.sum()

        # Insurance fund absorbs shortfall
        if_absorbed = min(step_shortfall, insurance_fund)
        insurance_fund -= if_absorbed
        shortfall_after_if = step_shortfall - if_absorbed

        cascade_history.append({
            "step":                 step + 1,
            "n_liquidated":         int(step_n_liquidated),
            "step_shortfall":       step_shortfall,
            "if_absorbed":          if_absorbed,
            "if_remaining":         insurance_fund,
            "shortfall_after_if":   shortfall_after_if,
            "liq_notional":         step_liq_notional,
            "cumulative_shock":     cumulative_shock,
        })

        already_liquidated |= new_liq_mask.values

        # Market impact from forced liquidations → amplifies price drop
        # Impact factor: liquidated notional relative to OI, scaled by amplifier
        if total_oi > 0 and step_liq_notional > 0:
            impact_ratio = step_liq_notional / total_oi
            # Additional shock: empirical factor — 1 unit of OI sold = ~0.5% additional move
            additional_shock = -impact_ratio * 0.005 * (1 + rng.uniform(0, 0.5))
            cumulative_shock += additional_shock

        # Stop cascade if no new liquidations
        if step_n_liquidated == 0:
            break

    total_shortfall    = sum(h["step_shortfall"] for h in cascade_history)
    total_if_drawdown  = insurance_fund_initial - insurance_fund
    if_exhausted       = insurance_fund <= 0
    clawback_required  = max(total_shortfall - insurance_fund_initial, 0)

    return {
        "cascade_history":       pd.DataFrame(cascade_history),
        "total_shortfall":       total_shortfall,
        "if_drawdown":           total_if_drawdown,
        "if_remaining":          insurance_fund,
        "if_exhausted":          if_exhausted,
        "clawback_required":     clawback_required,
        "final_price_shock":     cumulative_shock,
        "initial_shock":         initial_shock,
    }


def simulate_insurance_fund(
    aum: float = cfg.EXCHANGE_AUM,
    n_simulations: int = 500,
    seed: int = cfg.RANDOM_SEED,
) -> dict:
    """
    Monte Carlo simulation of insurance fund outcomes across stress scenarios.

    Tests Mild, Severe, and LUNA-style price shocks.

    Returns
    -------
    dict mapping scenario → {
        if_drawdown_distribution, exhaustion_probability,
        expected_clawback, mean_final_shock
    }
    """
    rng = np.random.default_rng(seed)

    if_initial = aum * cfg.INSURANCE_FUND_INITIAL
    traders    = generate_trader_population(aum, seed)

    scenario_shocks = {
        "normal": 0.0,
        "mild":   cfg.SCENARIO_SHOCKS["mild"]["BTC"],
        "severe": cfg.SCENARIO_SHOCKS["severe"]["BTC"],
        "luna":   cfg.SCENARIO_SHOCKS["luna"]["BTC"],
    }

    results = {}
    for scenario, shock in scenario_shocks.items():
        drawdowns     = []
        exhaustions   = []
        clawbacks     = []
        final_shocks  = []

        for i in range(n_simulations):
            # Add stochastic noise to initial shock (±20% of base)
            noisy_shock = shock * rng.uniform(0.8, 1.2)

            cascade = simulate_liquidation_cascade(
                traders, noisy_shock, aum, if_initial,
                seed=int(rng.integers(0, 2**31)),
            )
            drawdowns.append(cascade["if_drawdown"])
            exhaustions.append(int(cascade["if_exhausted"]))
            clawbacks.append(cascade["clawback_required"])
            final_shocks.append(cascade["final_price_shock"])

        results[scenario] = {
            "if_drawdown_distribution": np.array(drawdowns),
            "exhaustion_probability":   float(np.mean(exhaustions)),
            "expected_clawback":        float(np.mean(clawbacks)),
            "mean_if_drawdown":         float(np.mean(drawdowns)),
            "p99_if_drawdown":          float(np.percentile(drawdowns, 99)),
            "mean_final_shock":         float(np.mean(final_shocks)),
        }

    return results


def insurance_fund_summary_table(if_results: dict, aum: float) -> pd.DataFrame:
    """Render a summary table of insurance fund outcomes."""
    if_initial = aum * cfg.INSURANCE_FUND_INITIAL
    rows = []
    for scenario, res in if_results.items():
        rows.append({
            "Scenario":                   scenario.upper(),
            "IF Initial ($M)":            f"${if_initial/1e6:.1f}M",
            "Mean IF Drawdown ($M)":      f"${res['mean_if_drawdown']/1e6:.2f}M",
            "p99 IF Drawdown ($M)":       f"${res['p99_if_drawdown']/1e6:.2f}M",
            "Exhaustion Probability":     f"{res['exhaustion_probability']:.1%}",
            "Expected Clawback ($M)":     f"${res['expected_clawback']/1e6:.2f}M",
            "Final Price Shock (mean)":   f"{res['mean_final_shock']:.1%}",
        })
    return pd.DataFrame(rows).set_index("Scenario")


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    AUM = cfg.EXCHANGE_AUM
    print(f"Simulating insurance fund on ${AUM/1e6:.0f}M AUM derivatives exchange...")
    print(f"  Traders: {cfg.N_TRADERS:,}  |  IF initial: ${AUM * cfg.INSURANCE_FUND_INITIAL/1e6:.1f}M  |  OI: ${AUM * cfg.OI_TO_AUM_RATIO/1e6:.0f}M")

    results = simulate_insurance_fund(AUM, n_simulations=200)
    table   = insurance_fund_summary_table(results, AUM)
    print("\nInsurance Fund Summary:")
    print(table.to_string())
    print("\n[insurance_fund.py] OK")
