"""Tests op de integriteitscontrole.

Alle bestanden hier zijn synthetisch en worden in het geheugen opgebouwd.
"""
from __future__ import annotations

from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Relation,
    Transaction,
    VatCode,
    build_xaf,
)
from auditfile.integrity import controleer_auditfile
from auditfile.parsing import parse_auditfile

CONTROLE = "Stamgegevens zonder dubbelingen"


def _sluitende_boeking() -> list[Journal]:
    return [
        Journal(
            "MEM",
            "Memoriaal",
            [
                Transaction(
                    "M1",
                    "2025-01-01",
                    1,
                    [Line("1000", "100.00", "D"), Line("8000", "100.00", "C")],
                )
            ],
        )
    ]


def _bevindingen(spec: AuditfileSpec):
    af = parse_auditfile("synthetisch.xaf", build_xaf(spec))
    bevindingen = controleer_auditfile(af)
    return af, bevindingen[bevindingen["controle"] == CONTROLE]


def test_dubbel_rekeningnummer_wordt_gemeld():
    """De parser houdt het eerste record aan, maar de dubbeling moet blijken."""
    spec = AuditfileSpec(
        accounts=[
            Account("1000", "Kas", "B"),
            Account("1000", "Kas tweede omschrijving", "B"),
            Account("8000", "Omzet", "P"),
        ],
        journals=_sluitende_boeking(),
    )
    af, gevonden = _bevindingen(spec)

    # Het opgeschoonde schema toont de dubbeling niet meer.
    assert not af.accounts["accID"].duplicated().any()
    assert af.duplicaten == {"rekeningen": ["1000"]}
    assert list(gevonden["ernst"]) == ["waarschuwing"]
    assert "1000" in gevonden["bevinding"].iloc[0]


def test_dubbele_btw_code_en_relatie_worden_gemeld():
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B"), Account("8000", "Omzet", "P")],
        vat_codes=[VatCode("1", "Hoog"), VatCode("1", "Hoog, tweede regel")],
        relations=[Relation("D001", "Eerste"), Relation("D001", "Tweede")],
        journals=_sluitende_boeking(),
    )
    af, gevonden = _bevindingen(spec)

    assert af.duplicaten == {"btw-codes": ["1"], "relaties": ["D001"]}
    assert len(gevonden) == 2
    assert set(gevonden["ernst"]) == {"waarschuwing"}


def test_zonder_dubbelingen_meldt_de_controle_in_orde():
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B"), Account("8000", "Omzet", "P")],
        vat_codes=[VatCode("1", "Hoog")],
        relations=[Relation("D001", "Eerste")],
        journals=_sluitende_boeking(),
    )
    af, gevonden = _bevindingen(spec)

    assert af.duplicaten == {}
    assert list(gevonden["ernst"]) == ["in orde"]
