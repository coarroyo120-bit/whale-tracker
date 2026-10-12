"""Tests for compare_holdings. Run from the repo root:

    python -m unittest tests/test_compare.py -v

These describe what the function must do. They don't tell you how to do it.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from compare import compare_holdings  # noqa: E402

COLUMNS = ["cusip", "name_of_issuer", "put_call", "shares", "value_usd"]

PREV = pd.DataFrame([
    ["AAA111111", "ALPHA CORP", "", 60, 600],
    ["AAA111111", "ALPHA CORP", "", 40, 400],   # same stock, second row (trap 1)
    ["BBB222222", "BETA INC", "", 200, 2000],
    ["DDD444444", "DELTA CO", "", 80, 800],
    ["EEE555555", "ECHO LTD", "", 10, 100],
], columns=COLUMNS)

CURR = pd.DataFrame([
    ["AAA111111", "ALPHA CORP", "", 150, 1800],
    ["AAA111111", "ALPHA CORP", "Call", 5, 50],  # options on the same stock (trap 2)
    ["BBB222222", "BETA INC", "", 50, 500],
    ["CCC333333", "CHARLIE CORP", "", 30, 300],
    ["EEE555555", "ECHO LTD", "", 10, 250],     # price went up, no trading (trap 3)
], columns=COLUMNS)


class TestCompareHoldings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = compare_holdings(PREV, CURR)

    def row(self, cusip, put_call=""):
        match = self.result[(self.result["cusip"] == cusip) & (self.result["put_call"] == put_call)]
        self.assertEqual(len(match), 1, f"expected exactly one row for {cusip} {put_call!r}")
        return match.iloc[0]

    def test_has_required_columns(self):
        for col in ["cusip", "name_of_issuer", "put_call", "shares_prev", "shares_curr",
                    "share_change", "pct_change", "value_prev", "value_curr", "action"]:
            self.assertIn(col, self.result.columns)

    def test_one_row_per_position(self):
        # AAA stock, AAA call, BBB, CCC, DDD, EEE
        self.assertEqual(len(self.result), 6)

    def test_combines_duplicate_rows_before_comparing(self):
        r = self.row("AAA111111")
        self.assertEqual(r["shares_prev"], 100)
        self.assertEqual(r["share_change"], 50)
        self.assertEqual(r["action"], "ADDED")
        self.assertAlmostEqual(r["pct_change"], 50.0)

    def test_options_are_a_separate_position(self):
        self.assertEqual(self.row("AAA111111", "Call")["action"], "NEW")

    def test_reduced(self):
        r = self.row("BBB222222")
        self.assertEqual(r["action"], "REDUCED")
        self.assertEqual(r["share_change"], -150)
        self.assertAlmostEqual(r["pct_change"], -75.0)

    def test_new(self):
        r = self.row("CCC333333")
        self.assertEqual(r["action"], "NEW")
        self.assertEqual(r["shares_prev"], 0)
        self.assertTrue(pd.isna(r["pct_change"]))

    def test_sold_out(self):
        r = self.row("DDD444444")
        self.assertEqual(r["action"], "SOLD OUT")
        self.assertEqual(r["shares_curr"], 0)
        self.assertAlmostEqual(r["pct_change"], -100.0)

    def test_price_change_alone_is_unchanged(self):
        r = self.row("EEE555555")
        self.assertEqual(r["action"], "UNCHANGED")
        self.assertEqual(r["value_curr"], 250)


if __name__ == "__main__":
    unittest.main()
