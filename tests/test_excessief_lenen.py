"""Tests bij de drempeltoets excessief lenen.

Alle bedragen zijn verzonnen; de drempel zelf komt uit de wet en staat in
``docs/btw-bronnen.md``. De tests zetten de bedragen bewust rond de drempel om
de grenzen te raken, niet om een realistisch dossier na te bootsen.
"""
from __future__ import annotations

import pandas as pd
import pytest

from auditfile import excessief_lenen as el
from auditfile.demo import build_xaf, eenvoudige_spec, vul_rekening_courant
from auditfile.findings import NIET_MOGELIJK, SIGNAAL, WAARSCHUWING, verzamel_bevindingen
from auditfile.parsing import parse_auditfile

DREMPEL_2025 = 500_000.0


def _auditfile(bedrag: float, afwijkend: float = 0.0, versie: str = "4.0", boekjaar: str = "2025"):
    spec = eenvoudige_spec(versie)
    spec = vul_rekening_courant(spec, bedrag, afwijkend_gecodeerd=afwijkend)
    spec.fiscal_year = boekjaar
    spec.start_date = f"{boekjaar}-01-01"
    spec.end_date = f"{boekjaar}-12-31"
    return parse_auditfile("synthetisch.xaf", build_xaf(spec))


# --- Het wettelijke bedrag --------------------------------------------------


@pytest.mark.parametrize(
    ("jaar", "verwacht"),
    [(2023, 700_000.0), (2024, 500_000.0), (2025, 500_000.0), (2026, 500_000.0)],
)
def test_maximumbedrag_per_peildatum(jaar, verwacht) -> None:
    bedrag, toelichting = el.maximumbedrag(jaar)
    assert bedrag == verwacht
    assert "4.14a" in toelichting


def test_geen_bedrag_voor_een_jaar_voor_de_invoering() -> None:
    """Vóór 2023 bestond de regeling niet, dus is er niets te toetsen."""
    bedrag, toelichting = el.maximumbedrag(2022)
    assert bedrag is None
    assert "2023" in toelichting


def test_geen_bedrag_voor_een_jaar_zonder_vaststelling() -> None:
    """Het bedrag wordt niet geïndexeerd en dus nooit doorgeschreven."""
    bedrag, toelichting = el.maximumbedrag(el.LAATSTE_JAAR + 1)
    assert bedrag is None
    assert "niet geïndexeerd" in toelichting


def test_voorbehoud_bij_het_laatste_jaar() -> None:
    _, toelichting = el.maximumbedrag(el.LAATSTE_JAAR)
    assert "voorbehoud" in toelichting


# --- De peildatum -----------------------------------------------------------


def test_boekjaar_op_31_december_is_de_peildatum() -> None:
    peil = el.bepaal_peildatum(_auditfile(100_000.0))
    assert peil.geldig
    assert peil.jaar == 2025
    assert peil.datum == pd.Timestamp("2025-12-31")


def test_gebroken_boekjaar_is_geen_peildatum() -> None:
    """De wet peilt op het einde van het kalenderjaar, niet op de balansdatum."""
    spec = vul_rekening_courant(eenvoudige_spec("4.0"), 600_000.0)
    spec.end_date = "2025-06-30"
    af = parse_auditfile("gebroken.xaf", build_xaf(spec))

    peil = el.bepaal_peildatum(af)
    assert not peil.geldig
    assert "31 december" in peil.toelichting

    toets = el.beoordeel(af)
    assert toets.status == el.STATUS_NIET_MOGELIJK
    assert toets.ernst == NIET_MOGELIJK


# --- De rekeningselectie ----------------------------------------------------


def test_rekening_courant_wordt_op_rgs_code_gevonden() -> None:
    rekeningen = el.build_rc_rekeningen(_auditfile(250_000.0))
    assert list(rekeningen["rekening"]) == ["1400"]
    assert rekeningen.iloc[0]["methode"] == "RGS-code"
    assert rekeningen.iloc[0]["eindsaldo"] == pytest.approx(250_000.0)


def test_zonder_rekening_courant_geen_toets_en_geen_bevinding() -> None:
    af = parse_auditfile("zonder.xaf", build_xaf(eenvoudige_spec("4.0")))
    toets = el.beoordeel(af)
    assert toets.status == el.STATUS_GEEN_REKENING
    assert toets.ernst is None
    assert el.build_drempeltoets(af).empty


def test_afwijkende_codering_telt_niet_mee_maar_wordt_gemeld() -> None:
    """Een rekening-courant met een code buiten de toets blijft zichtbaar."""
    af = _auditfile(300_000.0, afwijkend=250_000.0)

    toets = el.beoordeel(af)
    assert toets.saldo_auditfile == pytest.approx(300_000.0)
    assert toets.rekeningen == 1

    afwijkend = el.build_afwijkende_codering(af)
    assert list(afwijkend["rekening"]) == ["1410"]
    assert afwijkend.iloc[0]["eindsaldo"] == pytest.approx(250_000.0)


# --- De toets ---------------------------------------------------------------


def test_onder_de_drempel_geeft_geen_bevinding() -> None:
    toets = el.beoordeel(_auditfile(100_000.0))
    assert toets.status == el.STATUS_ONDER
    assert toets.ernst is None
    assert toets.bovenmatig == pytest.approx(0.0)


def test_nabij_de_drempel_is_een_signaal() -> None:
    toets = el.beoordeel(_auditfile(DREMPEL_2025 * el.NABIJ_AANDEEL + 1_000.0))
    assert toets.status == el.STATUS_NABIJ
    assert toets.ernst == SIGNAAL


def test_boven_de_drempel_is_een_waarschuwing() -> None:
    toets = el.beoordeel(_auditfile(DREMPEL_2025 + 75_000.0))
    assert toets.status == el.STATUS_BOVEN
    assert toets.ernst == WAARSCHUWING
    assert toets.bovenmatig == pytest.approx(75_000.0)


def test_creditstand_is_geen_schuld_van_de_aandeelhouder() -> None:
    """Staat de rekening credit, dan is de vennootschap de schuldenaar."""
    toets = el.beoordeel(_auditfile(-80_000.0))
    assert toets.status == el.STATUS_GEEN_SCHULD
    assert toets.ernst is None


def test_precies_op_de_drempel_is_niet_bovenmatig() -> None:
    """Bovenmatig is het bedrag waarmee de drempel wordt overschreden."""
    toets = el.beoordeel(_auditfile(DREMPEL_2025))
    assert toets.status == el.STATUS_NABIJ
    assert toets.bovenmatig == pytest.approx(0.0)


# --- De invoer van de gebruiker ---------------------------------------------


def test_eigenwoningschuld_verlaagt_de_te_toetsen_schuld() -> None:
    af = _auditfile(DREMPEL_2025 + 50_000.0)
    toets = el.beoordeel(af, el.Invoer(eigenwoningschuld=200_000.0))
    assert toets.te_toetsen == pytest.approx(DREMPEL_2025 - 150_000.0)
    assert toets.status == el.STATUS_ONDER


def test_andere_vennootschappen_verhogen_de_te_toetsen_schuld() -> None:
    af = _auditfile(200_000.0)
    toets = el.beoordeel(af, el.Invoer(andere_vennootschappen=400_000.0))
    assert toets.te_toetsen == pytest.approx(600_000.0)
    assert toets.status == el.STATUS_BOVEN
    assert toets.bovenmatig == pytest.approx(100_000.0)


def test_eerder_belast_voordeel_verhoogt_het_maximumbedrag() -> None:
    """Art. 4.14a lid 2: hetzelfde bedrag wordt niet tweemaal belast."""
    af = _auditfile(DREMPEL_2025 + 60_000.0)
    assert el.beoordeel(af).status == el.STATUS_BOVEN

    toets = el.beoordeel(af, el.Invoer(eerder_belast_voordeel=200_000.0))
    assert toets.maximum == pytest.approx(DREMPEL_2025 + 200_000.0)
    assert toets.status == el.STATUS_ONDER
    assert toets.bovenmatig == pytest.approx(0.0)


def test_alleen_invoer_zonder_rekening_levert_toch_een_toets() -> None:
    """Een schuld aan een andere vennootschap staat niet in dit grootboek."""
    af = parse_auditfile("zonder.xaf", build_xaf(eenvoudige_spec("4.0")))
    toets = el.beoordeel(af, el.Invoer(andere_vennootschappen=DREMPEL_2025 + 10_000.0))
    assert toets.status == el.STATUS_BOVEN
    assert toets.bovenmatig == pytest.approx(10_000.0)


# --- De opbouwtabel ---------------------------------------------------------


def test_opbouw_scheidt_bestand_wet_en_gebruiker() -> None:
    af = _auditfile(DREMPEL_2025 + 20_000.0)
    opbouw = el.build_drempeltoets(af, el.Invoer(eigenwoningschuld=5_000.0))

    assert list(opbouw.columns) == el.OPBOUW_COLUMNS
    bronnen = set(opbouw["bron"])
    assert bronnen == {"auditfile", "gebruiker", "wet", "berekend"}

    per_onderdeel = opbouw.set_index("onderdeel")["bedrag"]
    assert per_onderdeel["Te toetsen schuld"] == pytest.approx(DREMPEL_2025 + 15_000.0)
    assert per_onderdeel["Bovenmatig deel"] == pytest.approx(15_000.0)


def test_opbouw_bij_een_onbekend_maximumbedrag_heeft_geen_bedrag() -> None:
    af = _auditfile(600_000.0, boekjaar=str(el.LAATSTE_JAAR + 1))
    opbouw = el.build_drempeltoets(af)
    per_onderdeel = opbouw.set_index("onderdeel")["bedrag"]
    assert pd.isna(per_onderdeel["Maximumbedrag volgens de wet"])
    assert pd.isna(per_onderdeel["Bovenmatig deel"])


# --- Doorwerking naar de bevindingen ----------------------------------------


def test_bevinding_bij_overschrijding() -> None:
    af = _auditfile(DREMPEL_2025 + 90_000.0)
    bevindingen = verzamel_bevindingen(af)
    fiscaal = bevindingen[
        bevindingen["onderwerp"].str.startswith("Rekening-courant en leningen aandeelhouder")
    ]
    assert len(fiscaal) == 1
    rij = fiscaal.iloc[0]
    assert rij["ernst"] == WAARSCHUWING
    assert rij["bedrag"] == pytest.approx(90_000.0)
    assert rij["rekening"] == "1400"
    assert rij["pagina"] == "Fiscale signalen"


def test_geen_bevinding_onder_de_drempel() -> None:
    bevindingen = verzamel_bevindingen(_auditfile(50_000.0))
    assert not bevindingen["onderwerp"].str.startswith(
        "Rekening-courant en leningen aandeelhouder"
    ).any()


def test_invoer_werkt_door_in_de_bevindingen() -> None:
    af = _auditfile(200_000.0)
    bevindingen = verzamel_bevindingen(
        af, excessief_lenen=el.Invoer(andere_vennootschappen=400_000.0)
    )
    fiscaal = bevindingen[
        bevindingen["onderwerp"].str.startswith("Rekening-courant en leningen aandeelhouder")
    ]
    assert len(fiscaal) == 1
    assert fiscaal.iloc[0]["bedrag"] == pytest.approx(100_000.0)
