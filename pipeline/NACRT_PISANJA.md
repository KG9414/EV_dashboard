# Načrt pisanja magistrske naloge
**Cilj oddaje: začetek septembra 2026**
**Začetek: 29. junij 2026**
**Trajanje: ~9 tednov**
**Strategija: poglavje za poglavjem → profesorju sproti**

---

## Struktura naloge (7 poglavij)

### 1. Uvod
- Motivacija in ozadje (rast EV flote, obremenitev omrežja, potencial V2G/G2V)
- Opredelitev problema in raziskovalna vprašanja (merjenje prožnosti, odprte podatki, raven flote)
- Cilji in prispevki naloge (simulacija flote, kvantifikacija prožnosti, vizualizacija za občino)
- Študija primera: občina Krško (flota ~16.803, penetracija 6,13 %, lokalni podatki)
- Struktura naloge (pregled poglavij, tok dela)

### 2. Teoretične osnove
- Tehnologiji V2G in G2V (dvosmerno polnjenje, storitve omrežju, agregacija flote)
- Prožnost flote električnih vozil (pozitivna in negativna, časovna razpoložljivost, meje delovanja)
- Modeliranje mobilnosti in generiranje poti (generiranje poti, prehodne matrike, demografski profil)
- Dinamika stanja napolnjenosti — SoC (poraba energije, meje SoC, kapaciteta baterije)
- Pregled obstoječih orodij (EPIOT, PFM, umestitev dela)
- Viri odprtih podatkov (OSM landuse, SiStat, potovalne ankete)

### 3. Metodologija
- Pregled simulacijskega cevovoda (koraki Step_0–Step_4, vhod in izhod, agregacija flote)
- Vhodni podatki in demografsko uteževanje (demografske uteži, profili uporabnikov, prehodne matrike)
- Generiranje poti in dodelitev vozil (generiranje poti, dodelitev vozil, konfiguraciji 2T / 4T)
- Določanje lokacij in usmerjanje (klici API, izohrone in razdalje, skaliranje)
- Simulacija dinamike SoC (dinamika po vozilu, 15-minutni intervali, poraba med potjo)
- Kvantifikacija prožnosti (pozitivna in negativna, agregacija flote, znakovne konvencije)
- Modelske predpostavke in robni pogoji (fiksni parametri, meje SoC, koeficienta α in β)
- Prostorska klasifikacija con (poligoni OSM, prostorski spoj, matrika tipov)

### 4. Vizualizacija
- Prototip v okolju Matplotlib (štiri vozila, animacija mobilnosti, dokaz koncepta)
- Prostorski prikaz gostote mobilnosti (toplotna karta, prostorska gostota, podloga contextily)
- Spletna aplikacija DomCenter (občinski vizualizator, interaktivni pogledi, mobilnost flote)
- Razvoj in nadgradnje vizualizacije (iterativni razvoj, od raziskave k občini, povezava z rezultati)
- Prikaz prožnosti (krivulje SoC, grafi prožnosti, časovne serije)

### 5. Rezultati
- Validacijski primer (izhod Matplotlib, tok poti, osnovni SoC)
- Dinamika stanja napolnjenosti (krivulje po vozilu, agregacija flote, dnevni vzorec)
- Pozitivna in negativna prožnost (razpoložljiva kapaciteta, časovni profili, seštevek flote)
- Rezultati po scenarijih (Tier 1/2/3, razpon penetracij, primerjava)
- Vizualni prikaz rezultatov (pogledi DomCenter, grafi prožnosti, prostorska razporeditev)
- Validacija modela (preverba 1–5 EV, pričakovano vedenje, skladnost)

### 6. Razprava
- Interpretacija rezultatov prožnosti (čas največje prožnosti, vpliv penetracije, dnevni vzorci)
- Omejitve modela in podatkov (redka pokritost OSM, skaliranje API, poenostavitve)
- Primerjava z obstoječimi orodji (DomCenter vs. EPIOT vs. PFM, prednost odprtih podatkov, prenosljivost)
- Implikacije za občinsko načrtovanje (potencial V2G, načrtovanje omrežja, prenos drugim)

### 7. Zaključek
- Povzetek prispevkov (kvantifikacija prožnosti, odprti podatki + študija primera)
- Odgovori na raziskovalna vprašanja (povzetek ugotovitev, izpolnitev ciljev)
- Smernice za nadaljnje delo (razrešitev zanke API, skaliranje, večje flote, članek WEVi)

---

## Tedenski načrt — cilj: oddaja profesorju po poglavjih, finalna verzija začetek septembra

| Teden | Datum | Poglavje | Profesorju do |
|---|---|---|---|
| **1–2** | 29. jun – 12. jul | **Pog. 3: Metodologija** (vsebina je že v kodi in enačbah) | **12. jul** |
| **3** | 13. jul – 19. jul | **Pog. 2: Teoretične osnove** | **19. jul** |
| **4** | 20. jul – 26. jul | **Pog. 4: Vizualizacija** | **26. jul** |
| **5** | 27. jul – 2. avg | **Pog. 5: Rezultati** | **2. avg** |
| **6** | 3. avg – 9. avg | **Pog. 6: Razprava** | **9. avg** |
| **7** | 10. avg – 16. avg | **Pog. 1: Uvod + Pog. 7: Zaključek** | **16. avg** |
| **8** | 17. avg – 23. avg | Celotna revizija, kazalo, literatura, slike | **23. avg → prva celotna verzija** |
| **9** | 24. avg – 31. avg | Popravki po komentarjih profesorja + lektoriranje | — |
| 🏁 | **1.–5. september** | **FINALNA ODDAJA** | |

---

## Podrobnosti po tednih

### TEDEN 1–2 | 29. jun – 12. jul → Pog. 3: Metodologija
- Opis simulacijskega cevovoda (Step_0 do Step_4)
- Matematične enačbe iz `docs/EQUATIONS.md` (Markov, gravitacija, SoC, prožnost…)
- Demografski profili (Commuter 44,9 %, Retired 21,6 %, Noncommuter 33,5 %) — SiStat
- Modelske predpostavke in robni pogoji
- Prostorska klasifikacija con (OSM)
- **Najprej** → ker je vsebina že dokumentirana in ni potrebno iskati novih virov

### TEDEN 3 | 13. jul – 19. jul → Pog. 2: Teoretične osnove
- V2G / G2V tehnologija, prožnost flote
- Modeliranje mobilnosti (Markovske verige, gravitacijski model)
- Dinamika SoC
- Pregled obstoječih orodij (EPIOT, PFM)
- Odprti podatki (OSM, SiStat, NHTS, SURS)

### TEDEN 4 | 20. jul – 26. jul → Pog. 4: Vizualizacija
- Matplotlib prototip (4 vozila, dokaz koncepta)
- Razvoj v Streamlit (DomCenter spletna aplikacija)
- Toplotna karta, krivulje prožnosti, histogram prihodov/odhodov
- Iterativni razvoj in scenariji

### TEDEN 5 | 27. jul – 2. avg → Pog. 5: Rezultati
- Validacijski primer (1–5 EV)
- Dinamika SoC in prožnost po scenarijih (Tier 1/2/3)
- Prostorska razporeditev rezultatov
- Slike in tabele iz `analysis/`

### TEDEN 6 | 3. avg – 9. avg → Pog. 6: Razprava
- Interpretacija ključnih rezultatov
- Omejitve (NHTS = ameriški podatki, fiksno 2 poti/dan, OSM pokritost)
- Primerjava z EPIOT in PFM
- Implikacije za Krško in prenosljivost metodologije

### TEDEN 7 | 10. avg – 16. avg → Pog. 1: Uvod + Pog. 7: Zaključek
- Uvod (pišeš zadnji — ko veš, kaj si napisala)
- Zaključek: povzetek prispevkov, odgovori na RV, smernice (WEVi članek)

### TEDEN 8 | 17. avg – 23. avg → Celotna revizija
- Sestavi vsa poglavja skupaj
- Preverba doslednosti enačb, oznak, slik
- Kazalo, seznam slik, literatura
- → **23. avg: pošlji profesorju PRVO CELOTNO VERZIJO**

### TEDEN 9 | 24. avg – 31. avg → Popravki + lektoriranje
- Popravki po komentarjih profesorja
- Lektoriranje slovenskega besedila
- Formatiranje po predpisih fakultete
- Izvleček (SLO + ENG)

### 🏁 1.–5. september → ODDAJA

---

## Predvideni obseg

| Poglavje | Strani |
|---|---|
| 1. Uvod | 4–6 |
| 2. Teoretične osnove | 12–18 |
| 3. Metodologija | 18–25 |
| 4. Vizualizacija | 8–12 |
| 5. Rezultati | 12–18 |
| 6. Razprava | 8–12 |
| 7. Zaključek | 4–6 |
| **Skupaj** | **~66–97 strani** |

---

## Naslednji korak (takoj)
Pogovor s profesorjem o primerjavi modelov → kaj ostane, kaj se popravi → nato začni pisati **Poglavje 3**.
