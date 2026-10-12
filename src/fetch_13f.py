"""Download the two most recent 13F-HR filings for each fund in whales.csv.

Source: SEC EDGAR (free, no API key). SEC fair-access rules:
  - Every request must carry a User-Agent with your name and email.
  - Stay under 10 requests per second.

Set the User-Agent in an environment variable before running:
  export SEC_USER_AGENT="Your Name your.email@example.com"
  python src/fetch_13f.py

Output:
  data/raw/<cik>_<period>.csv   one row per line of the filing's information table (as filed)
  data/filings.csv              one row per filing we used, plus flags for amendments
"""

import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
FILINGS_CSV = ROOT / "data" / "filings.csv"
WHALES_CSV = ROOT / "whales.csv"

PAUSE_SECONDS = 0.25  # about 4 requests per second, well under the SEC's limit of 10


def get_session():
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        sys.exit(
            "SEC_USER_AGENT is not set. The SEC requires a name and email, e.g.\n"
            '  export SEC_USER_AGENT="Your Name your.email@example.com"'
        )
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    return session


def get(session, url, as_json=False):
    """GET with a polite pause and a few retries for temporary errors."""
    for attempt in range(4):
        time.sleep(PAUSE_SECONDS)
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.json() if as_json else resp.content
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(2 ** attempt * 2)
            continue
        resp.raise_for_status()
    resp.raise_for_status()


def list_13f_filings(session, cik):
    """Return the fund's name and a DataFrame of its recent 13F-HR and 13F-HR/A filings."""
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    sub = get(session, url, as_json=True)
    recent = pd.DataFrame(sub["filings"]["recent"])
    filings = recent[recent["form"].isin(["13F-HR", "13F-HR/A"])].copy()
    return sub.get("name", ""), filings


def find_info_table_url(session, cik, accession):
    """The information table is the .xml file in the filing that isn't primary_doc.xml."""
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
    index = get(session, f"{folder}/index.json", as_json=True)
    xml_files = [
        item for item in index["directory"]["item"]
        if item["name"].lower().endswith(".xml") and item["name"].lower() != "primary_doc.xml"
    ]
    if not xml_files:
        return None
    # If there is more than one, the information table is the biggest.
    biggest = max(xml_files, key=lambda item: int(item.get("size") or 0))
    return f"{folder}/{biggest['name']}"


def _local(tag):
    """Strip the XML namespace: '{http://...}nameOfIssuer' -> 'nameOfIssuer'."""
    return tag.rsplit("}", 1)[-1]


def _child_text(element, name):
    for child in element.iter():
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def parse_info_table(xml_bytes):
    """Turn a 13F information table XML file into a DataFrame, one row per infoTable entry."""
    root = ET.fromstring(xml_bytes)
    rows = []
    for entry in root.iter():
        if _local(entry.tag) != "infoTable":
            continue
        rows.append({
            "name_of_issuer": _child_text(entry, "nameOfIssuer"),
            "title_of_class": _child_text(entry, "titleOfClass"),
            "cusip": _child_text(entry, "cusip").upper(),
            "value_usd": _child_text(entry, "value"),
            "shares": _child_text(entry, "sshPrnamt"),
            "share_type": _child_text(entry, "sshPrnamtType"),  # SH = shares, PRN = principal amount
            "put_call": _child_text(entry, "putCall"),          # blank = stock; Put/Call = options
            "investment_discretion": _child_text(entry, "investmentDiscretion"),
            "other_manager": _child_text(entry, "otherManager"),
        })
    df = pd.DataFrame(rows)
    for col in ["value_usd", "shares"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
    return df


def main():
    session = get_session()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    whales = pd.read_csv(WHALES_CSV)
    used = []

    for _, whale in whales.iterrows():
        cik = int(whale["cik"])
        try:
            sec_name, filings = list_13f_filings(session, cik)
        except Exception as err:  # keep going if one fund fails
            print(f"[skip] {whale['fund']} (CIK {cik}): could not list filings: {err}")
            continue
        print(f"{whale['fund']}: SEC name is '{sec_name}'")

        originals = filings[filings["form"] == "13F-HR"].sort_values(
            ["reportDate", "filingDate"], ascending=False
        )
        # One original per quarter, keep the newest two quarters.
        latest_two = originals.drop_duplicates("reportDate").head(2)
        if len(latest_two) < 2:
            print(f"[skip] {whale['fund']}: fewer than two 13F-HR filings found")
            continue

        for _, filing in latest_two.iterrows():
            period = filing["reportDate"]
            out_file = RAW_DIR / f"{cik}_{period}.csv"
            amendments = filings[(filings["form"] == "13F-HR/A") & (filings["reportDate"] == period)]
            used.append({
                "fund": whale["fund"],
                "manager": whale["manager"],
                "cik": cik,
                "sec_name": sec_name,
                "period": period,
                "filing_date": filing["filingDate"],
                "accession": filing["accessionNumber"],
                "amendment_count": len(amendments),
                "raw_file": out_file.relative_to(ROOT).as_posix(),
            })
            if out_file.exists():
                continue  # filings don't change once filed; don't download twice
            url = find_info_table_url(session, cik, filing["accessionNumber"])
            if url is None:
                print(f"[warn] {whale['fund']} {period}: no information table found")
                used.pop()
                continue
            holdings = parse_info_table(get(session, url))
            holdings.to_csv(out_file, index=False)
            print(f"  saved {period}: {len(holdings)} rows")

    if not used:
        sys.exit("No filings were downloaded. Check the CIKs and the SEC_USER_AGENT value.")
    pd.DataFrame(used).to_csv(FILINGS_CSV, index=False)
    print(f"Wrote {FILINGS_CSV.relative_to(ROOT)} with {len(used)} filings")


if __name__ == "__main__":
    main()
