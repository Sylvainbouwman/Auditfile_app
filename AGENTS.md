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
| `settings.py` | Lokale opslag van eigen invoer |
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
- **Voorstel is geen vastlegging** — een voorstel van de tool telt mee in de berekening
  omdat er anders niets te zien is, maar heet dan `voorstel` en de uitkomst wordt als
  rekenvoorbeeld gemarkeerd. Vastleggen gebeurt alleen op een handeling van de
  gebruiker. Schrijf nooit invoer weg als bijwerking van het openen van een pagina;
  `st.tabs` voert de code van álle tabbladen uit.

## Data en privacy

- **De repository is publiek.** Er mag dus nooit een XAF, een klantnaam, een
  klantwaarde of een daarvan afgeleid gegeven in terechtkomen — ook niet in een
  voorbeeld, een test of een schermafdruk.
- Runtime-invoer (zoals ingevoerde aangiftebedragen) mag nooit in een gevolgd bestand
  belanden. `tests/test_runtime_data_not_tracked.py` borgt dat: het controleert elk
  schrijfpad van een dossier op genegeerd en niet-gevolgd, dat het eerder gevolgde
  `testfiles/btw_aangifte.json` niet meer wordt gevolgd, en dat een echte schrijf-/
  leesronde via `DossierOpslag` in `.local-testdata/` landt zonder Git-wijziging.
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
