"""Integriteitscontrole van het auditfile zelf.

Voordat je op cijfers uit een auditfile vertrouwt, moet vaststaan dat het
bestand intern consistent is. Deze module toetst het bestand aan de
controletotalen die het zelf opgeeft en aan een aantal boekhoudkundige
minimumeisen. De uitkomst is bewust een platte bevindingenlijst, zodat die
zowel op het scherm als in de Excel-export past.

Ernstniveaus
------------
``kritiek``       het bestand is niet betrouwbaar; conclusies staan op losse schroeven
``waarschuwing``  afwijking die verklaard kan zijn maar beoordeling vraagt
``in orde``       de controle is uitgevoerd en gaf geen afwijking
``niet mogelijk`` het bestand bevat de gegevens niet om deze controle te doen
"""
from __future__ import annotations

import pandas as pd

from .model import Auditfile

KRITIEK = "kritiek"
WAARSCHUWING = "waarschuwing"
IN_ORDE = "in orde"
NIET_MOGELIJK = "niet mogelijk"

# Verschillen kleiner dan een halve cent zijn afrondingsruis in float-optellingen.
TOLERANTIE = 0.005

BEVINDING_COLUMNS = ["ernst", "controle", "bevinding", "aantal", "verschil"]

# Bij een dubbeling worden de betrokken identificaties genoemd, maar niet
# eindeloos: een bevindingregel moet leesbaar blijven.
MAXIMAAL_GENOEMD = 10


def _bevinding(ernst: str, controle: str, bevinding: str, aantal=None, verschil=None) -> dict:
    return {
        "ernst": ernst,
        "controle": controle,
        "bevinding": bevinding,
        "aantal": aantal,
        "verschil": verschil,
    }


def _vergelijk_totaal(
    controle: str,
    berekend: float,
    opgegeven: float | None,
    eenheid: str = "",
) -> dict:
    if opgegeven is None:
        return _bevinding(NIET_MOGELIJK, controle, "Het bestand geeft dit controletotaal niet op.")
    verschil = berekend - opgegeven
    if abs(verschil) < TOLERANTIE:
        return _bevinding(IN_ORDE, controle, f"Sluit aan op het bestand{eenheid}.", verschil=0.0)
    return _bevinding(
        KRITIEK,
        controle,
        "Het berekende totaal wijkt af van het totaal dat het bestand zelf opgeeft.",
        verschil=verschil,
    )


def controleer_auditfile(af: Auditfile) -> pd.DataFrame:
    """Voer alle integriteitscontroles uit en geef de bevindingen terug."""
    bevindingen: list[dict] = []
    lines = af.lines

    # --- Controletotalen van de transacties ---
    if lines.empty:
        bevindingen.append(
            _bevinding(KRITIEK, "Boekingsregels aanwezig", "Het bestand bevat geen boekingsregels.")
        )
    else:
        is_debet = lines["line_amntTp"].astype(str).str.strip().str.upper().eq("D")
        bevindingen.append(
            _vergelijk_totaal("Totaal debet", lines.loc[is_debet, "bedrag"].sum(), af.transaction_totals.total_debit)
        )
        bevindingen.append(
            _vergelijk_totaal("Totaal credit", -lines.loc[~is_debet, "bedrag"].sum(), af.transaction_totals.total_credit)
        )

        aantal = af.transaction_totals.lines_count
        if aantal is None:
            bevindingen.append(
                _bevinding(NIET_MOGELIJK, "Aantal boekingsregels", "Het bestand geeft geen linesCount op.")
            )
        elif aantal == len(lines):
            bevindingen.append(
                _bevinding(IN_ORDE, "Aantal boekingsregels", f"{len(lines)} regels, gelijk aan het bestand.", aantal=len(lines))
            )
        else:
            bevindingen.append(
                _bevinding(
                    KRITIEK,
                    "Aantal boekingsregels",
                    f"Het bestand meldt {aantal} regels, gelezen zijn er {len(lines)}.",
                    aantal=len(lines) - aantal,
                )
            )

        # --- Sluit het geheel op nul? ---
        totaal = lines["bedrag"].sum()
        if abs(totaal) < TOLERANTIE:
            bevindingen.append(_bevinding(IN_ORDE, "Debet is gelijk aan credit", "Alle boekingen samen sluiten op nul.", verschil=0.0))
        else:
            bevindingen.append(
                _bevinding(
                    KRITIEK,
                    "Debet is gelijk aan credit",
                    "De boekingen samen sluiten niet op nul; het journaal is onvolledig of onevenwichtig.",
                    verschil=totaal,
                )
            )

        # --- Sluit elke transactie afzonderlijk? ---
        per_transactie = lines.groupby(["tx_jrnID", "tx_nr"], dropna=False)["bedrag"].sum()
        scheef = per_transactie[per_transactie.abs() >= TOLERANTIE]
        if scheef.empty:
            bevindingen.append(
                _bevinding(IN_ORDE, "Iedere transactie sluit op nul", f"Alle {len(per_transactie)} transacties zijn in evenwicht.", aantal=0)
            )
        else:
            bevindingen.append(
                _bevinding(
                    KRITIEK,
                    "Iedere transactie sluit op nul",
                    f"{len(scheef)} van de {len(per_transactie)} transacties zijn niet in evenwicht.",
                    aantal=len(scheef),
                    verschil=float(scheef.sum()),
                )
            )

        bevindingen.extend(_controleer_regels(af))

    # --- Beginbalans ---
    bevindingen.extend(_controleer_beginbalans(af))

    # --- Stamgegevens ---
    bevindingen.extend(_controleer_stamgegevens(af))

    return pd.DataFrame(bevindingen, columns=BEVINDING_COLUMNS)


def _controleer_beginbalans(af: Auditfile) -> list[dict]:
    bevindingen = []
    ob = af.opening_balance
    if ob.empty:
        bevindingen.append(
            _bevinding(WAARSCHUWING, "Beginbalans aanwezig", "Het bestand bevat geen beginbalans; beginsaldi zijn nul verondersteld.")
        )
        return bevindingen

    is_debet = ob["ob_amntTp"].astype(str).str.strip().str.upper().eq("D")
    onvolledig = (
        "De beginbalans in het bestand is onvolledig ten opzichte van de eigen "
        "controletotalen. Daardoor kunnen beginsaldi ontbreken en zijn de "
        "eindsaldi van balansrekeningen mogelijk te laag."
    )
    for naam, berekend, opgegeven in (
        ("Beginbalans totaal debet", ob.loc[is_debet, "beginsaldo"].sum(), af.opening_totals.total_debit),
        ("Beginbalans totaal credit", -ob.loc[~is_debet, "beginsaldo"].sum(), af.opening_totals.total_credit),
    ):
        uitkomst = _vergelijk_totaal(naam, berekend, opgegeven)
        if uitkomst["ernst"] == KRITIEK:
            uitkomst["bevinding"] = onvolledig
        bevindingen.append(uitkomst)

    aantal = af.opening_totals.lines_count
    if aantal is not None and aantal != len(ob):
        bevindingen.append(
            _bevinding(
                WAARSCHUWING,
                "Aantal beginbalansregels",
                f"Het bestand meldt {aantal} regels, gelezen zijn er {len(ob)}. "
                "Controleer de beginsaldi tegen de jaarrekening van vorig jaar.",
                aantal=len(ob) - aantal,
            )
        )
    elif aantal is not None:
        bevindingen.append(
            _bevinding(IN_ORDE, "Aantal beginbalansregels", f"{len(ob)} regels, gelijk aan het bestand.", aantal=len(ob))
        )

    totaal = ob["beginsaldo"].sum()
    if abs(totaal) < TOLERANTIE:
        bevindingen.append(_bevinding(IN_ORDE, "Beginbalans sluit op nul", "De beginbalans is in evenwicht.", verschil=0.0))
    else:
        bevindingen.append(
            _bevinding(KRITIEK, "Beginbalans sluit op nul", "De beginbalans is niet in evenwicht.", verschil=totaal)
        )

    # Een beginbalans hoort alleen balansrekeningen te bevatten.
    balansrekeningen = set(af.accounts.loc[af.accounts["accTp"].str.upper() == "B", "accID"])
    bekende = set(af.accounts["accID"])
    resultaat_in_ob = ob[
        ob["ob_accID"].isin(bekende) & ~ob["ob_accID"].isin(balansrekeningen)
    ]
    if resultaat_in_ob.empty:
        bevindingen.append(
            _bevinding(IN_ORDE, "Beginbalans bevat alleen balansrekeningen", "Geen resultaatrekeningen in de beginbalans.", aantal=0)
        )
    else:
        bevindingen.append(
            _bevinding(
                WAARSCHUWING,
                "Beginbalans bevat alleen balansrekeningen",
                f"{len(resultaat_in_ob)} beginbalansregel(s) staan op een resultaatrekening.",
                aantal=len(resultaat_in_ob),
                verschil=float(resultaat_in_ob["beginsaldo"].sum()),
            )
        )
    return bevindingen


def _controleer_regels(af: Auditfile) -> list[dict]:
    """Controles op de boekingsregels zelf."""
    bevindingen = []
    lines = af.lines

    # Boekingen op rekeningen die niet in het rekeningschema staan.
    bekende = set(af.accounts["accID"])
    onbekend = lines[~lines["line_accID"].isin(bekende)]
    if onbekend.empty:
        bevindingen.append(
            _bevinding(IN_ORDE, "Rekeningen bestaan in het schema", "Alle boekingen staan op een bekende grootboekrekening.", aantal=0)
        )
    else:
        bevindingen.append(
            _bevinding(
                KRITIEK,
                "Rekeningen bestaan in het schema",
                f"{len(onbekend)} regel(s) staan op {onbekend['line_accID'].nunique()} rekening(en) die niet in het schema voorkomen.",
                aantal=len(onbekend),
                verschil=float(onbekend["bedrag"].sum()),
            )
        )

    # Datums buiten het boekjaar.
    start = pd.to_datetime(af.header.get("startDate", ""), errors="coerce")
    eind = pd.to_datetime(af.header.get("endDate", ""), errors="coerce")
    if pd.isna(start) or pd.isna(eind):
        bevindingen.append(
            _bevinding(NIET_MOGELIJK, "Boekingen binnen het boekjaar", "De header geeft geen begin- of einddatum van het boekjaar.")
        )
    else:
        datums = lines["datum"]
        buiten = lines[datums.notna() & ((datums < start) | (datums > eind))]
        zonder = lines[datums.isna()]
        if buiten.empty:
            bevindingen.append(
                _bevinding(IN_ORDE, "Boekingen binnen het boekjaar", "Alle boekingen vallen binnen het boekjaar.", aantal=0)
            )
        else:
            bevindingen.append(
                _bevinding(
                    WAARSCHUWING,
                    "Boekingen binnen het boekjaar",
                    f"{len(buiten)} regel(s) hebben een boekdatum buiten het boekjaar.",
                    aantal=len(buiten),
                    verschil=float(buiten["bedrag"].sum()),
                )
            )
        if not zonder.empty:
            bevindingen.append(
                _bevinding(
                    WAARSCHUWING,
                    "Boekdatum leesbaar",
                    f"{len(zonder)} regel(s) hebben geen leesbare boekdatum.",
                    aantal=len(zonder),
                )
            )

    # Periodenummers die niet in de periodetabel voorkomen.
    if af.periods.empty:
        bevindingen.append(
            _bevinding(NIET_MOGELIJK, "Perioden bestaan in de periodetabel", "Het bestand bevat geen periodetabel.")
        )
    else:
        bekende_perioden = set(af.periods["periodNumber"])
        periode = lines["periode"]
        buiten = lines[periode.notna() & ~periode.isin(bekende_perioden)]
        if buiten.empty:
            bevindingen.append(
                _bevinding(IN_ORDE, "Perioden bestaan in de periodetabel", "Alle boekingen vallen in een bekende periode.", aantal=0)
            )
        else:
            bevindingen.append(
                _bevinding(
                    WAARSCHUWING,
                    "Perioden bestaan in de periodetabel",
                    f"{len(buiten)} regel(s) verwijzen naar een periode die niet in de periodetabel staat.",
                    aantal=len(buiten),
                )
            )

    # Btw-codes die niet in de codetabel staan.
    gebruikte = set(lines.loc[lines["vat_vatID"] != "", "vat_vatID"])
    gebruikte |= set(lines.loc[lines["line_vatID"] != "", "line_vatID"])
    onbekende_codes = gebruikte - set(af.vat_codes["vatID"])
    if not gebruikte:
        bevindingen.append(
            _bevinding(WAARSCHUWING, "Btw-codes bestaan in de codetabel", "Geen enkele boekingsregel heeft een btw-code.")
        )
    elif onbekende_codes:
        bevindingen.append(
            _bevinding(
                WAARSCHUWING,
                "Btw-codes bestaan in de codetabel",
                f"{len(onbekende_codes)} gebruikte btw-code(s) komen niet voor in de codetabel: {', '.join(sorted(onbekende_codes))}.",
                aantal=len(onbekende_codes),
            )
        )
    else:
        bevindingen.append(
            _bevinding(IN_ORDE, "Btw-codes bestaan in de codetabel", "Alle gebruikte btw-codes staan in de codetabel.", aantal=0)
        )

    return bevindingen


def _controleer_stamgegevens(af: Auditfile) -> list[dict]:
    bevindingen = []

    # Dubbele stamgegevens. De parser houdt per identificatie het eerste record
    # aan; welke identificaties dubbel voorkwamen is daarom bij het inlezen
    # vastgelegd. Deze controle op de opgeschoonde tabellen uitvoeren zou altijd
    # nul opleveren.
    if af.duplicaten:
        for soort, waarden in af.duplicaten.items():
            genoemd = ", ".join(waarden[:MAXIMAAL_GENOEMD])
            if len(waarden) > MAXIMAAL_GENOEMD:
                genoemd += f" en {len(waarden) - MAXIMAAL_GENOEMD} andere"
            bevindingen.append(
                _bevinding(
                    WAARSCHUWING,
                    "Stamgegevens zonder dubbelingen",
                    f"{len(waarden)} {soort} komen meer dan eens voor in het bestand; "
                    f"het eerste record is aangehouden: {genoemd}.",
                    aantal=len(waarden),
                )
            )
    else:
        bevindingen.append(
            _bevinding(
                IN_ORDE,
                "Stamgegevens zonder dubbelingen",
                "Rekeningen, btw-codes, relaties en perioden komen elk eenmaal voor.",
                aantal=0,
            )
        )

    # Rekeningen zonder bruikbaar type kunnen niet in balans of resultaat worden ingedeeld.
    types = af.accounts["accTp"].astype(str).str.strip().str.upper()
    zonder_type = int((~types.isin(["B", "P"])).sum())
    if zonder_type:
        bevindingen.append(
            _bevinding(
                WAARSCHUWING,
                "Rekeningtype ingevuld",
                f"{zonder_type} rekening(en) hebben geen bruikbaar type B of P en vallen buiten balans en resultatenrekening.",
                aantal=zonder_type,
            )
        )
    else:
        bevindingen.append(
            _bevinding(IN_ORDE, "Rekeningtype ingevuld", "Alle rekeningen zijn ingedeeld als balans of resultaat.", aantal=0)
        )

    return bevindingen


def samenvatting(bevindingen: pd.DataFrame) -> dict[str, int]:
    """Aantal bevindingen per ernstniveau."""
    if bevindingen.empty:
        return {KRITIEK: 0, WAARSCHUWING: 0, IN_ORDE: 0, NIET_MOGELIJK: 0}
    telling = bevindingen["ernst"].value_counts().to_dict()
    return {niveau: int(telling.get(niveau, 0)) for niveau in (KRITIEK, WAARSCHUWING, IN_ORDE, NIET_MOGELIJK)}
