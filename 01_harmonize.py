"""
Harmonize Web of Science (WoS) and Scopus exports into a single
bibliometric dataframe with provenance flags and unified field names.

Outputs
-------
bibliometric_analysis/harmonized.parquet
bibliometric_analysis/harmonized.csv  (lightweight subset)
bibliometric_analysis/tables/01_source_overlap.csv
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent                               # parent of the workspace
TABLES = OUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)


def find_data_file(filename: str) -> Path:
    """Locate a raw data file regardless of where the workspace has been moved.
    Searches the workspace itself, its parent, a sibling 'SLR Predictive and
    Disaster' folder, and any other sibling directory."""
    candidates = [
        OUT / filename,                                   # self-contained workspace
        ROOT / filename,                                  # workspace nested in the data folder
        ROOT / "SLR Predictive and Disaster" / filename,  # data in a sibling project folder
    ]
    try:
        for sib in sorted(ROOT.iterdir()):
            if sib.is_dir() and sib != OUT:
                candidates.append(sib / filename)
    except OSError:
        pass
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Could not find '{filename}'. Searched: "
        + "; ".join(str(c) for c in candidates[:4]) + " ..."
    )


WOS_PATH = find_data_file("wos list of article.xlsx")
SCOPUS_PATH = find_data_file("scopus list of article.csv")

YEAR_LO, YEAR_HI = 2015, 2025  # protocol window


# ---------- helpers ----------

def norm_title(t: str) -> str:
    if not isinstance(t, str):
        return ""
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9 ]+", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def norm_doi(d: str) -> str:
    if not isinstance(d, str):
        return ""
    d = d.strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d


def split_list(s, sep=";"):
    if not isinstance(s, str) or not s.strip():
        return []
    return [x.strip() for x in s.split(sep) if x.strip()]


# ---------- WoS ----------

def load_wos() -> pd.DataFrame:
    df = pd.read_excel(WOS_PATH)
    out = pd.DataFrame({
        "source_db": "WoS",
        "authors": df["Authors"].fillna(""),
        "authors_full": df["Author Full Names"].fillna(""),
        "title": df["Article Title"].fillna(""),
        "year": pd.to_numeric(df["Publication Year"], errors="coerce"),
        "source_title": df["Source Title"].fillna(""),
        "doc_type": df["Document Type"].fillna("Unknown"),
        "language": df["Language"].fillna("Unknown"),
        "author_keywords": df["Author Keywords"].fillna(""),
        "index_keywords": df["Keywords Plus"].fillna(""),
        "abstract": df["Abstract"].fillna(""),
        "affiliations": df["Affiliations"].fillna(""),
        "addresses": df["Addresses"].fillna(""),
        "funding_orgs": df["Funding Orgs"].fillna(""),
        "publisher": df["Publisher"].fillna(""),
        "issn": df["ISSN"].fillna(""),
        "doi": df["DOI"].fillna(""),
        "citations": pd.to_numeric(df["Times Cited, All Databases"], errors="coerce").fillna(0).astype(int),
        "open_access": df["Open Access Designations"].fillna(""),
        "research_areas": df["Research Areas"].fillna(""),
        "wos_categories": df["WoS Categories"].fillna(""),
    })
    return out


# ---------- Scopus ----------

def load_scopus() -> pd.DataFrame:
    df = pd.read_csv(SCOPUS_PATH, low_memory=False)
    out = pd.DataFrame({
        "source_db": "Scopus",
        "authors": df["Authors"].fillna(""),
        "authors_full": df["Author full names"].fillna(""),
        "title": df["Title"].fillna(""),
        "year": pd.to_numeric(df["Year"], errors="coerce"),
        "source_title": df["Source title"].fillna(""),
        "doc_type": df["Document Type"].fillna("Unknown"),
        "language": df["Language of Original Document"].fillna("Unknown"),
        "author_keywords": df["Author Keywords"].fillna(""),
        "index_keywords": df["Index Keywords"].fillna(""),
        "abstract": df["Abstract"].fillna(""),
        "affiliations": df["Affiliations"].fillna(""),
        "addresses": df["Authors with affiliations"].fillna(""),
        "funding_orgs": df["Funding Details"].fillna(""),
        "publisher": df["Publisher"].fillna(""),
        "issn": df["ISSN"].fillna(""),
        "doi": df["DOI"].fillna(""),
        "citations": pd.to_numeric(df["Cited by"], errors="coerce").fillna(0).astype(int),
        "open_access": df["Open Access"].fillna(""),
        "research_areas": "",
        "wos_categories": "",
    })
    return out


# ---------- merge + dedup ----------

def harmonize() -> pd.DataFrame:
    wos = load_wos()
    sc = load_scopus()
    print(f"  WoS rows: {len(wos)}  |  Scopus rows: {len(sc)}")

    combined = pd.concat([wos, sc], ignore_index=True)
    combined["title_norm"] = combined["title"].map(norm_title)
    combined["doi_norm"] = combined["doi"].map(norm_doi)
    combined = combined[combined["year"].between(YEAR_LO, YEAR_HI, inclusive="both")].copy()
    print(f"  After year filter {YEAR_LO}-{YEAR_HI}: {len(combined)}")

    # 1) Match by DOI when present
    has_doi = combined["doi_norm"].str.len() > 5
    doi_grp = combined.loc[has_doi].groupby("doi_norm")
    # 2) Then by normalized title for entries without DOI
    no_doi = combined.loc[~has_doi].copy()
    no_doi["title_norm"] = no_doi["title_norm"].replace("", np.nan)
    no_doi = no_doi.dropna(subset=["title_norm"])

    # Build a dedup key per row
    combined["dedup_key"] = np.where(
        has_doi, "doi:" + combined["doi_norm"],
        "title:" + combined["title_norm"],
    )

    # Provenance tracking
    presence = (
        combined.groupby("dedup_key")["source_db"]
        .agg(lambda s: ",".join(sorted(set(s))))
        .rename("present_in")
        .reset_index()
    )
    combined = combined.merge(presence, on="dedup_key", how="left")

    # Keep the WoS row when both have it (WoS keeps Keywords Plus and research areas)
    combined["_pref"] = (combined["source_db"] == "WoS").astype(int)
    combined = (
        combined.sort_values(["_pref", "citations"], ascending=[False, False])
        .drop_duplicates("dedup_key", keep="first")
        .drop(columns=["_pref"])
        .reset_index(drop=True)
    )
    print(f"  After dedup: {len(combined)} unique records")

    # Overlap table
    overlap = combined["present_in"].value_counts().rename_axis("present_in").reset_index(name="n_records")
    overlap.to_csv(TABLES / "01_source_overlap.csv", index=False)
    print(overlap.to_string(index=False))

    return combined


if __name__ == "__main__":
    print("Harmonizing WoS + Scopus exports")
    df = harmonize()
    df.to_parquet(OUT / "harmonized.parquet", index=False)
    df.drop(columns=["abstract", "addresses"]).to_csv(OUT / "harmonized.csv", index=False)
    print(f"Wrote {OUT/'harmonized.parquet'}  ({len(df)} rows)")
