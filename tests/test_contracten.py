"""Tests bij het contractregister voor lease- en huurverplichtingen.

De koppeling met de auditfile zelf is dun (alleen de einddatum van het
boekjaar als peildatum); de meeste tests werken daarom direct met ``Contract``
en de eigen rekenlogica, zonder een synthetisch auditfile op te bouwen.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from auditfile import contracten as ct
from auditfile.model import Auditfile


def _contract(
    omschrijving: str = "Huur bedrijfspand",
    jaarbedrag: float = 12_000.0,
    ingang: date = date(2023, 1, 1),
    eind: date = date(2028, 1, 1),
) -> ct.Contract:
    return ct.Contract(
        omschrijving=omschrijving, jaarbedrag=jaarbedrag, ingangsdatum=ingang, einddatum=eind
    )


# --- Peildatum ----------------------------------------------------------


def test_balansdatum_uit_de_einddatum_van_het_boekjaar() -> None:
    af = Auditfile(header={"endDate": "2025-12-31"})
    assert ct.balansdatum(af) == date(2025, 12, 31)


def test_balansdatum_zonder_geldige_einddatum() -> None:
    assert ct.balansdatum(Auditfile(header={})) is None
    assert ct.balansdatum(Auditfile(header={"endDate": "onbekend"})) is None


# --- Resterende looptijd --------------------------------------------------


def test_resterende_maanden_bij_een_lopend_contract() -> None:
    contract = _contract(ingang=date(2023, 1, 1), eind=date(2028, 1, 1))
    assert ct.resterende_maanden(contract, date(2025, 12, 31)) == 24


def test_resterende_maanden_is_nul_na_afloop() -> None:
    contract = _contract(eind=date(2024, 1, 1))
    assert ct.resterende_maanden(contract, date(2025, 12, 31)) == 0


def test_resterende_maanden_op_de_einddatum_zelf_is_nul() -> None:
    contract = _contract(eind=date(2025, 12, 31))
    assert ct.resterende_maanden(contract, date(2025, 12, 31)) == 0


def test_resterende_maanden_rondt_af_op_hele_maanden() -> None:
    """Nog geen volle maand te gaan telt niet mee als een hele maand."""
    contract = _contract(eind=date(2026, 1, 15))
    assert ct.resterende_maanden(contract, date(2025, 12, 31)) == 0
    contract_net_wel = _contract(eind=date(2026, 1, 31))
    assert ct.resterende_maanden(contract_net_wel, date(2025, 12, 31)) == 1


# --- Overzicht en totaal ---------------------------------------------------


def test_overzicht_berekent_de_resterende_verplichting() -> None:
    contract = _contract(jaarbedrag=12_000.0, eind=date(2028, 1, 1))
    overzicht = ct.build_contractenoverzicht([contract], date(2025, 1, 1))
    assert list(overzicht.columns) == ct.CONTRACT_COLUMNS
    rij = overzicht.iloc[0]
    assert rij["resterende_maanden"] == 36
    assert rij["resterende_verplichting"] == pytest.approx(36_000.0)


def test_overzicht_zonder_peildatum_laat_de_verplichting_leeg() -> None:
    overzicht = ct.build_contractenoverzicht([_contract()], None)
    rij = overzicht.iloc[0]
    assert rij["resterende_maanden"] is None
    assert rij["resterende_verplichting"] is None


def test_overzicht_zonder_contracten_is_leeg() -> None:
    overzicht = ct.build_contractenoverzicht([], date(2025, 1, 1))
    assert overzicht.empty
    assert list(overzicht.columns) == ct.CONTRACT_COLUMNS


def test_totaal_telt_meerdere_contracten_op() -> None:
    contracten = [
        _contract(jaarbedrag=12_000.0, eind=date(2028, 1, 1)),
        _contract(jaarbedrag=6_000.0, eind=date(2027, 1, 1)),
    ]
    overzicht = ct.build_contractenoverzicht(contracten, date(2025, 1, 1))
    totaal = ct.totaal_resterende_verplichting(overzicht)
    # 36 maanden a 1.000 + 24 maanden a 500.
    assert totaal == pytest.approx(36_000.0 + 12_000.0)


def test_totaal_is_nul_bij_een_leeg_overzicht() -> None:
    overzicht = ct.build_contractenoverzicht([], date(2025, 1, 1))
    assert ct.totaal_resterende_verplichting(overzicht) == 0.0


# --- Opslag: heen en terug tussen Contract en dict -------------------------


def test_contract_naar_dict_en_terug_geeft_hetzelfde_contract() -> None:
    contract = _contract()
    ruw = ct.contract_naar_dict(contract)
    assert ruw["ingangsdatum"] == "2023-01-01"
    assert ruw["einddatum"] == "2028-01-01"

    teruggehaald = ct.contract_van_dict(ruw)
    assert teruggehaald == contract


def test_onbruikbare_rij_wordt_overgeslagen_niet_laten_crashen() -> None:
    """Een handmatig bewerkt of verouderd bestand mag de app niet breken."""
    ruw = [
        ct.contract_naar_dict(_contract(omschrijving="Goed contract")),
        {"omschrijving": "", "jaarbedrag": 100.0, "ingangsdatum": "2023-01-01", "einddatum": "2024-01-01"},
        {"omschrijving": "Geen datum", "jaarbedrag": 100.0, "ingangsdatum": "onbekend", "einddatum": "2024-01-01"},
        {"omschrijving": "Geen bedrag", "jaarbedrag": "niet-een-getal", "ingangsdatum": "2023-01-01", "einddatum": "2024-01-01"},
        {},
    ]
    contracten = ct.contracten_van_ruw(ruw)
    assert len(contracten) == 1
    assert contracten[0].omschrijving == "Goed contract"
