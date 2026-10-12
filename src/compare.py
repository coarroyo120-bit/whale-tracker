"""Quarter-over-quarter position changes for one fund.  <-- CARLOS WRITES THIS FILE

This is the analysis at the heart of the project, so write it yourself.
Until it's done, the website still builds; it just shows "moves coming soon"
for every fund.

Check your work with:
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

import pandas as pd


def compare_holdings(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError("Carlos: write the comparison logic here")
