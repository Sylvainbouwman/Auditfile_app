from __future__ import annotations

from io import BytesIO
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


@st.cache_data(show_spinner=False)
def parse_auditfile(file_name: str, file_bytes: bytes) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    del file_name
    root = ET.parse(BytesIO(file_bytes)).getroot()

    accounts = []
    for element in root.iter():
        if local_name(element.tag) == "ledgerAccount":
            accounts.append(child_texts(element))

    df_accounts = pd.DataFrame(accounts)
    df_accounts = ensure_columns(df_accounts, ACCOUNT_COLUMNS)
    df_accounts[ACCOUNT_COLUMNS] = df_accounts[ACCOUNT_COLUMNS].fillna("").astype(str)
    df_accounts = df_accounts.drop_duplicates(subset=["accID"], keep="first")

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
                lines.append({**transaction_info, **line_info})

    df_lines = pd.DataFrame(lines)
    df_lines = ensure_columns(df_lines, TRANSACTION_COLUMNS + LINE_COLUMNS)

    if df_lines.empty:
        mutation_saldo = pd.DataFrame(columns=["rekening", "mutaties_boekjaar", "aantal_boekingsregels"])
    else:
        df_lines[TRANSACTION_COLUMNS + LINE_COLUMNS] = df_lines[TRANSACTION_COLUMNS + LINE_COLUMNS].fillna("")
        df_lines["line_accID"] = df_lines["line_accID"].astype(str)
        df_lines["line_amnt"] = pd.to_numeric(df_lines["line_amnt"], errors="coerce").fillna(0.0)
        df_lines["bedrag"] = df_lines.apply(amount_to_signed, axis=1)

        df_lines = df_lines.merge(
            df_accounts[ACCOUNT_COLUMNS],
            left_on="line_accID",
            right_on="accID",
            how="left",
        )
        df_lines = ensure_columns(df_lines, ACCOUNT_COLUMNS)
        df_lines[["accDesc", "accTp", "RGScode"]] = df_lines[["accDesc", "accTp", "RGScode"]].fillna("")

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


def format_money(value: float) -> str:
    return f"EUR {value:,.2f}"


def main() -> None:
    st.title("Auditfile Analyzer")
    st.write("Vergelijk twee XAF/XML auditfiles op grootboekrekening en bekijk de grootboekkaart.")

    left, right = st.columns(2)
    with left:
        previous_file = st.file_uploader("Upload auditfile vorig jaar", type=["xaf", "xml"], key="previous")
    with right:
        current_file = st.file_uploader("Upload auditfile huidig jaar", type=["xaf", "xml"], key="current")

    if not previous_file or not current_file:
        st.info("Upload beide auditfiles om de vergelijking te maken.")
        st.stop()

    try:
        _, previous_lines, previous_saldo = parse_auditfile(
            previous_file.name,
            previous_file.getvalue(),
        )
        _, current_lines, current_saldo = parse_auditfile(
            current_file.name,
            current_file.getvalue(),
        )
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

    st.subheader("Top 20 grootste afwijkingen")
    st.dataframe(
        comparison.head(20)[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Vergelijking per grootboekrekening")
    status_filter = st.multiselect(
        "Status",
        options=["bestaand", "nieuw", "vervallen"],
        default=["bestaand", "nieuw", "vervallen"],
    )
    filtered_comparison = comparison[comparison["status"].isin(status_filter)]
    st.dataframe(
        filtered_comparison[display_columns],
        use_container_width=True,
        hide_index=True,
        height=520,
    )

    st.subheader("Grootboekkaart huidig jaar")
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
        st.stop()

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
            f"Saldo huidig jaar: {format_money(card['bedrag'].sum())}"
        )
        st.dataframe(
            card[CARD_COLUMNS],
            use_container_width=True,
            hide_index=True,
            height=500,
        )


if __name__ == "__main__":
    main()
