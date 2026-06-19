# Auditfile Analyzer

Een fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en belastingadvies. De tool laadt twee XAF-auditfiles (vorig jaar + huidig jaar), vergelijkt ze, en voert automatisch een reeks fiscale controles uit op basis van de UC03-analysechecklist.

---

## Wat doet de tool?

- **Jaar-op-jaar vergelijking** per grootboekrekening — nieuwe, vervallen en bestaande rekeningen met verschilbedrag en -percentage
- **BTW-analyse** — gebruik per code, rondrekening per aangifterubriek, drilldown per transactie
- **Logische controles** — periodiciteitscheck voor huur, lease, lonen, afschrijvingen en rente
- **UC03 Checklist** — 10 automatische analyses: BTW-positie, kostenboekingen zonder BTW, crediteurensaldo, overlopende posten, personeelsomvang, omzetstromen, lease-classificatie, huurverplichtingen, juridische kosten, boetes/dwangsommen
- **Excel-export** — 13 tabbladen met volledige data, RGS-rubrieken en Dutch opmaak

---

## Gebruik

```bash
streamlit run app.py
```

Installeer dependencies in de `.venv` omgeving:

```bash
pip install -r requirements.txt
```

De app draait lokaal in de browser. Klantdata verlaat de machine niet.

---

## Technologie

- Python / Streamlit
- Pandas, OpenPyXL
- XAF (XML) parsing via standaardbibliotheek

---

## Roadmap

Zie `ROADMAP.md` voor geplande uitbreidingen, waaronder debiteurenouderdom, RC DGA-detectie, suppletiedetectie en het automatisch reviewmemorandum.
