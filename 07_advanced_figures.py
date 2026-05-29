"""
Render the advanced figures (300 DPI) that extend the base figure set:

  adv_annual_pubs_citations.png   #1  Annual publications + citations (dual axis)
  adv_lifecycle.png               #5  Logistic life-cycle of cumulative output
  adv_citations_over_time.png     #13 Annual + cumulative citations
  adv_rci_country.png             #3  Relative Citation Impact by country
  adv_source_bubble.png           #8  Source metrics bubble chart
  adv_subject_areas.png           #10 Subject-area distribution
  adv_rising_sources.png          #11 Rising sources
  adv_world_map.png               #17 World choropleth of output
  adv_rising_countries_map.png    #19 Choropleth of recent output share
  adv_country_collab_pairs.png    #16 Top collaborating country pairs
  adv_country_network.png         #20 Country co-authorship network
  adv_author_network.png          #21 Author co-authorship network
  adv_thematic_map.png            #23 Strategic diagram (centrality vs density)
  adv_rpys.png                    #24 Reference Publication Year Spectroscopy
  adv_cocitation.png              #26 Co-citation network
  adv_coupling.png                #27 Bibliographic coupling network
  adv_historiograph.png           #28 Historiograph
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns

OUT = Path(__file__).resolve().parent          # the workspace (folder holding this script)
ROOT = OUT.parent
TABLES = OUT / "tables"
FIGS = OUT / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.labelsize": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#333333", "axes.linewidth": 0.9,
    "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "grid.linestyle": "--", "legend.frameon": False,
    "savefig.bbox": "tight", "savefig.dpi": 300,
})
PALETTE = ["#1f4e79", "#c0504d", "#9bbb59", "#8064a2", "#f79646",
           "#4bacc6", "#7f6084", "#806000", "#365f91", "#993300"]
sns.set_palette(PALETTE)


# ---------- enhancements ----------

def fig_annual_pubs_citations():
    ann = pd.read_csv(TABLES / "02_annual_metrics.csv")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.bar(ann["year"], ann["n_pubs"], color=PALETTE[0],
                  edgecolor="#11355a", linewidth=0.6, label="Publications", zorder=2)
    for b, v in zip(bars, ann["n_pubs"]):
        ax.text(b.get_x()+b.get_width()/2, v+15, f"{int(v)}", ha="center", fontsize=8.5, color="#11355a")
    ax2 = ax.twinx()
    ax2.plot(ann["year"], ann["total_citations"], color=PALETTE[1], marker="o", lw=2.2,
             label="Total citations", zorder=3)
    ax2.set_ylabel("Total citations received", color=PALETTE[1])
    ax2.tick_params(axis="y", labelcolor=PALETTE[1])
    ax2.grid(False)
    ax.set_xlabel("Publication year"); ax.set_ylabel("Publications")
    ax.set_title("Annual Publications and Citations (2015–2025)")
    ax.set_xticks(ann["year"]); ax.set_ylim(0, ann["n_pubs"].max()*1.15)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2, l1+l2, loc="upper left")
    fig.savefig(FIGS / "adv_annual_pubs_citations.png"); plt.close(fig)


def fig_lifecycle():
    lc = pd.read_csv(TABLES / "28_lifecycle_fit.csv")
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.bar(lc["year"], lc["n_pubs"], color=PALETTE[5], alpha=0.55, label="Annual publications")
    ax2 = ax.twinx()
    ax2.plot(lc["year"], lc["cumulative"], color=PALETTE[0], marker="o", lw=2,
             label="Observed cumulative")
    if lc["logistic_fit"].notna().any():
        ax2.plot(lc["year"], lc["logistic_fit"], "--", color=PALETTE[1], lw=2,
                 label="Logistic life-cycle fit")
    ax2.set_ylabel("Cumulative publications"); ax2.grid(False)
    ax.set_xlabel("Publication year"); ax.set_ylabel("Annual publications")
    ax.set_title("Life-Cycle Curve of Cumulative Scientific Production")
    ax.set_xticks(lc["year"])
    h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2, l1+l2, loc="upper left")
    ax.text(0.035, 0.55,
            "The logistic inflection lies well beyond the\nobserved window, indicating the field is\nstill in its early, pre-saturation growth phase.",
            transform=ax.transAxes, fontsize=8.5, color="#333", va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.9))
    fig.savefig(FIGS / "adv_lifecycle.png"); plt.close(fig)


def fig_citations_over_time():
    ann = pd.read_csv(TABLES / "02_annual_metrics.csv")
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    ax.bar(ann["year"], ann["total_citations"], color=PALETTE[1], alpha=0.8, label="Citations received per cohort")
    ax2 = ax.twinx()
    ax2.plot(ann["year"], ann["total_citations"].cumsum(), color=PALETTE[0], marker="s", lw=2,
             label="Cumulative citations")
    ax2.set_ylabel("Cumulative citations"); ax2.grid(False)
    ax.set_xlabel("Publication year"); ax.set_ylabel("Citations to papers of that year")
    ax.set_title("Citations Over Time")
    ax.set_xticks(ann["year"])
    h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2, l1+l2, loc="upper left")
    fig.savefig(FIGS / "adv_citations_over_time.png"); plt.close(fig)


# ---------- journal / source intelligence ----------

def fig_rci_country():
    g = pd.read_csv(TABLES / "20_rci_country.csv").head(18)
    fig, ax = plt.subplots(figsize=(10.5, 7))
    colors = ["#2e7d32" if v >= 1 else "#c0504d" for v in g["rci"][::-1]]
    bars = ax.barh(g["country"][::-1], g["rci"][::-1], color=colors, edgecolor="white")
    ax.axvline(1.0, color="#333", lw=1.2, ls="--")
    ax.text(1.02, 0.5, "corpus average (1.0)", rotation=90, va="center",
            transform=ax.get_yaxis_transform(), fontsize=8, color="#333")
    for b, v, n in zip(bars, g["rci"][::-1], g["n_pubs"][::-1]):
        ax.text(v+0.02, b.get_y()+b.get_height()/2, f"{v:.2f}  (n={int(n)})",
                va="center", fontsize=8.5)
    ax.set_xlabel("Relative Citation Impact (age-normalised, corpus mean = 1.0)")
    ax.set_title("Relative Citation Impact by Country (min. 20 papers)")
    fig.savefig(FIGS / "adv_rci_country.png"); plt.close(fig)


def fig_source_bubble():
    g = pd.read_csv(TABLES / "21_source_bubble.csv")
    fig, ax = plt.subplots(figsize=(11, 7))
    sizes = (g["h_index"] / g["h_index"].max() * 900) + 40
    sc = ax.scatter(g["n_pubs"], g["total_citations"], s=sizes,
                    c=g["mean_citations"], cmap="viridis", alpha=0.75, edgecolors="white", linewidths=1)
    # Label the most notable sources
    notable = g.sort_values("total_citations", ascending=False).head(8)
    for _, r in notable.iterrows():
        ax.annotate(str(r["source"])[:32], (r["n_pubs"], r["total_citations"]),
                    fontsize=8, xytext=(5, 4), textcoords="offset points", color="#222")
    ax.set_xlabel("Number of publications")
    ax.set_ylabel("Total citations")
    ax.set_title("Source Metrics Bubble (bubble size = source h-index)")
    cb = plt.colorbar(sc, ax=ax, pad=0.02, shrink=0.75); cb.set_label("Mean citations / paper", fontsize=9)
    fig.savefig(FIGS / "adv_source_bubble.png"); plt.close(fig)


def fig_subject_areas():
    g = pd.read_csv(TABLES / "22_subject_areas.csv").head(15)
    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    norm = plt.Normalize(g["n_pubs"].min(), g["n_pubs"].max())
    crest = sns.color_palette("crest", as_cmap=True)
    colors = crest(norm(g["n_pubs"]))
    bars = ax.barh(g["research_area"][::-1], g["n_pubs"][::-1], color=colors[::-1], edgecolor="white")
    for b, v, p in zip(bars, g["n_pubs"][::-1], g["share_pct"][::-1]):
        ax.text(v+3, b.get_y()+b.get_height()/2, f"{int(v)} ({p:.1f}%)", va="center", fontsize=8.5)
    ax.set_xlabel("Number of publications (Web of Science research areas)")
    ax.set_title("Subject-Area Distribution")
    fig.savefig(FIGS / "adv_subject_areas.png"); plt.close(fig)


def fig_rising_sources():
    g = pd.read_csv(TABLES / "23_rising_sources.csv").head(12)
    g["short"] = g["source"].str.title().str.slice(0, 48)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.barh(g["short"][::-1], g["n_pubs"][::-1], color="#cdd9e5", edgecolor="white", label="Total (2015–2025)")
    ax.barh(g["short"][::-1], g["recent_pubs"][::-1], color=PALETTE[0], edgecolor="white", label="Recent (2023–2025)")
    for y, (tot, rec, sh) in enumerate(zip(g["n_pubs"][::-1], g["recent_pubs"][::-1], g["recent_share_pct"][::-1])):
        ax.text(tot+1, y, f"{int(rec)}/{int(tot)} ({sh:.0f}% recent)", va="center", fontsize=8)
    ax.set_xlabel("Number of publications")
    ax.set_title("Rising Sources (share of output in 2023–2025)")
    ax.legend(loc="lower right")
    fig.savefig(FIGS / "adv_rising_sources.png"); plt.close(fig)


# ---------- global coverage ----------

def _world():
    import geopandas as gpd
    import pyogrio  # noqa
    w = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    return w[w["name"] != "Antarctica"].copy()


def fig_world_map():
    g = pd.read_csv(TABLES / "24_country_counts.csv")
    world = _world()
    merged = world.merge(g[["iso3", "n_pubs"]], left_on="iso_a3", right_on="iso3", how="left")
    fig, ax = plt.subplots(figsize=(14, 7.2))
    world.plot(ax=ax, color="#eeeeee", edgecolor="white", linewidth=0.4)
    merged.dropna(subset=["n_pubs"]).plot(
        column="n_pubs", cmap="YlOrRd", ax=ax, edgecolor="white", linewidth=0.4,
        legend=True, scheme=None,
        legend_kwds={"label": "Publications", "shrink": 0.5},
        norm=plt.matplotlib.colors.LogNorm(vmin=max(1, g["n_pubs"].min()), vmax=g["n_pubs"].max()))
    ax.set_title("Global Distribution of Publications by Country", fontsize=14, fontweight="bold")
    ax.set_axis_off()
    fig.savefig(FIGS / "adv_world_map.png"); plt.close(fig)


def fig_rising_countries_map():
    g = pd.read_csv(TABLES / "25_rising_countries.csv")
    world = _world()
    merged = world.merge(g[["iso3", "recent_share_pct"]], left_on="iso_a3", right_on="iso3", how="left")
    fig, ax = plt.subplots(figsize=(14, 7.2))
    world.plot(ax=ax, color="#eeeeee", edgecolor="white", linewidth=0.4)
    merged.dropna(subset=["recent_share_pct"]).plot(
        column="recent_share_pct", cmap="Greens", ax=ax, edgecolor="white", linewidth=0.4,
        legend=True, legend_kwds={"label": "Share of output in 2023–2025 (%)", "shrink": 0.5})
    ax.set_title("Rising Countries (share of output published in 2023–2025)", fontsize=14, fontweight="bold")
    ax.set_axis_off()
    fig.savefig(FIGS / "adv_rising_countries_map.png"); plt.close(fig)


def fig_country_collab_pairs():
    e = pd.read_csv(TABLES / "09_country_collab_edges.csv").head(15)
    e["pair"] = e["country_a"] + " — " + e["country_b"]
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    bars = ax.barh(e["pair"][::-1], e["weight"][::-1], color=PALETTE[6], edgecolor="white")
    for b, v in zip(bars, e["weight"][::-1]):
        ax.text(v+0.5, b.get_y()+b.get_height()/2, f"{int(v)}", va="center", fontsize=9)
    ax.set_xlabel("Number of co-authored publications")
    ax.set_title("Top International Collaboration Pairs")
    fig.savefig(FIGS / "adv_country_collab_pairs.png"); plt.close(fig)


def fig_country_network():
    e = pd.read_csv(TABLES / "09_country_collab_edges.csv")
    cc = pd.read_csv(TABLES / "24_country_counts.csv")
    size_of = dict(zip(cc["country"], cc["n_pubs"]))
    G = nx.Graph()
    for _, r in e.iterrows():
        if r["weight"] >= 3:
            G.add_edge(r["country_a"], r["country_b"], weight=int(r["weight"]))
    if len(G) == 0:
        return
    # keep giant component
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    G = G.subgraph(comps[0]).copy()
    pos = nx.spring_layout(G, seed=7, k=1.4/math.sqrt(len(G)), iterations=120, weight="weight")
    sizes = [max(120, size_of.get(n, 5)*1.2) for n in G.nodes]
    comms = list(nx.algorithms.community.greedy_modularity_communities(G, weight="weight"))
    cmap = sns.color_palette("Set2", n_colors=max(len(comms), 3))
    color_of = {n: cmap[i % len(cmap)] for i, com in enumerate(comms) for n in com}
    fig, ax = plt.subplots(figsize=(13, 9))
    w = np.array([d["weight"] for *_, d in G.edges(data=True)], float)
    nx.draw_networkx_edges(G, pos, width=0.3+3*w/w.max(), alpha=0.3, edge_color="#5b6b73", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=[color_of.get(n,"#999") for n in G.nodes],
                           edgecolors="white", linewidths=1.1, alpha=0.95, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=9, ax=ax)
    ax.set_title(f"Country Co-authorship Network ({len(G)} countries, {G.number_of_edges()} links)",
                 fontsize=13, fontweight="bold")
    ax.set_axis_off()
    fig.savefig(FIGS / "adv_country_network.png"); plt.close(fig)


def fig_author_network():
    nodes = pd.read_csv(TABLES / "26_author_collab_nodes.csv")
    edges = pd.read_csv(TABLES / "26_author_collab_edges.csv")
    size_of = dict(zip(nodes["author"], nodes["n_pubs"]))
    G = nx.Graph()
    for _, r in edges.iterrows():
        if r["weight"] >= 2:
            G.add_edge(r["author_a"], r["author_b"], weight=int(r["weight"]))
    if len(G) == 0:
        return
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    # show components with >=3 authors to reveal research groups
    keep = set()
    for c in comps:
        if len(c) >= 3:
            keep |= c
    G = G.subgraph(keep).copy()
    if len(G) == 0:
        return
    pos = nx.spring_layout(G, seed=11, k=1.5/math.sqrt(len(G)), iterations=120, weight="weight")
    sizes = [max(80, size_of.get(n, 1)*45) for n in G.nodes]
    comms = list(nx.algorithms.community.greedy_modularity_communities(G))
    cmap = sns.color_palette("tab10", n_colors=max(len(comms), 3))
    color_of = {n: cmap[i % len(cmap)] for i, com in enumerate(comms) for n in com}
    fig, ax = plt.subplots(figsize=(13, 9.5))
    nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color="#888", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=[color_of.get(n,"#999") for n in G.nodes],
                           edgecolors="white", linewidths=1, alpha=0.95, ax=ax)
    # label only hubs to avoid clutter
    hub = {n for n in G.nodes if size_of.get(n,0) >= 6 or G.degree(n) >= 3}
    nx.draw_networkx_labels(G.subgraph(hub), pos, font_size=8, ax=ax)
    ax.set_title(f"Author Co-authorship Network — research clusters "
                 f"({len(G)} authors, {G.number_of_edges()} links)", fontsize=13, fontweight="bold")
    ax.set_axis_off()
    fig.savefig(FIGS / "adv_author_network.png"); plt.close(fig)


# ---------- conceptual structure ----------

def fig_thematic_map():
    g = pd.read_csv(TABLES / "27_thematic_map.csv")
    if g.empty:
        return
    fig, ax = plt.subplots(figsize=(10.5, 8.5))
    cx = g["centrality"].median(); cy = g["density"].median()
    sizes = (g["sum_freq"] / g["sum_freq"].max() * 4500) + 400
    colors = sns.color_palette("Set2", n_colors=len(g))
    ax.scatter(g["centrality"], g["density"], s=sizes, c=colors, alpha=0.65, edgecolors="#333", linewidths=1.2)
    for _, r in g.iterrows():
        ax.annotate(r["label"], (r["centrality"], r["density"]),
                    ha="center", va="center", fontsize=8.5, fontweight="bold", color="#222")
    ax.axvline(cx, color="#888", ls="--", lw=1); ax.axhline(cy, color="#888", ls="--", lw=1)
    pad_x = (g["centrality"].max()-g["centrality"].min())*0.15 + 1
    pad_y = (g["density"].max()-g["density"].min())*0.15 + 1
    ax.set_xlim(g["centrality"].min()-pad_x, g["centrality"].max()+pad_x)
    ax.set_ylim(g["density"].min()-pad_y, g["density"].max()+pad_y)
    # quadrant labels
    xhi, xlo = ax.get_xlim()[1], ax.get_xlim()[0]
    yhi, ylo = ax.get_ylim()[1], ax.get_ylim()[0]
    ax.text(xhi, yhi, "Motor themes", ha="right", va="top", fontsize=10, color="#777", style="italic")
    ax.text(xlo, yhi, "Niche themes", ha="left", va="top", fontsize=10, color="#777", style="italic")
    ax.text(xlo, ylo, "Emerging / declining", ha="left", va="bottom", fontsize=10, color="#777", style="italic")
    ax.text(xhi, ylo, "Basic / transversal", ha="right", va="bottom", fontsize=10, color="#777", style="italic")
    ax.set_xlabel("Centrality (degree of external interaction)")
    ax.set_ylabel("Density (degree of internal development)")
    ax.set_title("Thematic Map (Strategic Diagram of Author-Keyword Clusters)")
    fig.savefig(FIGS / "adv_thematic_map.png"); plt.close(fig)


def fig_rpys():
    g = pd.read_csv(TABLES / "30_rpys.csv")
    g = g[g["ref_year"] >= 1990]
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.fill_between(g["ref_year"], 0, g["n_refs"], color=PALETTE[0], alpha=0.25)
    ax.plot(g["ref_year"], g["n_refs"], color=PALETTE[0], lw=1.6, label="Cited references")
    ax2 = ax.twinx()
    ax2.plot(g["ref_year"], g["deviation"], color=PALETTE[1], lw=1.8,
             label="Deviation from 5-year median")
    ax2.axhline(0, color="#999", lw=0.8); ax2.grid(False)
    ax2.set_ylabel("Deviation from 5-year median", color=PALETTE[1])
    ax2.tick_params(axis="y", labelcolor=PALETTE[1])
    # Clip the deviation axis so the informative positive peaks remain visible
    # rather than being flattened by the steep drop at the most recent years.
    dev_hi = float(g["deviation"].max())
    ax2.set_ylim(-dev_hi * 1.3, dev_hi * 1.3)
    # mark peak years (largest positive deviation)
    peaks = g.nlargest(3, "deviation")
    for _, r in peaks.iterrows():
        ax.annotate(f"{int(r['ref_year'])}", (r["ref_year"], r["n_refs"]),
                    fontsize=9, fontweight="bold", color=PALETTE[1],
                    xytext=(0, 8), textcoords="offset points", ha="center")
    ax.set_xlabel("Cited reference publication year"); ax.set_ylabel("Number of cited references")
    ax.set_title("Reference Publication Year Spectroscopy (RPYS)")
    h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2, l1+l2, loc="upper left")
    fig.savefig(FIGS / "adv_rpys.png"); plt.close(fig)


def _ref_network(nodes_csv, edges_csv, a_col, b_col, label_col, title, outfile,
                 min_w, max_nodes=45, cmap_name="Set3"):
    nodes = pd.read_csv(TABLES / nodes_csv)
    edges = pd.read_csv(TABLES / edges_csv)
    G = nx.Graph()
    for _, r in edges.iterrows():
        if r["weight"] >= min_w:
            G.add_edge(r[a_col], r[b_col], weight=int(r["weight"]))
    if len(G) == 0:
        print(f"  (skip {outfile}: empty)")
        return
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    G = G.subgraph(comps[0]).copy()
    if len(G) > max_nodes:
        # keep highest-degree nodes
        keep = [n for n, _ in sorted(G.degree(weight="weight"), key=lambda x: -x[1])[:max_nodes]]
        G = G.subgraph(keep).copy()
    label_map = dict(zip(nodes.iloc[:, 0], nodes[label_col]))
    size_col = "citations" if "citations" in nodes.columns else nodes.columns[1]
    size_of = dict(zip(nodes.iloc[:, 0], nodes[size_col]))
    pos = nx.kamada_kawai_layout(G, weight="weight")
    sizes = [max(120, float(size_of.get(n, 1)))*1.0 for n in G.nodes]
    smax = max(sizes); sizes = [120 + 1500*(s/smax) for s in sizes]
    comms = list(nx.algorithms.community.greedy_modularity_communities(G, weight="weight"))
    cmap = sns.color_palette(cmap_name, n_colors=max(len(comms), 3))
    color_of = {n: cmap[i % len(cmap)] for i, com in enumerate(comms) for n in com}
    fig, ax = plt.subplots(figsize=(13.5, 10))
    w = np.array([d["weight"] for *_, d in G.edges(data=True)], float)
    nx.draw_networkx_edges(G, pos, width=0.3+2.5*w/w.max(), alpha=0.3, edge_color="#5b6b73", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes,
                           node_color=[color_of.get(n,"#999") for n in G.nodes],
                           edgecolors="white", linewidths=1.1, alpha=0.95, ax=ax)
    labels = {n: str(label_map.get(n, n))[:26] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7.5, ax=ax)
    ax.set_title(f"{title} ({len(G)} nodes, {G.number_of_edges()} links)",
                 fontsize=13, fontweight="bold")
    ax.set_axis_off()
    fig.savefig(FIGS / outfile); plt.close(fig)


def fig_cocitation():
    _ref_network("32_cocitation_nodes.csv", "32_cocitation_edges.csv",
                 "ref_a", "ref_b", "label",
                 "Co-Citation Network of Cited References",
                 "adv_cocitation.png", min_w=3, max_nodes=40, cmap_name="Set2")


def fig_coupling():
    _ref_network("33_coupling_nodes.csv", "33_coupling_edges.csv",
                 "doc_a", "doc_b", "label",
                 "Bibliographic Coupling Network of Documents",
                 "adv_coupling.png", min_w=4, max_nodes=45, cmap_name="Set3")


def fig_historiograph():
    import re as _re
    nodes = pd.read_csv(TABLES / "34_historiograph_nodes.csv")
    edges = pd.read_csv(TABLES / "34_historiograph_edges.csv")
    # Keep the most locally cited nodes to form a readable genealogy
    top = nodes.sort_values("local_citations", ascending=False).head(20)
    keep = set(top["doc_id"])
    e = edges[edges["cited_id"].isin(keep) & edges["citing_id"].isin(keep)]
    G = nx.DiGraph()
    for _, r in e.iterrows():
        G.add_edge(r["cited_id"], r["citing_id"])
    G.add_nodes_from(keep)

    def clean_name(lab):
        # strip a trailing "(year)" so it is not duplicated with the year line
        return _re.sub(r"\s*\(\d{4}\)\s*$", "", str(lab)).strip()

    info = {r["doc_id"]: (clean_name(r["label"]), int(r["year"]), int(r["local_citations"]))
            for _, r in top.iterrows()}
    # x = year; y = staggered slot within the year to reduce overlap
    years = {n: info[n][1] for n in G.nodes}
    order = sorted(G.nodes, key=lambda n: (years[n], -info[n][2]))
    ypos = {}
    per_year = {}
    for n in order:
        y = years[n]
        slot = per_year.get(y, 0)
        ypos[n] = slot
        per_year[y] = slot + 1
    pos = {n: (years[n], ypos[n]) for n in G.nodes}

    fig, ax = plt.subplots(figsize=(15, 9.5))
    lc = [info[n][2] for n in G.nodes]
    sizes = [350 + 130*c for c in lc]
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.45, edge_color="#999",
                           arrows=True, arrowstyle="-|>", arrowsize=13,
                           node_size=sizes, connectionstyle="arc3,rad=0.12")
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=lc, cmap="YlOrRd",
                           edgecolors="#333", linewidths=1, ax=ax)
    labels = {n: f"{info[n][0][:14]}\n{info[n][1]}" for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7.5, ax=ax)
    ax.set_title("Historiograph of Within-Corpus Direct Citations "
                 f"({G.number_of_nodes()} key papers, {G.number_of_edges()} citation links)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Publication year")
    ax.margins(x=0.08, y=0.12)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIGS / "adv_historiograph.png"); plt.close(fig)


def main():
    print("Rendering advanced figures...")
    fig_annual_pubs_citations(); print("  annual pubs+citations")
    fig_lifecycle();             print("  lifecycle")
    fig_citations_over_time();   print("  citations over time")
    fig_rci_country();           print("  RCI country")
    fig_source_bubble();         print("  source bubble")
    fig_subject_areas();         print("  subject areas")
    fig_rising_sources();        print("  rising sources")
    fig_world_map();             print("  world map")
    fig_rising_countries_map();  print("  rising countries map")
    fig_country_collab_pairs();  print("  country collab pairs")
    fig_country_network();       print("  country network")
    fig_author_network();        print("  author network")
    fig_thematic_map();          print("  thematic map")
    fig_rpys();                  print("  RPYS")
    fig_cocitation();            print("  co-citation")
    fig_coupling();              print("  coupling")
    fig_historiograph();         print("  historiograph")
    n = len(list(FIGS.glob("adv_*.png")))
    print(f"Done. {n} advanced figures in {FIGS}")


if __name__ == "__main__":
    main()
