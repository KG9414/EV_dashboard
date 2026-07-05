"""
Velenje vs. Krško — prebivalstvo, površina, gostota (SURS, stat.si/obcine).
Vir: https://www.stat.si/obcine/en/Municip/Index/190 (Velenje, mid-2023)
     https://www.stat.si/obcine/en/Municip/Index/75  (Krško, mid-2024)
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(HERE, "velenje_krsko_demografija.png")

CITIES = ["Velenje", "Krško"]
POPULATION = [33680, 26070]      # občina, prebivalci
AREA_KM2 = [84, 287]             # občina, km²
DENSITY = [401, 91]              # preb./km²
NATIONAL_AVG_DENSITY = 105

COLOR_V = "#1f77b4"
COLOR_K = "#d62728"
COLORS = [COLOR_V, COLOR_K]

fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
fig.suptitle(
    "Velenje vs. Krško (občina) — prebivalstvo, površina, gostota\n"
    "Vir: SURS, Slovenske regije in občine v številkah (stat.si/obcine), Velenje sredina 2023, Krško sredina 2024",
    fontsize=11, fontweight="bold"
)

# Panel 1: Population
ax = axes[0]
bars = ax.bar(CITIES, POPULATION, color=COLORS, alpha=0.85)
ax.set_title("Prebivalstvo občine", fontsize=10)
ax.set_ylabel("Število prebivalcev")
for b, v in zip(bars, POPULATION):
    ax.text(b.get_x() + b.get_width()/2, v + 500, f"{v:,}", ha="center", fontsize=9)
ax.set_ylim(0, max(POPULATION) * 1.18)

# Panel 2: Area
ax = axes[1]
bars = ax.bar(CITIES, AREA_KM2, color=COLORS, alpha=0.85)
ax.set_title("Površina občine", fontsize=10)
ax.set_ylabel("km²")
for b, v in zip(bars, AREA_KM2):
    ax.text(b.get_x() + b.get_width()/2, v + 6, f"{v} km²", ha="center", fontsize=9)
ax.set_ylim(0, max(AREA_KM2) * 1.18)

# Panel 3: Density (with national average reference line)
ax = axes[2]
bars = ax.bar(CITIES, DENSITY, color=COLORS, alpha=0.85)
ax.axhline(NATIONAL_AVG_DENSITY, color="gray", linestyle="--", linewidth=1.5,
           label=f"Slovensko povprečje ({NATIONAL_AVG_DENSITY}/km²)")
ax.set_title("Gostota poselitve", fontsize=10)
ax.set_ylabel("preb./km²")
for b, v in zip(bars, DENSITY):
    ax.text(b.get_x() + b.get_width()/2, v + 10, f"{v}/km²", ha="center", fontsize=9)
ax.legend(fontsize=8, loc="upper right")
ax.set_ylim(0, max(DENSITY) * 1.25)

for ax in axes:
    ax.grid(axis="y", alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
print(f"Figure saved -> {OUT_PNG}")
