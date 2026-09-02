"""XAF-auditfiles inlezen.

Ondersteunt XAF 3.2 en 4.0. Beide versies gebruiken een eigen namespace; die
wordt gestript, zodat de rest van de code met kale elementnamen werkt.

Tekenconventie voor bedragen
----------------------------
XAF geeft een bedrag met een aparte debet/credit-indicatie (``amntTp`` D of
C). In de praktijk schrijven pakketten ook negatieve bedragen: ongeveer een
zesde van de regels in de beschikbare auditfiles. De juiste omrekening naar
een getekend bedrag (debet positief) is::

    getekend = -amnt als amntTp == "C", anders amnt

Het teken van het bedrag telt dus gewoon mee en de creditindicatie is een
tekenwissel. Een negatief creditbedrag is daarmee effectief een debetbedrag,
wat overeenkomt met een tegenboeking binnen dezelfde zijde.

Dit is geverifieerd en geen aanname: alleen met deze regel sluit de som van
alle regels op nul en zijn debet- en creditzijde tot op de cent gelijk aan de
controletotalen ``totalDebit`` en ``totalCredit`` die het bestand zelf opgeeft.
De variant die een negatief bedrag onaangeroerd laat, geeft op diezelfde
bestanden een onbalans van miljoenen euro's.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from .model import (
    ACCOUNT_COLUMNS,
    LINE_COLUMNS,
    RELATION_COLUMNS,
    SALDO_COLUMNS,
    TRANSACTION_COLUMNS,
    VAT_CODE_COLUMNS,
    VAT_LINE_COLUMNS,
    Auditfile,
    ControlTotals,
)

MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def vingerafdruk(file_bytes: bytes) -> str:
    """Korte vingerafdruk van de inhoud van een bestand.

    Dient als sleutel voor caches en voor de dossieridentiteit: de bestandsnaam
    zegt niets over de inhoud, twee klanten kunnen hetzelfde bestand noemen.
    Blake2b in plaats van SHA-256 omdat dit bij het inlezen over het volledige
    bestand loopt en snelheid hier telt; het gaat niet om een
    beveiligingsgarantie.
    """
    return hashlib.blake2b(file_bytes, digest_size=16).hexdigest()


def local_name(tag: str) -> str:
    """Elementnaam zonder namespace."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_texts(element: ET.Element, prefix: str = "") -> dict[str, str]:
    """Tekstwaarden van de directe bladkinderen van een element."""
    row = {}
    for child in element:
        if len(child):
            continue
        row[f"{prefix}{local_name(child.tag)}"] = (child.text or "").strip()
    return row


def find_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def find_descendant(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    for candidate in element.iter():
        if local_name(candidate.tag) == name:
            return candidate
    return None


def ensure_columns(df: pd.DataFrame, columns: list[str], default="") -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = default
    return df


def signed_amount(amount, amount_type) -> float:
    """Reken een bedrag met D/C-indicatie om naar een getekend bedrag.

    Debet is positief, credit negatief; zie de moduletoelichting voor de
    onderbouwing van deze conventie.
    """
    value = pd.to_numeric(amount, errors="coerce")
    if pd.isna(value):
        return 0.0
    value = float(value)
    return -value if str(amount_type).strip().upper() == "C" else value


def signed_amount_series(amounts: pd.Series, amount_types: pd.Series) -> pd.Series:
    """Gevectoriseerde variant van :func:`signed_amount`."""
    values = pd.to_numeric(amounts, errors="coerce").fillna(0.0)
    is_credit = amount_types.astype(str).str.strip().str.upper().eq("C")
    return pd.Series(np.where(is_credit, -values, values), index=amounts.index, dtype="float64")


def _dubbele_waarden(df: pd.DataFrame, kolom: str) -> list[str]:
    """Identificaties die in het bronbestand meer dan eens voorkomen.

    Moet worden vastgesteld *voordat* de stamgegevens worden opgeschoond: na de
    deduplicatie is niet meer te zien dat er een dubbeling was, en een controle
    daarna vindt altijd nul.
    """
    if df.empty or kolom not in df.columns:
        return []
    waarden = df[kolom].astype(str).str.strip()
    return sorted({waarde for waarde in waarden[waarden.duplicated()] if waarde})


def _control_totals(element: ET.Element | None) -> ControlTotals:
    """Lees de controletotalen die het bestand zelf opgeeft."""
    if element is None:
        return ControlTotals()
    texts = child_texts(element)

    def number(key: str) -> float | None:
        value = pd.to_numeric(texts.get(key), errors="coerce")
        return None if pd.isna(value) else float(value)

    count = pd.to_numeric(texts.get("linesCount"), errors="coerce")
    return ControlTotals(
        lines_count=None if pd.isna(count) else int(count),
        total_debit=number("totalDebit"),
        total_credit=number("totalCredit"),
    )


def _xaf_version(root: ET.Element) -> str:
    """Leid de XAF-versie af uit de namespace van het wortelelement."""
    tag = root.tag
    if "}" not in tag:
        return ""
    namespace = tag.split("}", 1)[0].lstrip("{")
    for candidate in ("4.0", "3.2", "3.1", "3.0"):
        if candidate in namespace or candidate.replace(".", "_") in namespace:
            return candidate
    return namespace


def _parse_accounts(company: ET.Element | None) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    if company is not None:
        for element in company.iter():
            if local_name(element.tag) == "ledgerAccount":
                rows.append(child_texts(element))

    df = ensure_columns(pd.DataFrame(rows), ["accID", "accDesc", "accTp", "RGScode", "leadReference"])
    for column in ["accID", "accDesc", "accTp", "RGScode", "leadReference"]:
        df[column] = df[column].fillna("").astype(str).str.strip()

    # XAF 4.0 levert RGScode rechtstreeks; 3.2 kent dat element niet en heeft
    # hooguit leadReference als referentiestelsel. De herkomst wordt vastgelegd
    # zodat zichtbaar blijft hoe hard de RGS-indeling is.
    heeft_rgs = df["RGScode"] != ""
    df["RGSbron"] = np.where(heeft_rgs, "RGScode", np.where(df["leadReference"] != "", "leadReference", ""))
    df["RGScode"] = np.where(heeft_rgs, df["RGScode"], df["leadReference"])
    dubbel = _dubbele_waarden(df, "accID")
    df = df.drop_duplicates(subset=["accID"], keep="first")
    return df[ACCOUNT_COLUMNS].reset_index(drop=True), dubbel


def _parse_vat_codes(company: ET.Element | None) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    if company is not None:
        for element in company.iter():
            if local_name(element.tag) == "vatCode":
                rows.append(child_texts(element))
    df = ensure_columns(pd.DataFrame(rows), VAT_CODE_COLUMNS)
    for column in VAT_CODE_COLUMNS:
        df[column] = df[column].fillna("").astype(str).str.strip()
    dubbel = _dubbele_waarden(df, "vatID")
    schoon = df.drop_duplicates(subset=["vatID"], keep="first")
    return schoon[VAT_CODE_COLUMNS].reset_index(drop=True), dubbel


def _parse_relations(company: ET.Element | None) -> tuple[pd.DataFrame, list[str]]:
    """Debiteuren en crediteuren uit customersSuppliers."""
    rows = []
    if company is not None:
        for element in company.iter():
            if local_name(element.tag) != "customerSupplier":
                continue
            row = child_texts(element)
            address = find_child(element, "streetAddress")
            if address is not None:
                address_texts = child_texts(address)
                row["plaats"] = address_texts.get("city", "")
                row["land"] = address_texts.get("country", "")
            rows.append(row)

    columns = RELATION_COLUMNS + ["plaats", "land"]
    df = ensure_columns(pd.DataFrame(rows), columns)
    for column in columns:
        df[column] = df[column].fillna("").astype(str).str.strip()
    dubbel = _dubbele_waarden(df, "custSupID")
    schoon = df.drop_duplicates(subset=["custSupID"], keep="first")
    return schoon[columns].reset_index(drop=True), dubbel


def _parse_periods(company: ET.Element | None) -> tuple[pd.DataFrame, list[str]]:
    columns = ["periodNumber", "startDatePeriod", "endDatePeriod", "maand"]
    rows = []
    if company is not None:
        for element in company.iter():
            if local_name(element.tag) != "period":
                continue
            texts = child_texts(element)
            number = pd.to_numeric(texts.get("periodNumber"), errors="coerce")
            if pd.isna(number):
                continue
            start = texts.get("startDatePeriod", "")
            maand = str(int(number))
            if len(start) >= 7:
                try:
                    maand = MONTHS_NL[int(start[5:7]) - 1]
                except (ValueError, IndexError):
                    pass
            rows.append(
                {
                    "periodNumber": int(number),
                    "startDatePeriod": start,
                    "endDatePeriod": texts.get("endDatePeriod", ""),
                    "maand": maand,
                }
            )
    if not rows:
        return pd.DataFrame(columns=columns), []
    df = pd.DataFrame(rows)
    dubbel = _dubbele_waarden(df, "periodNumber")
    schoon = (
        df.drop_duplicates(subset=["periodNumber"])
        .sort_values("periodNumber")
        .reset_index(drop=True)
    )
    return schoon, dubbel


def _parse_opening_balance(company: ET.Element | None) -> tuple[pd.DataFrame, ControlTotals]:
    opening = find_descendant(company, "openingBalance")
    columns = ["ob_nr", "ob_accID", "ob_amnt", "ob_amntTp"]
    if opening is None:
        empty = pd.DataFrame(columns=columns + ["beginsaldo"])
        return empty, ControlTotals()

    rows = []
    for ob_line in opening:
        if local_name(ob_line.tag) != "obLine":
            continue
        rows.append({f"ob_{key}": value for key, value in child_texts(ob_line).items()})

    df = ensure_columns(pd.DataFrame(rows), columns)
    for column in ["ob_nr", "ob_accID", "ob_amntTp"]:
        df[column] = df[column].fillna("").astype(str).str.strip()
    if df.empty:
        df["beginsaldo"] = pd.Series(dtype="float64")
    else:
        df["beginsaldo"] = signed_amount_series(df["ob_amnt"], df["ob_amntTp"])
    return df, _control_totals(opening)


def _parse_lines(company: ET.Element | None) -> tuple[pd.DataFrame, ControlTotals]:
    transactions = find_descendant(company, "transactions")
    if transactions is None:
        return pd.DataFrame(), ControlTotals()

    rows = []
    for journal in transactions:
        if local_name(journal.tag) != "journal":
            continue
        journal_texts = child_texts(journal)
        journal_info = {
            "tx_jrnID": journal_texts.get("jrnID", ""),
            "tx_jrn_desc": journal_texts.get("desc", ""),
            "tx_jrn_jrnTp": journal_texts.get("jrnTp", ""),
        }

        for transaction in journal:
            if local_name(transaction.tag) != "transaction":
                continue
            transaction_info = {f"tx_{key}": value for key, value in child_texts(transaction).items()}
            transaction_info.update(journal_info)

            for tr_line in transaction:
                if local_name(tr_line.tag) != "trLine":
                    continue
                line_info = {f"line_{key}": value for key, value in child_texts(tr_line).items()}
                vat_block = find_child(tr_line, "vat")
                if vat_block is not None:
                    line_info.update({f"vat_{key}": value for key, value in child_texts(vat_block).items()})
                rows.append({**transaction_info, **line_info})

    return pd.DataFrame(rows), _control_totals(transactions)


def _build_saldo(
    accounts: pd.DataFrame,
    opening_balance: pd.DataFrame,
    lines: pd.DataFrame,
) -> pd.DataFrame:
    if opening_balance.empty:
        opening = pd.DataFrame(columns=["rekening", "beginsaldo"])
    else:
        opening = (
            opening_balance.groupby("ob_accID", dropna=False)
            .agg(beginsaldo=("beginsaldo", "sum"))
            .reset_index()
            .rename(columns={"ob_accID": "rekening"})
        )

    if lines.empty:
        mutations = pd.DataFrame(columns=["rekening", "mutaties_boekjaar", "aantal_boekingsregels"])
    else:
        mutations = (
            lines.groupby("line_accID", dropna=False)
            .agg(mutaties_boekjaar=("bedrag", "sum"), aantal_boekingsregels=("bedrag", "size"))
            .reset_index()
            .rename(columns={"line_accID": "rekening"})
        )

    saldo = opening.merge(mutations, on="rekening", how="outer")
    saldo = ensure_columns(saldo, ["rekening", "beginsaldo", "mutaties_boekjaar", "aantal_boekingsregels"], default=0)
    saldo["rekening"] = saldo["rekening"].fillna("").astype(str)

    saldo = saldo.merge(accounts, left_on="rekening", right_on="accID", how="left")
    saldo = ensure_columns(saldo, ACCOUNT_COLUMNS)
    for column in ["accDesc", "accTp", "RGScode", "RGSbron"]:
        saldo[column] = saldo[column].fillna("")
    for column in ["beginsaldo", "mutaties_boekjaar", "aantal_boekingsregels"]:
        saldo[column] = pd.to_numeric(saldo[column], errors="coerce").fillna(0)

    saldo["eindsaldo"] = saldo["beginsaldo"] + saldo["mutaties_boekjaar"]
    # Een balansrekening wordt beoordeeld op het eindsaldo, een resultaat-
    # rekening op de mutatie over het boekjaar; die heeft geen beginsaldo.
    is_balans = saldo["accTp"].astype(str).str.strip().str.upper().eq("B")
    saldo["saldo"] = np.where(is_balans, saldo["eindsaldo"], saldo["mutaties_boekjaar"])
    saldo["aantal_boekingsregels"] = saldo["aantal_boekingsregels"].astype(int)
    return saldo[SALDO_COLUMNS].sort_values("rekening").reset_index(drop=True)


def parse_auditfile(file_name: str, file_bytes: bytes) -> Auditfile:
    """Lees een XAF-bestand in tot een :class:`Auditfile`."""
    root = ET.parse(BytesIO(file_bytes)).getroot()
    header = find_descendant(root, "header")
    company = find_descendant(root, "company")

    accounts, dubbele_rekeningen = _parse_accounts(company)
    vat_codes, dubbele_btw_codes = _parse_vat_codes(company)
    relations, dubbele_relaties = _parse_relations(company)
    periods, dubbele_perioden = _parse_periods(company)
    duplicaten = {
        soort: waarden
        for soort, waarden in (
            ("rekeningen", dubbele_rekeningen),
            ("btw-codes", dubbele_btw_codes),
            ("relaties", dubbele_relaties),
            ("perioden", dubbele_perioden),
        )
        if waarden
    }
    opening_balance, opening_totals = _parse_opening_balance(company)
    lines, transaction_totals = _parse_lines(company)

    all_line_columns = TRANSACTION_COLUMNS + LINE_COLUMNS + VAT_LINE_COLUMNS
    lines = ensure_columns(lines, all_line_columns)
    lines[all_line_columns] = lines[all_line_columns].fillna("")

    if lines.empty:
        for column in ["line_amnt", "vat_vatAmnt", "vat_vatPerc", "bedrag", "btw_bedrag"]:
            lines[column] = pd.Series(dtype="float64")
        lines["periode"] = pd.Series(dtype="Int64")
        lines["datum"] = pd.Series(dtype="datetime64[ns]")
        for column in ["accDesc", "accTp", "RGScode", "RGSbron"]:
            lines[column] = pd.Series(dtype="object")
    else:
        lines["line_accID"] = lines["line_accID"].astype(str).str.strip()
        lines["line_amnt"] = pd.to_numeric(lines["line_amnt"], errors="coerce").fillna(0.0)
        lines["vat_vatAmnt"] = pd.to_numeric(lines["vat_vatAmnt"], errors="coerce")
        lines["vat_vatPerc"] = pd.to_numeric(lines["vat_vatPerc"], errors="coerce")
        lines["bedrag"] = signed_amount_series(lines["line_amnt"], lines["line_amntTp"])
        # Alleen regels met een <vat>-blok krijgen een btw-bedrag; andere regels
        # blijven leeg in plaats van nul, zodat "geen btw" en "btw van nul"
        # onderscheiden blijven.
        heeft_btw = lines["vat_vatAmnt"].notna()
        lines["btw_bedrag"] = signed_amount_series(
            lines["vat_vatAmnt"].fillna(0.0), lines["vat_vatAmntTp"]
        ).where(heeft_btw)
        lines["periode"] = pd.to_numeric(lines["tx_periodNumber"], errors="coerce").astype("Int64")
        lines["datum"] = pd.to_datetime(lines["tx_trDt"], errors="coerce", format="mixed")
        lines = lines.merge(accounts, left_on="line_accID", right_on="accID", how="left")
        lines = ensure_columns(lines, ACCOUNT_COLUMNS)
        for column in ["accDesc", "accTp", "RGScode", "RGSbron"]:
            lines[column] = lines[column].fillna("")
        if "accID" in lines.columns:
            lines = lines.drop(columns=["accID"])

    saldo = _build_saldo(accounts, opening_balance, lines)

    return Auditfile(
        bestandsnaam=file_name,
        xaf_versie=_xaf_version(root),
        vingerafdruk=vingerafdruk(file_bytes),
        company=child_texts(company) if company is not None else {},
        header=child_texts(header) if header is not None else {},
        accounts=accounts,
        vat_codes=vat_codes,
        relations=relations,
        lines=lines,
        opening_balance=opening_balance,
        saldo=saldo,
        periods=periods,
        opening_totals=opening_totals,
        transaction_totals=transaction_totals,
        duplicaten=duplicaten,
    )
