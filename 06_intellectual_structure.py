"""
Intellectual-structure analyses built from the Scopus 'References' field.

The WoS export did not include cited-reference strings, so these analyses use
the Scopus-referenced subset (about 3,972 documents). Each reference inside the
Scopus References field ends with a parenthesised year, which is used as the
record delimiter.

Outputs (to bibliometric_analysis/tables/):
  30_rpys.csv                 Referenced Publication Year Spectroscopy
  31_local_cited_refs.csv     Most frequently cited references in the corpus
  32_cocitation_edges.csv     Co-citation network edges (top references)
  32_cocitation_nodes.csv     Co-citation node stats
  33_coupling_edges.csv       Bibliographic-coupling edges (documents)
  33_coupling_nodes.csv       Bibliographic-coupling node stats
  34_historiograph_edges.csv  Within-corpus direct citation edges
  34_historiograph_nodes.csv  Within-corpus direct citation nodes
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent                               # parent of the workspace
TABLES = OUT / "tables"
TABLES.mkdir(parents=True, exist_ok=True)


def find_data_file(filename: str) -> Path:
    """Locate a raw data file regardless of where the workspace has been moved."""
    candidates = [
        OUT / filename,
        ROOT / filename,
        ROOT / "SLR Predictive and Disaster" / filename,
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


SCOPUS = find_data_file("scopus list of article.csv")
YEAR_LO, YEAR_HI = 2015, 2025

REF_SPLIT = re.compile(r"(?<=\(\d{4}\))\s*;\s*")
YEAR_RX = re.compile(r"\((\d{4})\)")


def ascii_clean(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()


def title_fingerprint(text: str) -> str:
    """First four content words of a title, 5 chars each, lower-cased ASCII.
    Used on both reference title-starts and corpus paper titles so that the two
    can be matched for the historiograph."""
    t = ascii_clean(text).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = [w for w in t.split() if len(w) > 2][:4]
    return "".join(w[:5] for w in words)


def _title_token(ref: str) -> str:
    """
    Heuristic title fingerprint for a reference string. Splitting a Scopus
    reference on ', ' yields [authors_block, title_start, ...] because author
    initials are separated by '; ' rather than ', '. We fingerprint the title
    start, which avoids the surname+year collisions that plague common names
    such as Wang or Zhang.
    """
    parts = re.split(r",\s*", ref)
    if len(parts) < 2:
        return ""
    return title_fingerprint(parts[1])


def parse_reference(ref: str):
    """Return (key, year, surname) for a single reference string, or None."""
    ref = ref.strip()
    years = YEAR_RX.findall(ref)
    if not years:
        return None
    year = int(years[-1])
    if year < 1800 or year > YEAR_HI:
        return None
    # First author surname: first token of the reference, before initials/comma/semicolon
    head = re.split(r"[;,]", ref, maxsplit=1)[0].strip()
    head = ascii_clean(head)
    m = re.match(r"([A-Za-z\-']+)", head)
    surname = m.group(1).lower() if m else head.lower()[:12]
    if not surname:
        return None
    tok = _title_token(ref)
    key = f"{surname}|{tok}|{year}" if tok else f"{surname}||{year}"
    return key, year, surname


def own_key(authors: str, year, title: str) -> str | None:
    """Key for a corpus paper in the same format as parse_reference, so that
    references can be matched to corpus papers for the historiograph."""
    if not isinstance(authors, str) or not authors.strip() or pd.isna(year):
        return None
    first = re.split(r"[;,]", authors.strip(), maxsplit=1)[0].strip()
    first = ascii_clean(first)
    m = re.match(r"([A-Za-z\-']+)", first)
    if not m:
        return None
    surname = m.group(1).lower()
    tok = title_fingerprint(title) if isinstance(title, str) else ""
    return f"{surname}|{tok}|{int(year)}" if tok else f"{surname}||{int(year)}"


def load_scopus_refs():
    df = pd.read_csv(SCOPUS, low_memory=False)
    df = df[pd.to_numeric(df["Year"], errors="coerce").between(YEAR_LO, YEAR_HI)].copy()
    df = df[df["References"].notna()].copy()
    df["doc_key"] = [own_key(a, y, t) for a, y, t in zip(df["Authors"], df["Year"], df["Title"])]
    print(f"  Scopus docs with references: {len(df)}")
    return df


def main():
    df = load_scopus_refs()

    # Parse every reference once
    doc_refs = []           # list of (doc_index, [ref_keys])
    all_ref_years = []
    ref_freq = Counter()
    ref_first_full = {}     # key -> a representative display string
    for idx, refstr in zip(df.index, df["References"]):
        keys = []
        for raw in REF_SPLIT.split(str(refstr)):
            parsed = parse_reference(raw)
            if parsed is None:
                continue
            key, year, surname = parsed
            keys.append(key)
            all_ref_years.append(year)
            if key not in ref_first_full:
                ref_first_full[key] = ascii_clean(raw.strip())[:90]
        keys = list(dict.fromkeys(keys))  # unique within a document
        for k in keys:
            ref_freq[k] += 1
        doc_refs.append((idx, keys))
    print(f"  parsed {len(all_ref_years):,} dated references; {len(ref_freq):,} unique keys")

    # ---------- 1. RPYS ----------
    yr_counter = Counter(y for y in all_ref_years if 1950 <= y <= YEAR_HI)
    rpys = pd.DataFrame(sorted(yr_counter.items()), columns=["ref_year", "n_refs"])
    # 5-year median deviation (classic RPYS smoothing)
    rpys = rpys.sort_values("ref_year").reset_index(drop=True)
    med = rpys["n_refs"].rolling(5, center=True, min_periods=1).median()
    rpys["median_5yr"] = med.round(1)
    rpys["deviation"] = (rpys["n_refs"] - med).round(1)
    rpys.to_csv(TABLES / "30_rpys.csv", index=False)
    print(f"  RPYS: {len(rpys)} years")

    # ---------- 2. Most local cited references ----------
    local = pd.DataFrame(
        [(k, c, ref_first_full.get(k, k)) for k, c in ref_freq.most_common(30)],
        columns=["reference_key", "local_citations", "reference"],
    )
    local.to_csv(TABLES / "31_local_cited_refs.csv", index=False)
    print(f"  local cited refs: top {len(local)}")

    # ---------- 3. Co-citation network ----------
    top_refs = {k for k, _ in ref_freq.most_common(50)}
    co = Counter()
    for _, keys in doc_refs:
        present = [k for k in keys if k in top_refs]
        for a, b in combinations(sorted(set(present)), 2):
            co[(a, b)] += 1
    co_edges = pd.DataFrame(
        [(a, b, w) for (a, b), w in co.items() if w >= 3],
        columns=["ref_a", "ref_b", "weight"],
    ).sort_values("weight", ascending=False)
    co_nodes = pd.DataFrame(
        [(k, ref_freq[k], ref_first_full.get(k, k)) for k in top_refs],
        columns=["reference_key", "citations", "label"],
    ).sort_values("citations", ascending=False)
    co_edges.to_csv(TABLES / "32_cocitation_edges.csv", index=False)
    co_nodes.to_csv(TABLES / "32_cocitation_nodes.csv", index=False)
    print(f"  co-citation: {len(co_nodes)} nodes, {len(co_edges)} edges")

    # ---------- 4. Bibliographic coupling (documents) ----------
    # Two documents are coupled if they share references. Restrict to documents
    # with a reasonable number of references and pick the most-coupled ones.
    ref_to_docs = defaultdict(list)
    doc_meta = {}
    for (idx, keys) in doc_refs:
        for k in keys:
            ref_to_docs[k].append(idx)
    coupling = Counter()
    for k, docs in ref_to_docs.items():
        if len(docs) < 2 or len(docs) > 80:   # skip ultra-common refs (noise) and singletons
            continue
        for a, b in combinations(sorted(set(docs)), 2):
            coupling[(a, b)] += 1
    # Keep strongest couplings
    strong = [(a, b, w) for (a, b), w in coupling.items() if w >= 4]
    # Build node labels (first author + year)
    def doc_label(idx):
        a = df.loc[idx, "Authors"]
        y = df.loc[idx, "Year"]
        first = re.split(r"[;,]", str(a))[0].strip() if isinstance(a, str) else "Anon"
        return f"{ascii_clean(first)} ({int(y)})"
    coup_edges = pd.DataFrame(strong, columns=["doc_a", "doc_b", "weight"]).sort_values("weight", ascending=False).head(400)
    node_ids = set(coup_edges["doc_a"]) | set(coup_edges["doc_b"])
    coup_nodes = pd.DataFrame(
        [(i, doc_label(i), int(pd.to_numeric(df.loc[i, "Cited by"], errors="coerce") or 0)) for i in node_ids],
        columns=["doc_id", "label", "citations"],
    )
    coup_edges.to_csv(TABLES / "33_coupling_edges.csv", index=False)
    coup_nodes.to_csv(TABLES / "33_coupling_nodes.csv", index=False)
    print(f"  bibliographic coupling: {len(coup_nodes)} nodes, {len(coup_edges)} edges")

    # ---------- 5. Historiograph (within-corpus direct citations) ----------
    corpus_keys = {}
    for idx, k in zip(df.index, df["doc_key"]):
        if k:
            corpus_keys.setdefault(k, idx)   # first occurrence
    hist_edges = []
    for (idx, keys) in doc_refs:
        citing_year = pd.to_numeric(df.loc[idx, "Year"], errors="coerce")
        for k in keys:
            if k in corpus_keys and corpus_keys[k] != idx:
                cited_idx = corpus_keys[k]
                hist_edges.append((cited_idx, idx))  # cited -> citing
    he = pd.DataFrame(hist_edges, columns=["cited_id", "citing_id"])
    # local citation count per node
    local_cites = he["cited_id"].value_counts()
    keep_nodes = set(local_cites[local_cites >= 2].index)
    he = he[he["cited_id"].isin(keep_nodes) | he["citing_id"].isin(keep_nodes)]

    def label_year(idx):
        a = df.loc[idx, "Authors"]
        y = df.loc[idx, "Year"]
        first = re.split(r"[;,]", str(a))[0].strip() if isinstance(a, str) else "Anon"
        return ascii_clean(first), int(y) if not pd.isna(y) else 0

    hist_nodes_ids = set(he["cited_id"]) | set(he["citing_id"])
    hist_nodes = []
    for i in hist_nodes_ids:
        lab, yr = label_year(i)
        hist_nodes.append((i, f"{lab} ({yr})", yr,
                           int(local_cites.get(i, 0)),
                           int(pd.to_numeric(df.loc[i, "Cited by"], errors="coerce") or 0)))
    hist_nodes = pd.DataFrame(hist_nodes, columns=["doc_id", "label", "year", "local_citations", "global_citations"])
    he.to_csv(TABLES / "34_historiograph_edges.csv", index=False)
    hist_nodes.to_csv(TABLES / "34_historiograph_nodes.csv", index=False)
    print(f"  historiograph: {len(hist_nodes)} nodes, {len(he)} edges")

    print("Done.")


if __name__ == "__main__":
    main()
