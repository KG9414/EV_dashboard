"""
Kalibracija parametrov eksponentne porazdelitve trajanj poti na slovensko statistiko.

POPRAVEK (ta verzija): prejšnja verzija te skripte je uporabljala napačen cilj
(13 min), ki je bil pomotoma zamenjan s razdaljo (13,8 km). Neodvisno preverjeno
prek dveh uradnih SURS sporočil (stat.si) je pravi cilj 23 min (2021) / 24 min
(2025) — ne 13 min.

Vir SI (neposredno preverjeno, ne le citirano):
  - "Dnevna mobilnost potnikov, 2021" — stat.si/StatWeb/News/Index/10324
    Povprečno trajanje poti: 23 min
    Povprečna razdalja poti: 13,8 km   (= isto, kar citira Golubović, 2025, tabela 1)
    Povprečno število poti na dan: 2,2
  - "Dnevna mobilnost potnikov, 2025" — stat.si/StatWeb/News/Index/14062
    Povprečno trajanje poti: 24 min
    Povprečna razdalja poti: 14,4 km
    Povprečno število poti na dan: 2,3

Uporabljamo 2021 podatke (23 min, 13,8 km), ker isto leto/vir uporablja tudi
Golubović (2025) za svojo validacijo razdalje (tabela 1) — tako je trajanje in
razdalja interno usklajena na isti referenčni vir.

NHTS (obstoječi surovi params):
  trip_duration_params = [5.0, 18.90741191528791]
  Povprečje = loc + scale = 5.0 + 18.9 ≈ 23,9 min  ← že zelo blizu SI cilju!

Metoda:
  Eksponentna porazdelitev s premikom (shifted exponential), OMEJENA na [0,60]
  min in diskretizirana na 1000 točk (enako kot dejanska implementacija v
  Step_1_prod.py: np.random.choice(x_axis_trips, p=trips_distribution/sum(...))).

  POMEMBNO: zaradi odsekanja pri 60 min analitična formula (povprečje = loc +
  scale) NE velja več natančno — odsekani del repa (predvsem pri večjem scale)
  sistematično zniža dejansko povprečje. Pravi scale je zato poiskan numerično
  (bisekcija), ne izračunan analitično. Razlika je majhna pri scale~8
  (12,96 vs 13,0 analitično), a velika pri scale~18-19 (20,3-20,75 vs 23-23,9
  analitično — razlika ~10-12 %), zato je numerična korekcija nujna za pravilen
  rezultat.
"""

import numpy as np
import matplotlib.pyplot as plt

# --- SURS referenčne vrednosti (2021, neposredno preverjeno) ---
SURS_MEAN_DURATION_MIN = 23.0   # povprečno trajanje poti v SI [min]
SURS_MEAN_TRIPS_PER_DAY = 2.2   # povprečno število poti na dan
SURS_MEAN_DIST_KM = 13.8        # povprečna dolžina poti [km]

X_MAX = 60.0
N_GRID = 1000


def _discretized_mean(loc, scale, xmax=X_MAX, n=N_GRID):
    """Resnično povprečje porazdelitve PO odsekanju pri xmax in diskretizaciji
    na n točk — enako, kar dejansko vzorči np.random.choice v Step_1_prod.py."""
    x = np.linspace(0, xmax, n)
    d = (1 / scale) * np.exp(-(x - loc) / scale)
    d[x < loc] = 0
    d = d / d.sum()
    return float((x * d).sum())


def _solve_scale_for_mean(loc, target_mean, lo=1.0, hi=200.0, iters=80):
    """Bisekcija: poišče scale, da je _discretized_mean(loc, scale) == target_mean."""
    for _ in range(iters):
        mid = (lo + hi) / 2
        if _discretized_mean(loc, mid) < target_mean:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# --- Obstoječi NHTS parametri ---
LOC_NHTS = 5.0
SCALE_NHTS = 18.90741191528791
MEAN_NHTS_ANALITICNO = LOC_NHTS + SCALE_NHTS          # ≈ 23.9 min (NEpravilno po odsekanju)
MEAN_NHTS = _discretized_mean(LOC_NHTS, SCALE_NHTS)   # resnično povprečje po odsekanju

# --- SI kalibracija (numerično poiskan scale, ne analitičen mean-loc) ---
LOC_SI = 5.0
SCALE_SI = _solve_scale_for_mean(LOC_SI, SURS_MEAN_DURATION_MIN)
MEAN_SI = _discretized_mean(LOC_SI, SCALE_SI)  # ✓ resnično ujema SURS cilju

print("=" * 60)
print("KALIBRACIJA TRAJANJ POTI — NHTS → SI (popravljena verzija)")
print("=" * 60)
print(f"\nNHTS parametri (obstoječi):")
print(f"  loc   = {LOC_NHTS:.1f} min")
print(f"  scale = {SCALE_NHTS:.4f}")
print(f"  mean  = {MEAN_NHTS:.1f} min")
print(f"\nSI kalibrirani parametri:")
print(f"  loc   = {LOC_SI:.1f} min")
print(f"  scale = {SCALE_SI:.4f}")
print(f"  mean  = {MEAN_SI:.1f} min")
print(f"\nSURS referenca (2021, stat.si): {SURS_MEAN_DURATION_MIN:.1f} min")
print(f"NHTS surovo povprečje PO odsekanju/diskretizaciji: {MEAN_NHTS:.2f} min "
      f"(analitično brez odsekanja bi bilo {MEAN_NHTS_ANALITICNO:.1f} min — odsekanje pri 60 min "
      f"zniža povprečje za {MEAN_NHTS_ANALITICNO - MEAN_NHTS:.2f} min)")
print(f"Razlika NHTS (resnično) vs SI cilj: {abs(MEAN_NHTS - SURS_MEAN_DURATION_MIN):.2f} min "
      f"({abs(MEAN_NHTS - SURS_MEAN_DURATION_MIN)/SURS_MEAN_DURATION_MIN*100:.1f} %)")

# --- Validacija z vzorčenjem ---
np.random.seed(42)
N = 100_000
x_axis = np.linspace(0, 60, 1000)

# NHTS distribucija
dist_nhts = (1 / SCALE_NHTS) * np.exp(-(x_axis - LOC_NHTS) / SCALE_NHTS)
dist_nhts[x_axis < LOC_NHTS] = 0
dist_nhts /= dist_nhts.sum()
samples_nhts = np.random.choice(x_axis, size=N, p=dist_nhts)

# SI distribucija
dist_si = (1 / SCALE_SI) * np.exp(-(x_axis - LOC_SI) / SCALE_SI)
dist_si[x_axis < LOC_SI] = 0
dist_si /= dist_si.sum()
samples_si = np.random.choice(x_axis, size=N, p=dist_si)

print(f"\nValidacija ({N} vzorcev):")
print(f"  NHTS generirano povprečje: {samples_nhts.mean():.2f} min (surovo, brez kalibracije)")
print(f"  SI   generirano povprečje: {samples_si.mean():.2f} min (cilj 23,0 min ✓)")
print(f"  SI   mediana:              {np.median(samples_si):.2f} min")
print(f"  SI   P90:                  {np.percentile(samples_si, 90):.2f} min")

# --- Primerljiva tabela (kot Golubović, tabela 1) ---
print(f"\nPrimerjava s SURS (2021):")
print(f"{'':30s} {'SURS':>10s} {'NHTS':>10s} {'SI-kalib.':>10s}")
print(f"{'Povprečno trajanje poti [min]':30s} {SURS_MEAN_DURATION_MIN:>10.1f} {MEAN_NHTS:>10.1f} {MEAN_SI:>10.1f}")
print(f"{'Spodnja meja [min]':30s} {'5':>10s} {LOC_NHTS:>10.1f} {LOC_SI:>10.1f}")
print(f"\nImplicirana hitrost (13,8 km / {SURS_MEAN_DURATION_MIN:.0f} min): "
      f"{13.8 / (SURS_MEAN_DURATION_MIN/60):.1f} km/h  (realistično za lokalno cestno mrežo)")

# --- Graf ---
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].plot(x_axis, dist_nhts / dist_nhts.max(), label=f'NHTS (mean={MEAN_NHTS:.1f} min)', color='steelblue')
axes[0].plot(x_axis, dist_si / dist_si.max(), label=f'SI-kalib. (mean={MEAN_SI:.1f} min)', color='tomato')
axes[0].axvline(MEAN_NHTS, color='steelblue', linestyle='--', alpha=0.7)
axes[0].axvline(MEAN_SI, color='tomato', linestyle='--', alpha=0.7)
axes[0].axvline(SURS_MEAN_DURATION_MIN, color='green', linestyle=':', linewidth=2, label=f'SURS cilj ({SURS_MEAN_DURATION_MIN} min)')
axes[0].set_xlabel('Trajanje poti [min]')
axes[0].set_ylabel('Normalizirana gostota')
axes[0].set_title('Porazdelitev trajanj: NHTS vs SI-kalibrirana')
axes[0].legend()
axes[0].set_xlim(0, 60)

axes[1].hist(samples_nhts, bins=50, density=True, alpha=0.5, color='steelblue', label=f'NHTS (mean={samples_nhts.mean():.1f} min)')
axes[1].hist(samples_si, bins=50, density=True, alpha=0.5, color='tomato', label=f'SI (mean={samples_si.mean():.1f} min)')
axes[1].axvline(SURS_MEAN_DURATION_MIN, color='green', linestyle=':', linewidth=2, label='SURS cilj')
axes[1].set_xlabel('Trajanje poti [min]')
axes[1].set_ylabel('Gostota')
axes[1].set_title('Vzorčene vrednosti (N=100k)')
axes[1].legend()
axes[1].set_xlim(0, 60)

plt.tight_layout()
plt.savefig('si_duration_calibration.png', dpi=150, bbox_inches='tight')
print("\nGraf shranjen: si_duration_calibration.png")

print("\n" + "=" * 60)
print("PRIPOROČENI PARAMETRI ZA Step_1_prod.py:")
print("=" * 60)
print(f"trip_duration_params = np.array([{LOC_SI:.1f}, {SCALE_SI:.1f}])")
print(f"# loc={LOC_SI} min, scale={SCALE_SI} min → mean={MEAN_SI} min ≈ SURS 2021 ({SURS_MEAN_DURATION_MIN} min)")
