# UC_Auditfile_app — Auditfile Analyzer

| | |
|---|---|
| **Eigenaar** | Sylvain Bouwman |
| **Domein** | Samenstel / Fiscaal / Due Diligence |
| **Status** | Live |
| **Versie** | v1 — juni 2026 |

## Doel

Een fiscaal-inhoudelijke analysetool voor de samenstelpraktijk en belastingadvies: twee XAF-auditfiles (vorig jaar + huidig jaar) laden, vergelijken en automatisch een reeks fiscale controles uitvoeren op basis van de UC03-analysechecklist.

## Betrokkenen

| Rol | Toelichting |
|---|---|
| Eigenaar | Sylvain Bouwman |
| Gebruikers | Accountants en belastingadviseurs bij Join Administraties en DK Accountants |

## Trigger

Medewerker ontvangt een auditfile van een klant en wil een snelle fiscale analyse uitvoeren als onderdeel van de samenstelopdracht of due diligence.

## As-is situatie

Auditfile-analyse gebeurt handmatig in Excel: exporteren, kolommen aanmaken, vergelijken met vorig jaar, fiscale controles handmatig doorlopen. Tijdrovend en gevoelig voor menselijke fouten.

## To-be situatie

1. Medewerker laadt twee XAF-auditfiles in de tool (vorig jaar + huidig jaar)
2. Tool vergelijkt de bestanden automatisch en signaleert afwijkingen
3. Automatische fiscale controles op basis van de UC03-checklist (bijv. crediteuren/debiteuren-checks, ongebruikelijke boekingen, BTW-aansluitingen)
4. Alle verwerking gebeurt client-side — geen data gaat naar een server (privacy-compliant)
5. Exportmogelijkheid naar Excel voor verdere verwerking of dossiervorming

## Waarde

| | |
|---|---|
| **Tijdwinst** | Automatische analyse vervangt uren handmatig Excel-werk |
| **Kwaliteit** | Gestandaardiseerde checklist; minder kans op gemiste bevindingen |
| **Privacy** | Volledige client-side verwerking; klantdata verlaat de browser niet |
