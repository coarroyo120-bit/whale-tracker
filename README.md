# Whale Tracker

A free, bilingual (English/Spanish) website showing what 10 well-known investors bought and sold last quarter, using public SEC 13F filings.

**Live site:** https://coarroyo120-bit.github.io/whale-tracker/

## Status
Version 1 live. Data refreshes daily.

- [x] Download pipeline from SEC EDGAR (`src/fetch_13f.py`)
- [x] Website builder (`src/build_site.py`)
- [x] Daily automation with GitHub Actions + GitHub Pages
- [x] Quarter-over-quarter comparison logic (`src/compare.py`), 8 unit tests passing
- [x] Findings write-up from the first live run (below)
- [x] Older-filing label (flags a fund whose newest filing is behind the other funds)
- [x] Units label (flags a filing whose dollar values look 1,000 times too small)

## Findings from the first live run (Oct 2026)

The first run made 1,902 position comparisons across 10 funds (positions from both quarters combined). Checking the output turned up four things worth knowing about 13F data:

1. **One stock, many lines.** Berkshire Hathaway's Q2 2026 filing has 89 lines but only 29 distinct positions, because Berkshire reports many holdings split across separate lines. Comparing raw lines would have produced fake buys and sells, so the comparison combines lines by CUSIP and option type first. Icahn's filing shows the same pattern (18 lines, 12 positions).
2. **Same company, two securities.** Alphabet appears twice in Berkshire's moves. That's correct: Class A and Class C shares are different securities with different CUSIPs.
3. **A stale fund.** The newest 13F-HR under Greenlight Capital's CIK (1079114) covers Q4 2023, so its "moves" are more than two years old. To check: whether Greenlight now files under a different SEC entity.
4. **A fund a quarter behind.** Pershing Square's newest original 13F-HR covers Q1 2026, while the other funds are on Q2 2026. To check on EDGAR.

## How it was built

Built with AI assistance (Claude). I wrote the specs, including the rules for the quarter-over-quarter comparison, and chose the funds and scope. Claude wrote the code and the unit tests, and set up the GitHub Actions workflow and GitHub Pages hosting at my direction. I reviewed and merged the pull requests, checked the output before it went live, and reviewed and edited the site's HTML/CSS.

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

- **13F filings are delayed.** Each filing shows holdings on the last day of a quarter and can arrive up to 45 days later, so by the time the next one comes out, the data can be about 4.5 months old. The page labels any fund whose newest filing is behind the others, and the date at the top is the newest filing date on the page, not the build date.
- **Long U.S. positions only.** Short positions, most foreign stocks, bonds, and cash don't appear.
- **Amendments.** Funds sometimes file a 13F-HR/A after the original. The site uses the original filing and shows a warning when an amendment exists.
- **Dollar values.** The SEC has required whole dollars since Jan 3, 2023, but some filers still report in thousands. The site shows values as filed and labels any filing whose median value per share is under $1, a sign the numbers are 1,000 times too small. In the Q2 2026 data, Baupost and Duquesne get this label. The comparison uses share counts, not dollars, so price moves don't look like trades and the units issue doesn't change the move labels.
- **Stock splits** can make a share count jump with no trading. After a 2-for-1 split, a fund that bought nothing shows double the shares and gets labeled ADDED. The comparison doesn't adjust for splits yet.

## Disclaimer
Public SEC 13F data for education only. Not investment advice. Filings can be up to 45 days old and show long positions only.
