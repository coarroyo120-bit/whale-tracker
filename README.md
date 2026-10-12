# Whale Tracker

A free, bilingual (English/Spanish) website showing what 10 well-known investors bought and sold last quarter, using public SEC 13F filings.

## Status
Version 1 in progress.

- [x] Download pipeline from SEC EDGAR (`src/fetch_13f.py`)
- [x] Website builder (`src/build_site.py`)
- [x] Daily automation with GitHub Actions + GitHub Pages
- [ ] Quarter-over-quarter comparison logic (`src/compare.py`)
- [ ] Data validation checks and findings write-up

## How it works

```
GitHub Actions (every day, 11:23 UTC)
  1. fetch_13f.py   -> asks SEC EDGAR for each fund's two latest 13F-HR filings
                       saves new ones to data/raw/ and lists them in data/filings.csv
  2. build_site.py  -> runs compare.py on each fund, writes site/index.html
  3. commits any new data, then publishes the site to GitHub Pages
```

The funds are listed in `whales.csv`. To track a different fund, add its name and SEC CIK number there.

## Run it on your Mac

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your.email@example.com"
python src/fetch_13f.py
python src/build_site.py
open site/index.html

# check the comparison logic
python -m unittest tests/test_compare.py -v
```

## Data notes and limitations

- **13F filings are delayed.** Funds report holdings as of the last day of each quarter and have 45 days to file, so the newest data can be up to 4.5 months old.
- **Long U.S. positions only.** Short positions, most foreign stocks, bonds, and cash don't appear.
- **Amendments.** Funds sometimes file a 13F-HR/A after the original. The site uses the original filing and shows a warning when an amendment exists.
- **Dollar values** are reported in whole dollars (the SEC switched from thousands in 2023). The comparison uses share counts, not dollars, so price moves don't look like trades.

## Disclaimer
Public SEC 13F data for education only. Not investment advice. Filings can be up to 45 days old and show long positions only.
