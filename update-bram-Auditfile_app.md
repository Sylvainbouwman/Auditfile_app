# Update voor Bram — Auditfile Analyzer

Eerste opleverdocument voor deze tool. Dekt de periode 17 juli 2026 tot en met
11 september 2026 (er is tussen 14 juli en 25 augustus niet aan de tool
gewerkt).

## Doel en waarde

Fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en het
belastingadvies. Laadt twee XAF-auditfiles (vorig jaar en huidig jaar),
vergelijkt ze en voert fiscale controles uit: btw-rondrekening, suppletie,
periodieke en analytische controles, jaar-op-jaar vergelijking, ratio-analyse,
de drempeltoets excessief lenen en een Excel-export. Alles komt samen in een
automatisch gegenereerd reviewmemorandum, als Word-document en als Markdown.

Waarde voor het kantoor: de handmatige Excel-analyse bij een samenstelopdracht
(exporteren, vergelijken met vorig jaar, de checklist doorlopen) wordt
vervangen door een tool die dezelfde controles gestandaardiseerd uitvoert, met
minder kans op een gemiste bevinding en met een direct bruikbaar
reviewmemorandum. De tool draait lokaal; een auditfile verlaat de computer van
de gebruiker niet.

## Wijzigingen deze ronde

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

Twee punten staan met een uitdrukkelijk voorbehoud in de bron zelf: het bedrag
van de drempel excessief lenen per peildatum 31 december 2026 staat onder
voorbehoud van het Belastingplan 2027, en de fiscale behandeling van
belastingrente en invorderingsrente is niet in de tool verwerkt omdat art. 3.14
Wet IB 2001 daar niets over zegt.

## Tests en uitkomsten

```
"C:\Python314\python.exe" -m pytest tests/
418 passed in 44.11 s
```

Alle tests groen, gedraaid op 14 september 2026. De tests bouwen hun eigen
synthetische auditfiles op in het geheugen (`auditfile/demo.py`); er wordt
nooit klantdata gelezen, ook niet tijdens het testen.

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

## Open vragen

Uit `ROADMAP.md`, besluiten van Sylvain op 9 september 2026, nog niet gebouwd:

1. **Handmatige rekeningselectie bij excessief lenen.** Een rekening-courant
   die niet op de gebruikelijke RGS-codes staat (bijvoorbeeld gecodeerd als
   "overigen") valt nu buiten de automatische selectie; de tool meldt dat wel,
   maar corrigeert het niet. Goedgekeurd: de gebruiker mag zo'n rekening
   handmatig toevoegen, met zichtbaar onderscheid tussen automatisch en
   handmatig geselecteerd. Verandert de fiscale reikwijdte van de toets niet.
2. **PDF-export van het reviewmemorandum.** Goedgekeurd, naast de bestaande
   Word- en Markdown-uitvoer, op dezelfde opgebouwde `Memorandum` en lokaal
   gegenereerd zonder externe dienst.
3. **XSD-validatie en versie-echte fixtures.** Het gegenereerde 3.2-testbestand
   valideert sinds 2 september 2026 tegen het schema, met de hand gecontroleerd
   en niet in een test vastgelegd, omdat het officiële schema niet in de
   repository staat en `auditfile.nl` niet meer bereikbaar is. Te beslissen: de
   XSD en het officiële testbestand van de Belastingdienst
   (`XAF_4_0_Test_100425.XAF`) alsnog opnemen, met een uitzondering in
   `.gitignore`.
4. **Vergelijking tegen het bronmodel.** Voor tools die op een bestaand
   Wolters Kluwer-model zijn gebouwd geldt een verschillenbewijs; voor deze
   tool is dat niet aan de orde omdat zij uit de wet is opgebouwd en niet op
   een extern model is gebaseerd.

Kleinere technische restpunten uit de laatste review (zonder fiscale impact,
zie `ROADMAP.md` voor detail): bedragen lopen nog als float door de tool in
plaats van als `Decimal` (de transactiesleutel en de onleesbare bedragen zijn
inmiddels wel opgelost, zie hierboven), en de controletotalen van de
subadministratie worden wel ingelezen maar nog niet tegen een bevinding
getoetst.
