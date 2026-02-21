"""
scripts/export_results.py — Model Export Bridge
==============================================
Runs the full simulation suite and exports results for the web dashboard.
Generates dashboard/data.js with a hardcoded constant object.
"""

import os
import sys
import json
import numpy as np
import pandas as pd

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as cfg
from data.generator import generate_weekend_withdrawals, compute_gini
from models.withdrawal_forecast import run_all_scenarios
from models.reserve_optimizer import optimize_reserve, newsvendor_optimal_reserve
from models.stress_test import run_all_stress_tests, compute_safety_frontier
from models.historical_var import compute_var_suite
from models.insurance_fund import simulate_insurance_fund
from models.solvency import compute_solvency

def serialize_results(obj):
    """Recursively convert numpy types to Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: serialize_results(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_results(v) for v in obj]
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return serialize_results(obj.tolist())
    else:
        return obj

def run_export():
    print("Exporting model results for dashboard...")
    
    # 1. Load data from persistence
    print("  Loading persisted data...")
    users = pd.read_csv(cfg.USERS_CSV_PATH)
    market_df = pd.read_csv(cfg.MARKET_CSV_PATH)
    total_fiat = users['fiat_balance'].sum()  # Fiat liabilities (~$2.23B)
    total_assets = cfg.TOTAL_ASSETS_AUM       # Total AUM assets (~$2.9B)
    
    # 2. Run analysis
    print(f"  Running withdrawal Monte Carlo (10,000 paths) on ${total_fiat/1e9:.2f}B liabilities...")
    wd = run_all_scenarios(total_fiat, n_simulations=cfg.N_SIMULATIONS)
    
    print("  Running VaR suite...")
    var_result = compute_var_suite(market_df, total_fiat)
    
    print(f"  Running insurance fund simulation on ${total_assets/1e9:.2f}B total AUM...")
    if_results = simulate_insurance_fund(total_assets, n_simulations=1000)
    
    print("  Running solvency integration...")
    solvency_results = compute_solvency(
        wd, var_result, if_results, 
        total_fiat_liabilities=total_fiat,
        total_aum_assets=total_assets
    )
    
    print("  Running safety frontier analysis...")
    safety_frontiers = {}
    for sc in ['normal', 'mild', 'severe']:
        safety_frontiers[sc] = compute_safety_frontier(wd[sc]['hourly_paths'], total_fiat, n_points=50)

    # 3. Aggregate into DASHBOARD_BRIEF schema
    print("  Aggregating results...")
    
    # Run stress tests to get failure probabilities
    stress_results = run_all_stress_tests(wd, total_fiat)

    # Generate some histogram data for withdrawal distribution chart
    withdrawal_histograms = {}
    for sc in ['normal', 'mild', 'severe']:
        hist, bin_edges = np.histogram(wd[sc]['total_withdrawals'] / 1e6, bins=50, density=True)
        withdrawal_histograms[sc] = {
            'hist': serialize_results(hist),
            'bins': serialize_results(bin_edges)
        }

    dashboard_data = {
        'overview': {
            'totalFiat': float(total_fiat),
            'totalAUM': float(total_assets),
            'openInterest': float(total_assets * cfg.OI_TO_AUM_RATIO),
            'insuranceFund': float(total_assets * cfg.INSURANCE_FUND_INITIAL),
            'regimes': {
                'normal': 87.9, 
                'stressed': 9.8,
                'crisis': 2.3
            }
        },
        'scenarios': {
            sc: {
                'name': sc.capitalize(),
                'failureProb': float(stress_results[sc]['industry_10pct']['failure_rate']),
                'verdict': "SOLVENT" if "✓" in solvency_results[sc]['solvency_verdict'] else "INSOLVENT",
                'mean': float(wd[sc]['percentiles'][50]),
                'p95': float(wd[sc]['percentiles'][95]),
                'p99': float(wd[sc]['percentiles'][99]),
                'cvar99': float(wd[sc]['cvar_99']),
            } for sc in ['normal', 'mild', 'severe']
        },
        'withdrawalHistograms': withdrawal_histograms,
        'hourlyPaths': {
            sc: wd[sc]['hourly_paths'].mean(axis=1).cumsum().tolist() for sc in ['normal', 'mild', 'severe']
        },
        'solvency': {
            sc: {
                'liabilities': {
                    'withdrawal': float(solvency_results[sc]['fiat_withdrawal_demand']),
                    'derivatives': float(solvency_results[sc]['deriv_shortfall']),
                    'marketRisk': float(solvency_results[sc]['market_risk_loss'])
                },
                'assets': {
                    'fiatReserve': float(solvency_results[sc]['fiat_reserve']),
                    'insuranceFund': float(solvency_results[sc]['insurance_fund']),
                    'propCapital': float(solvency_results[sc]['prop_capital'])
                },
                'shortfall': float(abs(solvency_results[sc]['net_position']) if solvency_results[sc]['net_position'] < 0 else 0)
            } for sc in ['normal', 'mild', 'severe', 'luna']
        },
        'varComparison': {
            'hs': {
                'p95': float(var_result['hs_var_95_usd']), 
                'p99': float(var_result['hs_var_99_usd']),
                'cvar99': float(var_result['hs_cvar_99_usd'])
            },
            'fhs': {
                'p99': float(var_result['fhs_var_99_usd']),
                'cvar99': float(var_result['fhs_cvar_99_usd'])
            },
            'stressed': {
                'p99': float(var_result['stressed_var_99_usd']),
                'cvar99': float(var_result['stressed_cvar_99_usd'])
            },
            'luna': {
                'cvar99': float(var_result['scenario_losses']['luna']['loss_usd'])
            },
            'severe_shock': {
                'cvar99': float(var_result['scenario_losses']['severe']['loss_usd'])
            },
            'ewma_ess': int(var_result['ewma_ess_days'])
        },
        'safetyFrontier': {
            sc: {
                'x': safety_frontiers[sc]['reserve_pct_aum'].tolist(),
                'y': safety_frontiers[sc]['failure_rate'].tolist()
            } for sc in ['normal', 'mild', 'severe']
        },
        'ifDrawdown': serialize_results(if_results['severe']['if_drawdown_distribution'][:500]), 
        'reservePolicy': {
            'tier1': float(var_result['tier1_reserve']),
            'tier2': float(max(wd['severe']['percentiles'][95] - var_result['tier1_reserve'], 0)),
            'tier3': float(max(wd['severe']['cvar_99'] - wd['severe']['percentiles'][95], 0)),
            'annualCostTier1': float(var_result['tier1_reserve'] * cfg.YIELD_MID),
            'annualCostTier2': float(max(wd['severe']['percentiles'][95] - var_result['tier1_reserve'], 0) * cfg.YIELD_MID)
        }
    }

    # 4. Save to dashboard/data.js
    dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
    os.makedirs(dashboard_dir, exist_ok=True)
    
    output_path = os.path.join(dashboard_dir, "data.js")
    with open(output_path, "w") as f:
        f.write("// Liquidity Sentinel — Auto-generated Risk Model Results\n")
        f.write("const DATA = ")
        f.write(json.dumps(dashboard_data, indent=2))
        f.write(";\n")
        
    print(f"\nExport complete. results saved to: {output_path}")

if __name__ == "__main__":
    run_export()
