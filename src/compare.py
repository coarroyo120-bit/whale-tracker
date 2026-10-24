"""Quarter-over-quarter position changes for one fund.

Written from a spec-first prompt: Carlos defined the rules and tests below,
and the code was generated against them and checked by the test suite.

Check the logic with:
    python -m unittest tests/test_compare.py -v

------------------------------------------------------------------------------
INPUT
  prev, curr: DataFrames for the earlier and later quarter, one row per line of
  the filing, with at least these columns:
      cusip, name_of_issuer, put_call, shares, value_usd
  put_call is "" for plain stock, "Put" or "Call" for options.

OUTPUT
  One row per position, with these columns:
      cusip, name_of_issuer, put_call,
      shares_prev, shares_curr, share_change, pct_change,
      value_prev, value_curr, action

  action is one of: NEW, ADDED, REDUCED, SOLD OUT, UNCHANGED
  shares_prev / shares_curr are 0 (not blank) when the position doesn't exist.
  pct_change is blank (NaN) for NEW positions, since you can't divide by zero.

TRAPS IN REAL 13F DATA (the tests check the first two)
  1. One stock can appear on several rows in the same filing (split by
     sub-manager or investment discretion). Combine them before comparing.
  2. Options are separate positions from the stock. Calls on Apple are not
     Apple shares. A position is a cusip *plus* put_call.
  3. Compare shares, not dollars. A position's dollar value changes when the
     price moves, even if the fund didn't trade a single share.
  4. Stock splits make share counts jump without any trading. You don't need
     to fix this, but write down in the README that it can happen.
------------------------------------------------------------------------------
"""

import numpy as np
import pandas as pd

# A position is a security plus its option type (blank, "Put" or "Call").
POSITION = ["cusip", "put_call"]

OUTPUT_COLUMNS = [
    "cusip", "name_of_issuer", "put_call",
    "shares_prev", "shares_curr", "share_change", "pct_change",
    "value_prev", "value_curr", "action",
]


def combine_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Trap 1: one position can be split across several rows. Add them up.

    Grouped by cusip + put_call only (not the name), because a company's
    name can be spelled differently from one quarter to the next.
    """
    return df.groupby(POSITION, as_index=False).agg(
        name_of_issuer=("name_of_issuer", "first"),
        shares=("shares", "sum"),
        value_usd=("value_usd", "sum"),
    )


def compare_holdings(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    # Step 1: one row per position in each quarter.
    before = combine_rows(prev)
    after = combine_rows(curr)

    # Step 2: line the quarters up side by side. "outer" keeps positions
    # that exist in only one quarter (NEW and SOLD OUT).
    merged = before.merge(after, on=POSITION, how="outer", suffixes=("_prev", "_curr"))

    # Use this quarter's name, or last quarter's if the position was sold.
    merged["name_of_issuer"] = merged["name_of_issuer_curr"].fillna(merged["name_of_issuer_prev"])

    # A position missing from one quarter held 0 shares worth $0 there.
    merged = merged.rename(columns={"value_usd_prev": "value_prev", "value_usd_curr": "value_curr"})
    for col in ["shares_prev", "shares_curr", "value_prev", "value_curr"]:
        merged[col] = merged[col].fillna(0)

    # Step 3: measure the change in shares (trap 3: never dollars).
    merged["share_change"] = merged["shares_curr"] - merged["shares_prev"]
    # Blank for NEW positions: you can't divide by zero shares.
    merged["pct_change"] = merged["share_change"] / merged["shares_prev"].replace(0, np.nan) * 100

    # Step 4: label each position. Checked in order; the first match wins.
    merged["action"] = np.select(
        [
            merged["shares_prev"] == 0,      # didn't own it before
            merged["shares_curr"] == 0,      # doesn't own it now
            merged["share_change"] > 0,
            merged["share_change"] < 0,
        ],
        ["NEW", "SOLD OUT", "ADDED", "REDUCED"],
        default="UNCHANGED",                 # same shares, even if the price moved
    )

    return merged[OUTPUT_COLUMNS]
