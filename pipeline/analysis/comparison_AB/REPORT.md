# Poročilo: Primerjava modela A (Original) in modela B (Pipeline)

**Datum:** 2026-06-15  
**Konfiguracija:** N=25 vozil, 4 potovanja/vozilo, 1 dan (primarna); N=100 sekundarno  
**Replikacije:** R=1 (ena ponovitev na model — brez intervalov zaupanja)

---

## 1. Pregled modelov

| Lastnost | Model A — Original | Model B — Pipeline |
|---|---|---|
| Mesto | Velenje | Krško |
| Korak 1 (čas potovanj) | Markov + NHTS profili (2 day-type) | Markov + NHTS profili + demogr. profili (5 day-type) |
| Korak 2 (lokacije) | ORS isochrone API + POI vzorčenje | ORS isochrone (primarno, ista metoda kot A) + Haversine-KNN ring (fallback, redko) [^b2] |
| Demografski profili | Ne | Da (Commuter 44.9 %, Retired 21.6 %, Noncommuter 33.5 %) |
| Validator verig | Ne | Da |
| Day-types | 2 (Workday / Weekend) | 5 (Mon–Thu / Fri / Sat / Sun / Holiday) |
| API odvisnosti | ORS (isochrone + routing) + Overpass | Overpass + ORS (isochrone + routing) |

[^b2]: **Popravek (2026-06-17):** prvotna označba "Haversine ring + gravitacijski model" za Model B je opisovala poenostavljen primerjalni skript (`run_B_velenje.py` v1), NE dejanske produkcijske kode. `Step_2_prod.py` (line 187) dejansko najprej poskusi ORS izohrono — enako kot Model A — in se na Haversine ring zateče šele, če izohrona vrne 0 kandidatov. `run_B_velenje.py` je bil posodobljen na v2, da odraža to dejansko verigo. Glej §5 "B_velenje primerjava" za popravljeno ugotovitev.

---

## 2. Rezultati po oseh

### 2.1 Čas odhoda

| Metrika | Vrednost |
|---|---|
| KS statistika | 0.36 |
| KS p-vrednost | < 0.001 |
| Wasserstein razdalja | 3.45 h |

**Interpretacija:** Porazdelitvi časov odhodov se statistično značilno razlikujeta (KS p ≈ 0). Model A generira odhode razpršenejše čez cel dan; Model B ima izrazitejši jutranji vrh (commuter profili silijo zgodnje odhode 7–9h) in višjo verjetnost popoldanskih potovanj. Wasserstein razdalja 3.45 h pomeni, da je povprečna »premestitev mase« med porazdelitvama enaka skoraj 3,5 ure — vsebinsko velika razlika. Vzrok: B-jev demografski sistem in 5 day-types bolj disciplinirata čase ohodov kot A-jeva stohastična Markov-shema z dvema day-types.

### 2.2 Trajanje potovanj

| Metrika | Vrednost |
|---|---|
| KS statistika | 0.13 |
| KS p-vrednost | 0.37 (ni statistično značilno) |
| Wasserstein razdalja | 2.23 min |

**Interpretacija:** Porazdelitvi trajanj sta si zelo podobni — oba modela vzorčita iz iste eksponentne distribucije (NHTS fit, µ=5 min, λ≈0.053). Razlika ni statistično značilna. To je pričakovano: trajanje je vzorčeno iz iste izvorne porazdelitve v obeh modelih.

### 2.3 Razdalja potovanj

| Metrika | Vrednost |
|---|---|
| KS statistika | 0.18 |
| KS p-vrednost | 0.078 (mejno) |
| Wasserstein razdalja | 4.39 km |

**Interpretacija:** Razdalje so mejno različne (p ≈ 0.08). Model A ima debeljeji rep pri visokih razdaljah (max 86.9 km vs 67.7 km v B), kar kaže, da izohrone (Velenje) dosežejo bolj odročne destinacije. B (Krško produkcija, ORS isochrone + gravitacijski model na mase POI) preferira bližnje destinacije z večjo maso (veliki objekti v Krškem), kar skrajša rep porazdelitve — *opomba: pripis temu izključno "Haversine ring" je bil popravljen v §5; gre za gravitacijski model v interakciji z gostoto POI, glej "B_velenje primerjava"*. Razlika v Wasserstein razdalji (4.39 km) je vsebinsko zmerna.

### 2.4 Tipi aktivnosti

**Primarna konfiguracija (N=25, 4 pot.):**

| Aktivnost | A (%) | B (%) | Razlika (pp) |
|---|---|---|---|
| Work | 18.0 | 30.0 | +12 |
| Leisure | 34.0 | 42.0 | +8 |
| Personal | 20.0 | 14.0 | −6 |
| Shopping | 14.0 | 8.0 | −6 |
| Education | 6.0 | 2.0 | −4 |
| Business | 4.0 | 0.0 | −4 |
| Transport | 4.0 | 4.0 | 0 |

Jensen–Shannon divergenca (JSD) = 0.189; χ²-test p = 0.051 (mejno).

**Sekundarna konfiguracija (N=100):** JSD = 0.268; χ²-test p < 0.001 (statistično značilno).

**Interpretacija:** B ima bistveno višji delež Work potovanj (+12 pp pri N=25, +28 pp pri N=100). Vzrok je B-jev demografski sistem: Commuter profil (44.9 % vozil) zahteva Work potovanje, medtem ko A Work generira le stohastično prek Markova. Pri N=100 je razlika še izrazitejša, kar potrjuje sistematični učinek in ne naključja vzorčenja. B hkrati izloča Business kot samostojno kategorijo (verjetno se zlije z Work prek filtriranja po profilu). Višji Leisure delež v B izhaja iz tega, da Noncommuter in Retired profili prioritizirajo prostočasne aktivnosti.

### 2.5 Veljavnost verig

| Model | Delež z Work (%) | Simetričen povratek (%) |
|---|---|---|
| A | 36.0 | 16.0 |
| B | 56.0 | 44.0 |

**Opomba:** »Home« ni ekspliciten trip type v Step3 izhodih — Home je implicitno izhodišče in cilj vsake verige. »Simetričen povratek« pomeni, da zadnje potovanje v verigi vrne vozilo na isto aktivnostno vrsto kot prvo potovanje (npr. Work→...→Work).

**Interpretacija:** B-jev validator verig zagotavlja višji delež Work (commuter demografija) in bolj urejen povratek (44 % vs 16 %). A brez validatorja pogosteje generira nekonsistentne verige.

### 2.6 Prostorske lastnosti

> **Opomba:** A je bil zagnan za Velenje, B za Krško. Porazdelitvi destinacij **nista neposredno primerljivi** (različni mesti, različna prostorska struktura). Spodnje metrike primerjajo *metodološke lastnosti* — kako vsak model razprši destinacije v svojem mestu.

| Lastnost | A — Velenje | B — Krško |
|---|---|---|
| Število destinacij | 100 | 100 |
| Povp. razdalja med dest. (km) | 9.57 | 7.75 |
| Konveksna ogrinjača (km²) | 2 031.5 | 717.6 |
| Unikatne lokacije (zaokr. 1 km) | 74 | 59 |

**Interpretacija:** Model A (ORS isochrone) razprši destinacije po bistveno večjem območju (konveksna ogrinjača 2 031 km² vs 718 km²). Razlog: izohrona dovoljuje doseg do meje časa potovanja ne glede na gostoto POI-jev, kar vodi do redkih, a prostorsko razpršenih destinacij. B (Krško produkcija) uporablja isto ORS isochrone metodo kot A, a njen gravitacijski model (mass/d²) znotraj tega prednostno obravnava objekte z večjo maso (večje stavbe), ki so koncentrirani v mestnem jedru Krška — manjše območje, višja gostota. Višje število unikatnih lokacij v A (74 vs 59) kaže, da A vzorči iz večjega bazena POI-jev; B pa je bolj deterministično usmerjen k istim težkim lokacijam.

---

## 3. Operacijska primerjava

| Lastnost | A | B |
|---|---|---|
| Metoda destinacij | ORS isochrone API | ORS isochrone API (primarno) + Haversine-KNN ring (fallback) [^b2] |
| API klici | Da (isochrone + routing, ~10 klicev/vozilo) | Da (isochrone + routing); OSM lokalno predpomnjeno |
| Zamuda | `time.sleep(5)` na isochrone klic | Ni proaktivne zamude; retry z 10s sleep ob napaki/rate-limitu |
| Reproducibilnost | Nizka (API rate limits, omrežje) | Nizka–srednja (isochrone API odvisnost; OSM lokalno predpomnjeno) |
| Skalabilnost | Slaba (N=100 × R=20 ≈ 2000+ API klicev) | Srednja (precomp_*.pkl za POI, a isochrone klici ostanejo API-odvisni) |

---

## 4. Sklep

Modela se **statistično značilno razlikujeta** na čas odhoda (p ≈ 0, KS=0.36) in tipih aktivnosti (χ² p < 0.001 pri N=100), **ne razlikujeta** pa v porazdelitvi trajanj (p = 0.37). Razdalje so mejno različne (p ≈ 0.08).

Ključni mehanizmi, ki pojasnjujejo razlike:
- **Čas odhoda:** demografski profili in 5 day-types v B → izrazitejši jutrannji commuter vrh
- **Tipi aktivnosti:** B-jev Work-prisiljevalni Commuter profil → bistveno višji Work delež
- **Prostorska razpršenost:** A in B (produkcija) uporabljata isto primarno metodo (ORS isochrone); razlika v razpršenosti izhaja iz gostote/redkosti OSM POI po kategorijah in gravitacijskega modela, ne iz izbire metode same (glej popravljeno §5 "B_velenje primerjava")
- **Trajanje:** oba modela vzorčita iz iste NHTS distribucije → ni razlike

---

## 5. Omejitve in scope

- **R=1:** ena ponovitev na model. Brez intervalov zaupanja — rezultati so točkaste ocene in morda niso reprezentativni za celotno porazdelitev modela.
- **A=Velenje, B=Krško:** prostorske metrike (konveksna ogrinjača, meddestiancijska razdalja) niso neposredno primerljive — različni mesti z različno prostorsko strukturo. Primerjamo metodološke lastnosti.
- **Brez empiričnih podatkov za Krško/Velenje:** primerjava je mehanizmska (kaj model naredi), ne absolutnostna (kaj je resnično vedenje vozačev).
- **A-jevo izohrono okolje:** Isochrone API je Velenje-specifičen (area_id=3601675901). Prevzorčanje A za Krško bi zahtevalo spremembo izvorne kode — izven dosega te primerjave.
- **Haversine ring kot proxy — OPOMBA (2026-06-17, glej popravek spodaj):** prvotna analiza je domnevala, da B v produkciji uporablja Haversine ring kot primarno metodo, in pripisala nizko razdaljo v Velenju temu (30 km/h proxy). To je bilo napačno: `Step_2_prod.py` dejansko najprej poskusi ORS isochrone (enako kot A) in se na Haversine ring zateče le, ko isochrone vrne 0 kandidatov. Spodnja ugotovitev je bila po preverjanju popravljena.
- **B_velenje primerjava (POPRAVLJENO 2026-06-17):** `run_B_velenje.py` je bil prvotno (v1) implementiran z Haversine-ring-only metodo (brez ORS isochrone) — to ni odražalo dejanske produkcijske verige in je dalo prenizko oceno B-jeve metode. Po popravku na v2 (ORS isochrone primarno + Haversine-KNN fallback, enako kot `Step_2_prod.py`) se povprečna razdalja v Velenju **komaj spremeni: 5.02 → 5.24 km** (vs A: 15.8 km, B Krško produkcija: 13.2–15.3 km). Fallback na Haversine-KNN ni bil niti enkrat potreben (0/100) — ORS isochrone je obdelal vse potovanje.
  **Mehanizem (potrjeno iz log datoteke):** za Work/Education/Business v Velenju je natančno annularno območje izohrone (med floor in ceil trajanja) prazno 37/100-krat (100 % Education potovanj, 56 % Work potovanj), ker ima Velenje malo OSM-označenih stavb teh tipov v absolutnem številu (work=74, edu=19 objektov v celem mestu). Ko je annulus prazen, se `ors_isochrone_filter` interno zateče k CELOTNI izohroni od 0 minut, gravitacijski model (beta=2, ~1/d²) pa znotraj tega širšega nabora kandidatov močno preferira najbližjega — razdalja se sesede ne glede na to, kako velik je dejanski časovni proračun.
  **POPRAVEK glede vzroka (2026-06-17, po preverjanju s SURS podatki):** prvotna razlaga "redki/nepopolni OSM podatki v Velenju" je bila napačna in je bila preverjena z dejansko gostoto OSM objektov. Velenje ima VEČJO gostoto oznak na km² kot Krško v vseh kategorijah (work: 0.89 vs 0.47/km², edu: 0.23 vs 0.07/km², leisure: 1.22 vs 0.41/km², katerakoli stavba: 67 vs 44/km²) — OSM pokritost Velenja ni pomanjkljiva, je gostejša. Napačna je bila tudi domneva, da je Velenje "manjše mesto": po SURS podatkih (mid-2023/2024, [stat.si](https://www.stat.si/obcine/en/Municip/Index/190)) ima občina Velenje 33.680 prebivalcev na 84 km² (gostota 401/km², ~4× slovensko povprečje 105/km²) — VEČ prebivalcev kot cela občina Krško (26.070 na 287 km², gostota 91/km², POD slovenskim povprečjem). Naselje Velenje je 6. največje mesto v Sloveniji po prebivalstvu; mesto Krško sámo ni niti med 10 največjimi.
  **Pravi vzrok:** Velenje je manjše po OBČINSKI POVRŠINI (84 km² proti 287 km²), ne po prebivalstvu ali gostoti OSM oznak — to omejuje absolutno število različnih Work/Education stavb, ki sploh lahko obstajajo znotraj tako majhne površine, četudi je ta gosto poseljena. To je smiselna posledica kompaktne, goste urbane oblike Velenja (planirano rudarsko mesto 20. stoletja), NE pomanjkanje ali nizka kakovost OSM podatkov.
  **Posledica za interpretacijo:** kratke razdalje v Velenju (5.24 km) so verjetno realistična posledica kompaktnega, gosto poseljenega mesta — ne napaka modela. Daljše razdalje v Krškem (13.2–15.3 km, znotraj SURS območja 13.7–16.6 km) so skladne s tem, da je občina Krško redko poseljena (91/km², pod povprečjem) in razpotegnjena prek več ločenih naselij (Senovo, Leskovec, Brestanica, Kostanjevica) — prebivalci morajo pogosto prevoziti več, da dosežejo storitve. Obe številki sta lahko realistični za svoj kraj; primerjava z enotnim nacionalnim povprečjem SURS ne pove, katera metoda je "pravilnejša", ker gre za strukturno različna naselja (kompaktno mesto vs. razpotegnjena podeželska občina).
- **OSM podatki:** preverjena gostota OSM oznak je VIŠJA v Velenju kot v Krškem (glej popravek zgoraj) — to NI vzrok za nizko razdaljo v Velenju. Pokritost stavb v Krškem je redka na obrobju (Senovo, Leskovec), kar lahko sproži podoben mehanizem (prazen annulus → gravitacijski bias k najbližjemu) v teh conah — ni neposredno preverjeno v tej primerjavi.

---

## Datoteke

```
figures/
  ecdf_cas_odhoda.png           ← histogram časov odhodov (15-min razredi)
  ecdf_cas_trajanje_razdalja.png ← ECDF trio (3 paneli)
  kde_cas_trajanje_razdalja.png  ← KDE + histogram trio
  qq_trajanje_razdalja.png       ← Q–Q primerjava
  deleži_aktivnosti.png          ← grupirani stolpci (N=25 in N=100)
  poti_na_vozilo.png             ← povprečno število potovanj
  prostorska_A_velenje.png       ← hex density, Velenje
  prostorska_B_krsko.png         ← hex density, Krško
  povzetek_porazdelitve.png      ← summary small-multiples panel

metrics/
  01_distribucijske_metrike.csv
  02a_deleži_aktivnosti_N25.csv
  02b_deleži_aktivnosti_N100.csv
  02c_aktivnosti_povzetek.csv
  03_poti_na_vozilo.csv
  04_veljavnost_verig.csv
  05_prostorske_lastnosti.csv
  06_operacijska_primerjava.csv
```
