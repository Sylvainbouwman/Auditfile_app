"""Jaar-op-jaar vergelijking van twee auditfiles."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .controls import rgs_rubriek
from .model import SALDO_COLUMNS, Auditfile
from .parsing import ensure_columns

VERGELIJKING_COLUMNS = [
    "rekening",
    "accDesc",
    "accTp",
    "RGScode",
    "RGS-rubriek",
    "beginsaldo_vorig",
    "mutatie_vorig",
    "eindsaldo_vorig",
    "beginsaldo_huidig",
    "mutatie_huidig",
    "eindsaldo_huidig",
    "saldo_vorig",
    "saldo_huidig",
    "verschil_bedrag",
    "verschil_pct",
    "status",
    "regels_vorig",
    "regels_huidig",
]

# Een verschil van meer dan een kwart wordt als opvallend beschouwd. Dit sluit
# aan op de signaleringsdrempel uit de roadmap.
OPVALLEND_VERSCHIL_PCT = 25.0


def _hernoem(saldo: pd.DataFrame, achtervoegsel: str) -> pd.DataFrame:
    return saldo.rename(
        columns={
            "beginsaldo": f"beginsaldo_{achtervoegsel}",
            "mutaties_boekjaar": f"mutatie_{achtervoegsel}",
            "eindsaldo": f"eindsaldo_{achtervoegsel}",
            "saldo": f"saldo_{achtervoegsel}",
            "aantal_boekingsregels": f"regels_{achtervoegsel}",
            "accDesc": f"accDesc_{achtervoegsel}",
            "accTp": f"accTp_{achtervoegsel}",
            "RGScode": f"RGScode_{achtervoegsel}",
        }
    )


def compare_saldi(vorig: Auditfile | pd.DataFrame, huidig: Auditfile | pd.DataFrame) -> pd.DataFrame:
    """Vergelijk de saldi van twee boekjaren per grootboekrekening."""
    saldo_vorig = vorig.saldo if isinstance(vorig, Auditfile) else vorig
    saldo_huidig = huidig.saldo if isinstance(huidig, Auditfile) else huidig

    saldo_vorig = ensure_columns(saldo_vorig.copy(), SALDO_COLUMNS)
    saldo_huidig = ensure_columns(saldo_huidig.copy(), SALDO_COLUMNS)
    saldo_vorig["aanwezig_vorig"] = True
    saldo_huidig["aanwezig_huidig"] = True

    vergelijking = _hernoem(saldo_vorig, "vorig").merge(
        _hernoem(saldo_huidig, "huidig"), on="rekening", how="outer"
    )

    for kolom in ["aanwezig_vorig", "aanwezig_huidig"]:
        vergelijking[kolom] = vergelijking[kolom].fillna(False).astype(bool)

    numerieke_kolommen = [
        "beginsaldo_vorig",
        "mutatie_vorig",
        "eindsaldo_vorig",
        "saldo_vorig",
        "regels_vorig",
        "beginsaldo_huidig",
        "mutatie_huidig",
        "eindsaldo_huidig",
        "saldo_huidig",
        "regels_huidig",
    ]
    vergelijking = ensure_columns(vergelijking, numerieke_kolommen, default=0)
    for kolom in numerieke_kolommen:
        vergelijking[kolom] = pd.to_numeric(vergelijking[kolom], errors="coerce").fillna(0)

    # Stamgegevens komen bij voorkeur uit het huidige jaar; dat is het meest
    # actuele rekeningschema.
    for doel, bron_huidig, bron_vorig in (
        ("accDesc", "accDesc_huidig", "accDesc_vorig"),
        ("accTp", "accTp_huidig", "accTp_vorig"),
        ("RGScode", "RGScode_huidig", "RGScode_vorig"),
    ):
        vergelijking = ensure_columns(vergelijking, [bron_huidig, bron_vorig])
        huidige_waarde = vergelijking[bron_huidig].fillna("").astype(str)
        vorige_waarde = vergelijking[bron_vorig].fillna("").astype(str)
        vergelijking[doel] = huidige_waarde.where(huidige_waarde != "", vorige_waarde)

    vergelijking["RGS-rubriek"] = vergelijking["RGScode"].map(rgs_rubriek)
    vergelijking["verschil_bedrag"] = vergelijking["saldo_huidig"] - vergelijking["saldo_vorig"]
    # Een percentage bij een beginstand van nul zegt niets; dat blijft leeg in
    # plaats van oneindig of nul te worden.
    noemer = vergelijking["saldo_vorig"].abs()
    vergelijking["verschil_pct"] = np.where(
        noemer > 0.005, vergelijking["verschil_bedrag"] / noemer * 100, np.nan
    )
    vergelijking["status"] = np.select(
        [
            vergelijking["aanwezig_huidig"] & ~vergelijking["aanwezig_vorig"],
            vergelijking["aanwezig_vorig"] & ~vergelijking["aanwezig_huidig"],
        ],
        ["nieuw", "vervallen"],
        default="bestaand",
    )
    vergelijking["verschil_abs"] = vergelijking["verschil_bedrag"].abs()
    return (
        vergelijking.sort_values("verschil_abs", ascending=False)
        .drop(columns=["verschil_abs"])[VERGELIJKING_COLUMNS]
        .reset_index(drop=True)
    )


def build_rubriek_vergelijking(vergelijking: pd.DataFrame) -> pd.DataFrame:
    """Vat de vergelijking samen per RGS-rubriek.

    Een overzicht per rubriek laat sneller zien waar het jaar is veranderd dan
    een lijst van honderden rekeningen.
    """
    kolommen = ["RGS-rubriek", "aantal_rekeningen", "saldo_vorig", "saldo_huidig", "verschil_bedrag", "verschil_pct", "signaal"]
    if vergelijking.empty:
        return pd.DataFrame(columns=kolommen)

    met_rubriek = vergelijking[vergelijking["RGS-rubriek"] != ""].copy()
    if met_rubriek.empty:
        return pd.DataFrame(columns=kolommen)

    samenvatting = (
        met_rubriek.groupby("RGS-rubriek", dropna=False)
        .agg(
            aantal_rekeningen=("rekening", "size"),
            saldo_vorig=("saldo_vorig", "sum"),
            saldo_huidig=("saldo_huidig", "sum"),
        )
        .reset_index()
    )
    samenvatting["verschil_bedrag"] = samenvatting["saldo_huidig"] - samenvatting["saldo_vorig"]
    noemer = samenvatting["saldo_vorig"].abs()
    samenvatting["verschil_pct"] = np.where(
        noemer > 0.005, samenvatting["verschil_bedrag"] / noemer * 100, np.nan
    )
    samenvatting["signaal"] = np.where(
        samenvatting["verschil_pct"].abs() >= OPVALLEND_VERSCHIL_PCT,
        f"Wijkt meer dan {OPVALLEND_VERSCHIL_PCT:.0f}% af van vorig jaar",
        "",
    )
    return samenvatting.sort_values("RGS-rubriek")[kolommen].reset_index(drop=True)


def build_opvallende_verschillen(vergelijking: pd.DataFrame, minimaal_bedrag: float = 1000.0) -> pd.DataFrame:
    """Rekeningen die zowel in bedrag als in percentage opvallen."""
    if vergelijking.empty:
        return vergelijking

    groot_genoeg = vergelijking["verschil_bedrag"].abs() >= minimaal_bedrag
    sterk_gewijzigd = vergelijking["verschil_pct"].abs() >= OPVALLEND_VERSCHIL_PCT
    nieuw_of_vervallen = vergelijking["status"].isin(["nieuw", "vervallen"])
    return vergelijking[groot_genoeg & (sterk_gewijzigd | nieuw_of_vervallen)].reset_index(drop=True)


# --- Horen deze twee bestanden bij elkaar? ----------------------------------

# Dezelfde eerste drie kolommen als de bevindingen van integrity.py, zodat de app
# ze op dezelfde manier toont en kleurt. Een bedrag of aantal hoort hier niet bij:
# deze controles gaan over de vraag of de bestanden bij elkaar horen, niet over
# een saldo.
PAAR_COLUMNS = ["ernst", "controle", "bevinding"]

# Verschillen kleiner dan een halve cent zijn afrondingsruis.
TOLERANTIE = 0.005


def _paar_bevinding(ernst: str, controle: str, bevinding: str) -> dict:
    return {"ernst": ernst, "controle": controle, "bevinding": bevinding}


def _jaar(waarde: str) -> int | None:
    """Het boekjaar als getal, of niets wanneer het geen jaartal is."""
    getal = pd.to_numeric(str(waarde).strip(), errors="coerce")
    return None if pd.isna(getal) else int(getal)


def controleer_bestandenpaar(vorig: Auditfile, huidig: Auditfile) -> pd.DataFrame:
    """Toets of de twee auditfiles bij elkaar horen.

    De vergelijking zelf rekent alles door zonder te vragen of de bestanden
    samenhoren. Twee auditfiles van verschillende ondernemingen leveren dan een
    plausibel ogende jaarvergelijking op, en dat is een gevaarlijker fout dan een
    lege uitkomst. Deze controle gaat daarom vooraf aan de cijfers.

    De ernst volgt de vraag of de uitkomst nog te gebruiken is: een andere
    onderneming of een andere valuta maakt de vergelijking zinloos (kritiek), een
    gat tussen de boekjaren maakt haar minder bruikbaar maar niet onbruikbaar
    (waarschuwing).
    """
    from .integrity import IN_ORDE, KRITIEK, NIET_MOGELIJK, WAARSCHUWING

    bevindingen: list[dict] = []

    controle = "Zelfde onderneming"
    identiteit_vorig = vorig.dossier_identiteit
    identiteit_huidig = huidig.dossier_identiteit
    if not identiteit_vorig or not identiteit_huidig:
        bevindingen.append(
            _paar_bevinding(
                NIET_MOGELIJK,
                controle,
                "Een van de bestanden vermeldt geen btw-nummer, KvK-nummer of naam, "
                "waardoor niet is vast te stellen of het om dezelfde onderneming gaat.",
            )
        )
    elif identiteit_vorig != identiteit_huidig:
        naam_vorig = vorig.bedrijfsnaam or "onbekend"
        naam_huidig = huidig.bedrijfsnaam or "onbekend"
        bevindingen.append(
            _paar_bevinding(
                KRITIEK,
                controle,
                f"De bestanden horen bij verschillende ondernemingen: {naam_vorig} "
                f"tegenover {naam_huidig}. De vergelijking is niet zinvol.",
            )
        )
    else:
        bevindingen.append(
            _paar_bevinding(IN_ORDE, controle, "Beide bestanden horen bij dezelfde onderneming.")
        )

    controle = "Twee verschillende bestanden"
    if vorig.vingerafdruk and vorig.vingerafdruk == huidig.vingerafdruk:
        bevindingen.append(
            _paar_bevinding(
                KRITIEK,
                controle,
                "Beide keren is hetzelfde bestand geladen. Elke vergelijking komt "
                "daardoor op nul uit.",
            )
        )
    else:
        bevindingen.append(
            _paar_bevinding(IN_ORDE, controle, "Er zijn twee verschillende bestanden geladen.")
        )

    controle = "Zelfde valuta"
    if not vorig.valuta or not huidig.valuta:
        bevindingen.append(
            _paar_bevinding(NIET_MOGELIJK, controle, "Een van de bestanden vermeldt geen valuta.")
        )
    elif vorig.valuta != huidig.valuta:
        bevindingen.append(
            _paar_bevinding(
                KRITIEK,
                controle,
                f"De bestanden staan in verschillende valuta ({vorig.valuta} en "
                f"{huidig.valuta}). Bedragen zijn niet vergelijkbaar en niet op te tellen.",
            )
        )
    else:
        bevindingen.append(
            _paar_bevinding(IN_ORDE, controle, f"Beide bestanden staan in {huidig.valuta}.")
        )

    controle = "Aansluitende boekjaren"
    jaar_vorig = _jaar(vorig.boekjaar)
    jaar_huidig = _jaar(huidig.boekjaar)
    if jaar_vorig is None or jaar_huidig is None:
        bevindingen.append(
            _paar_bevinding(NIET_MOGELIJK, controle, "Een van de bestanden vermeldt geen boekjaar.")
        )
    elif jaar_huidig == jaar_vorig:
        bevindingen.append(
            _paar_bevinding(
                KRITIEK, controle, f"Beide bestanden hebben boekjaar {jaar_huidig}."
            )
        )
    elif jaar_huidig < jaar_vorig:
        bevindingen.append(
            _paar_bevinding(
                KRITIEK,
                controle,
                f"Het bestand voor het huidige jaar heeft boekjaar {jaar_huidig} en dat "
                f"voor vorig jaar {jaar_vorig}. De bestanden zijn verwisseld.",
            )
        )
    elif jaar_huidig - jaar_vorig > 1:
        ontbrekend = jaar_huidig - jaar_vorig - 1
        bevindingen.append(
            _paar_bevinding(
                WAARSCHUWING,
                controle,
                f"Tussen de boekjaren {jaar_vorig} en {jaar_huidig} zitten {ontbrekend} "
                "jaar die niet zijn geladen. De beginbalans van het huidige jaar sluit "
                "dan niet aan op de eindbalans van het vorige.",
            )
        )
    else:
        bevindingen.append(
            _paar_bevinding(
                IN_ORDE, controle, f"Boekjaar {jaar_huidig} volgt op {jaar_vorig}."
            )
        )

    controle = "Periodes overlappen niet"
    start_huidig = str(huidig.header.get("startDate", "")).strip()
    eind_vorig = str(vorig.header.get("endDate", "")).strip()
    if not start_huidig or not eind_vorig:
        bevindingen.append(
            _paar_bevinding(
                NIET_MOGELIJK,
                controle,
                "Een van de bestanden vermeldt geen begin- of einddatum.",
            )
        )
    elif start_huidig <= eind_vorig:
        bevindingen.append(
            _paar_bevinding(
                KRITIEK,
                controle,
                f"Het huidige boekjaar begint op {start_huidig}, terwijl het vorige pas "
                f"op {eind_vorig} eindigt. De periodes overlappen, dus boekingen worden "
                "dubbel meegeteld.",
            )
        )
    else:
        bevindingen.append(
            _paar_bevinding(
                IN_ORDE,
                controle,
                f"Het vorige jaar eindigt op {eind_vorig}, het huidige begint op {start_huidig}.",
            )
        )

    return pd.DataFrame(bevindingen, columns=PAAR_COLUMNS)


# --- Jaarovergang -----------------------------------------------------------

JAAROVERGANG_COLUMNS = [
    "rekening",
    "accDesc",
    "RGScode",
    "eindsaldo_vorig",
    "beginsaldo_huidig",
    "verschil",
    "signaal",
]


def build_jaarovergang(vorig: Auditfile, huidig: Auditfile) -> pd.DataFrame:
    """Sluit de eindbalans van vorig jaar aan op de beginbalans van dit jaar.

    Alleen balansrekeningen: het resultaat van vorig jaar gaat via de
    resultaatbestemming naar het eigen vermogen en staat dus niet als beginsaldo
    op een resultaatrekening.

    Een verschil per rekening is niet altijd een fout. Bij de resultaatbestemming
    verschuift het resultaat binnen het eigen vermogen, en bij een omnummering
    verhuist een saldo naar een ander nummer. Wat wel moet kloppen is het totaal:
    de som van alle beginsaldi hoort gelijk te zijn aan de som van alle
    eindsaldi van vorig jaar.
    """
    balans_vorig = vorig.saldo[vorig.saldo["accTp"].astype(str).str.upper().eq("B")]
    balans_huidig = huidig.saldo[huidig.saldo["accTp"].astype(str).str.upper().eq("B")]
    if balans_vorig.empty and balans_huidig.empty:
        return pd.DataFrame(columns=JAAROVERGANG_COLUMNS)

    links = balans_vorig[["rekening", "accDesc", "RGScode", "eindsaldo"]].rename(
        columns={"eindsaldo": "eindsaldo_vorig"}
    )
    rechts = balans_huidig[["rekening", "accDesc", "RGScode", "beginsaldo"]].rename(
        columns={"beginsaldo": "beginsaldo_huidig"}
    )
    samen = links.merge(rechts, on="rekening", how="outer", suffixes=("_vorig", "_huidig"))
    for kolom in ["accDesc", "RGScode"]:
        huidige_waarde = samen[f"{kolom}_huidig"].fillna("").astype(str)
        vorige_waarde = samen[f"{kolom}_vorig"].fillna("").astype(str)
        samen[kolom] = huidige_waarde.where(huidige_waarde != "", vorige_waarde)
    for kolom in ["eindsaldo_vorig", "beginsaldo_huidig"]:
        samen[kolom] = pd.to_numeric(samen[kolom], errors="coerce").fillna(0.0)
    samen["verschil"] = samen["beginsaldo_huidig"] - samen["eindsaldo_vorig"]

    # Op het eigen vermogen hoort een verschil te staan: daar landt het
    # resultaat van vorig jaar. Dat is geen signaal maar de verklaring.
    eigen_vermogen = set(huidig.saldo.loc[_eigen_vermogen(huidig.saldo), "rekening"]) | set(
        vorig.saldo.loc[_eigen_vermogen(vorig.saldo), "rekening"]
    )

    def signaal(rij: pd.Series) -> str:
        if abs(rij["verschil"]) < TOLERANTIE:
            return ""
        if rij["rekening"] in eigen_vermogen:
            return "Resultaatbestemming eigen vermogen"
        if abs(rij["eindsaldo_vorig"]) < TOLERANTIE:
            return "Beginsaldo zonder eindsaldo vorig jaar"
        if abs(rij["beginsaldo_huidig"]) < TOLERANTIE:
            return "Eindsaldo vorig jaar niet overgenomen"
        return "Beginsaldo wijkt af van de eindstand"

    samen["signaal"] = samen.apply(signaal, axis=1)
    return (
        samen[JAAROVERGANG_COLUMNS]
        .sort_values("verschil", key=lambda reeks: reeks.abs(), ascending=False)
        .reset_index(drop=True)
    )


# Het eigen vermogen is de enige balanspost die tussen twee bestanden mag
# verschuiven zonder dat er een boeking tegenover staat: daar landt het
# resultaat van vorig jaar bij de bestemming.
EIGEN_VERMOGEN_RGS = "BEiv"
EIGEN_VERMOGEN_PATROON = (
    r"eigen vermogen|kapitaal|reserve|onverdeeld|winstsaldo|resultaat.*boekjaar|agio"
)


def _eigen_vermogen(saldo: pd.DataFrame) -> pd.Series:
    """Welke balansrekeningen horen tot het eigen vermogen?"""
    from .controls import _selecteer

    masker, _ = _selecteer(
        saldo, EIGEN_VERMOGEN_RGS, EIGEN_VERMOGEN_PATROON, rekeningtype="B"
    )
    return masker


def build_jaarovergang_verloop(vorig: Auditfile, huidig: Auditfile) -> pd.DataFrame:
    """De harde controle op de jaarovergang, met de resultaatbestemming erin.

    Het beginsaldo van dit jaar hoort per balansrekening gelijk te zijn aan het
    eindsaldo van vorig jaar. Op één post mag daarvan worden afgeweken: bij de
    resultaatbestemming verschuift het resultaat van vorig jaar naar het eigen
    vermogen, terwijl het in het vorige bestand nog op de resultaatrekeningen
    staat. De controle valt daarom in twee delen uiteen::

        buiten het eigen vermogen: beginbalans dit jaar = eindbalans vorig jaar
        het eigen vermogen zelf:   toename = het resultaat van vorig jaar

    Let op dat de totalen van beide balansen niet tegen elkaar zijn af te zetten:
    een sluitende beginbalans telt altijd op tot nul en de eindbalans van vorig
    jaar altijd tot het resultaat met omgekeerd teken. Die vergelijking zou dus
    altijd kloppen en niets aantonen; deze splitsing laat de aansluiting wel
    zien.
    """
    kolommen = ["post", "bedrag", "toelichting"]
    if vorig.saldo.empty and huidig.saldo.empty:
        return pd.DataFrame(columns=kolommen)

    is_balans_vorig = vorig.saldo["accTp"].astype(str).str.upper().eq("B")
    is_balans_huidig = huidig.saldo["accTp"].astype(str).str.upper().eq("B")
    ev_vorig = _eigen_vermogen(vorig.saldo)
    ev_huidig = _eigen_vermogen(huidig.saldo)

    eind_overig = float(vorig.saldo.loc[is_balans_vorig & ~ev_vorig, "eindsaldo"].sum())
    begin_overig = float(huidig.saldo.loc[is_balans_huidig & ~ev_huidig, "beginsaldo"].sum())
    eind_ev = float(vorig.saldo.loc[ev_vorig, "eindsaldo"].sum())
    begin_ev = float(huidig.saldo.loc[ev_huidig, "beginsaldo"].sum())
    resultaat = float(vorig.saldo.loc[~is_balans_vorig, "mutaties_boekjaar"].sum())

    jaar_vorig = vorig.boekjaar or "vorig jaar"
    jaar_huidig = huidig.boekjaar or "huidig jaar"
    posten = [
        {
            "post": f"Balans {jaar_vorig} buiten het eigen vermogen",
            "bedrag": eind_overig,
            "toelichting": "Som van de eindsaldi van de balansrekeningen, zonder het eigen vermogen.",
        },
        {
            "post": f"Beginbalans {jaar_huidig} buiten het eigen vermogen",
            "bedrag": begin_overig,
            "toelichting": "Dezelfde rekeningen aan het begin van dit jaar. Deze twee horen gelijk te zijn.",
        },
        {
            "post": "Verschil buiten het eigen vermogen",
            "bedrag": begin_overig - eind_overig,
            "toelichting": "Hoort nul te zijn. Blijft er iets staan, dan is een eindstand "
            "niet overgenomen of is er op de beginbalans gecorrigeerd.",
        },
        {
            "post": f"Eigen vermogen einde {jaar_vorig}",
            "bedrag": eind_ev,
            "toelichting": "Credit is een positief vermogen.",
        },
        {
            "post": f"Eigen vermogen begin {jaar_huidig}",
            "bedrag": begin_ev,
            "toelichting": "Hierin is het resultaat van vorig jaar bestemd.",
        },
        {
            "post": "Toename van het eigen vermogen",
            "bedrag": begin_ev - eind_ev,
            "toelichting": "Wat er bij de jaarovergang aan het eigen vermogen is toegevoegd.",
        },
        {
            "post": f"Resultaat {jaar_vorig}",
            "bedrag": resultaat,
            "toelichting": "Som van de mutaties op de resultaatrekeningen. Credit is winst; "
            "die winst hoort de toename van het eigen vermogen te verklaren.",
        },
        {
            "post": "Onverklaard in het eigen vermogen",
            "bedrag": (begin_ev - eind_ev) - resultaat,
            "toelichting": "Hoort nul te zijn. Blijft er iets staan, dan is er vermogen "
            "bijgekomen of onttrokken buiten het resultaat om: een storting, een "
            "dividend, een privéonttrekking of een stelselwijziging. Beoordeel dit.",
        },
    ]
    return pd.DataFrame(posten, columns=kolommen)


def jaarovergang_sluit_aan(verloop: pd.DataFrame, marge: float = 0.005) -> bool:
    """Sluit de jaarovergang aan? Beide verschillen moeten nul zijn."""
    if verloop.empty:
        return True
    te_toetsen = ("Verschil buiten het eigen vermogen", "Onverklaard in het eigen vermogen")
    bedragen = verloop.loc[verloop["post"].isin(te_toetsen), "bedrag"]
    return bool((bedragen.abs() < marge).all())
