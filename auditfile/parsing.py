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
    SUBADMINISTRATIE_COLUMNS,
    SUBADMINISTRATIE_TOTALEN_COLUMNS,
    TRANSACTION_COLUMNS,
    VAT_CODE_COLUMNS,
    VAT_LINE_COLUMNS,
    Auditfile,
    ControlTotals,
    empty_subadministratie,
    empty_subadministratie_totalen,
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


# De openstaande bedragen per relatie, met hun D/C-indicatie. Bron- en
# doelnaam staan hier naast elkaar omdat de brontag misleidend heet: opBalDesc
# suggereert een omschrijving en is in XAF 4.0 een bedrag.
RELATIESALDO_VELDEN: tuple[tuple[str, str, str], ...] = (
    ("openstaand_begin", "opBalDesc", "opBalTp"),
    ("openstaand_eind", "clBalDesc", "clBalTp"),
)


def _parse_relations(
    company: ET.Element | None, versie: str = ""
) -> tuple[pd.DataFrame, list[str]]:
    """Debiteuren en crediteuren uit customersSuppliers.

    De openstaande bedragen per relatie worden uitsluitend bij XAF 4.0 gelezen.
    Dat is geen overbodige voorzichtigheid: ``opBalDesc`` bestaat in beide
    versies en betekent in 3.2 een omschrijving van de beginbalans van het
    grootboek. Zou een 3.2-bestand die tag binnen een relatie zetten, dan werd
    een tekst als openstaand bedrag gelezen. De versiecontrole staat daarom hier
    en nergens anders; verder in de tool zijn de kolommen simpelweg leeg.

    Een waarde die geen getal is, wordt NaN en telt dus als niet aanwezig. Een
    veld dat er staat maar niet te lezen is, mag niet als gegeven doorgaan.
    """
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

    tekstkolommen = [
        kolom for kolom in RELATION_COLUMNS if kolom not in {naam for naam, _, _ in RELATIESALDO_VELDEN}
    ] + ["plaats", "land"]
    columns = tekstkolommen + [naam for naam, _, _ in RELATIESALDO_VELDEN]

    ruw = pd.DataFrame(rows)
    df = ensure_columns(ruw.copy(), tekstkolommen)
    for column in tekstkolommen:
        df[column] = df[column].fillna("").astype(str).str.strip()

    for naam, bedragtag, typetag in RELATIESALDO_VELDEN:
        if versie == "4.0" and bedragtag in ruw.columns:
            bedragen = pd.to_numeric(ruw[bedragtag].astype(str).str.strip(), errors="coerce")
            soorten = ruw[typetag] if typetag in ruw.columns else pd.Series("", index=ruw.index)
            getekend = signed_amount_series(bedragen.fillna(0.0), soorten)
            df[naam] = getekend.where(bedragen.notna())
        else:
            df[naam] = pd.Series(float("nan"), index=df.index, dtype="float64")

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


# --- Welke gegevensblokken zitten erin? -------------------------------------

# De blokken die deze tool niet als tabel inleest maar die bepalen wat er aan
# analyse mogelijk is. Ze worden bij het inlezen geteld, zodat de tool kan zeggen
# wat een bestand wel en niet toelaat in plaats van een analyse te tonen die op
# niets rust. Zie ``capability.py`` voor de interpretatie.
#
# De subadministratie van XAF 3.2 staat hier niet tussen: die wordt sinds
# ``_parse_subledgers()`` volledig ingelezen. Ernaast nog een aparte telling
# houden zou dezelfde kennis op twee plaatsen zetten, waar ze uiteen kan gaan
# lopen.
BLOK_TELLERS: tuple[str, ...] = (
    "relatie_opBalDesc",
    "relatie_clBalDesc",
    "settDate",
)


def _tel_elementen(wortel: ET.Element | None, naam: str, gevuld: bool = False) -> int:
    """Tel hoe vaak een element voorkomt binnen een deelboom.

    Met ``gevuld`` worden alleen elementen geteld die ook tekst hebben; een leeg
    element zegt niets over de beschikbaarheid van het gegeven.
    """
    if wortel is None:
        return 0
    aantal = 0
    for element in wortel.iter():
        if local_name(element.tag) != naam:
            continue
        if gevuld and not (element.text or "").strip():
            continue
        aantal += 1
    return aantal


def _tel_blokken(company: ET.Element | None) -> dict[str, int]:
    """Tel de blokken die bepalen welke analyse een bestand toelaat.

    Let op de context. ``opBalDesc`` bestaat in beide versies maar betekent iets
    anders: in XAF 3.2 is het een omschrijving van de beginbalans van het
    grootboek, in XAF 4.0 het openstaande bedrag per relatie. Daarom wordt hij
    uitsluitend binnen ``customersSuppliers`` geteld; buiten die deelboom zou de
    3.2-omschrijving als openstaand bedrag worden geteld.
    """
    tellingen = {sleutel: 0 for sleutel in BLOK_TELLERS}
    if company is None:
        return tellingen

    relaties = find_descendant(company, "customersSuppliers")
    transacties = find_descendant(company, "transactions")

    tellingen["relatie_opBalDesc"] = _tel_elementen(relaties, "opBalDesc", gevuld=True)
    tellingen["relatie_clBalDesc"] = _tel_elementen(relaties, "clBalDesc", gevuld=True)
    tellingen["settDate"] = _tel_elementen(transacties, "settDate", gevuld=True)
    return tellingen


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


# --- Subadministratie (alleen XAF 3.2) --------------------------------------

# Per blok: de naam die in de kolom ``bron`` komt, het omvattende element, het
# element per subadministratie en het element per regel.
SUBADMINISTRATIE_BLOKKEN: tuple[tuple[str, str, str, str], ...] = (
    ("beginbalans", "obSubledgers", "obSubledger", "obSbLine"),
    ("mutatie", "subledgers", "subledger", "sbLine"),
)

# De tekstvelden van een subadministratieregel die deze tool overneemt, met de
# naam in het model erachter waar die afwijkt. Wat de XSD verder toestaat
# (costID, prodID, projID, artGrpID, qntityID, qntity, recRef en bij sbLine een
# eigen vat- en currency-blok) blijft buiten het model: die velden gaan over
# kostenplaatsen, projecten en voorraad, niet over openstaande posten, en de
# btw-analyse werkt op de grootboekregels.
SUBADMINISTRATIE_VELDEN: tuple[tuple[str, str], ...] = (
    ("custSupID", "custSupID"),
    ("invRef", "invRef"),
    ("invTp", "invTp"),
    ("invPurSalTp", "invPurSalTp"),
    ("matchKeyID", "matchKeyID"),
    ("mutTp", "mutTp"),
    ("desc", "omschrijving"),
    ("docRef", "documentreferentie"),
)

# ``invDt`` is de factuurdatum en ``invDueDt`` de vervaldatum. Dit is de enige
# plek in XAF met een echte vervaldatum; ``trDt``, ``effDate`` en ``settDate``
# zijn dat alle drie niet. Zie ``docs/xaf-velden.md``.
SUBADMINISTRATIE_DATUMVELDEN: tuple[str, ...] = ("invDt", "invDueDt")

NIET_GEKOPPELD = "niet gevonden"
NIET_EENDUIDIG = "sleutel niet eenduidig"


def _rekeningkaart_beginbalans(opening_balance: pd.DataFrame) -> dict[str, set[str]]:
    """Regelnummer van de beginbalans -> de rekening(en) op dat nummer."""
    kaart: dict[str, set[str]] = {}
    if opening_balance.empty or "ob_nr" not in opening_balance.columns:
        return kaart
    for nummer, rekening in zip(
        opening_balance["ob_nr"].astype(str).str.strip(),
        opening_balance["ob_accID"].astype(str).str.strip(),
    ):
        kaart.setdefault(nummer, set()).add(rekening)
    return kaart


def _rekeningkaart_boekingen(lines: pd.DataFrame) -> dict[tuple[str, str, str], set[str]]:
    """Dagboek, transactie en regelnummer -> de rekening(en) op die sleutel.

    Een set en niet een enkele waarde, omdat de sleutel niet gegarandeerd uniek
    is: het schema legt alleen ``jrnID`` vast en pakketten hergebruiken een
    transactienummer. Wijzen twee boekingen met dezelfde sleutel naar dezelfde
    rekening, dan is de uitkomst alsnog eenduidig; wijzen ze naar verschillende
    rekeningen, dan valt de rekening niet vast te stellen en zegt de tool dat.
    """
    kaart: dict[tuple[str, str, str], set[str]] = {}
    if lines.empty or "line_nr" not in lines.columns:
        return kaart
    for dagboek, transactie, regel, rekening in zip(
        lines["tx_jrnID"].astype(str).str.strip(),
        lines["tx_nr"].astype(str).str.strip(),
        lines["line_nr"].astype(str).str.strip(),
        lines["line_accID"].astype(str).str.strip(),
    ):
        kaart.setdefault((dagboek, transactie, regel), set()).add(rekening)
    return kaart


def _koppel_rekening(kaart: dict, sleutel, methode: str) -> tuple[str, str]:
    """De rekening bij een verwijzing, met de manier waarop die is gevonden."""
    rekeningen = kaart.get(sleutel)
    if rekeningen is None:
        return "", NIET_GEKOPPELD
    if len(rekeningen) > 1:
        return "", NIET_EENDUIDIG
    return next(iter(rekeningen)), methode


def _parse_subledgers(
    company: ET.Element | None,
    opening_balance: pd.DataFrame,
    lines: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lees de subadministratie van XAF 3.2: ``obSbLine`` en ``sbLine``.

    Deze blokken bestaan alleen in XAF 3.2; XAF 4.0 heeft ze geschrapt. Toch
    staat hier geen versiecontrole, anders dan bij de openstaande bedragen per
    relatie. Daar was die nodig omdat ``opBalDesc`` in beide versies bestaat en
    iets anders betekent, dus een omschrijving als bedrag gelezen zou kunnen
    worden. Hier is niets dubbelzinnig: ``obSubledgers`` en ``subledgers`` komen
    in 4.0 niet voor, en de regels worden bovendien alleen binnen die twee
    deelbomen gezocht. Een 4.0-bestand levert daarmee een lege tabel op zonder
    dat de versie hoeft te worden bevraagd.

    De rekening staat niet op de regel zelf. ``obSbLine`` draagt ``obLineNr``,
    het regelnummer van de beginbalans, en ``sbLine`` draagt ``jrnID``, ``trNr``
    en ``trLineNr`` naar de grootboekboeking. Beide verwijzingen worden hier
    opgelost; lukt dat niet, dan blijft de rekening leeg en staat in
    ``koppeling`` waarom.

    Naast de regels komen de controletotalen mee die elke subadministratie zelf
    opgeeft, met ernaast wat er werkelijk is gelezen. Het oordeel over een
    verschil hoort in ``integrity.py`` en niet hier.
    """
    beginbalans = _rekeningkaart_beginbalans(opening_balance)
    boekingen = _rekeningkaart_boekingen(lines)

    regels: list[dict] = []
    totalen: list[dict] = []
    for bron, bloknaam, subnaam, lijnnaam in SUBADMINISTRATIE_BLOKKEN:
        blok = find_descendant(company, bloknaam)
        if blok is None:
            continue
        index = 0
        for subledger in blok:
            if local_name(subledger.tag) != subnaam:
                continue
            index += 1
            kop = child_texts(subledger)
            gelezen = 0
            debet = 0.0
            credit = 0.0
            for lijn in subledger:
                if local_name(lijn.tag) != lijnnaam:
                    continue
                waarden = child_texts(lijn)
                soort = str(waarden.get("amntTp", "")).strip().upper()
                bedrag = signed_amount(waarden.get("amnt"), soort)
                # De zijde volgt uit amntTp en een negatief bedrag verlaagt het
                # totaal van de eigen zijde, net zoals bij de grootboekregels en
                # zoals de controletotalen in het bestand zelf zijn opgebouwd.
                if soort == "C":
                    credit -= bedrag
                else:
                    debet += bedrag
                gelezen += 1

                if bron == "beginbalans":
                    rekening, koppeling = _koppel_rekening(
                        beginbalans, str(waarden.get("obLineNr", "")).strip(), "obLineNr"
                    )
                else:
                    rekening, koppeling = _koppel_rekening(
                        boekingen,
                        tuple(
                            str(waarden.get(veld, "")).strip()
                            for veld in ("jrnID", "trNr", "trLineNr")
                        ),
                        "jrnID/trNr/trLineNr",
                    )

                rij = {
                    "bron": bron,
                    "sb_index": index,
                    "sbType": kop.get("sbType", ""),
                    "sbDesc": kop.get("sbDesc", ""),
                    "sb_nr": str(waarden.get("nr", "")).strip(),
                    "rekening": rekening,
                    "koppeling": koppeling,
                    "amntTp": soort,
                    "bedrag": bedrag,
                }
                for veld in ("obLineNr", "jrnID", "trNr", "trLineNr"):
                    rij[veld] = str(waarden.get(veld, "")).strip()
                for brontag, kolom in SUBADMINISTRATIE_VELDEN:
                    rij[kolom] = str(waarden.get(brontag, "")).strip()
                for veld in SUBADMINISTRATIE_DATUMVELDEN:
                    rij[veld] = str(waarden.get(veld, "")).strip()
                regels.append(rij)

            totalen.append(
                {
                    "bron": bron,
                    "sb_index": index,
                    "sbType": kop.get("sbType", ""),
                    "sbDesc": kop.get("sbDesc", ""),
                    "regels_volgens_bestand": kop.get("linesCount", ""),
                    "totaal_debet_volgens_bestand": kop.get("totalDebit", ""),
                    "totaal_credit_volgens_bestand": kop.get("totalCredit", ""),
                    "regels_gelezen": gelezen,
                    "totaal_debet_gelezen": debet,
                    "totaal_credit_gelezen": credit,
                }
            )

    if regels:
        sub = ensure_columns(pd.DataFrame(regels), SUBADMINISTRATIE_COLUMNS)
        for kolom in SUBADMINISTRATIE_DATUMVELDEN:
            sub[kolom] = pd.to_datetime(sub[kolom], errors="coerce", format="ISO8601")
        sub["sb_index"] = pd.to_numeric(sub["sb_index"], errors="coerce").astype("Int64")
        sub = sub[SUBADMINISTRATIE_COLUMNS].reset_index(drop=True)
    else:
        sub = empty_subadministratie()

    if totalen:
        sub_totalen = ensure_columns(pd.DataFrame(totalen), SUBADMINISTRATIE_TOTALEN_COLUMNS)
        # Een ontbrekend of onleesbaar controletotaal wordt NaN en geen nul: zo is
        # zichtbaar dat het totaal er niet staat in plaats van dat het bestand
        # nul zou opgeven.
        for kolom in (
            "regels_volgens_bestand",
            "totaal_debet_volgens_bestand",
            "totaal_credit_volgens_bestand",
        ):
            sub_totalen[kolom] = pd.to_numeric(sub_totalen[kolom], errors="coerce")
        sub_totalen = sub_totalen[SUBADMINISTRATIE_TOTALEN_COLUMNS].reset_index(drop=True)
    else:
        sub_totalen = empty_subadministratie_totalen()

    return sub, sub_totalen


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

    versie = _xaf_version(root)
    accounts, dubbele_rekeningen = _parse_accounts(company)
    vat_codes, dubbele_btw_codes = _parse_vat_codes(company)
    relations, dubbele_relaties = _parse_relations(company, versie)
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
    blokken = _tel_blokken(company)

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

    # Na het normaliseren van de boekingsregels, want de subadministratie
    # verwijst ernaar om haar rekening te vinden.
    subadministratie, subadministratie_totalen = _parse_subledgers(
        company, opening_balance, lines
    )
    saldo = _build_saldo(accounts, opening_balance, lines)

    return Auditfile(
        bestandsnaam=file_name,
        xaf_versie=versie,
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
        subadministratie=subadministratie,
        subadministratie_totalen=subadministratie_totalen,
        duplicaten=duplicaten,
        blokken=blokken,
    )
