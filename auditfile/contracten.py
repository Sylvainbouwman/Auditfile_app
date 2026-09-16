"""Contractregister voor lease- en huurverplichtingen.

Waarom dit bestaat
------------------
Een lopende huur- of leaseverplichting hoort in de regel niet als schuld op de
balans: de wederpartij heeft de toekomstige prestatie nog niet geleverd, dus is
er nog geen vordering of schuld die in het vermogen thuishoort. Wel hoort zij,
als de bedragen daarvoor materieel zijn, als "niet in de balans opgenomen
verplichting" in de toelichting bij de jaarrekening (art. 2:381 lid 1 BW; RJ
214 voor de rechtspersonen die daaronder vallen). Een auditfile ziet alleen de
geboekte kosten van dit boekjaar, niet de onderliggende overeenkomst en haar
resterende looptijd. De gebruiker legt het contract daarom zelf vast; de tool
telt op wat er per de balansdatum nog resteert.

Wat dit niet is
----------------
Geen contante-waardeberekening (de resterende termijnen worden niet
contant gemaakt) en geen juridische kwalificatie van het contract als
operationele of financiële lease. Dat blijft aan de gebruiker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .model import Auditfile

CONTRACT_COLUMNS = [
    "omschrijving",
    "jaarbedrag",
    "ingangsdatum",
    "einddatum",
    "resterende_maanden",
    "resterende_verplichting",
]


@dataclass(frozen=True)
class Contract:
    """Eén vastgelegd lease- of huurcontract, zoals de gebruiker het invoert."""

    omschrijving: str
    jaarbedrag: float
    ingangsdatum: date
    einddatum: date


def balansdatum(af: Auditfile) -> date | None:
    """De einddatum van het boekjaar, als peildatum voor de resterende looptijd.

    Zonder een geldige einddatum in het bestand is er geen peildatum en dus
    geen resterende verplichting te berekenen; de contracten blijven dan wel
    zichtbaar, maar zonder dat cijfer.
    """
    ruw = pd.to_datetime(af.header.get("endDate", ""), errors="coerce")
    if pd.isna(ruw):
        return None
    return pd.Timestamp(ruw).date()


def resterende_maanden(contract: Contract, peildatum: date) -> int:
    """Het aantal resterende hele maanden vanaf de peildatum tot de einddatum.

    Nul zodra het contract op de peildatum al is afgelopen; nooit negatief. Een
    contract dat vóór de peildatum is beëindigd draagt dus niets meer bij aan
    de opgetelde verplichting.
    """
    if peildatum >= contract.einddatum:
        return 0
    maanden = (contract.einddatum.year - peildatum.year) * 12 + (
        contract.einddatum.month - peildatum.month
    )
    if contract.einddatum.day < peildatum.day:
        maanden -= 1
    return max(maanden, 0)


def build_contractenoverzicht(
    contracten: list[Contract], peildatum: date | None
) -> pd.DataFrame:
    """De vastgelegde contracten met de resterende verplichting per de peildatum.

    Zonder peildatum (het boekjaar geeft geen geldige einddatum) blijven de
    twee laatste kolommen leeg: er is dan wel een contract, maar geen
    berekenbare resterende termijn.
    """
    if not contracten:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    rijen = []
    for contract in contracten:
        if peildatum is None:
            maanden = None
            verplichting = None
        else:
            maanden = resterende_maanden(contract, peildatum)
            verplichting = contract.jaarbedrag / 12.0 * maanden
        rijen.append(
            {
                "omschrijving": contract.omschrijving,
                "jaarbedrag": contract.jaarbedrag,
                # Als Timestamp, niet als date: zo krijgt de kolom een
                # datetime64-dtype en herkent de presentatielaag (formatting.py)
                # hem automatisch als datum.
                "ingangsdatum": pd.Timestamp(contract.ingangsdatum),
                "einddatum": pd.Timestamp(contract.einddatum),
                "resterende_maanden": maanden,
                "resterende_verplichting": verplichting,
            }
        )
    return pd.DataFrame(rijen, columns=CONTRACT_COLUMNS)


def totaal_resterende_verplichting(overzicht: pd.DataFrame) -> float:
    """De som van de resterende verplichting over alle contracten."""
    if overzicht.empty or "resterende_verplichting" not in overzicht:
        return 0.0
    return float(
        pd.to_numeric(overzicht["resterende_verplichting"], errors="coerce")
        .fillna(0.0)
        .sum()
    )


# --- Opslag: een Contract is voor de schijf een dict met ISO-datums ---------


def contract_naar_dict(contract: Contract) -> dict:
    """Een contract voor opslag: datums als ISO-tekst, JSON kent geen datum."""
    return {
        "omschrijving": contract.omschrijving,
        "jaarbedrag": contract.jaarbedrag,
        "ingangsdatum": contract.ingangsdatum.isoformat(),
        "einddatum": contract.einddatum.isoformat(),
    }


def contract_van_dict(ruw: dict) -> Contract | None:
    """Eén opgeslagen contract terug naar een ``Contract``, of ``None`` bij een
    onbruikbare rij. Een dossier van een oudere of handmatig bewerkte versie
    van het bestand mag zo'n rij niet laten crashen; hij wordt overgeslagen.
    """
    ingang = pd.to_datetime(ruw.get("ingangsdatum"), errors="coerce")
    eind = pd.to_datetime(ruw.get("einddatum"), errors="coerce")
    if pd.isna(ingang) or pd.isna(eind):
        return None
    try:
        jaarbedrag = float(ruw.get("jaarbedrag", 0.0))
    except (TypeError, ValueError):
        return None
    omschrijving = str(ruw.get("omschrijving", "")).strip()
    if not omschrijving:
        return None
    return Contract(
        omschrijving=omschrijving,
        jaarbedrag=jaarbedrag,
        ingangsdatum=pd.Timestamp(ingang).date(),
        einddatum=pd.Timestamp(eind).date(),
    )


def contracten_van_ruw(ruw: list[dict]) -> list[Contract]:
    """Alle bruikbare contracten uit de opgeslagen ruwe lijst."""
    contracten = [contract_van_dict(item) for item in ruw]
    return [contract for contract in contracten if contract is not None]
