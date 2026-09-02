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
from auditfile.controls import _selecteer
from auditfile.parsing import parse_auditfile
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    OpeningLine,
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


def test_omzetbelasting_telt_niet_als_omzet():
    """Zonder RGS-codes valt de selectie terug op de omschrijving.

    De zoekterm "omzet" vindt dan ook "Omzetbelasting". Het rekeningtype uit het
    auditfile (B of P) moet die balansrekening buiten de omzet houden.
    """
    spec = AuditfileSpec(
        versie="3.2",
        accounts=[
            Account("1300", "Debiteuren", "B"),
            Account("1800", "Omzetbelasting hoog tarief", "B"),
            Account("8000", "Omzet hoog tarief", "P"),
        ],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "V1",
                        "2025-01-31",
                        1,
                        [
                            Line("1300", "1210.00", "D"),
                            Line("8000", "1000.00", "C"),
                            Line("1800", "210.00", "C"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("zonder_rgs.xaf", build_xaf(spec))
    assert set(af.accounts["RGSbron"]) == {""}, "dit bestand hoort geen RGS-codes te hebben"

    per_periode = build_omzet_per_periode(af)
    januari = per_periode[per_periode["periode"] == 1].iloc[0]
    assert round(float(januari["omzet"]), 2) == 1000.00


def _gedeeltelijk_gecodeerd():
    """Een schema waarin maar een deel van de rekeningen een RGS-code heeft."""
    return AuditfileSpec(
        accounts=[
            Account("1300", "Debiteuren", "B", "BVorDeb"),
            Account("1800", "Omzetbelasting", "B", "BSchObr"),
            Account("8000", "Omzet hoog tarief", "P", "WOmzNeh"),
            Account("8100", "Omzet laag tarief", "P"),
        ],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "V1",
                        "2025-01-31",
                        1,
                        [
                            Line("1300", "2100.00", "D"),
                            Line("8000", "1000.00", "C"),
                            Line("8100", "1000.00", "C"),
                            Line("1800", "100.00", "C"),
                        ],
                    )
                ],
            )
        ],
    )


def test_niet_gecodeerde_rekening_valt_niet_buiten_de_selectie():
    """De terugval op de omschrijving geldt per rekening, niet per controle.

    Zodra ergens in het schema een RGS-code stond, schakelde de hele controle
    over op RGS en vielen de niet-gecodeerde rekeningen weg. Bij een
    gedeeltelijk gecodeerd schema miste de omzetanalyse dan halve omzet.
    """
    af = parse_auditfile("gedeeltelijk.xaf", build_xaf(_gedeeltelijk_gecodeerd()))
    per_periode = build_omzet_per_periode(af)
    januari = per_periode[per_periode["periode"] == 1].iloc[0]
    assert round(float(januari["omzet"]), 2) == 2000.00


def test_de_gebruikte_methode_wordt_benoemd():
    af = parse_auditfile("gedeeltelijk.xaf", build_xaf(_gedeeltelijk_gecodeerd()))
    _, methode = _selecteer(af.lines, "WOmz", r"omzet|opbrengst", rekeningtype="P")
    assert methode == "RGS-code en omschrijving"


def test_rgs_code_blijft_beslissend_waar_hij_staat():
    """Een gecodeerde rekening wordt niet alsnog op haar naam meegenomen.

    De omzetbelastingrekening heeft een eigen RGS-code die geen omzet is. Dat de
    naam "omzet" bevat mag haar niet in de omzetselectie brengen, ook niet nu de
    omschrijving als terugval bestaat.
    """
    af = parse_auditfile("gedeeltelijk.xaf", build_xaf(_gedeeltelijk_gecodeerd()))
    masker, _ = _selecteer(af.lines, "WOmz", r"omzet|opbrengst")
    assert "1800" not in set(af.lines.loc[masker, "line_accID"])


def _relatiebestand():
    """Eén debiteur die factureert en deels betaalt, plus een crediteur.

    De debiteurenrekening heeft een beginsaldo, zodat het verschil tussen de
    netto mutatie en het openstaande saldo zichtbaar is.
    """
    return AuditfileSpec(
        accounts=[
            Account("1100", "Bank", "B", "BLimBan"),
            Account("1300", "Debiteuren", "B", "BVorDeb"),
            Account("1600", "Crediteuren", "B", "BSchCre"),
            Account("4000", "Kosten", "P", "WBedAlg"),
            Account("8000", "Omzet", "P", "WOmzNeh"),
        ],
        relations=[Relation("D001", "Afnemer Alfa BV", "C"), Relation("C001", "Leverancier Beta BV", "S")],
        opening_lines=[OpeningLine("1300", "5000.00", "D"), OpeningLine("1600", "5000.00", "C")],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "V1",
                        "2025-01-31",
                        1,
                        [
                            Line("1300", "1000.00", "D", custSupID="D001"),
                            Line("8000", "1000.00", "C"),
                        ],
                    ),
                    Transaction(
                        "V2",
                        "2025-02-28",
                        2,
                        [
                            Line("1100", "400.00", "D"),
                            Line("1300", "400.00", "C", custSupID="D001"),
                        ],
                    ),
                ],
            ),
            Journal(
                "INK",
                "Inkoopboek",
                [
                    Transaction(
                        "I1",
                        "2025-03-31",
                        3,
                        [
                            Line("4000", "700.00", "D"),
                            Line("1600", "700.00", "C", custSupID="C001"),
                        ],
                    )
                ],
            ),
        ],
    )


def test_relatieanalyse_scheidt_factureren_van_afwikkelen():
    """Een klant die betaalt mag niet uit het overzicht verdwijnen.

    De netto mutatie van deze debiteur is 600, maar er is voor 1.000
    gefactureerd. Op de netto mutatie afgaan zou de omvang van de relatie
    onderschatten, en bij volledige betaling zelfs op nul uitkomen.
    """
    af = parse_auditfile("relaties.xaf", build_xaf(_relatiebestand()))
    debiteuren = build_relatie_analyse(af, "debiteur").set_index("relatie")

    assert round(debiteuren.loc["D001", "gefactureerd"], 2) == 1000.00
    assert round(debiteuren.loc["D001", "afgewikkeld"], 2) == 400.00
    assert round(debiteuren.loc["D001", "netto_mutatie"], 2) == 600.00


def test_netto_mutatie_is_niet_het_openstaande_saldo():
    """Het beginsaldo zit er niet in; dat moet uit de kolomnaam blijken.

    Het eindsaldo van de debiteurenrekening is 5.600, de netto mutatie 600. De
    analyse claimt dus geen openstaande post.
    """
    af = parse_auditfile("relaties.xaf", build_xaf(_relatiebestand()))
    eindsaldo = float(af.saldo.loc[af.saldo["rekening"] == "1300", "eindsaldo"].iloc[0])
    netto = float(build_relatie_analyse(af, "debiteur").iloc[0]["netto_mutatie"])

    assert round(eindsaldo, 2) == 5600.00
    assert round(netto, 2) == 600.00
    assert "openstaand" not in " ".join(build_relatie_analyse(af, "debiteur").columns)


def test_relatieanalyse_kijkt_alleen_naar_de_relatierekeningen():
    """Alleen de debiteurenrekening telt mee, niet elke balansrekening."""
    af = parse_auditfile("relaties.xaf", build_xaf(_relatiebestand()))
    debiteuren = build_relatie_analyse(af, "debiteur")
    crediteuren = build_relatie_analyse(af, "crediteur")

    assert debiteuren.iloc[0]["methode"] == "RGS-code (debiteurenrekening)"
    assert list(debiteuren["relatie"]) == ["D001"]
    assert list(crediteuren["relatie"]) == ["C001"]
    assert round(crediteuren.iloc[0]["gefactureerd"], 2) == 700.00
