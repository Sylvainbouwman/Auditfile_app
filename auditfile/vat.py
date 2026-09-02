"""Btw-analyse op een auditfile.

De opzet in het kort
--------------------
Een auditfile bevat geen aangifte. Wel bevat hij per boekingsregel een btw-code
met percentage en btw-bedrag. Deze module:

1. vat het gebruik per btw-code samen (grondslag, btw, percentages, zijde);
2. stelt per code een aangifterubriek voor, met reden en zekerheid;
3. laat die toewijzing overschrijven door de gebruiker;
4. telt op tot een netto btw-positie volgens de auditfile;
5. sluit die aan op de btw-grootboekrekeningen én op de ingediende aangifte;
6. signaleert btw-anomalieën op regelniveau.

Tekens
------
In het grootboek staat af te dragen btw credit (negatief) en voorbelasting
debet (positief). Op het aangifteformulier staan beide juist als positief
bedrag. Elke rubriek heeft daarom een teken waarmee het grootboekbedrag naar
een aangiftebedrag wordt omgerekend. Beide worden getoond, zodat de omrekening
navolgbaar blijft en een onverwacht teken opvalt in plaats van weg te vallen.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .model import Auditfile
from .vat_rubrics import (
    AFDRACHT,
    AFDRACHT_CODES,
    INFORMATIEF,
    ONBEKEND,
    RUBRIEK_PER_CODE,
    VOORBELASTING,
    VOORBELASTING_CODES,
    rubriek,
)

# Een btw-bedrag mag van grondslag maal percentage afwijken door afronding per
# factuurregel. Deze marge is bewust ruim: hij moet echte fouten tonen, geen
# centenverschillen.
AFRONDINGSMARGE_EURO = 1.00
AFRONDINGSMARGE_RELATIEF = 0.02

# Boven dit percentage geldt een tarief als "hoog". De grens is bewust ruim
# gekozen zodat een tariefwijziging de indeling niet ongeldig maakt.
GRENS_HOOG_TARIEF = 15.0

# Rubrieken waarvan de grondslag omzet is; die staat credit in het grootboek.
OMZETGRONDSLAG = {"1a", "1b", "1c", "1d", "1e", "3a", "3b", "3c"}


def grondslag_teken(rubriek_code: str) -> int:
    """Teken om een grootboekgrondslag naar een aangiftegrondslag om te rekenen."""
    return -1 if rubriek_code in OMZETGRONDSLAG else 1


def btw_teken(rubriek_code: str) -> int:
    """Teken om een grootboek-btw-bedrag naar een aangiftebedrag om te rekenen."""
    return -1 if rubriek_code in AFDRACHT_CODES else 1


# --- Gebruik per btw-code ---------------------------------------------------


def btw_regels(af: Auditfile) -> pd.DataFrame:
    """Alle boekingsregels met een btw-code.

    Een code kan zowel in het ``<vat>``-blok als los op de regel staan; beide
    tellen mee, met het vat-blok als eerste keus.
    """
    lines = af.lines
    if lines.empty:
        return lines.copy()
    code = lines["vat_vatID"].astype(str).str.strip()
    fallback = lines["line_vatID"].astype(str).str.strip()
    code = code.where(code != "", fallback)
    result = lines.assign(btw_code=code)
    return result[result["btw_code"] != ""].copy()


def build_vat_usage(af: Auditfile) -> pd.DataFrame:
    """Vat het gebruik per btw-code samen en stel een rubriek voor."""
    regels = btw_regels(af)
    kolommen = [
        "btw_code",
        "omschrijving",
        "aantal_regels",
        "grondslag_grootboek",
        "btw_grootboek",
        "percentages",
        "hoofdpercentage",
        "aandeel_credit",
        "rubriek_voorstel",
        "zekerheid",
        "reden",
    ]
    if regels.empty:
        return pd.DataFrame(columns=kolommen)

    def percentages(waarden: pd.Series) -> str:
        uniek = sorted({float(waarde) for waarde in waarden.dropna()})
        return ", ".join(f"{waarde:g}%" for waarde in uniek)

    def hoofdpercentage(waarden: pd.Series) -> float:
        """Het percentage dat het vaakst voorkomt; leeg als er geen is."""
        schoon = waarden.dropna()
        if schoon.empty:
            return float("nan")
        return float(schoon.mode().iloc[0])

    usage = (
        regels.groupby("btw_code", dropna=False)
        .agg(
            aantal_regels=("bedrag", "size"),
            grondslag_grootboek=("bedrag", "sum"),
            btw_grootboek=("btw_bedrag", "sum"),
            percentages=("vat_vatPerc", percentages),
            hoofdpercentage=("vat_vatPerc", hoofdpercentage),
            # Aandeel van de grondslag dat credit staat: bij omzet richting 1,
            # bij kosten richting 0. Dit is het sterkste signaal voor de zijde.
            aandeel_credit=("bedrag", lambda reeks: float((reeks < 0).mean())),
        )
        .reset_index()
    )

    codes = af.vat_codes.rename(columns={"vatID": "btw_code", "vatDesc": "omschrijving"})
    usage = usage.merge(
        codes[["btw_code", "omschrijving", "vatToPayAccID", "vatToClaimAccID"]],
        on="btw_code",
        how="left",
    )
    for kolom in ["omschrijving", "vatToPayAccID", "vatToClaimAccID"]:
        usage[kolom] = usage[kolom].fillna("")

    voorstellen = usage.apply(_stel_rubriek_voor, axis=1, result_type="expand")
    usage[["rubriek_voorstel", "zekerheid", "reden"]] = voorstellen
    return usage[kolommen].sort_values("btw_code").reset_index(drop=True)


# Trefwoorden die op een rubriek wijzen, in volgorde van specifiek naar algemeen.
_TREFWOORDEN: tuple[tuple[str, str, str], ...] = (
    (r"prive|privé|bijtelling", "1d", "de omschrijving wijst op privegebruik"),
    (r"invoer|art(ikel)?\.?\s*23", "4a", "de omschrijving wijst op invoer"),
    (r"verwerving|intracommunautaire verwerving|icv", "4b", "de omschrijving wijst op een verwerving binnen de EU"),
    (r"uitvoer|export|buiten de eu|derde land", "3a", "de omschrijving wijst op uitvoer"),
    (r"\bicp\b|intracommunautair|binnen de eu|\bicl\b", "3b", "de omschrijving wijst op een prestatie binnen de EU"),
    (r"voorbelasting|te vorderen|inkoop.*btw|btw.*inkoop", "5b", "de omschrijving wijst op voorbelasting"),
)


def _stel_rubriek_voor(rij: pd.Series) -> pd.Series:
    """Stel een aangifterubriek voor bij een btw-code.

    Het voorstel combineert vier signalen: een expliciete rubriekcode in de
    omschrijving, trefwoorden, de debet/credit-zijde van de grondslag en het
    percentage. De reden wordt meegegeven zodat de gebruiker het voorstel kan
    beoordelen in plaats van het te moeten geloven.
    """
    omschrijving = str(rij.get("omschrijving", "")).lower()
    aandeel_credit = float(rij.get("aandeel_credit", 0.0) or 0.0)
    percentage = rij.get("hoofdpercentage")
    percentage = float(percentage) if pd.notna(percentage) else None
    is_omzet = aandeel_credit >= 0.5

    # 1. Een expliciete rubriekcode in de omschrijving is het hardste signaal.
    expliciet = re.search(r"(?<![0-9a-z])([1-5][a-e])(?![0-9a-z])", omschrijving)
    if expliciet:
        code = expliciet.group(1)
        if code in RUBRIEK_PER_CODE:
            return pd.Series([code, "hoog", f"de omschrijving noemt rubriek {code} letterlijk"])

    # 2. Verlegging: dezelfde term betekent iets anders aan de verkoop- en aan
    #    de inkoopkant. De zijde van de grondslag geeft de doorslag.
    if re.search(r"verleg", omschrijving):
        if is_omzet:
            return pd.Series(["1e", "middel", "verlegging bij een omzetcode: de leverancier geeft alleen de grondslag aan"])
        return pd.Series(["2a", "middel", "verlegging bij een inkoopcode: de btw is naar de afnemer verlegd"])

    # 3. Overige trefwoorden.
    for patroon, code, reden in _TREFWOORDEN:
        if re.search(patroon, omschrijving):
            return pd.Series([code, "middel", reden])

    # 4. Zonder trefwoord resteren de zijde en het percentage.
    if percentage is not None and percentage > 0:
        if is_omzet:
            code = "1a" if percentage >= GRENS_HOOG_TARIEF else "1b"
            tarief = "hoog" if percentage >= GRENS_HOOG_TARIEF else "laag"
            return pd.Series([code, "middel", f"omzetcode met {percentage:g}% ({tarief} tarief)"])
        return pd.Series(["5b", "middel", f"inkoopcode met {percentage:g}%, dus voorbelasting"])

    if percentage == 0:
        if is_omzet:
            return pd.Series(["1e", "laag", "omzetcode met 0%; controleer of dit 1e, 3a, 3b of 3c moet zijn"])
        return pd.Series([ONBEKEND, "laag", "inkoopcode met 0% zonder nadere aanwijzing"])

    return pd.Series([ONBEKEND, "geen", "geen percentage en geen herkenbare omschrijving"])


# --- Toewijzing en optelling ------------------------------------------------


def pas_mapping_toe(usage: pd.DataFrame, mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """Voeg de definitief gekozen rubriek per btw-code toe.

    Een keuze van de gebruiker gaat altijd voor op het voorstel.
    """
    mapping = mapping or {}
    result = usage.copy()
    if result.empty:
        result["rubriek"] = pd.Series(dtype="object")
        result["rubriek_bron"] = pd.Series(dtype="object")
        return result

    gekozen = result["btw_code"].astype(str).map(mapping)
    result["rubriek"] = gekozen.where(gekozen.notna(), result["rubriek_voorstel"])
    result["rubriek_bron"] = np.where(gekozen.notna(), "vastgelegd", "voorstel")

    result["grondslag_aangifte"] = [
        grondslag * grondslag_teken(code)
        for grondslag, code in zip(result["grondslag_grootboek"], result["rubriek"])
    ]
    result["btw_aangifte"] = [
        btw * btw_teken(code) if pd.notna(btw) else 0.0
        for btw, code in zip(result["btw_grootboek"], result["rubriek"])
    ]
    return result


def build_rubric_summary(usage_met_rubriek: pd.DataFrame, aangifte: dict[str, float] | None = None) -> pd.DataFrame:
    """Tel op per aangifterubriek en vergelijk met de ingediende aangifte."""
    kolommen = [
        "rubriek",
        "omschrijving",
        "aantal_regels",
        "grondslag_volgens_xaf",
        "btw_volgens_xaf",
        "btw_volgens_aangifte",
        "verschil",
        "status",
    ]
    if usage_met_rubriek.empty:
        return pd.DataFrame(columns=kolommen)

    aangifte = aangifte or {}
    samenvatting = (
        usage_met_rubriek.groupby("rubriek", dropna=False)
        .agg(
            aantal_regels=("aantal_regels", "sum"),
            grondslag_volgens_xaf=("grondslag_aangifte", "sum"),
            btw_volgens_xaf=("btw_aangifte", "sum"),
        )
        .reset_index()
    )
    samenvatting["omschrijving"] = samenvatting["rubriek"].map(lambda code: rubriek(code).omschrijving)
    samenvatting["btw_volgens_aangifte"] = samenvatting["rubriek"].map(
        lambda code: float(aangifte.get(code, 0.0) or 0.0)
    )
    # Het verschil behoudt zijn teken: een te lage en een te hoge aangifte
    # mogen elkaar niet opheffen.
    samenvatting["verschil"] = samenvatting["btw_volgens_xaf"] - samenvatting["btw_volgens_aangifte"]

    def status(rij: pd.Series) -> str:
        if not rubriek(rij["rubriek"]).heeft_btw:
            return "Alleen grondslag"
        if rij["btw_volgens_aangifte"] == 0:
            return "Geen aangifte ingevuld"
        return "Sluit aan" if abs(rij["verschil"]) < AFRONDINGSMARGE_EURO else "Verschil"

    samenvatting["status"] = samenvatting.apply(status, axis=1)

    # Sorteer op de volgorde van het aangifteformulier, met het onbekende blok
    # aan het eind.
    volgorde = {code: index for index, code in enumerate(RUBRIEK_PER_CODE)}
    samenvatting["_volgorde"] = samenvatting["rubriek"].map(lambda code: volgorde.get(code, 999))
    return samenvatting.sort_values("_volgorde")[kolommen].reset_index(drop=True)


def build_vat_position(samenvatting: pd.DataFrame) -> dict[str, float]:
    """Bereken de netto btw-positie volgens de auditfile.

    Af te dragen omzetbelasting minus voorbelasting. Rubrieken die niet konden
    worden ingedeeld tellen niet mee; hun bedrag wordt apart teruggegeven zodat
    de tool kan waarschuwen in plaats van stilzwijgend af te ronden.
    """
    if samenvatting.empty:
        return {"af_te_dragen": 0.0, "voorbelasting": 0.0, "netto": 0.0, "niet_ingedeeld": 0.0}

    btw = samenvatting.set_index("rubriek")["btw_volgens_xaf"]
    af_te_dragen = float(btw.reindex(AFDRACHT_CODES).fillna(0).sum())
    voorbelasting = float(btw.reindex(VOORBELASTING_CODES).fillna(0).sum())
    niet_ingedeeld = float(btw.get(ONBEKEND, 0.0))
    return {
        "af_te_dragen": af_te_dragen,
        "voorbelasting": voorbelasting,
        "netto": af_te_dragen - voorbelasting,
        "niet_ingedeeld": niet_ingedeeld,
    }


# --- Aansluiting met het grootboek ------------------------------------------


def btw_grootboekrekeningen(af: Auditfile) -> list[str]:
    """De btw-rekeningen zoals de btw-codetabel ze zelf aanwijst.

    Dat is betrouwbaarder dan zoeken op rekeningnummer of omschrijving: het
    bestand vertelt hier zelf op welke rekeningen de btw terechtkomt.
    """
    codes = af.vat_codes
    rekeningen: set[str] = set()
    for kolom in ["vatToPayAccID", "vatToClaimAccID"]:
        if kolom in codes.columns:
            rekeningen |= {waarde for waarde in codes[kolom].astype(str).str.strip() if waarde}
    return sorted(rekeningen)


def build_ledger_reconciliation(af: Auditfile) -> pd.DataFrame:
    """Sluit de btw volgens de boekingsregels aan op de btw-grootboekrekeningen.

    Twee onafhankelijke wegen naar hetzelfde bedrag: de som van de btw-bedragen
    op de boekingsregels, en de mutatie op de rekeningen die de btw-codetabel
    als btw-rekening aanwijst. Lopen ze uiteen, dan is er btw geboekt zonder
    btw-code of andersom.
    """
    kolommen = ["rekening", "omschrijving", "beginsaldo", "mutatie_boekjaar", "eindsaldo", "rol"]
    rekeningen = btw_grootboekrekeningen(af)
    if not rekeningen:
        return pd.DataFrame(columns=kolommen)

    te_betalen = {
        waarde for waarde in af.vat_codes["vatToPayAccID"].astype(str).str.strip() if waarde
    }
    te_vorderen = {
        waarde for waarde in af.vat_codes["vatToClaimAccID"].astype(str).str.strip() if waarde
    }

    def rol(rekening: str) -> str:
        if rekening in te_betalen and rekening in te_vorderen:
            return "Te betalen en te vorderen"
        if rekening in te_betalen:
            return "Te betalen"
        return "Te vorderen"

    saldo = af.saldo[af.saldo["rekening"].isin(rekeningen)].copy()
    saldo["rol"] = saldo["rekening"].map(rol)
    saldo = saldo.rename(columns={"accDesc": "omschrijving", "mutaties_boekjaar": "mutatie_boekjaar"})
    return saldo[kolommen].sort_values("rekening").reset_index(drop=True)


# Rekeningen die als liquide middelen gelden; nodig om een afdracht aan de
# Belastingdienst te herkennen.
_LIQUIDE_RGS = "BLim"
_LIQUIDE_OMSCHRIJVING = r"\bbank\b|\bkas\b|giro|rekening.courant bank|spaarrekening|kruisposten"


def _is_liquide(lines: pd.DataFrame) -> pd.Series:
    op_rgs = lines["RGScode"].astype(str).str.startswith(_LIQUIDE_RGS)
    op_naam = lines["accDesc"].astype(str).str.contains(
        _LIQUIDE_OMSCHRIJVING, case=False, na=False, regex=True
    )
    is_balans = lines["accTp"].astype(str).str.upper().eq("B")
    return (op_rgs | op_naam) & is_balans


def build_vat_ledger_flow(af: Auditfile, samenvatting: pd.DataFrame) -> pd.DataFrame:
    """Btw-rondrekening: verklaar het verloop van de btw-rekeningen.

    Dit is de rondrekening zoals die in de praktijk wordt gemaakt::

        beginsaldo
        + btw uit facturen (boekingen waarin ook een btw-code voorkomt)
        + afdrachten en teruggaven (boekingen tegen een liquide middelenrekening)
        + overige mutaties (correcties, suppleties, herrubriceringen)
        = eindsaldo

    De regel "overige mutaties" is het interessantste getal van het overzicht:
    daar zit wat niet uit de facturatie of uit de betalingen volgt.

    Alle bedragen staan als grootboeksaldo, dus een schuld aan de Belastingdienst
    is negatief (credit).
    """
    kolommen = ["post", "bedrag", "aantal_regels", "toelichting"]
    rekeningen = btw_grootboekrekeningen(af)
    if not rekeningen or af.lines.empty:
        return pd.DataFrame(columns=kolommen)

    lines = af.lines
    op_btw_rekening = lines["line_accID"].isin(rekeningen)

    # Transacties waarin ergens een btw-code voorkomt: dat is de facturatiestroom.
    heeft_code = (lines["vat_vatID"] != "") | (lines["line_vatID"] != "")
    transactie_sleutel = lines["tx_jrnID"].astype(str) + "\x1f" + lines["tx_nr"].astype(str)
    transacties_met_code = set(transactie_sleutel[heeft_code])
    transacties_met_liquide = set(transactie_sleutel[_is_liquide(lines)])

    btw_regels_op_rekening = lines[op_btw_rekening].copy()
    sleutel = transactie_sleutel[op_btw_rekening]
    uit_facturen = sleutel.isin(transacties_met_code)
    via_liquide = sleutel.isin(transacties_met_liquide) & ~uit_facturen

    beginsaldo = float(
        af.saldo.loc[af.saldo["rekening"].isin(rekeningen), "beginsaldo"].sum()
    )
    eindsaldo = float(
        af.saldo.loc[af.saldo["rekening"].isin(rekeningen), "eindsaldo"].sum()
    )

    facturen = btw_regels_op_rekening[uit_facturen]
    betalingen = btw_regels_op_rekening[via_liquide]
    overig = btw_regels_op_rekening[~uit_facturen & ~via_liquide]

    posten = [
        {
            "post": "Beginsaldo btw-rekeningen",
            "bedrag": beginsaldo,
            "aantal_regels": None,
            "toelichting": "Stand aan het begin van het boekjaar; credit is een schuld aan de Belastingdienst.",
        },
        {
            "post": "Btw uit facturatie",
            "bedrag": float(facturen["bedrag"].sum()),
            "aantal_regels": len(facturen),
            "toelichting": "Mutaties op de btw-rekeningen in boekingen waarin ook een btw-code voorkomt.",
        },
        {
            "post": "Afdrachten en teruggaven",
            "bedrag": float(betalingen["bedrag"].sum()),
            "aantal_regels": len(betalingen),
            "toelichting": "Mutaties in boekingen die ook een bank- of kasrekening raken.",
        },
        {
            "post": "Overige mutaties",
            "bedrag": float(overig["bedrag"].sum()),
            "aantal_regels": len(overig),
            "toelichting": "Wat niet uit de facturatie en niet uit de betalingen volgt: "
            "correcties, herrubriceringen en mogelijke suppleties. Beoordeel deze post.",
        },
        {
            "post": "Eindsaldo btw-rekeningen",
            "bedrag": eindsaldo,
            "aantal_regels": None,
            "toelichting": "Stand aan het einde van het boekjaar; vergelijk met de nog te betalen btw over het laatste tijdvak.",
        },
    ]

    # Aansluiting van de facturatiestroom op de btw-codes: twee onafhankelijke
    # wegen naar hetzelfde bedrag.
    positie = build_vat_position(samenvatting)
    volgens_codes = -positie["netto"]  # als grootboeksaldo: een schuld is credit
    volgens_facturen = float(facturen["bedrag"].sum())
    posten.append(
        {
            "post": "Controle: btw uit facturatie tegenover de btw-codes",
            "bedrag": volgens_facturen - volgens_codes,
            "aantal_regels": None,
            "toelichting": "Verschil tussen de mutatie op de btw-rekeningen uit facturatie en "
            "de netto btw die uit de btw-codes volgt. Een verschil wijst op btw die "
            "zonder code is geboekt, of op een code zonder tegenboeking.",
        }
    )
    verloop = pd.DataFrame(posten, columns=kolommen)
    # Nullable integer: posten zonder regelaantal blijven leeg in plaats van
    # "None" te tonen.
    verloop["aantal_regels"] = verloop["aantal_regels"].astype("Int64")
    return verloop


# --- Anomalieën -------------------------------------------------------------


def build_vat_anomalies(af: Auditfile, usage_met_rubriek: pd.DataFrame | None = None) -> pd.DataFrame:
    """Signaleer btw-boekingen die opvallen.

    Elke regel in de uitkomst is een signaal met een reden en, waar mogelijk,
    het bedrag dat ermee gemoeid is. Een signaal is geen fout: het is iets om
    naar te kijken.
    """
    kolommen = ["signaal", "aantal_regels", "bedrag", "toelichting"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    signalen: list[dict] = []
    regels = btw_regels(af)

    def voeg_toe(signaal: str, selectie: pd.DataFrame, toelichting: str, bedragkolom: str = "bedrag") -> None:
        if selectie.empty:
            return
        signalen.append(
            {
                "signaal": signaal,
                "aantal_regels": len(selectie),
                "bedrag": float(selectie[bedragkolom].sum()),
                "toelichting": toelichting,
            }
        )

    # 1. Btw-bedrag dat niet past bij grondslag maal percentage. Een veelvoorkomende
    #    verklaring is dat de btw-code aan een bedrag inclusief btw hangt; dat wordt
    #    apart gemeld, want dat is geen fout maar een boekingswijze.
    if not regels.empty:
        met_percentage = regels[regels["vat_vatPerc"].notna() & (regels["vat_vatPerc"] > 0)].copy()
        if not met_percentage.empty:
            tarief = met_percentage["vat_vatPerc"] / 100.0
            verwacht_exclusief = met_percentage["bedrag"] * tarief
            verwacht_inclusief = met_percentage["bedrag"] * tarief / (1 + tarief)
            marge = np.maximum(AFRONDINGSMARGE_EURO, verwacht_exclusief.abs() * AFRONDINGSMARGE_RELATIEF)

            past_exclusief = (met_percentage["btw_bedrag"] - verwacht_exclusief).abs() <= marge
            past_inclusief = (met_percentage["btw_bedrag"] - verwacht_inclusief).abs() <= marge

            voeg_toe(
                "Grondslag lijkt inclusief btw geboekt",
                met_percentage[~past_exclusief & past_inclusief],
                "Op deze regels past het btw-bedrag bij een grondslag inclusief btw. "
                "Dat is geen fout, maar de grondslag in de rubriekentelling is dan te "
                "hoog: die hoort exclusief btw te zijn.",
                bedragkolom="btw_bedrag",
            )
            voeg_toe(
                "Btw-bedrag past niet bij grondslag maal percentage",
                met_percentage[~past_exclusief & ~past_inclusief],
                "Het geboekte btw-bedrag wijkt meer dan de afrondingsmarge af van "
                "grondslag maal percentage, ook wanneer de grondslag inclusief btw "
                "zou zijn. Beoordeel deze regels afzonderlijk.",
                bedragkolom="btw_bedrag",
            )

    # 2. Omzet zonder btw-code.
    is_omzet = lines["accTp"].astype(str).str.upper().eq("P") & (lines["bedrag"] < 0)
    zonder_code = (lines["vat_vatID"] == "") & (lines["line_vatID"] == "")
    voeg_toe(
        "Omzetboeking zonder btw-code",
        lines[is_omzet & zonder_code],
        "Opbrengstboekingen zonder btw-code. Beoordeel of dit vrijgestelde of "
        "verlegde omzet is, of dat een code ontbreekt.",
    )

    # 3. Kosten zonder btw-code, met uitzondering van posten waar dat normaal is.
    zonder_btw_normaal = r"loon|salaris|sociale lasten|pensioen|afschrijving|rente|belasting|dividend|verzekering"
    is_kosten = lines["accTp"].astype(str).str.upper().eq("P") & (lines["bedrag"] > 0)
    uitgezonderd = lines["accDesc"].astype(str).str.contains(zonder_btw_normaal, case=False, na=False, regex=True)
    voeg_toe(
        "Kostenboeking zonder btw-code",
        lines[is_kosten & zonder_code & ~uitgezonderd],
        "Kostenboekingen zonder btw-code, buiten de posten waar dat gebruikelijk "
        "is zoals lonen, afschrijvingen en rente. Mogelijk is voorbelasting "
        "misgelopen.",
    )

    # 4. Btw geboekt op een btw-rekening zonder btw-code op de regel.
    btw_rekeningen = btw_grootboekrekeningen(af)
    if btw_rekeningen:
        op_btw_rekening = lines["line_accID"].isin(btw_rekeningen)
        voeg_toe(
            "Boeking op een btw-rekening zonder btw-code",
            lines[op_btw_rekening & zonder_code],
            "Mutaties op de btw-rekeningen zonder btw-code. Dit zijn doorgaans "
            "de afdracht aan de Belastingdienst en correctieboekingen; "
            "controleer of daar ook een suppletie tussen zit.",
        )

    # 5. Eén btw-code met meerdere tarieven binnen een afdrachtrubriek. Bij
    #    voorbelasting is dat normaal: één inkoopcode dekt daar alle tarieven.
    #    Bij een omzetrubriek betekent het dat 1a en 1b door elkaar lopen.
    if usage_met_rubriek is not None and not usage_met_rubriek.empty:
        meerdere = usage_met_rubriek[
            (usage_met_rubriek["percentages"].str.count(",") >= 1)
            & usage_met_rubriek["rubriek"].isin(AFDRACHT_CODES)
        ]
        if not meerdere.empty:
            signalen.append(
                {
                    "signaal": "Btw-code met meerdere tarieven in een afdrachtrubriek",
                    "aantal_regels": int(meerdere["aantal_regels"].sum()),
                    "bedrag": float(meerdere["btw_grootboek"].sum()),
                    "toelichting": "Deze codes dekken meer dan één tarief terwijl ze in een rubriek vallen die per tarief wordt aangegeven: "
                    + "; ".join(
                        f"{code} ({percentages})"
                        for code, percentages in zip(meerdere["btw_code"], meerdere["percentages"])
                    )
                    + ". De verdeling over 1a, 1b en 1c is daardoor niet zuiver uit de codes af te leiden.",
                }
            )

        # 6. Codes die niet aan een rubriek konden worden gekoppeld.
        niet_ingedeeld = usage_met_rubriek[usage_met_rubriek["rubriek"] == ONBEKEND]
        if not niet_ingedeeld.empty:
            signalen.append(
                {
                    "signaal": "Btw-code zonder aangifterubriek",
                    "aantal_regels": int(niet_ingedeeld["aantal_regels"].sum()),
                    "bedrag": float(niet_ingedeeld["btw_grootboek"].sum()),
                    "toelichting": "Deze codes tellen niet mee in de netto btw-positie: "
                    + ", ".join(niet_ingedeeld["btw_code"])
                    + ". Wijs ze handmatig een rubriek toe.",
                }
            )

    # 7. Btw-bedrag geboekt zonder grondslag.
    if not regels.empty:
        zonder_grondslag = regels[(regels["bedrag"].abs() < 0.005) & (regels["btw_bedrag"].abs() >= 0.005)]
        voeg_toe(
            "Btw zonder grondslag",
            zonder_grondslag,
            "Regels met een btw-bedrag maar zonder bedrag om btw over te berekenen.",
            bedragkolom="btw_bedrag",
        )

    # 8. Btw op posten waar de aftrek beperkt of uitgesloten kan zijn.
    beperkt = r"representat|relatiegeschenk|horeca|restaurant|kantine|personeelsfeest|personeelsuitje"
    if not regels.empty:
        aandacht = regels[regels["accDesc"].astype(str).str.contains(beperkt, case=False, na=False, regex=True)]
        voeg_toe(
            "Btw op posten met mogelijk beperkte aftrek",
            aandacht,
            "Op representatie, horeca en personeelsvoorzieningen kan de aftrek "
            "beperkt of uitgesloten zijn (Besluit uitsluiting aftrek omzetbelasting 1968). "
            "Beoordeel of een correctie nodig is.",
            bedragkolom="btw_bedrag",
        )

    if not signalen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(signalen, columns=kolommen)


def build_vat_drilldown(af: Auditfile, btw_code: str | None = None) -> pd.DataFrame:
    """Alle boekingsregels achter een btw-code, of achter alle codes."""
    regels = btw_regels(af)
    kolommen = [
        "btw_code",
        "datum",
        "periode",
        "journaal",
        "transactie",
        "rekening",
        "rekeningomschrijving",
        "omschrijving",
        "relatie",
        "grondslag",
        "percentage",
        "btw_bedrag",
        "verwachte_btw",
        "afwijking",
        "documentreferentie",
    ]
    if regels.empty:
        return pd.DataFrame(columns=kolommen)

    if btw_code is not None:
        regels = regels[regels["btw_code"].astype(str) == str(btw_code)]
        if regels.empty:
            return pd.DataFrame(columns=kolommen)

    resultaat = regels.copy()
    resultaat["verwachte_btw"] = np.where(
        resultaat["vat_vatPerc"].notna(),
        resultaat["bedrag"] * resultaat["vat_vatPerc"].fillna(0) / 100.0,
        np.nan,
    )
    resultaat["afwijking"] = resultaat["btw_bedrag"] - resultaat["verwachte_btw"]
    resultaat["documentreferentie"] = resultaat["line_docRef"].where(
        resultaat["line_docRef"] != "", resultaat["line_invRef"]
    )

    relaties = af.relations.set_index("custSupID")["custSupName"].to_dict() if not af.relations.empty else {}
    resultaat["relatie"] = resultaat["line_custSupID"].map(relaties).fillna(resultaat["line_custSupID"])

    resultaat = resultaat.rename(
        columns={
            "line_accID": "rekening",
            "accDesc": "rekeningomschrijving",
            "line_desc": "omschrijving",
            "tx_jrn_desc": "journaal",
            "tx_nr": "transactie",
            "bedrag": "grondslag",
            "vat_vatPerc": "percentage",
        }
    )
    return resultaat[kolommen].sort_values(["btw_code", "datum", "transactie"]).reset_index(drop=True)
