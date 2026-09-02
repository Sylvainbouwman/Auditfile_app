# Auditfile Analyzer

Fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en het
belastingadvies. De tool leest twee XAF-auditfiles (vorig jaar en huidig jaar),
vergelijkt ze en voert een reeks controles uit. De tool is bedoeld om lokaal te
draaien; bij lokale uitvoering blijven de auditfiles op de eigen computer.

## Wat doet de tool?

**Bevindingen.** Alle controles leveren hun eigen tabel op; op deze pagina staan
ze in één vorm, gesorteerd op ernst en bedrag. Vier niveaus: kritiek (de cijfers
zijn zo niet te gebruiken), waarschuwing (afwijking die beoordeling vraagt),
signaal (iets om naar te kijken) en niet mogelijk (de controle kon niet worden
uitgevoerd, wat ook een bevinding is). De materialiteit is instelbaar met een
vast bedrag en een percentage van de omzet; de hoogste van de twee geldt.
Bevindingen onder de drempel worden gemarkeerd en niet weggelaten, en een
bevinding zonder bedrag valt nooit onder de drempel. Per bevinding is een
beoordeling en een notitie vast te leggen; die hangen aan de bevinding en niet
aan haar plaats in de lijst, dus ze staan er bij een volgende analyse van
hetzelfde dossier weer bij. Dit is de lijst waaruit het reviewmemorandum kan
worden opgebouwd.

**Overzicht.** Een telling van de signalen per categorie, met de pagina waar ze
staan. Een leeg blok op het overzicht betekende eerder niet dat er niets was: de
periodieke, balans-, relatie- en fiscale signalen stonden alleen op hun eigen
pagina.

**Bestandscontrole.** Eerst de vraag of de twee bestanden bij elkaar horen:
dezelfde onderneming, dezelfde valuta, aansluitende boekjaren, niet twee keer
hetzelfde bestand en geen overlappende periodes. Een vergelijking van twee
willekeurige auditfiles rekent namelijk gewoon door en ziet er plausibel uit.
Daarna wordt de jaarovergang getoetst: de beginbalans van dit jaar hoort gelijk
te zijn aan de eindbalans van vorig jaar, met het resultaat van vorig jaar
bestemd in het eigen vermogen.

Vervolgens wordt elk auditfile getoetst aan de controletotalen die het zelf
opgeeft: aantallen regels, totaal
debet en credit, sluit elke transactie op nul, staan alle boekingen op een
bekende rekening en binnen het boekjaar. Wijkt daar iets af, dan staat dat
bovenaan.

**Jaarvergelijking.** Per RGS-rubriek voor de hoofdlijn en per grootboekrekening
voor het detail, met nieuwe en vervallen rekeningen en filters op status,
rekeningsoort en verschilbedrag.

**Btw.** Een auditfile bevat geen aangifte, maar wel btw-codes per boekingsregel.
De tool stelt per code een aangifterubriek voor op grond van de omschrijving, het
tarief en de debet/creditzijde, en zegt erbij waarop dat voorstel berust. Een
voorstel wordt pas een keuze wanneer je de indeling vastlegt; tot dat moment
staat er per code "voorstel" en meldt de tool dat de btw-positie een
rekenvoorbeeld is. Na het vastleggen staat er "geaccepteerd" of "aangepast",
zodat zichtbaar blijft wie wat heeft bepaald. Bij verlegging, invoer en
intracommunautaire verwerving draagt één btw-code aan twee rubrieken bij: de
verschuldigde btw in 2a, 4a of 4b en dezelfde btw als voorbelasting in 5b. Het
aftrekbare aandeel staat per code op 100% en is aanpasbaar bij vrijgesteld of
gemengd gebruik. Daarna volgt de optelling per rubriek en de vergelijking met de
ingediende aangiften. Alle rubrieken van het formulier zijn invulbaar, zowel de
btw als het bedrag waarover die is berekend, ook wanneer een rubriek niet in het
auditfile voorkomt: dan is dat juist het verschil. Een leeg veld betekent niet
ingevuld en is iets anders dan een aangifte van nul. Verder is er een
rondrekening over de btw-grootboekrekeningen en een reeks signalen op
regelniveau.

**Analytische controles.** Komen vaste lasten in elke periode voor, zijn er
ongebruikelijke boekingen (weekend, ronde bedragen, grote memoriaalposten in de
laatste periode, omzet aan de verkeerde kant), staan balansposten aan de
verwachte kant, en hoe verlopen omzet en loonkosten per periode.

**Relaties.** Wat er per relatie in het boekjaar is gefactureerd en afgewikkeld
op de debiteuren- en crediteurenrekeningen, inclusief btw, met de concentratie
over de grootste relaties. Dit is geen omzet en geen openstaande-postenlijst; de
netto mutatie is de verandering van het saldo in dit jaar, zonder beginsaldo, en
dus niet het openstaande bedrag.

Openstaande posten met een ouderdom zijn niet principieel onmogelijk uit een
auditfile, maar hangen aan de versie en aan het boekhoudpakket. XAF 3.2 heeft een
optionele subadministratie (`obSbLine` en `sbLine`) met factuurdatum, vervaldatum
en afletterkenmerk; XAF 4.0 heeft die blokken geschrapt en geeft per relatie een
openstaand bedrag bij begin en einde van het boekjaar (`opBalDesc`/`clBalDesc`).
Let op: `settDate` in 4.0 is géén vervaldatum maar de leverdatum, en `effDate` is
de mutatiedatum in 3.2 en de factuurdatum in 4.0. Deze tool leest die blokken nog
niet; zie `ROADMAP.md`.

**Fiscale signalen.** Posten die om een beoordeling vragen: boetes en
dwangsommen, juridische kosten, representatie en horeca, rekening-courant met de
directie, auto en privegebruik, giften. De tool signaleert en concludeert niet.

**Excel-export.** Ruim twintig werkbladen met Nederlandse getalnotatie, filters
en vastgezette koppen. Bedragen zijn getallen, dus optelbaar.

## Gebruik

```bash
"C:\Python314\python.exe" -m streamlit run app.py
```

Kies in de zijbalk een gegevensbron:

- **Eigen bestanden** — twee XAF-bestanden uploaden.
- **Demo (synthetisch)** — volledig verzonnen gegevens uit `auditfile/demo.py`,
  om de tool te bekijken of te tonen zonder klantbestand.
- **Testmap** — leest `vorig_jaar.xaf` en `huidig_jaar.xaf` uit `testfiles/`.

Afhankelijkheden installeren:

```bash
pip install -r requirements.txt
```

## Tests

```bash
"C:\Python314\python.exe" -m pytest tests/
```

De tests draaien op synthetische auditfiles die in het geheugen worden
opgebouwd; er wordt nooit klantdata gelezen.

## Opbouw

| Module | Verantwoordelijkheid |
|---|---|
| `app.py` | Uitsluitend de interface |
| `auditfile/parsing.py` | XAF 3.2 en 4.0 inlezen |
| `auditfile/model.py` | Datamodel |
| `auditfile/integrity.py` | Controle op het bestand zelf |
| `auditfile/vat.py` | Btw-analyse en rondrekening |
| `auditfile/vat_rubrics.py` | Rubrieken van de aangifte omzetbelasting |
| `auditfile/controls.py` | Analytische en fiscale controles |
| `auditfile/comparison.py` | Jaar-op-jaar vergelijking |
| `auditfile/excel.py` | Excel-export |
| `auditfile/formatting.py` | Presentatie van tabellen |
| `auditfile/settings.py` | Lokale opslag van eigen invoer |
| `auditfile/demo.py` | Synthetische auditfiles |
| `inspect_xaf.py` | Losse CLI om een onbekende XAF-structuur te verkennen |

Fiscale waarden en rubrieken zijn herleidbaar tot hun bron; de vindplaatsen
staan in [`docs/btw-bronnen.md`](docs/btw-bronnen.md).

## Privacy

De repository is publiek. Er staat geen klantdata in en die mag er ook niet in
komen, ook niet als voorbeeld. Eigen invoer (aangiftebedragen, grondslagen, de
koppeling van btw-codes aan rubrieken en het aftrekbare aandeel per code) wordt
bewaard in `.local-testdata/`, dat door Git wordt genegeerd.
`tests/test_runtime_data_not_tracked.py` bewaakt die scheiding.

Die invoer staat per dossier apart, in `.local-testdata/dossiers/<sleutel>`. De
sleutel is een korte hash van onderneming plus boekjaar, zodat er geen klantnaam
of nummer in een mapnaam op schijf staat; binnen de map staat naam en boekjaar in
`dossier.json`, zodat in de app te zien is wat er lokaal ligt. Zo kan de
beoordeling van de ene klant niet bij de andere opduiken, ook niet wanneer daar
dezelfde btw-codes voorkomen. Vermeldt een auditfile geen onderneming of geen
boekjaar, dan is er geen dossier en wordt er niets bewaard. Het openen van een
auditfile schrijft niets weg; dat gebeurt pas als je invoer bewaart. In de
zijbalk staat onder "Lokale opslag" welke dossiers er zijn, met een knop om de
invoer van het huidige dossier te wissen.

Waar de gegevens blijven, hangt af van waar de app draait. Streamlit bestaat uit
een browser en een Python-proces: `st.file_uploader` stuurt het gekozen bestand
naar dat proces. Draait de app op de eigen computer, dan komt het bestand niet
verder dan die computer. Draait de app op een server, dan gaat het bestand naar
die server, ook als de browser lokaal staat. Zet de tool daarom niet op een
gedeelde omgeving zonder die afweging te maken.

Twee dingen om te weten bij lokaal gebruik:

- Ingelezen auditfiles staan in de Streamlit-cache van het draaiende proces en
  verdwijnen bij het afsluiten.
- Aangiftebedragen en btw-koppelingen blijven daarna op schijf staan in
  `.local-testdata/`. Verwijder die map om ze te wissen.

## Roadmap

Zie [`ROADMAP.md`](ROADMAP.md).
