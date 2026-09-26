# Openstaande punten

## Fiscale bronnen niet online te bevestigen (27-09-2026)

Status: gesloten 27-09-2026. Eigenaar: Sylvain Bouwman. Vindplaats: herkansing door de
agent `toolbouw:bron-controleur` op 27-09-2026, in het kader van de statuswijziging van
`auditfile-app` in `bouwman-tools/tools.json`.

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

## Kapotte documentverwijzing (27-09-2026)

Status: gesloten 27-09-2026. `auditfile/aangifte.py:24` verwees naar
`docs/xbrl-aangifte.md`, dat niet bestaat. Hersteld naar `docs/btw-bronnen.md`,
waar de tabel met definities en vindplaatsen daadwerkelijk staat.
