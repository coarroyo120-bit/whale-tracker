"""Build the static website (site/index.html) from the downloaded 13F data.

Run after fetch_13f.py:
    python src/build_site.py

The page is bilingual: every label has an English and a Spanish version, and a
button switches between them.
"""

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare_holdings  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FILINGS_CSV = ROOT / "data" / "filings.csv"
SITE_DIR = ROOT / "site"

ACTION_LABELS = {
    "NEW": ("New", "Nueva"),
    "ADDED": ("Added", "Aumentó"),
    "REDUCED": ("Reduced", "Redujo"),
    "SOLD OUT": ("Sold out", "Vendió todo"),
    "UNCHANGED": ("Unchanged", "Sin cambio"),
}


def t(en, es):
    """A label in both languages. The page's script shows one or the other."""
    return f'<span lang="en">{html.escape(en)}</span><span lang="es">{html.escape(es)}</span>'


def money(x):
    if pd.isna(x):
        return "–"
    sign = "-" if x < 0 else ""
    x = abs(x)
    for limit, suffix in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if x >= limit:
            return f"{sign}${x / limit:,.1f}{suffix}"
    return f"{sign}${x:,.0f}"


def load_holdings(path):
    df = pd.read_csv(ROOT / path, dtype={"cusip": str, "put_call": str})
    df["put_call"] = df["put_call"].fillna("")
    return df


def top_holdings(df, n=10):
    stock = df[df["put_call"] == ""]
    grouped = (stock.groupby("cusip", as_index=False)
               .agg(name_of_issuer=("name_of_issuer", "first"), value_usd=("value_usd", "sum")))
    total = df["value_usd"].sum()
    grouped["weight"] = grouped["value_usd"] / total * 100
    return grouped.sort_values("value_usd", ascending=False).head(n)


def moves_table(moves, n=10):
    moves = moves[moves["action"] != "UNCHANGED"].copy()
    if moves.empty:
        return f'<p class="note">{t("No changes this quarter.", "Sin cambios este trimestre.")}</p>'
    # Rough dollar size of each move: shares traded x current (or last) price per share.
    price = (moves["value_curr"] / moves["shares_curr"]).where(
        moves["shares_curr"] > 0, moves["value_prev"] / moves["shares_prev"])
    moves["est_dollars"] = moves["share_change"] * price
    moves = moves.reindex(moves["est_dollars"].abs().sort_values(ascending=False).index).head(n)

    rows = []
    for _, m in moves.iterrows():
        en, es = ACTION_LABELS.get(m["action"], (m["action"], m["action"]))
        kind = f' <span class="opt">{html.escape(m["put_call"])}</span>' if m["put_call"] else ""
        pct = "–" if pd.isna(m["pct_change"]) else f'{m["pct_change"]:+.0f}%'
        rows.append(
            f'<tr><td>{html.escape(str(m["name_of_issuer"]))}{kind}</td>'
            f'<td><span class="tag tag-{m["action"].replace(" ", "-").lower()}">{t(en, es)}</span></td>'
            f'<td class="num sm-hide">{int(m["share_change"]):+,}</td>'
            f'<td class="num">{pct}</td>'
            f'<td class="num">{money(m["est_dollars"])}</td></tr>'
        )
    return (
        '<div class="scroll"><table><thead><tr>'
        f'<th>{t("Company", "Empresa")}</th><th>{t("Move", "Movimiento")}</th>'
        f'<th class="num sm-hide">{t("Shares", "Acciones")}</th><th class="num">%</th>'
        f'<th class="num">{t("Approx. $", "$ aprox.")}</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
    )


def holdings_table(top):
    rows = "".join(
        f'<tr><td>{html.escape(str(h["name_of_issuer"]))}</td>'
        f'<td class="num">{money(h["value_usd"])}</td>'
        f'<td class="num">{h["weight"]:.1f}%</td></tr>'
        for _, h in top.iterrows()
    )
    return (
        '<table><thead><tr>'
        f'<th>{t("Company", "Empresa")}</th><th class="num">{t("Value", "Valor")}</th>'
        f'<th class="num">{t("% of portfolio", "% del portafolio")}</th>'
        '</tr></thead><tbody>' + rows + "</tbody></table>"
    )


def fund_section(fund_rows):
    fund_rows = fund_rows.sort_values("period")
    prev_info, curr_info = fund_rows.iloc[0], fund_rows.iloc[1]
    prev, curr = load_holdings(prev_info["raw_file"]), load_holdings(curr_info["raw_file"])

    try:
        moves_html = moves_table(compare_holdings(prev, curr))
    except NotImplementedError:
        moves_html = f'<p class="note">{t("Moves coming soon.", "Movimientos muy pronto.")}</p>'

    warning = ""
    if curr_info["amendment_count"] > 0:
        warning = (f'<p class="warn">{t("This fund amended its filing. Figures use the original.", "Este fondo enmendó su reporte. Las cifras usan el original.")}</p>')

    return f"""
<section class="fund">
  <header>
    <h2>{html.escape(curr_info["fund"])}</h2>
    <p class="meta">{html.escape(curr_info["manager"])} · {t("Quarter ending", "Trimestre al")} {curr_info["period"]} · {t("filed", "presentado")} {curr_info["filing_date"]}</p>
    <p class="stats"><strong>{money(curr["value_usd"].sum())}</strong> {t("reported holdings", "en posiciones reportadas")} · <strong>{len(curr)}</strong> {t("lines in filing", "líneas en el reporte")}</p>
  </header>
  {warning}
  <h3>{t("Biggest moves vs. prior quarter", "Mayores movimientos vs. trimestre anterior")} <span class="since">({prev_info["period"]} → {curr_info["period"]})</span></h3>
  {moves_html}
  <details><summary>{t("Top 10 holdings", "10 principales posiciones")}</summary>{holdings_table(top_holdings(curr))}</details>
</section>"""


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Whale Tracker</title>
<meta name="description" content="What well-known investors bought and sold last quarter, from public SEC 13F filings.">
<style>
:root {{ --ink:#14202b; --muted:#5b6b78; --line:#d9e1e7; --bg:#f6f8f9; --card:#fff; --sea:#0f5c7a;
  --up:#1d7a4c; --down:#b23a3a; --warn-bg:#fff6e0; --warn:#7a5a00; }}
@media (prefers-color-scheme: dark) {{ :root {{ --ink:#e6edf2; --muted:#9aaab6; --line:#2b3a46; --bg:#0d1820;
  --card:#13222d; --sea:#5fb3d4; --up:#5cc58d; --down:#ef8080; --warn-bg:#3a2f12; --warn:#f0cf77; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:880px; margin:0 auto; padding:32px 16px 64px; }}
.top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }}
h1 {{ margin:0; font-size:2rem; letter-spacing:-0.02em; }}
h1 span {{ color:var(--sea); }}
.lede {{ color:var(--muted); margin:6px 0 0; max-width:60ch; }}
button {{ font:inherit; border:1px solid var(--line); background:var(--card); color:var(--ink); padding:6px 12px; border-radius:6px; cursor:pointer; white-space:nowrap; }}
.updated {{ color:var(--muted); font-size:.85rem; margin:16px 0 24px; }}
.fund {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:20px; margin-bottom:20px; }}
.fund h2 {{ margin:0; font-size:1.3rem; }}
.meta, .since, .note {{ color:var(--muted); font-size:.9rem; }}
.meta {{ margin:2px 0 8px; }}
.stats {{ margin:0 0 12px; }}
h3 {{ font-size:1rem; margin:16px 0 8px; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
th, td {{ text-align:left; padding:6px 4px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:600; font-size:.8rem; text-transform:uppercase; letter-spacing:.03em; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tag {{ font-size:.78rem; font-weight:600; padding:2px 8px; border-radius:99px; border:1px solid currentColor; white-space:nowrap; }}
.tag-new, .tag-added {{ color:var(--up); }}
.tag-reduced, .tag-sold-out {{ color:var(--down); }}
.opt {{ font-size:.75rem; color:var(--muted); border:1px solid var(--line); border-radius:4px; padding:0 4px; }}
.warn {{ background:var(--warn-bg); color:var(--warn); padding:8px 12px; border-radius:6px; font-size:.9rem; }}
details {{ margin-top:12px; }}
summary {{ cursor:pointer; color:var(--sea); font-weight:600; }}
footer {{ color:var(--muted); font-size:.85rem; border-top:1px solid var(--line); padding-top:16px; margin-top:32px; }}
footer a {{ color:var(--sea); }}
body.es [lang="en"], body:not(.es) [lang="es"] {{ display:none; }}
.scroll {{ overflow-x:auto; }}
@media (max-width:560px) {{ .top {{ flex-direction:column; }} .sm-hide {{ display:none; }}
  .fund {{ padding:16px 12px; }} table {{ font-size:.85rem; }} th, td {{ padding:6px 3px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1>Whale <span>Tracker</span></h1>
      <p class="lede">{lede}</p>
    </div>
    <button id="lang" type="button" aria-label="Cambiar idioma / Switch language">Español</button>
  </div>
  <p class="updated">{updated_label} {updated}</p>
  {sections}
  <footer>
    <p>{disclaimer}</p>
    <p>{source} <a href="https://www.sec.gov/edgar/search/">SEC EDGAR</a> · <a href="https://github.com/coarroyo120-bit/whale-tracker">GitHub</a></p>
  </footer>
</div>
<script>
(function () {{
  var btn = document.getElementById("lang");
  function set(lang) {{
    document.body.classList.toggle("es", lang === "es");
    document.documentElement.lang = lang;
    btn.textContent = lang === "es" ? "English" : "Español";
  }}
  var saved = null;
  try {{ saved = localStorage.getItem("lang"); }} catch (e) {{}}
  set(saved || ((navigator.language || "").slice(0, 2) === "es" ? "es" : "en"));
  btn.addEventListener("click", function () {{
    var next = document.body.classList.contains("es") ? "en" : "es";
    set(next);
    try {{ localStorage.setItem("lang", next); }} catch (e) {{}}
  }});
}})();
</script>
</body>
</html>
"""


def main():
    filings = pd.read_csv(FILINGS_CSV)
    sections = []
    for fund, rows in filings.groupby("fund", sort=False):
        if len(rows) < 2:
            continue
        sections.append(fund_section(rows))

    page = PAGE.format(
        lede=t("What well-known investors bought and sold last quarter, from their public SEC 13F filings.",
               "Lo que compraron y vendieron inversionistas conocidos el último trimestre, según sus reportes 13F públicos ante la SEC."),
        updated_label=t("Data checked:", "Datos revisados:"),
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        sections="\n".join(sections),
        disclaimer=t("For education only. Not investment advice. 13F filings show long U.S. positions only and can be up to 45 days old when filed.",
                     "Solo con fines educativos. No es asesoría de inversión. Los reportes 13F muestran solo posiciones largas en EE. UU. y pueden tener hasta 45 días de antigüedad."),
        source=t("Source:", "Fuente:"),
    )
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote site/index.html with {len(sections)} funds")


if __name__ == "__main__":
    main()
