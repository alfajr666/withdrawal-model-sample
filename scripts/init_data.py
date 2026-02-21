"""
scripts/init_data.py — Data Persistence Script
==============================================
Generates and persists synthetic data to disk for easier inspection.
Creates data/raw/ directory and saves:
  - synthetic_users_scaled.csv  : 100K-user base with fiat balances
  - market_history_365d.csv      : 365-day regime-switching market data
"""

import os
import sys
import pandas as pd

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as cfg
from data.generator import generate_user_base
from data.market_data import generate_market_data

def run_init():
    """Generate and save data."""
    print("Initiating data generation and persistence...")
    
    # Create data/raw directory
    raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    print(f"  Target directory: {raw_dir}")

    # 1. Generate and save user base
    print("  Generating user base (100K users)...")
    users = generate_user_base(target_aum=cfg.FIAT_LIABILITIES_TARGET)
    users_path = os.path.join(raw_dir, "synthetic_users_scaled.csv")
    users.to_csv(users_path, index=False)
    print(f"  Saved: {users_path}")

    # 2. Generate and save market data
    print("  Generating market history (365 days)...")
    market_df = generate_market_data(n_days=cfg.N_DAYS_HISTORY)
    market_path = os.path.join(raw_dir, "market_history_365d.csv")
    market_df.to_csv(market_path, index=False)
    print(f"  Saved: {market_path}")

    print("\nData initialization complete. All raw files persisted.")
    print("Ready for inspection or further analysis.")

if __name__ == "__main__":
    run_init()
