"""Suppletiedetectie en de aansluiting op het verschil met de aangifte.

Alle auditfiles zijn synthetisch; er wordt nooit klantdata gelezen.
"""
from __future__ import annotations

import pytest

from auditfile import suppletie as sup
from auditfile import vat
from auditfile.demo import (
    DEMO_SUPPLETIEREKENING,
    build_xaf,
    demopaar,
    eenvoudige_spec,
    vul_suppletie,
)
from auditfile.findings import Materialiteit, verzamel_bevindingen
from auditfile.memorandum import bouw_memorandum, naar_markdown
from auditfile.parsing import parse_auditfile

# Het bedrag dat de demo als suppletie boekt. Rond en herkenbaar, zodat een
# verschoven teken meteen opvalt.
SUPPLETIEBEDRAG = 1_500.0


def _auditfile(bedrag: float = SUPPLETIEBEDRAG, **kwargs):
    spec = vul_suppletie(eenvoudige_spec("4.0"), bedrag, **kwargs)
    return parse_auditfile("synthetisch.xaf", build_xaf(spec))


def _samenvatting(af, aangifte=None):
    gebruik = vat.pas_mapping_toe(vat.build_vat_usage(af))
    return vat.build_rubric_summary(gebruik, aangifte)


# --- Detectie ---------------------------------------------------------------


def test_geen_suppletie_in_het_gewone_bestand(af_40):
    assert sup.detecteer_suppleties(af_40).empty


def test_suppletie_wordt_gevonden_met_bedrag_en_periode():
    gevonden = sup.detecteer_suppleties(_auditfile())
    assert len(gevonden) == 1
    regel = gevonden.iloc[0]
    assert regel["rekening"] == DEMO_SUPPLETIEREKENING.accID
    # Credit op een btw-rekening: als grootboekbedrag negatief.
    assert regel["bedrag"] == pytest.approx(-SUPPLETIEBEDRAG)
    assert regel["periode"] == 12
    assert regel["trefwoord"] == "suppletie"
    assert regel["zekerheid"] == sup.HOOG


def test_rekening_buiten_de_btw_codetabel_telt_mee():
    """De suppletierekening staat niet in de btw-codetabel maar wel in de selectie."""
    af = _auditfile()
    rekeningen, methode = sup.btw_balansrekeningen(af)
    assert DEMO_SUPPLETIEREKENING.accID not in vat.btw_grootboekrekeningen(af)
    assert DEMO_SUPPLETIEREKENING.accID in rekeningen
    assert methode == "btw-codetabel en omschrijving"


@pytest.mark.parametrize(
    "omschrijving, trefwoord, zekerheid",
    [
        ("Suppletie omzetbelasting 2025", "suppletie", sup.HOOG),
        ("Naheffingsaanslag OB", "naheffingsaanslag", sup.HOOG),
        ("Aanvullende aangifte omzetbelasting", "aanvullende aangifte", sup.HOOG),
        ("Correctie btw voorgaand tijdvak", "btw-correctie", sup.MIDDEL),
    ],
)
def test_elk_trefwoord_wordt_herkend(omschrijving, trefwoord, zekerheid):
    gevonden = sup.detecteer_suppleties(_auditfile(omschrijving=omschrijving))
    assert len(gevonden) == 1
    assert gevonden.iloc[0]["trefwoord"] == trefwoord
    assert gevonden.iloc[0]["zekerheid"] == zekerheid


def test_correctie_zonder_btw_in_de_tekst_telt_niet_mee():
    """Anders vangt het woord elke memoriaalcorrectie op de rekening op."""
    assert sup.detecteer_suppleties(_auditfile(omschrijving="Correctie boekingsfout")).empty


@pytest.mark.parametrize(
    "omschrijving, tijdvak, jaar",
    [
        ("Suppletie Q3 2025", "Q3", "2025"),
        ("Suppletie 4e kwartaal 2024", "Q4", "2024"),
        ("Suppletie kwartaal 1", "Q1", ""),
        ("Suppletie november 2025", "november", "2025"),
        ("Suppletie omzetbelasting", "", ""),
    ],
)
def test_tijdvak_en_jaar_uit_de_omschrijving(omschrijving, tijdvak, jaar):
    gevonden = sup.detecteer_suppleties(_auditfile(omschrijving=omschrijving))
    assert gevonden.iloc[0]["tijdvak"] == tijdvak
    assert gevonden.iloc[0]["jaar"] == jaar


def test_suppletie_over_een_ander_jaar_valt_buiten_de_aansluiting():
    af = _auditfile(omschrijving="Suppletie Q4 2024")
    gevonden = sup.detecteer_suppleties(af)
    assert not bool(gevonden.iloc[0]["hoort_bij_boekjaar"])

    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af))
    assert aansluiting.aantal == 0
    assert aansluiting.geboekt == pytest.approx(0.0)
    assert aansluiting.geboekt_ander_jaar == pytest.approx(SUPPLETIEBEDRAG)


# --- Aansluiting ------------------------------------------------------------


def _aangifte_met_verschil(af, verschil: float) -> dict[str, float]:
    """Aangiftebedragen die precies ``verschil`` afwijken van het auditfile.

    Positief betekent: er is minder aangegeven dan het auditfile laat zien, dus
    er is nog btw af te dragen.
    """
    samenvatting = _samenvatting(af).set_index("rubriek")["btw_volgens_xaf"]
    aangifte = {code: float(bedrag) for code, bedrag in samenvatting.items() if code != "?"}
    aangifte["1a"] = aangifte.get("1a", 0.0) - verschil
    return aangifte


def test_geen_aangifte_ingevoerd_geeft_geen_vergelijking(af_40):
    aansluiting = sup.bouw_aansluiting(af_40, _samenvatting(af_40))
    assert aansluiting.status == sup.GEEN_VERGELIJKING
    assert aansluiting.verschil_met_aangifte is None
    assert "geen aangiftebedrag ingevoerd" in aansluiting.toelichting


def test_suppletie_zonder_ingevoerde_aangifte():
    af = _auditfile()
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af))
    assert aansluiting.status == sup.SUPPLETIE_ZONDER_VERGELIJKING
    assert aansluiting.geboekt == pytest.approx(SUPPLETIEBEDRAG)


def test_geen_suppletie_en_geen_verschil(af_40):
    aangifte = _aangifte_met_verschil(af_40, 0.0)
    aansluiting = sup.bouw_aansluiting(af_40, _samenvatting(af_40, aangifte))
    assert aansluiting.status == sup.GEEN_AANLEIDING
    assert aansluiting.verschil_met_aangifte == pytest.approx(0.0)


def test_verschil_zonder_geboekte_suppletie(af_40):
    aangifte = _aangifte_met_verschil(af_40, SUPPLETIEBEDRAG)
    aansluiting = sup.bouw_aansluiting(af_40, _samenvatting(af_40, aangifte))
    assert aansluiting.status == sup.GEEN_SUPPLETIE
    assert aansluiting.verschil_met_aangifte == pytest.approx(SUPPLETIEBEDRAG)
    assert aansluiting.restant == pytest.approx(SUPPLETIEBEDRAG)


def test_suppletie_sluit_aan_op_het_verschil():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, SUPPLETIEBEDRAG)
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af, aangifte))
    assert aansluiting.status == sup.SLUIT_AAN
    assert aansluiting.restant == pytest.approx(0.0)
    assert "Of zij ook is ingediend" in aansluiting.toelichting


def test_suppletie_verklaart_het_verschil_deels():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, SUPPLETIEBEDRAG + 400.0)
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af, aangifte))
    assert aansluiting.status == sup.DEELS
    assert aansluiting.restant == pytest.approx(400.0)


def test_suppletie_zonder_verschil_met_de_aangifte():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, 0.0)
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af, aangifte))
    assert aansluiting.status == sup.ZONDER_VERSCHIL


def test_zonder_btw_rekeningen_is_de_vraag_niet_te_beantwoorden():
    spec = eenvoudige_spec("4.0")
    spec.vat_codes = []
    # Ook de rekeningen die op hun omschrijving btw-rekening zijn, moeten weg:
    # anders vindt de selectie ze alsnog en is dit geen lege situatie.
    for rekening in spec.accounts:
        if "omzetbelasting" in rekening.accDesc.lower():
            rekening.accDesc = f"Tussenrekening {rekening.accID}"
    af = parse_auditfile("zonder_btw.xaf", build_xaf(spec))
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af))
    assert aansluiting.status == sup.GEEN_BTW_REKENINGEN
    assert sup.naar_tabel(aansluiting).empty
    assert sup.detecteer_suppleties(af).empty


def test_teruggaaf_keert_het_teken_om():
    """Een suppletie die geld teruggeeft staat debet en levert een negatief bedrag."""
    af = _auditfile(-SUPPLETIEBEDRAG)
    aansluiting = sup.bouw_aansluiting(af, _samenvatting(af))
    assert aansluiting.geboekt == pytest.approx(-SUPPLETIEBEDRAG)


# --- Overzicht en memorandum ------------------------------------------------


def test_tabel_toont_verschil_suppletie_en_restant():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, SUPPLETIEBEDRAG)
    tabel = sup.naar_tabel(sup.bouw_aansluiting(af, _samenvatting(af, aangifte)))
    assert list(tabel["post"]) == [
        "Verschil tussen auditfile en aangifte",
        "Geboekte suppletie",
        "Restant",
    ]
    assert tabel.iloc[1]["bedrag"] == pytest.approx(SUPPLETIEBEDRAG)


def test_bevinding_komt_in_de_verzameling():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, SUPPLETIEBEDRAG + 400.0)
    bevindingen = verzamel_bevindingen(af, aangifte=aangifte)
    suppletiepunten = bevindingen[bevindingen["onderwerp"].str.startswith("Suppletie:")]
    assert len(suppletiepunten) == 1
    assert suppletiepunten.iloc[0]["ernst"] == "waarschuwing"
    assert suppletiepunten.iloc[0]["bedrag"] == pytest.approx(400.0)


def test_zonder_aanleiding_geen_bevinding(af_40):
    aangifte = _aangifte_met_verschil(af_40, 0.0)
    bevindingen = verzamel_bevindingen(af_40, aangifte=aangifte)
    assert bevindingen[bevindingen["onderwerp"].str.startswith("Suppletie:")].empty


def test_de_bevinding_staat_in_het_memorandum():
    af = _auditfile()
    aangifte = _aangifte_met_verschil(af, SUPPLETIEBEDRAG + 400.0)
    materialiteit = Materialiteit(absoluut=100.0)
    bevindingen = verzamel_bevindingen(af, aangifte=aangifte, materialiteit=materialiteit)
    tekst = naar_markdown(bouw_memorandum(af, bevindingen, materialiteit))
    assert "verklaart het verschil deels" in tekst.lower()


def test_de_demo_bevat_een_geboekte_suppletie():
    """Anders kan de functie stil uit de demo verdwijnen."""
    _, huidig_bytes = demopaar()
    huidig = parse_auditfile("demo.xaf", huidig_bytes)
    gevonden = sup.detecteer_suppleties(huidig)
    assert len(gevonden) == 1
    assert gevonden.iloc[0]["tijdvak"] == "Q3"
    assert bool(gevonden.iloc[0]["hoort_bij_boekjaar"])
