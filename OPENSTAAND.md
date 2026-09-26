# Openstaande punten

## Fiscale bronnen niet online te bevestigen (27-09-2026)

Status: open. Eigenaar: Sylvain Bouwman. Vindplaats: bron-controle door de agent
`toolbouw:bron-controleur` op 27-09-2026, in het kader van de statuswijziging van
`auditfile-app` in `bouwman-tools/tools.json`.

De controleur kon de volgende bronnen niet zelf online nalezen (timeouts en
TLS-fouten bij wetten.overheid.nl en de belastingdienst-PDF); wat hij wél kon
nalezen klopte met de code. Dit blokkeert de statuswijziging naar `live` totdat
iemand deze artikelen handmatig heeft bevestigd:

- art. 4.14a lid 2 Wet IB 2001, geldende tekst 2026 (`auditfile/excessief_lenen.py`,
  bedrag € 500.000), ook de versies na 20-02-2026;
- art. 10.1 Wet IB 2001, of art. 4.14a daarvan is uitgesloten van indexatie
  (`auditfile/excessief_lenen.py:75-77`);
- art. 15 lid 1 Wet OB 1968, onderdelen b, c 1° en c 2° (`auditfile/vat_rubrics.py:122-137`,
  `AFTREKBAAR_IN_5B`);
- Toelichting btw-aangifte 2026 (Belastingdienst-PDF), rubrieknamen 1a-5g
  (`auditfile/vat_rubrics.py:51-117`);
- paragraafnummer 509383 bij de btw van rubriek 1a in de XBRL-taxonomie
  (`auditfile/aangifte.py:67`); de geautomatiseerde uitlezing gaf inconsistent
  509382 voor zowel het omzet- als het btw-element.

Blijven deze bronnen bevestigen wat er in de code staat, dan is dit punt te
sluiten zonder verdere wijziging.

## Kapotte documentverwijzing (27-09-2026)

Status: gesloten 27-09-2026. `auditfile/aangifte.py:24` verwees naar
`docs/xbrl-aangifte.md`, dat niet bestaat. Hersteld naar `docs/btw-bronnen.md`,
waar de tabel met definities en vindplaatsen daadwerkelijk staat.
