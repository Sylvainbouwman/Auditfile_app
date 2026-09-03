# Auditfile_app

Projectspecifieke aanvulling op de globale instructies en de `AI_kopgroep`-instructies.
Alleen wat uniek is voor deze repository staat hier.

## Doel

Fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en het
belastingadvies. Laadt twee XAF-auditfiles (vorig jaar en huidig jaar), vergelijkt ze en
voert fiscale controles uit: btw-rondrekening, logische controles op periodiciteit,
jaar-op-jaar vergelijking en Excel-export. Einddoel is een automatisch gegenereerd
reviewmemorandum met fiscale aandachtspunten.

## Documentatie

- `README.md` — gebruik en functionaliteit.
- `ROADMAP.md` — **leidend** voor nieuwe functies en prioritering. Raadpleeg dit bestand
  bij twijfel over wat als volgende op te pakken.
- `UC_Auditfile_app.md` — use case.

## Commando's

```bash
"C:\Python314\python.exe" -m streamlit run app.py
"C:\Python314\python.exe" -m pytest tests/
pip install -r requirements.txt
```

`streamlit` staat niet in PATH; roep het altijd aan via `python -m streamlit`. De
afhankelijkheden staan in de virtuele omgeving `.venv`.

## Werkwijze

- **Kleine stappen**: één wijziging tegelijk, niet meerdere losse aanpassingen bundelen
  tenzij expliciet gevraagd.
- **Eerst voorstel, dan uitvoeren**: bij niet-triviale wijzigingen eerst het voorstel
  toelichten en op bevestiging wachten voordat code wordt aangepast.

## Architectuur

Single-user Streamlit-app, volledig in het geheugen: geen database en geen backend
buiten Streamlit zelf. `app.py` bevat **uitsluitend** de interface; alle logica staat
in het pakket `auditfile/`, zodat die zonder Streamlit te testen is. Zet nieuwe
rekenlogica dus nooit in `app.py`.

| Module | Verantwoordelijkheid |
|---|---|
| `parsing.py` | XAF 3.2 en 4.0 inlezen tot een `Auditfile` |
| `model.py` | Datamodel; gegevens in een dataclass, niet in `DataFrame.attrs` |
| `integrity.py` | Controle van het bestand tegen zijn eigen controletotalen |
| `vat_rubrics.py` | Rubrieken van de aangifte omzetbelasting |
| `vat.py` | Btw-analyse, rubriekvoorstel, rondrekening, signalen |
| `controls.py` | Periodieke, analytische en fiscale controles |
| `comparison.py` | Jaar-op-jaar vergelijking |
| `excel.py` | Excel-export |
| `formatting.py` | Presentatie van tabellen in de app |
| `notatie.py` | Nederlandse notatie van losse bedragen, percentages en datums |
| `settings.py` | Lokale opslag van eigen invoer |
| `capability.py` | Wat het bestand toelaat: aanwezige blokken, dekking, bewijsniveau |
| `relatiesaldi.py` | Openstaande bedragen per relatie (XAF 4.0) en hun aansluiting |
| `openstaand.py` | Openstaande posten en ouderdom uit de subadministratie (XAF 3.2) |
| `excessief_lenen.py` | Drempeltoets Wet excessief lenen bij eigen vennootschap |
| `findings.py` | Uniform bevindingenmodel, materialiteit en de verzamelaar |
| `memorandum.py` | Het reviewmemorandum: opbouw in secties en de Markdown-uitvoer |
| `demo.py` | Synthetische auditfiles: demodata én testfixtures |

`inspect_xaf.py` is een losse CLI om een onbekende XAF-structuur te verkennen.

### Domeinbegrippen en vaste keuzes

- **XAF** — Nederlands XML-auditfileformaat, namespace-zwaar; `local_name()` strippt de
  namespaces. Zowel 3.2 als 4.0 wordt ondersteund; 4.0 levert `RGScode`, 3.2 hooguit
  `leadReference`. De herkomst staat in de kolom `RGSbron`.
- **Debet/credit** — `signed_amount()` rekent om naar een getekend bedrag: debet
  positief, `amntTp="C"` draait het teken om. Het teken van het bedrag zelf telt
  gewoon mee, dus een negatief creditbedrag is effectief debet. Dit is geverifieerd
  tegen de controletotalen `totalDebit` en `totalCredit` in de bestanden zelf; de
  andere interpretatie geeft een onbalans van miljoenen. Verander dit niet zonder
  die controle opnieuw te doen.
- **RGS boven omschrijving, per rekening** — heeft een rekening een RGS-code, dan
  beslist die code; heeft ze er geen, dan de omschrijving. De keuze valt per rekening
  en niet per controle, anders vallen in een gedeeltelijk gecodeerd schema alle
  niet-gecodeerde rekeningen buiten de selectie. De omschrijving mag een bestaande
  code nooit overrulen, want een zoekterm als "omzet" vindt ook "Omzetbelasting", en
  dat is een balansrekening. Kent een controle geen RGS-voorvoegsel, dan is de
  omschrijving de enige methode en geldt die wel voor alle rekeningen. Geef altijd een
  `rekeningtype` mee. `_selecteer()` in `controls.py` regelt dit en geeft de gebruikte
  methode terug.
- **Btw-rubrieken** — de koppeling van btw-code aan aangifterubriek is een
  interpretatie. De tool doet een voorstel mét reden en zekerheid; de keuze van de
  gebruiker gaat altijd voor. Laat de tool nooit een rubriek stilzwijgend vaststellen.
- **Bedragen blijven getallen** — nooit een bedrag als opgemaakte tekst in een
  DataFrame zetten. Opmaak gebeurt in de presentatielaag via `column_config`, anders
  is sorteren en filteren stuk.
- **Signalen, geen oordelen** — controles benoemen wat er is gezien en wat beoordeeld
  moet worden. Fiscale conclusies horen bij de gebruiker.
- **Eén bevindingenmodel** — elke controle houdt zijn eigen tabel, want daar horen
  eigen kolommen bij. Daarboven zet `findings.py` alles om naar één `Bevinding`
  (categorie, onderwerp, ernst, bedrag, rekening, methode, toelichting, pagina).
  Komt er een controle bij, voeg die dan toe aan `verzamel_bevindingen()`, anders
  ontbreekt zij in het reviewmemorandum. Ernst is kritiek, waarschuwing, signaal of
  niet mogelijk; `in orde` is geen bevinding. Materialiteit markeert een bevinding
  onder de drempel en laat haar nooit weg, en een bevinding zonder bedrag valt nooit
  onder de drempel: wat niet te wegen is, mag niet stilzwijgend onbelangrijk worden.
  De beoordeling en de notitie van de gebruiker hangen aan `Bevinding.sleutel`, een
  hash van categorie, onderwerp en rekening. Neem daar nooit het bedrag of de ernst
  in op: dan zou een gewijzigd bedrag de vastgelegde beoordeling weggooien.
- **Het memorandum bouwt op en geeft daarna uit** — `bouw_memorandum()` maakt van
  de bevindingen een `Memorandum` met secties en punten, zonder opmaak;
  `naar_markdown()` zet dat om naar tekst. Alle formulering, ordening en
  nummering hoort in de eerste laag, zodat zij als tekst te testen is en een
  tweede uitvoervorm (Word, PDF) een tweede renderer wordt in plaats van een
  tweede versie van dezelfde zinnen. Het document sorteert zelf op ernst, dan
  boven de drempel vóór eronder, dan bedrag: op bedrag alleen zou een bevinding
  zonder bedrag achter een kleine post eindigen, terwijl zij juist altijd
  meetelt. Een bevinding met ernst `niet mogelijk` staat altijd in de sectie
  over wat niet kon worden vastgesteld, ook met een beoordeling erop; een
  bevinding die de gebruiker heeft afgehandeld verhuist naar de sectie
  achteraan. Laat nooit iets weg.

- **Voorstel is geen vastlegging** — een voorstel van de tool telt mee in de berekening
  omdat er anders niets te zien is, maar heet dan `voorstel` en de uitkomst wordt als
  rekenvoorbeeld gemarkeerd. Vastleggen gebeurt alleen op een handeling van de
  gebruiker. Schrijf nooit invoer weg als bijwerking van het openen van een pagina;
  `st.tabs` voert de code van álle tabbladen uit.

- **Een wettelijke drempel toetst de tool niet af** — bij excessief lenen meet de
  tool één vennootschap op de balansdatum, terwijl de wet de belastingplichtige
  en zijn partner toetst over alle vennootschappen op 31 december. Wat daartussen
  zit (peildatum, andere vennootschappen, eigenwoningschuld met hypotheekrecht,
  eerder belast fictief regulier voordeel) staat als eigen regel in de opbouw,
  met de bron erbij: auditfile, wet, gebruiker of berekend. Bouw nooit een
  fiscale toets die de gebruikersinvoer met het bestandsgegeven op één hoop
  gooit, en laat de tool zeggen dat de toets niet kan wanneer de peildatum niet
  klopt of het bedrag voor dat jaar niet is vastgesteld.

- **Eerst vaststellen wat er is** — bijna alles in XAF is optioneel en 3.2 en 4.0
  verschillen inhoudelijk. `capability.py` stelt per bestand vast welke blokken
  aanwezig én gevuld zijn en welk bewijsniveau daaruit volgt. Bouw nooit een analyse
  die stilzwijgend aanneemt dat een veld gevuld is; laat de tool zeggen dat iets niet
  kan. De veldsemantiek per versie staat in `docs/xaf-velden.md`, inclusief de
  valkuilen: `settDate` is geen vervaldatum, `effDate` betekent niet hetzelfde in
  beide versies, en `opBalDesc` is in 3.2 een omschrijving en in 4.0 een bedrag.

- **Versiekennis blijft in de parser** — dat `opBalDesc` alleen in XAF 4.0 een
  bedrag is, wordt één keer afgevangen: `_parse_relations()` leest de openstaande
  bedragen per relatie alleen bij versie 4.0 en zet ze meteen om naar een
  getekend getal in `openstaand_begin` en `openstaand_eind`. Bij 3.2 blijven die
  kolommen leeg (NaN, niet nul). Geen enkele analysefunctie hoort daarna nog naar
  de XAF-versie te vragen; doet ze dat wel, dan staat de kennis op twee plaatsen
  en kan ze uiteenlopen.

  Bij de subadministratie van XAF 3.2 (`obSbLine` en `sbLine`) staat om dezelfde
  reden juist géén versiecontrole: die elementnamen bestaan in 4.0 niet en zijn
  dus niet dubbelzinnig, en ze worden bovendien alleen binnen `obSubledgers` en
  `subledgers` gezocht. Een 4.0-bestand levert daarmee vanzelf een lege tabel op.
  Waar een versiecontrole nodig is, is dat om een dubbelzinnige tag af te vangen
  en niet als algemene voorzorg.

- **Een verwijzing is geen rekening** — een subadministratieregel draagt geen
  `accID`. `obSbLine` verwijst met `obLineNr` naar de beginbalans, `sbLine` met
  `jrnID`, `trNr` en `trLineNr` naar de grootboekboeking, en alleen `jrnID` is
  in de XSD als sleutel vastgelegd. De parser lost de verwijzing op en zet in de
  kolom `koppeling` hoe dat is gegaan. Lost zij niet op, of wijst zij naar
  verschillende rekeningen, dan blijft de rekening leeg. Vul daar nooit een
  gok in: een post op de verkeerde rekening aansluiten is erger dan een post die
  niet aansluit.

## Data en privacy

- **De repository is publiek.** Er mag dus nooit een XAF, een klantnaam, een
  klantwaarde of een daarvan afgeleid gegeven in terechtkomen — ook niet in een
  voorbeeld, een test of een schermafdruk.
- Runtime-invoer (zoals ingevoerde aangiftebedragen) mag nooit in een gevolgd bestand
  belanden. `tests/test_runtime_data_not_tracked.py` borgt dat: het controleert elk
  schrijfpad van een dossier op genegeerd en niet-gevolgd, dat het eerder gevolgde
  `testfiles/btw_aangifte.json` niet meer wordt gevolgd, en dat een echte schrijf-/
  leesronde via `DossierOpslag` in `.local-testdata/` landt zonder Git-wijziging.
- **Genegeerd op map, niet op bestandstype.** `.local-testdata/` en `testfiles/` staan
  als geheel in `.gitignore`. Beide mappen bevatten klantbestanden of daarvan afgeleide
  invoer, en een regel per extensie laat altijd een soort door. De privacytest
  controleert dat een `.csv`, `.xlsx` of `.pdf` in `testfiles/` genegeerd is en dat er
  niets in die map wordt gevolgd.
- **Datapaden zijn verankerd aan de repo**, niet aan de werkmap: `settings.LOCAL_DATA_DIR`
  en de testmappaden in `app.py` gaan uit van de eigen bestandslocatie. Streamlit kan
  vanuit elke map worden gestart, en een relatief pad schreef klant-afgeleide invoer dan
  naar een map buiten het bereik van deze `.gitignore`. Zet nooit een nieuw datapad op
  een relatief `Path()`.
- **Eén dossier, één map.** Eigen invoer hoort bij één onderneming en één boekjaar en
  staat in `.local-testdata/dossiers/<sleutel>`, met `sleutel` een korte hash van
  onderneming plus boekjaar (`Auditfile.dossier_sleutel`). Zet nooit een klantnaam of
  nummer in een pad; zonder sleutel wordt er niets bewaard. Komt er een nieuw soort
  invoer bij, zet die dan in `DossierOpslag` en voeg het pad toe aan de privacytest.
  Draai die test vóór elke commit die aan opslag of paden raakt.

## Publicatie en gereed

Publieke repo `Sylvainbouwman/Auditfile_app`, branch `main`. Geen CI-workflow en geen
sync naar `bouwman-tools`; publiceren is pushen naar `main`.

Gereed: `python -m pytest tests/` groen, gewijzigde logica gedekt, en README of ROADMAP
bijgewerkt waar dat geldt.
