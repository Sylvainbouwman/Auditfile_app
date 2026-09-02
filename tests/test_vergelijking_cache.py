"""De vergelijking moet bij de juiste bestanden horen.

De vergelijkingsfunctie in ``app.py`` krijgt twee ``Auditfile``-objecten mee die
Streamlit niet kan hashen. Die argumenten beginnen daarom met een underscore en
vallen buiten de cachesleutel; wat overblijft is de sleutel die de app zelf
meegeeft. Legt die sleutel de inhoud niet vast, dan krijgt een tweede dossier
met gelijknamige bestanden de vergelijking van het eerste terug.
"""
from __future__ import annotations

import app
from auditfile.comparison import compare_saldi
from auditfile.demo import build_xaf, eenvoudige_spec
from auditfile.parsing import parse_auditfile


def _spec_met_extra_omzet(bedrag: str):
    """Twee specs die alleen in een bedrag verschillen."""
    spec = eenvoudige_spec("4.0")
    for journaal in spec.journals:
        for transactie in journaal.transactions:
            for regel in transactie.lines:
                if regel.accID == "8000":
                    regel.amnt = bedrag
    return spec


def test_sleutel_verschilt_bij_gelijke_bestandsnaam():
    """Zelfde naam, andere inhoud: de sleutel moet verschillen."""
    naam = "auditfile.xaf"
    eerste = parse_auditfile(naam, build_xaf(_spec_met_extra_omzet("1000.00")))
    tweede = parse_auditfile(naam, build_xaf(_spec_met_extra_omzet("1900.00")))

    assert eerste.bestandsnaam == tweede.bestandsnaam
    assert eerste.vingerafdruk != tweede.vingerafdruk
    assert app.vergelijkingssleutel(eerste, eerste) != app.vergelijkingssleutel(eerste, tweede)


def test_sleutel_gelijk_bij_gelijke_inhoud():
    """Dezelfde inhoud onder een andere naam mag de cache wel gebruiken."""
    inhoud = build_xaf(eenvoudige_spec("4.0"))
    eerste = parse_auditfile("een.xaf", inhoud)
    tweede = parse_auditfile("twee.xaf", inhoud)

    assert eerste.vingerafdruk == tweede.vingerafdruk
    assert app.vergelijkingssleutel(eerste, eerste) == app.vergelijkingssleutel(tweede, tweede)


def test_verschillende_inhoud_geeft_andere_vergelijking():
    """Zonder verschil in uitkomst zou de sleutel niets te beschermen hebben."""
    naam = "auditfile.xaf"
    eerste = parse_auditfile(naam, build_xaf(_spec_met_extra_omzet("1000.00")))
    tweede = parse_auditfile(naam, build_xaf(_spec_met_extra_omzet("1900.00")))
    vorig = parse_auditfile("vorig.xaf", build_xaf(eenvoudige_spec("3.2")))

    een = compare_saldi(vorig, eerste)
    twee = compare_saldi(vorig, tweede)
    saldo_een = een.loc[een["rekening"] == "8000", "saldo_huidig"].iloc[0]
    saldo_twee = twee.loc[twee["rekening"] == "8000", "saldo_huidig"].iloc[0]
    assert saldo_een != saldo_twee
