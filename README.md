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
hetzelfde dossier weer bij. Dit is de lijst waaruit het reviewmemorandum wordt
opgebouwd.

**Memorandum.** Dezelfde bevindingen als een stuk om te lezen. De kop noemt de
onderneming, het boekjaar en beide bestanden met hun XAF-versie; daarna staan de
uitgangspunten met de gebruikte materialiteitsdrempel en haar opbouw, een
samenvatting met de zwaarste punten, en de aandachtspunten op volgorde van
gewicht: eerst ernst, dan boven de drempel vóór eronder, dan bedrag. Elk punt
heeft één nummer waarmee het aan te wijzen is, met het bedrag, de rekening,
waarop de selectie berust en de pagina met de onderbouwing.

Wat de tool niet kon vaststellen staat in een eigen sectie en verdwijnt nooit
uit het stuk: een memorandum dat zwijgt over een controle die niet kon worden
uitgevoerd, wekt de indruk dat er niets aan de hand is. Bevindingen die u zelf
hebt beoordeeld verhuizen met hun status en notitie naar een sectie achteraan,
zodat de hoofdlijst overhoudt wat nog aandacht vraagt. Onderaan staat de
verantwoording: het bewijsniveau voor de openstaande posten, de RGS-dekking van
het rekeningschema, hoeveel bevindingen onder de drempel liggen en hoeveel er
nog geen beoordeling hebben. Het stuk is te downloaden als Word-document
(`.docx`) en als Markdown-bestand. Beide komen uit dezelfde opbouw, dus de
formulering staat maar op één plek en de twee vormen kunnen niet uiteenlopen.

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

**Jaarvergelijking.** Vier ratio's naast elkaar, dan per RGS-rubriek voor de
hoofdlijn en per grootboekrekening voor het detail, met nieuwe en vervallen
rekeningen en filters op status, rekeningsoort en verschilbedrag.

**Ratio's.** Brutomarge, personeelskosten als deel van de omzet, solvabiliteit en
liquiditeit, voor beide boekjaren. Onder elke uitkomst staat de opbouw: welke
rubrieken zijn gebruikt, hoeveel rekeningen daarin vallen en of dat op de
RGS-code of op de omschrijving berust. Het resultaat van het boekjaar wordt bij
het eigen vermogen geteld zodra uit de balans blijkt dat het nog niet is bestemd.
De tool geeft geen normwaarden: gesignaleerd wordt een verschuiving tussen beide
jaren, een negatief eigen vermogen en kortlopende schulden die de vlottende
activa overtreffen. Dekt de rubrieksindeling minder dan negentig procent van de
balans, dan volgt er geen balansratio maar de melding dat die niet mogelijk is.

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

**Suppletie.** Naast de rondrekening staat de vraag die daarop volgt: is er voor
het verschil met de aangifte al een suppletie geboekt? De tool zoekt op de
btw-rekeningen naar boekingen die zichzelf een suppletie, naheffing,
aanvullende aangifte of btw-correctie noemen, leest het tijdvak uit de
omschrijving en zet het geboekte bedrag naast het verschil met de aangifte, met
het restant erbij. Boekingen uit de facturatie vallen af, want een suppletie is
geen factuur. Een boeking is geen indiening: of er nog een suppletie moet
worden gedaan, blijft een oordeel van de beoordelaar.

**Analytische controles.** Komen vaste lasten in elke periode voor, zijn er
ongebruikelijke boekingen (weekend, ronde bedragen, grote memoriaalposten in de
laatste periode, omzet aan de verkeerde kant), staan balansposten aan de
verwachte kant, en hoe verlopen omzet en loonkosten per periode.

**Relaties.** Wat er per relatie in het boekjaar is gefactureerd en afgewikkeld
op de debiteuren- en crediteurenrekeningen, inclusief btw, met de concentratie
over de grootste relaties. Dit is geen omzet en geen openstaande-postenlijst; de
netto mutatie is de verandering van het saldo in dit jaar, zonder beginsaldo, en
dus niet het openstaande bedrag.

Geeft het bestand XAF 4.0-relatiesaldi, dan staat daar de openstaande stand per
debiteur en crediteur bij begin en einde van het boekjaar, met de aansluiting op
het saldo van de debiteuren- en de crediteurenrekening. Loopt dat uiteen, dan
staat er iets op de relatierekening dat niet aan een relatie hangt of ontbreekt
er een relatie; de tool benoemt het verschil en concludeert niet. Per relatie
komt er een signaal bij een onlogisch teken, zoals een crediteur met een
debetsaldo, en bij een verloop dat niet op de boekingen aansluit.

Vult het bestand de subadministratie van XAF 3.2, dan staan daar de openstaande
posten zelf, met hun ouderdom. De regels van de beginbalans en die van de
mutaties vormen samen een post: gegroepeerd op het afletterkenmerk, anders op de
factuurreferentie, anders per regel; wat het is geworden staat erbij. Een post
die op nul uitkomt is afgeletterd en valt uit de lijst. De ouderdom loopt vanaf
de vervaldatum en anders vanaf de factuurdatum, in de klassen nog niet vervallen,
0-30, 31-60, 61-90 en meer dan 90 dagen. Die twee bases staan nooit in dezelfde
rij, want dagen te laat betekent iets anders dan dagen sinds de factuur, en een
post zonder beide datums valt in een eigen klasse in plaats van in de laagste.
De peildatum is de balansdatum en is in de app aan te passen. Het totaal wordt
tegenover het saldo van de debiteuren- en de crediteurenrekening gezet.

Zo'n regel draagt geen rekeningnummer; de tool leidt de rekening af uit de
verwijzing naar de beginbalans of naar de grootboekboeking en laat zien hoe dat
is gegaan. Leidt de verwijzing nergens heen of is zij niet eenduidig, dan blijft
de rekening leeg in plaats van dat er een wordt gekozen, en valt de post buiten
de aansluiting in plaats van naar een van beide kanten te worden geraden. De
losse regels staan onder de posten, met de controletotalen die het blok zelf
opgeeft.

Of dit allemaal kan, hangt aan de versie en aan het boekhoudpakket. De
subadministratie van XAF 3.2 is de enige plek met een echte vervaldatum, en zij
is optioneel: in de beschikbare 3.2-bestanden is zij leeg. XAF 4.0 heeft die
blokken geschrapt en geeft per relatie een openstaand bedrag bij begin en einde
van het boekjaar (`opBalDesc`/`clBalDesc`); dat is een eindstand, geen
factuurlijst en geen ouderdom. Let op: `settDate` in 4.0 is géén vervaldatum maar de leverdatum,
`effDate` is de mutatiedatum in 3.2 en de factuurdatum in 4.0, en `opBalDesc` is
in 3.2 een omschrijving van de grootboekbeginbalans en pas in 4.0 een bedrag per
relatie. Zie `ROADMAP.md` en `docs/xaf-velden.md`.

**Fiscale signalen.** Posten die om een beoordeling vragen: boetes en
dwangsommen, juridische kosten, representatie en horeca, rekening-courant met de
directie, auto en privegebruik, giften. De tool signaleert en concludeert niet.

Op dezelfde pagina staat de **drempeltoets excessief lenen**. De tool selecteert
de rekening-courant- en leningrekeningen met aandeelhouders en bestuurders op hun
RGS-code en zet het eindsaldo tegenover het maximumbedrag van art. 4.14a lid 2
Wet IB 2001 (€ 700.000 per 31 december 2023, € 500.000 daarna; het bedrag wordt
niet geïndexeerd). De opbouw staat regel voor regel, met per regel de bron:
auditfile, wet of gebruiker.

Dat laatste is nodig, want tussen het grootboek en de wet zit een gat dat een
auditfile niet dicht. De wet toetst de belastingplichtige en zijn partner over
alle vennootschappen waarin een aanmerkelijk belang wordt gehouden, per
31 december; dit bestand is het grootboek van één vennootschap op de
balansdatum. De eigenwoningschuld waarvoor een recht van hypotheek is verstrekt
blijft buiten beschouwing, en het maximumbedrag wordt verhoogd met eerder belast
fictief regulier voordeel. Die drie bedragen vult u zelf in; ze worden bewaard in
de dossiermap en pas op de bewaarknop. Eindigt het boekjaar niet op 31 december,
of is voor die peildatum geen bedrag vastgesteld, dan geeft de tool de gemeten
stand wel maar noemt zij de toets niet mogelijk. Een rekening-courant met een
RGS-code buiten de selectie, zoals "rekening-courant overigen", telt niet mee in
het bedrag maar wordt apart gemeld.

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
- **Testmap** — leest `vorig_jaar.xaf` en `huidig_jaar.xaf` uit `testfiles/`. Deze
  optie is een lokale ontwikkelsnelkoppeling en verschijnt alleen wanneer beide
  bestanden er staan. De bestanden zijn door Git genegeerd, dus op een server
  bestaat de keuze niet.

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
| `auditfile/suppletie.py` | Geboekte suppleties en hun aansluiting op het verschil |
| `auditfile/controls.py` | Analytische en fiscale controles |
| `auditfile/comparison.py` | Jaar-op-jaar vergelijking |
| `auditfile/ratios.py` | Brutomarge, personeelsquote, solvabiliteit en liquiditeit |
| `auditfile/relatiesaldi.py` | Openstaande bedragen per relatie (XAF 4.0) |
| `auditfile/openstaand.py` | Openstaande posten en ouderdom (XAF 3.2) |
| `auditfile/excessief_lenen.py` | Drempeltoets excessief lenen |
| `auditfile/findings.py` | Bevindingen, materialiteit en beoordeling |
| `auditfile/memorandum.py` | Het reviewmemorandum als document (Markdown en Word) |
| `auditfile/capability.py` | Wat het bestand toelaat en met welk bewijsniveau |
| `auditfile/excel.py` | Excel-export |
| `auditfile/formatting.py` | Presentatie van tabellen |
| `auditfile/notatie.py` | Nederlandse notatie van losse waarden, zonder Streamlit |
| `auditfile/settings.py` | Lokale opslag van eigen invoer |
| `auditfile/demo.py` | Synthetische auditfiles |
| `inspect_xaf.py` | Losse CLI om een onbekende XAF-structuur te verkennen |

Fiscale waarden en rubrieken zijn herleidbaar tot hun bron; de vindplaatsen
staan in [`docs/btw-bronnen.md`](docs/btw-bronnen.md).

## Privacy

De repository is publiek. Er staat geen klantdata in en die mag er ook niet in
komen, ook niet als voorbeeld. Eigen invoer (aangiftebedragen, grondslagen, de
koppeling van btw-codes aan rubrieken, het aftrekbare aandeel per code, de
beoordeling per bevinding en de dossiergegevens bij de drempeltoets excessief
lenen) wordt bewaard in `.local-testdata/`, dat door Git wordt genegeerd.
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
