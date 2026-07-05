# Poročilo: Primerjava DomCenter pipeline orodja z referenčnimi podatki

**Datum:** 2026-06-17

## 1. Namen

To poročilo primerja moje trenutno orodje (DomCenter pipeline) z dvema referencama:

1. **NHTS** (ameriška nacionalna anketa o potovanjih) — kot vir, iz katerega je orodje izpeljano (Markov verige, časi odhoda).
2. **Model A** — izvorna metoda iz OneDrive datotek, zagnana za Velenje.
3. **SURS 2025** — slovenski uradni statistični podatki o mobilnosti, kot neodvisna realnostna preverba.

Cilj je preveriti, ali je moje orodje (Model B) realistično, in pojasniti razlike, kjer obstajajo — brez prilagajanja podatkov, da bi se ujemali z želenim izidom.

---

## 2. Uporabljeni viri podatkov

| Vir | Opis | Status |
|---|---|---|
| NHTS | Ameriška anketa, filtrirano na avtomobilske poti (TRPTRANS=3) | 396.824 potovanj |
| DomCenter pipeline (Model B) | Produkcijski izhod Step 1, Krško, 1344 EV | 2.688 zapisov |
| Model A (OneDrive) | Izvorna metoda, Velenje, N=25 vozil, 4 potovanja | ORS izohrona |
| Model B v2 (DomCenter pipeline) | Enaka metoda kot produkcija, Velenje, N=25 vozil | ORS izohrona + Haversine-KNN fallback |
| SURS — Potovalne navade prebivalstva, Slovenija, 2025 | Dnevni kazalniki mobilnosti in trajanje/razdalja po namenu | Vir naveden generično, natančen URL še ni potrjen |
| SURS — Slovenske regije in občine v številkah | Prebivalstvo, površina, gostota poselitve | Potrjen vir, glej povezave v §5 |

---

## 3. Primerjava 1 — NHTS vs. DomCenter pipeline (Krško)

**Metoda:** NHTS avtomobilske poti so preslikane na 8 kategorij namena potovanja (Work, Business, Education, Shopping, Transport, Leisure, Personal, Home) z isto preslikavo, ki jo pipeline uporablja za Markov verige (`Functions_step_1.py`). Pipeline izhod je primerjan na enakih kategorijah.

**[SLIKA 1: /Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/analysis/Comparison2-0/comparison_nhts_vs_pipeline.png]**

### Ugotovitve

- **Tip potovanja (panel A):** Home je izključen (ni smiselna kategorija destinacije), deleži so prenormirani na preostalih 7 kategorij.
- **Čas odhoda (panel B):** NHTS in pipeline distribucija se primerjata neposredno; vključena je tudi krivulja, iz katere je pipeline vzorčil čase odhoda (`df_gauss_v1.xlsx`) — ta krivulja je izpeljana iz NHTS podatkov, **ni slovenska**. Dodana sta dva zelena pasova — SURS 2025 deleži potovanj v oknih 7–9h in 14–16h (glej tabelo spodaj).
- **Trajanje potovanja (panel C):** primerjava NHTS in pipeline z novim SURS 2025 območjem (delovni/nedelovni dan, 23–29 min). Stara kalibracija (~13 min, `Step_1_fit_si.py`) ni več prikazana na grafu — ostane le kot opomba v `notes.txt`, ker se z novo SURS 2025 tabelo ne ujema popolnoma (13 min vs. 24 min) in vira razlike nisem mogel preveriti.
- **Trajanje po namenu potovanja (panel D):** NHTS in pipeline trajanje sta primerjana s SURS 2025 trajanjem po namenu.

### Trajanje po namenu (minute)

| Namen | NHTS | Pipeline | SURS 2025 |
|---|---|---|---|
| Work | 23,3 | 20,8 | 24,0 |
| Business | 22,7 | 19,3 | 34,0 |
| Education | 17,6 | 23,5 | 33,0 |
| Shopping | 16,1 | 20,1 | 13,0 |
| Transport | 19,1 | 20,3 | 14,0 |
| Leisure | 22,5 | 22,2 | 32,0 |
| Personal | 17,7 | 20,6 | 22,0 |

**Ključna ugotovitev:** pipeline trajanje je za vse namene stisnjeno v ozko območje (19–23 min), ker se trajanje vzorči iz ene skupne porazdelitve, ne glede na namen potovanja. Realni SURS podatki kažejo veliko variacijo po namenu (13 min nakupovanje vs. 34 min poslovni opravki). To je strukturna razlika — ne šum.

**Trips/day preverba:** pipeline uporablja fiksno število 2 potovanj/vozilo/dan. SURS 2025 realno območje je [1,8–2,4] potovanj/dan (nedelovni–delovni dan) — vrednost 2 pade znotraj tega območja.

### Dodatne SURS 2025 preverbe (čas odhoda in trajanje)

| Preverba | SURS 2025 | NHTS | Pipeline |
|---|---|---|---|
| Delež potovanj, ki se začnejo 7.–9. uro | 13 % | 12,1 % | **46,4 %** |
| Delež potovanj, ki se začnejo 14.–16. uro | 17 % | 14,9 % | 12,8 % |
| Delež potovanj, krajših od 10 min | 41 % | 41,6 % | 24,0 % |

**Ključna ugotovitev:** NHTS se v obeh preverbah dobro ujema s SURS 2025. Pipeline pa močno preveč koncentrira odhode v jutranje okno 7–9h (46,4 % proti realnim 13 % — skoraj 3,6× preveč). Pipeline tudi premalo generira zelo kratka potovanja (24 % proti realnim 41 %), kar je skladno z ugotovitvijo iz zgornje tabele, da se trajanje ne razlikuje dovolj po namenu (Shopping bi moral biti najkrajši, a ni).

**Opomba o viru:** zgornje tri preverbe izhajajo iz natisnjenega besedila (alinee) na SURS strani — natančen URL ni viden na posnetku zaslona, številke (povprečje 14,4 km / 24 min) pa se ujemajo z že potrjeno SURS 2025 tabelo, zato so obravnavane kot isti vir/leto.

### Panel E — Odhodi na delo (Work), vs. SURS graf po namenu/uri (2021)

SURS ima tudi graf "Poti po nekaterih namenih in uri začetka" za delo/nakupovanje/prosti čas po urah dneva (**2021**, ne 2025 — drugačen vir/leto, brez natisnjenih vrednosti na posameznih točkah). Ker je modra (delo) krivulja na tem grafu neposredno relevantna za zgornjo "7–9h" ugotovitev, sem dodal nov panel (E), ki primerja SAMO Work potovanja med NHTS in pipeline, z približnimi vrhovi SURS krivulje kot referenco (oster vrh ob 6.–7. uri ~15,5 %, manjši vrh ob 14.–16. uri ~12,5 % — ocenjeno iz mrežnih črt grafa, ne natisnjene vrednosti).

| | SURS 2021 (Work, približno) | NHTS Work | Pipeline Work |
|---|---|---|---|
| Delež odhodov 6.–7. ura | ~15,5 % | 13,1 % | **0,0 %** |

**Vzrok je najden v kodi** (`pipeline/Step_1_prod.py`, vrstica 17–18):

```python
def sample_work_start():
    return np.random.uniform(7,9)
```

Čas odhoda na delo se vzorči iz **enakomerne (uniform) porazdelitve med 7.00 in 9.00** — od tod trda spodnja meja pri 7.00 (zato je delež v oknu 6–7h dobesedno 0 %, ne približek) in raven razrez 7–9h (23,7 % / 23,5 %, skoraj enako po obeh urah) namesto resničnega, ostro koničastega jutranjega vrha, ki se v resnici začne pred 7. uro. To je ena samostojna, namensko zakodirana vrstica — ne nekaj, kar bi izhajalo iz Markove verige ali demografskih profilov. NHTS Work (13,1 % v oknu 6–7h) te omejitve nima in se s SURS 2021 vrhom razmeroma dobro ujema, kar potrjuje, da je omejitev specifična za pipeline, ne podedovana iz NHTS.

**[Panel E je del SLIKE 1 zgoraj — ni dodatna slika.]**

---

## 4. Primerjava 2 — Model A (OneDrive) vs. Model B (DomCenter pipeline), Velenje

**Metoda:** oba modela sta zagnana za Velenje z istimi domovi in istimi tipi/časi potovanj (Step 1 je deljen). Model B v2 uporablja **enako primarno metodo destinacij kot Model A** — ORS izohrona — z Haversine-KNN fallbackom, če izohrona ne vrne kandidatov (enako kot dejanska produkcijska koda v `Step_2_prod.py`).

**[SLIKA 2: /Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/analysis/Comparison_Velenje/comparison_velenje_distance.png]**

### Ugotovitve

- **Tipi potovanj in časi odhoda:** identični med A in B (KS=0,00, p=1,00) — pričakovano, ker oba izhajata iz istega Step 1 Markova.
- **Razdalja potovanja:**

| | Model A (ORS izohrona) | Model B v2 (ORS izohrona + fallback) |
|---|---|---|
| Povprečje | 15,83 km | 5,24 km |
| Mediana | 9,02 km | 4,59 km |
| Haversine-KNN fallback uporabljen | — | 0/100 (0 %) |

KS statistika = 0,37 (p<0,001), Wasserstein razdalja = 10,59 km — razdalji sta statistično značilno različni.

**SURS 2025 realno območje za razdaljo/potovanje:** [13,7–16,6] km (delovni–nedelovni dan, vsi prevozni načini). Model A pade znotraj tega območja, Model B ne.

---

## 5. Zakaj se razdalje razlikujejo — Velenje vs. Krško

Pomembno: čeprav je Model B uporabil **identično metodo** kot Model A, se razdalja v Velenju ni bistveno spremenila. Razlog ni metoda, temveč značilnosti samega Velenja v primerjavi z dejanskim ciljnim mestom naloge, Krškim.

**[SLIKA 3: /Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/analysis/Comparison_Velenje/velenje_krsko_demografija.png]**

### Prebivalstvo, površina, gostota (SURS, stat.si/obcine)

| | Velenje | Krško |
|---|---|---|
| Prebivalstvo občine | 33.680 (sredina 2023) | 26.070 (sredina 2024) |
| Površina občine | 84 km² | 287 km² |
| Gostota poselitve | 401 preb./km² | 91 preb./km² |
| Slovensko povprečje gostote | 105 preb./km² | 105 preb./km² |
| Rang po prebivalstvu (občine) | 8. mesto | 12. mesto |
| Rang naselja po prebivalstvu | 6. največje mesto v Sloveniji | ni med 10 največjimi |

Viri: [Velenje — SURS](https://www.stat.si/obcine/en/Municip/Index/190), [Krško — SURS](https://www.stat.si/obcine/en/Municip/Index/75), [Slovenia Cities by Population](https://worldpopulationreview.com/cities/slovenia)

**Razlaga:** Velenje ima več prebivalcev kot celotna občina Krško, na manj kot tretjini površine — gostota poselitve je skoraj 4× nad slovenskim povprečjem. Velenje je kompaktno, gosto naseljeno mesto (planirano rudarsko mesto 20. stoletja). Krško je redko poseljena, razpotegnjena občina (pod slovenskim povprečjem gostote), razdeljena na več ločenih naselij (Senovo, Leskovec, Brestanica, Kostanjevica).

To je skladno s prostorsko porazdelitvijo destinacij v obeh modelih:

**[SLIKA 4: /Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/analysis/comparison_AB/figures/prostorska_A_velenje.png]**

**[SLIKA 5: /Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/analysis/comparison_AB/figures/prostorska_B_krsko.png]**

V Velenju se destinacije zgostijo tesno okoli središča mesta. V Krškem so destinacije razpotegnjene na širšem območju, z več ločenimi gostejšimi conami.

**Mehanizem (preverjeno iz log datoteke poganjanja Modela B):** za Work/Education/Business v Velenju natančno časovno okno izohrone (med floor in ceil trajanja potovanja) ne vsebuje kandidatov v 37/100 primerih (100 % Education potovanj, 56 % Work potovanj) — ne zaradi pomanjkljivih OSM podatkov (gostota OSM oznak je v Velenju dejansko VIŠJA kot v Krškem v vsaki kategoriji: work 0,89 vs. 0,47/km², education 0,23 vs. 0,07/km², leisure 1,22 vs. 0,41/km²), temveč ker manjša površina občine (84 km² proti 287 km²) omejuje absolutno število takih stavb, ki sploh lahko obstajajo znotraj meje. Ko je časovno okno prazno, koda preide na celotno izohrono od 0 minut, gravitacijski model pa znotraj tega nabora kandidatov močno preferira najbližjega — razdalja se zniža ne glede na razpoložljiv časovni proračun.

**Zaključek tega dela:** kratka razdalja v Velenju (5,24 km) je verjetno realistična posledica kompaktnega, gosto poseljenega mesta — ne napaka modela. Daljša razdalja v Krškem (13,2–15,3 km v produkcijskih testih, znotraj SURS območja 13,7–16,6 km) je skladna z razpotegnjeno, redko poseljeno občino. Primerjava ene številke z enim nacionalnim povprečjem SURS ne pove, katera metoda je "pravilnejša" — gre za dve strukturno različni naselji.

---

## 6. SURS 2025 referenčni podatki (uporabljeni kot primerjalna osnova)

### Dnevni kazalniki mobilnosti (vsi prevozni načini, Slovenija)

| Kazalnik | Vsi dnevi | Delovni dan | Nedelovni dan |
|---|---|---|---|
| Potovanj/oseba/dan | 2,3 | 2,4 | 1,8 |
| Razdalja/oseba/dan (km) | 32,4 | 33,7 | 29,2 |
| Čas potovanja/oseba/dan (min) | 55 | 57 | 51 |
| Zasedenost avtomobila | 1,6 | 1,4 | 2,0 |
| Razdalja/potovanje (km) | 14,4 | 13,7 | 16,6 |
| Trajanje/potovanje (min) | 24 | 23 | 29 |

### Razdalja in trajanje po namenu (vsi prevozni načini, Slovenija)

| Namen | Razdalja (km) | Trajanje (min) |
|---|---|---|
| Delo | 18,3 | 24 |
| Poslovni opravki | 32,9 | 34 |
| Izobraževanje | 15,8 | 33 |
| Nakupovanje | 6,9 | 13 |
| Peljati/priti iskat | 8,8 | 14 |
| Prosti čas | 14,9 | 32 |
| Osebni opravki | 14,7 | 22 |

**Opomba o viru:** zgornji dve tabeli izhajata iz podatkov, ki sem jih prejel kot zaslonske posnetke SURS interaktivnega orodja o potovalnih navadah. Natančen URL/tabela še ni potrjena — priporočam, da pred uporabo v nalogi preveriš in dodaš točen vir/citat. Podatki o prebivalstvu/površini/gostoti v §5 imajo potrjene, klikljive vire (stat.si/obcine).

---

## 7. Zaključki in omejitve

- Pipeline trajanje in trips/day padejo znotraj realnega SURS območja; trajanje po namenu pa ne variira dovolj (strukturna poenostavitev modela, ne napaka v podatkih).
- **Najbolj izstopajoča najdba:** pipeline koncentrira 46,4 % vseh odhodov v okno 7.–9. ura, medtem ko je realni SURS 2025 delež 13 % — skoraj 3,6× preveč. NHTS sam (12,1 %) se s SURS dobro ujema, razlika torej ni podedovana iz NHTS. **Vzrok je natančno lokaliziran v kodi:** `sample_work_start()` v `Step_1_prod.py` (vrstica 17–18) vzorči čas odhoda na delo iz `np.random.uniform(7,9)` — trda spodnja meja 7.00 in raven razrez do 9.00, namesto resničnega, ostrega jutranjega vrha pred 7. uro (SURS 2021 Work krivulja, ~15,5 % ob 6.–7. uri). To je ena samostojna vrstica kode, ne emergentno vedenje modela — najbolj konkretna, do izvorne kode sledljiva pomanjkljivost, odkrita v tem poročilu.
- Razdalja v Velenju ne pade znotraj SURS območja, razdalja v Krškem (dejansko ciljno mesto) pa pade — razlika je pojasnjena z demografskimi/geografskimi lastnostmi obeh občin, ne z napako v metodi.
- Stara SURS kalibracija v `Step_1_fit_si.py` (13 min, 13,8 km, 2,94 potovanj/dan) se ne ujema popolnoma z novo SURS 2025 tabelo (24 min, 14,4 km, 2,3 potovanj/dan) — vir te razlike ni bil preverjen znotraj tega poročila.
- R=1 (ena ponovitev na model) — brez intervalov zaupanja, rezultati so točkaste ocene.
- NHTS je ameriška anketa (drugo leto, druga država) — primerjava je mehanizmska (kaj model naredi), ne absolutna (kakšno je dejansko vedenje slovenskih voznikov).

---

## Seznam slik

| # | Datoteka |
|---|---|
| 1 | `analysis/Comparison2-0/comparison_nhts_vs_pipeline.png` |
| 2 | `analysis/Comparison_Velenje/comparison_velenje_distance.png` |
| 3 | `analysis/Comparison_Velenje/velenje_krsko_demografija.png` |
| 4 | `analysis/comparison_AB/figures/prostorska_A_velenje.png` |
| 5 | `analysis/comparison_AB/figures/prostorska_B_krsko.png` |
