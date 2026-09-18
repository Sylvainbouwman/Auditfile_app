# Update voor Bram — Auditfile Analyzer

Eerste opleverdocument voor deze tool, op 14 september 2026. Dekt de periode
17 juli 2026 tot en met 11 september 2026 (er is tussen 14 juli en
25 augustus niet aan de tool gewerkt). **Bijgewerkt op 16 september 2026** met
de twee punten die toen nog open stonden: die zijn gebouwd, getest en
gemerged in `main`. **Opnieuw bijgewerkt op 18 september 2026** met vier
functies die zijn gebouwd naar aanleiding van de vraag wat de tool voor de
assistenten bruikbaarder zou maken.

## Doel en waarde

Fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en het
belastingadvies. Laadt twee XAF-auditfiles (vorig jaar en huidig jaar),
vergelijkt ze en voert fiscale controles uit: btw-rondrekening, suppletie,
periodieke en analytische controles, jaar-op-jaar vergelijking, ratio-analyse,
de drempeltoets excessief lenen en een Excel-export. De ingediende btw-aangifte
kan als XBRL-bestand worden ingelezen en naast het auditfile worden gelegd, en
lease- en huurverplichtingen worden in een eigen register bijgehouden. Alles
komt samen in een automatisch gegenereerd reviewmemorandum, als Word-document,
als PDF en als Markdown.

Waarde voor het kantoor: de handmatige Excel-analyse bij een samenstelopdracht
(exporteren, vergelijken met vorig jaar, de checklist doorlopen) wordt
vervangen door een tool die dezelfde controles gestandaardiseerd uitvoert, met
minder kans op een gemiste bevinding en met een direct bruikbaar
reviewmemorandum. Wat de beoordelaar vorig jaar over een bevinding heeft
opgeschreven, staat dit jaar naast dezelfde bevinding, zodat het dossier over
de jaren heen een lijn houdt. De tool draait lokaal; een auditfile verlaat de
computer van de gebruiker niet.

## Wijzigingen deze ronde

### Nieuw sinds 16 september 2026

Vier functies, gebouwd na de vraag wat de tool voor de assistenten bruikbaarder
zou maken. Alle vier zijn gebouwd en met tests afgedekt; de stand van de tests
staat onder "Tests en uitkomsten".

- **Bevindingen in bulk beoordelen.** De pagina Bevindingen kan bij een groot
  dossier tientallen regels tonen, die tot nu toe stuk voor stuk een
  beoordeling en een notitie moesten krijgen. Er is nu een selectiekolom: vink
  een reeks bevindingen aan, kies één beoordeling en die geldt voor alle
  aangevinkte regels tegelijk. De wijziging wordt pas weggeschreven wanneer de
  gebruiker haar vastlegt, zodat een misklik niet meteen in het dossier staat.
- **Contractregister voor lease en huur.** Nieuwe pagina Contracten
  (`auditfile/contracten.py`). Verplichtingen uit lease- en huurcontracten
  staan niet in de balans maar moeten wel worden toegelicht; de tool rekent per
  contract uit hoeveel maanden er per balansdatum resteren en wat de resterende
  verplichting daarmee is, en telt dat op tot één bedrag. De invoer hoort bij
  één dossier en één boekjaar en blijft op de computer van de gebruiker. Dit is
  een eerste stap: de tool leest de contracten niet uit het auditfile, want die
  staan er niet in, en toetst de gegeven bedragen niet aan de geboekte
  huurlasten.
- **Beoordeling van vorig jaar als referentie.** De pagina Bevindingen toont
  per bevinding wat dezelfde bevinding vorig jaar voor beoordeling kreeg,
  gelezen uit het dossier van het boekjaar dat toch al als "vorig jaar" wordt
  geladen. Die kolom is alleen ter informatie; er wordt nooit iets automatisch
  overgenomen. Het punt waar het om draait: de koppeling blijft ook werken als
  de uitkomst dit jaar anders is dan vorig jaar, bijvoorbeeld een
  rekening-courant die dit jaar wél over de drempel van de Wet excessief lenen
  gaat. Juist dan is het waardevol om te zien wat er vorig jaar over is
  opgeschreven. Daarvoor is naast de bestaande sleutel een tweede, stabiele
  sleutel toegevoegd die niet meebeweegt met de uitkomst van het jaar
  (`auditfile/findings.py`, `identiteitssleutel`).
- **Btw-aangifte inlezen uit het XBRL-bestand.** De aangegeven bedragen moesten
  per rubriek worden overgetypt om ze met het auditfile te kunnen vergelijken.
  Dat kan nu automatisch (`auditfile/aangifte.py`): de btw-aangifte gaat sinds
  1 januari 2014 verplicht als XBRL-bericht via Digipoort naar de
  Belastingdienst, en de gangbare pakketten kunnen dat bestand exporteren. De
  gebruiker laadt alle tijdvakken van het boekjaar tegelijk; de tool telt op en
  meldt het wanneer een tijdvak ontbreekt, twee tijdvakken elkaar overlappen,
  een tijdvak buiten het boekjaar valt, of een bericht bij een ander
  btw-identificatienummer hoort dan het auditfile. Ook een suppletiebericht kan
  worden ingelezen; dat wordt apart geteld en nooit bij de aangiften opgeteld,
  omdat een suppletie de gecorrigeerde stand geeft van een tijdvak waarover al
  aangifte is gedaan. De ingelezen bedragen vullen het formulier als voorstel
  en worden pas bewaard wanneer de gebruiker ze vastlegt.

  Twee keuzes zijn hier van belang voor het platform. De koppeling van veld
  naar rubriek gaat op de elementnaam uit de taxonomie en niet op het
  rubrieknummer van het formulier, omdat dat nummer presentatie is en in het
  verleden is gewijzigd; bij 3a en 3b is dat het duidelijkst, waar pas uit de
  elementnaam blijkt welke van de twee "binnen de EU" betreft. En de namespace
  van het bericht wordt genegeerd, zodat een nieuwe jaarversie van de taxonomie
  geen bestand onleesbaar maakt; wat de tool niet herkent, meldt zij per veld in
  plaats van het stil over te slaan.

### Nieuw sinds 14 september 2026

Op 9 september 2026 had Sylvain twee uitbreidingen goedgekeurd die toen nog
niet gebouwd waren (zie "Open vragen" hieronder in de vorige versie van dit
document). Beide zijn nu gereed, gebouwd op 15 september 2026 en gemerged in
`main` op 16 september 2026.

- **Handmatige rekeningselectie bij excessief lenen.** De drempeltoets
  selecteert rekening-courant- en leningrekeningen op vaste RGS-codes voor
  aandeelhouders en bestuurders; een rekening die de dga bijvoorbeeld als
  "rekening-courant overigen" heeft gecodeerd, viel daardoor buiten de toets.
  De tool meldde dat al, maar corrigeerde het niet. Op de pagina Fiscale
  signalen kan de gebruiker zo'n rekening nu zelf aan de toets toevoegen; de
  tabel met geselecteerde rekeningen laat er per rekening bij zien of zij
  automatisch (op RGS-code of omschrijving) of handmatig is gevonden, en een
  handmatig toegevoegde rekening is ook weer te verwijderen
  (`auditfile/excessief_lenen.py`, functie `build_rc_rekeningen()`). De keuze
  verandert de RGS-selectie zelf niet en geldt alleen voor dat ene dossier; zij
  werkt door in de bevindingen, het reviewmemorandum en de Excel-export, zodat
  die drie dezelfde selectie tonen als de pagina zelf.
- **PDF-export van het reviewmemorandum.** Naast Word en Markdown staat er nu
  een derde downloadknop voor PDF, gegenereerd met `reportlab` op dezelfde
  opgebouwde `Memorandum` en dus met dezelfde formulering als de andere twee
  vormen (`auditfile/memorandum.py`, functie `naar_pdf()`). Lokaal
  gegenereerd, zonder externe dienst. Bij het bouwen kwam aan het licht dat het
  gekozen lettertype (Helvetica) het eurosymbool wel correct tekent, maar geen
  koppeling meelevert waarmee een PDF-lezer het teken bij kopiëren of
  doorzoeken herkent; nagemeten met vier verschillende PDF-programma's, telkens
  hetzelfde resultaat. Het bedrag zelf blijft daardoor onaangetast, alleen het
  euroteken zou bij kopiëren wegvallen; de tool schrijft het teken in de PDF
  daarom voluit als "EUR" zodat een bedrag ook na kopiëren of zoeken klopt.

### 17 juli 2026 tot en met 11 september 2026

In deze periode is de tool feitelijk opnieuw opgebouwd: van een los Streamlit-
script naar een pakket `auditfile/` met een testsuite van 393 tests. Op
hoofdlijnen, met de bron in `ROADMAP.md` en de moduletabel in `AGENTS.md`:

- **Eén bevindingenmodel.** Elke controle levert bevindingen aan één
  verzamelaar (`auditfile/findings.py`), met vier ernstniveaus (kritiek,
  waarschuwing, signaal, niet mogelijk) en een instelbare materialiteitsdrempel.
  Een bevinding onder de drempel wordt gemarkeerd, nooit weggelaten; een
  bevinding zonder bedrag valt nooit onder de drempel. Beoordeling en notitie
  per bevinding worden bewaard bij het dossier en blijven staan bij een
  volgende analyse van hetzelfde dossier.
- **Reviewmemorandum als document.** `auditfile/memorandum.py` bouwt de
  bevindingen om tot een leesbaar stuk: kop met onderneming en boekjaar,
  uitgangspunten met de materialiteitsdrempel, samenvatting, aandachtspunten op
  volgorde van ernst, een eigen sectie voor wat niet kon worden vastgesteld en
  een verantwoording met bewijsniveau en RGS-dekking. Downloadbaar als Word
  (`.docx`) en als Markdown, uit dezelfde opbouw, dus zonder dat de twee vormen
  uiteen kunnen lopen.
- **Suppletiedetectie.** `auditfile/suppletie.py` beantwoordt de vraag die op
  de btw-rondrekening volgt: is er voor het verschil met de aangifte al een
  suppletie geboekt? Zoekt op de btw-rekeningen naar boekingen die zichzelf een
  suppletie, naheffing, aanvullende aangifte of btw-correctie noemen, leest het
  tijdvak uit de omschrijving en zet het geboekte bedrag naast het verschil.
  Boekingen uit de facturatie tellen bewust niet mee, anders vangt het woord
  "correctie" de tegenboeking van elke creditnota op.
- **Openstaande posten en relatiesaldi.** Voor XAF 4.0 een aansluiting van de
  openstaande stand per relatie op het grootboek (`auditfile/relatiesaldi.py`);
  voor XAF 3.2 de subadministratie zelf, met een echte vervaldatum en een
  ouderdomsopbouw in vaste klassen (`auditfile/openstaand.py`). Een
  subadministratieregel draagt geen rekeningnummer; de tool lost de verwijzing
  op en laat leeg zien wanneer dat niet eenduidig kan, in plaats van te gokken.
- **Drempeltoets excessief lenen.** `auditfile/excessief_lenen.py` zet het
  eindsaldo van de rekening-courant- en leningrekeningen met aandeelhouders en
  bestuurders tegenover het wettelijke maximumbedrag, met de opbouw regel voor
  regel en de bron per regel (auditfile, wet of gebruiker). Wat niet uit het
  grootboek volgt (andere vennootschappen, eigenwoningschuld, eerder belast
  fictief voordeel) is expliciet gebruikersinvoer, en de tool zegt dat de toets
  niet mogelijk is bij een gebroken boekjaar of een peildatum zonder
  vastgesteld bedrag.
- **Ratio-analyse.** `auditfile/ratios.py` geeft brutomarge, personeelsquote,
  solvabiliteit en liquiditeit voor beide boekjaren, met per uitkomst de
  opbouw en de dekking van de gebruikte rubrieken. Onder negentig procent
  dekking volgt geen balansratio in plaats van een cijfer dat er goed uitziet.
- **Vaststellen wat een bestand toelaat.** `auditfile/capability.py` bepaalt
  per bestand welke gegevensblokken aanwezig én gevuld zijn en welk
  bewijsniveau daaruit volgt, zodat de tool nooit stilzwijgend aanneemt dat een
  veld is gevuld.
- **Btw-rubricering aangescherpt.** Alle rubrieken van de aangifte zijn
  invulbaar geworden, ook rubrieken die niet in het auditfile voorkomen (een
  leeg veld is iets anders dan een aangifte van nul); verlegde btw komt nu ook
  als voorbelasting in 5b terug; omzetbelasting zelf telt niet langer mee als
  omzet in de periodenanalyse; een btw-voorstel van de tool wordt pas een
  keuze na een handeling van de gebruiker.
- **Nederlandse notatie overal.** Bedragen, percentages en verhoudingen gaan
  via `auditfile/notatie.py`, dus met een komma en zonder dat een
  presentatielaag een eigen versie van dezelfde opmaak bouwt.
- **Privacywaarborg.** Eigen invoer (aangiftebedragen, beoordelingen, de
  dossiergegevens bij excessief lenen) staat per dossier apart in
  `.local-testdata/dossiers/<sleutel>`, buiten Git. Een eigen test
  (`tests/test_runtime_data_not_tracked.py`) bewaakt dat er nooit
  klant-afgeleide invoer in een gevolgd bestand belandt.
- **Onleesbare bedragen worden gemeld, niet meer stil op nul gezet.** Een
  bedrag dat wel is ingevuld maar geen getal is, werd voorheen zonder melding
  0,00. Sinds 11 september 2026 telt de parser deze gevallen en meldt
  `integrity.py` ze met vindplaats als de bevinding "Bedragen leesbaar".
- **Een hergebruikt transactienummer maskeert geen onbalans meer.** De
  transactiebalans groepeerde op dagboek en transactienummer; twee losse,
  óngebalanceerde transacties met hetzelfde nummer sloten daardoor samen ten
  onrechte. `transactie_sleutel()` in `parsing.py` groepeert nu op het
  volgnummer dat de parser zelf toekent, gebruikt door `integrity.py`, `vat.py`
  en `suppletie.py`. Het hergebruik zelf blijft gemeld: nagezocht in de
  officiële specificatie (`XMLAuditfileFinancieel_4.0_FunHie.pdf`, downloaded
  van de Belastingdienst/ODB-pagina) staat vast dat een transactienummer uniek
  moet zijn binnen het dagboek, ook al dwingt geen van beide XAF-schema's dit
  af. De bevinding "Transactienummer eenduidig binnen het dagboek" blijft
  daarom een waarschuwing en geen kritieke bevinding: de cijfers kloppen, de
  herleidbaarheid van dagboek plus transactienummer niet.

## Fiscale bronnen en conclusies

Vastgelegd met vindplaats in `docs/btw-bronnen.md`, geraadpleegd op
1 september 2026:

| Onderwerp | Conclusie | Vindplaats |
|---|---|---|
| Btw-rubrieken van de aangifte | Indeling gelijk voor 2024–2026, met de aangepaste kolomkoppen sinds 2025 | Belastingdienst, *Toelichting bij de btw-aangifte*, uitgaven 2024/2025/2026 |
| Verleggingsregeling | Verlegde btw in 2a, aftrek in 5b onder de gewone voorwaarden | Art. 12 lid 5 Wet OB 1968; art. 24b/24ba Uitv.besl. OB 1968 |
| Aftrek bij verlegging, invoer en intracommunautaire verwerving | 2a, 4a en 4b zijn aftrekbaar in 5b, aandeel standaard 100%, aanpasbaar | Art. 15 lid 1 Wet OB 1968 |
| Drempel excessief lenen | € 700.000 per 31-12-2023, € 500.000 vanaf 31-12-2024, niet geïndexeerd | Art. 4.14a lid 2 en 4 Wet IB 2001; Stb. 2022, 531 en Stb. 2023, 499 |
| Boetes en dwangsommen | Bepaalde boeten en bestuursrechtelijke dwangsommen niet aftrekbaar in de IB, doorwerkend naar de Vpb | Art. 3.14 lid 1 onderdelen c en i Wet IB 2001; art. 8 lid 1 Wet Vpb 1969 |
| Niet in de balans opgenomen verplichtingen (lease en huur) | Een lopende huur- of leaseverplichting hoort in de regel niet als schuld op de balans, maar bij materialiteit wel in de toelichting | Art. 2:381 lid 1 BW; RJ 214 voor de rechtspersonen die daaronder vallen |
| Velden van de btw-aangifte in XBRL | Elk veld van de aangifte gekoppeld aan zijn rubriek, met het Nederlandse label en het paragraafnummer van de definitie | Nederlandse Taxonomie, belastingdienstdeel `bd-omzetbelasting` (schema, label- en reference-linkbase); *Belastingdienst taxonomie definities* |

Twee punten staan met een uitdrukkelijk voorbehoud in de bron zelf: het bedrag
van de drempel excessief lenen per peildatum 31 december 2026 staat onder
voorbehoud van het Belastingplan 2027, en de fiscale behandeling van
belastingrente en invorderingsrente is niet in de tool verwerkt omdat art. 3.14
Wet IB 2001 daar niets over zegt.

## Tests en uitkomsten

```
"C:\Python314\python.exe" -m pytest tests/
471 passed
```

Alle tests groen. Gemeten op 18 september 2026: 451 op `main`, en 471 met de
aangiftefunctie erbij die op dat moment nog niet was gemerged. Eerdere standen:
431 op 16 september 2026 en 418 op 14 september 2026. De 40 tests die er deze
ronde bij kwamen horen bij de vier functies hierboven; 20 daarvan gaan over het
inlezen van de aangifte, waaronder een test die vastlegt dat een bericht ook
wordt gelezen wanneer het een nieuwere versie van de taxonomie gebruikt, en een
test die bevestigt dat de vorig-jaar-beoordeling gekoppeld blijft wanneer de
uitkomst van dit jaar verandert.

De tests bouwen hun eigen synthetische bestanden op in het geheugen
(`auditfile/demo.py`), inclusief het XBRL-aangiftebericht; er wordt nooit
klantdata gelezen, ook niet tijdens het testen.

## Testberekeningen

Twee representatieve gevallen, doorgerekend met de echte rekenkern op
synthetische data.

**Drempeltoets excessief lenen** (`auditfile.excessief_lenen.beoordeel`):
rekening-courant eindsaldo € 620.000,00, boekjaar 2025 (drempel dat jaar
€ 500.000,00). Tooluitkomst: status "boven de drempel", bovenmatig deel
€ 120.000,00, met de opbouw regel voor regel (auditfile → schuld,
gebruikersinvoer op nul voor eigenwoningschuld en andere vennootschappen, de
wettelijke drempel, het bovenmatige deel). Rekenkundig correct: € 620.000,00
− € 500.000,00 = € 120.000,00.

**Suppletie** (`auditfile.suppletie.bouw_aansluiting`): een boeking over Q4 2025
van € 1.500,00 die zichzelf "Suppletie omzetbelasting Q4" noemt, zonder
ingevoerd aangiftebedrag. Tooluitkomst: status "Suppletie geboekt, verschil
niet vast te stellen", met de toelichting dat er zonder aangiftebedrag niets
tegenover de boeking te zetten is. Dat is het bedoelde gedrag: de tool
concludeert niet dat er te veel of te weinig is gesuppleerd zonder een
aangiftebedrag als vergelijkingsbasis.

**Inlezen van de aangifte** (`auditfile.aangifte.lees_aangifte` en `tel_op`):
vier synthetische XBRL-kwartaalberichten over boekjaar 2025, elk met een omzet
tegen het algemene tarief van € 34.600,00, daarover € 7.266,00 btw, en
€ 630,00 voorbelasting. Hier rekent de tool niet aan de btw zelf: zij leest de
bedragen die in de berichten staan en telt de tijdvakken op. De verwachte
uitkomst is daarom de som van de vier berichten: 4 × € 34.600,00 =
€ 138.400,00 omzet in rubriek 1a, 4 × € 7.266,00 = € 29.064,00 btw in 1a en
4 × € 630,00 = € 2.520,00 voorbelasting in 5b. Tooluitkomst: exact die drie
bedragen, zonder meldingen.

Tweede geval, met hetzelfde materiaal maar zonder het derde kwartaal.
Tooluitkomst: € 21.798,00 btw in 1a, gelijk aan 3 × € 7.266,00, met de melding
"Tussen 2025-06-30 en 2025-10-01 zit een gat: er ontbreekt een tijdvak." De
tool telt dus wat zij krijgt en verzwijgt niet dat het onvolledig is; het is
aan de gebruiker om te beoordelen of dat tijdvak ontbreekt of dat er geen
aangifte over hoefde.

## Open vragen

De twee punten die in de vorige versie van dit document hier stonden
(handmatige rekeningselectie bij excessief lenen en PDF-export van het
reviewmemorandum) zijn gebouwd; zie "Nieuw sinds 14 september 2026" hierboven.

Nieuw open sinds deze ronde:

1. **Het inlezen van de aangifte is nog niet getoetst op een echte export.**
   De koppeling van veld naar rubriek is overgenomen uit de taxonomie van de
   Belastingdienst zelf en getest met een synthetisch bericht, maar er is nog
   geen XBRL-bestand uit een echt pakket doorheen gehaald. Te sluiten met één
   export uit AFAS Profit of Exact Online, bij voorkeur van een eigen of
   fictief dossier. De tool is erop ingericht dat dit zichtbaar misgaat en niet
   stil: elk veld dat zij niet herkent, meldt zij bij naam.
2. **Het contractregister is een eerste stap.** De contracten worden handmatig
   vastgelegd, de tool leest ze niet uit het auditfile (ze staan er niet in) en
   legt de opgegeven bedragen niet naast de geboekte huur- en leasekosten van
   het boekjaar. Of die aansluiting erbij moet, is een keuze die nog niet is
   gemaakt.

Uit `ROADMAP.md` staat verder nog open:

1. **XSD-validatie en versie-echte fixtures.** Het gegenereerde 3.2-testbestand
   valideert sinds 2 september 2026 tegen het schema, met de hand gecontroleerd
   en niet in een test vastgelegd, omdat het officiële schema niet in de
   repository staat en `auditfile.nl` niet meer bereikbaar is. Te beslissen: de
   XSD en het officiële testbestand van de Belastingdienst
   (`XAF_4_0_Test_100425.XAF`) alsnog opnemen, met een uitzondering in
   `.gitignore`.
2. **Vergelijking tegen het bronmodel.** Voor tools die op een bestaand
   Wolters Kluwer-model zijn gebouwd geldt een verschillenbewijs; voor deze
   tool is dat niet aan de orde omdat zij uit de wet is opgebouwd en niet op
   een extern model is gebaseerd.

Kleinere technische restpunten uit de laatste review (zonder fiscale impact,
zie `ROADMAP.md` voor detail): bedragen lopen nog als float door de tool in
plaats van als `Decimal` (de transactiesleutel en de onleesbare bedragen zijn
inmiddels wel opgelost, zie hierboven), en de controletotalen van de
subadministratie worden wel ingelezen maar nog niet tegen een bevinding
getoetst.

## Actie voor Bram

Geen platformaanpassing gevraagd. Deze ronde bestaat uit functies binnen de
tool zelf; er is niets nodig van de Join/DK-kant om ze te laten werken.

Wel twee punten die het overwegen waard zijn wanneer de tool naar het platform
gaat, omdat ze daar anders opnieuw moeten worden bedacht:

1. **Het inlezen van de btw-aangifte is breder bruikbaar dan deze tool.** Elke
   toepassing die een aangegeven bedrag naast een administratie legt, kan
   hetzelfde XBRL-bericht gebruiken; het formaat is gestandaardiseerd en voor
   alle pakketten gelijk. De koppeling van veld naar rubriek staat met haar
   vindplaats in `docs/btw-bronnen.md` en is los van deze tool te hergebruiken.
   Het is de moeite waard om die koppeling op het platform op één plek te
   houden in plaats van per tool.
2. **De beoordeling van vorig jaar veronderstelt dat het vorige dossier
   bewaard is.** In deze tool staat die beoordeling lokaal op de computer van
   de gebruiker, per onderneming en boekjaar. Op een platform met meerdere
   gebruikers is dat een ander vraagstuk: wie ziet wiens beoordeling, en hoe
   lang wordt zij bewaard. Dat is een keuze voor de platformkant, niet iets
   wat de tool zelf kan oplossen.
