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
"C:\Python314\python.exe" -m pytest tests/          # privacyregressietest
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
buiten Streamlit zelf. Alle applicatielogica staat plat in `app.py`.

- **XML-parsing** (`parse_auditfile`, met `@st.cache_data`) — leest XAF/XML in Pandas-
  DataFrames: grootboekrekeningen, btw-codes, beginbalans, journaalposten, btw-bijlagen
  en bedrijfsgegevens.
- **Saldivergelijking** (`compare_saldi`) — jaar-op-jaar met status nieuw/vervallen/bestaand.
- **Btw-analyse** — `build_vat_usage`, `build_vat_drilldown`, `build_all_vat_drilldown`,
  `build_vat_reconciliation`, `build_vat_rubric_summary`. Gebruikte rubrieken: 1a, 1e,
  2a/5b, 5b.
- **Logische controles** (`build_logical_controls`) — datakwaliteit op periodiciteit
  (dagelijks/maandelijks/per kwartaal/jaarlijks).
- **Excel-export** (`build_excel_export`) — twaalf tabbladen via OpenPyXL, met Nederlandse
  getalnotatie (€ 1.234,56), autofilter, vastgezette koppen en RGS-kolommen.
- `inspect_xaf.py` — losse CLI om een onbekende XAF-structuur te verkennen vóórdat je
  ondersteuning toevoegt aan `app.py`.

### Domeinbegrippen

- **XAF** — Nederlands XML-auditfileformaat, namespace-zwaar; `local_name()` strippt de
  namespaces.
- **RGS** — Referentiemodel Generieke Structuur. De mapping van circa zestien rubrieken is
  hardcoded en dekt balans en resultatenrekening.
- **Debet/credit** — bedragen lopen via `typed_amount_to_signed()`; credits met type `"C"`
  worden genegeerd in teken (negatief gemaakt).

## Data en privacy

- **De repository is publiek.** Er mag dus nooit een XAF, een klantnaam, een
  klantwaarde of een daarvan afgeleid gegeven in terechtkomen — ook niet in een
  voorbeeld, een test of een schermafdruk.
- Runtime-invoer (zoals ingevoerde aangiftebedragen) mag nooit in een gevolgd bestand
  belanden. `tests/test_runtime_data_not_tracked.py` borgt dat: het controleert dat het
  wegschrijfpad door Git wordt genegeerd, dat het eerder gevolgde
  `testfiles/btw_aangifte.json` niet meer wordt gevolgd, en dat een echte schrijf-/
  leesronde via de app-helpers in `.local-testdata/` landt zonder Git-wijziging.
  Draai die test vóór elke commit die aan opslag of paden raakt.

## Publicatie en gereed

Publieke repo `Sylvainbouwman/Auditfile_app`, branch `main`. Geen CI-workflow en geen
sync naar `bouwman-tools`; publiceren is pushen naar `main`.

Gereed: `python -m pytest tests/` groen, gewijzigde logica gedekt, en README of ROADMAP
bijgewerkt waar dat geldt.
