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
