"""Tests op het inlezen van XAF-auditfiles."""
from __future__ import annotations

import pandas as pd
import pytest

from auditfile.parsing import parse_auditfile, signed_amount, signed_amount_series
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Transaction,
    build_xaf,
)


# --- Tekenconventie ---------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "kind", "verwacht"),
    [
        ("100.00", "D", 100.0),
        ("100.00", "C", -100.0),
        # Het teken van het bedrag telt gewoon mee; de creditindicatie draait
        # het om. Een negatieve creditregel is dus effectief een debetbedrag.
        ("-100.00", "D", -100.0),
        ("-100.00", "C", 100.0),
        ("0.00", "D", 0.0),
        ("", "D", 0.0),
        ("onleesbaar", "C", 0.0),
        ("100.00", "c", -100.0),
        ("100.00", " C ", -100.0),
    ],
)
def test_signed_amount_volgt_uitsluitend_het_bedragtype(amount, kind, verwacht):
    assert signed_amount(amount, kind) == verwacht


def test_signed_amount_series_gelijk_aan_scalar():
    amounts = pd.Series(["100.00", "-100.00", "50.00", ""])
    kinds = pd.Series(["D", "C", "C", "D"])
    reeks = signed_amount_series(amounts, kinds)
    los = [signed_amount(a, k) for a, k in zip(amounts, kinds)]
    assert list(reeks) == los


def test_boekingsregels_sluiten_op_nul(af_40):
    """De som van alle getekende bedragen moet nul zijn: debet is credit."""
    assert round(af_40.lines["bedrag"].sum(), 2) == 0.00


def test_getekende_bedragen_sluiten_aan_op_controletotalen(af_40):
    """Debet- en creditzijde moeten gelijk zijn aan de totalen in het bestand.

    De zijde volgt uit ``amntTp``, niet uit het teken van de uitkomst: een
    negatieve debetregel verlaagt het debettotaal.
    """
    lines = af_40.lines
    is_debet = lines["line_amntTp"].str.upper() == "D"
    debet = lines.loc[is_debet, "bedrag"].sum()
    credit = lines.loc[~is_debet, "bedrag"].sum()
    assert round(debet, 2) == round(af_40.transaction_totals.total_debit, 2)
    assert round(-credit, 2) == round(af_40.transaction_totals.total_credit, 2)


def test_negatieve_bedragen_komen_daadwerkelijk_voor(af_40):
    """Borgt dat de fixture het scenario dekt waar het om gaat."""
    assert (af_40.lines["line_amnt"] < 0).any()


# --- Structuur --------------------------------------------------------------


def test_beide_xaf_versies_geven_hetzelfde_resultaat(af_32, af_40):
    """3.2 en 4.0 verschillen in metadata, niet in cijfers."""
    assert af_32.xaf_versie == "3.2"
    assert af_40.xaf_versie == "4.0"
    assert len(af_32.lines) == len(af_40.lines)
    assert round(af_32.lines["bedrag"].sum(), 2) == round(af_40.lines["bedrag"].sum(), 2)
    saldo_32 = af_32.saldo.set_index("rekening")["saldo"].round(2)
    saldo_40 = af_40.saldo.set_index("rekening")["saldo"].round(2)
    assert saldo_32.to_dict() == saldo_40.to_dict()


def test_rgs_herkomst_wordt_vastgelegd(af_32, af_40):
    """XAF 4.0 levert RGScode; 3.2 valt terug op leadReference."""
    assert set(af_40.accounts["RGSbron"]) == {"RGScode"}
    assert set(af_32.accounts["RGSbron"]) == {"leadReference"}


def test_relaties_worden_ingelezen(af_40):
    assert set(af_40.relations["custSupID"]) == {"D001", "C001"}
    assert set(af_40.relations["custSupTp"]) == {"C", "S"}


def test_relatie_op_boekingsregel_beschikbaar(af_40):
    """custSupID op de regel is nodig voor debiteuren- en crediteurenanalyse."""
    assert (af_40.lines["line_custSupID"] != "").any()


def test_bedrijfsgegevens(af_40):
    info = dict(af_40.company_info_frame().to_records(index=False))
    assert info["Bedrijfsnaam"] == "Testbedrijf Synthetisch BV"
    assert info["Boekjaar"] == "2025"
    assert info["XAF-versie"] == "4.0"


def test_perioden(af_40):
    assert len(af_40.periods) == 12
    assert af_40.period_labels[1] == "jan"
    assert af_40.period_labels[12] == "dec"


# --- Saldi ------------------------------------------------------------------


def test_beginsaldo_uit_openingsbalans(af_40):
    saldo = af_40.saldo.set_index("rekening")
    assert round(saldo.loc["0100", "beginsaldo"], 2) == 12000.00
    assert round(saldo.loc["1600", "beginsaldo"], 2) == -20000.00


def test_eindsaldo_is_begin_plus_mutatie(af_40):
    saldo = af_40.saldo
    berekend = (saldo["beginsaldo"] + saldo["mutaties_boekjaar"]).round(2)
    assert list(berekend) == list(saldo["eindsaldo"].round(2))


def test_resultaatrekening_heeft_geen_beginsaldo_in_saldo(af_40):
    """Voor een P-rekening telt de mutatie, niet het eindsaldo."""
    saldo = af_40.saldo.set_index("rekening")
    assert round(saldo.loc["4300", "saldo"], 2) == round(saldo.loc["4300", "mutaties_boekjaar"], 2)


def test_balansrekening_gebruikt_eindsaldo(af_40):
    saldo = af_40.saldo.set_index("rekening")
    assert round(saldo.loc["0100", "saldo"], 2) == round(saldo.loc["0100", "eindsaldo"], 2)


def test_saldo_afschrijving_klopt(af_40):
    """Twaalf maanden huur van 1.000 plus de losse memoriaalboekingen."""
    saldo = af_40.saldo.set_index("rekening")
    assert round(saldo.loc["4000", "saldo"], 2) == 12000.00
    assert round(saldo.loc["4300", "saldo"], 2) == 2400.00


# --- Randgevallen -----------------------------------------------------------


def test_leeg_auditfile_levert_lege_maar_bruikbare_structuur():
    spec = AuditfileSpec(accounts=[Account("8000", "Omzet", "P")], journals=[])
    af = parse_auditfile("leeg.xaf", build_xaf(spec))
    assert af.lines.empty
    assert "bedrag" in af.lines.columns
    assert len(af.saldo) == 0 or af.saldo["mutaties_boekjaar"].sum() == 0


def test_regel_zonder_omschrijving_breekt_niet():
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B"), Account("8000", "Omzet", "P")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "M1",
                        "2025-01-01",
                        1,
                        [
                            Line("1000", "100.00", "D", desc=""),
                            Line("8000", "100.00", "C", desc=""),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("zonder_omschrijving.xaf", build_xaf(spec))
    assert len(af.lines) == 2
    assert round(af.lines["bedrag"].sum(), 2) == 0.00


def test_boeking_op_onbekende_rekening_verdwijnt_niet():
    """Een regel op een rekening buiten het schema moet zichtbaar blijven."""
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "M1",
                        "2025-01-01",
                        1,
                        [Line("1000", "100.00", "D"), Line("9999", "100.00", "C")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("onbekende_rekening.xaf", build_xaf(spec))
    assert len(af.lines) == 2
    assert "9999" in set(af.saldo["rekening"])
    assert round(af.lines["bedrag"].sum(), 2) == 0.00


def test_btw_bedrag_leeg_bij_regel_zonder_btw(af_40):
    """Geen btw-blok is iets anders dan een btw-bedrag van nul."""
    zonder_btw = af_40.lines[af_40.lines["vat_vatID"] == ""]
    assert zonder_btw["btw_bedrag"].isna().all()
    met_btw = af_40.lines[af_40.lines["vat_vatID"] != ""]
    assert met_btw["btw_bedrag"].notna().all()
