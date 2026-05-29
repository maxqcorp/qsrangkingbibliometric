"""
Compute the full bibliometric metric stack on the harmonized corpus:
performance (productivity), impact (citations), science-mapping inputs.

All tables are written to bibliometric_analysis/tables/.
Summary stats go to bibliometric_analysis/summary.json for the report.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent
TABLES = OUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

CURRENT_YEAR = 2025  # data window end; aligns with protocol
COUNTRY_RX = re.compile(r"([A-Za-z\.\- ]+?)\s*[,;]?\s*$")

# ---------- light text helpers ----------

def clean_kw(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9 \-/]", " ", s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    # light singularization to merge plurals
    if len(s) > 4 and s.endswith("ies"):
        s = s[:-3] + "y"
    elif len(s) > 3 and s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def split_kw(s: str) -> list[str]:
    if not isinstance(s, str):
        return []
    parts = re.split(r"\s*;\s*", s)
    return [clean_kw(p) for p in parts if p and p.strip()]


COUNTRY_PATTERNS = {
    "USA": ["usa", "united states", "u.s.a.", "u s a", " united states "],
    "United Kingdom": ["united kingdom", "uk ", "england", "scotland", "wales", "northern ireland"],
    "South Korea": ["south korea", "korea, republic of", "republic of korea", "korea south"],
    "North Korea": ["north korea", "dprk"],
    "China": ["peoples r china", "p r china", "china"],
    "Russia": ["russian federation", "russia"],
    "UAE": ["united arab emirates", "u arab emirates"],
    "Czech Republic": ["czech republic", "czechia"],
    "Iran": ["iran (islamic republic of)", "iran"],
    "Vietnam": ["viet nam", "vietnam"],
    "Hong Kong": ["hong kong"],
    "Taiwan": ["taiwan"],
}

STANDARD_COUNTRIES = {
    "australia","austria","belgium","brazil","canada","chile","colombia","cyprus","denmark",
    "egypt","ethiopia","finland","france","germany","ghana","greece","hungary","india",
    "indonesia","ireland","israel","italy","japan","jordan","kenya","lebanon","malaysia",
    "mexico","morocco","nepal","netherlands","new zealand","nigeria","norway","oman",
    "pakistan","philippines","poland","portugal","qatar","romania","saudi arabia","singapore",
    "slovakia","slovenia","south africa","spain","sri lanka","sweden","switzerland","thailand",
    "tunisia","turkey","ukraine","uruguay","venezuela", "bangladesh","peru","argentina",
    "kazakhstan","ecuador","bolivia","luxembourg","croatia","serbia","bulgaria","estonia",
    "latvia","lithuania","iceland","albania","macedonia","azerbaijan","armenia","georgia",
    "uzbekistan","yemen","iraq","syria","palestine","cuba","panama","costa rica","jamaica",
}


def extract_country(address: str) -> str | None:
    """Pull a country name out of a free-text address string."""
    if not isinstance(address, str) or not address.strip():
        return None
    a = address.lower()
    for canon, pats in COUNTRY_PATTERNS.items():
        for p in pats:
            if p in a:
                return canon
    # Try last token after final comma
    tail = a.split(",")[-1].strip().strip(".")
    tail = tail.split(";")[0].strip()
    if tail in STANDARD_COUNTRIES:
        return tail.title()
    return None


def extract_countries(field: str) -> list[str]:
    """Multiple addresses separated by ';'."""
    if not isinstance(field, str) or not field.strip():
        return []
    parts = re.split(r";", field)
    found = []
    for p in parts:
        c = extract_country(p)
        if c:
            found.append(c)
    return sorted(set(found))


def split_authors(s: str) -> list[str]:
    if not isinstance(s, str) or not s.strip():
        return []
    parts = re.split(r";", s)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            # Normalize "Last, F." style
            p = re.sub(r"\s+", " ", p)
            out.append(p)
    return out


def split_affils(s: str) -> list[str]:
    if not isinstance(s, str) or not s.strip():
        return []
    parts = re.split(r";", s)
    return [p.strip() for p in parts if p.strip()]


# ---------- metrics ----------

def annual_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Per-year publications, citations, mean TC, growth rate."""
    g = (
        df.groupby("year")
        .agg(
            n_pubs=("title", "size"),
            total_citations=("citations", "sum"),
            mean_citations=("citations", "mean"),
            median_citations=("citations", "median"),
        )
        .reset_index()
        .sort_values("year")
    )
    g["growth_rate_pct"] = g["n_pubs"].pct_change() * 100
    g["mean_citations"] = g["mean_citations"].round(2)
    g["median_citations"] = g["median_citations"].round(1)
    g["growth_rate_pct"] = g["growth_rate_pct"].round(2)
    return g


def cagr(series: pd.Series) -> float:
    series = series.dropna().sort_index()
    if len(series) < 2 or series.iloc[0] <= 0:
        return float("nan")
    n = len(series) - 1
    return ((series.iloc[-1] / series.iloc[0]) ** (1 / n) - 1) * 100


def doc_type_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("doc_type").agg(n=("title","size"), citations=("citations","sum")).reset_index()
    g["share_pct"] = (g["n"] / g["n"].sum() * 100).round(2)
    return g.sort_values("n", ascending=False)


def language_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df["language"].value_counts().rename_axis("language").reset_index(name="n")
    g["share_pct"] = (g["n"] / g["n"].sum() * 100).round(2)
    return g


def top_sources(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    g = (
        df[df["source_title"].str.len() > 0]
        .groupby("source_title")
        .agg(
            n_pubs=("title", "size"),
            total_citations=("citations", "sum"),
            mean_citations=("citations", "mean"),
        )
        .reset_index()
    )
    g["mean_citations"] = g["mean_citations"].round(2)
    g = g.sort_values(["n_pubs", "total_citations"], ascending=False)
    return g.head(n)


def bradford_zones(df: pd.DataFrame) -> pd.DataFrame:
    """Partition sources into 3 Bradford zones of approximately equal output."""
    src = (
        df.groupby("source_title")
        .size()
        .reset_index(name="n_pubs")
        .sort_values("n_pubs", ascending=False)
    )
    src = src[src["source_title"].str.len() > 0].reset_index(drop=True)
    total = src["n_pubs"].sum()
    cum = src["n_pubs"].cumsum()
    src["zone"] = np.where(
        cum <= total / 3, "Core (Zone 1)",
        np.where(cum <= 2 * total / 3, "Zone 2", "Zone 3"),
    )
    summary = src.groupby("zone").agg(n_sources=("source_title","nunique"), n_pubs=("n_pubs","sum"))
    summary["share_pubs_pct"] = (summary["n_pubs"] / total * 100).round(2)
    summary = summary.reindex(["Core (Zone 1)","Zone 2","Zone 3"])
    return src, summary.reset_index()


def explode_authors(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        for a in split_authors(r["authors"]):
            rows.append((a, r["citations"], r["year"]))
    return pd.DataFrame(rows, columns=["author","citations","year"])


def top_authors(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    a = explode_authors(df)
    g = a.groupby("author").agg(n_pubs=("citations","size"), total_citations=("citations","sum")).reset_index()
    g["mean_citations"] = (g["total_citations"]/g["n_pubs"]).round(2)
    return g.sort_values(["n_pubs","total_citations"], ascending=False).head(n)


def lotka(df: pd.DataFrame) -> pd.DataFrame:
    """Lotka's law: fraction of authors with k papers."""
    a = explode_authors(df)
    counts = a["author"].value_counts()
    dist = counts.value_counts().sort_index().rename_axis("n_pubs").reset_index(name="n_authors")
    total = dist["n_authors"].sum()
    dist["share_authors_pct"] = (dist["n_authors"]/total*100).round(3)
    # Expected under Lotka c/k^2 fit (c = 1/zeta(2) ≈ 0.6079)
    dist["expected_lotka_pct"] = (0.6079 / dist["n_pubs"]**2 * 100).round(3)
    return dist


def top_affiliations(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        for af in split_affils(r["affiliations"]):
            rows.append((af, r["citations"]))
    g = pd.DataFrame(rows, columns=["affiliation","citations"])
    if g.empty:
        return g
    g = g.groupby("affiliation").agg(n_pubs=("citations","size"), total_citations=("citations","sum")).reset_index()
    g["mean_citations"] = (g["total_citations"]/g["n_pubs"]).round(2)
    return g.sort_values(["n_pubs","total_citations"], ascending=False).head(n)


def top_countries(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        addr = r["addresses"] if r["addresses"] else r["affiliations"]
        for c in extract_countries(addr):
            rows.append((c, r["citations"]))
    g = pd.DataFrame(rows, columns=["country","citations"])
    if g.empty:
        return g
    g = g.groupby("country").agg(n_pubs=("citations","size"), total_citations=("citations","sum")).reset_index()
    g["mean_citations"] = (g["total_citations"]/g["n_pubs"]).round(2)
    return g.sort_values(["n_pubs","total_citations"], ascending=False).head(n)


def country_collab(df: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    """SCP (single-country) vs MCP (multi-country) for top countries."""
    rows = []
    pair_rows = []
    for _, r in df.iterrows():
        addr = r["addresses"] if r["addresses"] else r["affiliations"]
        cs = extract_countries(addr)
        if not cs:
            continue
        mode = "SCP" if len(cs) == 1 else "MCP"
        for c in cs:
            rows.append((c, mode))
        for a, b in combinations(sorted(set(cs)), 2):
            pair_rows.append((a, b))
    g = pd.DataFrame(rows, columns=["country","mode"])
    if g.empty:
        return g, pd.DataFrame()
    summary = g.groupby(["country","mode"]).size().unstack(fill_value=0).reset_index()
    summary["total"] = summary.get("SCP",0) + summary.get("MCP",0)
    summary["MCP_ratio_pct"] = (summary.get("MCP",0)/summary["total"]*100).round(2)
    summary = summary.sort_values("total", ascending=False).head(n)

    pairs = pd.DataFrame(pair_rows, columns=["country_a","country_b"])
    pair_edges = pairs.groupby(["country_a","country_b"]).size().reset_index(name="weight").sort_values("weight", ascending=False)
    return summary, pair_edges


def h_index(citations: list[int]) -> int:
    cs = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(cs, 1):
        if c >= i:
            h = i
        else:
            break
    return h


def g_index(citations: list[int]) -> int:
    cs = sorted(citations, reverse=True)
    cum, g = 0, 0
    for i, c in enumerate(cs, 1):
        cum += c
        if cum >= i*i:
            g = i
        else:
            break
    return g


def citation_metrics(df: pd.DataFrame) -> dict:
    cs = df["citations"].tolist()
    nz = [c for c in cs if c > 0]
    total = sum(cs)
    m = {
        "n_records": len(df),
        "total_citations": int(total),
        "mean_citations_per_paper": round(np.mean(cs), 2),
        "median_citations_per_paper": float(np.median(cs)),
        "max_citations": int(max(cs)),
        "cited_papers_pct": round(len(nz)/len(cs)*100, 2),
        "uncited_papers_pct": round((len(cs)-len(nz))/len(cs)*100, 2),
        "h_index": h_index(cs),
        "g_index": g_index(cs),
    }
    return m


def top_cited_papers(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    g = df.sort_values("citations", ascending=False).head(n).copy()
    g["TC_per_year"] = (g["citations"] / (CURRENT_YEAR - g["year"] + 1)).round(2)
    return g[["authors","year","title","source_title","citations","TC_per_year","doi"]]


# ---------- science mapping inputs ----------

STOPWORDS = {
    "and","of","the","in","for","with","using","based","on","a","an","via","using","using-",
    "study","analysi","analysis","approach","approache","model","method","review",
}


def keyword_freq(df: pd.DataFrame, kind: str = "author") -> pd.DataFrame:
    col = "author_keywords" if kind == "author" else "index_keywords"
    counter: Counter = Counter()
    for s in df[col]:
        for k in split_kw(s):
            if k and k not in STOPWORDS and len(k) > 2:
                counter[k] += 1
    g = pd.DataFrame(counter.most_common(), columns=["keyword","n"])
    g["share_pct"] = (g["n"] / g["n"].sum() * 100).round(3)
    return g


def keyword_cooccurrence(df: pd.DataFrame, kind: str = "author", min_count: int = 8) -> pd.DataFrame:
    col = "author_keywords" if kind == "author" else "index_keywords"
    freq = Counter()
    co: Counter = Counter()
    for s in df[col]:
        kws = [k for k in split_kw(s) if k and k not in STOPWORDS and len(k) > 2]
        kws = list(dict.fromkeys(kws))  # unique, ordered
        for k in kws:
            freq[k] += 1
        for a, b in combinations(sorted(set(kws)), 2):
            co[(a, b)] += 1
    keep = {k for k, c in freq.items() if c >= min_count}
    rows = [(a, b, w) for (a, b), w in co.items() if a in keep and b in keep and w >= 2]
    edges = pd.DataFrame(rows, columns=["kw_a","kw_b","weight"]).sort_values("weight", ascending=False)
    return edges


def keyword_trend(df: pd.DataFrame, top_terms: list[str]) -> pd.DataFrame:
    """Yearly counts for each top author keyword (for thematic-evolution plot)."""
    yrs = sorted(df["year"].dropna().unique())
    rows = []
    for y in yrs:
        sub = df[df["year"] == y]
        counter = Counter()
        for s in sub["author_keywords"]:
            for k in split_kw(s):
                if k in top_terms:
                    counter[k] += 1
        for term, n in counter.items():
            rows.append((y, term, n))
    return pd.DataFrame(rows, columns=["year","keyword","n"])


def funding_table(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    rows = []
    for s in df["funding_orgs"]:
        if not isinstance(s, str): continue
        for f in re.split(r";", s):
            f = f.strip()
            if f:
                rows.append(f)
    g = pd.Series(rows).value_counts().rename_axis("funder").reset_index(name="n").head(n)
    return g


def open_access_table(df: pd.DataFrame) -> pd.DataFrame:
    def norm_oa(s):
        if not isinstance(s, str) or not s.strip():
            return "No OA / Not reported"
        s = s.lower()
        if "gold" in s: return "Gold OA"
        if "green" in s: return "Green OA"
        if "hybrid" in s: return "Hybrid OA"
        if "bronze" in s: return "Bronze OA"
        if "all open" in s or "all_open" in s: return "All Open Access"
        return s.title()[:40]
    df = df.copy()
    df["OA_norm"] = df["open_access"].map(norm_oa)
    g = df["OA_norm"].value_counts().rename_axis("category").reset_index(name="n")
    g["share_pct"] = (g["n"]/g["n"].sum()*100).round(2)
    return g


def collaboration_index(df: pd.DataFrame) -> dict:
    counts = df["authors"].apply(lambda s: len(split_authors(s)))
    single_author = (counts == 1).sum()
    multi_author = (counts > 1).sum()
    return {
        "mean_authors_per_paper": round(counts.mean(), 2),
        "median_authors_per_paper": float(counts.median()),
        "max_authors_per_paper": int(counts.max()),
        "single_authored_papers": int(single_author),
        "single_authored_share_pct": round(single_author/len(df)*100, 2),
        "co_authored_papers": int(multi_author),
        "collaboration_index": round(counts[counts > 1].mean(), 2) if multi_author else 0,
    }


# ---------- run ----------

def main():
    df = pd.read_parquet(OUT / "harmonized.parquet")
    print(f"Loaded {len(df)} harmonized records")

    summary: dict = {}

    # ----- Performance -----
    ann = annual_metrics(df)
    ann.to_csv(TABLES / "02_annual_metrics.csv", index=False)
    summary["annual"] = {
        "year_range": [int(df["year"].min()), int(df["year"].max())],
        "total_records": int(len(df)),
        "cagr_pubs_pct": round(cagr(ann.set_index("year")["n_pubs"]), 2),
        "peak_year": int(ann.loc[ann["n_pubs"].idxmax(), "year"]),
        "peak_year_pubs": int(ann["n_pubs"].max()),
    }

    dt = doc_type_table(df); dt.to_csv(TABLES / "03_doc_types.csv", index=False)
    lt = language_table(df); lt.to_csv(TABLES / "04_languages.csv", index=False)
    ts = top_sources(df, 30); ts.to_csv(TABLES / "05_top_sources.csv", index=False)
    bs, bsum = bradford_zones(df)
    bs.to_csv(TABLES / "06_bradford_sources.csv", index=False)
    bsum.to_csv(TABLES / "06_bradford_summary.csv", index=False)
    summary["bradford_core_n_sources"] = int(bsum.loc[bsum["zone"]=="Core (Zone 1)","n_sources"].iloc[0])

    ta = top_authors(df, 30); ta.to_csv(TABLES / "07_top_authors.csv", index=False)
    la = lotka(df); la.to_csv(TABLES / "07_lotka.csv", index=False)
    summary["unique_authors"] = int(explode_authors(df)["author"].nunique())

    tf = top_affiliations(df, 30); tf.to_csv(TABLES / "08_top_affiliations.csv", index=False)
    tc = top_countries(df, 30); tc.to_csv(TABLES / "09_top_countries.csv", index=False)
    cc, edges = country_collab(df, 30)
    cc.to_csv(TABLES / "09_country_collab.csv", index=False)
    edges.to_csv(TABLES / "09_country_collab_edges.csv", index=False)

    funders = funding_table(df, 30); funders.to_csv(TABLES / "10_top_funders.csv", index=False)
    oa = open_access_table(df); oa.to_csv(TABLES / "11_open_access.csv", index=False)

    # ----- Impact / Citations -----
    summary["impact"] = citation_metrics(df)
    cited = top_cited_papers(df, 25)
    cited.to_csv(TABLES / "12_top_cited.csv", index=False)

    # ----- Collaboration -----
    summary["collaboration"] = collaboration_index(df)

    # ----- Science mapping -----
    kw_a = keyword_freq(df, "author"); kw_a.head(60).to_csv(TABLES / "13_top_author_keywords.csv", index=False)
    kw_i = keyword_freq(df, "index"); kw_i.head(60).to_csv(TABLES / "13_top_index_keywords.csv", index=False)

    co = keyword_cooccurrence(df, "author", min_count=10)
    co.to_csv(TABLES / "14_keyword_cooccurrence.csv", index=False)

    top_kw_list = kw_a.head(15)["keyword"].tolist()
    kt = keyword_trend(df, top_kw_list); kt.to_csv(TABLES / "15_keyword_trend.csv", index=False)

    summary["sources_unique"] = int(df["source_title"].nunique())
    summary["affils_unique"] = int(
        pd.Series([a for s in df["affiliations"] for a in split_affils(s)]).nunique()
    )
    summary["keywords_unique_author"] = int(len(kw_a))
    summary["keywords_unique_index"] = int(len(kw_i))

    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("Summary keys:", list(summary.keys()))
    print(f"\nWrote {len(list(TABLES.glob('*.csv')))} tables to {TABLES}")


if __name__ == "__main__":
    main()
