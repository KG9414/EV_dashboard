# NHTS vs. evropske ankete o mobilnosti — utemeljitev metodološke odločitve

Zbrano za magistrsko nalogo: zakaj NHTS (ameriški podatki) namesto evropske alternative?

---

## Pregled evropskih anket — primerjalna tabela

| Anketa | Država | Javno dostopna? | Podatki na ravni poti? | Uporabna za EV simulacijo? | Opomba |
|---|---|---|---|---|---|
| **MiD** (Mobilität in Deutschland) | Nemčija | Omejena — zahteva registracijo in plačilo (KBA) | Da — čas odhoda, trajanje, razdalja, namen poti | Da — standardno orodje (emobpy, VencoPy) | Zadnji val 2023; 421.000 gospodinjstev |
| **ODiN / OViN** (Onderweg in Nederland) | Nizozemska | Agregatni podatki prosto; mikrodata prek DANS-EASY | Da (mikrodata) — čas, namen, razdalja, prevozno sredstvo | Da — validirana za EV raziskave | ODiN nadomestil OViN od 2018 |
| **NTS** (National Travel Survey) | Velika Britanija | Omejena — UK Data Service (registracija); "Special Licence" za celotne mikrodata | Da — tedenski potovalni dnevnik na pot | Da — pogosta v britanski EV literaturi | Letna anketa 2002–2023 |
| **HETUS** (Harmonised European Time Use Survey) | EU (Eurostat) | Delno — agregatne tabele prosto; mikrodata omejeni | Podatki o rabi časa, ne neposredni potovalni dnevniki | Posredno — za modeliranje aktivnostnih verig | Zadnji val 2008–2015; metodološko heterogeno |
| **Eurostat (potniška mobilnost)** | EU | Agregatni rezultati | Ne — brez mikrodat na ravni posameznika | Omejeno — samo agregatni modal share, km/osebo/leto | Eurostat: potniška mobilnost za ceste ni del reguliranega EU statističnega sistema |
| **Anketa o dnevni mobilnosti** | Slovenija (SURS) | Agregatni povzetki v SiStat bazi | Ni potrjenih javnih podatkov na ravni poti | Ne — ne v obliki, ki bi bila neposredno uporabna za EV simulacijo | Pilotna anketa 2017, ponovitev 2021; četrtletna |

---

## Nemška MiD — najbližji strukturni ekvivalent NHTS

MiD je od vseh evropskih anket najbolj podobna NHTS. Val 2017: 316.000 oseb, ~1 milijon potovalnih zapisov z vsemi ključnimi spremenljivkami (čas odhoda, trajanje, razdalja, namen, prevozno sredstvo). Dostop zahteva registracijo in plačilo pri nemškem zveznem prometnem uradu (KBA). Do konca 2024 je bila distribucija prek Clearingstelle Verkehr (DLR) — od 2025 dalje prek KBA.

**Dve ključni odprtokodni EV orodji, zgrajeni na MiD:**
- **emobpy** (Gaete-Morales et al., 2021, *Scientific Data*, DOI: 10.1038/s41597-021-00932-9) — generira profile mobilnosti, porabe, razpoložljivosti za polnjenje in obremenitve omrežja pri 15-minutni resoluciji iz distribucij MiD 2017.
- **VencoPy** (Fasihi et al., 2021, *Energies*, DOI: 10.3390/en14144349) — izračunava prožnost polnjenja EV iz nacionalnih potovalnih anket; demonstriran na MiD 2008 in MiD 2017.

---

## Zakaj se NHTS uporablja izven ZDA

### Dokumentirani razlogi iz literature

**1. Kakovost in granularnost podatkov.** NHTS 2017 pokriva ~264.000 gospodinjstev z vsemi potovalnimi zapisi, vključno s časom odhoda, trajanjem, razdaljo, namenom in tipom vozila. Primerljive evropske ankete so bodisi omejeno dostopne (MiD, NTS) bodisi strukturno šibkejše na mikro ravni.

**2. Javna dostopnost brez institucionalnih ovir.** NHTS mikrodata se brezplačno prenese z nhts.ornl.gov. MiD zahteva plačljivo registracijo; NTS zahteva institucionalno priključenost na UK Data Service. Za raziskovalce izven Nemčije ali VB je NHTS praktično najbolj dostopna anketa z zahtevano granularnostjo.

**3. Precedent v literaturi:**
   - **"Trip Chain Simulation of Electric Vehicles based on NHTS Data"** (IEEE PESGM 2020, DOI: 10.1109/PESGM41954.2020.9220726) — stohastični parametri za trip chains (čas odhoda, trajanje, razdalja) pridobljeni iz NHTS, s Monte Carlo simulacijo. Metodologijo reproducirajo v ne-ameriških kontekstih.
   - **Danski projekt "Test-en-Elbil"** — danski raziskovalci so NHTS podatke uporabili kot referenčno osnovo za primerjavo vzorcev EV in ICEV rabe.
   - **ev-flow** (arXiv:2606.19520, 2025) — generira EV vedenje s stohastičnim modelom, utemeljenim z NHTS 2017; eksplicitno navaja odsotnost enako odprtega in granularnega alternativnega vira.

**4. Odsotnost pan-evropske alternative.** Eurostat eksplicitno navaja: *"Statistike potniške mobilnosti za cestni promet niso del reguliranega evropskega statističnega sistema."* Projekt OPTIMISM WP2 (JRC, 2013) je pregledal 15 nationalnih anket in ugotovil veliko metodološko heterogenost — kar zmanjšuje zanesljivost medanketnih primerjav.

---

## Prenosljivost — kaj pravi literatura

### Podobnosti, ki podpirajo transfer

- **Porazdelitve dnevnih razdalj so si strukturno podobne.** NHTS 2017: povprečna dolžina poti ~18 km; Slovenija (SiStat 2021): ~13 km. Ključni za EV simulacijo sta oblika porazdelitve in desni rep (dolge poti), ne absolutno povprečje.
- **Dominanca kratkih poti velja v vseh državah.** Poti pod 20 km prevladujejo tako v ameriških kot evropskih zbirkah. Ker je tipičen doseg BEV 200–400 km, porazdelitev razdalj redko vpliva na to, ali vozilo zaključi pot brez polnjenja.
- **Vzorci časov odhodov.** Jutranje in večerne konice so strukturno podobne v vseh industrializiranih državah — določa jih delovni urnik, ki je relativno stabilen čez različne zahodnoevropske države. Ta spremenljivka je najpomembnejša za simulacijo povpraševanja po polnjenju.

### Razlike, ki omejujejo prenos

- **Dnevna prevožena razdalja.** NHTS 2022: povprečna pot ~21 km; Slovenija 2021: ~13 km. To pomeni, da modeli na osnovi NHTS brez kalibracije nekoliko precenijo dnevno porabo energije.
- **Stopnja avtomobilske odvisnosti.** Slovenija ima 29 % poti v ne-avtomobilskih načinih (2021 SiStat); NHTS odraža visoko avtomobilsko odvisnost ZDA. Brez popravkov se simulira previsoka razpoložljivost vozil za polnjenje.
- **Primerjalna ugotovitev iz literature:** Študija iz 2024 (*Transportation Planning and Technology*, DOI: 10.1080/03081060.2024.2311081) o šestih evropskih državah ugotavlja, da imajo vse nacionalne ankete "izzive kakovosti in nedoslednosti metodologije" — kar implicitno podpira NHTS kot referenčno osnovo: če so same evropske ankete heterogene in pomanjkljive, se marginalna prednost lokalne ankete pred kakovostno tujo zmanjša.

---

## Slovenska situacija — kaj obstaja

**Kar obstaja:**
- SURS je opravil pilotno "Anketo o dnevni potniški mobilnosti" jeseni 2017 in 2021 (četrtletno).
- Objavljeni agregatni kazalniki (SiStat): 3,2 poti/dan (2017), 13 km povprečna dolžina poti, 76 min/dan skupnega časa potovanja; >2/3 poti z avtomobilom.

**Kar ne obstaja (javno):**
- Ni potrjenih javnih mikrodat z individualnimi potovalnimi zapisi (čas odhoda, trajanje, razdalja per pot).
- Ni slovenskega gospodinjskega potovalnega dnevnika v smislu NHTS/MiD — SURS anketa je lažja, periodična slika, ne kontinuiran dnevnik.
- Nobena slovensko specifična EV simulacija, ki bi bila objavljena in bi neposredno uporabila SURS mikrodata za trip-chain modeliranje, ni bila najdena. Študija EV kot porazdeljenega hranilnika za Slovenijo (DOI: 10.3390/en17112733) temelji na agregatnih predpostavkah, ne na individualnih potovalnih verigah.

**Kar to pomeni za nalogo:**
Slovenija nima javno dostopnih potovalnih mikrodat, ki bi bile uporabne za NHTS-style trip-chain simulacijo. Agregatni SURS kazalniki so koristni za **kalibracijo in validacijo** parametrov simulacije (npr. preverjanje, da je povprečna dnevna razdalja v pravilnem razredu), ne morejo pa nadomestiti potovalnih mikrodat kot generativnega vhoda modela. To je osrednja metodološka utemeljitev za uporabo zunanje podatkovne baze.

---

## Znane omejitve NHTS v slovenskem/evropskem kontekstu

1. **Neskladje urbanega tkiva.** ZDA imajo bistveno višjo avtomobilsko odvisnost kot Slovenija. Kalibracija NHTS odraža ameriške modele; to vpliva na oceno razpoložljivosti vozil za polnjenje.
2. **Daljša povprečna dnevna razdalja.** NHTS brez kalibracije preceni dnevno porabo energije (~60 % višja povprečna razdalja poti).
3. **Sestava voznega parka.** NHTS odraža ameriški park (višji delež SUV in pick-upov, drugačna povprečna učinkovitost). Slovensko/evropska vozila so tipično manjša in učinkovitejša.
4. **Ni medsebojne validacije.** Ker ni slovenskih potovalnih mikrodat, ni enostavnega načina validirati, da NHTS distribucije časa in razdalj reproducirajo slovensko vedenje. To je treba eksplicitno navesti kot epistemično omejitev.

---

## Priporočeno oblikovanje argumenta v poglavju Metodologija

Standardna akademska obramba uporabe NHTS v ne-ameriškem kontekstu temelji na treh stebrih:

1. **Ustrezna lokalna alternativa ne obstaja.** Slovenija nima javnih potovalnih mikrodat; najbližje evropske alternative (MiD, NTS) zahtevajo institucionalni dostop, ki je bil nepraktičen.

2. **Ključni simulacijski vhodi (distribucije časov odhodov, distribucije dolžin poti) so strukturno podobni med industrijskimi državami** — to potrjujejo agregatni kazalniki NHTS, SURS in evropskih anket.

3. **Precedent v literaturi.** Raziskovalci eksplicitno uporabljajo NHTS kot nadomestilo v ne-ameriških kontekstih (danski V2G projekt; kitajske EV omrežne študije; več IEEE prispevkov). Orodji emobpy in VencoPy MiD 2017 uporabljata na enak način, kot ta naloga NHTS — oba sta nadomestila za lokalne podatke tam, kjer ti niso javno dostopni.

**Kalibracijski korak** — usklajevanje parametrov, pridobljenih iz NHTS, z agregatnimi slovenskimi kazalniki iz SURS — je ustrezen metodološki most in mora biti eksplicitno opisan v metodološkem poglavju.

---

## Ključni viri

- Gaete-Morales et al. (2021). *emobpy.* Scientific Data. DOI: 10.1038/s41597-021-00932-9
- Fasihi et al. (2021). *VencoPy.* Energies. DOI: 10.3390/en14144349
- IEEE PESGM 2020. *Trip Chain Simulation of EVs based on NHTS.* DOI: 10.1109/PESGM41954.2020.9220726
- arXiv:2606.19520 (2025). *ev-flow: NHTS-Grounded Generator of Synthetic EV Charging Behavior.*
- arXiv:1711.01440 (2017). *Numerical Analysis of UK National Travel Data for Fleet Electrification.*
- Transportation Planning and Technology (2024). *Comparative study of national travel surveys in six European countries.* DOI: 10.1080/03081060.2024.2311081
- SURS (2017, 2021). *Anketa o dnevni potniški mobilnosti.* stat.si
- Energies (2024). *Slovenia EV as Nationwide Battery Storage.* DOI: 10.3390/en17112733
- JRC/OPTIMISM WP2 (2013). *Analysis of national travel surveys in Europe.*

---

*Zbrano: julij 2026 | Iskanje prek Google Scholar, arXiv, IEEE Xplore, ScienceDirect, Eurostat, SURS*
