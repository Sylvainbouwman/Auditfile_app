# Fiscale bronnen bij de btw-analyse

Vindplaatsen bij de waarden en regels die in de code zijn vastgelegd. Geraadpleegd
op 1 september 2026 (CEST). Herbevestig deze gegevens na Prinsjesdag en bij de
jaarwisseling; zie de skill `onderhoud-en-jaarwerk`.

## Rubrieken van de aangifte omzetbelasting

Vastgelegd in `auditfile/vat_rubrics.py`.

Bron: Belastingdienst, *Toelichting bij de btw-aangifte (omzetbelasting)*, deel
"Voor ondernemers in Nederland".

- Uitgave 2026: <https://download.belastingdienst.nl/belastingdienst/docs/toelichting_bij_btw_aangifte_ob0731t62fd.pdf>
- Uitgave 2025: <https://download.belastingdienst.nl/belastingdienst/docs/toelichting_bij_btw_aangifte_ob0731t53fd.pdf>
- Uitgave 2024: <https://download.belastingdienst.nl/belastingdienst/docs/toelichting_bij_dig_aangifte_omzetbelasting_ob0731t42fd.pdf>
- Overzichtspagina: <https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/themaoverstijgend/brochures_en_publicaties/toelichting_bij_de_digitale_aangifte_omzetbelasting>

| Code | Omschrijving | Omzet | Btw | Eindtelling |
|---|---|---|---|---|
| 1a | Leveringen/diensten belast met hoog tarief | ja | ja | + |
| 1b | Leveringen/diensten belast met laag tarief | ja | ja | + |
| 1c | Leveringen/diensten belast met overige tarieven, behalve 0% | ja | ja | + |
| 1d | Privegebruik | ja | ja | + |
| 1e | Leveringen/diensten belast met 0% of niet bij u belast | ja | nee | n.v.t. |
| 2a | Leveringen/diensten waarbij de btw naar u is verlegd | ja | ja | + |
| 3a | Leveringen naar landen buiten de EU (uitvoer) | ja | nee | n.v.t. |
| 3b | Leveringen naar of diensten in landen binnen de EU | ja | nee | n.v.t. |
| 3c | Installatie/afstandsverkopen binnen de EU | ja | nee | n.v.t. |
| 4a | Leveringen/diensten uit landen buiten de EU | ja | ja | + |
| 4b | Leveringen/diensten uit landen binnen de EU | ja | ja | + |
| 5a | Verschuldigde btw (rubrieken 1 tot en met 4) | nee | berekend | subtotaal |
| 5b | Voorbelasting | nee | ja | − |

Eindtelling: `5a = btw(1a) + btw(1b) + btw(1c) + btw(1d) + btw(2a) + btw(4a) + btw(4b)`
en `totaal te betalen of terug te vragen = 5a − 5b`. Bevestigd door het rekenvoorbeeld
op blz. 3 van de *Toelichting bij de Suppletie btw* (januari 2025):
<https://download.belastingdienst.nl/belastingdienst/docs/toelichting_suppletie_btw_ob1431t21pl.pdf>

Let op bij onderhoud:

- **Er bestaan geen rubrieken 5c tot en met 5g meer.** Het subtotaal heet op het
  formulier "Totaal btw" zonder rubriekcode. Rubriek 5d verviel toen de KOR per
  2020 een omzetgerelateerde vrijstelling werd. Een boekhoudpakket of de XBRL
  Nederlandse Taxonomie kan die oude codes nog wel voeren.
- De indeling is voor 2024, 2025 en 2026 gelijk; alleen de bewoording is per 2025
  aangepast. De kolomkoppen heten sinds 2025 "Omzet" en "Btw" in plaats van
  "Bedrag waarover omzetbelasting wordt berekend" en "Omzetbelasting". Rubriek 2a
  luidde in 2024 nog "waarbij de heffing van omzetbelasting naar u is verlegd".
- Per 1 januari 2026 gaat het tarief voor logies naar 21%. Dat raakt alleen de
  verdeling tussen 1a en 1b, niet de rubriekindeling zelf.

## De aangifte als XBRL-bestand: welk element hoort bij welke rubriek

Vastgelegd in `auditfile/aangifte.py`. Geraadpleegd op 17 september 2026 (CEST).

De btw-aangifte gaat sinds 1 januari 2014 verplicht als XBRL-bericht via Digipoort
naar de Belastingdienst. De elementnamen komen uit het belastingdienstdeel (`bd`)
van de Nederlandse Taxonomie. De koppeling hieronder is niet afgeleid uit de
omschrijving maar overgenomen uit de taxonomie zelf: het schema geeft de
elementnamen, de label-linkbase het Nederlandse label en de reference-linkbase het
paragraafnummer van de officiële definitie.

- Schema: <http://www.nltaxonomie.nl/10.0/basis/bd/items/bd-omzetbelasting.xsd>
- Nederlandse labels: <http://www.nltaxonomie.nl/10.0/basis/bd/items/bd-omzetbelasting-lab-nl.xml>
- Verwijzingen naar de definities: <http://www.nltaxonomie.nl/10.0/basis/bd/items/bd-omzetbelasting-ref.xml>
- De definities zelf, per paragraafnummer: *Belastingdienst taxonomie definities*,
  <https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/NT16_BD_20220921%20BD%20Taxonomie%20definities.pdf>
- Overzicht van de taxonomieversies: <https://www.sbr-nl.nl/>

| Rubriek | Element (omzet) | Element (btw) | Paragraaf |
|---|---|---|---|
| 1a | `TaxedTurnoverSuppliesServicesGeneralTariff` | `ValueAddedTaxSuppliesServicesGeneralTariff` | 509382 / 509383 |
| 1b | `TaxedTurnoverSuppliesServicesReducedTariff` | `ValueAddedTaxSuppliesServicesReducedTariff` | 509384 / 509385 |
| 1c | `TaxedTurnoverSuppliesServicesOtherRates` | `ValueAddedTaxSuppliesServicesOtherRates` | 509386 / 509387 |
| 1d | `TaxedTurnoverPrivateUse` | `ValueAddedTaxPrivateUse` | 509388 / 509389 |
| 1e | `SuppliesServicesNotTaxed` | — | 509390 |
| 2a | `TurnoverSuppliesServicesByWhichVATTaxationIsTransferred` | `ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred` | 509393 / 509395 |
| 3a | `SuppliesToCountriesOutsideTheEC` | — | 509400 |
| 3b | `SuppliesToCountriesWithinTheEC` | — | 509398 |
| 3c | `InstallationDistanceSalesWithinTheEC` | — | 509401 |
| 4a | `TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC` | `ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC` | 509402 / 509403 |
| 4b | `TurnoverFromTaxedSuppliesFromCountriesWithinTheEC` | `ValueAddedTaxOnSuppliesFromCountriesWithinTheEC` | 509404 / 509405 |
| 5a | — | `ValueAddedTaxOwed` | 509406 |
| 5b | — | `ValueAddedTaxOnInput` | 509407 |

Daarnaast, buiten de rubrieken om:

| Element | Betekenis | Paragraaf |
|---|---|---|
| `ValueAddedTaxOwedToBePaidBack` | Totaal te betalen of terug te vragen | 509408 |
| `SmallEntrepreneurProvisionReduction` | Vermindering volgens de kleineondernemersregeling | 516662 |
| `ValueAddedTaxAmountTotalOld` | Suppletie: wat er eerder over dat tijdvak was aangegeven | 637579 |
| `ValueAddedTaxAmountTotalNew` | Suppletie: het nieuwe totaal | 637578 |
| `ValueAddedTaxToBePaidAdditionalToBePaidBack` | Suppletie: bij te betalen of terug te vragen | 643303 |

Let op bij onderhoud:

- **Koppel op de elementnaam, niet op het rubrieknummer.** Het nummer op het
  formulier is presentatie en is eerder gewijzigd; de elementnaam is de vaste
  identiteit van het gegeven. Dat is bij 3a en 3b het scherpst te zien: welke van
  de twee "binnen de EU" is, volgt uit `WithinTheEC` in de naam en niet uit het
  nummer.
- **Een suppletie gebruikt dezelfde rubriekelementen als een aangifte**, met de
  gecorrigeerde standen erin. De definitie bij paragraaf 509383 zegt dat met
  zoveel woorden ("in de periode waarover aangifte of suppletie wordt gedaan").
  De twee soorten mogen daarom niet bij elkaar worden opgeteld: dat telt hetzelfde
  tijdvak dubbel. Het onderscheid volgt uit de verwijzing naar het taxonomieschema
  bovenin het bericht, en anders uit de aanwezige velden: paragraaf 509408 komt
  volgens zijn eigen definitie alleen in een aangifte voor en niet in een suppletie.
- **De elementnamen zijn stabiel over taxonomieversies.** Tussen versie 9.0 en 10.0
  is geen rubriekelement hernoemd of verdwenen; er kwamen er vijf bij, alle voor de
  buitenlandregelingen (MOSS en VOES). De parser werkt daarom op de lokale
  elementnaam en negeert de namespace, net als bij XAF. Wat hij niet herkent, meldt
  hij per elementnaam, zodat een echte wijziging opvalt in plaats van weg te vallen.
- `SmallEntrepreneurProvisionReduction` hoort bij de oude rubriek 5d, die verviel
  toen de KOR per 2020 een omzetgerelateerde vrijstelling werd. Het element bestaat
  nog in de taxonomie; oudere aangiften kunnen het bevatten.

## Verleggingsregeling

- Art. 12 lid 5 Wet OB 1968 (delegatiegrondslag): <https://wetten.overheid.nl/BWBR0002629/2026-01-01>
- Art. 24b Uitvoeringsbesluit omzetbelasting 1968 (onderaanneming en het ter
  beschikking stellen van personeel), art. 24ba (overige aangewezen gevallen):
  <https://wetten.overheid.nl/BWBR0002633/2026-01-01>

De leverancier vermeldt bij binnenlandse verlegging alleen de omzet in rubriek 1e
en draagt zelf geen btw af. De afnemer geeft de verlegde btw aan in rubriek 2a en
trekt die onder de gewone voorwaarden af in 5b. Bij vrijgesteld gebruik vervalt
die aftrek en blijft de btw uit 2a drukken.

## Aftrek van btw die de ondernemer zelf verschuldigd wordt

- Art. 15 lid 1 Wet OB 1968: <https://wetten.overheid.nl/BWBR0002629/2026-01-01>
  (versie 1 januari 2026, geraadpleegd 2 september 2026).

Letterlijk uit dat artikel, voor de drie rubrieken die de tool als aftrekbaar in
5b behandelt:

| Rubriek | Verschuldigd wegens | Aftrekgrondslag |
|---|---|---|
| 2a | verlegging, art. 12 lid 2 tot en met 5 | art. 15 lid 1 onderdeel c, onder 2° |
| 4a | invoer | art. 15 lid 1 onderdeel c, onder 1° |
| 4b | intracommunautaire verwerving, art. 17a lid 1 | art. 15 lid 1 onderdeel b |

De slotzin van art. 15 lid 1 stelt de voorwaarde: "een en ander voor zover de
goederen en de diensten door de ondernemer worden gebruikt voor belaste
handelingen." Het aftrekbare aandeel volgt dus niet uit het auditfile. De tool
gaat uit van 100% en laat dat per btw-code aanpassen; bij vrijgesteld of gemengd
gebruik hoort een lager aandeel en blijft de btw uit 2a, 4a of 4b drukken. Voor
onroerende zaken in gemengd gebruik geeft dezelfde bepaling een aftrek naar
evenredigheid van het zakelijke gebruik.

## Intracommunautair en invoer

- Uitvoer buiten de EU: rubriek 3a, nultarief op grond van Tabel II, onderdeel a,
  post 2 Wet OB 1968.
- Intracommunautaire levering en diensten aan EU-ondernemers: rubriek 3b, ook op
  te nemen in de opgaaf ICP.
- Intracommunautaire verwerving en naar de afnemer verlegde diensten van
  EU-ondernemers: rubriek 4b, met aftrek in 5b. Diensten aan onroerende zaken in
  Nederland horen echter in 2a.
- Invoer met verleggingsregeling: rubriek 4a, art. 23 Wet OB 1968.

## Aftrekbeperking bij representatie, horeca en personeelsvoorzieningen

Gebruikt als signaal in `auditfile/vat.py`. Grondslag: Besluit uitsluiting aftrek
omzetbelasting 1968 (BUA). De tool signaleert alleen; zij berekent geen correctie.

## Boetes en dwangsommen

Gebruikt in `auditfile/controls.py`.

- Art. 3.14 lid 1 onderdeel c Wet IB 2001 sluit uit: geldboeten van de
  strafrechter en geldsommen ter voorkoming van strafvervolging (of een
  daarmee vergelijkbare buitenlandse wijze van bestraffing), bestuurlijke
  boeten **en daarmee vergelijkbare buitenlandse boeten**, boeten uit bij wet
  geregeld tuchtrecht, en boeten van een instelling van de Europese Unie. De
  zinsnede over het buitenland hangt in de wettekst dus aan de bestuurlijke
  boeten, niet aan de hele opsomming; tuchtrechtboeten en EU-boeten kennen geen
  eigen buitenlandclausule.
- Art. 3.14 lid 1 onderdeel i sluit dwangsommen uit als bedoeld in afdeling 5.3.2
  van de Algemene wet bestuursrecht (last onder dwangsom, art. 5:31d tot en met
  5:39 Awb) en daarmee vergelijkbare buitenlandse dwangsommen. Dit onderdeel geldt
  sinds 1 januari 2020.
- Doorwerking naar de vennootschapsbelasting via art. 8 lid 1 Wet Vpb 1969, dat
  art. 3.14 lid 1 onderdelen b tot en met i van overeenkomstige toepassing
  verklaart.
- Vindplaatsen: <https://wetten.overheid.nl/BWBR0011353/2026-02-21> (Wet IB 2001)
  en <https://wetten.overheid.nl/BWBR0002672/2026-01-01> (Wet Vpb 1969); afdeling
  5.3.2 Awb: <https://wetten.overheid.nl/BWBR0005537>

Niet onder de uitsluiting vallen: contractuele boetes tussen private partijen,
civielrechtelijke dwangsommen (art. 611a Rv), en ontnemingsvorderingen en
schadevergoeding bij misdrijven (art. 3.14 lid 3). De tool moet daarom signaleren
en niet concluderen.

Nog te onderzoeken: de behandeling van belastingrente en invorderingsrente. Art.
3.14 zegt daar niets over; die beoordeling loopt langs andere bepalingen. Neem
hierover geen uitspraak op in de tool zonder aanvullend onderzoek.

## Drempel excessief lenen

Verwerkt in `auditfile/excessief_lenen.py`. De bedragen staan daar per peildatum
in `MAXIMUMBEDRAGEN`, met deze sectie als vindplaats. Buiten de reeks geeft de
tool geen bedrag: vóór 2023 bestond de regeling niet en na het laatst
vastgestelde jaar is het bedrag niet vastgesteld.

| Peildatum 31 december | Maximumbedrag |
|---|---|
| 2023 | € 700.000 |
| 2024 | € 500.000 |
| 2025 | € 500.000 |
| 2026 | € 500.000 |

- Art. 4.14a lid 2 Wet IB 2001. Het bedrag wordt niet geïndexeerd: art. 4.14a
  komt niet voor in de opsomming van art. 10.1 Wet IB 2001.
- Peildatum en waardering: art. 4.14a lid 4 (einde kalenderjaar, nominale waarde).
  Het maximum geldt voor de belastingplichtige en zijn partner gezamenlijk
  (lid 3).
- Invoering op € 700.000: Wet excessief lenen bij eigen vennootschap, Stb. 2022,
  531: <https://zoek.officielebekendmakingen.nl/stb-2022-531.html>
- Verlaging naar € 500.000 per 1 januari 2024: Belastingplan 2024, Stb. 2023, 499,
  artikel I onderdeel 0A: <https://zoek.officielebekendmakingen.nl/stb-2023-499.html>
- Eigenwoningschuld blijft buiten beschouwing voor zover daarvoor een recht van
  hypotheek aan de vennootschap is verstrekt (art. 4.14a lid 6). Voor een op
  31 december 2022 bestaande eigenwoningschuld geldt die hypotheekeis niet
  (overgangsrecht art. 10a.23 Wet IB 2001).
- Het bedrag per peildatum 31 december 2026 staat onder voorbehoud van het
  Belastingplan 2027.
