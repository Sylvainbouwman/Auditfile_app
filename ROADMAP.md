# Auditfile Analyzer — Roadmap

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
- Suppletie-indicatie bij afwijking

### BTW-anomalieën
- Verkoop zonder BTW-code
- Inkoop zonder BTW-code
- Meerdere BTW-percentages op één code
- BTW op representatiekosten
- BTW op privé-uitgaven (signalering)

### Aangifte-detectie (zonder aangiftebestand)
- Zoeken op omschrijvingen: BTW, OB, Omzetbelasting, Belastingdienst, Suppletie, Q1/Q2/Q3/Q4
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

### Suppletiedetectie
- BTW-suppletie geboekt maar niet zichtbaar in rondrekening
- Aansluiting suppletie op verschil XAF vs. aangifte

### Lease- en huurdetectie
- Operationele lease aanwezig maar niet zichtbaar als verplichting
- Financiële lease versus operationele lease onderscheid op basis van boekingen

---

## Categorie 6: AI-laag

### Reviewmemorandum (einddoel)
Automatisch gegenereerd document met bevindingen, bijvoorbeeld:

> Op basis van de auditfile zijn 7 aandachtspunten geïdentificeerd:
> 1. Afschrijvingen ontbreken in 4 maanden
> 2. Debiteuren >90 dagen bedragen € 125.000
> 3. BTW-rondrekening sluit niet aan
> 4. Juridische kosten stijgen 300%
> 5. RC DGA overschrijdt € 500.000
> 6. Leaseverplichtingen gedetecteerd
> 7. Geen loonkosten in december

### Toekomstige mogelijkheden
- Koppeling met AFAS (GetConnector) voor automatische import jaarrekening
- Vergelijking met branchegemiddelden (SBI-code)
- Exporteren naar Word of PDF voor dossiervorming

---

## Prioritering (top 10)

Bijgewerkt op 1 september 2026.

| # | Functionaliteit | Status |
|---|----------------|--------|
| 1 | BTW-rondrekening afronden | Gereed |
| 2 | 12-maandscontrole | Gereed |
| 3 | Debiteuren per relatie en concentratie | Gereed |
| 4 | Crediteuren per relatie en concentratie | Gereed |
| 5 | RC DGA detectie | Gereed |
| 6 | Suppletiedetectie | Gedeeltelijk: "overige mutaties" in de rondrekening |
| 7 | Lease- en huurdetectie | Gereed als periodieke controle |
| 8 | AI-reviewpunten | Bevindingenlijst en materialiteit gereed; formulering gepland |
| 9 | Ratio-analyse | Gereed |
| 10 | Automatisch reviewmemorandum | Bevindingen, materialiteit en beoordeling per bevinding gereed; het document zelf nog niet |

### Wat als eerste te doen staat

Bijgewerkt op 3 september 2026, na de ratio-analyse.

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
   dossiermap. **Wat rest**: de rekeningselectie gebruikt de codes voor
   aandeelhouders en bestuurders en laat commissarissen en "overigen" buiten de
   toets. Een rekening-courant met de dga die als "overigen" is gecodeerd valt
   daarmee buiten het bedrag; `build_afwijkende_codering()` meldt dat wel, maar
   corrigeert het niet. Te beslissen of de gebruiker een rekening handmatig aan
   de toets moet kunnen toevoegen.
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
   `methode` en de opbouw maken dat zichtbaar, ze voorkomen het niet.
7. **Reviewmemorandum als document.** De bouwstenen liggen er: bevindingen met
   ernst, bedrag, materialiteit en een beoordeling per bevinding. Wat rest is de
   samenvoeging en de formulering.

### Kleinere punten uit de review die nog openstaan

- **Brede RGS-voorvoegsels.** `BVor` geldt buiten de relatieanalyse nog als
  debiteuren en `BSch` als crediteuren, terwijl daar meer soorten vorderingen en
  schulden onder vallen. Hetzelfde geldt voor alle personeelskosten als loon en
  alle financiële baten en lasten als rente. Vastgesteld op 3 september 2026 bij
  de ratio-analyse: dat is een probleem waar de rubriek één post moet afbakenen
  en juist niet waar zij een hele zijde van de balans moet afbakenen. Voor de
  current ratio zijn `BVor` en `BSch` de goede rubrieken, want RGS zet de
  langlopende vorderingen onder `BFva`. Het openstaande punt blijft dus staan
  voor de debiteuren- en crediteurenanalyse en niet voor de liquiditeit.
- **Bedragen als float.** De toleranties maken dat werkbaar, maar voor exact
  reproduceerbare centencontroles zijn `Decimal` of hele centen robuuster.
- **Geen XSD-validatie.** De parser leest wat er is en zet onleesbare bedragen
  stil op nul. Een validatie tegen het schema zou een kapot bestand hard
  afwijzen in plaats van half in te lezen.
- **Transactiesleutel.** De transactiebalans groepeert op dagboek en
  transactienummer. Hergebruik van hetzelfde nummer kan twee ongebalanceerde
  transacties samen laten sluiten. Bij het koppelen van de subadministratie is
  dit al afgevangen: een sleutel die naar verschillende rekeningen wijst, levert
  geen rekening op.
- **Betekenis van `sbType` en `mutTp`.** De XSD geeft alleen de toegestane
  waarden (CS, CU, SU, ZZ en I, P, Z) en geen omschrijving. De tool geeft ze
  onveranderd door en leidt er niets uit af. Vaststellen wat ze betekenen vraagt
  de functionele documentatie van XAF 3.2.
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
