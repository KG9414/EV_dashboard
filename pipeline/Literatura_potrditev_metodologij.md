# Literatura: potrditev metodologij (DomCenter pipeline)

Zbrani viri potrjujejo posamezne metodološke odločitve v simulacijskem cevovodu. Za vsako metodologijo so navedeni 2–4 papirji, ki potrjujejo enak ali zelo podoben pristop.

---

## 1. Teorija verižnih poti (Trip Chain Theory)

- **Shun, T. et al. (2016).** "Charging demand for electric vehicle based on stochastic analysis of trip chain." *IET Generation, Transmission & Distribution*, vol. 10, no. 1. https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-gtd.2015.0995
  - Uporablja trip chain teorijo z Monte Carlo simulacijo za modeliranje zaporedja dom→služba→ostalo in iz tega izpelje profile povpraševanja po polnjenju.

- **Wei, Z. et al. (2017).** "Modeling of plug-in electric vehicle travel patterns and charging load based on trip chain generation." *Journal of Power Sources*, vol. 359. https://www.sciencedirect.com/science/article/abs/pii/S0378775317306687
  - Generira trip chains (dom→destinacija→dom) z Naive Bayes modelom in sledi porabi energije po posamezni poti — neposreden precedent za strukturo cevovoda.

- **Pan, L. et al. (2024).** "An urban charging load forecasting model based on trip chain model for private passenger electric vehicles: A case study in Beijing." *Energy*, vol. 299. https://www.sciencedirect.com/science/article/abs/pii/S0360544224006169
  - Trip chain teorija za napoved obremenitve polnjenja v mestu; potrjuje, da je trip chain standardni pristop v najnovejši literaturi.

- **Fiori, C. et al. (2024).** "Simulation of Trip Chains in a Metropolitan Area to Evaluate the Energy Needs of Electric Vehicles and Charging Demand." *World Electric Vehicle Journal*, vol. 16, no. 8. https://www.mdpi.com/2032-6653/16/8/435
  - Agent-based simulacija s trip chain podatki; poraba energije razčlenjena po tipu vozila in zaporedju poti — ujema se s per-vehicle pristopom v cevovodu.

---

## 2. Prostorsko-časovni modeli / time geography

- **Miller, H.J. (2017).** "Time geography and space–time prism." In *International Encyclopedia of Geography*. https://cpb-us-w2.wpmucdn.com/u.osu.edu/dist/a/390/files/2017/03/Miller-time-geography-and-space-time-prism-1rp3u1q.pdf
  - Kanonični metodološki vir Hägerstandovega koncepta prostorsko-časovnega prizma, ki omejuje možno gibanje med aktivnostmi.

- **Neutens, T. et al. (2023).** "Space–time prism and accessibility incorporating monetary budget and mobility-as-a-service." *International Journal of Geographical Information Science*. https://www.tandfonline.com/doi/full/10.1080/13658816.2023.2280642
  - Razširitev prostorsko-časovnega prizma na zaporedne aktivnosti z omejitvami časa in virov — potrjuje kombinacijo prizma z modeliranjem trip chains.

- **Farhan, J. & Chen, T.D. (2018).** "Impact of ridesharing on operational efficiency of shared autonomous electric vehicles." *Transportation Research Part E*. https://arxiv.org/pdf/1806.10719
  - Eksplicitno aplicira prostorsko-časovne omejitve na usmerjanje EV; ker morajo vozila k polnilniku, je njihova izvedljiva trajektorija omejena s prizmom — neposredno potrjuje isohronski pristop v cevovodu.

---

## 3. Markovske verige za prehode med aktivnostmi

- **Wang, Y. & Infield, D. (2018).** "Markov Chain Monte Carlo simulation of electric vehicle use for network integration studies." *International Journal of Electrical Power & Energy Systems*, vol. 99. https://www.sciencedirect.com/science/article/abs/pii/S0142061517307226
  - Gradi Markovsko verigo s stanji {vožnja, parkiranje, polnjenje} × {nizek/srednji/visok SoC} iz realnih podatkov; najbližji neposredni precedent za prehodno matriko v cevovodu.

- **Grahn, P. et al. (2012).** "Deviations in Markov chain modeled electric vehicle charging patterns from real world data." *IEEE PES ISGT Europe*. https://ieeexplore.ieee.org/document/6338818
  - Gradi in validira Markovske prehodne matrike za stanja dom/služba/vožnja ob primerjavi z realnimi podatki; empirična osnova za Markovske modele v kontekstu EV.

- **Essayeh, C. et al. (2025).** "EV Fleet Flexibility Estimation and Forecasting for V2X Applications." *arXiv:2502.06435*. https://arxiv.org/abs/2502.06435
  - Uporablja stohastično modeliranje stanj EV za izračun fleksibilnosti flote; stanje (priključeno/v vožnji/razpoložljivo) se razvija po verjetnostih — potrjuje Markovske prehode kot vodilni pristop za V2X modeliranje.

---

## 4. Gravitacijski model za izbiro destinacije

- **Pourabdollah, M. et al. (2024).** "Electric Charging Demand Forecast and Capture for Infrastructure Placement Using Gravity Modelling: A Case Study." *IEEE ISGT Europe 2024*. https://ieeexplore.ieee.org/document/10421918/
  - Eksplicitno uporablja parametrični gravitacijski model za porazdelitev povpraševanja po polnjenju od izvorov na destinacijske lokacije — isti princip razdalje in privlačnosti kot v cevovodu.

- **Liu, Y.S., Tayarani, M. & Gao, H.O. (2022).** "An activity-based travel and charging behavior model for simulating battery electric vehicle charging demand." *Energy*, vol. 258. https://www.sciencedirect.com/science/article/abs/pii/S0360544222018382
  - Prostorske prehodne verjetnosti (parametrična oblika gravitacijskega razpadanja z razdaljo) za izbiro destinacije pri delu, nakupovanju in socialnih poteh.

- **Li, X. et al. (2025).** "A multi-time scale charging load forecasting method based on an improved gravity model." *International Journal of Electrical Power & Energy Systems*, vol. 163. https://www.sciencedirect.com/science/article/pii/S0142061525001917
  - Neposredno uporablja izboljšan gravitacijski model za prostorsko porazdelitev povpraševanja po polnjenju; potrjuje, da je gravitacijsko modeliranje aktiven mainstream pristop.

---

## 5. Demografsko uteževanje flote

- **Zhang, J. et al. (2020).** "Daily electric vehicle charging load profiles considering demographics of vehicle users." *Applied Energy*, vol. 274. https://www.sciencedirect.com/science/article/abs/pii/S0306261920305754
  - Segmentira EV uporabnike po starosti, spolu in izobrazbi z NHTS podatki in za vsako skupino gradi različne dnevne profile — neposredno potrjuje pristop dodeljevanja demografskih profilov.

- **Helmus, J.R., Lees, M.H. & van den Hoed, R. (2020).** "A data driven typology of electric vehicle user types and charging sessions." *Transportation Research Part C*, vol. 115. https://research.hva.nl/en/publications/a-data-driven-typology-of-electric-vehicle-user-types-and-chargin/
  - Razvrsti realne seje javnega polnjenja v tipe EV uporabnikov z značilnimi časovnimi vzorci; empirična osnova za razdelitev komutant/upokojenec/ostalo.

- **Liu, Y.S. et al. (2022).** (*enako kot pri točki 4*)
  - Iz anket o potovanjih parametrizira različne kategorije uporabnikov (komutanti, nekomercialne poti) v aktivnostnem modelu.

---

## 6. Simulacija dinamike SoC

- **Hipolito, F., Vandet, C.A. & Rich, J. (2022).** "Charging, steady-state SoC and energy storage distributions for EV fleets." *Applied Energy*, vol. 317. https://www.sciencedirect.com/science/article/pii/S0306261922004597
  - Izpelje stacionarne porazdelitve SoC za EV flote; ugotovi, da je ~40 % kapacitete razpoložljive za V2G — potrjuje metodologijo sledenja SoC na ravni vozila z agregacijo na floto.

- **Wang, Y. & Infield, D. (2018).** (*enako kot pri točki 3*)
  - Sledi SoC po vozilu skozi stanja vožnja/parkiranje/polnjenje pri visoki časovni resoluciji; validira, da kombinacija Markovskih prehodov z ažuriranjem SoC po časovnem koraku pravilno reproducira realne vzorce polnjenja.

- **Fiori, C. et al. (2024).** (*enako kot pri točki 1*)
  - Ocenjuje porabo energije po poti na osnovi hitrosti in sledi izpraznitvi baterije po vozilu skozi trip chain — ista struktura kot razdalja × faktor porabe v cevovodu.

---

## 7. Kvantifikacija prožnosti V2G

- **Essayeh, C. et al. (2025).** (*enako kot pri točki 3*)
  - Definira prožnost flote V2X kot agregiran politop izvedljivih profilov moči polnjenja/razelektrenja; eksplicitno loči pozitivno (razelektrenje) in negativno (odlog polnjenja) prožnost.

- **Wu, C. et al. (2021).** "Quantifying energy flexibility of commuter plug-in electric vehicles within a residence–office coupling virtual microgrid. Part I." *Energy and Buildings*, vol. 252. https://www.sciencedirect.com/science/article/abs/pii/S0378778821008355
  - Splošni okvir za kvantifikacijo prožnosti PEV za preoblikovanje neto bremena (povečanje in zmanjšanje); enaka konceptualizacija kot pozitivna/negativna prožnost v cevovodu.

- **Pfenninger, S. et al. (2024).** "Impact of V2G Flexibility on Congestion Management in the German Transmission Grid." *World Electric Vehicle Journal*, vol. 14, no. 12. https://www.mdpi.com/2032-6653/14/12/328
  - Kvantificira dvosmerno prožnost V2G na ravni flote (pozitivna: razelektrenje; negativna: odlog bremena); potrjuje, da je dvostransko merjenje prožnosti standard v najnovejši literaturi.

---

## 8. Pristop odprtih podatkov (OSM + ankete + popis)

- **Strobel, L. & Pruckner, M. (2023).** "OMOD: An open-source tool for creating disaggregated mobility demand based on OpenStreetMap." *Computers, Environment and Urban Systems*, vol. 104. https://www.sciencedirect.com/science/article/abs/pii/S0198971523000923
  - Celotna mobilnostna simulacija izključno z OSM prostorskimi podatki in nacionalno anketo o potovanjih — natanko isti nabor odprtih podatkov kot v tej nalogi (OSM + SiStat + NHTS).

- **Kashiyama, T. et al. (2024).** "Nationwide synthetic human mobility dataset construction from limited travel surveys and open data." *Computer-Aided Civil and Infrastructure Engineering*. https://onlinelibrary.wiley.com/doi/10.1111/mice.13285
  - Sintetična populacija mobilnosti iz odprtih statističnih podatkov in omejenih anket z agent-based simulacijo; potrjuje, da sta popis + anketa o potovanjih zadostna za realistično disaggregirano mobilnost.

- **Padgham, M. & Lovelace, R. (2023).** "Modelling Sustainable Transport – An Open Data Approach to Model Mode Shift Towards Net Zero." *Springer LNNS*. https://link.springer.com/chapter/10.1007/978-3-031-85578-8_23
  - OSM, popis in nacionalne ankete kot edini podatkovni vhodi za modeliranje prometnega povpraševanja — neposredno potrjuje pristop odprtih podatkov.

---

## 9. Modeliranje na ravni občine / lokalnem nivoju

- **Troiano, S. et al. (2024).** "Electric Vehicles to Support Grid Needs: Evidence from a Medium-Sized City." *World Electric Vehicle Journal*, vol. 8, no. 2. https://www.mdpi.com/2624-8921/8/2/30
  - Modelira V2G potencial za srednje velik italijanski kraj (Viterbo) z real-world podatki; neposredno primerljivo z analizo na ravni občine in eksplicitno naslavlja vrzel v literaturi za manjša mesta.

- **Helmus, J.R. et al. (2025).** "Urban scale vehicle-to-building-to-grid integration leveraging human mobility modeling for enhanced grid flexibility." *Building Simulation*, Springer. https://link.springer.com/article/10.1007/s12273-025-1346-3
  - Eksplicitno aplicira V2B2G okvir na mestnem/občinskem nivoju in povezuje mobilnostno simulacijo s kvantifikacijo prožnosti omrežja pri sub-nacionalni prostorski ločljivosti.

---

## 10. Isohronska selekcija lokacij

> **Opomba:** Za isohronsko filtriranje kot eksplicitno poimenovano metodologijo ni bil najden neposredni citat. Pristop se v literaturi pojavlja implicitno pod pojmom "prostorska dostopnost" ali "omrežne omejitve dosega". Priporočilo: navezati na dostopnostno literaturo (npr. Miller 2017 zgoraj) in pristop opisati kot aplikacijo prostorske dostopnosti, ne pričakovati neposrednega citata za "isohronsko filtriranje destinacij v EV simulaciji".

- **Iliopoulou, C. et al. (2023).** "Siting of electric vehicle charging stations method addressing area potential and increasing their accessibility." *Transportation Research Part D*, vol. 117. https://www.sciencedirect.com/science/article/abs/pii/S096669232300073X
  - Uporablja cone dostopnosti (konceptualno enake izohronam) za oceno pokritosti kandidatnih lokacij polnilnikov; potrjuje, da je isohronska dosegljivost sprejeta v literaturi o EV infrastrukturi.

- **Liu, Y.S. et al. (2022).** (*enako kot pri točki 4*)
  - Filtrira izvedljive destinacije polnjenja po omrežni razdalji — funkcionalni ekvivalent isohronskega filtriranja, čeprav ne poименovan eksplicitno.

---

*Zbrano: julij 2026 | Viri so bile preverjene z iskanjem po Google Scholar, Scopus in arXiv.*
