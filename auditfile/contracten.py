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


# --- Aansluiting op de geboekte huur- en leasekosten --------------------------

# Dezelfde zoektermen als de periodieke controles op huur en lease; pacht valt er
# bewust buiten, want het register is voor lease- en huurcontracten.
HUURLEASE_PATROON = r"\bhuur\b|lease|leasing"

# Een verschil onder deze grens (in procenten van het bedrag volgens de
# contracten) meldt de tool niet. Bewust ruim: de geboekte kosten kunnen ook
# servicekosten of een afwijkende facturering bevatten die het register niet kent.
AANSLUITDREMPEL_PCT = 10.0

KOSTEN_ZONDER_CONTRACT = "Kosten zonder vastgelegd contract"
CONTRACT_ZONDER_KOSTEN = "Contract zonder geboekte kosten"
VERSCHIL = "Verschil met de contracten"
AANSLUITEND = "Aansluitend"
NIET_MOGELIJK_STATUS = "Niet mogelijk"
GEEN_KOSTEN_EN_CONTRACTEN = "Geen kosten en geen contracten"


@dataclass(frozen=True)
class Contractaansluiting:
    """Wat de contracten voor dit boekjaar zeggen naast wat er is geboekt.

    ``verwacht`` is wat de vastgelegde contracten over de dagen van het boekjaar
    aan kosten opleveren; ``geboekt`` is het saldo van de rekeningen die op
    omschrijving als huur of lease worden herkend. Het verschil is een signaal
    en geen oordeel: de tool weet niet of de geboekte kosten bij die contracten
    horen.
    """

    status: str
    geboekt: float
    verwacht: float | None
    verschil: float | None
    rekeningen: tuple[str, ...]
    methode: str
    aantal_contracten: int
    toelichting: str


def _boekjaar(af: Auditfile) -> tuple[date, date] | None:
    """Begin- en einddatum van het boekjaar, of ``None`` als een van beide ontbreekt."""
    begin = pd.to_datetime(af.header.get("startDate", ""), errors="coerce")
    eind = pd.to_datetime(af.header.get("endDate", ""), errors="coerce")
    if pd.isna(begin) or pd.isna(eind) or eind < begin:
        return None
    return pd.Timestamp(begin).date(), pd.Timestamp(eind).date()


def verwachte_kosten(contract: Contract, begin: date, eind: date) -> float:
    """De kosten van één contract over het boekjaar, naar dagen toegerekend.

    De einddatum van een contract geldt als de eerste dag waarop het niet meer
    loopt, dezelfde lezing als bij ``resterende_maanden``. Een boekjaar van
    twaalf maanden geeft zo precies het jaarbedrag bij een contract dat het hele
    jaar loopt.
    """
    boekjaar_dagen = (eind - begin).days + 1
    overlap_begin = max(contract.ingangsdatum, begin)
    overlap_eind = min(contract.einddatum, date.fromordinal(eind.toordinal() + 1))
    overlap_dagen = (overlap_eind - overlap_begin).days
    if overlap_dagen <= 0 or boekjaar_dagen <= 0:
        return 0.0
    boekjaar_maanden = max(round(boekjaar_dagen / 30.4375), 1)
    return contract.jaarbedrag / 12.0 * boekjaar_maanden * overlap_dagen / boekjaar_dagen


def build_contractaansluiting(
    af: Auditfile, contracten: list[Contract]
) -> Contractaansluiting:
    """Leg de contracten naast de geboekte huur- en leasekosten van het boekjaar.

    Een operationele lease die niet als verplichting zichtbaar is, wordt niet
    gedetecteerd: dat vraagt een beoordeling van het contract zelf (zie de
    module-docstring) en blijft een bewuste beperking.
    """
    from .controls import _selecteer

    geboekt = 0.0
    rekeningen: tuple[str, ...] = ()
    methode = "geen treffers"
    if not af.saldo.empty:
        masker, methode = _selecteer(
            af.saldo, None, HUURLEASE_PATROON, rekeningtype="P"
        )
        geboekt = float(af.saldo.loc[masker, "mutaties_boekjaar"].sum())
        rekeningen = tuple(str(r) for r in af.saldo.loc[masker, "rekening"])

    aantal = len(contracten)

    def maak(status: str, verwacht=None, verschil=None, toelichting="") -> Contractaansluiting:
        return Contractaansluiting(
            status, geboekt, verwacht, verschil, rekeningen, methode, aantal, toelichting
        )

    if not rekeningen and aantal == 0:
        return maak(GEEN_KOSTEN_EN_CONTRACTEN)
    if aantal == 0:
        return maak(
            KOSTEN_ZONDER_CONTRACT,
            toelichting=(
                "Er zijn huur- of leasekosten geboekt, maar er is geen contract "
                "vastgelegd in het contractregister. Beoordeel of er een "
                "meerjarige verplichting loopt die in de toelichting hoort."
            ),
        )

    boekjaar = _boekjaar(af)
    if boekjaar is None:
        return maak(
            NIET_MOGELIJK_STATUS,
            toelichting=(
                "Het auditfile geeft geen bruikbare begin- en einddatum van het "
                "boekjaar, dus de contracten zijn niet naast de kosten te leggen."
            ),
        )

    verwacht = sum(verwachte_kosten(contract, *boekjaar) for contract in contracten)
    verschil = geboekt - verwacht

    if not rekeningen:
        return maak(
            CONTRACT_ZONDER_KOSTEN,
            verwacht,
            verschil,
            "Er zijn contracten vastgelegd die in dit boekjaar kosten horen op te "
            "leveren, maar er zijn geen rekeningen herkend als huur of lease. "
            "Controleer of de kosten onder een andere omschrijving zijn geboekt.",
        )
    if verwacht <= 0.0 and geboekt > 0.0:
        return maak(
            KOSTEN_ZONDER_CONTRACT,
            verwacht,
            verschil,
            "Er zijn huur- of leasekosten geboekt, maar geen van de vastgelegde "
            "contracten loopt in dit boekjaar.",
        )
    drempel = abs(verwacht) * AANSLUITDREMPEL_PCT / 100.0
    if abs(verschil) <= drempel:
        return maak(AANSLUITEND, verwacht, verschil)
    richting = "meer" if verschil > 0 else "minder"
    return maak(
        VERSCHIL,
        verwacht,
        verschil,
        f"Er is {richting} geboekt dan de vastgelegde contracten over dit "
        "boekjaar opleveren. Mogelijke oorzaken: een contract dat ontbreekt of "
        "afwijkt in het register, servicekosten of btw in de geboekte kosten, of "
        "een afwijkende facturering.",
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
