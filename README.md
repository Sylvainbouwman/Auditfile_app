# XAF Analyzer — DK Accountants

Een lokale HTML-tool voor het automatisch analyseren van XAF-auditfiles (Nederlandse standaard voor boekhoudkundige data-exports). Gebouwd voor gebruik door accountants en belastingadviseurs bij DK Accountants / Join Administraties.

---

## Wat doet de tool?

De XAF Analyzer leest een auditfile in en voert automatisch een reeks analyses uit op basis van de UC03-analysechecklist (grootboekanalyse). De output bestaat uit gestructureerde bevindingen per categorie, met een ernst-indeling (waarschuwing / attentie / controlepunt / akkoord) en een visuele statuscheck per onderdeel.

De tool is bedoeld als startpunt voor de jaarrekeningcontrole, niet als vervanging van het professionele oordeel van de accountant.

---

## Analysechecklist (UC03)

De tool loopt de volgende onderdelen automatisch af:

**BTW**
- BTW-positie rekening 1800 (te betalen / te vorderen)
- Kostenboekingen zonder BTW-code (exclusief lonen, afschrijvingen, rente)
- Representatiekosten — 80%-regel en WKR
- BTW-correctie privégebruik auto

**Balans en debiteuren**
- Debiteurensaldo — ouderdomsanalyse
- Crediteurensaldo
- Overlopende activa en passiva — afgrenzing boekjaar

**Kosten en lonen**
- Personeelskosten — aansluiting loonheffingaangiften
- Vakantiegeldvoorziening — aanwezig en volledig?
- WKR-vergoedingen — vrije ruimte en eindheffing
- 12-termijnencheck huur en lease
- CBO — omzetstromen huidig jaar (vergelijking vorig jaar: toekomstige versie)

**MVA en lease**
- Materiële vaste activa — aansluiting activastaat
- Financiële lease — rentecomponent, kortlopend deel, termijnen
- Operationele lease — toelichting buiten balans
- Afschrijvingen — aansluiting cumulatief

**Overige signalen**
- Juridische kosten — mogelijke voorziening of contingente verplichting
- Salarissen — indicatie personeelsomvang per maand
- Boetes en dwangsommen — niet aftrekbaar VPB (art. 3.14 Wet IB)
- Huurverplichtingen buiten balans

---

## Wat kun je goed met een auditfile?

Een XAF-bestand bevat grootboekkaarten, dagboeken, journaalposten, BTW-codes, debiteuren, crediteuren en boekingsomschrijvingen. Dat dekt naar schatting 70-90% van de UC03-analyse.

**Wat de auditfile niet kan:**
- Vakantiedagensaldo (vereist HR/payroll-data)
- Aansluiting loonheffing ultimo vs. laatste aangifte (vereist loonaangiften)
- WKR-analyse (alleen betrouwbaar bij consistent gelabeld rekeningschema)
- Intercompany-afstemming over meerdere administraties (vereist meerdere XAF-bestanden)
- MVA-aansluiting volledig (activastaat is een aanvullende bron)

---

## Technische achtergrond

**Waarom HTML en niet Python?**

De tool is bewust als enkelvoudig HTML-bestand gebouwd. Voordelen:

- Geen installatie nodig — openen en gebruiken
- Volledig lokaal — klantdata (de XAF) verlaat de machine nooit
- AVG-compliant by design
- Deelbaar als één bestand via Teams of e-mail
- Werkt zonder internetverbinding

Python (Streamlit) is overwogen maar heeft voor dit gebruik een hogere drempel: vereist interpreter, packages en terminal. Voor batchverwerking van meerdere klanten tegelijk is Python wél de betere keuze — dat is een toekomstige uitbreiding.

**XAF-versies**

De tool detecteert automatisch de versie van het aangeleverde bestand:

| Versie | Pakket | Kenmerken |
|---|---|---|
| XAF 4.0 | AFAS | `<ledgerAccount>`, `<amnt>` + `<amntTp>` (D/C), `<customerSupplier>` |
| XAF 3.x | Exact | `<account>`, `<debitAmount>` / `<creditAmount>`, `<customer>` / `<supplier>` |

XAF is een Nederlandse standaard van de Belastingdienst. De structuur is gestandaardiseerd, maar de implementatie verschilt per boekhoudpakket. AFAS en Exact gebruiken andere tagnamen en bedragnotaties. De tool handelt dit transparant af.

---

## Gebruik

1. Open `dk-xaf-analyzer-v4.html` in een moderne browser (Chrome, Edge, Firefox)
2. Sleep een XAF-bestand op de uploadzone of klik op "Bestand kiezen"
3. De tool verwerkt het bestand lokaal — dit duurt enkele seconden afhankelijk van de bestandsgrootte
4. Bekijk de bevindingen per tabblad of exporteer naar CSV

---

## Roadmap

- [ ] Upload vorig jaar XAF voor automatische CBO-vergelijking (afwijkingen >20%)
- [ ] Debiteurenouderdomsanalyse op basis van vervaldatum
- [ ] BTW-rondrekening verkoopboek versus ingediende aangiften
- [ ] Batchverwerking meerdere klanten (Python)
- [ ] Ondersteuning Twinfield, Visma en Unit4 XAF-varianten
- [ ] Exporteren naar Word-reviewmemo

---

## Context

Gebouwd als onderdeel van UC03 (Grootboekanalyse) binnen de AI-kopgroep van DK Accountants / Join Administraties. Aanvullende use cases: UC04 (AI-startpunt dossier), waarbij de auditfile als primaire bron voor het bedrijfsprofiel dient en de SBI-code uitsluitend als validatie.

---

## Versies

| Versie | Wijzigingen |
|---|---|
| v1 | Eerste opzet, demodata, basale analyses |
| v2 | Voortgangsbalk, async parser, UI-verbeteringen |
| v3 | Correcte AFAS XAF 4.0 parser, bedrijfsprofielkaart |
| v4 | UC03-checklist, versiedetectie AFAS/Exact, verbeterde BTW-filter (excl. lonen/afschrijvingen), MVA-tab, WKR, vakantiegeld, boetes VPB |
