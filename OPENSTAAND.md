# Openstaande punten

Formaat: per punt

> Dit document is de bron voor de openstaande punten van deze tool. Elk punt heeft een
> status (open of gesloten), een eigenaar (Sylvain of sessie) en een vindplaats. Een
> gesloten punt blijft staan, met datum en reden. Het overzicht in
> `AI_kopgroep/OPEN-PUNTEN.md` leest de regel "Formaat: per punt" hierboven en toont dan
> alleen de open punten met eigenaar Sylvain. Wat een sessie zelf kan doen, staat hier
> wel maar niet in dat overzicht.
>
> `ROADMAP.md`, `update-bram-Auditfile_app.md`, `UC_Auditfile_app.md` en `README.md` zijn
> beschrijving of verslag. Een punt dat daarin nog open staat, hoort hier.
>
> Omgezet naar deze vorm op 04-10-2026 23:13 CEST. De tekst van daarvoor staat in de
> Git-historie (laatste versie in commit d77e214). De twee bestaande punten, die nog geen
> nummer hadden, staan hieronder woordelijk als punt 1 en 2. Punten 3 t/m 41 zijn bij
> de omzetting toegevoegd uit `ROADMAP.md`, `update-bram-Auditfile_app.md`,
> `UC_Auditfile_app.md`, `README.md` en de twee documenten in `docs/`. Waar elk punt uit die
> documenten is gebleven staat in `omzetting-actiedocumenten-2026-10-04.md`. Nummers worden
> nooit hergebruikt.

**Over eigenaarschap.** De POC is van Sylvain en hij beslist alles wat erin zit. Bram
bouwt de tool daarna op de kantooromgeving en kijkt niet in deze repository. Een punt dat
een fiscaal of inhoudelijk besluit van Sylvain vraagt heeft hem als eigenaar. Dingen die de
tool bewust niet doet en zelf meldt staan open met eigenaar sessie en zijn als achtergrond
gemarkeerd. De eigenaar van de twee bestaande punten is niet inhoudelijk gewijzigd.

## Open

### 3. Contractregister legt de bedragen niet naast de geboekte huur- en leasekosten
- **Status:** open, wacht op besluit van Sylvain
- **Eigenaar:** Sylvain
- **Vindplaats:** `auditfile/contracten.py`; `ROADMAP.md`, r.31, r.38 en r.339; `update-bram-Auditfile_app.md`, r.65 en r.310

Het contractregister is een eerste stap. De contracten worden handmatig vastgelegd en de tool legt de opgegeven bedragen niet naast de geboekte huur- en leasekosten van het boekjaar. Ook een signaal als er kosten zijn geboekt maar geen contract is vastgelegd ontbreekt, net als de detectie van een operationele lease die niet als verplichting zichtbaar is. Dat vervolg raakt het bevindingenmodel en is bewust niet in de eerste stap meegenomen. Of die aansluiting erbij moet is een keuze die nog niet is gemaakt.

**Te sluiten wanneer:** besloten is of de aansluiting en het signaal erin komen of vastgelegd is dat het register een handmatige registratie blijft.

### 4. Geen contante waarde en geen kwalificatie van een lease als operationeel of financieel
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/contracten.py`; README, rubriek Contracten; `ROADMAP.md`, r.36 en r.340

Het register telt alleen de resterende termijnen per de balansdatum op (jaarbedrag gedeeld door twaalf maal het aantal resterende maanden). Er is geen contante-waardeberekening en het contract wordt niet gekwalificeerd als operationele of financiële lease. Dat blijft aan de gebruiker. Ook het onderscheid op basis van boekingen is niet gebouwd.

### 6. Kleinere ideeën zonder besluit: meerjarenvergelijking, vuistregels per kantoor, samenvatting en KVK of SBI
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `ROADMAP.md`, rubriek Wat de assistenten nog super bruikbaar zou maken; `ROADMAP.md`, r.105

Genoemd maar niet in de bouwvolgorde van 16 september 2026 opgenomen: een meerjarenvergelijking (drie tot vijf boekjaren in plaats van twee), instelbare vuistregels per kantoor (het personeelsbedrag en de materialiteitsdrempel), een korte samenvatting in gewone taal boven het memorandum en een koppeling met KVK-nummer of SBI-code voor duiding van signalen. Er is niet over besloten.

### 7. Geen schema-validatie voor XAF 3.2 en niet van het ingelezen bestand
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `tests/test_xsd.py`; `docs/xaf-velden.md`, paragraaf Herkomst van deze paragraaf; `ROADMAP.md`, r.111, r.449 en r.578; `update-bram-Auditfile_app.md`, r.318

Drie zaken horen hierbij. Ten eerste valideert het gegenereerde 3.2-bestand sinds 02-09-2026 tegen het 3.2-schema, maar dat is met de hand vastgesteld en niet in een test vastgelegd: de XSD van 3.2 staat niet in de repository en `auditfile.nl` is niet meer bereikbaar. Wat rest is een 3.2-schema uit een betrouwbare bron. Voor 4.0 is dit sinds 26-09-2026 wel geborgd: de XSD en het officiële testbestand staan in `docs/xaf-schema/` en `tests/test_xsd.py` valideert het testbestand en de 4.0-bestanden uit `demo.py` (daarmee is de vraag uit het opleverdocument voor Bram beantwoord). Ten tweede is er geen bewijs dat alle gedeeltelijke exports of beide XAF-versies tegen de XSD zijn gevalideerd (hercontrole in `ROADMAP.md`). Ten derde valideert de parser het ingelezen bestand niet: zij leest wat er is en wijst een bestand niet af, terwijl een schemavalidatie een kapot bestand hard zou afwijzen in plaats van half in te lezen. Een bedrag dat geen getal is wordt sinds 11-09-2026 wel gemeld (bevinding Bedragen leesbaar).

**Te sluiten wanneer:** een 3.2-schema uit een betrouwbare bron is opgenomen of vastgelegd is dat 3.2 niet wordt gevalideerd en besloten is of een ingelezen bestand tegen het schema wordt getoetst.

### 11. De btw-vergelijking gaat per boekjaar en niet per aangiftetijdvak
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/vat.py`; `ROADMAP.md`, r.160

Bewuste keuze volgens `ROADMAP.md`: de tool ondersteunt de assistent die met de jaarrekening begint en wil weten waar de aandachtspunten zitten, niet de aangiftecontrole per tijdvak. Een uitsplitsing per maand of kwartaal staat daarom niet op de rol.

### 13. Btw op privé-uitgaven signaleren
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/vat.py`, r.173; `auditfile/controls.py`, r.717-722; `ROADMAP.md`, r.172

Op de roadmap staat de signalering van btw op privé-uitgaven. Vermoeden zonder bewijs: er is een rubricevoorstel dat op privégebruik wijst (`vat.py`, rubriek 1d) en een fiscaal signaal Auto en privegebruik (`controls.py`), maar een signaal dat btw op privé-uitgaven als zodanig meldt is niet gevonden. Daarom blijft het punt open.

**Te sluiten wanneer:** aangetoond is dat een bestaand signaal dit dekt (met een test) of het signaal is gebouwd of besloten is dat het niet komt.

### 15. Aangiftetijdlijn reconstrueren uit boekingen
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/aangifte.py`; `auditfile/suppletie.py`; `ROADMAP.md`, r.178

Genoemd onder Aangifte-detectie in de roadmap. Niet teruggevonden in de code (gezocht op tijdlijn in `auditfile/`). De aangifte-inlezer leest de tijdvakken uit het XBRL-bericht; een reconstructie uit de boekingen zonder aangiftebestand is iets anders en is niet gebouwd.

**Te sluiten wanneer:** de reconstructie is gebouwd of besloten is dat zij vervalt.

### 18. Periodecontrole op maanden zonder inkopen
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`; `ROADMAP.md`, r.204

De roadmap noemt maanden zonder omzet, zonder inkopen en zonder loonkosten. Omzet en loonkosten zijn gebouwd. Voor inkopen is in `controls.py` geen periodecontrole gevonden.

**Te sluiten wanneer:** de controle is gebouwd of besloten is dat zij vervalt.

### 20. Veel kleine boekingen net onder een drempelwaarde (splitsingsrisico)
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`; `ROADMAP.md`, r.214

Genoemd onder Ongebruikelijke boekingen. In `controls.py` is geen signaal gevonden voor veel kleine boekingen net onder een drempelwaarde (gezocht op splits en net onder).

**Te sluiten wanneer:** het signaal is gebouwd of besloten is dat het vervalt.

### 21. Ouderdom op niveau 2 alleen vanaf factuurdatum en relatieanalyse over mutaties
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/openstaand.py`; `auditfile/controls.py`; `ROADMAP.md`, r.260 en r.265

Op niveau 2 (subadministratie zonder vervaldatum) is er geen vervaldatum en is alleen de ouderdom vanaf de factuurdatum te geven. De relatieanalyse zelf gaat over mutaties in het boekjaar en niet over openstaande posten; de oude openstaande posten komen via de ouderdomsanalyse op niveau 1 of 2.

### 22. Geen normwaarden en geen branchevergelijking bij de ratio's
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/ratios.py`; `ROADMAP.md`, r.285

De tool signaleert een verschuiving van vijf procentpunt in de marge of de personeelsquote, een daling van tien procentpunt in de solvabiliteit, een negatief eigen vermogen en kortlopende schulden boven de vlottende activa. Normwaarden en een vergelijking met de branche zijn bewust niet opgenomen.

### 25. De drempeltoets excessief lenen is bewust geen vaststelling
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/excessief_lenen.py`; `ROADMAP.md`, r.312

De wet toetst de belastingplichtige en zijn partner over alle vennootschappen per 31 december; het auditfile is het grootboek van één vennootschap op de balansdatum. De eigenwoningschuld met hypotheekrecht en het eerder belaste fictieve reguliere voordeel staan niet in een grootboek en zijn invoer in de opbouw, met de bron per regel. Bij een gebroken boekjaar en bij een peildatum zonder vastgesteld bedrag zegt de tool dat de toets niet mogelijk is.

### 26. Autokosten zonder bijtelling signaleren
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, r.717-722; `ROADMAP.md`, r.320

Op de roadmap staat: autokosten aanwezig maar geen bijtelling geboekt. Vermoeden zonder bewijs: het fiscale signaal Auto en privegebruik in `controls.py` selecteert autokosten op de omschrijving en vraagt om beoordeling van de bijtelling. Of de specifieke toets (geen bijtelling geboekt) bestaat is niet vastgesteld, dus het punt blijft open.

**Te sluiten wanneer:** aangetoond is dat het bestaande signaal dit dekt (met een test) of de toets is gebouwd of besloten is dat zij niet komt.

### 27. Privé-opnamen en box 3-relevantie signaleren
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, r.711-716; `auditfile/excessief_lenen.py`; `ROADMAP.md`, r.324, r.325 en r.326

Op de roadmap staan grote vorderingen op aandeelhouders, ongebruikelijke privé-opnamen en signalering van mogelijke box 3-relevantie. Vermoeden zonder bewijs: het signaal Rekening-courant met aandeelhouder of directie en de drempeltoets excessief lenen dekken een deel. Ongebruikelijke privé-opnamen en box 3-relevantie als zodanig zijn niet gevonden, dus het punt blijft open.

**Te sluiten wanneer:** per onderdeel aangetoond is wat bestaat of is gebouwd of besloten is dat het niet komt.

### 28. AFAS-koppeling en vergelijking met branchegemiddelden (SBI)
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `ROADMAP.md`, rubriek Toekomstige mogelijkheden; `ROADMAP.md`, r.375 en r.376

Toekomstige mogelijkheden zonder besluit: een koppeling met AFAS (GetConnector) voor automatische import van de jaarrekening en een vergelijking met branchegemiddelden op basis van de SBI-code. De tool draait lokaal en gebruikt geen externe API.

### 29. Open posten op niveau 4 (reconstructie uit boekingsregels) is niet gebouwd
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/capability.py`; `auditfile/openstaand.py`; `ROADMAP.md`, r.424; `docs/xaf-velden.md`, r.203

Niveau 4 is een reconstructie uit grootboekregels waarbij de factuurreferentie en de relatie op beide zijden staan: alleen met de gebruikte methode en de gemeten dekking in beeld en met een betalingstermijn die de gebruiker zelf opgeeft. Voor de nu beschikbare klantbestanden levert het niets op, want daar staat de factuurreferentie vrijwel alleen op de factuurzijde. Salderen per referentie zou dan vrijwel elke factuur als openstaand laten staan en dat oogt volledig terwijl het onwaar is.

**Te sluiten wanneer:** een bestand beschikbaar is waarop niveau 4 zinvol te meten is en het is gebouwd of besloten is dat het niet komt.

### 30. Versie-echte fixtures voor gedeeltelijk gevulde exports
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/demo.py`; `tests/test_openstaand.py`; `ROADMAP.md`, r.431; `update-bram-Auditfile_app.md`, r.318

`vul_subadministratie()` levert een 3.2-bestand met subadministratie en `vul_relatiesaldi()` een 4.0-bestand met relatiesaldi. Nog niet gebouwd zijn gedeeltelijk gevulde exports, zoals een subadministratie zonder vervaldatum of met een verwijzing die niet oplost. Vermoeden zonder bewijs voor de volledigheid: `tests/test_openstaand.py` dekt volgens de roadmap al een ontbrekende vervaldatum en een ambigue rekeningkoppeling.

**Te sluiten wanneer:** per gedeeltelijke export een test bestaat of vastgelegd is welke gevallen bewust niet worden gedekt.

### 31. Ratio's met een teller op omschrijving blijven gevoelig voor het rekeningschema
- **Status:** open, bewuste beperking, als achtergrond gemarkeerd op 04-10-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/ratios.py`; `ROADMAP.md`, r.484

Een ratio met een teller die op de omschrijving berust blijft gevoelig voor het rekeningschema. De omzetselectie sluit woorden als inkoop en kosten vooraf uit, maar een schema zonder RGS-codes en met eigenzinnige omschrijvingen kan een rekening nog verkeerd indelen. De kolom methode en de opbouw maken dat zichtbaar zonder het te voorkomen.

### 32. De rondrekening telt een suppletie met btw-code als facturatie
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/vat.py`; `tests/test_suppletie.py`, r.92 en r.100; `ROADMAP.md`, r.509

De rondrekening in `vat.py` telt een suppletie met btw-code nog als facturatie en niet als overige mutatie. Wat dat doet met de controleregel btw uit facturatie tegenover de btw-codes is niet gemeten. Het besluit van 27-09-2026 over de suppletie met btw-code zelf (alleen in het memoriaal en met een trefwoord van hoge zekerheid) is vastgelegd in de twee genoemde tests.

**Te sluiten wanneer:** gemeten is wat het doet met die controleregel en dat is vastgelegd in een test of de rondrekening is aangepast.

### 37. docs/xaf-velden.md zegt nog dat sbType en mutTp niet zijn vastgesteld
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `docs/xaf-velden.md`; `docs/xaf-velden.md`, r.155 en r.164

De tabel (r.155-156) en de alinea eronder (r.158-165, met de zin Open punt) zeggen dat de betekenis niet is vastgesteld. `ROADMAP.md` legt vast dat de betekenis op 11-09-2026 is gevonden. Het document is dus achterhaald. Niet aangepast bij de omzetting van deze lijst, want daarbij wijzigen alleen `OPENSTAAND.md` en het omzettingsbestand.

**Te sluiten wanneer:** `docs/xaf-velden.md` is bijgewerkt met de gevonden betekenis en de vindplaats.

### 38. Maximumbedrag excessief lenen per 31-12-2026 staat onder voorbehoud van het Belastingplan 2027
- **Status:** open, wacht op het Belastingplan 2027
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/excessief_lenen.py`, `MAXIMUMBEDRAGEN`; `docs/btw-bronnen.md`, r.205-230; `docs/btw-bronnen.md`, r.229; `update-bram-Auditfile_app.md`, r.229

Volgens de tabel in `docs/btw-bronnen.md` is het maximumbedrag € 500.000 voor peildatum 31 december 2026, onder voorbehoud van het Belastingplan 2027. Voor een peildatum buiten de reeks geeft de tool geen bedrag en zegt zij dat de toets niet mogelijk is.

**Te sluiten wanneer:** het Belastingplan 2027 is vastgesteld en het bedrag voor 2026 is bevestigd of aangepast, met de vindplaats erbij.

### 39. Belastingrente en invorderingsrente zijn niet in de tool verwerkt
- **Status:** open, fiscale vraag, wacht op besluit van Sylvain
- **Eigenaar:** Sylvain
- **Vindplaats:** `docs/btw-bronnen.md`; `update-bram-Auditfile_app.md`, r.232

De fiscale behandeling van belastingrente en invorderingsrente is niet in de tool verwerkt, omdat art. 3.14 Wet IB 2001 daar niets over zegt. Er is geen bron vastgelegd waaruit de behandeling volgt. Of dit erin moet komen vraagt een fiscaal besluit na bronverificatie.

**Te sluiten wanneer:** een bron is vastgelegd en besloten is of de behandeling erin komt of vastgelegd is dat de tool er bewust niets mee doet.

### 40. Overdracht aan de platformbouw: aangifte-koppeling en bewaring van de beoordeling van vorig jaar
- **Status:** open, overdracht aan de platformbouw (Bram)
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/aangifte.py`; `auditfile/settings.py`; `docs/btw-bronnen.md`; `update-bram-Auditfile_app.md`, r.343 en r.350

Twee aanbevelingen voor het moment dat de tool naar het platform gaat. Eén: de koppeling van XBRL-veld naar rubriek is breder bruikbaar dan deze tool en hoort op het platform op één plek te staan. Twee: de beoordeling van vorig jaar staat nu lokaal per onderneming en boekjaar; op een platform met meerdere gebruikers is wie wiens beoordeling ziet en hoe lang zij wordt bewaard een keuze voor de platformkant. De implementatie is aan Bram. Er is geen platformaanpassing gevraagd.

**Te sluiten wanneer:** de platformbouw de aanbevelingen heeft beoordeeld of vastgelegd is dat zij vervallen.

### 41. De use case zegt client-side verwerking, README beschrijft verwerking in het Python-proces
- **Status:** open
- **Eigenaar:** sessie
- **Vindplaats:** `UC_Auditfile_app.md`, r.43; `README.md`, rubriek Privacy; `UC_Auditfile_app.md`, r.43; `README.md`, r.304

`UC_Auditfile_app.md` zegt onder Waarde dat de verwerking volledig client-side is en dat klantdata de browser niet verlaat. De tool is een Streamlit-app en `README.md` legt uit dat het bestand naar het Python-proces gaat, dat lokaal of op een server kan draaien. Alleen bij lokale uitvoering blijft het bestand op de eigen computer. De formulering in de use case klopt dus niet voor de tool zoals zij is gebouwd.

**Te sluiten wanneer:** de use case is aangepast of is vastgesteld dat de formulering bedoeld is voor een andere uitvoering.

## Gesloten

### 1. Fiscale bronnen niet online te bevestigen (27-09-2026)
- **Status:** gesloten 27-09-2026
- **Eigenaar:** Sylvain
- **Vindplaats:** herkansing door de agent `toolbouw:bron-controleur` op 27-09-2026, in het kader van de statuswijziging van `auditfile-app` in `bouwman-tools/tools.json`

Bij de eerste ronde gaf `WebFetch` op `wetten.overheid.nl` een timeout, een verbroken
verbinding en een afgekapte pagina. Via `curl` met HTTP/1.1 kwam de wettekst wel binnen,
en daarmee zijn alle vijf punten alsnog bevestigd, zonder afwijking:

- art. 4.14a lid 2 Wet IB 2001, bedrag € 500.000 (`auditfile/excessief_lenen.py:83-85`):
  klopt, ook in de versie "geldend van 21-02-2026 t/m heden"
  (https://wetten.overheid.nl/BWBR0011353/2026-02-21). De wijziging van 21-02-2026 raakt
  dit bedrag niet.
- art. 10.1 Wet IB 2001, geen indexatie van art. 4.14a (`auditfile/excessief_lenen.py:75-77`):
  klopt. De opsomming in lid 1 noemt art. 4.14a niet.
- art. 15 lid 1 Wet OB 1968, onderdelen b, c 1° en c 2° (`auditfile/vat_rubrics.py:122-137`,
  `AFTREKBAAR_IN_5B`): klopt, inclusief de letterlijke slotzin op regel 132-133
  (https://wetten.overheid.nl/BWBR0002629/2026-01-01).
- Toelichting btw-aangifte 2026 (Belastingdienst-PDF), rubrieknamen 1a-5g
  (`auditfile/vat_rubrics.py:51-117`): klopt, met één kanttekening zonder gevolg voor de
  code — de toelichting behandelt 1a en 1b onder één gezamenlijk kopje, en noemt de
  omschrijving van subtotaal 5a niet apart (5c-5g bestaan volgens diezelfde toelichting
  niet meer, wat overeenkomt met de code).
- paragraafnummer 509383 bij de btw van rubriek 1a in de XBRL-taxonomie
  (`auditfile/aangifte.py:67`): klopt, nagelopen in de referentielinkbase van de
  NT20-taxonomie (`bd-i_ValueAddedTaxSuppliesServicesGeneralTariff` → 509383;
  `bd-i_TaxedTurnoverSuppliesServicesGeneralTariff` → 509382). De eerdere inconsistente
  automatische uitlezing kwam waarschijnlijk doordat elk element ook referenties zonder
  paragraafnummer heeft.

### 2. Kapotte documentverwijzing (27-09-2026)
- **Status:** gesloten 27-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/aangifte.py`, r.24

`auditfile/aangifte.py:24` verwees naar
`docs/xbrl-aangifte.md`, dat niet bestaat. Hersteld naar `docs/btw-bronnen.md`,
waar de tabel met definities en vindplaatsen daadwerkelijk staat.

### 5. Het inlezen van de aangifte is getoetst op een echte export
- **Status:** gesloten 04-10-2026, bewijs in ROADMAP.md van 26-09-2026 en 27-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/aangifte.py`; `tests/test_aangifte.py`, `test_een_suppletie_wordt_herkend_aan_het_schema`; `ROADMAP.md`, r.82, r.87 en r.95; `update-bram-Auditfile_app.md`, r.303

Gesloten 04-10-2026. Het punt stond in `update-bram-Auditfile_app.md` (Open vragen, punt 1) en in `ROADMAP.md` (punt 4, Wat rest) als nog niet getoetst op een echte export. `ROADMAP.md` legt vast dat `lees_aangifte()` op 26-09-2026 een echt XBRL-bericht (een aangifte over één maandtijdvak) en op 27-09-2026 een echte suppletie (jaartijdvak 2024) heeft verwerkt, met de niet-herkende kopgegevens als niet meegeteld gemeld. De bestanden staan lokaal in `testfiles/` en niet in Git. Het bewijs is dus een gedateerde meting in het document en geen test in de testset. De synthetische berichten uit `demo.py` worden wel door `tests/test_aangifte.py` gedekt. Het opleverdocument voor Bram (stand 22-09-2026) is op dit punt achterhaald.

### 8. Onleesbare bedragen werden stil op nul gezet
- **Status:** gesloten 04-10-2026, hersteld op 11-09-2026 met tests
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/parsing.py`; `auditfile/integrity.py`; `tests/test_leesbare_bedragen.py`, `test_onleesbaar_bedrag_wordt_geteld_met_vindplaats` en `test_onleesbaar_bedrag_is_een_kritieke_bevinding`; `ROADMAP.md`, r.116 en r.121

Gesloten 04-10-2026. `signed_amount()` en `signed_amount_series()` in `auditfile/parsing.py` zetten onleesbare bedragen op nul. Hersteld op 11-09-2026 (`ROADMAP.md`): de parser telt de onleesbare waarden per blok en veld en `integrity.py` maakt er de bevinding Bedragen leesbaar van. Bewijs: de twee genoemde tests. Gemeten op 04-10-2026: de volledige testset (490 tests) is groen.

### 9. Een hergebruikt transactienummer maskeerde een onbalans
- **Status:** gesloten 04-10-2026, hersteld op 11-09-2026 met tests
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/parsing.py`, `transactie_sleutel()` r.220; `tests/test_transactiesleutel.py`, `test_hergebruikt_nummer_maskeert_de_onbalans_niet_meer` en `test_hergebruikt_nummer_wordt_apart_gemeld`; `ROADMAP.md`, r.116, r.121 en r.584

Gesloten 04-10-2026. De controles groepeerden op dagboek en transactienummer. Twee ongebalanceerde transacties met hetzelfde nummer sloten daardoor samen ten onrechte. Hersteld op 11-09-2026: `transactie_sleutel()` groepeert op het volgnummer dat de parser zelf toekent en `integrity.py`, `vat.py` en `suppletie.py` gebruiken die ene sleutel. Bewijs: de twee genoemde tests.

### 10. Controletotalen van de subadministratie werden niet getoetst
- **Status:** gesloten 04-10-2026, hersteld op 22-09-2026 met tests
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/integrity.py`; `tests/test_integrity.py`, `test_afwijkende_controletotalen_subadministratie_geven_bevindingen` en `test_ontbrekende_bedragtotalen_subadministratie_zijn_niet_mogelijk`; `ROADMAP.md`, r.116, r.143 en r.636

Gesloten 04-10-2026. `integrity.py` toetst per subadministratie het aantal regels en de debet- en credittotalen aan het bestand. Een afwijkend aantal regels is een waarschuwing en afwijkende bedragen zijn kritiek. Ontbreekt een controletotaal dan meldt de tool dat de toets niet mogelijk is. Hersteld op 22-09-2026 (`ROADMAP.md`). Bewijs: de twee genoemde tests.

### 12. Btw-anomalieën: codes ontbreken, meerdere tarieven en representatie
- **Status:** gesloten 04-10-2026, gebouwd met tests
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/vat.py`, r.735-757 (omzet en kosten zonder btw-code), r.769-786 (meerdere tarieven) en r.842-853 (representatie); `tests/test_vat.py`, r.558, r.565 en r.597; `ROADMAP.md`, r.168, r.169, r.170 en r.171

Gesloten 04-10-2026. Vier punten uit de roadmap (verkoop zonder btw-code, inkoop zonder btw-code, meerdere btw-percentages op één code en btw op representatiekosten) zijn aanwezig als signaal in `auditfile/vat.py`. De drie eerste hebben een test in `tests/test_vat.py`; de representatiesignalering is alleen in de code aangetroffen. Het signaal voor meerdere tarieven geldt bewust alleen binnen een afdrachtrubriek, want bij voorbelasting dekt één inkoopcode alle tarieven.

### 14. Aangifte-detectie op omschrijving (zonder aangiftebestand)
- **Status:** gesloten 04-10-2026, gebouwd met test
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/suppletie.py`, r.63-64; `tests/test_suppletie.py`, `test_suppletie_wordt_gevonden_met_bedrag_en_periode`; `ROADMAP.md`, r.175

Gesloten 04-10-2026. Het zoeken op omschrijvingen (suppletie, naheffing, aanvullende aangifte) en het uitlezen van het tijdvak zijn gebouwd in `suppletie.py`. `ROADMAP.md` noemt dit gereed voor de suppletie. Bewijs: de patronen in `suppletie.py` en de genoemde test. De reconstructie van de aangiftetijdlijn staat als eigen punt open.

### 16. 12-maandscontrole op vaste lasten
- **Status:** gesloten 04-10-2026, gebouwd met test
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, `PERIODIEKE_CONTROLES` r.212-220; `tests/test_controls.py`, `test_ontbrekende_perioden_worden_gemeld`; `ROADMAP.md`, r.192

Gesloten 04-10-2026. Huur, lease, abonnementen, salarissen en afschrijvingen staan in `PERIODIEKE_CONTROLES` (aangevuld met verzekeringen en rente). De prioriteringstabel in `ROADMAP.md` noemt dit gereed. Bewijs: de code en de genoemde test.

### 17. Periodecontrole: maanden zonder omzet en zonder loonkosten
- **Status:** gesloten 04-10-2026, gebouwd met test
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, r.805 en r.845; `tests/test_controls.py`, `test_perioden_zonder_omzet_worden_gemeld`; `ROADMAP.md`, r.203 en r.205

Gesloten 04-10-2026. `build_omzet_per_periode()` meldt Geen omzet in deze periode en `build_personeelskosten_per_periode()` meldt Geen loonkosten in deze periode. Bewijs: de twee regels code en de genoemde test voor de omzet. Maanden zonder inkopen staan als eigen punt open.

### 19. Ongebruikelijke boekingen: de signalen uit de roadmap
- **Status:** gesloten 04-10-2026, zeven van de acht gebouwd met tests, splitsingsrisico staat apart open
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, r.300 en r.400-444; `auditfile/integrity.py`, r.474-494; `tests/test_controls.py`, `test_weekendboeking_wordt_gesignaleerd` en r.140; `ROADMAP.md`, r.208, r.209, r.210, r.211, r.212, r.213 en r.215

Gesloten 04-10-2026. Aanwezig in de code: grote memoriaalboekingen in de laatste periode (r.408-419), negatieve omzet als omzetboeking aan de debetzijde (r.430-436), negatieve loonkosten als loonkosten aan de creditzijde (r.438-444), boekingen op zaterdag of zondag (r.400-406), ronde bedragen boven een drempel (r.421-428) en tegengestelde boekingen op vaste-lastenrekeningen (r.300). Boekingen buiten het boekjaar worden door `integrity.py` gemeld. Tests bestaan voor het weekend en de omzet aan de debetzijde. Het splitsingsrisico staat als eigen punt open.

### 23. Trendanalyse: sterke stijgingen en dalingen jaar op jaar
- **Status:** gesloten 04-10-2026, gebouwd
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/comparison.py`, r.34 en r.150-151; `auditfile/findings.py`, r.962-968; `ROADMAP.md`, r.291 en r.292

Gesloten 04-10-2026. `OPVALLEND_VERSCHIL_PCT = 25.0` en de melding Wijkt meer dan 25% af van vorig jaar in `comparison.py`; `findings.py` neemt de opvallende verschillen op als bevinding. Een aparte test op de drempel is niet aangetroffen.

### 24. AI-reviewpunten als automatisch gegenereerde aandachtspunten
- **Status:** gesloten 04-10-2026, gebouwd
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/findings.py`, `verzamel_bevindingen()` r.1068 en r.536-600; `auditfile/memorandum.py`; `ROADMAP.md`, r.296, r.297 en r.298

Gesloten 04-10-2026. De drie voorbeelden uit de roadmap komen voor als signaal (afschrijvingen die niet in alle perioden voorkomen, geen loonkosten in een periode en een sterke stijging per rekening) en `verzamel_bevindingen()` verzamelt ze in het bevindingenmodel dat het memorandum voedt. De prioriteringstabel in `ROADMAP.md` noemt dit gereed.

### 33. Brede RGS-voorvoegsels gaven debiteuren en crediteuren een te ruime selectie
- **Status:** gesloten 04-10-2026, opgelost op 03-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/controls.py`, `RELATIEREKENINGEN` r.455-458 en `build_balanspost_signalen()` r.629-639; `ROADMAP.md`, r.546

Gesloten 04-10-2026. `build_balanspost_signalen()` wees de debiteuren met `BVor` en de crediteuren met `BSch` aan, waaronder ook de omzetbelasting en de rekening-courant met de dga vielen. Opgelost op 03-09-2026 en verduidelijkt op 08-09-2026 (`ROADMAP.md`): de controle gebruikt `RELATIEREKENINGEN`, dezelfde selectie als de relatieanalyse. Bewijs: de code in `controls.py` (de selectie wordt ook door `relatiesaldi.py`, `openstaand.py` en `capability.py` gebruikt). Een aparte test op dit gedrag is niet aangetroffen.

### 34. Bedragen als float in plaats van Decimal
- **Status:** gesloten 04-10-2026, bewust niet omgezet en gemeten op 27-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `tests/test_float_precisie.py`, `test_ruime_administratie_blijft_ver_onder_de_marge` en `test_een_echte_cent_verschil_blijft_zichtbaar`; `ROADMAP.md`, r.568; `update-bram-Auditfile_app.md`, r.330

Gesloten 04-10-2026. `ROADMAP.md` sloot het punt op 27-09-2026 met een meting tegen een exacte som in hele centen: bij een miljoen regels blijft de afwijking ver onder de halve cent. `tests/test_float_precisie.py` bewaakt die ruimte en omzetten is alsnog aan de orde als die test stukgaat. `update-bram-Auditfile_app.md` noemt het nog als restpunt en is op dit punt achterhaald.

### 35. Mag een transactienummer binnen één dagboek terugkomen
- **Status:** gesloten 04-10-2026, beantwoord op 11-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `auditfile/integrity.py`, r.296-324; `tests/test_transactiesleutel.py`, `test_hergebruikt_nummer_wordt_apart_gemeld`; `ROADMAP.md`, r.591

Gesloten 04-10-2026. Antwoord: nee. De functionele specificatie schrijft voor dat het transactienummer uniek is binnen het dagboek (vindplaats en sha256 van het pakket staan in `ROADMAP.md`, beantwoord op 11-09-2026). De bevinding Transactienummer eenduidig binnen het dagboek meldt het hergebruik als waarschuwing en geen kritieke bevinding, want de cijfers kloppen. Bewijs: het besluit met datum in `ROADMAP.md`, de code in `integrity.py` en de genoemde test.

### 36. Betekenis van sbType en mutTp
- **Status:** gesloten 04-10-2026, gevonden op 11-09-2026
- **Eigenaar:** sessie
- **Vindplaats:** `ROADMAP.md`, rubriek Kleinere punten uit de review; `ROADMAP.md`, r.625

Gesloten 04-10-2026. De betekenis is gevonden op 11-09-2026 in de revisietabel van XAF 4.0 naar 3.2 (sbType: CS, CU, SU en ZZ; mutTp: I, P en Z; paginanummers staan in `ROADMAP.md`). De tool geeft de waarden onveranderd door en leidt er niets uit af. Bewijs: het gedateerde antwoord in het document zelf. Het document `docs/xaf-velden.md` is nog niet bijgewerkt, zie het volgende punt.
