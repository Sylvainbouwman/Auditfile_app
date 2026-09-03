"""Nederlandse notatie van losse waarden, en waar zij hoort te staan.

De notatie stond alleen in ``formatting.py``, en die module haalt Streamlit
binnen. Een analysemodule kon haar daarom niet gebruiken en liet een bedrag in
een toelichting als ``2520.00`` staan. Deze tests bewaken beide kanten: de
notatie zelf, en dat zij zonder Streamlit te gebruiken blijft.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from auditfile.comparison import compare_saldi
from auditfile.demo import demopaar
from auditfile.findings import _uit_jaarvergelijking
from auditfile.notatie import GEEN_WAARDE, datum_nl, euro, euro_kort, procent
from auditfile.parsing import parse_auditfile

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- De notatie zelf --------------------------------------------------------


@pytest.mark.parametrize(
    "waarde, verwacht",
    [
        (1234.56, "€ 1.234,56"),
        (-2520.0, "€ -2.520,00"),
        (0, "€ 0,00"),
        (1_234_567.891, "€ 1.234.567,89"),
        ("2520.00", "€ 2.520,00"),
    ],
)
def test_euro_in_nederlandse_notatie(waarde, verwacht):
    assert euro(waarde) == verwacht


def test_zonder_waarde_geen_nul():
    """Onbekend is iets anders dan nul; een leeg veld zou als nul worden gelezen."""
    assert euro(None) == GEEN_WAARDE
    assert euro(float("nan")) == GEEN_WAARDE
    assert euro("geen bedrag") == GEEN_WAARDE
    assert procent(None) == GEEN_WAARDE
    assert datum_nl(None) == ""


def test_kerncijfers_en_percentages():
    assert euro_kort(1234.56) == "€ 1.235"
    assert procent(12.34) == "12,3%"
    assert datum_nl("2025-12-31") == "31-12-2025"


# --- Waar de notatie mag staan ----------------------------------------------


@pytest.mark.parametrize(
    "module",
    ["auditfile.notatie", "auditfile.findings", "auditfile.openstaand", "auditfile.relatiesaldi"],
)
def test_de_analyselaag_haalt_geen_streamlit_binnen(module):
    """Anders is de notatie weer alleen in de app te gebruiken.

    In een apart proces, want de testrun zelf importeert Streamlit al via
    ``app.py`` in andere tests.
    """
    uitkomst = subprocess.run(
        [sys.executable, "-c", f"import {module}, sys; print('streamlit' in sys.modules)"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert uitkomst.returncode == 0, uitkomst.stderr
    assert uitkomst.stdout.strip() == "False"


# --- De bedragen in de bevindingen ------------------------------------------


def test_bevindingen_noemen_hun_bedragen_in_nederlandse_notatie():
    """De toelichting is tekst en komt zo in het memorandum terecht."""
    vorig_bytes, huidig_bytes = demopaar()
    vorig = parse_auditfile("demo_vorig_jaar.xaf", vorig_bytes)
    huidig = parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes)

    bevindingen = _uit_jaarvergelijking(compare_saldi(vorig, huidig))

    assert bevindingen
    for bevinding in bevindingen:
        assert "€" in bevinding.toelichting
        # Geen machinegetal meer: geen punt als decimaalteken.
        assert ".00 " not in bevinding.toelichting
        assert ",00" in bevinding.toelichting or ",5" in bevinding.toelichting
