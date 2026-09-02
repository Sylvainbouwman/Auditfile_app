# Auditfile Analyzer

Fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en het
belastingadvies. De tool leest twee XAF-auditfiles (vorig jaar en huidig jaar),
vergelijkt ze en voert een reeks controles uit. Alle verwerking gebeurt lokaal;
er gaan geen gegevens naar een server.

## Wat doet de tool?

**Bestandscontrole.** Voordat er cijfers worden getoond wordt het auditfile
getoetst aan de controletotalen die het zelf opgeeft: aantallen regels, totaal
debet en credit, sluit elke transactie op nul, staan alle boekingen op een
bekende rekening en binnen het boekjaar. Wijkt daar iets af, dan staat dat
bovenaan.

**Jaarvergelijking.** Per RGS-rubriek voor de hoofdlijn en per grootboekrekening
voor het detail, met nieuwe en vervallen rekeningen en filters op status,
rekeningsoort en verschilbedrag.

**Btw.** Een auditfile bevat geen aangifte, maar wel btw-codes per boekingsregel.
De tool stelt per code een aangifterubriek voor op grond van de omschrijving, het
tarief en de debet/creditzijde, en zegt erbij waarop dat voorstel berust. Die
toewijzing is aanpasbaar en wordt lokaal bewaard. Daarna volgt de optelling per
rubriek, de vergelijking met de ingediende aangiften, een rondrekening over de
btw-grootboekrekeningen en een reeks signalen op regelniveau.

**Analytische controles.** Komen vaste lasten in elke periode voor, zijn er
ongebruikelijke boekingen (weekend, ronde bedragen, grote memoriaalposten in de
laatste periode, omzet aan de verkeerde kant), staan balansposten aan de
verwachte kant, en hoe verlopen omzet en loonkosten per periode.

**Relaties.** Grootste debiteuren en crediteuren met concentratierisico, op basis
van de relatiegegevens in het auditfile.

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
komen, ook niet als voorbeeld. Eigen invoer (aangiftebedragen en de koppeling van
btw-codes aan rubrieken) wordt bewaard in `.local-testdata/`, dat door Git wordt
genegeerd. `tests/test_runtime_data_not_tracked.py` bewaakt die scheiding.

## Roadmap

Zie [`ROADMAP.md`](ROADMAP.md).
