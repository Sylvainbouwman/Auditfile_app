# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Over de app

De Auditfile Analyzer is een fiscaal-inhoudelijke analysetool voor de Nederlandse samenstelpraktijk en belastingadvies. De tool laadt twee XAF-auditfiles (vorig jaar + huidig jaar), vergelijkt ze, en voert fiscale controles uit: BTW-rondrekening, logische controles op periodiciteit, jaar-op-jaar vergelijking, en Excel-export. Het einddoel is een automatisch gegenereerd reviewmemorandum met fiscale aandachtspunten.

## Werkwijze

- **Kleine stappen**: één wijziging tegelijk, niet meerdere losse aanpassingen bundelen tenzij expliciet gevraagd.
- **Eerst voorstel, dan uitvoeren**: bij niet-triviale wijzigingen eerst het voorstel toelichten en wachten op bevestiging voordat code wordt aangepast.
- **ROADMAP.md is leidend**: nieuwe functies en prioritering worden bepaald door `ROADMAP.md`. Raadpleeg dit bestand bij twijfel over wat als volgende op te pakken.

## Running the app

```bash
streamlit run app.py
```

Install dependencies into the `.venv` virtual environment:

```bash
pip install -r requirements.txt
```

There are no automated tests or linting configurations.

## Architecture

This is a single-user Streamlit web app for analyzing Dutch XAF (eXtensible AuditFile) audit files. Everything is in-memory — no database, no backend server beyond Streamlit.

### Two-file workflow

The user uploads two XAF files (prior year + current year). The app parses both, compares them, and lets the user export a multi-sheet Excel workbook.

### `app.py` (main application, ~1 275 lines)

All application logic lives here in a flat structure:

- **XML parsing** (`parse_auditfile`, decorated with `@st.cache_data`) — reads XAF/XML into several Pandas DataFrames: ledger accounts, VAT codes, opening balances, journal transactions, VAT attachments, and company metadata.
- **Account comparison** (`compare_saldi`) — year-over-year variance analysis with new/deleted/existing status.
- **VAT (BTW) analysis** — usage summaries (`build_vat_usage`), transaction drilldowns (`build_vat_drilldown`, `build_all_vat_drilldown`), reconciliation (`build_vat_reconciliation`), and rubric mapping (`build_vat_rubric_summary`). Dutch BTW rubrics used: 1a, 1e, 2a/5b, 5b.
- **Logical controls** (`build_logical_controls`) — data quality checks for transaction periodicity (daily/monthly/quarterly/annual).
- **Excel export** (`build_excel_export`) — generates a formatted 12-sheet workbook using OpenPyXL with Dutch number formatting (€1.234,56), autofilter, frozen headers, and RGS classification columns.
- **Streamlit UI** (bottom of file) — file upload widgets, dashboard metrics, tabbed analysis views, ledger card viewer, and download button.

### `inspect_xaf.py` (development utility, ~212 lines)

Standalone CLI tool for introspecting unknown XAF file structures. Run it directly to identify transaction element paths in new XAF variants before adding support in `app.py`.

### Key domain concepts

- **XAF**: Dutch XML audit file format (namespace-heavy; `local_name()` strips namespaces).
- **RGS**: Referentiemodel Generieke Structuur — Dutch standard chart-of-accounts classification. Hard-coded mapping of ~16 rubrics covers balance sheet and P&L categories.
- **Debit/Credit convention**: amounts use `typed_amount_to_signed()` — credits with type `"C"` are negated.
- **BTW rubrics**: VAT codes are mapped to declaration rubrics (1a, 1e, 2a/5b) for reconciliation against filed tax returns.

### Excel sheets generated

1. Bedrijfsgegevens (company info)
2. Grootboekrekeningen (ledger accounts + RGS)
3. Mutaties (all transactions)
4. Grootboekkaarten (ledger cards)
5. Top 20 afwijkingen (top 20 variances)
6. Vergelijking (year-over-year comparison)
7. Balans (balance sheet)
8. Resultatenrekening (P&L)
9. BTW-codetabel (VAT code definitions)
10. BTW-gebruik (VAT usage summary)
11. BTW-drilldown (VAT transactions)
12. Logische controles (data quality checks)
