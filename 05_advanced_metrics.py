"""
Advanced bibliometric metrics that extend the base analysis.

Outputs (to bibliometric_analysis/tables/):
  20_rci_by_year.csv              Relative Citation Impact per year
  21_source_bubble.csv            Source metrics for bubble chart (pubs, TC, h)
  22_subject_areas.csv            WoS research-area distribution
  23_rising_sources.csv           Sources with strongest recent growth
  24_country_counts.csv           Country publication counts (for world map)
  25_rising_countries.csv         Countries with strongest recent growth
  26_author_collab_edges.csv      Author co-authorship edges
  26_author_collab_nodes.csv      Author co-authorship node stats
  27_thematic_map.csv             Keyword clusters with centrality/density
  28_lifecycle_fit.csv            Logistic life-cycle fit of cumulative output

Reuses the harmonized corpus from 01_harmonize.py.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent
TABLES = OUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

CURRENT_YEAR = 2025

# ----------------- shared helpers (mirrors 02_metrics) -----------------

STOPWORDS = {
    "and", "of", "the", "in", "for", "with", "using", "based", "on", "a", "an",
    "via", "study", "analysis", "approach", "model", "method", "review",
}


def clean_kw(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9 \-/]", " ", s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    if len(s) > 4 and s.endswith("ies"):
        s = s[:-3] + "y"
    elif len(s) > 3 and s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def split_kw(s):
    if not isinstance(s, str):
        return []
    return [clean_kw(p) for p in re.split(r"\s*;\s*", s) if p and p.strip()]


def split_authors(s):
    if not isinstance(s, str) or not s.strip():
        return []
    return [re.sub(r"\s+", " ", p.strip()) for p in re.split(r";", s) if p.strip()]


COUNTRY_PATTERNS = {
    "USA": ["usa", "united states", "u.s.a.", " united states "],
    "United Kingdom": ["united kingdom", "uk ", "england", "scotland", "wales"],
    "South Korea": ["south korea", "korea, republic", "republic of korea"],
    "China": ["peoples r china", "p r china", "china"],
    "Russia": ["russian federation", "russia"],
    "UAE": ["united arab emirates", "u arab emirates"],
    "Iran": ["iran"],
    "Vietnam": ["viet nam", "vietnam"],
    "Hong Kong": ["hong kong"],
    "Taiwan": ["taiwan"],
}
STANDARD_COUNTRIES = {
    "australia", "austria", "belgium", "brazil", "canada", "chile", "colombia", "denmark",
    "egypt", "finland", "france", "germany", "greece", "hungary", "india", "indonesia",
    "ireland", "israel", "italy", "japan", "jordan", "kenya", "malaysia", "mexico", "morocco",
    "nepal", "netherlands", "new zealand", "nigeria", "norway", "oman", "pakistan",
    "philippines", "poland", "portugal", "qatar", "romania", "saudi arabia", "singapore",
    "slovakia", "slovenia", "south africa", "spain", "sri lanka", "sweden", "switzerland",
    "thailand", "tunisia", "turkey", "ukraine", "bangladesh", "peru", "argentina",
    "kazakhstan", "ecuador", "luxembourg", "croatia", "serbia", "bulgaria", "estonia",
    "iraq", "iceland",
}
COUNTRY_TO_ISO3 = {
    "USA": "USA", "United Kingdom": "GBR", "South Korea": "KOR", "China": "CHN",
    "Russia": "RUS", "UAE": "ARE", "Iran": "IRN", "Vietnam": "VNM", "Hong Kong": "HKG",
    "Taiwan": "TWN", "Australia": "AUS", "Austria": "AUT", "Belgium": "BEL", "Brazil": "BRA",
    "Canada": "CAN", "Chile": "CHL", "Colombia": "COL", "Denmark": "DNK", "Egypt": "EGY",
    "Finland": "FIN", "France": "FRA", "Germany": "DEU", "Greece": "GRC", "Hungary": "HUN",
    "India": "IND", "Indonesia": "IDN", "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA",
    "Japan": "JPN", "Jordan": "JOR", "Kenya": "KEN", "Malaysia": "MYS", "Mexico": "MEX",
    "Morocco": "MAR", "Nepal": "NPL", "Netherlands": "NLD", "New Zealand": "NZL",
    "Nigeria": "NGA", "Norway": "NOR", "Oman": "OMN", "Pakistan": "PAK",
    "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT", "Qatar": "QAT",
    "Romania": "ROU", "Saudi Arabia": "SAU", "Singapore": "SGP", "Slovakia": "SVK",
    "Slovenia": "SVN", "South Africa": "ZAF", "Spain": "ESP", "Sri Lanka": "LKA",
    "Sweden": "SWE", "Switzerland": "CHE", "Thailand": "THA", "Tunisia": "TUN",
    "Turkey": "TUR", "Ukraine": "UKR", "Bangladesh": "BGD", "Peru": "PER",
    "Argentina": "ARG", "Kazakhstan": "KAZ", "Ecuador": "ECU", "Luxembourg": "LUX",
    "Croatia": "HRV", "Serbia": "SRB", "Bulgaria": "BGR", "Estonia": "EST", "Iraq": "IRQ",
    "Iceland": "ISL",
}


def extract_country(address: str):
    if not isinstance(address, str) or not address.strip():
        return None
    a = address.lower()
    for canon, pats in COUNTRY_PATTERNS.items():
        for p in pats:
            if p in a:
                return canon
    tail = a.split(",")[-1].strip().strip(".").split(";")[0].strip()
    if tail in STANDARD_COUNTRIES:
        return tail.title()
    return None


def extract_countries(field):
    if not isinstance(field, str) or not field.strip():
        return []
    found = []
    for p in re.split(r";", field):
        c = extract_country(p)
        if c:
            found.append(c)
    return sorted(set(found))


def h_index(cits):
    cs = sorted(cits, reverse=True)
    h = 0
    for i, c in enumerate(cs, 1):
        if c >= i:
            h = i
        else:
            break
    return h


# ----------------- metric computations -----------------

def rci_by_country(df, min_pubs=20, n=20):
    """
    Relative Citation Impact (MNCS-style). Each paper's citations are divided
    by the mean citations of all corpus papers published in the same year, which
    controls for citation ageing. The corpus-wide mean of this normalised score
    is 1.0 by construction, so a country value above 1.0 means its papers attract
    more citations than the corpus average of the same age.
    """
    year_mean = df.groupby("year")["citations"].transform("mean")
    nci = np.where(year_mean > 0, df["citations"] / year_mean, 0.0)
    work = df.assign(nci=nci)

    rows = []
    for _, r in work.iterrows():
        addr = r["addresses"] if r["addresses"] else r["affiliations"]
        for c in extract_countries(addr):
            rows.append((c, r["nci"], 1))
    long = pd.DataFrame(rows, columns=["country", "nci", "one"])
    g = long.groupby("country").agg(
        n_pubs=("one", "sum"),
        rci=("nci", "mean"),
    ).reset_index()
    g = g[g["n_pubs"] >= min_pubs].copy()
    g["rci"] = g["rci"].round(3)
    g["iso3"] = g["country"].map(COUNTRY_TO_ISO3)
    return g.sort_values("rci", ascending=False).head(n)


def source_bubble(df, n=25):
    rows = []
    for src, grp in df.groupby("source_title"):
        if not src:
            continue
        rows.append({
            "source": src,
            "n_pubs": len(grp),
            "total_citations": int(grp["citations"].sum()),
            "mean_citations": round(grp["citations"].mean(), 2),
            "h_index": h_index(grp["citations"].tolist()),
        })
    g = pd.DataFrame(rows).sort_values(["n_pubs", "total_citations"], ascending=False)
    return g.head(n)


def subject_areas(df, n=20):
    counter = Counter()
    for s in df["research_areas"]:
        if isinstance(s, str) and s.strip():
            for area in re.split(r";", s):
                area = area.strip()
                if area:
                    counter[area] += 1
    g = pd.DataFrame(counter.most_common(n), columns=["research_area", "n_pubs"])
    if len(g):
        total = sum(counter.values())
        g["share_pct"] = (g["n_pubs"] / total * 100).round(2)
    return g


def rising_sources(df, n=15, recent_lo=2023):
    """Sources with the largest share of output in recent years."""
    rows = []
    for src, grp in df.groupby("source_title"):
        if not src or len(grp) < 8:
            continue
        recent = (grp["year"] >= recent_lo).sum()
        rows.append({
            "source": src,
            "n_pubs": len(grp),
            "recent_pubs": int(recent),
            "recent_share_pct": round(recent / len(grp) * 100, 1),
        })
    g = pd.DataFrame(rows)
    if g.empty:
        return g
    g = g.sort_values(["recent_pubs", "recent_share_pct"], ascending=False)
    return g.head(n)


def country_counts(df):
    rows = []
    for _, r in df.iterrows():
        addr = r["addresses"] if r["addresses"] else r["affiliations"]
        for c in extract_countries(addr):
            rows.append((c, r["citations"], r["year"]))
    g = pd.DataFrame(rows, columns=["country", "citations", "year"])
    agg = g.groupby("country").agg(
        n_pubs=("citations", "size"),
        total_citations=("citations", "sum"),
    ).reset_index()
    agg["iso3"] = agg["country"].map(COUNTRY_TO_ISO3)
    agg["mean_citations"] = (agg["total_citations"] / agg["n_pubs"]).round(2)
    return agg.sort_values("n_pubs", ascending=False), g


def rising_countries(country_long, n=15, recent_lo=2023):
    rows = []
    for c, grp in country_long.groupby("country"):
        if len(grp) < 10:
            continue
        recent = (grp["year"] >= recent_lo).sum()
        rows.append({
            "country": c,
            "iso3": COUNTRY_TO_ISO3.get(c),
            "n_pubs": len(grp),
            "recent_pubs": int(recent),
            "recent_share_pct": round(recent / len(grp) * 100, 1),
        })
    g = pd.DataFrame(rows)
    if g.empty:
        return g
    return g.sort_values(["recent_pubs", "recent_share_pct"], ascending=False).head(n)


def author_collab(df, min_pubs=5, max_nodes=60):
    """Co-authorship network among the most productive authors."""
    pub_count = Counter()
    cit_sum = Counter()
    edges = Counter()
    for _, r in df.iterrows():
        authors = split_authors(r["authors"])
        for a in authors:
            pub_count[a] += 1
            cit_sum[a] += int(r["citations"])
        for a, b in combinations(sorted(set(authors)), 2):
            edges[(a, b)] += 1
    keep = {a for a, c in pub_count.items() if c >= min_pubs}
    if len(keep) > max_nodes:
        keep = set([a for a, _ in sorted(pub_count.items(), key=lambda x: -x[1])[:max_nodes]])
    nodes = pd.DataFrame([
        {"author": a, "n_pubs": pub_count[a], "total_citations": cit_sum[a]}
        for a in keep
    ]).sort_values("n_pubs", ascending=False)
    edge_rows = [(a, b, w) for (a, b), w in edges.items() if a in keep and b in keep and w >= 1]
    edges_df = pd.DataFrame(edge_rows, columns=["author_a", "author_b", "weight"]).sort_values("weight", ascending=False)
    return nodes, edges_df


def thematic_map(df, min_count=12):
    """
    Strategic diagram (Cobo et al. 2011): for each keyword cluster compute
    centrality (external links) and density (internal links).
    Cluster via co-occurrence + greedy modularity.
    """
    import networkx as nx
    freq = Counter()
    co = Counter()
    for s in df["author_keywords"]:
        kws = [k for k in split_kw(s) if k and k not in STOPWORDS and len(k) > 2]
        kws = list(dict.fromkeys(kws))
        for k in kws:
            freq[k] += 1
        for a, b in combinations(sorted(set(kws)), 2):
            co[(a, b)] += 1
    keep = {k for k, c in freq.items() if c >= min_count}
    G = nx.Graph()
    for (a, b), w in co.items():
        if a in keep and b in keep and w >= 2:
            G.add_edge(a, b, weight=w)
    if len(G) == 0:
        return pd.DataFrame()
    comms = list(nx.algorithms.community.greedy_modularity_communities(G, weight="weight"))
    rows = []
    for i, com in enumerate(comms):
        com = set(com)
        if len(com) < 2:
            continue
        internal = 0.0
        external = 0.0
        for u, v, d in G.edges(data=True):
            w = d["weight"]
            if u in com and v in com:
                internal += w
            elif u in com or v in com:
                external += w
        density = internal / len(com)
        centrality = external / len(com)
        label = ", ".join(sorted(com, key=lambda x: -freq.get(x, 0))[:3])
        rows.append({
            "cluster": i + 1,
            "label": label,
            "size": len(com),
            "sum_freq": int(sum(freq.get(k, 0) for k in com)),
            "centrality": round(centrality, 2),
            "density": round(density, 2),
        })
    return pd.DataFrame(rows).sort_values("sum_freq", ascending=False)


def logistic(x, L, k, x0):
    return L / (1 + np.exp(-k * (x - x0)))


def lifecycle_fit(df):
    g = df.groupby("year").size().reset_index(name="n_pubs").sort_values("year")
    g["cumulative"] = g["n_pubs"].cumsum()
    x = g["year"].to_numpy(dtype=float)
    y = g["cumulative"].to_numpy(dtype=float)
    x0 = x - x.min()
    try:
        popt, _ = curve_fit(logistic, x0, y,
                            p0=[y.max() * 1.5, 0.5, x0.mean()], maxfev=10000)
        g["logistic_fit"] = logistic(x0, *popt).round(1)
        L, k, mid = popt
        g.attrs["L"] = float(L)
        g.attrs["k"] = float(k)
        g.attrs["midpoint_year"] = float(x.min() + mid)
    except Exception as e:
        print("  lifecycle fit failed:", e)
        g["logistic_fit"] = np.nan
    return g


def main():
    df = pd.read_parquet(OUT / "harmonized.parquet")
    print(f"Loaded {len(df)} records")

    rci = rci_by_country(df); rci.to_csv(TABLES / "20_rci_country.csv", index=False)
    print(f"  RCI by country ({len(rci)} countries)")
    sb = source_bubble(df, 25); sb.to_csv(TABLES / "21_source_bubble.csv", index=False)
    print("  source bubble")
    sa = subject_areas(df, 20); sa.to_csv(TABLES / "22_subject_areas.csv", index=False)
    print(f"  subject areas ({len(sa)})")
    rs = rising_sources(df, 15); rs.to_csv(TABLES / "23_rising_sources.csv", index=False)
    print("  rising sources")

    cc, cc_long = country_counts(df)
    cc.to_csv(TABLES / "24_country_counts.csv", index=False)
    print(f"  country counts ({len(cc)} countries)")
    rc = rising_countries(cc_long, 15); rc.to_csv(TABLES / "25_rising_countries.csv", index=False)
    print("  rising countries")

    nodes, edges = author_collab(df, min_pubs=5)
    nodes.to_csv(TABLES / "26_author_collab_nodes.csv", index=False)
    edges.to_csv(TABLES / "26_author_collab_edges.csv", index=False)
    print(f"  author collaboration ({len(nodes)} nodes, {len(edges)} edges)")

    tm = thematic_map(df); tm.to_csv(TABLES / "27_thematic_map.csv", index=False)
    print(f"  thematic map ({len(tm)} clusters)")

    lc = lifecycle_fit(df); lc.to_csv(TABLES / "28_lifecycle_fit.csv", index=False)
    print(f"  lifecycle fit (midpoint ~ {lc.attrs.get('midpoint_year', float('nan')):.0f})")

    print("Done.")


if __name__ == "__main__":
    main()
