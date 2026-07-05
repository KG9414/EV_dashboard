# Enačbe simulacijskega modela

Pregled vseh matematičnih enačb, ki se uporabljajo v simulacijskem cevovodu in vizualizaciji.

---

## Kazalo

1. [Prostorske razdalje](#1-prostorske-razdalje)
2. [Markovska veriga prehodov](#2-markovska-veriga-prehodov)
3. [Gravitacijski model](#3-gravitacijski-model)
4. [Kombinacija Markova in gravitacije](#4-kombinacija-markova-in-gravitacije)
5. [Porazdelitev odhoda](#5-porazdelitev-odhoda)
6. [Porazdelitev trajanja potovanj](#6-porazdelitev-trajanja-potovanj)
7. [Pretvorba časa v intervale](#7-pretvorba-časa-v-intervale)
8. [Dosegljivostni prstan (Haversine Ring)](#8-dosegljivostni-prstan-haversine-ring)
9. [Poraba energije](#9-poraba-energije)
10. [Razdalja na 15-minutni interval](#10-razdalja-na-15-minutni-interval)
11. [Meje moči polnjenja](#11-meje-moči-polnjenja)
12. [Kumulativna prožnost SoC](#12-kumulativna-prožnost-soc)
13. [Linearna interpolacija položaja](#13-linearna-interpolacija-položaja)
14. [Dodelitev profilov voznikov](#14-dodelitev-profilov-voznikov)
15. [Skaliranje mas za gravitacijo](#15-skaliranje-mas-za-gravitacijo)
16. [Skupna obremenitev polnjenja flote](#16-skupna-obremenitev-polnjenja-flote)
17. [Histogram prihodov in odhodov s parkirišča](#17-histogram-prihodov-in-odhodov-s-parkirišča)
18. [Uteži toplotne karte gostote vozil](#18-uteži-toplotne-karte-gostote-vozil)
19. [Skaliranje vizualnega ozračja delovnega mesta](#19-skaliranje-vizualnega-ozračja-delovnega-mesta)
20. [Začetno stanje napolnjenosti baterije](#20-začetno-stanje-napolnjenosti-baterije)
21. [Simulacija stanja napolnjenosti (SoC)](#21-simulacija-stanja-napolnjenosti-soc)
22. [Pozitivna in negativna prožnost SoC](#22-pozitivna-in-negativna-prožnost-soc)
23. [Prostorska mrežna analiza — dodelitev celice](#23-prostorska-mrežna-analiza--dodelitev-celice)
24. [Skupna energija in neto pretok po coni](#24-skupna-energija-in-neto-pretok-po-coni)

---

## 1. Prostorske razdalje

### Haversinova formula

$$d = 2r \arcsin\!\left(\sqrt{\sin^2\!\left(\frac{\Delta\varphi}{2}\right) + \cos\varphi_1\,\cos\varphi_2\,\sin^2\!\left(\frac{\Delta\lambda}{2}\right)}\right)$$

**Spremenljivke:**
- $\varphi_1, \varphi_2$ — geografska širina začetne in končne točke (radianti)
- $\lambda_1, \lambda_2$ — geografska dolžina začetne in končne točke (radianti)
- $\Delta\varphi = \varphi_2 - \varphi_1$, $\Delta\lambda = \lambda_2 - \lambda_1$
- $r = 6371\,\text{km}$ — polmer Zemlje
- $d$ — razdalja po krogelni površini (km)

**Razlaga:** Haversinova formula izračuna najkrajšo razdaljo med dvema točkama na površini Zemlje (ortodroma). Uporablja se za merjenje razdalje med lokacijami vozil, točkami interesa in centroidi con. Ker je Zemlja sferična (ne ravna), ta formula daje natančnejši rezultat kot enostavna evklidska razdalja. Rezultat je v kilometrih.

*Izvorna datoteka: [pipeline/Functions_step_1.py](../pipeline/Functions_step_1.py) in [pipeline/Functions_step_2.py](../pipeline/Functions_step_2.py)*

---

## 2. Markovska veriga prehodov

### Matrika prehodnih verjetnosti

$$P_{ij} = \frac{n_{ij}}{\sum_k n_{ik}}$$

**Spremenljivke:**
- $n_{ij}$ — število opazovanih prehodov iz stanja $i$ v stanje $j$ v referenčnih podatkih NHTS
- $P_{ij}$ — verjetnost prehoda iz aktivnosti $i$ v aktivnost $j$
- Stanja: `Home`, `Work`, `Business`, `Education`, `Shopping`, `Transport`, `Leisure`, `Personal`

**Razlaga:** Na podlagi realnih podatkov o potovalnih navadah (NHTS) se za vsak 15-minutni interval izgradi matrika prehodnih verjetnosti. Za vsak par sosednjih intervalov se prešteje, kolikokrat so vozniki spremenili aktivnost iz ene vrste v drugo. Te frekvence se normalizirajo z vsoto po vrstici, tako da dobimo veljavno porazdelitev verjetnosti. Diagonal matrike (prehod iz stanja v isto stanje) je nastavljena na 0, ker nas zanima samo dejansko menjanje aktivnosti.

*Izvorna datoteka: [pipeline/Functions_step_1.py:121](../pipeline/Functions_step_1.py) in [pipeline/Step_1_prod.py:224](../pipeline/Step_1_prod.py)*

---

## 3. Gravitacijski model

### Utežena verjetnost destinacije

$$P(i \to j) \propto \frac{M_j}{d(i,j)^\beta}$$

$$p_j = \frac{M_j / d_{ij}^\beta}{\sum_k M_k / d_{ik}^\beta}$$

**Spremenljivke:**
- $M_j$ — "masa" destinacije $j$: površina poligona v m² (iz OSM podatkov), večja masa = večji kraj
- $d_{ij}$ — haversinova razdalja med izhodiščem $i$ in destinacijo $j$ (km)
- $\beta = 2$ — eksponent zatiranja razdalje (privzeto)
- $p_j$ — verjetnost izbire destinacije $j$
- $\varepsilon = 10^{-9}$ — majhna konstanta, ki prepreči deljenje z nič

**Razlaga:** Gravitacijski model posnemа Newtonov zakon gravitacije, aplikiran na mobilnost. Večji kraji (pisarne, šole, nakupovalna središča) privabljajo več obiskov, bližnji kraji pa so bolj verjetna destinacija kot oddaljeni. Eksponent $\beta = 2$ pomeni, da se privlačnost zmanjša s kvadratom razdalje. Model se uporablja pri vzorčenju konkretne destinacije znotraj dosegljivega območja.

*Izvorna datoteka: [pipeline/Functions_step_2.py:427–462](../pipeline/Functions_step_2.py)*

---

## 4. Kombinacija Markova in gravitacije

### Konveksna mešanica verjetnosti

$$\mathbf{p}_{\text{final}} = (1 - \alpha)\,\mathbf{p}_{\text{Markov}} + \alpha\,\mathbf{p}_{\text{gravity}}$$

**Spremenljivke:**
- $\mathbf{p}_{\text{Markov}}$ — vektor verjetnosti iz Markove matrike prehodov za trenutno stanje
- $\mathbf{p}_{\text{gravity}}$ — vektor verjetnosti iz gravitacijskega modela (normaliziran po vrstah aktivnosti)
- $\alpha = 0.3$ — parameter mešanja; 0 = čisti Markov, 1 = čista gravitacija
- $\mathbf{p}_{\text{final}}$ — končna porazdelitev, iz katere se vzorči naslednja aktivnost

**Razlaga:** Markovska veriga sama po sebi ne upošteva prostorske razporeditve aktivnosti v občini Krško. Gravitacijski model pa ne upošteva časovnih vzorcev potovanj. Konveksna mešanica združi oba pristopa: 70 % teže damo Markovi verigi (realni vzorci iz podatkov), 30 % pa gravitacijskemu modelu (prostorska privlačnost). Rezultat se normalizira, da je vsota verjetnosti enaka 1.

*Izvorna datoteka: [pipeline/Functions_step_1.py:150](../pipeline/Functions_step_1.py)*

---

## 5. Porazdelitev odhoda

### Gaussova mešanica za verjetnost odhoda

$$f(t) = \sum_{k=1}^{K} w_k \cdot \mathcal{N}(t;\,\mu_k,\,\sigma_k)$$

kjer je $\mathcal{N}(t;\,\mu,\,\sigma) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(t-\mu)^2}{2\sigma^2}}$

**Spremenljivke:**
- $t \in [0, 23.75]$ — čas v urah (mreža z ločljivostjo 15 minut, 96 točk)
- $\mu_k, \sigma_k, w_k$ — srednja vrednost, standardni odklon in utež $k$-te Gaussove komponente
- $K$ — število komponent (fitano na NHTS podatkih)
- $f(t)$ — gostota verjetnosti odhoda ob uri $t$

**Razlaga:** Verjetnost, da voznik odide ob določeni uri, ni enakomerna čez dan. Na podlagi realnih podatkov NHTS je bila porazdelitev časa odhodov aproksimirana z mešanico Gaussovih porazdelitev. Vsaka komponenta zajame en "val" odhoda (npr. jutranja konica ob 7:30, popoldanska ob 16:00). Parametri $\mu_k$, $\sigma_k$ in $w_k$ so bili pridobljeni s postopkom prilagoditve krivulje.

*Izvorna datoteka: [pipeline/Functions_step_0.py:39–44](../pipeline/Functions_step_0.py)*

---

## 6. Porazdelitev trajanja potovanj

### Eksponentna porazdelitev trajanja

$$f(\tau) = \frac{1}{\beta} \exp\!\left(-\frac{\tau - \tau_{\min}}{\beta}\right), \quad \tau \geq \tau_{\min}$$

**Spremenljivke:**
- $\tau$ — trajanje potovanja (minute), $\tau \in [0, 60]$
- $\tau_{\min} = 5\,\text{min}$ — minimalno trajanje potovanja
- $\beta \approx 18.9\,\text{min}$ — parameter skale (fitano na NHTS podatkih)
- $f(\tau)$ — gostota verjetnosti trajanja potovanja

**Razlaga:** Trajanje potovanj v realnosti sledi eksponentni porazdelitvi — kratka potovanja so pogostejša, dolga pa redkejša. Parameter $\beta$ določa, kako hitro verjetnost upada z daljšim trajanjem. Vrednost $\beta \approx 18.9$ minut pomeni, da je povprečno pričakovano trajanje (nad minimumom) ok. 19 minut. Vrednosti pod 5 minut so zavrnjene (minimalni pogoj), vrednosti nad 60 minut so omejene.

*Izvorna datoteka: [pipeline/Step_1_prod.py:149](../pipeline/Step_1_prod.py)*

---

## 7. Pretvorba časa v intervale

### Časovni indeks iz ure in minute (format HH:MM)

$$i = 4 \cdot h + \left\lfloor \frac{m}{15} \right\rfloor$$

### Časovni indeks iz decimalne ure

$$i = 4 \cdot \lfloor t \rfloor + \left\lceil \frac{(t - \lfloor t \rfloor) \cdot 60}{15} \right\rceil$$

**Spremenljivke:**
- $h$ — ura (0–23)
- $m$ — minuta (0–59)
- $t$ — čas v decimalnih urah (npr. 7.5 = 07:30)
- $i \in [0, 95]$ — indeks 15-minutnega intervala v dnevu (skupaj 96 intervalov)

**Razlaga:** Celoten dan je razdeljen na 96 enakih 15-minutnih intervalov (24 ur × 4 intervali/uro). Da se datumi in časi iz podatkov NHTS prevedejo v matrični indeks, se hora in minuta prevedeta v zaporedni interval. Ta indeks se nato uporablja za indeksiranje vseh matrik stanj, razdalj in polnjenja.

*Izvorna datoteka: [pipeline/Functions_step_1.py:97–167](../pipeline/Functions_step_1.py)*

---

## 8. Dosegljivostni prstan (Haversine Ring)

### Maksimalna in minimalna dosegljiva razdalja

$$r_{\max} = \frac{\Delta t \cdot v}{60}, \qquad r_{\min} = \max\!\left(0,\; \frac{(\Delta t - 5) \cdot v}{60}\right)$$

**Spremenljivke:**
- $\Delta t$ — razpoložljivi čas potovanja (minute, iz podatkov o potovanju)
- $v = 30\,\text{km/h}$ — povprečna hitrost v mestnem prometu (privzeto)
- $r_{\max}$ — maksimalni doseg v km
- $r_{\min}$ — minimalni doseg v km (5-minutni varnostni odmik)

**Razlaga:** Namesto klica zunanjega API-ja za izohorone (iso-chronous contours) se dosegljivo območje oceni s preprostim haversinskim obročem. Vse destinacije, ki ležijo v krogu med $r_{\min}$ in $r_{\max}$ od izhodišča, se štejejo za dosegljive v danem času potovanja. Privzeta hitrost 30 km/h je konzervativna ocena za mestno in primestno vožnjo.

*Izvorna datoteka: [pipeline/Functions_step_2.py:1007–1008](../pipeline/Functions_step_2.py)*

---

## 9. Poraba energije

### Stohastična poraba na potovanje

$$E = d \cdot \eta, \quad \eta \sim \mathcal{N}(0.17,\; 0.02)$$

**Spremenljivke:**
- $d$ — razdalja potovanja (km), pridobljena iz OpenRouteService API
- $\eta$ — specifična poraba energije (kWh/km); naključno vzorčena iz normalne porazdelitve
- $\mu_\eta = 0.17\,\text{kWh/km}$ — povprečna specifična poraba
- $\sigma_\eta = 0.02\,\text{kWh/km}$ — standardni odklon (variabilnost med vožnjami)
- $E$ — skupna poraba energije za potovanje (kWh)

**Razlaga:** Poraba električne energije na enoto razdalje ni konstantna — odvisna je od stila vožnje, profila ceste, podnebnih razmer in obremenitve vozila. Modelirana je z normalno porazdelitvijo s povprečjem 0.17 kWh/km (tipično za manjše električno vozilo) in standardnim odklonom 0.02 kWh/km. Vsako potovanje dobi svojo naključno vrednost $\eta$, kar uvede realistično variabilnost v skupno porabo energije.

*Izvorna datoteka: [pipeline/Step_2_prod.py:230–231](../pipeline/Step_2_prod.py)*

---

## 10. Razdalja na 15-minutni interval

### Enakomerna razporeditev razdalje po intervalih

$$d_{\text{interval}} = \frac{d_{\text{skupaj}}}{n_{\text{intervalov}}}$$

kjer je $n_{\text{intervalov}} = i_{\text{konec}} - i_{\text{start}}$

**Spremenljivke:**
- $d_{\text{skupaj}}$ — skupna razdalja potovanja (km)
- $i_{\text{start}}, i_{\text{konec}}$ — začetni in končni indeks 15-minutnega intervala
- $n_{\text{intervalov}}$ — število 15-minutnih intervalov, ki jih potovanje zasede
- $d_{\text{interval}}$ — razdalja, ki jo vozilo prevozi v vsakem 15-minutnem intervalu

**Razlaga:** Za namen simulacije na ravni matrice stanj se skupna razdalja potovanja enakomerno porazdeli po vseh 15-minutnih intervalih, ki jih potovanje pokriva. S tem se predpostavi enakomerna hitrost vožnje znotraj potovanja. Ta vrednost se shranjuje v matriko `vehicle_distance`, ki opisuje kilometer po kilometer gibanje vsake vozila skozi dan.

*Izvorna datoteka: [pipeline/Step_3_prod.py:74](../pipeline/Step_3_prod.py)*

---

## 11. Meje moči polnjenja

### Minimalna in maksimalna moč polnjenja med parkiranjem pri delu

$$P_{\min} = \min\!\left(\frac{E_{\text{prihod}}}{\Delta t_{\text{park}}},\; P_{\max}^{\text{polnilec}}\right)$$

$$P_{\max} = \min\!\left(\frac{E_{\text{prihod}} + E_{\text{naslednje}}}{\Delta t_{\text{park}}},\; P_{\max}^{\text{polnilec}}\right)$$

kjer je $\Delta t_{\text{park}} = (i_{\text{odhod}} - i_{\text{prihod}}) \cdot 0.25\,\text{h}$

**Spremenljivke:**
- $E_{\text{prihod}}$ — energija, porabljena na potovanju do dela (kWh); minimum, ki ga je treba napolniti
- $E_{\text{naslednje}}$ — vsota energij vseh naslednjih potovanj pred prihodom domov (kWh)
- $\Delta t_{\text{park}}$ — čas parkiranja pri delu (ure)
- $P_{\max}^{\text{polnilec}} = 11\,\text{kW}$ — maksimalna moč AC polnilca (fizična omejitev)
- $P_{\min}$ — najmanjša povprečna moč polnjenja (kW), potrebna za zagotovitev povratka
- $P_{\max}$ — največja povprečna moč polnjenja (kW), da se napolni za vse preostale vožnje

**Razlaga:** Med parkiranjem pri delu ima vozilo priložnost za polnjenje. Minimalna moč je tista, ki je nujno potrebna, da vozilo po delovniku sploh pride domov (pokrije vsaj energijo prihoda). Maksimalna moč pokriva tudi vse nadaljnje vožnje tega dne. Obe vrednosti sta omejeni z zmogljivostjo fizičnega polnilca (11 kW). Ta interval $[P_{\min}, P_{\max}]$ definira razpon prožnosti za upravljanje obremenitev.

*Izvorna datoteka: [app/simulation.py:197–204](../app/simulation.py)*

---

## 12. Kumulativna prožnost SoC

### Časovni razvoj prožnosti stanja napolnjenosti

$$\text{flex}^+(t) = \sum_{\tau=0}^{t} \delta^+(\tau), \qquad \text{flex}^-(t) = \sum_{\tau=0}^{t} \delta^-(\tau)$$

kjer velja za vsako vozilo $v$, ki prispe na delo ob $t_s$ in odide ob $t_e$:

$$\delta^+(t_s) \mathrel{+}= P^+_v, \quad \delta^+(t_e) \mathrel{-}= P^+_v$$
$$\delta^-(t_s) \mathrel{+}= P^-_v, \quad \delta^-(t_e) \mathrel{-}= P^-_v$$

**Spremenljivke:**
- $P^+_v$ — pozitivna prožnost vozila $v$ (kWh): koliko dodatne energije bi lahko sprejelo
- $P^-_v$ — negativna prožnost vozila $v$ (kWh): koliko energije bi lahko vrnilo v omrežje
- $\delta^+, \delta^-$ — diferencialni vektorji sprememb prožnosti
- $\text{flex}^+(t), \text{flex}^-(t)$ — kumulativna pozitivna in negativna prožnost v trenutku $t$

**Razlaga:** Kumulativna prožnost SoC (State of Charge) kaže, koliko energije bi celotna flota EV-jev v danem trenutku potencialno lahko sprejela (pozitivna prožnost — V2G shranjevanje) ali oddala (negativna prožnost — G2V). Ko vozilo prispe na delovno mesto, se prožnost poveča; ko odpelje, se zmanjša. Kumulativna vsota daje skupno razpoložljivo prožnost flote v vsakem 15-minutnem intervalu.

*Izvorna datoteka: [app/simulation.py:239–277](../app/simulation.py)*

---

## 13. Linearna interpolacija položaja

### Položaj vozila med vožnjo

$$\mathbf{x}(t) = (1-\alpha)\,\mathbf{x}_{\text{start}} + \alpha\,\mathbf{x}_{\text{end}} + \boldsymbol{\varepsilon}, \quad \alpha = \frac{t - t_s}{t_e - t_s}$$

kjer je $\boldsymbol{\varepsilon} \sim \mathcal{N}(\mathbf{0},\; (5 \times 10^{-5})^2 \mathbf{I})$

**Spremenljivke:**
- $\mathbf{x}_{\text{start}} = (\lambda_s, \varphi_s)$ — koordinate izhodišča (lon, lat)
- $\mathbf{x}_{\text{end}} = (\lambda_e, \varphi_e)$ — koordinate cilja (lon, lat)
- $t_s, t_e$ — začetni in končni indeks intervala potovanja
- $\alpha \in [0, 1]$ — napredek potovanja
- $\boldsymbol{\varepsilon}$ — majhen Gaussov šum (v stopinjah) za vizualni realizem
- $\mathbf{x}(t)$ — interpoliran položaj vozila v intervalu $t$

**Razlaga:** Za animacijo na zemljevidu moramo vedeti, kje je vsako vozilo v vsakem 15-minutnem intervalu. Med potovanjem se položaj linearno interpolira med izhodiščem in ciljem. Majhen naključni šum $\boldsymbol{\varepsilon}$ (reda velikosti ~5 m) prepreči, da bi se vsa vozila, ki potujejo po isti poti, popolnoma prekrivala — doda vizualno raznolikost brez izgube informacij.

*Izvorna datoteka: [app/simulation.py:163–168](../app/simulation.py)*

---

## 14. Dodelitev profilov voznikov

### Multinomialno vzorčenje

$$\text{profil}_v \sim \text{Categorical}(\mathbf{p}), \quad \mathbf{p} = [p_C, p_R, p_N]$$

Na podlagi podatkov SiStat za občino Krško (1. 1. 2025):

$$p_C = \frac{11748}{26175} \approx 0.449, \quad p_R = \frac{5654}{26175} \approx 0.216, \quad p_N = \frac{8773}{26175} \approx 0.335$$

**Spremenljivke:**
- $p_C$ — delež zaposlenih voznikov (Commuter)
- $p_R$ — delež upokojencev (Retired, 65+ let)
- $p_N$ — delež ostalih (Nonccommuter: otroci 0–14 in neaktivni 15–64)
- $\text{profil}_v$ — naključno dodeljen profil vozila $v$

**Razlaga:** Vsako vozilo v simulaciji dobi profil voznika, ki določa, katere vrste aktivnosti so mu dovoljene in ali mora imeti potovanje na delo. Deleži profilov temeljijo na dejanskih demografskih podatkih za občino Krško iz statističnega urada (SiStat). Vzorčenje je neodvisno za vsako vozilo, kar pomeni, da se pri dovolj velikem vzorcu flota statistično ujema z dejansko demografijo.

*Izvorna datoteka: [pipeline/Step_1_prod.py:76–99](../pipeline/Step_1_prod.py)*

---

## 15. Skaliranje mas za gravitacijo

### Normalizacija površin na skupno lestvico

$$M_j = \begin{cases} \text{round}\!\left(A_j \cdot \dfrac{5000}{A_{\max}}\right) & \text{če } A_j > 0 \\ 500 & \text{sicer} \end{cases}$$

**Spremenljivke:**
- $A_j$ — površina poligona destinacije $j$ v m² (koordinatni sistem EPSG:3857)
- $A_{\max} = \max_k A_k$ — maksimalna površina med vsemi destinacijami tega tipa
- $M_j$ — normalizirana masa destinacije $j$ (brez enote, lestvica 0–5000)
- 500 — privzeta masa za točkovne objekte brez površine (npr. posamezne stavbe)

**Razlaga:** Različne OSM (OpenStreetMap) geometrije imajo zelo različne površine — od majhnih točkovnih objektov do velikih industrijskih con. Da bi imel gravitacijski model primerljive uteži za vse destinacije, se površine normalizirajo tako, da je največja vrednost enaka 5000. Točkovni objekti (ki nimajo površine) dobijo privzeto vrednost 500, ki je 10× manjša od maksimuma, da niso preveč dominantni.

*Izvorna datoteka: [pipeline/Functions_step_1.py:69–76](../pipeline/Functions_step_1.py)*

---

## 16. Skupna obremenitev polnjenja flote

### Seštevek posameznih vozil po intervalih

$$P_{\text{fleet,min}}(t) = \sum_{v=1}^{N} P_{\text{min},v}(t), \qquad P_{\text{fleet,max}}(t) = \sum_{v=1}^{N} P_{\text{max},v}(t)$$

**Spremenljivke:**
- $N$ — skupno število vozil v simulaciji
- $P_{\text{min},v}(t)$ — spodnja meja moči polnjenja vozila $v$ v intervalu $t$ (kW), izračunana po enačbi 11
- $P_{\text{max},v}(t)$ — zgornja meja moči polnjenja vozila $v$ v intervalu $t$ (kW)
- $P_{\text{fleet,min}}(t),\, P_{\text{fleet,max}}(t)$ — skupna minimalna/maksimalna moč polnjenja celotne flote (kW) v intervalu $t$

**Razlaga:** Vsak vozilo, ki je parkirano pri delu, prispeva svojo moč polnjenja (interval $[P_{\text{min}}, P_{\text{max}}]$) v skupno obremenitev omrežja. Z vsoto po vseh vozilih dobimo skupno krivuljo obremenitve omrežja za celotno floto. To sta dve krivulji — minimalna (osnovna obremenitev, ki je nujno potrebna) in maksimalna (največja možna, če bi se vse polnilo hkrati). Razlika med njima je razpon prožnosti, ki je na voljo za upravljanje omrežja (V2G/G2V).

*Izvorna datoteka: [app/simulation.py:67–70](../app/simulation.py)*

---

## 17. Histogram prihodov in odhodov s parkirišča

### Detekcija prehodov stanj

$$\text{arr}(t) = \sum_{v=1}^{N} \mathbf{1}\!\left[\,\text{tip}_{v,\,t-1} = \text{Driving} \;\land\; \text{tip}_{v,\,t} = \text{Work}\,\right]$$

$$\text{dep}(t) = \sum_{v=1}^{N} \mathbf{1}\!\left[\,\text{tip}_{v,\,t-1} = \text{Work} \;\land\; \text{tip}_{v,\,t} = \text{Driving}\,\right]$$

**Spremenljivke:**
- $\text{tip}_{v,t}$ — vrsta aktivnosti vozila $v$ v intervalu $t$ (niz: `"Driving"`, `"Work"`, `"Home"`, ...)
- $\mathbf{1}[\cdot]$ — indikatorska funkcija (1, če pogoj velja; 0 sicer)
- $\text{arr}(t)$ — število vozil, ki so prispela na delovno parkirišče v intervalu $t$
- $\text{dep}(t)$ — število vozil, ki so zapustila delovno parkirišče v intervalu $t$

**Razlaga:** Diagram prihodov in odhodov prikazuje prometni tok na delovnem parkirišču čez dan. Prihod se zabeleži, ko vozilo v zaporednih intervalih preide iz stanja vožnje (`Driving`) v stanje dela (`Work`). Odhod se zabeleži pri obratnem prehodu. Oba histograma se narisujeta na stolpičnem grafu v nadzorni plošči in skupaj kažeta "konico" prihajanja zjutraj ter odhajanja popoldne.

*Izvorna datoteka: [app/simulation.py:210–215](../app/simulation.py)*

---

## 18. Uteži toplotne karte gostote vozil

### Diferencialne uteži glede na stanje gibanja

$$w_v(t) = \begin{cases} 0.05 & \text{če } \text{tip}_{v,t} = \text{Driving} \\ 2.5 & \text{sicer (parkirano)} \end{cases}$$

**Spremenljivke:**
- $\text{tip}_{v,t}$ — aktivnost vozila $v$ v intervalu $t$
- $w_v(t)$ — utež vozila $v$ pri izgradnji toplotne karte (brez enote)
- Razmerje uteži parkirano/vozeče: $2.5 / 0.05 = 50$

**Razlaga:** Toplotna karta (density heatmap) prikazuje, kje se vozila v danem trenutku zbirajo. Parkirana vozila dobijo 50× večjo utež od vozečih, ker so prostorsko stabilna in bolj zanimiva za analizo obremenitve omrežja. Vozeča vozila prispevajo minimalno utež (0.05), da ostanejo vidna na karti, ne pa da dominirajo nad parkirnimi lokacijami. Algoritem Plotly potem na osnovi teh uteži izračuna gostoto z Gaussovim jedrom polmera 55 px.

*Izvorna datoteka: [app/charts.py:99–103](../app/charts.py)*

---

## 19. Skaliranje vizualnega ozračja delovnega mesta

### Velikost indikatorja glede na zasedenost

$$\text{size}(t) = 18 + 4 \cdot n_{\text{work}}(t)$$

kjer je $n_{\text{work}}(t) = \sum_{v=1}^{N} \mathbf{1}\!\left[\text{tip}_{v,t} = \text{Work}\right]$

**Spremenljivke:**
- $n_{\text{work}}(t)$ — število vozil, parkiranih pri delu v intervalu $t$
- $18$ — bazna velikost kroga (px), vidna tudi pri 0 vozilih
- $4$ — linearni koeficient povečevanja na vozilo (px/vozilo)
- $\text{size}(t)$ — premer vizualnega glow-indikatorja na zemljevidu (px)

**Razlaga:** Na interaktivnem zemljevidu se delovno mesto označi z zelenim "sijajem" (glow), ki se povečuje sorazmerno s številom trenutno parkiranih vozil. Ko je parkirišče prazno, ostane bazni krog velikosti 18 px. Za vsako dodano vozilo se premer poveča za 4 px, kar omogoča intuitiven vizualni prikaz obremenjenosti parkirišča brez gledanja v graf.

*Izvorna datoteka: [app/charts.py:135](../app/charts.py)*

---

## 20. Začetno stanje napolnjenosti baterije

### Enakomerna naključna porazdelitev

$$\text{SoC}_{v,0} \sim U(60\%,\; 80\%), \quad v = 1, \ldots, N$$

**Spremenljivke:**
- $\text{SoC}_{v,0}$ — začetni SoC vozila $v$ ob $t=0$ (%)
- $U(a,b)$ — enakomerna porazdelitev na intervalu $[a, b]$
- $N$ — število vozil

**Razlaga:** Pred začetkom dneva vsako vozilo dobi naključen začetni SoC, vzorčen iz enakomerne porazdelitve med 60 % in 80 %. Ta razpon ustreza "delno napolnjenim" baterijam, ki so tipične za vozila ob začetku delovnika po polnočnem polnjenju. Vrednosti zunaj tega razpona (npr. 100 % ali 20 %) so namerno izključene, ker bi vodile do nerealistično visoke ali nizke prožnosti.

*Izvorna datoteka: [pipeline/Step_4_prod.py:78–82](../pipeline/Step_4_prod.py)*

---

## 21. Simulacija stanja napolnjenosti (SoC)

### Rekurzivna poraba baterije po intervalih

$$\text{SoC}_{v,t} = \max\!\left(\text{SoC}_{v,t-1} - \frac{E_{v,t}}{C_v} \cdot 100,\; 0\right)$$

kjer je $E_{v,t}$ energija, porabljena med vožnjo v intervalu $t$ (kWh):

$$E_{v,t} = \frac{E_{\text{potovanje}}}{n_{\text{intervalov}}}$$

**Spremenljivke:**
- $\text{SoC}_{v,t}$ — stanje napolnjenosti vozila $v$ ob koncu intervala $t$ (%)
- $E_{v,t}$ — energija, porabljena v 15-minutnem intervalu $t$ (kWh)
- $C_v = 72\,\text{kWh}$ — kapaciteta baterije vozila $v$ (privzeto enakomerna za vso floto)
- $\max(\cdot, 0)$ — spodnja meja pri 0 % (fizična omejitev — baterija ne more biti negativna)
- $E_{\text{potovanje}}$ — skupna energija potovanja (kWh), izračunana v koraku 2 ($E = d \cdot \eta$)
- $n_{\text{intervalov}}$ — število intervalov, ki jih potovanje zasede

**Razlaga:** SoC se simulira korak za korakom čez dan: pri vsakem 15-minutnem intervalu se odšteje energija, ki jo vozilo porabi med vožnjo (porazdeljeno enakomerno po intervalih potovanja). Ko vozilo miruje, se SoC ne zmanjšuje (polnjenje ni modelirano v tej fazi — dobimo konzervativno oceno od spodaj). Vrednost se ne sme spustiti pod 0 %, kar se modelira z max-funkcijo.

*Izvorna datoteka: [pipeline/Functions_step_4.py:132–167](../pipeline/Functions_step_4.py)*

---

## 22. Pozitivna in negativna prožnost SoC

### Razpoložljiva energija glede na pragove SoC

$$F^+_{v,t} = \max\!\left(\frac{\text{SoC}_{v,t} - \text{SoC}_{\min}}{100} \cdot C_v,\; 0\right)$$

$$F^-_{v,t} = \max\!\left(\frac{\text{SoC}_{\max} - \text{SoC}_{v,t}}{100} \cdot C_v,\; 0\right)$$

**Spremenljivke:**
- $F^+_{v,t}$ — pozitivna prožnost vozila $v$ v intervalu $t$ (kWh): energija, ki je na voljo za oddajo v omrežje (V2G)
- $F^-_{v,t}$ — negativna prožnost vozila $v$ v intervalu $t$ (kWh): energija, ki jo baterija še lahko sprejme (G2V)
- $\text{SoC}_{\min} = 20\,\%$ — spodnji prag SoC (varnostna rezerva — vozilo mora ohraniti vsaj 20 %)
- $\text{SoC}_{\max} = 80\,\%$ — zgornji prag SoC (zaščita baterije pred prepolnitvijo)
- $C_v = 72\,\text{kWh}$ — kapaciteta baterije

**Razlaga:** Prožnost opisuje, koliko energije je vsako vozilo v danem trenutku sposobno oddati ali sprejeti. Pozitivna prožnost $F^+$ je energija med trenutnim SoC in spodnjo varnostno mejo 20 % — toliko bi vozilo teoretično lahko oddalo v omrežje (V2G), ne da bi ostalo brez dovolj energije za povratek. Negativna prožnost $F^-$ je energija med trenutnim SoC in zgornjo mejo 80 % — toliko bi baterija še lahko sprejela brez škodljivega prepolnjenja. Obe vrednosti sta odrezani pri 0 (vrednosti izven praga kažejo presežek/primanjkljaj, ki se ne upošteva).

*Izvorna datoteka: [pipeline/Functions_step_4.py:172–201](../pipeline/Functions_step_4.py)*

---

## 23. Prostorska mrežna analiza — dodelitev celice

### Indeks mrežne celice iz geografskih koordinat

$$r = \left\lfloor \frac{d_{\text{lat}}(\lambda, \varphi_{\min}, \lambda, \varphi)}{\Delta d} \right\rfloor, \qquad c = \left\lfloor \frac{d_{\text{lon}}(\lambda_{\min}, \varphi, \lambda, \varphi)}{\Delta d} \right\rfloor$$

### Koordinate središča celice

$$\varphi_{\text{center}} = \varphi_{\min} + \frac{(r + 0.5) \cdot \Delta d}{111}, \qquad \lambda_{\text{center}} = \lambda_{\min} + \frac{(c + 0.5) \cdot \Delta d}{111 \cdot \cos \varphi_{\min}}$$

**Spremenljivke:**
- $r, c$ — vrstični in stolpični indeks mrežne celice
- $\varphi, \lambda$ — geografska širina in dolžina točke (stopinje)
- $\varphi_{\min} = 45.92°$, $\lambda_{\min} = 15.45°$ — jugozahodni kot območja Krško
- $\Delta d = 0.5\,\text{km}$ — prostorska ločljivost mrežne celice
- $d_{\text{lat}}, d_{\text{lon}}$ — haversinova razdalja v km vzdolž meridiana/vzporednika
- $111\,\text{km/°}$ — standardna pretvorba stopinj v km vzdolž meridiana

**Razlaga:** Za prostorsko analizo aktivnosti EV-jev se območje Krško razdeli na mrežo kvadratnih celic s stranico 0,5 km. Vsaka koordinata (začetek/konec potovanja) se preslika v indeks celice z Haversinovo razdaljo od jugo-zahodnega roba mrežne mreže. To omogoča aggregiranje vseh potovanj po prostorskih celicah — koliko prihodov, odhodov in kWh energije je bilo pri kateri celici. Koordinate središča celice se izračunajo za označevanje osi in izvoz.

*Izvorna datoteka: [pipeline/Step_4_analysis.py:32–43](../pipeline/Step_4_analysis.py)*

---

## 24. Skupna energija in neto pretok po coni

### Agregacija potovanj po prostorskih celicah

$$E_{\text{zona}}(z) = \sum_{\substack{p:\; \text{cell}(\varphi_e^p, \lambda_e^p) = z}} E_p$$

$$\Phi_{\text{neto}}(z) = \text{prihodi}(z) - \text{odhodi}(z)$$

kjer je $\text{prihodi}(z) = \bigl|\{p : \text{cell}(\varphi_e^p, \lambda_e^p) = z\}\bigr|$ in $\text{odhodi}(z) = \bigl|\{p : \text{cell}(\varphi_s^p, \lambda_s^p) = z\}\bigr|$

**Spremenljivke:**
- $z$ — identifikator prostorske mrežne celice $(r, c)$
- $E_p$ — poraba energije potovanja $p$ (kWh), iz koraka 2
- $(\varphi_e^p, \lambda_e^p)$ — koordinate cilja potovanja $p$
- $(\varphi_s^p, \lambda_s^p)$ — koordinate izhodišča potovanja $p$
- $E_{\text{zona}}(z)$ — skupna energija, "dostavljene" v cono $z$ (kWh)
- $\Phi_{\text{neto}}(z)$ — neto pretok vozil v coni $z$; pozitiven = ponor (privlačna cona), negativen = izvir

**Razlaga:** Prostorska analiza odgovori na vprašanje: "Kateri deli Krška so energetsko najbolj obremenjeni?" Za vsako cono se seštejejo vse energije potovanj, ki so se tam končala (ker tam vozilo potrebuje polnjenje). Neto pretok pokaže, ali je cona pretežno "ponor" (kamor ljudje prihajajo — npr. delovna cona) ali "izvir" (odkoder odhajajo — npr. stanovanjska cona). Rezultat se shrani in razvrsti po skupni energiji za identifikacijo kritičnih con v omrežju.

*Izvorna datoteka: [pipeline/Step_4_analysis.py:65–82](../pipeline/Step_4_analysis.py)*

---

## Povzetek po korakih cevovoda

| Korak | Datoteka | Ključne enačbe |
|-------|----------|----------------|
| **Korak 1** — Generiranje potovanj | `Step_1_prod.py` | Markovska veriga, Gaussova mešanica odhodov, eksponentna porazdelitev trajanja, dodelitev profilov |
| **Korak 2** — Določanje lokacij | `Step_2_prod.py` | Gravitacijski model, Haversinov prstan, poraba energije |
| **Korak 3** — Parametri vozil | `Step_3_prod.py` | Razdalja na interval |
| **Pomožne funkcije** | `Functions_step_1.py` | Haversinova razdalja, kombinacija Markova in gravitacije, skaliranje mas |
| **Pomožne funkcije** | `Functions_step_2.py` | Gravitacijska destinacija, Haversinov prstan, haversinova razdalja |
| **Vizualizacija** | `app/simulation.py` | Meje polnjenja, kumulativna prožnost, linearna interpolacija, seštevek obremenitve flote, histogram prihodov/odhodov |
| **Vizualizacija** | `app/charts.py` | Uteži toplotne karte, skaliranje ozračja delovnega mesta |
| **Korak 4** — SoC simulacija | `Step_4_prod.py`, `Functions_step_4.py` | Začetni SoC, rekurzivna simulacija SoC, pozitivna/negativna prožnost |
| **Korak 4** — Prostorska analiza | `Step_4_analysis.py` | Mrežna dodelitev celic, skupna energija po coni, neto pretok |
