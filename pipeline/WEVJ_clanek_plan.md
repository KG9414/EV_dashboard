# Plan za WEVJ članek — dve različici

Preverjeno pred pisanjem: metodologija je v celoti dokumentirana (`docs/EQUATIONS.md`), obstaja validacijska primerjava modela A/B (`analysis/comparison_AB/`), Streamlit orodje deluje, in obstajajo že generirani SoC-flex podatki za več velikosti flote — vključno s ciljno skalo **824 vozil** (`scenarios/scenario_new_824/04_SoC_flexibility/`) in celo 1344 vozil. Te podatke še nisem analizirala — vem samo, da datoteke obstajajo, ne kaj kažejo. Poglavje 5 (Rezultati) v nalogi še ni napisano (po `NACRT_PISANJA.md` je na vrsti šele ~27. jul–2. avg).

To je razlog za dve ločeni verziji: ena je gradljiva takoj, druga zahteva analitično delo, ki še ni opravljeno.

---

## Plan A — Sintetični članek (metoda/orodje kot prispevek)

**Delovni naslov:** *An Open-Data Mobility and SoC Simulation Pipeline for V2G Flexibility Estimation in Data-Scarce Municipalities: A Krško Case Study*

**Osrednja ideja:** Prispevek je cevovod sam — Markov+gravitacijski model mobilnosti (NHTS) + 15-min SoC/prožnostni pogon + odprto vizualizacijsko orodje — kot poceni, prenosljiva alternativa zaprtim komercialnim platformam (EPIOT, PFM) za občine brez telematskih/pametnih-merilnih podatkov. Krško je demonstracijski primer, ne glavna ugotovitev. Validacija (A/B primerjava, KS/Wasserstein/JSD) je dokaz metodološke trdnosti.

**Skica strukture (~10–12 str.):**
1. Uvod — vrzel: občine brez flotnih podatkov ne morejo oceniti V2G prožnosti
2. Sorodno delo — EPIOT, PFM, kratek pregled
3. Metodologija — arhitektura cevovoda (strnjeno iz EQUATIONS.md: Markov, gravitacija, kombinacija, SoC rekurzija, F+/F-)
4. Validacija — A/B statistike → cevovod generira realistične vzorce mobilnosti
5. Demonstracija — Krško, ena prožnostna krivulja, DomCenter kot izhod
6. Razprava — omejitve (NHTS=ZDA podatki, fiksni 2 poti/dan, OSM pokritost), prenosljivost
7. Zaključek

**5 slik:**
1. Diagram arhitekture cevovoda (Step 0→4) — **ne obstaja, je treba narisati**
2. Validacijski panel — obstaja (`analysis/comparison_AB/figures/`), potrebno preoblikovanje za tisk
3. Prostorska karta gostote destinacij Krško — obstaja (`prostorska_B_krsko.png`) ali svež posnetek Streamlit toplotne karte
4. Ena ponazoritvena krivulja prožnosti (824 vozil, en scenarij) — podatki obstajajo, a **niso analizirani**; uporabljeno kot demonstracija, ne kot glavna trditev
5. Posnetek zaslona DomCenter orodja — **potreben svež screenshot**

**Tveganje:** nizko. Vse gradnike razen diagrama (1) in ene krivulje (4) že imaš; krivulja (4) je ena sama grafa, ne zahteva analize po scenarijih.

**Naslednji korak, če izbereš to:** zgraditi diagram cevovoda + izbrati/preoblikovati validacijske slike + izrisati eno flex-krivuljo iz `scenario_new_824` + posneti svež screenshot orodja.

---

## Plan B — Analitični članek (rezultati kot prispevek)

**Delovni naslov:** *Quantifying Vehicle-to-Grid Flexibility of a Semi-Rural EV Fleet Across Penetration Scenarios: Evidence from Krško, Slovenia*

**Osrednja ideja:** Prispevek je kvantificirana ugotovitev — koliko pozitivne/negativne prožnosti (kWh) je na voljo, kdaj čez dan, in kako se to skalira z deležem EV penetracije (obstoječi scenariji nakazujejo tier-je pri 20/100/824/1344 vozilih). Metoda je opisana skopo, kot instrument, ne kot sporočilo.

**Skica strukture:**
1. Uvod — občinsko načrtovanje omrežja potrebuje številke, ne le orodje
2. Metodologija — strnjeno (SoC/flex enačbe, definicija penetracijskih tier-jev)
3. Rezultati — osrednji del: flex krivulje po tier-jih, čas vrha prožnosti, prispevek na vozilo, občutljivost na penetracijo
4. Razprava — pomen za omrežno načrtovanje Krškega, primerjava z literaturo (če obstaja)
5. Zaključek

**5 slik:**
1. Krivulja pozitivne/negativne prožnosti flote čez dan, primerjava 2–3 tier-jev (glavna slika) — **zahteva analizo obstoječih xlsx datotek, ni narejena**
2. Prispevek prožnosti po profilu voznika (Commuter/Retired/Noncommuter) — **ne vem, ali podatki to sploh podpirajo v trenutni obliki, treba preveriti**
3. Časovni potek/trajanje vrha prožnosti (koliko ur/dan flex presega prag) — izpeljana analiza, ni narejena
4. Občutljivost: skupna dnevna kWh prožnost vs. velikost flote/penetracija (uporabi 20/100/824/1344) — zahteva analizo med scenariji
5. Prostorska/conska razčlenitev prožnosti (katere cone prispevajo največ) — deloma se navezuje na `zone_flex_pos/neg` iz V2G tool plana (delno implementirano)

**Tveganje:** visoko dokler se ne opravi dejanska analiza. Ne vem, kaj ti podatki pravzaprav kažejo — možno je, da rezultati niso dovolj "čisti" ali zanimivi za samostojen članek brez dodatnega dela (npr. dodatnih scenarijev, čiščenja robnih primerov).

**Naslednji korak, če izbereš to:** najprej dejansko odpreti in analizirati `04_SoC_flex_timeseries_*` datoteke za 20/100/824/1344 vozil, preden se karkoli trdi o slikah — šele takrat vemo, ali je zgodba analitičnega članka sploh nosilna.

---

## Priporočilo za vzporedno delo zdaj

Ker želiš začeti takoj, vzporedno z nalogo: Plan A je gradljiv brez čakanja na Poglavje 5 in brez tveganja fabrikacije podatkov. Plan B lahko teče vzporedno kot **raziskovalna naloga**, ne kot pisanje — najprej analiza podatkov, šele nato odločitev, ali je zgodba dovolj močna za članek. Ti dve poti se lahko kasneje združita (hibridni članek), a le če analiza B dejansko obrodi jasen rezultat.
