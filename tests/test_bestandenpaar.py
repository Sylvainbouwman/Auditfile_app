"""Horen de twee auditfiles bij elkaar, en sluit de jaarovergang aan?

Twee auditfiles van verschillende ondernemingen leveren een plausibel ogende
jaarvergelijking op. Dat is gevaarlijker dan een lege uitkomst, dus moet de tool
het zeggen. Alle bestanden hier zijn synthetisch.
"""
from __future__ import annotations

from auditfile.comparison import (
    build_jaarovergang,
    build_jaarovergang_verloop,
    controleer_bestandenpaar,
    jaarovergang_sluit_aan,
)
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    OpeningLine,
    Transaction,
    build_xaf,
)
from auditfile.integrity import IN_ORDE, KRITIEK, NIET_MOGELIJK, WAARSCHUWING
from auditfile.parsing import parse_auditfile

REKENINGEN = [
    Account("0500", "Eigen vermogen", "B"),
    Account("1100", "Bank", "B"),
    Account("4000", "Kosten", "P"),
    Account("8000", "Omzet", "P"),
]


def _auditfile(
    boekjaar: str = "2025",
    naam: str = "Testbedrijf Synthetisch BV",
    btw_nummer: str = "NL000000000B01",
    kvk: str = "00000000",
    beginsaldi: list[OpeningLine] | None = None,
    resultaat: str = "1000.00",
):
    """Een sluitend auditfile met een winst van ``resultaat``."""
    spec = AuditfileSpec(
        company_name=naam,
        tax_reg_ident=btw_nummer,
        commerce_nr=kvk,
        fiscal_year=boekjaar,
        start_date=f"{boekjaar}-01-01",
        end_date=f"{boekjaar}-12-31",
        accounts=list(REKENINGEN),
        opening_lines=beginsaldi or [],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "V1",
                        f"{boekjaar}-06-30",
                        6,
                        [Line("1100", resultaat, "D"), Line("8000", resultaat, "C")],
                    )
                ],
            )
        ],
    )
    return parse_auditfile(f"synthetisch_{boekjaar}.xaf", build_xaf(spec))


def _ernst(bevindingen, controle: str) -> str:
    return bevindingen.loc[bevindingen["controle"] == controle, "ernst"].iloc[0]


# --- Hoort het paar bij elkaar? --------------------------------------------


def test_een_kloppend_paar_geeft_geen_bevindingen():
    bevindingen = controleer_bestandenpaar(_auditfile("2024"), _auditfile("2025"))
    assert set(bevindingen["ernst"]) == {IN_ORDE}


def test_verschillende_ondernemingen_zijn_kritiek():
    bevindingen = controleer_bestandenpaar(
        _auditfile("2024", naam="Eerste Synthetische BV", btw_nummer="NL000000000B01"),
        _auditfile("2025", naam="Tweede Synthetische BV", btw_nummer="NL000000000B02"),
    )
    assert _ernst(bevindingen, "Zelfde onderneming") == KRITIEK


def test_zonder_identificatie_is_de_onderneming_niet_vast_te_stellen():
    bevindingen = controleer_bestandenpaar(
        _auditfile("2024", naam="", btw_nummer="", kvk=""), _auditfile("2025")
    )
    assert _ernst(bevindingen, "Zelfde onderneming") == NIET_MOGELIJK


def test_twee_keer_hetzelfde_bestand_is_kritiek():
    af = _auditfile("2025")
    bevindingen = controleer_bestandenpaar(af, af)
    assert _ernst(bevindingen, "Twee verschillende bestanden") == KRITIEK
    assert _ernst(bevindingen, "Aansluitende boekjaren") == KRITIEK


def test_verwisselde_bestanden_zijn_kritiek():
    bevindingen = controleer_bestandenpaar(_auditfile("2025"), _auditfile("2024"))
    assert _ernst(bevindingen, "Aansluitende boekjaren") == KRITIEK
    assert _ernst(bevindingen, "Periodes overlappen niet") == KRITIEK


def test_een_gat_tussen_de_boekjaren_is_een_waarschuwing():
    bevindingen = controleer_bestandenpaar(_auditfile("2023"), _auditfile("2025"))
    assert _ernst(bevindingen, "Aansluitende boekjaren") == WAARSCHUWING


def test_verschillende_valuta_is_kritiek():
    """De demogenerator schrijft altijd EUR, dus de header wordt hier aangepast."""
    vorig = _auditfile("2024")
    huidig = _auditfile("2025")
    huidig.header["curCode"] = "USD"
    bevindingen = controleer_bestandenpaar(vorig, huidig)
    assert _ernst(bevindingen, "Zelfde valuta") == KRITIEK


# --- Jaarovergang -----------------------------------------------------------


def test_aansluitende_jaarovergang_sluit_aan():
    """De winst van vorig jaar hoort in het eigen vermogen van dit jaar te staan.

    Vorig jaar: geen beginbalans, winst 1.000, dus bank 1.000 debet en geen eigen
    vermogen. Dit jaar begint met bank 1.000 debet en eigen vermogen 1.000
    credit: de winst is bestemd.
    """
    vorig = _auditfile("2024")
    huidig = _auditfile(
        "2025",
        beginsaldi=[OpeningLine("1100", "1000.00", "D"), OpeningLine("0500", "1000.00", "C")],
    )
    verloop = build_jaarovergang_verloop(vorig, huidig).set_index("post")

    assert round(verloop.loc["Verschil buiten het eigen vermogen", "bedrag"], 2) == 0.00
    assert round(verloop.loc["Resultaat 2024", "bedrag"], 2) == -1000.00
    assert round(verloop.loc["Toename van het eigen vermogen", "bedrag"], 2) == -1000.00
    assert round(verloop.loc["Onverklaard in het eigen vermogen", "bedrag"], 2) == 0.00
    assert jaarovergang_sluit_aan(build_jaarovergang_verloop(vorig, huidig))


def test_ontbrekende_beginbalans_valt_op():
    """Zonder overgenomen beginbalans moet de controle klagen.

    Dit is het geval waar een vergelijking van de balanstotalen blind voor is:
    een sluitende beginbalans telt altijd op tot nul en de eindbalans van vorig
    jaar altijd tot het resultaat met omgekeerd teken. De splitsing tussen het
    eigen vermogen en de rest maakt het verschil wel zichtbaar.
    """
    vorig = _auditfile("2024")
    huidig = _auditfile("2025")
    verloop = build_jaarovergang_verloop(vorig, huidig).set_index("post")

    assert round(verloop.loc["Balans 2024 buiten het eigen vermogen", "bedrag"], 2) == 1000.00
    assert round(verloop.loc["Beginbalans 2025 buiten het eigen vermogen", "bedrag"], 2) == 0.00
    assert round(verloop.loc["Verschil buiten het eigen vermogen", "bedrag"], 2) == -1000.00
    assert round(verloop.loc["Onverklaard in het eigen vermogen", "bedrag"], 2) == 1000.00
    assert not jaarovergang_sluit_aan(build_jaarovergang_verloop(vorig, huidig))


def test_storting_buiten_het_resultaat_blijft_onverklaard():
    """Vermogen dat niet uit het resultaat komt, hoort te worden benoemd."""
    vorig = _auditfile("2024")
    huidig = _auditfile(
        "2025",
        beginsaldi=[
            OpeningLine("1100", "1000.00", "D"),
            OpeningLine("0500", "1500.00", "C"),
            OpeningLine("1100", "500.00", "D"),
        ],
    )
    verloop = build_jaarovergang_verloop(vorig, huidig)
    per_post = verloop.set_index("post")

    assert round(per_post.loc["Verschil buiten het eigen vermogen", "bedrag"], 2) == 500.00
    assert round(per_post.loc["Onverklaard in het eigen vermogen", "bedrag"], 2) == -500.00
    assert not jaarovergang_sluit_aan(verloop)


def test_jaarovergang_per_rekening_benoemt_het_verschil():
    vorig = _auditfile("2024")
    huidig = _auditfile("2025", beginsaldi=[OpeningLine("1100", "400.00", "D")])
    overgang = build_jaarovergang(vorig, huidig).set_index("rekening")

    assert round(overgang.loc["1100", "eindsaldo_vorig"], 2) == 1000.00
    assert round(overgang.loc["1100", "beginsaldo_huidig"], 2) == 400.00
    assert round(overgang.loc["1100", "verschil"], 2) == -600.00
    assert overgang.loc["1100", "signaal"] == "Beginsaldo wijkt af van de eindstand"


def test_resultaatrekeningen_horen_niet_in_de_jaarovergang():
    """Een resultaatrekening heeft geen beginsaldo; die hoort er niet in."""
    overgang = build_jaarovergang(_auditfile("2024"), _auditfile("2025"))
    assert "8000" not in set(overgang["rekening"])
    assert "1100" in set(overgang["rekening"])


# --- Demodata ---------------------------------------------------------------


def test_het_demopaar_sluit_aan():
    """De demo moet laten zien hoe een kloppende jaarovergang eruitziet.

    Anders toont de demomodus een verschil dat alleen aan de demodata ligt, en
    dat leert de gebruiker het verkeerde.
    """
    from auditfile.demo import demopaar

    vorig_bytes, huidig_bytes = demopaar()
    vorig = parse_auditfile("demo_vorig_jaar.xaf", vorig_bytes)
    huidig = parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes)

    assert set(controleer_bestandenpaar(vorig, huidig)["ernst"]) == {IN_ORDE}
    assert jaarovergang_sluit_aan(build_jaarovergang_verloop(vorig, huidig))

    # Alleen het eigen vermogen mag afwijken, en dan met de reden erbij.
    overgang = build_jaarovergang(vorig, huidig)
    signalen = set(overgang.loc[overgang["signaal"] != "", "signaal"])
    assert signalen <= {"Resultaatbestemming eigen vermogen"}
