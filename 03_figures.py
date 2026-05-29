"""
Generate publication-quality figures (300 DPI, vector-friendly typography)
from harmonized data + computed tables.

Figures
-------
fig01_annual_production.png        annual pubs + cumulative line
fig02_doc_types_languages.png      doc types + languages
fig03_top_sources.png              ranked top sources
fig04_bradford.png                 Bradford zones + curve
fig05_top_authors.png              top authors by output + impact
fig06_lotka.png                    Lotka observed vs expected
fig07_top_countries.png            top countries + SCP/MCP
fig08_top_affiliations.png         top affiliations
fig09_funders_oa.png               top funders + OA share
fig10_top_cited.png                top-cited papers (h-bar)
fig11_keyword_treemap.png          top 30 author keywords (bar)
fig12_keyword_network.png          keyword co-occurrence network
fig13_thematic_evolution.png       top keyword trends 2015-2025
fig14_three_fields.png             three-fields plot (country -> author -> kw)
fig15_wordcloud.png                wordcloud of author keywords
fig16_database_overlap.png         WoS / Scopus overlap
fig17_citation_distribution.png    citation histogram + Lorenz curve
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mtick
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from wordcloud import WordCloud

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent
TABLES = OUT / "tables"
FIGS = OUT / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

# ---------- global aesthetics (Q1 journal-friendly) ----------
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.9,
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.6,
    "grid.linestyle": "--",
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})

# Distinctive but print-safe palette
PALETTE = ["#1f4e79", "#c0504d", "#9bbb59", "#8064a2", "#f79646",
           "#4bacc6", "#7f6084", "#806000", "#365f91", "#993300"]
sns.set_palette(PALETTE)


def _annot_bars(ax, fmt="{:,}", offset=3, fs=9, color="#333"):
    for p in ax.patches:
        v = p.get_height() if p.get_height() != 0 else p.get_width()
        if p.get_width() > p.get_height():  # horizontal bar
            ax.annotate(fmt.format(int(p.get_width())),
                        (p.get_width(), p.get_y() + p.get_height()/2),
                        ha="left", va="center", xytext=(offset,0),
                        textcoords="offset points", fontsize=fs, color=color)
        else:
            ax.annotate(fmt.format(int(p.get_height())),
                        (p.get_x() + p.get_width()/2, p.get_height()),
                        ha="center", va="bottom", xytext=(0, offset),
                        textcoords="offset points", fontsize=fs, color=color)


# ---------- 1. Annual production ----------

def fig_annual(ann: pd.DataFrame, summary: dict):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.bar(ann["year"], ann["n_pubs"], color=PALETTE[0],
                  edgecolor="#11355a", linewidth=0.6, label="Annual publications", zorder=2)
    for b, v in zip(bars, ann["n_pubs"]):
        ax.text(b.get_x()+b.get_width()/2, v+15, f"{int(v)}", ha="center", fontsize=9, color="#11355a")

    ax2 = ax.twinx()
    ax2.plot(ann["year"], ann["n_pubs"].cumsum(),
             color=PALETTE[1], marker="o", lw=2.2, label="Cumulative publications", zorder=3)
    ax2.fill_between(ann["year"], 0, ann["n_pubs"].cumsum(), color=PALETTE[1], alpha=0.08)
    ax2.set_ylabel("Cumulative publications", color=PALETTE[1])
    ax2.tick_params(axis="y", labelcolor=PALETTE[1])
    ax2.grid(False)

    ax.set_xlabel("Publication year")
    ax.set_ylabel("Annual publications")
    ax.set_title(f"Annual Scientific Production (2015–2025) — CAGR ≈ {summary['annual']['cagr_pubs_pct']:.1f}%")
    ax.set_xticks(ann["year"])
    ax.set_ylim(0, ann["n_pubs"].max()*1.15)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2, l1+l2, loc="upper left")

    fig.savefig(FIGS / "fig01_annual_production.png")
    plt.close(fig)


# ---------- 2. Doc types + languages ----------

def fig_doc_types(dt: pd.DataFrame, lang: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    top_dt = dt.head(7).copy()
    other = dt.iloc[7:]
    if len(other):
        top_dt = pd.concat([top_dt, pd.DataFrame([{
            "doc_type":"Other", "n":int(other["n"].sum()),
            "citations":int(other["citations"].sum()),
            "share_pct": round(other["share_pct"].sum(),2)
        }])], ignore_index=True)
    colors = sns.color_palette("crest", n_colors=len(top_dt))
    wedges, _ = axes[0].pie(top_dt["n"], colors=colors, startangle=90,
                            wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5))
    axes[0].set_title("Document Types")
    labels = [f"{r['doc_type']}  ({r['n']:,}; {r['share_pct']:.1f}%)" for _, r in top_dt.iterrows()]
    axes[0].legend(wedges, labels, loc="upper center", bbox_to_anchor=(0.5, -0.04),
                   fontsize=8, ncol=2, frameon=False)

    top_lang = lang.head(6).copy()
    other_l = lang.iloc[6:]
    if len(other_l):
        top_lang = pd.concat([top_lang, pd.DataFrame([{
            "language":"Other", "n":int(other_l["n"].sum()),
            "share_pct":round(other_l["share_pct"].sum(),2)
        }])], ignore_index=True)
    bars = axes[1].barh(top_lang["language"][::-1], top_lang["n"][::-1],
                        color=sns.color_palette("flare", n_colors=len(top_lang))[::-1],
                        edgecolor="white")
    axes[1].set_title("Languages of Publication")
    axes[1].set_xlabel("Number of papers (log scale)")
    axes[1].set_xscale("log")
    for b, v, p in zip(bars, top_lang["n"][::-1], top_lang["share_pct"][::-1]):
        axes[1].text(v*1.05, b.get_y()+b.get_height()/2, f"{int(v):,}  ({p:.1f}%)",
                     va="center", fontsize=9)

    fig.savefig(FIGS / "fig02_doc_types_languages.png")
    plt.close(fig)


# ---------- 3. Top sources ----------

def fig_top_sources(ts: pd.DataFrame, n=20):
    ts = ts.head(n).copy()
    ts["short"] = ts["source_title"].str.title().str.replace(" And ", " & ").str.slice(0, 55)
    fig, ax = plt.subplots(figsize=(11, 7))
    # color by mean citations
    norm = plt.Normalize(ts["mean_citations"].min(), ts["mean_citations"].max())
    colors = plt.cm.viridis(norm(ts["mean_citations"]))
    bars = ax.barh(ts["short"][::-1], ts["n_pubs"][::-1], color=colors[::-1], edgecolor="white")
    ax.set_xlabel("Number of publications")
    ax.set_title(f"Top {n} Most Productive Sources (colour = mean citations / paper)")
    for b, v, c in zip(bars, ts["n_pubs"][::-1], ts["mean_citations"][::-1]):
        ax.text(v+1, b.get_y()+b.get_height()/2,
                f"{int(v)}  ⌀{c:.1f} TC", va="center", fontsize=9, color="#222")
    sm = plt.cm.ScalarMappable(cmap="viridis", norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.02, shrink=0.7)
    cbar.set_label("Mean citations / paper", fontsize=9)
    fig.savefig(FIGS / "fig03_top_sources.png")
    plt.close(fig)


# ---------- 4. Bradford ----------

def fig_bradford(bs: pd.DataFrame, bsum: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    bs = bs.copy().reset_index(drop=True)
    bs["rank"] = bs.index + 1
    bs["cum"] = bs["n_pubs"].cumsum()
    colors = {"Core (Zone 1)": PALETTE[0], "Zone 2": PALETTE[2], "Zone 3": PALETTE[1]}
    for z, sub in bs.groupby("zone"):
        axes[0].fill_between(sub["rank"], 0, sub["cum"], color=colors[z], alpha=0.5, label=z)
    axes[0].plot(bs["rank"], bs["cum"], color="#333", lw=1)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Source rank (log)")
    axes[0].set_ylabel("Cumulative publications")
    axes[0].set_title("Bradford's Law — cumulative production by ranked sources")
    axes[0].legend(loc="upper left")

    # Zone summary
    z = bsum.copy()
    x = np.arange(len(z))
    w = 0.4
    axes[1].bar(x - w/2, z["n_sources"], width=w, color=PALETTE[0], label="Sources")
    axes[1].bar(x + w/2, z["n_pubs"], width=w, color=PALETTE[1], label="Publications")
    axes[1].set_xticks(x); axes[1].set_xticklabels(z["zone"])
    axes[1].set_title("Bradford Zones — sources vs publications")
    axes[1].legend(loc="upper right")
    for i, r in z.iterrows():
        axes[1].text(i-w/2, r["n_sources"]+5, f"{int(r['n_sources'])}", ha="center", fontsize=9)
        axes[1].text(i+w/2, r["n_pubs"]+5, f"{int(r['n_pubs'])}\n({r['share_pubs_pct']:.1f}%)",
                     ha="center", fontsize=9)
    axes[1].set_ylim(0, max(z["n_pubs"].max(), z["n_sources"].max())*1.32)

    fig.savefig(FIGS / "fig04_bradford.png")
    plt.close(fig)


# ---------- 5. Top authors ----------

def fig_top_authors(ta: pd.DataFrame, n=20):
    ta = ta.head(n).copy()
    fig, ax = plt.subplots(figsize=(11, 7))
    norm = plt.Normalize(ta["total_citations"].min(), ta["total_citations"].max())
    colors = plt.cm.plasma(norm(ta["total_citations"]))
    bars = ax.barh(ta["author"][::-1], ta["n_pubs"][::-1], color=colors[::-1], edgecolor="white")
    ax.set_xlabel("Number of publications")
    ax.set_title(f"Top {n} Most Productive Authors (colour = total citations)")
    for b, v, c in zip(bars, ta["n_pubs"][::-1], ta["total_citations"][::-1]):
        ax.text(v+0.1, b.get_y()+b.get_height()/2,
                f"{int(v)}  ({int(c):,} TC)", va="center", fontsize=9, color="#222")
    sm = plt.cm.ScalarMappable(cmap="plasma", norm=norm); sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.02, shrink=0.7)
    cbar.set_label("Total citations", fontsize=9)
    fig.savefig(FIGS / "fig05_top_authors.png")
    plt.close(fig)


# ---------- 6. Lotka ----------

def fig_lotka(la: pd.DataFrame, n_authors_total: int):
    la = la.head(15).copy()
    la["expected_pct"] = la["expected_lotka_pct"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = la["n_pubs"]
    ax.bar(x, la["share_authors_pct"], color=PALETTE[0], alpha=0.85, label="Observed")
    ax.plot(x, la["expected_pct"], color=PALETTE[1], marker="o", lw=2, label="Lotka's law (theoretical)")
    ax.set_xlabel("Number of publications per author (k)")
    ax.set_ylabel("Share of authors (%)")
    ax.set_title(f"Lotka's Law — productivity distribution across {n_authors_total:,} authors")
    ax.set_xticks(x)
    ax.legend()
    fig.savefig(FIGS / "fig06_lotka.png")
    plt.close(fig)


# ---------- 7. Countries ----------

def fig_countries(tc: pd.DataFrame, cc: pd.DataFrame, n=20):
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    tc = tc.head(n).copy()
    bars = axes[0].barh(tc["country"][::-1], tc["n_pubs"][::-1], color=PALETTE[0], edgecolor="white")
    axes[0].set_xlabel("Number of publications")
    axes[0].set_title(f"Top {n} Countries by Output")
    for b, v, mc in zip(bars, tc["n_pubs"][::-1], tc["mean_citations"][::-1]):
        axes[0].text(v+5, b.get_y()+b.get_height()/2,
                     f"{int(v)}  (⌀{mc:.1f} TC)", va="center", fontsize=9)

    cc = cc.head(n).copy()
    cc = cc[::-1]  # invert for horizontal stack top->down
    scp = cc.get("SCP", pd.Series([0]*len(cc)))
    mcp = cc.get("MCP", pd.Series([0]*len(cc)))
    axes[1].barh(cc["country"], scp, color=PALETTE[0], label="Single-country pubs (SCP)")
    axes[1].barh(cc["country"], mcp, left=scp, color=PALETTE[1], label="Multi-country pubs (MCP)")
    for y, (s, m, ratio) in enumerate(zip(scp, mcp, cc["MCP_ratio_pct"])):
        axes[1].text(s+m+8, y, f"MCP {ratio:.0f}%", va="center", fontsize=8, color="#444")
    axes[1].set_xlabel("Publications")
    axes[1].set_title("International Collaboration (SCP vs MCP)")
    axes[1].legend(loc="lower right")

    fig.savefig(FIGS / "fig07_top_countries.png")
    plt.close(fig)


# ---------- 8. Affiliations ----------

def fig_affiliations(tf: pd.DataFrame, n=20):
    tf = tf.head(n).copy()
    tf["short"] = tf["affiliation"].str.slice(0, 55)
    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(tf["short"][::-1], tf["n_pubs"][::-1], color=PALETTE[2], edgecolor="white")
    ax.set_xlabel("Number of publications")
    ax.set_title(f"Top {n} Contributing Affiliations")
    for b, v, c in zip(bars, tf["n_pubs"][::-1], tf["total_citations"][::-1]):
        ax.text(v+0.3, b.get_y()+b.get_height()/2,
                f"{int(v)}  ({int(c):,} TC)", va="center", fontsize=8, color="#222")
    fig.savefig(FIGS / "fig08_top_affiliations.png")
    plt.close(fig)


# ---------- 9. Funders + OA ----------

def fig_funders_oa(funders: pd.DataFrame, oa: pd.DataFrame, n=15):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))

    fd = funders.head(n).copy()
    fd["short"] = fd["funder"].str.slice(0, 50)
    bars = axes[0].barh(fd["short"][::-1], fd["n"][::-1], color=PALETTE[3], edgecolor="white")
    axes[0].set_title(f"Top {n} Funding Organisations")
    axes[0].set_xlabel("Number of acknowledgements")
    for b, v in zip(bars, fd["n"][::-1]):
        axes[0].text(v+0.5, b.get_y()+b.get_height()/2, f"{int(v)}",
                     va="center", fontsize=9)

    oa_top = oa.head(8).copy()
    colors = sns.color_palette("YlGnBu", n_colors=len(oa_top))
    wedges, _ = axes[1].pie(oa_top["n"], colors=colors, startangle=90,
                             wedgeprops=dict(width=0.4, edgecolor="white", linewidth=1.5))
    axes[1].set_title("Open Access Status")
    labels = [f"{r['category']} — {r['n']:,} ({r['share_pct']:.1f}%)" for _, r in oa_top.iterrows()]
    axes[1].legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)

    fig.savefig(FIGS / "fig09_funders_oa.png")
    plt.close(fig)


# ---------- 10. Top-cited ----------

def fig_top_cited(top: pd.DataFrame, n=15):
    top = top.head(n).copy()
    top["label"] = top.apply(
        lambda r: f"{str(r['authors']).split(';')[0]} et al. ({int(r['year'])}) — {str(r['source_title'])[:35]}",
        axis=1)
    fig, ax = plt.subplots(figsize=(11, 7))
    norm = plt.Normalize(top["TC_per_year"].min(), top["TC_per_year"].max())
    colors = plt.cm.YlOrRd(norm(top["TC_per_year"]))
    bars = ax.barh(top["label"][::-1], top["citations"][::-1],
                   color=colors[::-1], edgecolor="white")
    for b, v, pyr in zip(bars, top["citations"][::-1], top["TC_per_year"][::-1]):
        ax.text(v+3, b.get_y()+b.get_height()/2,
                f"{int(v):,}  ({pyr:.1f}/yr)", va="center", fontsize=9, color="#222")
    ax.set_xlabel("Total citations")
    ax.set_title(f"Top {n} Most Cited Papers (colour = citations per year)")
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=norm); sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.02, shrink=0.7)
    cbar.set_label("Citations / year", fontsize=9)
    fig.savefig(FIGS / "fig10_top_cited.png")
    plt.close(fig)


# ---------- 11. Top keywords bar ----------

def fig_top_keywords(kw: pd.DataFrame, n=30):
    kw = kw.head(n).copy()
    fig, ax = plt.subplots(figsize=(11, 8.5))
    norm = plt.Normalize(kw["n"].min(), kw["n"].max())
    colors = plt.cm.viridis(norm(kw["n"]))
    bars = ax.barh(kw["keyword"][::-1].str.title(), kw["n"][::-1], color=colors[::-1], edgecolor="white")
    ax.set_xlabel("Frequency")
    ax.set_title(f"Top {n} Author Keywords (colour = frequency)")
    for b, v, p in zip(bars, kw["n"][::-1], kw["share_pct"][::-1]):
        ax.text(v+2, b.get_y()+b.get_height()/2, f"{int(v)}  ({p:.2f}%)",
                va="center", fontsize=9, color="#222")
    fig.savefig(FIGS / "fig11_keyword_treemap.png")
    plt.close(fig)


# ---------- 12. Keyword network ----------

def fig_keyword_network(edges: pd.DataFrame, kw: pd.DataFrame, max_nodes=60, max_edges=180):
    if edges.empty:
        return
    top_kw = set(kw.head(max_nodes)["keyword"])
    sub = edges[edges["kw_a"].isin(top_kw) & edges["kw_b"].isin(top_kw)].head(max_edges)
    G = nx.Graph()
    for _, r in sub.iterrows():
        G.add_edge(r["kw_a"], r["kw_b"], weight=int(r["weight"]))
    if len(G) == 0:
        return

    # Node sizes ~ keyword frequency
    freq = dict(zip(kw["keyword"], kw["n"]))
    sizes = [max(120, freq.get(n, 1)*4) for n in G.nodes]

    # Communities for colouring (Louvain via greedy modularity)
    comms = list(nx.algorithms.community.greedy_modularity_communities(G))
    color_of = {}
    cmap = sns.color_palette("Set2", n_colors=max(len(comms), 3))
    for i, c in enumerate(comms):
        for n in c:
            color_of[n] = cmap[i % len(cmap)]
    node_colors = [color_of.get(n, "#999") for n in G.nodes]

    # Two-stage layout: Kamada-Kawai for a stable backbone, then jitter on top
    try:
        pos = nx.kamada_kawai_layout(G, weight="weight")
    except Exception:
        pos = nx.spring_layout(G, seed=42, k=2.0/math.sqrt(len(G)), iterations=200, weight="weight")

    fig, ax = plt.subplots(figsize=(15, 11))
    weights = np.array([d["weight"] for _,_,d in G.edges(data=True)], dtype=float)
    if weights.max() > 0:
        widths = 0.3 + 3.0 * (weights / weights.max())
    else:
        widths = [0.5]*len(weights)
    nx.draw_networkx_edges(G, pos, width=widths, alpha=0.3, edge_color="#5b6b73", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=node_colors,
                            edgecolors="white", linewidths=1.2, alpha=0.95, ax=ax)

    # Place labels slightly offset above their nodes; key terms get larger font
    freq_arr = np.array([freq.get(n, 1) for n in G.nodes])
    qhi, qmid = np.quantile(freq_arr, [0.85, 0.5])
    for n, (x, y) in pos.items():
        f = freq.get(n, 1)
        fs = 11 if f >= qhi else (9 if f >= qmid else 7.5)
        weight = "bold" if f >= qhi else "normal"
        # Offset label outward from centroid to reduce overlap
        ax.text(x, y + 0.04, n.title(), ha="center", va="bottom",
                fontsize=fs, fontweight=weight, color="#111",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))

    ax.set_title(f"Keyword Co-occurrence Network  —  {len(G)} terms, {G.number_of_edges()} links, {len(comms)} thematic clusters",
                 fontsize=14, fontweight="bold")
    # Legend for clusters
    legend_handles = []
    for i, c in enumerate(comms[:6]):
        top3 = sorted(c, key=lambda x: -freq.get(x, 0))[:3]
        label = f"Cluster {i+1}: " + ", ".join(t.title() for t in top3)
        legend_handles.append(Line2D([0],[0], marker="o", color="w",
                                      markerfacecolor=cmap[i % len(cmap)],
                                      markersize=10, label=label))
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9, framealpha=0.85)
    ax.set_axis_off()
    fig.savefig(FIGS / "fig12_keyword_network.png")
    plt.close(fig)


# ---------- 13. Thematic evolution ----------

def fig_thematic_evolution(kt: pd.DataFrame, top_k=10):
    if kt.empty: return
    top_terms = (kt.groupby("keyword")["n"].sum()
                 .sort_values(ascending=False).head(top_k).index.tolist())
    sub = kt[kt["keyword"].isin(top_terms)].copy()
    pivot = sub.pivot_table(index="year", columns="keyword", values="n", aggfunc="sum").fillna(0)
    pivot = pivot[top_terms]  # preserve order
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    pivot.plot(ax=ax, marker="o", linewidth=1.8)
    ax.set_title(f"Thematic Evolution — Top {top_k} Author Keywords (2015–2025)")
    ax.set_xlabel("Year"); ax.set_ylabel("Annual keyword count")
    ax.set_xticks(pivot.index)
    ax.legend(loc="upper left", ncol=2, fontsize=9, title="Keyword")
    fig.savefig(FIGS / "fig13_thematic_evolution.png")
    plt.close(fig)


# ---------- 14. Three-fields plot (Sankey-style) ----------

def fig_three_fields(df: pd.DataFrame, tc: pd.DataFrame, ta: pd.DataFrame, kw: pd.DataFrame, n=10):
    """
    Crude three-fields plot using stacked horizontal bars and lines.
    Columns: Country (left) -> Author (middle) -> Keyword (right).
    """
    from collections import defaultdict
    import re as _re

    top_countries = tc.head(n)["country"].tolist()
    top_authors = ta.head(n)["author"].tolist()
    top_kw = kw.head(n)["keyword"].tolist()

    # Build country->author and author->keyword links
    ca = Counter()
    ak = Counter()
    for _, r in df.iterrows():
        addr = r["addresses"] if r["addresses"] else r["affiliations"]
        cs = set()
        if isinstance(addr, str):
            for c in top_countries:
                # naive substring match
                if c.lower() in addr.lower():
                    cs.add(c)
        authors = []
        if isinstance(r["authors"], str):
            for a in r["authors"].split(";"):
                a = a.strip()
                if a in top_authors:
                    authors.append(a)
        kws = []
        if isinstance(r["author_keywords"], str):
            for k in r["author_keywords"].split(";"):
                k = k.strip().lower()
                # apply same light normalisation as metrics
                if len(k) > 4 and k.endswith("ies"): k = k[:-3] + "y"
                elif len(k) > 3 and k.endswith("s") and not k.endswith("ss"): k = k[:-1]
                if k in top_kw:
                    kws.append(k)
        for c in cs:
            for a in authors:
                ca[(c, a)] += 1
        for a in authors:
            for k in kws:
                ak[(a, k)] += 1

    if not ca and not ak:
        return

    # Positions
    fig, ax = plt.subplots(figsize=(15, 9))
    def col_positions(items, x):
        n = len(items)
        y = np.linspace(0.05, 0.95, n)
        return {it: (x, yy) for it, yy in zip(items, y)}, y
    posC, _ = col_positions(top_countries, 0.05)
    posA, _ = col_positions(top_authors, 0.5)
    posK, _ = col_positions(top_kw, 0.95)

    # Draw nodes
    def node(ax, x, y, label, color):
        ax.add_patch(FancyBboxPatch((x-0.08, y-0.02), 0.16, 0.04,
                                    boxstyle="round,pad=0.005",
                                    fc=color, ec="white", lw=1, alpha=0.95,
                                    transform=ax.transAxes))
        ax.text(x, y, label, ha="center", va="center", fontsize=9,
                color="white", fontweight="bold", transform=ax.transAxes)
    for c, (x, y) in posC.items(): node(ax, x, y, c[:18], PALETTE[0])
    for a, (x, y) in posA.items(): node(ax, x, y, a[:20], PALETTE[3])
    for k, (x, y) in posK.items(): node(ax, x, y, k[:22].title(), PALETTE[2])

    # Draw edges (curved) with widths
    def edge(p0, p1, w, color):
        x0, y0 = p0; x1, y1 = p1
        ax.plot([x0+0.08, x1-0.08], [y0, y1], color=color, lw=w, alpha=0.45,
                transform=ax.transAxes, solid_capstyle="round")

    if ca:
        wmax = max(ca.values())
        for (c, a), w in ca.items():
            if c in posC and a in posA:
                edge(posC[c], posA[a], 0.5 + 5*(w/wmax), PALETTE[0])
    if ak:
        wmax = max(ak.values())
        for (a, k), w in ak.items():
            if a in posA and k in posK:
                edge(posA[a], posK[k], 0.5 + 5*(w/wmax), PALETTE[2])

    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_axis_off()
    ax.text(0.05, 1.0, "Countries", ha="center", fontsize=12, fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 1.0, "Authors", ha="center", fontsize=12, fontweight="bold", transform=ax.transAxes)
    ax.text(0.95, 1.0, "Keywords", ha="center", fontsize=12, fontweight="bold", transform=ax.transAxes)
    ax.set_title("Three-Fields Plot — Country × Author × Keyword (top 10 each)", fontsize=13, fontweight="bold")
    fig.savefig(FIGS / "fig14_three_fields.png")
    plt.close(fig)


# ---------- 15. Word cloud ----------

def fig_wordcloud(kw: pd.DataFrame):
    freq = dict(zip(kw["keyword"].str.title(), kw["n"]))
    wc = WordCloud(width=1600, height=900, background_color="white",
                   colormap="viridis", max_words=150, prefer_horizontal=0.85,
                   relative_scaling=0.4)
    wc.generate_from_frequencies(freq)
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.set_axis_off()
    ax.set_title("Word Cloud — Author Keywords", fontsize=14, fontweight="bold")
    fig.savefig(FIGS / "fig15_wordcloud.png")
    plt.close(fig)


# ---------- 16. Database overlap ----------

def fig_overlap(overlap: pd.DataFrame):
    """Simple proportional 'Venn' using two overlapping circles."""
    from matplotlib.patches import Circle
    counts = dict(zip(overlap["present_in"], overlap["n_records"]))
    only_wos = counts.get("WoS", 0)
    only_sc  = counts.get("Scopus", 0)
    both     = counts.get("Scopus,WoS", 0) + counts.get("WoS,Scopus", 0)
    total = only_wos + only_sc + both

    fig, ax = plt.subplots(figsize=(8, 6))
    r1 = math.sqrt((only_wos + both) / math.pi) * 0.05
    r2 = math.sqrt((only_sc + both) / math.pi) * 0.05
    # offset so circles overlap
    sep = (r1 + r2) * 0.65
    c1 = Circle((-sep/2, 0), r1, alpha=0.55, color=PALETTE[0], label="Web of Science")
    c2 = Circle(( sep/2, 0), r2, alpha=0.55, color=PALETTE[1], label="Scopus")
    ax.add_patch(c1); ax.add_patch(c2)
    ax.text(-sep, 0, f"WoS-only\n{only_wos:,}\n({only_wos/total*100:.1f}%)",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#1a1a1a")
    ax.text(sep, 0, f"Scopus-only\n{only_sc:,}\n({only_sc/total*100:.1f}%)",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#1a1a1a")
    ax.text(0, 0, f"Both\n{both:,}\n({both/total*100:.1f}%)",
            ha="center", va="center", fontsize=12, fontweight="bold", color="#222")
    ax.text(0, -max(r1, r2)*1.25, f"Total unique records: {total:,}",
            ha="center", fontsize=11, fontweight="bold")
    ax.set_xlim(-max(r1, r2)*2.5, max(r1, r2)*2.5)
    ax.set_ylim(-max(r1, r2)*1.8, max(r1, r2)*1.6)
    ax.set_aspect("equal"); ax.set_axis_off()
    ax.set_title("Database Overlap — Web of Science ∩ Scopus", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right")
    fig.savefig(FIGS / "fig16_database_overlap.png")
    plt.close(fig)


# ---------- 17. Citation distribution + Lorenz ----------

def fig_citations(df: pd.DataFrame, summary: dict):
    cs = np.array(sorted(df["citations"].tolist()))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # Histogram (log y) — clip bin edges to data range to keep them monotonic
    edges = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500]
    edges = [e for e in edges if e < cs.max()]
    edges.append(int(cs.max()) + 1)
    axes[0].hist(cs, bins=edges, color=PALETTE[0], edgecolor="white", alpha=0.9)
    axes[0].set_yscale("log")
    axes[0].set_xscale("symlog", linthresh=1)
    axes[0].set_xlabel("Citations per paper")
    axes[0].set_ylabel("Number of papers (log)")
    axes[0].set_title("Citation Distribution")
    m = summary["impact"]
    txt = (f"N = {m['n_records']:,}  ·  Total TC = {m['total_citations']:,}\n"
           f"Mean {m['mean_citations_per_paper']}  ·  Median {m['median_citations_per_paper']}  ·  Max {m['max_citations']:,}\n"
           f"h = {m['h_index']}  ·  g = {m['g_index']}  ·  Cited {m['cited_papers_pct']}%")
    axes[0].text(0.97, 0.96, txt, transform=axes[0].transAxes, fontsize=8.5,
                 va="top", ha="right",
                 bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.9))

    # Lorenz curve for citation concentration
    cs_sorted = np.sort(cs)
    cum = np.cumsum(cs_sorted) / cs_sorted.sum() if cs_sorted.sum() > 0 else np.zeros_like(cs_sorted, dtype=float)
    p = np.linspace(0, 1, len(cum))
    gini = 1 - 2*np.trapz(cum, p)
    axes[1].plot(p*100, cum*100, color=PALETTE[1], lw=2, label=f"Lorenz curve (Gini = {gini:.3f})")
    axes[1].plot([0,100],[0,100], "--", color="#888", lw=1, label="Equality")
    axes[1].fill_between(p*100, p*100, cum*100, color=PALETTE[1], alpha=0.12)
    axes[1].set_xlabel("Cumulative share of papers (%)")
    axes[1].set_ylabel("Cumulative share of citations (%)")
    axes[1].set_title("Citation Concentration (Lorenz curve)")
    axes[1].legend(loc="upper left")

    fig.savefig(FIGS / "fig17_citation_distribution.png")
    plt.close(fig)


# ---------- main ----------

def main():
    df = pd.read_parquet(OUT / "harmonized.parquet")
    with open(OUT / "summary.json") as f:
        summary = json.load(f)
    overlap = pd.read_csv(TABLES / "01_source_overlap.csv")
    ann = pd.read_csv(TABLES / "02_annual_metrics.csv")
    dt = pd.read_csv(TABLES / "03_doc_types.csv")
    lang = pd.read_csv(TABLES / "04_languages.csv")
    ts = pd.read_csv(TABLES / "05_top_sources.csv")
    bs = pd.read_csv(TABLES / "06_bradford_sources.csv")
    bsum = pd.read_csv(TABLES / "06_bradford_summary.csv")
    ta = pd.read_csv(TABLES / "07_top_authors.csv")
    la = pd.read_csv(TABLES / "07_lotka.csv")
    tf = pd.read_csv(TABLES / "08_top_affiliations.csv")
    tc = pd.read_csv(TABLES / "09_top_countries.csv")
    cc = pd.read_csv(TABLES / "09_country_collab.csv")
    funders = pd.read_csv(TABLES / "10_top_funders.csv")
    oa = pd.read_csv(TABLES / "11_open_access.csv")
    top_cited = pd.read_csv(TABLES / "12_top_cited.csv")
    kw_a = pd.read_csv(TABLES / "13_top_author_keywords.csv")
    edges = pd.read_csv(TABLES / "14_keyword_cooccurrence.csv")
    kt = pd.read_csv(TABLES / "15_keyword_trend.csv")

    print("Building figures...")
    fig_annual(ann, summary);                                                   print("  fig01")
    fig_doc_types(dt, lang);                                                    print("  fig02")
    fig_top_sources(ts);                                                        print("  fig03")
    fig_bradford(bs, bsum);                                                     print("  fig04")
    fig_top_authors(ta);                                                        print("  fig05")
    fig_lotka(la, summary["unique_authors"]);                                   print("  fig06")
    fig_countries(tc, cc);                                                      print("  fig07")
    fig_affiliations(tf);                                                       print("  fig08")
    fig_funders_oa(funders, oa);                                                print("  fig09")
    fig_top_cited(top_cited);                                                   print("  fig10")
    fig_top_keywords(kw_a);                                                     print("  fig11")
    fig_keyword_network(edges, kw_a);                                           print("  fig12")
    fig_thematic_evolution(kt);                                                 print("  fig13")
    fig_three_fields(df, tc, ta, kw_a);                                         print("  fig14")
    fig_wordcloud(kw_a);                                                        print("  fig15")
    fig_overlap(overlap);                                                       print("  fig16")
    fig_citations(df, summary);                                                 print("  fig17")
    print(f"Done. {len(list(FIGS.glob('*.png')))} figures in {FIGS}")


if __name__ == "__main__":
    main()
