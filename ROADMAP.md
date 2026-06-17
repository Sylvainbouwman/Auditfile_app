# Auditfile Analyzer — Roadmap

## Visie
Een fiscaal-inhoudelijke auditfile-analysetool die verder gaat dan bestaande software zoals Caseware, door fiscale logica toe te voegen bovenop de XAF-data. Gebouwd voor de samenstelpraktijk en belastingadvies.

---

## Categorie 1: BTW & fiscale controles

### BTW-rondrekening (in ontwikkeling)
- XAF → aangifterubriek → netto BTW
- Invoer per rubriek (1a, 1e, 2a/5b, 5b)
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

### Ouderdomsanalyse (indien open posten beschikbaar)
- Indeling: 0-30 / 31-60 / 61-90 / >90 dagen

### Debiteurenscan
- Top 10 debiteuren
- Concentratierisico
- Oude openstaande posten

### Crediteurenscan
- Achterstallige betalingen
- Leveranciersconcentratie
- Crediteuren met onlogisch debetsaldo

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

| # | Functionaliteit | Status |
|---|----------------|--------|
| 1 | BTW-rondrekening afronden | In ontwikkeling |
| 2 | 12-maandscontrole | Gepland |
| 3 | Debiteurenouderdom | Gepland |
| 4 | Crediteurenouderdom | Gepland |
| 5 | RC DGA detectie | Gepland |
| 6 | Suppletiedetectie | Gepland |
| 7 | Lease- en huurdetectie | Gepland |
| 8 | AI-reviewpunten | Gepland |
| 9 | Ratio-analyse | Gepland |
| 10 | Automatisch reviewmemorandum | Toekomst |

---

## Technische stack
- Python / Streamlit
- XAF/auditfile als invoer
- Lokaal draaiend, geen externe API vereist
- GitHub: Sylvainbouwman/Auditfile_app
