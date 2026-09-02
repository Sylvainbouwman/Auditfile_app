"""De dossiersleutel: waar hoort eigen invoer bij?

Eigen invoer hoort bij één onderneming en één boekjaar. De sleutel bepaalt dus
of invoer terugkomt bij hetzelfde dossier en, belangrijker, of hij wegblijft bij
een ander. Alle gegevens hier zijn synthetisch.
"""
from __future__ import annotations

from auditfile.demo import Account, AuditfileSpec, Journal, Line, Transaction, build_xaf
from auditfile.parsing import parse_auditfile


def _auditfile(
    bestandsnaam: str = "synthetisch.xaf",
    naam: str = "Testbedrijf Synthetisch BV",
    btw_nummer: str = "NL000000000B01",
    kvk: str = "00000000",
    boekjaar: str = "2025",
    bedrag: str = "100.00",
):
    spec = AuditfileSpec(
        company_name=naam,
        tax_reg_ident=btw_nummer,
        commerce_nr=kvk,
        fiscal_year=boekjaar,
        start_date=f"{boekjaar}-01-01",
        end_date=f"{boekjaar}-12-31",
        accounts=[Account("1000", "Kas", "B"), Account("8000", "Omzet", "P")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "M1",
                        f"{boekjaar}-01-01",
                        1,
                        [Line("1000", bedrag, "D"), Line("8000", bedrag, "C")],
                    )
                ],
            )
        ],
    )
    return parse_auditfile(bestandsnaam, build_xaf(spec))


def test_zelfde_onderneming_en_jaar_geeft_dezelfde_sleutel():
    """Een gecorrigeerd auditfile over hetzelfde jaar hoort bij hetzelfde dossier.

    De sleutel hangt daarom niet aan de bestandsinhoud: anders was de
    beoordeling weg zodra de klant een nieuwe export aanlevert.
    """
    eerste = _auditfile("eerste_export.xaf", bedrag="100.00")
    tweede = _auditfile("correctie_export.xaf", bedrag="900.00")

    assert eerste.vingerafdruk != tweede.vingerafdruk
    assert eerste.dossier_sleutel == tweede.dossier_sleutel
    assert eerste.dossier_sleutel != ""


def test_ander_boekjaar_is_een_ander_dossier():
    assert _auditfile(boekjaar="2024").dossier_sleutel != _auditfile(boekjaar="2025").dossier_sleutel


def test_andere_onderneming_is_een_ander_dossier():
    eerste = _auditfile(btw_nummer="NL000000000B01")
    tweede = _auditfile(btw_nummer="NL000000000B02")
    assert eerste.dossier_sleutel != tweede.dossier_sleutel


def test_naamswijziging_verandert_het_dossier_niet():
    """Het btw-nummer gaat voor op de naam; een statutaire naamswijziging niet."""
    eerste = _auditfile(naam="Testbedrijf Synthetisch BV")
    tweede = _auditfile(naam="Testbedrijf Synthetisch Holding BV")
    assert eerste.dossier_identiteit == "NL000000000B01"
    assert eerste.dossier_sleutel == tweede.dossier_sleutel


def test_zonder_nummers_valt_de_sleutel_terug_op_de_naam():
    af = _auditfile(btw_nummer="", kvk="", naam="Naamloos Synthetisch BV")
    assert af.dossier_identiteit == "Naamloos Synthetisch BV"
    assert af.dossier_sleutel != ""


def test_zonder_identificatie_of_boekjaar_is_er_geen_sleutel():
    assert _auditfile(btw_nummer="", kvk="", naam="").dossier_sleutel == ""
    assert _auditfile(boekjaar="").dossier_sleutel == ""


def test_de_sleutel_bevat_geen_ondernemingsgegevens():
    """De sleutel komt in een mapnaam op schijf; daar hoort geen klantnaam in."""
    af = _auditfile()
    sleutel = af.dossier_sleutel
    assert af.bedrijfsnaam.lower() not in sleutel.lower()
    assert "NL000000000B01".lower() not in sleutel.lower()
    assert "00000000" not in sleutel
    assert af.boekjaar not in sleutel
    assert len(sleutel) == 16 and all(teken in "0123456789abcdef" for teken in sleutel)
