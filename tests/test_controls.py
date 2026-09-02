"""Tests op de analytische controles."""
from __future__ import annotations

import pytest

from auditfile.controls import (
    build_balanspost_signalen,
    build_fiscale_signalen,
    build_omzet_per_periode,
    build_ongebruikelijke_boekingen,
    build_periodieke_controles,
    build_personeelskosten_per_periode,
    build_relatie_analyse,
    build_relatie_concentratie,
    compacte_perioden,
    rgs_rubriek,
)
from auditfile.parsing import parse_auditfile
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Relation,
    Transaction,
    build_xaf,
    eenvoudige_spec,
)


# --- Periodesamenvatting ----------------------------------------------------


@pytest.mark.parametrize(
    ("perioden", "verwacht"),
    [
        ([], ""),
        ([3], "3"),
        ([1, 2, 3], "1-3"),
        ([1, 2, 3, 7], "1-3, 7"),
        ([1, 3, 5], "1, 3, 5"),
    ],
)
def test_compacte_perioden(perioden, verwacht):
    assert compacte_perioden(perioden) == verwacht


def test_compacte_perioden_met_maandnamen():
    labels = {1: "jan", 2: "feb", 3: "mrt", 7: "jul"}
    assert compacte_perioden([1, 2, 3, 7], labels) == "jan-mrt, jul"


def test_rgs_rubriek():
    assert rgs_rubriek("WOmzNeh") == "Netto-omzet"
    assert rgs_rubriek("BLimKas") == "Liquide middelen"
    assert rgs_rubriek("") == ""
    assert rgs_rubriek(None) == ""
    assert rgs_rubriek("XXXX") == ""


# --- Periodieke controles ---------------------------------------------------


def test_huur_in_alle_perioden_geeft_geen_signaal(af_40):
    """In de fixture staat twaalf maanden huur van hetzelfde bedrag."""
    controles = build_periodieke_controles(af_40)
    huur = controles[controles["rekening"] == "4000"].iloc[0]
    assert huur["aantal_perioden"] == 12
    assert huur["ontbrekende_perioden"] == ""
    assert huur["conclusie"] == "Geen bijzonderheden"


def test_ontbrekende_perioden_worden_gemeld():
    spec = eenvoudige_spec("4.0")
    # Haal de huurboekingen van juli tot en met september weg.
    inkoop = next(journaal for journaal in spec.journals if journaal.jrnID == "INK")
    inkoop.transactions = [
        transactie for transactie in inkoop.transactions if transactie.periodNumber not in (7, 8, 9)
    ]
    af = parse_auditfile("gaten.xaf", build_xaf(spec))
    controles = build_periodieke_controles(af)
    huur = controles[controles["rekening"] == "4000"].iloc[0]
    assert huur["conclusie"] == "Ontbrekende perioden"
    assert huur["ontbrekende_perioden"] == "jul-sep"
    assert "3 van de 12" in huur["toelichting"]


def test_periodieke_controle_gebruikt_rgs_wanneer_beschikbaar(af_40):
    controles = build_periodieke_controles(af_40)
    afschrijving = controles[controles["controle"] == "Afschrijvingen"].iloc[0]
    assert "RGS-code" in afschrijving["methode"]


def test_periodieke_controle_valt_terug_op_omschrijving(af_32):
    """Zonder bruikbare RGS-code moet de omschrijving het werk doen."""
    controles = build_periodieke_controles(af_32)
    huur = controles[controles["rekening"] == "4000"]
    assert not huur.empty


def test_elke_conclusie_met_signaal_heeft_toelichting(af_40):
    controles = build_periodieke_controles(af_40)
    met_signaal = controles[controles["conclusie"] != "Geen bijzonderheden"]
    assert (met_signaal["toelichting"].str.len() > 0).all()


# --- Ongebruikelijke boekingen ----------------------------------------------


def test_negatieve_omzet_wordt_gesignaleerd(af_40):
    """De creditnota in de fixture staat debet op een omzetrekening."""
    signalen = build_ongebruikelijke_boekingen(af_40)
    assert "Omzetboeking aan de debetzijde" in set(signalen["signaal"])


def test_weekendboeking_wordt_gesignaleerd():
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B"), Account("8000", "Omzet", "P")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    # 4 januari 2025 is een zaterdag.
                    Transaction(
                        "M1",
                        "2025-01-04",
                        1,
                        [Line("1000", "100.00", "D"), Line("8000", "100.00", "C")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("weekend.xaf", build_xaf(spec))
    assert "Boeking op zaterdag of zondag" in set(build_ongebruikelijke_boekingen(af)["signaal"])


def test_geen_signalen_op_een_leeg_bestand():
    spec = AuditfileSpec(accounts=[Account("1000", "Kas", "B")], journals=[])
    af = parse_auditfile("leeg.xaf", build_xaf(spec))
    assert build_ongebruikelijke_boekingen(af).empty
    assert build_periodieke_controles(af).empty
    assert build_fiscale_signalen(af).empty


# --- Relaties ---------------------------------------------------------------


def test_debiteuren_per_relatie(af_40):
    debiteuren = build_relatie_analyse(af_40, "debiteur")
    assert list(debiteuren["relatie"]) == ["D001"]
    assert debiteuren.iloc[0]["naam"] == "Afnemer Alfa BV"
    assert round(debiteuren.iloc[0]["aandeel_pct"], 1) == 100.0


def test_crediteuren_per_relatie(af_40):
    crediteuren = build_relatie_analyse(af_40, "crediteur")
    assert list(crediteuren["relatie"]) == ["C001"]
    assert crediteuren.iloc[0]["naam"] == "Leverancier Beta BV"


def test_concentratie_signaleert_afhankelijkheid(af_40):
    concentratie = build_relatie_concentratie(af_40)
    assert set(concentratie["soort"]) == {"Debiteuren", "Crediteuren"}
    assert (concentratie["signaal"].str.len() > 0).all()


def test_relatieanalyse_zonder_relaties_is_leeg():
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
                        [Line("1000", "100.00", "D"), Line("8000", "100.00", "C")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("zonder_relaties.xaf", build_xaf(spec))
    assert build_relatie_analyse(af, "debiteur").empty
    assert build_relatie_concentratie(af).empty


# --- Balansposten -----------------------------------------------------------


def test_crediteur_met_debetsaldo_wordt_gesignaleerd():
    spec = AuditfileSpec(
        accounts=[
            Account("1600", "Crediteuren", "B", "BSchCre", "BSchCre"),
            Account("1100", "Bank", "B", "BLimBan", "BLimBan"),
        ],
        opening_lines=[],
        journals=[
            Journal(
                "BNK",
                "Bank",
                [
                    Transaction(
                        "B1",
                        "2025-01-01",
                        1,
                        # Te veel betaald: crediteuren komt debet te staan.
                        [Line("1600", "500.00", "D"), Line("1100", "500.00", "C")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("debetcrediteur.xaf", build_xaf(spec))
    signalen = build_balanspost_signalen(af)
    crediteuren = signalen[signalen["categorie"] == "Crediteuren"]
    assert not crediteuren.empty
    assert "debet" in crediteuren.iloc[0]["signaal"]


def test_normale_balans_geeft_geen_signalen(af_40):
    signalen = build_balanspost_signalen(af_40)
    assert "Crediteuren" not in set(signalen["categorie"])


# --- Fiscale signalen -------------------------------------------------------


def test_boetes_krijgen_genuanceerde_toelichting(af_40):
    signalen = build_fiscale_signalen(af_40)
    boetes = signalen[signalen["onderwerp"] == "Boetes en dwangsommen"]
    assert not boetes.empty
    toelichting = boetes.iloc[0]["toelichting"]
    # De uitsluiting moet correct zijn onderbouwd en de uitzondering benoemen.
    assert "art. 3.14 lid 1 onderdelen c en i Wet IB 2001" in toelichting
    assert "art. 8 lid 1 Wet Vpb 1969" in toelichting
    assert "Contractuele boetes" in toelichting


def test_juridische_kosten_worden_gevonden(af_40):
    signalen = build_fiscale_signalen(af_40)
    assert "Juridische kosten" in set(signalen["onderwerp"])


def test_fiscaal_signaal_behoudt_teken_van_bedrag(af_40):
    """Kosten staan debet; dat moet zichtbaar blijven in plaats van absoluut."""
    signalen = build_fiscale_signalen(af_40)
    boetes = signalen[signalen["onderwerp"] == "Boetes en dwangsommen"].iloc[0]
    assert boetes["bedrag"] > 0


# --- Omzet en personeel -----------------------------------------------------


def test_omzet_per_periode_toont_alle_perioden(af_40):
    omzet = build_omzet_per_periode(af_40)
    assert len(omzet) == 12
    assert omzet.iloc[0]["maand"] == "jan"


def test_perioden_zonder_omzet_worden_gemeld(af_40):
    """In de fixture is alleen in de eerste drie perioden omzet geboekt."""
    omzet = build_omzet_per_periode(af_40)
    zonder = omzet[omzet["signaal"] != ""]
    assert len(zonder) == 9


def test_omzet_wordt_positief_getoond(af_40):
    omzet = build_omzet_per_periode(af_40)
    assert omzet["omzet"].sum() > 0


def test_personeelskosten_zonder_fte_schatting(af_40):
    """De tool mag geen aantal medewerkers uit het loonbedrag afleiden."""
    kosten = build_personeelskosten_per_periode(af_40)
    assert "fte" not in " ".join(kosten.columns).lower()
