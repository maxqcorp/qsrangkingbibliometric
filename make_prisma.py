"""
Generate the PRISMA 2020-style flow diagram for the identification stage of
the bibliometric corpus assembly.

Covers identification through year filtering and deduplication to the final
4,261 unique records used in the bibliometric analysis. Title/abstract
screening and full-text eligibility are noted as the next stages of the SLR.

Output: bibliometric_analysis/figures/fig00_prisma.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

WORKSPACE = Path(__file__).resolve().parent    # the workspace (folder holding this script)
ROOT = WORKSPACE.parent
OUT = WORKSPACE / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---- numbers from harmonisation step ----
N_WOS = 2069
N_SCOPUS = 4040
N_RAW = N_WOS + N_SCOPUS              # 6,109
N_AFTER_YEAR = 6067                   # year filter 2015 to 2025
N_EXCLUDED_YEAR = N_RAW - N_AFTER_YEAR   # 42
N_FINAL = 4261
N_DUPLICATES = N_AFTER_YEAR - N_FINAL    # 1,806
N_BOTH = 1802
N_WOS_ONLY = 225
N_SCOPUS_ONLY = 2234

# ---- visual style ----
BLUE = "#1F4E79"
LIGHT_BLUE = "#DAE6F1"
ORANGE = "#C97A1B"
LIGHT_ORANGE = "#FDEBD0"
GREEN = "#2E7D32"
LIGHT_GREEN = "#CFE2D6"
GRAY_TEXT = "#2c2c2c"
ARROW_COLOR = "#444444"


def box(ax, x, y, w, h, title, body=None, fc=LIGHT_BLUE, ec=BLUE,
        title_fs=11, body_fs=10):
    ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h,
                                boxstyle="round,pad=0.005,rounding_size=0.012",
                                fc=fc, ec=ec, lw=1.4))
    if body is None:
        ax.text(x, y, title, ha="center", va="center",
                fontsize=title_fs, color=BLUE, fontweight="bold",
                wrap=True)
    else:
        ax.text(x, y + 0.018, title, ha="center", va="center",
                fontsize=title_fs, color=BLUE, fontweight="bold")
        ax.text(x, y - 0.024, body, ha="center", va="center",
                fontsize=body_fs, color=GRAY_TEXT, linespacing=1.35)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                  arrowstyle="-|>", mutation_scale=16,
                                  color=ARROW_COLOR, lw=1.4,
                                  connectionstyle="arc3,rad=0.0"))


def band_label(ax, y_top, y_bot, label):
    """Vertical phase label on the left margin."""
    h = y_top - y_bot
    y_mid = (y_top + y_bot) / 2
    ax.add_patch(mpatches.Rectangle((0.005, y_bot), 0.045, h,
                                     fc=BLUE, ec="none"))
    ax.text(0.0275, y_mid, label,
            ha="center", va="center",
            color="white", fontsize=11, fontweight="bold", rotation=90)


def main():
    fig, ax = plt.subplots(figsize=(13.5, 12))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()

    # Title
    ax.text(0.5, 0.965,
            "PRISMA 2020 Flow Diagram",
            ha="center", va="center",
            fontsize=15, fontweight="bold", color=BLUE)
    ax.text(0.5, 0.935,
            "Identification of Studies for the Bibliometric Analysis "
            "(Web of Science and Scopus, 2015 to 2025)",
            ha="center", va="center",
            fontsize=11, color=GRAY_TEXT, style="italic")

    # --- Phase labels (left margin) ---
    band_label(ax, 0.90, 0.62, "Identification")
    band_label(ax, 0.60, 0.32, "Screening")
    band_label(ax, 0.30, 0.06, "Included")

    # --- Identification phase ---
    # Two top boxes (database sources)
    box(ax, 0.30, 0.84, 0.34, 0.085,
        "Records identified from",
        f"Web of Science Core Collection\n(n = {N_WOS:,})")
    box(ax, 0.70, 0.84, 0.34, 0.085,
        "Records identified from",
        f"Scopus\n(n = {N_SCOPUS:,})")

    # Merge box
    box(ax, 0.40, 0.71, 0.42, 0.075,
        "Total records identified",
        f"(n = {N_RAW:,})")

    # Year-filter exclusion (right side)
    box(ax, 0.80, 0.71, 0.32, 0.075,
        "Records excluded",
        f"Outside year window 2015 to 2025\n(n = {N_EXCLUDED_YEAR})",
        fc=LIGHT_ORANGE, ec=ORANGE)

    # --- Screening phase ---
    # After year filter
    box(ax, 0.40, 0.555, 0.42, 0.075,
        "Records after year filter",
        f"(n = {N_AFTER_YEAR:,})")

    # Duplicates exclusion (right side)
    box(ax, 0.80, 0.555, 0.32, 0.085,
        "Duplicates removed",
        f"Matched by DOI or by\nnormalised title\n(n = {N_DUPLICATES:,})",
        fc=LIGHT_ORANGE, ec=ORANGE)

    # Unique records
    box(ax, 0.40, 0.40, 0.42, 0.075,
        "Unique records after deduplication",
        f"(n = {N_FINAL:,})")

    # Provenance breakdown (informational, on left side of unique-records box)
    box(ax, 0.80, 0.40, 0.32, 0.105,
        "Database provenance",
        f"Indexed in both: {N_BOTH:,} ({N_BOTH/N_FINAL*100:.1f}%)\n"
        f"WoS only: {N_WOS_ONLY} ({N_WOS_ONLY/N_FINAL*100:.1f}%)\n"
        f"Scopus only: {N_SCOPUS_ONLY:,} ({N_SCOPUS_ONLY/N_FINAL*100:.1f}%)",
        fc="white", ec=BLUE)

    # --- Included phase ---
    # Final inclusion (bibliometric analysis)
    box(ax, 0.40, 0.21, 0.52, 0.085,
        "Records included in bibliometric analysis",
        f"(n = {N_FINAL:,})",
        fc=LIGHT_GREEN, ec=GREEN, title_fs=12, body_fs=11)

    # (footer note removed per review: keep the diagram clean)

    # ---- arrows ----
    # WoS -> merge
    arrow(ax, 0.30, 0.7975, 0.34, 0.7475)
    # Scopus -> merge
    arrow(ax, 0.70, 0.7975, 0.46, 0.7475)
    # merge -> after year filter
    arrow(ax, 0.40, 0.6725, 0.40, 0.5925)
    # merge -> year-filter exclusion (lateral)
    arrow(ax, 0.61, 0.71, 0.64, 0.71)
    # after year filter -> unique
    arrow(ax, 0.40, 0.5175, 0.40, 0.4375)
    # after year filter -> duplicates exclusion (lateral)
    arrow(ax, 0.61, 0.555, 0.64, 0.555)
    # unique -> provenance (lateral)
    arrow(ax, 0.61, 0.40, 0.64, 0.40)
    # unique -> final
    arrow(ax, 0.40, 0.3625, 0.40, 0.2525)

    plt.tight_layout()
    plt.savefig(OUT / "fig00_prisma.png", dpi=300, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT/'fig00_prisma.png'}")


if __name__ == "__main__":
    main()
