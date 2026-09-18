# Auditfile Analyzer — Roadmap

## Besluiten en hercontrole — 9 september 2026

Sylvain heeft de volgende uitbreidingen goedgekeurd. **Beide zijn gebouwd op
15 september 2026**; zie de vaknoten bij punt 5 en punt 8 hieronder voor de
implementatie.

- **Handmatige rekeningselectie bij excessief lenen:** de gebruiker mag een
  ontbrekende DGA-rekening aan de selectie toevoegen. Toon welke rekening automatisch
  en welke handmatig is geselecteerd, met de toelichting erbij. Dit besluit geldt
  uitsluitend voor deze toets en verandert de fiscale reikwijdte niet.
- **PDF-export van het reviewmemorandum:** toevoegen naast Word en Markdown, op
  hetzelfde opgebouwde `Memorandum`. Generatie lokaal, zonder externe dienst.
  Controleer volledigheid, leesbaarheid en paginaovergangen met synthetische data.

Deze besluiten beantwoorden de keuze over handmatige rekeningselectie bij punt 5
en de gewenste uitvoervorm bij punt 8 hieronder.

## Wat de assistenten nog "super bruikbaar" zou maken — 16 september 2026

Sylvain wil de tool verder brengen dan losse controles: een lijst met
kandidaat-features, geprioriteerd op wat in de praktijk het meeste tijd
bespaart. Op volgorde van bouwen (eenvoudigste eerst):

1. **Bulkbeoordeling van bevindingen (gereed).** Op de pagina Bevindingen kan
   de gebruiker meerdere rijen aanvinken en in één keer een beoordeling en een
   notitie toepassen, in plaats van rij voor rij. De losse celbewerking blijft
   ernaast bestaan. Legt niets vast op schijf; dat blijft de knop "Beoordeling
   vastleggen" doen.
2. **Contractregister voor lease en huur (gereed als eerste stap).** Eigen
   pagina "Contracten" waar per dossier lease- en huurcontracten worden
   vastgelegd: omschrijving, jaarbedrag, ingangsdatum en einddatum
   (`auditfile/contracten.py`). De tool telt de resterende termijnen op per de
   balansdatum (jaarbedrag gedeeld door twaalf, keer het aantal resterende
   maanden) en toont het totaal; geen contante-waardeberekening en geen
   kwalificatie als operationele of financiële lease, dat blijft aan de
   gebruiker. **Wat rest (bewust een los vervolg):** koppeling met de
   bestaande periodieke controle voor huur/lease — een signaal als er kosten
   zijn geboekt maar nog geen bijbehorend contract is vastgelegd. Dat raakt
   het bevindingenmodel en is expliciet niet in deze eerste stap meegenomen.
3. **Vorig-jaar-beoordeling automatisch tonen (gereed).** Op de pagina
   Bevindingen staat een read-only kolom "Vorig jaar" die de beoordeling van
   dezelfde bevinding uit het dossier van het vorige boekjaar toont, puur ter
   referentie. Besluit van Sylvain bij het voorstel: deze koppeling moet juist
   ook werken wanneer de uitkomst van dit jaar afwijkt van vorig jaar (bijvoorbeeld
   een rekening-courant die dit jaar over de drempel gaat, terwijl dat vorig
   jaar niet zo was) — dat is precies het moment waarop de referentie het
   meeste waard is. De gewone `Bevinding.sleutel` is daarvoor niet bruikbaar,
   want die verandert mee met een statuswoord in het onderwerp (zoals "boven
   de drempel" of "verschil"). `Bevinding` heeft daarom een los veld
   `identiteit` gekregen en een eigen `identiteitssleutel`
   (`auditfile/findings.py`): waar het onderwerp de uitkomst van dit jaar
   bevat, geeft de aanroeper een vaste identiteit mee (bijvoorbeeld "Rubriek
   2a" in plaats van "Rubriek 2a: verschil"); voor de meeste bevindingen, waar
   het onderwerp al stabiel is, blijft het veld leeg en valt de koppeling
   terug op het onderwerp zelf. `voeg_vorig_jaar_toe()` koppelt op die sleutel
   aan `DossierOpslag.voor(vorig.dossier_sleutel)`, het dossier dat de
   gebruiker toch al als "Auditfile vorig jaar" laadt.
4. **Aangifte inlezen.** Gereed. De keuze die hier openstond, welk formaat de
   tool moet herkennen, is beantwoord met onderzoek: de btw-aangifte gaat sinds
   2014 verplicht als XBRL-bericht via Digipoort, en zowel AFAS Profit als Exact
   Online kan dat bestand exporteren. Er was dus geen keuze tussen pakketten
   nodig, want ze leveren alle hetzelfde gestandaardiseerde bestand; een PDF
   inlezen is daarmee van de baan.

   `auditfile/aangifte.py` leest zo'n bericht, en de nieuwe inlezer op de
   btw-pagina vult daarmee de invoervelden. Vier keuzes daarin zijn dragend.
   De koppeling gaat op de elementnaam uit de taxonomie en niet op het
   rubrieknummer, want dat nummer is presentatie en is eerder gewijzigd; bij
   3a en 3b is dat het scherpst, waar `WithinTheEC` in de naam zegt wat het
   nummer niet zegt. De mapping is overgenomen uit de taxonomie zelf, met het
   Nederlandse label en het paragraafnummer van de officiële definitie erbij,
   en staat in `docs/btw-bronnen.md`. Omdat één bericht één tijdvak beslaat en
   het boekjaar er meestal meer vraagt, kunnen alle tijdvakken tegelijk worden
   geladen; de tool telt op en meldt een gat, een overlap, een tijdvak buiten
   het boekjaar en een afwijkend btw-nummer. Een suppletie wordt apart geteld,
   want zij geeft de gecorrigeerde stand van een tijdvak waarover al aangifte
   is gedaan en gebruikt dezelfde rubriekelementen. En het ingelezen bedrag is
   een voorstel dat pas op een handeling van de gebruiker wordt vastgelegd.

   Wat rest: dit is gebouwd op de officiële taxonomie en getest met een
   synthetisch bericht uit `demo.py`, niet met een echte export uit Profit of
   Exact. Die toets staat nog open. De parser is er wel op ingericht: hij
   negeert de namespace en dus de taxonomieversie, en meldt elk veld dat hij
   niet herkent bij naam in plaats van het stil over te slaan.

Kleinere ideeën die zijn genoemd maar niet in deze volgorde zijn opgenomen:
meerjarenvergelijking (3–5 boekjaren in plaats van 2), instelbare vuistregels
per kantoor (het personeelsbedrag, de materialiteitsdrempel), een korte
samenvatting in gewone taal boven het memorandum, en een koppeling met
KVK-nummer of SBI-code voor duiding van signalen.

Bij hercontrole van punt 4 blijkt een deel van de genoemde ontbrekende tests al
aanwezig: `tests/test_openstaand.py` controleert een ontbrekende vervaldatum,
ontbrekende datums en een ambigue rekeningkoppeling. Dit is geen bewijs dat alle
gedeeltelijke exports of beide XAF-versies tegen de XSD zijn gevalideerd.

Drie technische reviewpunten hieronder waren nog in de bron teruggevonden:
`signed_amount()` en `signed_amount_series()` in `auditfile/parsing.py` zetten
onleesbare bedragen op nul; `auditfile/integrity.py` groepeert transacties op
dagboek en nummer; subadministratietotalen hebben daar nog geen eigen toets.

**Twee daarvan zijn hersteld op 11-09-2026**, met regressieproeven in
`tests/test_leesbare_bedragen.py` en `tests/test_transactiesleutel.py`.

- *Onleesbare bedragen.* De parser rekent nog steeds door, maar telt de
  onleesbare waarden per blok en veld en geeft de vindplaats mee; `integrity.py`
  maakt daar de bevinding "Bedragen leesbaar" van. Een leeg veld blijft
  gewoon nul en is geen fout. Een waarde die als 0,00 meetelt is kritiek, een
  waarde die leeg blijft een waarschuwing, omdat de tool dan verderop zelf zegt
  dat iets niet kan.
- *Transactiesleutel.* De controles groeperen op een volgnummer dat de parser
  zelf toekent. Gemeten op 11-09-2026 met een synthetisch bestand waarin één
  dagboek tweemaal transactienummer 5 bevat, de ene boeking 100,00 debet te veel
  en de andere 100,00 credit te veel: de standaardbranch meldde "Alle 1
  transacties zijn in evenwicht", ernst in orde, met ook de controletotalen en
  de debet-credit-toets in orde, dus geen enkel ander signaal. Na herstel meldt
  de controle "2 van de 2 transacties zijn niet in evenwicht", ernst kritiek,
  verschil 200,00, plus een waarschuwing over het hergebruikte nummer. Die
  waarschuwing noemt sinds 11-09-2026 ook het gebrek zelf: de functionele
  specificatie eist bij `transaction/nr` een nummer dat uniek is binnen het
  dagboek, in XAF 4.0 en in XAF 3.2 gelijkluidend. De vindplaats staat onder de
  technische aandachtspunten.

Open blijft de eigen toets op de subadministratietotalen (zie hieronder onder
de technische aandachtspunten).

## Visie
Een fiscaal-inhoudelijke auditfile-analysetool die verder gaat dan bestaande software zoals Caseware, door fiscale logica toe te voegen bovenop de XAF-data. Gebouwd voor de samenstelpraktijk en belastingadvies.

---

## Categorie 1: BTW & fiscale controles

### BTW-rondrekening (in ontwikkeling)
- XAF → aangifterubriek → netto BTW
- Invoer per rubriek (1a, 1e, 2a/5b, 5b)
- Verlegging, invoer en verwerving: verschuldigd in 2a, 4a of 4b én aftrekbaar in
  5b, met een aftrekbaar aandeel per btw-code (gereed)
- Alle rubrieken invulbaar, btw én grondslag, ook rubrieken die niet in het
  auditfile voorkomen (gereed)
- Vergelijking per boekjaar, niet per aangiftetijdvak. **Bewuste keuze**: de tool
  ondersteunt de assistent die met de jaarrekening begint en wil weten waar de
  aandachtspunten zitten, niet de aangiftecontrole per tijdvak. Een uitsplitsing
  per maand of kwartaal staat daarom niet op de rol.
- Samenvatting en verschillenanalyse
- Suppletie-indicatie bij afwijking (gereed; zie Suppletiedetectie)

### BTW-anomalieën
- Verkoop zonder BTW-code
- Inkoop zonder BTW-code
- Meerdere BTW-percentages op één code
- BTW op representatiekosten
- BTW op privé-uitgaven (signalering)

### Aangifte-detectie (zonder aangiftebestand)
- Zoeken op omschrijvingen: BTW, OB, Omzetbelasting, Belastingdienst, Suppletie,
  Q1/Q2/Q3/Q4. Gereed voor de suppletie: `suppletie.py` doet dit zoeken en leest
  het tijdvak uit de omschrijving
- Reconstructie aangiftetijdlijn op basis van boekingen

---

### Bestandenpaar en jaarovergang (gereed)
- Zelfde onderneming, zelfde valuta, aansluitende boekjaren, niet twee keer
  hetzelfde bestand, geen overlappende periodes
- Eindbalans vorig jaar tegenover beginbalans huidig jaar, met de
  resultaatbestemming als verklaringsregel

---

## Categorie 2: Logische controles samenstelpraktijk

### 12-maandscontrole
Controleer of vaste lasten elke maand voorkomen:
- Huur
- Lease
- Abonnementen
- Salarissen
- Afschrijvingen

Output per categorie: X/12 maanden ✅ ⚠️ ❌

### Periodecontrole
- Maanden zonder omzet
- Maanden zonder inkopen
- Maanden zonder loonkosten

### Ongebruikelijke boekingen
- Grote memoriaalboekingen in december
- Negatieve omzet
- Negatieve loonkosten
- Boekingen buiten het boekjaar
- Boekingen op zaterdag of zondag
- Ronde bedragen boven drempelwaarde
- Veel kleine boekingen net onder een drempelwaarde (splitsingsrisico)
- Tegengestelde boekingen op vaste-lastenrekeningen

---

## Categorie 3: Debiteuren & crediteuren

### Wat laat het bestand toe? (gereed)
Per bestand vaststellen welke gegevensblokken aanwezig én gevuld zijn, met de
dekking op de debiteuren- en crediteurenrekeningen en het bewijsniveau dat
daaruit volgt. Zie `docs/xaf-velden.md` en `auditfile/capability.py`.

Gemeten op de beschikbare bestanden: geen subadministratie in het 3.2-bestand,
geen gevulde relatiesaldi in het 4.0-bestand, en de factuurreferentie staat
vrijwel alleen op de factuurzijde. Voor die dossiers is dus geen
openstaande-postenanalyse mogelijk, en dat zegt de tool nu.

### Relatiesaldi uit XAF 4.0 (gereed)
Staan `opBalDesc`/`clBalDesc` wél gevuld, dan leest de tool de openstaande stand
per relatie en zet die tegenover het saldo van de debiteuren- en de
crediteurenrekening. Een verschil is een signaal en geen fout: op een
relatierekening staan vaker posten die niet aan een relatie hangen. Per relatie
volgt een signaal bij een onlogisch teken en bij een verloop dat niet op de
boekingen aansluit. Dit is bewijsniveau 3: een eindstand, geen factuurlijst en
geen ouderdom.

### Subadministratie uit XAF 3.2 (gereed)
De openstaande posten bij het begin van het boekjaar en hun mutaties, met de
enige echte vervaldatum die XAF kent. De tool leest ze in, lost de verwijzing
naar de grootboekrekening op en toont ze op de relatiepagina met de
controletotalen die het blok zelf opgeeft. Zie `docs/xaf-velden.md` voor de
velden en de valkuilen.

### Open posten en ouderdom (gereed)
Op niveau 1 of 2 maakt `openstaand.py` van de subadministratieregels posten:
gegroepeerd op het afletterkenmerk, anders op de factuurreferentie, anders per
regel. Afgeletterde posten vallen weg. De ouderdom loopt vanaf de vervaldatum en
anders vanaf de factuurdatum, in de klassen nog niet vervallen / 0-30 / 31-60 /
61-90 / >90, met een eigen klasse voor een post zonder datum. De opbouw splitst
op de gebruikte basis, en het totaal wordt tegenover het saldo van de
debiteuren- en de crediteurenrekening gezet.

### Debiteurenscan
- Grootste debiteuren naar gefactureerd bedrag (gereed)
- Concentratierisico (gereed)
- Oude openstaande posten — gereed op niveau 1 of 2, via de ouderdomsanalyse
  hierboven. De relatieanalyse zelf gaat nog steeds over mutaties in het
  boekjaar en niet over openstaande posten

### Crediteurenscan
- Achterstallige betalingen — gereed op niveau 1: de crediteurenposten voorbij
  hun vervaldatum staan in de ouderdomsopbouw. Op niveau 2 is er geen
  vervaldatum en is alleen de ouderdom vanaf de factuurdatum te geven
- Leveranciersconcentratie (gereed)
- Crediteuren met onlogisch debetsaldo — gereed voor bestanden met relatiesaldi;
  zonder die standen is er geen saldo per crediteur om op te toetsen

---

## Categorie 4: Jaarrekening-review

### Ratio-analyse (gereed)
`ratios.py` geeft de brutomarge, de personeelskosten als deel van de omzet, de
solvabiliteit en de current en quick ratio, voor beide boekjaren naast elkaar.
Elke uitkomst heeft een opbouw met per bouwsteen het bedrag, het aantal
rekeningen en de gebruikte methode. Het resultaat van het boekjaar wordt bij het
eigen vermogen geteld zodra uit de balanstelling blijkt dat het nog niet is
bestemd; komt de balans noch op nul noch op het resultaat uit, dan volgt er geen
solvabiliteit. Dekt de rubrieksindeling minder dan negentig procent van de
balans, dan is een balansratio niet mogelijk.

Geen normwaarden en geen branchevergelijking. Gesignaleerd worden een
verschuiving van vijf procentpunt in de marge of de personeelsquote, een daling
van tien procentpunt in de solvabiliteit, een negatief eigen vermogen en
kortlopende schulden boven de vlottende activa.

### Trendanalyse
- Jaar-op-jaar vergelijking per rekeningcategorie
- Signalering van sterke stijgingen of dalingen (>25%)

### AI-reviewpunten
Automatisch gegenereerde aandachtspunten, bijvoorbeeld:
- Afschrijvingen slechts in 8 maanden geboekt — controleer activastaat
- Geen loonkosten in december — controleer aansluiting salarisadministratie
- Sterke stijging juridische kosten (+250%) — controleer mogelijke geschillen

---

## Categorie 5: Specifiek fiscaal

### Rekening-courant DGA detectie (gereed)
- Signalering op de rekeningomschrijving, als fiscaal aandachtspunt (gereed)
- Saldo bepalen (gereed)
- Drempeltoets excessief lenen (gereed). `excessief_lenen.py` selecteert de
  rekening-courant- en leningrekeningen met aandeelhouders en bestuurders op hun
  RGS-code, zet het eindsaldo tegenover het maximumbedrag van art. 4.14a lid 2
  Wet IB 2001 en geeft de opbouw regel voor regel, met per regel de bron:
  auditfile, wet of gebruiker. Boven de drempel is een waarschuwing, binnen 10%
  eronder een signaal. De toets is bewust geen vaststelling: de wet toetst de
  belastingplichtige en zijn partner over alle vennootschappen per 31 december,
  en de eigenwoningschuld met hypotheekrecht en het eerder belaste fictieve
  reguliere voordeel staan niet in een grootboek. Die staan daarom als invoer in
  de opbouw. Bij een gebroken boekjaar en bij een peildatum waarvoor geen bedrag
  is vastgesteld zegt de tool dat de toets niet mogelijk is.

### Auto van de zaak
- Autokosten aanwezig maar geen bijtelling geboekt
- Signalering op basis van rekeningomschrijvingen

### Privé-opnamen en box 3
- Grote vorderingen op aandeelhouders
- Ongebruikelijke privé-opnamen
- Signalering mogelijke box 3-relevantie

### Suppletiedetectie (gereed)
- BTW-suppletie geboekt maar niet zichtbaar in rondrekening
- Aansluiting suppletie op verschil XAF vs. aangifte

`suppletie.py` zoekt op de btw-rekeningen naar boekingen die zichzelf een
suppletie, naheffing, aanvullende aangifte of btw-correctie noemen, leest het
tijdvak uit de omschrijving en zet het geboekte bedrag naast het verschil met
de aangifte. De uitkomst staat op de pagina Btw onder de rondrekening en in de
bevindingen.

### Lease- en huurdetectie
- Operationele lease aanwezig maar niet zichtbaar als verplichting
- Financiële lease versus operationele lease onderscheid op basis van boekingen

---

## Categorie 6: AI-laag

### Reviewmemorandum (gereed als Markdown en Word)
Automatisch gegenereerd document met de bevindingen, in de vorm die hierboven
als einddoel stond:

> Op basis van deze twee auditfiles zijn 22 aandachtspunten benoemd die
> beoordeling vragen: 1 waarschuwing en 21 signalen.
> 1. Afschrijvingen: ontbrekende perioden (€ 2.400,00, rekening 4300)
> 2. Rond bedrag (€ 28.000,00, 16 regels)
> 3. …

`memorandum.py` bouwt uit de bevindingen een document in twee lagen:
`bouw_memorandum()` maakt de secties en de punten zonder opmaak,
`naar_markdown()`, `naar_docx()` en `naar_pdf()` zetten die om naar tekst, naar
een Word-bestand en naar een PDF-bestand. De indeling is kop, uitgangspunten
met de materialiteitsdrempel en haar opbouw, samenvatting, de aandachtspunten
per ernst op volgorde van gewicht, wat niet kon worden vastgesteld, de al
beoordeelde bevindingen en de verantwoording. Elk punt heeft één doorlopend
nummer. Op de pagina Memorandum staat het stuk met een downloadknop voor elk
van de drie vormen.

De Word- en de PDF-uitvoer zijn allebei een tweede renderer op hetzelfde
`Memorandum` en geen tweede versie van dezelfde zinnen: de koppen, de
kenmerkenlijst, de genummerde samenvatting, de punten als kop en de cursieve
herkomstregel zijn opmaak, en elke formulering blijft in `bouw_memorandum()`
staan. **PDF is gereed sinds 15 september 2026**, met `reportlab`; zie punt 8
onder "Wat als eerste te doen staat" voor de opzet en het font-voorbehoud bij
het eurosymbool.

### Toekomstige mogelijkheden
- Koppeling met AFAS (GetConnector) voor automatische import jaarrekening
- Vergelijking met branchegemiddelden (SBI-code)

---

## Prioritering (top 10)

Bijgewerkt op 3 september 2026.

| # | Functionaliteit | Status |
|---|----------------|--------|
| 1 | BTW-rondrekening afronden | Gereed |
| 2 | 12-maandscontrole | Gereed |
| 3 | Debiteuren per relatie en concentratie | Gereed |
| 4 | Crediteuren per relatie en concentratie | Gereed |
| 5 | RC DGA detectie | Gereed |
| 6 | Suppletiedetectie | Gereed: geboekte suppleties met tijdvak, naast het verschil met de aangifte |
| 7 | Lease- en huurdetectie | Gereed als periodieke controle |
| 8 | AI-reviewpunten | Gereed: bevindingen met materialiteit, en de formulering in het memorandum |
| 9 | Ratio-analyse | Gereed |
| 10 | Automatisch reviewmemorandum | Gereed als Markdown, Word (.docx) en PDF, met downloadknoppen |

### Wat als eerste te doen staat

Bijgewerkt op 3 september 2026, na de suppletiedetectie. Daarmee is de top 10
hierboven volledig gereed; wat hieronder staat, is wat er per punt nog aan
verfijning open staat.

1. **XAF 4.0-relatiesaldi inlezen.** Gereed. `opBalDesc`/`opBalTp` en
   `clBalDesc`/`clBalTp` staan getekend in het model als `openstaand_begin` en
   `openstaand_eind`, alleen bij versie 4.0 gelezen; `relatiesaldi.py` sluit ze
   aan op de debiteuren- en crediteurenrekening en signaleert een onlogisch teken
   en een verloop dat niet op de boekingen aansluit. Levert voor de nu
   beschikbare bestanden niets op omdat het pakket die velden niet vult, wel voor
   bestanden die dat wel doen.
2. **XAF 3.2-subadministratie inlezen.** Gereed. `obSbLine` en `sbLine` staan
   als één tabel in `Auditfile.subadministratie`, met factuurdatum, vervaldatum,
   afletterkenmerk, relatie en factuurreferentie, en met de controletotalen per
   subadministratie in `Auditfile.subadministratie_totalen`. De rekening staat
   niet op de regel: die volgt uit `obLineNr` naar de beginbalans of uit
   `jrnID`, `trNr` en `trLineNr` naar de grootboekboeking, en de kolom
   `koppeling` legt vast hoe dat is gegaan. Een verwijzing die nergens heen
   leidt of niet eenduidig is, geeft geen rekening in plaats van een gok. Het
   bewijsniveau in `capability.py` leest deze tabel nu rechtstreeks, dus de
   losse elementtellingen voor de subadministratie zijn vervallen.
3. **Open-posten- en ageing-engine.** Gereed voor niveau 1 en 2.
   `openstaand.py` maakt posten van de subadministratieregels, bepaalt de
   ouderdom op de balansdatum en sluit het totaal aan op het grootboek; de
   uitkomsten staan op de relatiepagina en in de bevindingen. Wat rest is
   **niveau 4**: een reconstructie uit boekingsregels, alleen met de gebruikte
   methode en de gemeten dekking in beeld, en met een betalingstermijn die de
   gebruiker zelf opgeeft. Voor de nu beschikbare klantbestanden levert die
   niets op, want daar staat de factuurreferentie vrijwel alleen op de
   factuurzijde.
4. **Versie-echte fixtures.** Gedeeltelijk gereed: `vul_subadministratie()`
   levert een 3.2-bestand mét subadministratie en `vul_relatiesaldi()` een
   4.0-bestand mét relatiesaldi. Wat rest zijn gedeeltelijk gevulde exports,
   bijvoorbeeld een subadministratie zonder vervaldatum of met een verwijzing
   die niet oplost. Het gegenereerde 3.2-bestand valideert sinds 2 september
   2026 tegen de XSD; daarvoor deed het dat niet, omdat de elementvolgorde in
   `company` afweek, `opBalDate` ontbrak en `docRef` op `trLine` leeg bleef
   terwijl 3.2 dat veld verplicht stelt. Die validatie is eenmalig met de hand
   gedaan en staat niet in de tests: de XSD zit niet in de repository en het
   domein `auditfile.nl` is niet meer bereikbaar. **Te beslissen**: de XSD (en
   het officiële testbestand) in de repository opnemen en er een test op zetten. Neem ook
   het officiële testbestand van de Belastingdienst
   (`XAF_4_0_Test_100425.XAF` uit het productoverzicht 4.0.3) op als
   conformance-bestand; dat is synthetisch en openbaar, maar vraagt een
   uitzondering in `.gitignore` omdat `*.XAF` wordt genegeerd.
5. **Drempeltoets excessief lenen.** Gereed. `excessief_lenen.py` bepaalt de
   peildatum uit de einddatum van het boekjaar, haalt het maximumbedrag uit
   `MAXIMUMBEDRAGEN` (met `docs/btw-bronnen.md` als vindplaats), selecteert de
   rekeningen op de RGS-codes voor rekening-courant en leningen met
   aandeelhouders en bestuurders, en geeft de opbouw met per regel de bron. De
   uitkomst staat op de pagina Fiscale signalen, in de bevindingen en in de
   Excel-export; de eigen invoer staat in `excessief_lenen.json` in de
   dossiermap. De rekeningselectie gebruikt de codes voor aandeelhouders en
   bestuurders en laat commissarissen en "overigen" buiten de toets. Een
   rekening-courant met de dga die als "overigen" is gecodeerd valt daarmee
   buiten het bedrag; `build_afwijkende_codering()` meldt dat, en sinds
   15 september 2026 kan de gebruiker zo'n rekening op de pagina zelf aan de
   toets toevoegen. **Handmatige rekeningselectie, gebouwd op 15 september
   2026.** `build_rc_rekeningen()` neemt naast de RGS-selectie ook
   `extra_rekeningen` op: rekeningnummers die de gebruiker zelf heeft
   aangewezen, mits ze op de balans voorkomen en nog niet automatisch zijn
   geselecteerd. De kolom `herkomst` (`HERKOMST_AUTOMATISCH` of
   `HERKOMST_HANDMATIG`) maakt per rekening zichtbaar waarop de selectie
   berust, en de opbouwtabel telt het aantal automatisch en handmatig
   geselecteerde rekeningen apart. De keuze verandert de RGS-selectie zelf
   niet: zij geldt alleen voor dit dossier, staat in
   `excessief_lenen_rekeningen.json` naast de bestaande dossierinvoer, en werkt
   door in de bevindingen (`verzamel_bevindingen(..., excessief_lenen_rekeningen=...)`)
   en de Excel-export, zodat memorandum en werkboek dezelfde selectie tonen als
   de pagina Fiscale signalen. Getest in `tests/test_excessief_lenen.py`: een
   eigen herkomst per rekening, geen dubbele selectie bij een al automatisch
   gevonden rekening, een onbekend rekeningnummer dat genegeerd wordt, en de
   doorwerking naar de opbouwtekst en de bevinding.
6. **Ratio-analyse.** Gereed. `ratios.py` deelt de rekeningen in bij de eerste
   rubrieksgroep die ze herkent, meet de dekking van die indeling en geeft de
   ratio's van beide jaren met hun opbouw. De uitkomsten staan op de pagina
   Jaarvergelijking, in de bevindingen en in de Excel-export. `RGS_RUBRIEKEN` in
   `controls.py` is bij deze stap aangevuld tot alle hoofdrubrieken van niveau 2;
   daarvoor ontbraken onder meer `BFva`, `BEff`, `BVrz` en `BPro`, wat die
   rekeningen stil buiten elke rubriekstelling liet vallen. **Wat rest**: een
   ratio met een teller die op de omschrijving berust, blijft gevoelig voor het
   rekeningschema. De omzetselectie sluit nu woorden als "inkoop" en "kosten"
   vooraf uit, maar een schema zonder RGS-codes en met eigenzinnige
   omschrijvingen kan nog steeds een rekening verkeerd indelen; de kolom
   `methode` en de opbouw maken dat zichtbaar, ze voorkomen het niet. De
   percentages en verhoudingen in de signalen en de opbouw gaan sinds
   3 september 2026 via `notatie.procent()` en `notatie.getal()`, dus met een
   komma.
7. **Suppletiedetectie.** Gereed. `suppletie.py` beantwoordt de vraag die op
   de rondrekening volgt: is er voor het verschil met de aangifte al een
   suppletie geboekt? De rekeningen komen uit de btw-codetabel, aangevuld met
   balansrekeningen die op hun omschrijving een btw-rekening zijn, want een
   suppletie wordt vaak op een eigen "nog te betalen omzetbelasting" geboekt.
   Boekingen uit de facturatie vallen af, anders vangt het woord "correctie"
   de tegenboeking van elke creditnota op. Het tijdvak komt uit de
   omschrijving; een suppletie met het tijdvak van een ander jaar telt apart en
   niet mee in het restant. De uitkomst is een van acht statussen, met de
   bijbehorende bevinding in het memorandum. **Wat rest**: een suppletie die
   het pakket mét btw-code boekt, valt met de facturatie af. Dat is de prijs
   voor het uitsluiten van de creditnota's; te beslissen of een boeking in een
   memoriaaldagboek die uitsluiting mag doorbreken.
8. **Reviewmemorandum als document.** Gereed als Markdown en Word.
   `memorandum.py` bouwt de bevindingen om naar een document met kop,
   uitgangspunten, samenvatting, de aandachtspunten per ernst, een eigen sectie
   voor wat niet kon worden vastgesteld, de al beoordeelde bevindingen achteraan
   en een verantwoording met het bewijsniveau en de RGS-dekking. De opbouw
   (`bouw_memorandum()`) staat los van de uitvoer (`naar_markdown()`,
   `naar_docx()` en `naar_pdf()`), zodat een vorm erbij een renderer is en niet
   een tweede versie van dezelfde zinnen; de herkomst- en de beoordelingsregel
   staan daarom als property bij `Punt`. Het document sorteert zelf op ernst,
   dan boven de drempel vóór eronder, dan bedrag: `naar_frame()` sorteert op
   ernst en bedrag, waardoor een bevinding zonder bedrag onderaan haar
   ernstgroep zou zakken terwijl zij juist altijd meetelt.

   **PDF-uitvoer, gebouwd op 15 september 2026.** `naar_pdf()` is de derde
   renderer op dezelfde `Memorandum`, met `reportlab` (`SimpleDocTemplate`),
   lokaal en zonder externe dienst. `KeepTogether` houdt de kop van een punt en
   zijn eerste alinea samen, zodat een paginaovergang nooit tussen die twee
   invoegt. Reportlabs ingebouwde Helvetica tekent het eurosymbool goed maar
   levert er geen ToUnicode-tabel bij mee, waardoor het teken bij kopiëren of
   doorzoeken van de PDF wegvalt terwijl de rest van het bedrag blijft staan;
   nagemeten met `pypdf`, `pdfplumber`, `pymupdf` en `poppler`s `pdftotext`,
   alle vier met hetzelfde resultaat. `_pdf_escape()` vervangt het teken daarom
   door `EUR`, wat in elk PDF-programma leesbaar én doorzoekbaar blijft; de
   andere Nederlandse tekens (ë, ï, “ ”, •) heeft dit lettertype wel met een
   geldige codering. Getest in `tests/test_memorandum.py` op dezelfde manier
   als de Word-uitvoer: elk onderwerp komt terug in de PDF-tekst, de volledige
   analyse (niet alleen een handvol zelfgemaakte punten) levert een geldig
   document op, een memorandum zonder bevindingen blijft geldig, en een
   langere analyse (het aantal bevindingen in de demo) levert meerdere
   pagina's op waarvan geen enkele leeg blijft. Op de pagina Memorandum staat
   de downloadknop tussen Word en Markdown in.

### Kleinere punten uit de review die nog openstaan

- **Brede RGS-voorvoegsels.** Opgelost op 3 september 2026 waar de rubriek één
  post moest afbakenen. `build_balanspost_signalen()` wees de debiteuren met
  `BVor` en de crediteuren met `BSch` aan, en daaronder vallen ook de
  omzetbelasting, de rekening-courant met de dga en de vooruitbetaalde kosten.
  Een creditstand op die rekening-courant en een debetstand op de
  omzetbelasting zijn beide doodnormaal, en werden gemeld als een post die aan
  de verkeerde kant staat met "Debiteuren" of "Crediteuren" als categorie
  erboven. De controle gebruikt nu `RELATIEREKENINGEN`, dezelfde selectie als de
  relatieanalyse en de saldoaansluiting, dus één plaats beslist wat een
  debiteur is. Een bestand dat alleen op niveau 2 codeert (`BVor` zonder
  subcode) levert daardoor geen signaal meer: dat bestand zegt zelf niet welke
  vordering een handelsdebiteur is, en de dekking daarvan staat in
  `capability.py`. Voor de liquiditeit blijven `BVor` en `BSch` juist de goede
  rubrieken, want RGS zet de langlopende vorderingen onder `BFva`.

  **Verduidelijkt op 8 september 2026**: de toelichting bij een via RGS
  geselecteerde rekening zegt nu dat `WPer` alle personeelskosten selecteert
  en `WFbe` alle financiële baten en lasten. De controle bewijst dus niet dat
  uitsluitend loon of rente is onderzocht. Dit staat per rekening in de
  uitvoer, ook bij een gemengd gecodeerd schema; een selectie uitsluitend op
  omschrijving krijgt geen RGS-toelichting. Namen, bevindingensleutels en
  berekeningen blijven behouden, zodat bestaande beoordelingen geldig blijven.
- **Bedragen als float.** De toleranties maken dat werkbaar, maar voor exact
  reproduceerbare centencontroles zijn `Decimal` of hele centen robuuster.
- **Geen XSD-validatie.** De parser leest wat er is en wijst een bestand niet
  af. Een validatie tegen het schema zou een kapot bestand hard afwijzen in
  plaats van half in te lezen. **Niet meer stil sinds 11-09-2026**: een bedrag dat
  wel is ingevuld maar geen getal is, wordt geteld en met vindplaats gemeld in
  de bevinding "Bedragen leesbaar".
- **Transactiesleutel.** ~~De transactiebalans groepeert op dagboek en
  transactienummer.~~ **Hersteld op 11-09-2026**: `transactie_sleutel()` in
  `parsing.py` groepeert op het volgnummer dat de parser zelf toekent, en
  `integrity.py`, `vat.py` en `suppletie.py` gebruiken alle die ene sleutel.
  Het hergebruik zelf wordt apart gemeld. Bij het koppelen van de
  subadministratie was dit al afgevangen: een sleutel die naar verschillende
  rekeningen wijst, levert geen rekening op.
- **Mag een transactienummer binnen één dagboek terugkomen? Nee.**
  ~~Open vraag.~~ **Beantwoord op 11-09-2026.** De functionele specificatie
  schrijft bij `transaction/nr` voor: "Transactienummer. Moet uniek zijn binnen
  het dagboek." Vindplaats: `XMLAuditfileFinancieel_4.0_FunHie.pdf`, versie 4.0
  van 06-02-2025, element TRANSACTION, veld Transaction Number, pagina 9. Voor
  XAF 3.2 geldt dezelfde eis: het revisiedocument
  `XMLAuditfileXAF_4.0_met_revisie_naar_XAF_3.2.pdf` (versie 4.0 van 06-02-2025,
  pagina 23) legt 3.2 en 4.0 over elkaar en kleurt rood wat in 4.0 is gewijzigd
  of geschrapt; deze zin staat er zwart en is dus ongewijzigd, terwijl het in
  4.0 geschrapte `transaction/amnt` op diezelfde pagina wel rood staat
  (nagemeten met `pdfplumber`: rood is RGB 0,71/0,03/0,18, de zin zelf is
  zwart). Beide documenten komen uit `XMLAuditfile-Financieel-XAF-v-4.0.3.zip`,
  op 11-09-2026 gedownload van de openbare pagina van Belastingdienst/ODB
  `odb.belastingdienst.nl/documentatie/xml-auditfile-financieel-xaf-4-0-3/`
  (1.127.379 bytes, sha256
  `49ba39862d10277130b170002933bfdfe804b33c145a5b4f975341c7578c9f1c`). Het
  pakket en de uitgepakte inhoud staan buiten de repository en zijn niet
  gecommit.
  Het schema dwingt de eis niet af. De XSD van XAF 3.2 legt zes sleutels vast,
  op `ledgerAccount/accID`, `customerSupplier/custSupID`, `vatCode/vatID`,
  `period/periodNumber`, `journal/jrnID` en een `basicID`, en geen daarvan raakt
  `transaction/nr`; er staat op dat element ook geen `unique`. Nagemeten op
  11-09-2026 in `XmlAuditfileFinancieel3.2.xsd`; de namespace
  `http://www.auditfiles.nl/XAF/3.2` gaf toen geen antwoord, dus is de
  schematekst gelezen uit een woordelijke kopie in de publieke repository
  `BananaAccounting/Netherlands`. De XSD van 4.0 uit het pakket hierboven kent
  in het geheel geen `xsd:key`, `xsd:unique` of `xsd:keyref`. Hergebruik
  valideert dus tegen het schema en is toch in strijd met de specificatie.
  De bevinding "Transactienummer eenduidig binnen het dagboek" zegt sinds
  11-09-2026 dat het bestand op dit punt niet aan de specificatie voldoet, met
  de vindplaats erbij. De ernst blijft een waarschuwing en wordt geen kritiek:
  de controles groeperen op het eigen volgnummer, dus de cijfers kloppen; wat
  ontbreekt is de herleidbaarheid van een verwijzing naar dagboek plus
  transactienummer.
- **Betekenis van `sbType` en `mutTp`.** ~~Vaststellen wat ze betekenen vraagt
  de functionele documentatie van XAF 3.2.~~ **Gevonden op 11-09-2026** in
  `XMLAuditfileXAF_4.0_met_revisie_naar_XAF_3.2.pdf` (versie 4.0 van
  06-02-2025), dat de XAF 3.2-velden voluit weergeeft. `sbType` is Subledger
  Type met de codelijst CS = Customers / Suppliers, CU = Customers,
  SU = Suppliers en ZZ = Other (pagina's 19 en 20 voor de beginbalans, 26 en 27
  voor de transacties). `mutTp` is Mutatiesoort: "Geeft aan of het gaat om een
  factuur of ontvangst/betaling. Verplicht bij opboeken van een factuur", met
  I = Invoice, P = Payment en Z = Other (pagina's 21 en 29). De tool geeft de
  waarden nog steeds onveranderd door en leidt er niets uit af; wie er wel iets
  mee wil doen, heeft nu de omschrijving.
- **Controletotalen van de subadministratie.** Ze worden ingelezen en naast de
  eigen telling gezet, maar `integrity.py` toetst ze nog niet en er komt geen
  bevinding uit.

### Gedeelde XAF-kennis met xaf-export-tool

`xaf-export-tool` (JavaScript, lokale conversie) en deze tool bevatten beide
XAF-kennis. Besluit van 2 september 2026: **geen derde repository met contracten
en een hashvergelijkscript.** In plaats daarvan is `docs/xaf-velden.md` in deze
repository de bron van de veldsemantiek, en verwijst de andere tool daarnaar.
Beide tools houden hun eigen parser. Wordt de kennis uitgebreid, dan eerst hier
en daarna bewust in de andere tool.

Al gecorrigeerd in die tool op 2 september 2026: de kolom "Vervaldatum" die met
`effDate` werd gevuld, en de overgangsdatum die op 1 januari 2026 stond in plaats
van 2027.

---

## Technische stack
- Python / Streamlit
- XAF/auditfile als invoer
- Lokaal draaiend, geen externe API vereist
- GitHub: Sylvainbouwman/Auditfile_app
