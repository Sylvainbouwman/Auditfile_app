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

### Ouderdomsanalyse (indien open posten beschikbaar)
- Vereist niveau 1 of 2: een gevulde XAF 3.2-subadministratie. Wacht op een
  bestand dat die levert; de capability-laag wijst het aan.
- Indeling: 0-30 / 31-60 / 61-90 / >90 dagen

### Debiteurenscan
- Grootste debiteuren naar gefactureerd bedrag (gereed)
- Concentratierisico (gereed)
- Oude openstaande posten — vereist de ouderdomsanalyse hierboven; de huidige
  analyse gaat over mutaties in het boekjaar, niet over openstaande posten

### Crediteurenscan
- Achterstallige betalingen
- Leveranciersconcentratie (gereed)
- Crediteuren met onlogisch debetsaldo — gereed voor bestanden met relatiesaldi;
  zonder die standen is er geen saldo per crediteur om op te toetsen

---

## Categorie 4: Jaarrekening-review

### Ratio-analyse
- Brutomarge
- Personeelskosten als % van omzet
- Solvabiliteit
- Liquiditeit
- Vergelijking huidig jaar vs. vorig jaar

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

### Rekening-courant DGA detectie
- Automatisch signaleren van mogelijke RC DGA op basis van rekeningnummer en omschrijving
- Saldo bepalen
- Signaal bij overschrijding drempel excessief lenen (€ 500.000 tot en met 2023, daarna lager)

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
| 5 | RC DGA detectie | Signalering gereed, drempeltoets nog niet |
| 6 | Suppletiedetectie | Gedeeltelijk: "overige mutaties" in de rondrekening |
| 7 | Lease- en huurdetectie | Gereed als periodieke controle |
| 8 | AI-reviewpunten | Bevindingenlijst en materialiteit gereed; formulering gepland |
| 9 | Ratio-analyse | Gepland |
| 10 | Automatisch reviewmemorandum | Bevindingen, materialiteit en beoordeling per bevinding gereed; het document zelf nog niet |

### Wat als eerste te doen staat

Bijgewerkt op 2 september 2026, na de volledige review en de capability-laag.

1. **XAF 4.0-relatiesaldi inlezen.** Gereed. `opBalDesc`/`opBalTp` en
   `clBalDesc`/`clBalTp` staan getekend in het model als `openstaand_begin` en
   `openstaand_eind`, alleen bij versie 4.0 gelezen; `relatiesaldi.py` sluit ze
   aan op de debiteuren- en crediteurenrekening en signaleert een onlogisch teken
   en een verloop dat niet op de boekingen aansluit. Levert voor de nu
   beschikbare bestanden niets op omdat het pakket die velden niet vult, wel voor
   bestanden die dat wel doen.
2. **XAF 3.2-subadministratie inlezen.** `obSbLine` en `sbLine` als eigen
   model, met factuurdatum, vervaldatum, afletterkenmerk en de koppeling naar de
   grootboekboeking. Dit is de enige bron in XAF met een echte vervaldatum.
3. **Open-posten- en ageing-engine.** Pas bouwen wanneer er een bestand is dat
   bewijsniveau 1 of 2 haalt; `capability.py` wijst dat aan. Een reconstructie
   uit boekingsregels op niveau 4 mag alleen met de gebruikte methode en de
   gemeten dekking in beeld, en met een betalingstermijn die de gebruiker zelf
   opgeeft.
4. **Versie-echte fixtures.** Synthetische 3.2-bestanden mét subadministratie en
   4.0-bestanden mét relatiesaldi, plus gedeeltelijk gevulde exports. Neem ook
   het officiële testbestand van de Belastingdienst
   (`XAF_4_0_Test_100425.XAF` uit het productoverzicht 4.0.3) op als
   conformance-bestand; dat is synthetisch en openbaar, maar vraagt een
   uitzondering in `.gitignore` omdat `*.XAF` wordt genegeerd.
5. **Drempeltoets excessief lenen.** De bedragen per peildatum staan al
   geverifieerd in `docs/btw-bronnen.md`; alleen de toets ontbreekt nog.
6. **Ratio-analyse** (brutomarge, personeelskosten als percentage van de omzet,
   solvabiliteit, liquiditeit), jaar op jaar.
7. **Reviewmemorandum als document.** De bouwstenen liggen er: bevindingen met
   ernst, bedrag, materialiteit en een beoordeling per bevinding. Wat rest is de
   samenvoeging en de formulering.

### Kleinere punten uit de review die nog openstaan

- **Brede RGS-voorvoegsels.** `BVor` geldt buiten de relatieanalyse nog als
  debiteuren en `BSch` als crediteuren, terwijl daar meer soorten vorderingen en
  schulden onder vallen. Hetzelfde geldt voor alle personeelskosten als loon en
  alle financiële baten en lasten als rente.
- **Bedragen als float.** De toleranties maken dat werkbaar, maar voor exact
  reproduceerbare centencontroles zijn `Decimal` of hele centen robuuster.
- **Geen XSD-validatie.** De parser leest wat er is en zet onleesbare bedragen
  stil op nul. Een validatie tegen het schema zou een kapot bestand hard
  afwijzen in plaats van half in te lezen.
- **Transactiesleutel.** De transactiebalans groepeert op dagboek en
  transactienummer. Hergebruik van hetzelfde nummer kan twee ongebalanceerde
  transacties samen laten sluiten.

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
