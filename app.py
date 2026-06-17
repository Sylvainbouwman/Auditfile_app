from __future__ import annotations

from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Auditfile Analyzer", layout="wide")

ACCOUNT_COLUMNS = ["accID", "accDesc", "accTp", "RGScode"]
TRANSACTION_COLUMNS = ["tx_nr", "tx_desc", "tx_periodNumber", "tx_trDt", "tx_jrnID", "tx_jrn_desc"]
LINE_COLUMNS = [
    "line_nr",
    "line_accID",
    "line_docRef",
    "line_effDate",
    "line_desc",
    "line_amnt",
    "line_amntTp",
    "line_invRef",
    "line_vatID",
]
VAT_LINE_COLUMNS = [
    "vat_vatID",
    "vat_vatPerc",
    "vat_vatAmnt",
    "vat_vatAmntTp",
]
VAT_CODE_COLUMNS = [
    "vatID",
    "vatDesc",
    "vatToPayAccID",
    "vatToClaimAccID",
]
COMPANY_INFO_COLUMNS = ["Onderdeel", "Waarde"]
OPENING_BALANCE_COLUMNS = [
    "ob_nr",
    "ob_accID",
    "ob_amnt",
    "ob_amntTp",
]
CARD_COLUMNS = [
    "tx_trDt",
    "tx_periodNumber",
    "tx_jrnID",
    "tx_nr",
    "tx_desc",
    "line_nr",
    "line_docRef",
    "line_effDate",
    "line_desc",
    "line_amnt",
    "line_amntTp",
    "bedrag",
]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_texts(element: ET.Element, prefix: str = "") -> dict[str, str]:
    row = {}
    for child in list(element):
        if len(child):
            continue
        row[f"{prefix}{local_name(child.tag)}"] = (child.text or "").strip()
    return row


def ensure_columns(df: pd.DataFrame, columns: list[str], default="") -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = default
    return df


def amount_to_signed(row: pd.Series) -> float:
    return typed_amount_to_signed(row.get("line_amnt"), row.get("line_amntTp", ""))


def typed_amount_to_signed(amount_value, amount_type_value) -> float:
    amount = pd.to_numeric(amount_value, errors="coerce")
    if pd.isna(amount):
        amount = 0.0

    amount_type = str(amount_type_value).strip().upper()
    if amount_type == "C":
        return -float(amount)
    return float(amount)


def typed_amount_to_signed_preserve_negative(amount_value, amount_type_value) -> float:
    amount = pd.to_numeric(amount_value, errors="coerce")
    if pd.isna(amount):
        amount = 0.0
    amount = float(amount)
    if amount < 0:
        return amount

    amount_type = str(amount_type_value).strip().upper()
    if amount_type == "C":
        return -amount
    return amount


def empty_saldo() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rekening",
            "accDesc",
            "accTp",
            "RGScode",
            "beginsaldo",
            "mutaties_boekjaar",
            "eindsaldo",
            "saldo",
            "aantal_boekingsregels",
        ]
    )


def build_company_info(root: ET.Element) -> pd.DataFrame:
    header = next((element for element in root.iter() if local_name(element.tag) == "header"), None)
    company = next((element for element in root.iter() if local_name(element.tag) == "company"), None)
    header_info = child_texts(header) if header is not None else {}
    company_info = child_texts(company) if company is not None else {}

    rows = [
        ("Bedrijfsnaam", company_info.get("companyName", "")),
        ("KvK-nummer", company_info.get("Commercenr", "")),
        ("BTW-nummer", company_info.get("taxRegIdent", "")),
        ("BTW-land", company_info.get("taxRegistrationCountry", "")),
        ("Boekjaar", header_info.get("fiscalYear", "")),
        ("Startdatum", header_info.get("startDate", "")),
        ("Einddatum", header_info.get("endDate", "")),
        ("Valuta", header_info.get("curCode", "")),
        ("Aangemaakt op", header_info.get("dateCreated", "")),
        ("Software", header_info.get("softwareDesc", "")),
        ("Softwareversie", header_info.get("softwareVersion", "")),
        ("RGS-versie", header_info.get("RGSVersion", "")),
    ]
    return pd.DataFrame(rows, columns=COMPANY_INFO_COLUMNS)


@st.cache_data(show_spinner=False)
def parse_auditfile(file_name: str, file_bytes: bytes) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    del file_name
    root = ET.parse(BytesIO(file_bytes)).getroot()
    company_info = build_company_info(root)

    accounts = []
    for element in root.iter():
        if local_name(element.tag) == "ledgerAccount":
            accounts.append(child_texts(element))

    df_accounts = pd.DataFrame(accounts)
    df_accounts = ensure_columns(df_accounts, ACCOUNT_COLUMNS)
    df_accounts[ACCOUNT_COLUMNS] = df_accounts[ACCOUNT_COLUMNS].fillna("").astype(str)
    df_accounts = df_accounts.drop_duplicates(subset=["accID"], keep="first")

    vat_codes = []
    for element in root.iter():
        if local_name(element.tag) == "vatCode":
            vat_codes.append(child_texts(element))

    df_vat_codes = pd.DataFrame(vat_codes)
    df_vat_codes = ensure_columns(df_vat_codes, VAT_CODE_COLUMNS)
    df_vat_codes[VAT_CODE_COLUMNS] = df_vat_codes[VAT_CODE_COLUMNS].fillna("").astype(str)
    df_vat_codes = df_vat_codes.drop_duplicates(subset=["vatID"], keep="first")

    opening_balance_lines = []
    for opening_balance in root.iter():
        if local_name(opening_balance.tag) != "openingBalance":
            continue

        for ob_line in list(opening_balance):
            if local_name(ob_line.tag) != "obLine":
                continue

            opening_balance_lines.append(
                {
                    f"ob_{key}": value
                    for key, value in child_texts(ob_line).items()
                }
            )

    df_opening_balance = pd.DataFrame(opening_balance_lines)
    df_opening_balance = ensure_columns(df_opening_balance, OPENING_BALANCE_COLUMNS)
    if not df_opening_balance.empty:
        df_opening_balance[OPENING_BALANCE_COLUMNS] = df_opening_balance[OPENING_BALANCE_COLUMNS].fillna("")
        df_opening_balance["ob_accID"] = df_opening_balance["ob_accID"].astype(str)
        df_opening_balance["ob_amnt"] = pd.to_numeric(df_opening_balance["ob_amnt"], errors="coerce").fillna(0.0)
        df_opening_balance["beginsaldo"] = df_opening_balance.apply(
            lambda row: typed_amount_to_signed(row.get("ob_amnt"), row.get("ob_amntTp", "")),
            axis=1,
        )

        opening_saldo = (
            df_opening_balance.groupby("ob_accID", dropna=False)
            .agg(beginsaldo=("beginsaldo", "sum"))
            .reset_index()
            .rename(columns={"ob_accID": "rekening"})
        )
    else:
        opening_saldo = pd.DataFrame(columns=["rekening", "beginsaldo"])

    lines = []
    current_journal = {}
    for journal in root.iter():
        if local_name(journal.tag) != "journal":
            continue

        current_journal = {
            f"tx_jrn_{key}": value
            for key, value in child_texts(journal).items()
            if key in {"jrnID", "desc", "jrnTp"}
        }

        for transaction in list(journal):
            if local_name(transaction.tag) != "transaction":
                continue

            transaction_info = {
                f"tx_{key}": value
                for key, value in child_texts(transaction).items()
            }
            transaction_info.update(current_journal)

            for tr_line in list(transaction):
                if local_name(tr_line.tag) != "trLine":
                    continue

                line_info = {
                    f"line_{key}": value
                    for key, value in child_texts(tr_line).items()
                }
                for child in list(tr_line):
                    if local_name(child.tag) == "vat":
                        line_info.update(
                            {
                                f"vat_{key}": value
                                for key, value in child_texts(child).items()
                            }
                        )
                lines.append({**transaction_info, **line_info})

    df_lines = pd.DataFrame(lines)
    df_lines = ensure_columns(df_lines, TRANSACTION_COLUMNS + LINE_COLUMNS + VAT_LINE_COLUMNS)
    df_lines.attrs["vat_codes"] = df_vat_codes
    df_lines.attrs["company_info"] = company_info

    if df_lines.empty:
        mutation_saldo = pd.DataFrame(columns=["rekening", "mutaties_boekjaar", "aantal_boekingsregels"])
    else:
        df_lines[TRANSACTION_COLUMNS + LINE_COLUMNS + VAT_LINE_COLUMNS] = df_lines[
            TRANSACTION_COLUMNS + LINE_COLUMNS + VAT_LINE_COLUMNS
        ].fillna("")
        df_lines["line_accID"] = df_lines["line_accID"].astype(str)
        df_lines["line_amnt"] = pd.to_numeric(df_lines["line_amnt"], errors="coerce").fillna(0.0)
        df_lines["vat_vatAmnt"] = pd.to_numeric(df_lines["vat_vatAmnt"], errors="coerce").fillna(0.0)
        df_lines["vat_vatPerc"] = pd.to_numeric(df_lines["vat_vatPerc"], errors="coerce")
        df_lines["bedrag"] = df_lines.apply(amount_to_signed, axis=1)

        df_lines = df_lines.merge(
            df_accounts[ACCOUNT_COLUMNS],
            left_on="line_accID",
            right_on="accID",
            how="left",
        )
        df_lines = ensure_columns(df_lines, ACCOUNT_COLUMNS)
        df_lines[["accDesc", "accTp", "RGScode"]] = df_lines[["accDesc", "accTp", "RGScode"]].fillna("")
        df_lines.attrs["vat_codes"] = df_vat_codes
        df_lines.attrs["company_info"] = company_info

        mutation_saldo = (
            df_lines.groupby("line_accID", dropna=False)
            .agg(
                mutaties_boekjaar=("bedrag", "sum"),
                aantal_boekingsregels=("bedrag", "count"),
            )
            .reset_index()
            .rename(columns={"line_accID": "rekening"})
        )

    saldo = opening_saldo.merge(mutation_saldo, on="rekening", how="outer")
    saldo = ensure_columns(saldo, ["rekening", "beginsaldo", "mutaties_boekjaar", "aantal_boekingsregels"], default=0)
    saldo["rekening"] = saldo["rekening"].fillna("").astype(str)

    saldo = saldo.merge(
        df_accounts[ACCOUNT_COLUMNS],
        left_on="rekening",
        right_on="accID",
        how="left",
    )
    saldo = ensure_columns(saldo, ACCOUNT_COLUMNS)
    saldo[["accDesc", "accTp", "RGScode"]] = saldo[["accDesc", "accTp", "RGScode"]].fillna("")

    for column in ["beginsaldo", "mutaties_boekjaar", "aantal_boekingsregels"]:
        saldo[column] = pd.to_numeric(saldo[column], errors="coerce").fillna(0)

    saldo["eindsaldo"] = saldo["beginsaldo"] + saldo["mutaties_boekjaar"]
    saldo["saldo"] = saldo.apply(
        lambda row: row["eindsaldo"]
        if str(row.get("accTp", "")).strip().upper() == "B"
        else row["mutaties_boekjaar"],
        axis=1,
    )
    saldo = saldo[
        [
            "rekening",
            "accDesc",
            "accTp",
            "RGScode",
            "beginsaldo",
            "mutaties_boekjaar",
            "eindsaldo",
            "saldo",
            "aantal_boekingsregels",
        ]
    ].sort_values("rekening")

    return df_accounts, df_lines, saldo


def first_non_empty(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        value = row.get(column, "")
        if pd.notna(value) and str(value) != "":
            return str(value)
    return ""


def compare_saldi(saldo_vorig: pd.DataFrame, saldo_huidig: pd.DataFrame) -> pd.DataFrame:
    saldo_vorig = ensure_columns(saldo_vorig.copy(), list(empty_saldo().columns))
    saldo_huidig = ensure_columns(saldo_huidig.copy(), list(empty_saldo().columns))

    saldo_vorig["aanwezig_vorig"] = True
    saldo_huidig["aanwezig_huidig"] = True

    vorig = saldo_vorig.rename(
        columns={
            "saldo": "saldo_vorig_jaar",
            "beginsaldo": "beginsaldo_vorig_jaar",
            "mutaties_boekjaar": "mutaties_vorig_jaar",
            "eindsaldo": "eindsaldo_vorig_jaar",
            "aantal_boekingsregels": "regels_vorig_jaar",
            "accDesc": "accDesc_vorig",
            "accTp": "accTp_vorig",
            "RGScode": "RGScode_vorig",
        }
    )
    huidig = saldo_huidig.rename(
        columns={
            "saldo": "saldo_huidig_jaar",
            "beginsaldo": "beginsaldo_huidig_jaar",
            "mutaties_boekjaar": "mutaties_huidig_jaar",
            "eindsaldo": "eindsaldo_huidig_jaar",
            "aantal_boekingsregels": "regels_huidig_jaar",
            "accDesc": "accDesc_huidig",
            "accTp": "accTp_huidig",
            "RGScode": "RGScode_huidig",
        }
    )

    comparison = vorig.merge(huidig, on="rekening", how="outer")
    comparison = ensure_columns(
        comparison,
        [
            "saldo_vorig_jaar",
            "saldo_huidig_jaar",
            "beginsaldo_vorig_jaar",
            "beginsaldo_huidig_jaar",
            "mutaties_vorig_jaar",
            "mutaties_huidig_jaar",
            "eindsaldo_vorig_jaar",
            "eindsaldo_huidig_jaar",
            "regels_vorig_jaar",
            "regels_huidig_jaar",
            "aanwezig_vorig",
            "aanwezig_huidig",
        ],
        default=0,
    )

    comparison["aanwezig_vorig"] = comparison["aanwezig_vorig"].fillna(False).astype(bool)
    comparison["aanwezig_huidig"] = comparison["aanwezig_huidig"].fillna(False).astype(bool)

    numeric_columns = [
        "saldo_vorig_jaar",
        "saldo_huidig_jaar",
        "beginsaldo_vorig_jaar",
        "beginsaldo_huidig_jaar",
        "mutaties_vorig_jaar",
        "mutaties_huidig_jaar",
        "eindsaldo_vorig_jaar",
        "eindsaldo_huidig_jaar",
        "regels_vorig_jaar",
        "regels_huidig_jaar",
    ]
    for column in numeric_columns:
        comparison[column] = pd.to_numeric(comparison[column], errors="coerce").fillna(0)

    comparison["accDesc"] = comparison.apply(
        lambda row: first_non_empty(row, ["accDesc_huidig", "accDesc_vorig"]),
        axis=1,
    )
    comparison["accTp"] = comparison.apply(
        lambda row: first_non_empty(row, ["accTp_huidig", "accTp_vorig"]),
        axis=1,
    )
    comparison["RGScode"] = comparison.apply(
        lambda row: first_non_empty(row, ["RGScode_huidig", "RGScode_vorig"]),
        axis=1,
    )

    comparison["verschil_bedrag"] = comparison["saldo_huidig_jaar"] - comparison["saldo_vorig_jaar"]
    comparison["verschil_abs"] = comparison["verschil_bedrag"].abs()
    comparison["verschil_pct"] = comparison.apply(
        lambda row: None
        if row["saldo_vorig_jaar"] == 0
        else row["verschil_bedrag"] / abs(row["saldo_vorig_jaar"]) * 100,
        axis=1,
    )
    comparison["status"] = comparison.apply(
        lambda row: "nieuw"
        if row["aanwezig_huidig"] and not row["aanwezig_vorig"]
        else "vervallen"
        if row["aanwezig_vorig"] and not row["aanwezig_huidig"]
        else "bestaand",
        axis=1,
    )

    return comparison.sort_values("verschil_abs", ascending=False)


def get_vat_codes(lines: pd.DataFrame) -> pd.DataFrame:
    vat_codes = lines.attrs.get("vat_codes")
    if isinstance(vat_codes, pd.DataFrame):
        return export_dataframe(vat_codes, VAT_CODE_COLUMNS)
    return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})


def get_company_info(lines: pd.DataFrame) -> pd.DataFrame:
    company_info = lines.attrs.get("company_info")
    if isinstance(company_info, pd.DataFrame):
        return export_dataframe(company_info, COMPANY_INFO_COLUMNS)
    return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})


def build_vat_usage(lines: pd.DataFrame) -> pd.DataFrame:
    lines = ensure_columns(lines.copy(), LINE_COLUMNS + VAT_LINE_COLUMNS)
    vat_codes = lines.attrs.get("vat_codes")
    if not isinstance(vat_codes, pd.DataFrame):
        vat_codes = pd.DataFrame(columns=VAT_CODE_COLUMNS)
    vat_codes = ensure_columns(vat_codes.copy(), VAT_CODE_COLUMNS)

    vat_lines = lines[lines["vat_vatID"].astype(str).str.strip() != ""].copy()
    if vat_lines.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    vat_lines["grondslagbedrag"] = vat_lines.apply(
        lambda row: typed_amount_to_signed_preserve_negative(row.get("line_amnt"), row.get("line_amntTp", "")),
        axis=1,
    )
    vat_lines["btw_bedrag"] = vat_lines.apply(
        lambda row: typed_amount_to_signed_preserve_negative(row.get("vat_vatAmnt"), row.get("vat_vatAmntTp", "")),
        axis=1,
    )
    vat_lines["vat_vatPerc"] = pd.to_numeric(vat_lines["vat_vatPerc"], errors="coerce")

    usage = (
        vat_lines.groupby("vat_vatID", dropna=False)
        .agg(
            aantal_transactieregels=("vat_vatID", "count"),
            totaal_grondslagbedrag=("grondslagbedrag", "sum"),
            totaal_btw_bedrag=("btw_bedrag", "sum"),
            gebruikte_percentages=(
                "vat_vatPerc",
                lambda values: ", ".join(
                    sorted(
                        {
                            f"{float(value):g}%"
                            for value in values.dropna()
                        }
                    )
                ),
            ),
        )
        .reset_index()
        .rename(columns={"vat_vatID": "vatID"})
    )

    usage = usage.merge(vat_codes[["vatID", "vatDesc"]], on="vatID", how="left")
    usage = ensure_columns(
        usage,
        [
            "vatID",
            "vatDesc",
            "aantal_transactieregels",
            "totaal_grondslagbedrag",
            "totaal_btw_bedrag",
            "gebruikte_percentages",
        ],
    )
    return usage[
        [
            "vatID",
            "vatDesc",
            "aantal_transactieregels",
            "totaal_grondslagbedrag",
            "totaal_btw_bedrag",
            "gebruikte_percentages",
        ]
    ].sort_values("vatID")


def build_vat_drilldown(lines: pd.DataFrame, vat_id: str) -> pd.DataFrame:
    columns = TRANSACTION_COLUMNS + LINE_COLUMNS + VAT_LINE_COLUMNS + ["accDesc"]
    lines = ensure_columns(lines.copy(), columns)
    selected_lines = lines[lines["vat_vatID"].astype(str) == str(vat_id)].copy()
    if selected_lines.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    selected_lines["datum"] = selected_lines.apply(
        lambda row: first_non_empty(row, ["tx_trDt", "line_effDate"]),
        axis=1,
    )
    selected_lines["documentreferentie"] = selected_lines.apply(
        lambda row: first_non_empty(row, ["line_docRef", "line_invRef"]),
        axis=1,
    )
    selected_lines["bedrag"] = selected_lines.apply(
        lambda row: typed_amount_to_signed_preserve_negative(row.get("line_amnt"), row.get("line_amntTp", "")),
        axis=1,
    )
    selected_lines["BTW-bedrag"] = selected_lines.apply(
        lambda row: typed_amount_to_signed_preserve_negative(row.get("vat_vatAmnt"), row.get("vat_vatAmntTp", "")),
        axis=1,
    )
    selected_lines["BTW-percentage"] = pd.to_numeric(selected_lines["vat_vatPerc"], errors="coerce")
    if "accID" in selected_lines.columns:
        selected_lines = selected_lines.drop(columns=["accID"])

    selected_lines = selected_lines.rename(
        columns={
            "tx_periodNumber": "periode",
            "tx_jrn_desc": "journaal",
            "line_accID": "accID",
            "accDesc": "rekeningomschrijving",
            "line_desc": "omschrijving transactieregel",
            "line_amntTp": "bedragstype",
        }
    )
    selected_lines = selected_lines.sort_values("datum", na_position="last")
    return selected_lines[
        [
            "datum",
            "periode",
            "journaal",
            "accID",
            "rekeningomschrijving",
            "omschrijving transactieregel",
            "bedrag",
            "bedragstype",
            "BTW-percentage",
            "BTW-bedrag",
            "documentreferentie",
        ]
    ]


def build_all_vat_drilldown(lines: pd.DataFrame) -> pd.DataFrame:
    usage = build_vat_usage(lines)
    if "vatID" not in usage.columns or usage.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    drilldowns = []
    for vat_id in usage["vatID"].dropna().astype(str):
        drilldown = build_vat_drilldown(lines, vat_id)
        if "Melding" in drilldown.columns:
            continue
        drilldown.insert(0, "vatID", vat_id)
        drilldown.attrs = {}
        drilldowns.append(drilldown)

    if not drilldowns:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    vat_codes = lines.attrs.get("vat_codes")
    if not isinstance(vat_codes, pd.DataFrame):
        vat_codes = pd.DataFrame(columns=VAT_CODE_COLUMNS)
    vat_codes = ensure_columns(vat_codes.copy(), VAT_CODE_COLUMNS)

    result = pd.concat(drilldowns, ignore_index=True)
    result = result.merge(vat_codes[["vatID", "vatDesc"]], on="vatID", how="left")
    result = result[
        [
            "vatID",
            "vatDesc",
            "datum",
            "periode",
            "journaal",
            "accID",
            "rekeningomschrijving",
            "omschrijving transactieregel",
            "bedrag",
            "bedragstype",
            "BTW-percentage",
            "BTW-bedrag",
            "documentreferentie",
        ]
    ]
    return result.sort_values(["vatID", "datum"], na_position="last")
def build_vat_reconciliation(lines: pd.DataFrame, declared_vat: dict | None = None) -> pd.DataFrame:
    usage = build_vat_usage(lines)

    if "vatID" not in usage.columns or usage.empty:
        return pd.DataFrame({"Melding": ["Geen BTW-gegevens beschikbaar"]})

    declared_vat = declared_vat or {}

    result = usage.copy()
    def determine_rubric(vat_desc: str) -> str:
        vat_desc = str(vat_desc).lower()

        if "1a" in vat_desc:
            return "1a"
        elif "1b" in vat_desc:
            return "1b"
        elif "1e" in vat_desc:
            return "1e"
        elif "2a" in vat_desc or "verlegd" in vat_desc:
            return "2a/5b"
        elif "5b" in vat_desc or "voorbelasting" in vat_desc:
            return "5b"
        else:
            return "Onbekend"

    result["rubriek"] = result["vatDesc"].apply(determine_rubric)
    result["btw_volgens_xaf"] = pd.to_numeric(result["totaal_btw_bedrag"], errors="coerce").fillna(0)

    result["btw_volgens_aangifte"] = result["vatID"].astype(str).map(
        lambda vat_id: float(declared_vat.get(vat_id, 0) or 0)
    )

    result["verschil"] = result["btw_volgens_xaf"] - result["btw_volgens_aangifte"]

    result["status"] = result["verschil"].apply(
        lambda x: "✅ Sluit aan" if abs(x) < 1 else "⚠️ Verschil"
    )

    return result[
        [
            "vatID",
            "vatDesc",
            "rubriek",
            "aantal_transactieregels",
            "totaal_grondslagbedrag",
            "btw_volgens_xaf",
            "btw_volgens_aangifte",
            "verschil",
            "status",
            "gebruikte_percentages",
        ]
    ].sort_values("vatID")

def build_vat_rubric_summary(reconciliation: pd.DataFrame) -> pd.DataFrame:
    if reconciliation.empty or "rubriek" not in reconciliation.columns:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    summary = (
        reconciliation.groupby("rubriek", dropna=False)
        .agg(
            btw_volgens_xaf=("btw_volgens_xaf", "sum"),
            btw_volgens_aangifte=("btw_volgens_aangifte", "sum"),
            verschil=("verschil", "sum"),
        )
        .reset_index()
    )

    summary["btw_volgens_xaf"] = summary["btw_volgens_xaf"].abs().round(0)
    summary["btw_volgens_aangifte"] = summary["btw_volgens_aangifte"].abs().round(0)
    summary["verschil"] = summary["verschil"].abs().round(0)

    return summary.sort_values("rubriek")
def build_vat_account_analysis(lines: pd.DataFrame) -> pd.DataFrame:
    lines = ensure_columns(lines.copy(), ["line_accID", "accDesc", "line_desc", "bedrag"])

    btw_mask = (
        lines["accDesc"].astype(str).str.contains(
            "btw|omzetbelasting|belastingdienst",
            case=False,
            na=False,
        )
    )

    result = lines[btw_mask].copy()

    if result.empty:
        return pd.DataFrame({"Melding": ["Geen BTW-rekeningen gevonden"]})

    summary = (
        result.groupby(["line_accID", "accDesc"], dropna=False)
        .size()
        .reset_index(name="Aantal boekingen")
    )

    return summary.sort_values("Aantal boekingen", ascending=False)

def build_logical_controls(lines: pd.DataFrame) -> pd.DataFrame:
    columns = ["line_accID", "accDesc", "tx_periodNumber", "line_amnt", "line_amntTp", "bedrag"]
    lines = ensure_columns(lines.copy(), columns)
    if lines.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    lines["periode_nummer"] = pd.to_numeric(lines["tx_periodNumber"], errors="coerce")
    lines = lines[lines["periode_nummer"].notna()].copy()
    if lines.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    lines["periode_nummer"] = lines["periode_nummer"].astype(int)
    lines["bedrag"] = lines.apply(
        lambda row: typed_amount_to_signed(row.get("line_amnt"), row.get("line_amntTp", "")),
        axis=1,
    )
    max_period = int(lines["periode_nummer"].max()) if not lines.empty else 12
    expected_period_count = min(12, max(max_period, 1))
    expected_periods = set(range(1, expected_period_count + 1))

    controls = [
        ("Huur", ["huur", "rent"], True),
        ("Lonen / salarissen", ["loon", "salaris", "salarissen", "wages", "payroll"], True),
        ("Afschrijvingen", ["afschrijving", "afschrijvingen", "depreciation"], True),
        ("Verzekeringen", ["verzekering", "verzekeringen", "insurance"], False),
    ]

    rows = []
    for control_name, search_terms, expects_12_periods in controls:
        pattern = "|".join(search_terms)
        control_lines = lines[lines["accDesc"].astype(str).str.contains(pattern, case=False, na=False, regex=True)]
        if control_lines.empty:
            continue

        for (account, description), account_lines in control_lines.groupby(["line_accID", "accDesc"], dropna=False):
            period_totals = (
                account_lines.groupby("periode_nummer", dropna=False)["bedrag"]
                .sum()
                .sort_index()
            )
            periods_with_mutations = [int(period) for period in period_totals.index]
            period_count = len(periods_with_mutations)
            total_amount = float(period_totals.sum())
            average_amount = total_amount / period_count if period_count else 0.0
            max_deviation = (
                float((period_totals - average_amount).abs().max())
                if period_count and pd.notna(average_amount)
                else 0.0
            )
            strong_deviation = (
                period_count > 1
                and abs(average_amount) > 0.005
                and (period_totals - average_amount).abs().max() > abs(average_amount) * 0.5
            )

            check_missing_periods = expects_12_periods or period_count >= 10
            missing_periods = sorted(expected_periods - set(periods_with_mutations)) if check_missing_periods else []

            if missing_periods:
                conclusion = "Let op: ontbrekende perioden"
            elif strong_deviation:
                conclusion = "Let op: sterke afwijking"
            elif not expects_12_periods and period_count < 10:
                conclusion = "Handmatig beoordelen"
            else:
                conclusion = "OK"

            rows.append(
                {
                    "controle": control_name,
                    "rekeningnummer": str(account),
                    "rekeningomschrijving": str(description),
                    "aantal_perioden_met_mutaties": period_count,
                    "perioden_met_mutaties": ", ".join(str(period) for period in periods_with_mutations),
                    "ontbrekende_perioden": ", ".join(str(period) for period in missing_periods),
                    "totaalbedrag": total_amount,
                    "gemiddeld_bedrag_per_periode": float(average_amount),
                    "grootste_afwijking_tov_gemiddelde": max_deviation,
                    "conclusie": conclusion,
                }
            )

    if not rows:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    return pd.DataFrame(rows).sort_values(["controle", "rekeningnummer"])


def format_money(value: float) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        number = 0.0
    formatted = f"{float(number):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_euro_whole(value) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return ""
    formatted = f"{float(number):,.0f}"
    return "€ " + formatted.replace(",", ".")


def format_date_nl(value) -> str:
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.strftime("%d-%m-%Y")


def export_dataframe(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Maak een veilige kopie voor Excel; lege tabbladen krijgen een melding."""
    export_df = df.copy()
    if columns:
        export_df = ensure_columns(export_df, columns)
        export_df = export_df[columns]

    if export_df.empty:
        return pd.DataFrame({"Melding": ["Geen gegevens beschikbaar"]})

    return export_df


RGS_RUBRIEKEN = {
    "BEiv": "Eigen vermogen",
    "BIva": "Immateriele vaste activa",
    "BLas": "Langlopende schulden",
    "BLim": "Liquide middelen",
    "BMva": "Materiele vaste activa",
    "BSch": "Kortlopende schulden",
    "BVor": "Vorderingen",
    "BVrd": "Voorraden",
    "WAfs": "Afschrijvingen",
    "WBed": "Bedrijfskosten",
    "WBel": "Belastingen resultaat",
    "WFbe": "Financiele baten en lasten",
    "WKpr": "Kostprijs van de omzet",
    "WOmz": "Netto-omzet",
    "WPer": "Personeelskosten",
}


def enrich_rgs_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg RGS-rubriek en omschrijving toe voor het Excel-tabblad Grootboekrekeningen."""
    export_df = ensure_columns(df.copy(), ["RGScode"])

    def rgs_rubriek(code) -> str:
        code_text = str(code or "").strip()
        if not code_text:
            return ""
        if code_text.startswith("Resultaat"):
            return "Resultaat"
        return RGS_RUBRIEKEN.get(code_text[:4], "")

    export_df["RGS rubriek"] = export_df["RGScode"].apply(rgs_rubriek)
    export_df["RGS omschrijving"] = export_df["RGS rubriek"]
    return export_df


def worksheet_amount_columns(df: pd.DataFrame) -> list[int]:
    amount_words = ("saldo", "bedrag", "mutaties", "amnt", "afwijking")
    columns = []
    for index, column in enumerate(df.columns, start=1):
        column_name = str(column).casefold()
        if "pct" in column_name or "percentage" in column_name:
            continue
        if any(word in column_name for word in amount_words):
            columns.append(index)
    return columns


def prepare_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Schrijf numerieke tekst als getal weg, met behoud van zichtbare voorloopnullen."""
    export_df = df.copy()
    numeric_column_formats = {}

    for column in export_df.columns:
        if pd.api.types.is_numeric_dtype(export_df[column]):
            continue

        values = export_df[column].dropna().astype(str).str.strip()
        values = values[values != ""]
        if values.empty:
            continue

        normalized_values = values.str.replace(",", ".", regex=False)
        if not normalized_values.str.fullmatch(r"-?\d+(\.\d+)?").all():
            continue

        export_df[column] = pd.to_numeric(
            export_df[column].astype(str).str.strip().str.replace(",", ".", regex=False),
            errors="coerce",
        )

        if normalized_values.str.fullmatch(r"\d+").all():
            width = int(values.str.len().max())
            if width > 1 and values.str.startswith("0").any():
                numeric_column_formats[str(column)] = "0" * width

    export_df.attrs["numeric_column_formats"] = numeric_column_formats
    return export_df


def format_excel_sheet(worksheet, df: pd.DataFrame) -> None:
    """Zet filters, bovenste rij vast, bedragen en kolombreedtes netjes."""
    from openpyxl.utils import get_column_letter

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    amount_columns = set(worksheet_amount_columns(df))
    numeric_column_formats = df.attrs.get("numeric_column_formats", {})
    for column_number, column_name in enumerate(df.columns, start=1):
        excel_column = get_column_letter(column_number)
        max_length = len(str(column_name))

        for value in df[column_name].head(1000):
            if pd.notna(value):
                max_length = max(max_length, len(str(value)))

        worksheet.column_dimensions[excel_column].width = min(max(max_length + 2, 12), 60)

        if column_number in amount_columns:
            for cell in worksheet[excel_column][1:]:
                cell.number_format = "#,##0.00;[Red]-#,##0.00"

        if str(column_name) in numeric_column_formats:
            for cell in worksheet[excel_column][1:]:
                cell.number_format = numeric_column_formats[str(column_name)]


def build_excel_export(
    current_saldo: pd.DataFrame,
    current_lines: pd.DataFrame,
    comparison: pd.DataFrame,
    comparison_columns: list[str],
) -> bytes:
    """Bouw het Excelbestand met meerdere tabbladen voor de downloadknop."""
    output = BytesIO()

    saldo_columns = [
        "rekening",
        "accDesc",
        "accTp",
        "RGScode",
        "beginsaldo",
        "mutaties_boekjaar",
        "eindsaldo",
        "saldo",
        "aantal_boekingsregels",
    ]
    grootboek_columns = [
        "rekening",
        "accDesc",
        "accTp",
        "RGScode",
        "RGS rubriek",
        "RGS omschrijving",
        "beginsaldo",
        "mutaties_boekjaar",
        "eindsaldo",
        "saldo",
        "aantal_boekingsregels",
    ]
    mutation_columns = [
        "tx_trDt",
        "tx_periodNumber",
        "tx_jrnID",
        "tx_jrn_desc",
        "tx_nr",
        "tx_desc",
        "line_nr",
        "line_accID",
        "accDesc",
        "accTp",
        "RGScode",
        "line_docRef",
        "line_effDate",
        "line_desc",
        "line_amnt",
        "line_amntTp",
        "bedrag",
    ]

    current_saldo_safe = ensure_columns(current_saldo.copy(), saldo_columns)
    current_saldo_export = enrich_rgs_columns(current_saldo_safe)
    current_lines_safe = ensure_columns(current_lines.copy(), mutation_columns)
    comparison_by_account = comparison.sort_values("rekening")
    comparison_safe = export_dataframe(comparison_by_account, comparison_columns)

    balance_2025 = current_saldo_safe[
        current_saldo_safe["accTp"].astype(str).str.upper().eq("B")
    ].copy().sort_values("rekening")
    profit_loss_2025 = current_saldo_safe[
        current_saldo_safe["accTp"].astype(str).str.upper().eq("P")
    ].copy().sort_values("rekening")
    ledger_cards = current_lines_safe.sort_values(
        ["line_accID", "tx_trDt", "tx_nr", "line_nr"],
        na_position="last",
    )

    sheets = {
        "Bedrijfsgegevens": get_company_info(current_lines),
        "Grootboekrekeningen": export_dataframe(current_saldo_export.sort_values("rekening"), grootboek_columns),
        "Mutaties": export_dataframe(current_lines_safe.sort_values(["line_accID", "tx_trDt", "tx_nr", "line_nr"], na_position="last"), mutation_columns),
        "Grootboekkaarten": export_dataframe(ledger_cards, mutation_columns),
        "Top 20 afwijkingen": export_dataframe(comparison.head(20), comparison_columns),
        "Vergelijking 2024-2025": comparison_safe,
        "Balans 2025": export_dataframe(balance_2025, saldo_columns),
        "Resultatenrekening 2025": export_dataframe(profit_loss_2025, saldo_columns),
        "BTW-codetabel": get_vat_codes(current_lines),
        "BTW-gebruik": build_vat_usage(current_lines),
        "BTW-drilldown": build_all_vat_drilldown(current_lines),
        "Logische controles": build_logical_controls(current_lines),
    }

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df = prepare_numeric_columns(sheet_df)
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
            format_excel_sheet(writer.sheets[sheet_name], sheet_df)

    return output.getvalue()


def main() -> None:
    st.title("Auditfile Analyzer")
    st.write("Vergelijk twee XAF/XML auditfiles op grootboekrekening en bekijk de grootboekkaart.")

    test_mode = st.sidebar.checkbox("Testmodus (bestanden uit testfiles/)", value=False)

    if test_mode:
        prev_path = Path("testfiles/vorig_jaar.xaf")
        curr_path = Path("testfiles/huidig_jaar.xaf")
        if not prev_path.exists() or not curr_path.exists():
            st.warning(
                "Testmodus actief maar bestanden niet gevonden. "
                "Zet je testbestanden in de map `testfiles/` met de namen "
                "`vorig_jaar.xaf` en `huidig_jaar.xaf`."
            )
            st.stop()
        previous_name = prev_path.name
        previous_bytes = prev_path.read_bytes()
        current_name = curr_path.name
        current_bytes = curr_path.read_bytes()
    else:
        left, right = st.columns(2)
        with left:
            previous_file = st.file_uploader("Upload auditfile vorig jaar", type=["xaf", "xml"], key="previous")
        with right:
            current_file = st.file_uploader("Upload auditfile huidig jaar", type=["xaf", "xml"], key="current")

        if not previous_file or not current_file:
            st.info("Upload beide auditfiles om de vergelijking te maken.")
            st.stop()
        previous_name = previous_file.name
        previous_bytes = previous_file.getvalue()
        current_name = current_file.name
        current_bytes = current_file.getvalue()

    try:
        _, previous_lines, previous_saldo = parse_auditfile(previous_name, previous_bytes)
        _, current_lines, current_saldo = parse_auditfile(current_name, current_bytes)
        comparison = compare_saldi(previous_saldo, current_saldo)
    except Exception as exc:
        st.error("Fout bij het verwerken van de auditfiles.")
        st.exception(exc)
        st.stop()

    st.success("Beide auditfiles zijn ingelezen.")

    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Regels vorig jaar", f"{len(previous_lines):,}")
    metric_b.metric("Regels huidig jaar", f"{len(current_lines):,}")
    metric_c.metric("Rekeningen vorig jaar", f"{len(previous_saldo):,}")
    metric_d.metric("Rekeningen huidig jaar", f"{len(current_saldo):,}")

    display_columns = [
        "rekening",
        "accDesc",
        "accTp",
        "RGScode",
        "beginsaldo_vorig_jaar",
        "mutaties_vorig_jaar",
        "eindsaldo_vorig_jaar",
        "beginsaldo_huidig_jaar",
        "mutaties_huidig_jaar",
        "eindsaldo_huidig_jaar",
        "saldo_vorig_jaar",
        "saldo_huidig_jaar",
        "verschil_bedrag",
        "verschil_pct",
        "status",
        "regels_vorig_jaar",
        "regels_huidig_jaar",
    ]

    tab_vergelijking, tab_grootboek, tab_btw, tab_controles, tab_export = st.tabs(
        ["Vergelijking", "Grootboekkaarten", "BTW", "Logische controles", "Export"]
    )

    _vergelijking_bedrag_cols = [
        "beginsaldo_vorig_jaar", "mutaties_vorig_jaar", "eindsaldo_vorig_jaar",
        "beginsaldo_huidig_jaar", "mutaties_huidig_jaar", "eindsaldo_huidig_jaar",
        "saldo_vorig_jaar", "saldo_huidig_jaar", "verschil_bedrag",
    ]

    with tab_vergelijking:
        st.subheader("Top 20 grootste afwijkingen")
        _top20 = comparison.head(20)[display_columns].copy()
        for _col in _vergelijking_bedrag_cols:
            if _col in _top20.columns:
                _top20[_col] = _top20[_col].apply(format_euro_whole)
        st.dataframe(_top20, use_container_width=True, hide_index=True)

        st.subheader("Vergelijking per grootboekrekening")
        status_filter = st.multiselect(
            "Status",
            options=["bestaand", "nieuw", "vervallen"],
            default=["bestaand", "nieuw", "vervallen"],
        )
        filtered_comparison = comparison[comparison["status"].isin(status_filter)].sort_values("rekening")
        _vergelijking = filtered_comparison[display_columns].copy()
        for _col in _vergelijking_bedrag_cols:
            if _col in _vergelijking.columns:
                _vergelijking[_col] = _vergelijking[_col].apply(format_euro_whole)
        st.dataframe(_vergelijking, use_container_width=True, hide_index=True, height=520)

    with tab_grootboek:
        current_saldo = ensure_columns(current_saldo, ["rekening", "accDesc", "saldo"])
        account_options = (
            current_saldo.assign(
                label=lambda df: df.apply(
                    lambda row: f"{row['rekening']} - {row['accDesc']} ({format_money(row['saldo'])})",
                    axis=1,
                )
            )
            .sort_values("rekening")
        )

        if account_options.empty:
            st.info("Geen grootboekregels gevonden in het huidige jaar.")
        else:
            selected_label = st.selectbox("Kies een grootboekrekening", account_options["label"].tolist())
            selected_account = selected_label.split(" - ", 1)[0]

            card = current_lines[current_lines["line_accID"].astype(str) == selected_account].copy()
            if card.empty:
                st.info("Geen boekingsregels gevonden voor deze rekening.")
            else:
                card = ensure_columns(card, CARD_COLUMNS)
                card = card.sort_values(["tx_trDt", "tx_nr", "line_nr"], na_position="last")
                st.write(
                    f"Rekening {selected_account} | "
                    f"Aantal boekingsregels: {len(card):,} | "
                    f"Saldo huidig jaar: € {format_money(card['bedrag'].sum())}"
                )
                _card = card[CARD_COLUMNS].copy()
                _card["tx_trDt"] = _card["tx_trDt"].apply(format_date_nl)
                _card["line_effDate"] = _card["line_effDate"].apply(format_date_nl)
                _card["bedrag"] = _card["bedrag"].apply(lambda v: "€ " + format_money(v))
                st.dataframe(
                    _card,
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                )

    with tab_btw:
        st.subheader("BTW-codetabel")
        st.dataframe(
            get_vat_codes(current_lines),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Gebruik per BTW-code")
        vat_usage = build_vat_usage(current_lines)
        _vat_usage = vat_usage.copy()
        for _col in ["totaal_grondslagbedrag", "totaal_btw_bedrag"]:
            if _col in _vat_usage.columns:
                _vat_usage[_col] = _vat_usage[_col].apply(format_euro_whole)
        st.dataframe(_vat_usage, use_container_width=True, hide_index=True)

        st.subheader("BTW-rondrekening")
        st.caption(
            "Vul per aangifterubriek het bedrag in volgens de ingediende BTW-aangifte. "
            "De tool vergelijkt dit met de BTW volgens de auditfile."
        )

        st.subheader("Ingediende BTW-aangifte")
        declared_by_rubric = {}
        for rubric in ["1a", "1e", "2a/5b", "5b"]:
            declared_by_rubric[rubric] = st.number_input(
                f"Aangiftebedrag rubriek {rubric}",
                value=0.00,
                step=1.00,
                format="%.2f",
                key=f"declared_rubric_{rubric}",
            )

        reconciliation = build_vat_reconciliation(current_lines, {})
        reconciliation_display = reconciliation.rename(columns={
            "vatID": "BTW-code",
            "vatDesc": "Omschrijving",
            "rubriek": "Rubriek",
            "aantal_transactieregels": "Aantal regels",
            "totaal_grondslagbedrag": "Grondslag",
            "btw_volgens_xaf": "BTW volgens XAF",
            "gebruikte_percentages": "Percentages",
        })
        recon_cols = [c for c in ["BTW-code", "Omschrijving", "Rubriek", "Aantal regels", "Grondslag", "BTW volgens XAF", "Percentages"] if c in reconciliation_display.columns]
        _recon = reconciliation_display[recon_cols].copy()
        for _col in ["Grondslag", "BTW volgens XAF"]:
            if _col in _recon.columns:
                _recon[_col] = _recon[_col].apply(format_euro_whole)
        st.dataframe(_recon, use_container_width=True, hide_index=True)

        st.subheader("Samenvatting per aangifterubriek")
        rubric_summary = build_vat_rubric_summary(reconciliation)
        if "rubriek" in rubric_summary.columns:
            rubric_summary["btw_volgens_aangifte"] = rubric_summary["rubriek"].map(
                lambda r: declared_by_rubric.get(r, 0)
            )
            rubric_summary["verschil"] = (
                rubric_summary["btw_volgens_xaf"]
                - rubric_summary["btw_volgens_aangifte"]
            ).abs().round(0)
            rubric_summary["status"] = rubric_summary.apply(
                lambda row: "—" if row["btw_volgens_aangifte"] == 0
                else ("✅ Sluit aan" if row["verschil"] < 1 else "⚠️ Verschil"),
                axis=1,
            )

        rubric_display = rubric_summary.rename(columns={
            "rubriek": "Rubriek",
            "btw_volgens_xaf": "BTW volgens XAF",
            "btw_volgens_aangifte": "Ingediende aangifte",
            "verschil": "Verschil",
            "status": "Status",
        })
        _rubric = rubric_display.copy()
        for _col in ["BTW volgens XAF", "Ingediende aangifte", "Verschil"]:
            if _col in _rubric.columns:
                _rubric[_col] = _rubric[_col].apply(format_euro_whole)
        st.dataframe(_rubric, use_container_width=True, hide_index=True)

        if "rubriek" in rubric_summary.columns and "btw_volgens_xaf" in rubric_summary.columns:
            btw_afdracht = rubric_summary.loc[
                rubric_summary["rubriek"].isin(["1a", "1b", "1c", "1d", "2a", "4a", "4b"]),
                "btw_volgens_xaf",
            ].sum()
            btw_voorbelasting = rubric_summary.loc[
                rubric_summary["rubriek"].isin(["5b"]),
                "btw_volgens_xaf",
            ].sum()
            netto_btw_xaf = btw_afdracht - btw_voorbelasting

            st.subheader("Netto BTW volgens XAF")
            col1, col2, col3 = st.columns(3)
            col1.metric("Af te dragen BTW", format_euro_whole(btw_afdracht))
            col2.metric("Voorbelasting", format_euro_whole(btw_voorbelasting))
            col3.metric("Netto te betalen", format_euro_whole(netto_btw_xaf))

        if "vatID" in vat_usage.columns and not vat_usage.empty:
            st.subheader("Drilldown per BTW-code")
            vat_options = vat_usage.assign(
                label=lambda df: df.apply(
                    lambda row: f"{row['vatID']} - {row.get('vatDesc', '')}",
                    axis=1,
                )
            )
            selected_vat_label = st.selectbox("Selecteer BTW-code", vat_options["label"].tolist())
            selected_vat_id = selected_vat_label.split(" - ", 1)[0]
            vat_drilldown = build_vat_drilldown(current_lines, selected_vat_id)

            show_all_vat_rows = st.checkbox("Toon alle regels", value=False)
            displayed_vat_drilldown = vat_drilldown if show_all_vat_rows else vat_drilldown.head(100)
            _drilldown = displayed_vat_drilldown.copy()
            for _col in ["tx_trDt", "line_effDate"]:
                if _col in _drilldown.columns:
                    _drilldown[_col] = _drilldown[_col].apply(format_date_nl)
            if "bedrag" in _drilldown.columns:
                _drilldown["bedrag"] = _drilldown["bedrag"].apply(lambda v: "€ " + format_money(v))
            if "BTW-bedrag" in _drilldown.columns:
                _drilldown["BTW-bedrag"] = _drilldown["BTW-bedrag"].apply(lambda v: "€ " + format_money(v))
            st.dataframe(_drilldown, use_container_width=True, hide_index=True, height=420)

            if "bedrag" in vat_drilldown.columns and "BTW-bedrag" in vat_drilldown.columns:
                summary_a, summary_b, summary_c = st.columns(3)
                summary_a.metric("Aantal transacties", f"{len(vat_drilldown):,}")
                summary_b.metric("Totaal grondslagbedrag", "€ " + format_money(vat_drilldown["bedrag"].sum()))
                summary_c.metric("Totaal BTW-bedrag", "€ " + format_money(vat_drilldown["BTW-bedrag"].sum()))

    with tab_controles:
        logical_controls = build_logical_controls(current_lines)
        st.dataframe(
            logical_controls,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    with tab_export:
        excel_export = build_excel_export(
            current_saldo=current_saldo,
            current_lines=current_lines,
            comparison=comparison,
            comparison_columns=display_columns,
        )
        st.download_button(
            label="Download Excel-export",
            data=excel_export,
            file_name="auditfile_analyzer_2024_2025.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
