"""Wat laat een auditfile toe, en wat niet?

Bijna alles in XAF is optioneel, en 3.2 en 4.0 verschillen inhoudelijk. Deze
laag stelt per bestand vast wat er werkelijk in staat. De belangrijkste test is
niet dat een blok bestaat, maar dat de tool "niet mogelijk" zegt waar dat het
juiste antwoord is. Alle bestanden hier zijn synthetisch.
"""
from __future__ import annotations

from auditfile.capability import (
    NIVEAU_GEEN,
    NIVEAU_RECONSTRUCTIE,
    NIVEAU_RELATIESALDO,
    build_bestandsprofiel,
    build_relatiedekking,
    openstaande_posten_niveau,
)
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Relation,
    Transaction,
    build_xaf,
    demopaar,
)
from auditfile.parsing import parse_auditfile

REKENINGEN = [
    Account("1100", "Bank", "B", "BLimBan"),
    Account("1300", "Debiteuren", "B", "BVorDeb"),
    Account("1600", "Crediteuren", "B", "BSchCre"),
    Account("8000", "Omzet", "P", "WOmzNeh"),
]


def _bestand(versie: str = "4.0", relaties=None, journalen=None, beginbalans_omschrijving: str = ""):
    spec = AuditfileSpec(
        versie=versie,
        accounts=list(REKENINGEN),
        relations=relaties if relaties is not None else [Relation("D001", "Afnemer Alfa BV", "C")],
        opening_balance_desc=beginbalans_omschrijving,
        journals=journalen or [],
    )
    return parse_auditfile(f"synthetisch_{versie}.xaf", build_xaf(spec))


def _verkoop(referentie_op_betaling: bool):
    """Twee facturen met een ontvangst; de referentie op één of op beide zijden."""
    transacties = []
    for nummer in (1, 2):
        transacties.append(
            Transaction(
                f"V{nummer}",
                f"2025-0{nummer}-15",
                nummer,
                [
                    Line("1300", "1210.00", "D", custSupID="D001", invRef=f"F00{nummer}"),
                    Line("8000", "1210.00", "C"),
                ],
            )
        )
        transacties.append(
            Transaction(
                f"B{nummer}",
                f"2025-0{nummer}-28",
                nummer,
                [
                    Line("1100", "1210.00", "D"),
                    Line(
                        "1300",
                        "1210.00",
                        "C",
                        custSupID="D001",
                        invRef=f"F00{nummer}" if referentie_op_betaling else "",
                    ),
                ],
            )
        )
    return [Journal("VRK", "Verkoopboek", transacties)]


# --- Tellen van de blokken --------------------------------------------------


def test_de_omschrijving_van_de_beginbalans_is_geen_relatiesaldo():
    """`opBalDesc` betekent in 3.2 iets anders dan in 4.0.

    In XAF 3.2 is het een omschrijving van de beginbalans van het grootboek, in
    XAF 4.0 een openstaand bedrag per relatie. Wie op tagnaam telt, ziet in een
    3.2-bestand een omschrijving als openstaand bedrag en concludeert dat er een
    openstaandenanalyse mogelijk is.
    """
    af = _bestand("3.2", beginbalans_omschrijving="Beginbalans per 1 januari")
    assert af.blokken["relatie_opBalDesc"] == 0
    assert af.blokken["relatie_clBalDesc"] == 0
    assert openstaande_posten_niveau(af)[0] == NIVEAU_GEEN


def test_relatiesaldi_van_versie_40_worden_geteld():
    af = _bestand(
        "4.0",
        relaties=[
            Relation(
                "D001",
                "Afnemer Alfa BV",
                "C",
                openstaand_begin="333.33",
                openstaand_eind="444.44",
            ),
            Relation("C001", "Leverancier Beta BV", "S"),
        ],
    )
    assert af.blokken["relatie_opBalDesc"] == 1
    assert af.blokken["relatie_clBalDesc"] == 1


def test_zonder_subadministratie_blijven_de_tellingen_nul():
    af = _bestand("3.2")
    for sleutel in ("obSbLine", "sbLine", "obSbLine_invDueDt", "sbLine_invDueDt"):
        assert af.blokken[sleutel] == 0


# --- Het bewijsniveau -------------------------------------------------------


def test_een_gevuld_relatiesaldo_geeft_niveau_drie():
    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="444.44")],
    )
    niveau, uitleg = openstaande_posten_niveau(af)
    assert niveau == NIVEAU_RELATIESALDO
    assert "eindstand per relatie" in uitleg


def test_referentie_op_beide_zijden_geeft_niveau_vier():
    """Dan is per factuur te salderen tot een openstaand bedrag."""
    af = _bestand("4.0", journalen=_verkoop(referentie_op_betaling=True))
    niveau, uitleg = openstaande_posten_niveau(af)
    assert niveau == NIVEAU_RECONSTRUCTIE
    assert "betalingstermijn" in uitleg


def test_referentie_alleen_op_de_factuur_geeft_geen_niveau():
    """De kern van deze laag.

    Salderen per factuurreferentie levert dan niets af: elke factuur blijft
    volledig openstaan. Dat oogt als een complete openstaandenlijst en is onwaar.
    """
    af = _bestand("4.0", journalen=_verkoop(referentie_op_betaling=False))
    niveau, uitleg = openstaande_posten_niveau(af)
    assert niveau == NIVEAU_GEEN
    assert "factuurzijde" in uitleg

    dekking = build_relatiedekking(af).set_index("soort")
    # Alle vier de regels dragen een relatie-id, de helft een referentie.
    assert round(dekking.loc["debiteur", "met_relatie_pct"], 0) == 100
    assert round(dekking.loc["debiteur", "met_factuurreferentie_pct"], 0) == 50
    assert round(dekking.loc["debiteur", "gekoppeld_pct"], 0) == 0


def test_een_bestand_zonder_relatiegegevens_geeft_geen_niveau():
    af = _bestand("4.0", relaties=[])
    niveau, _ = openstaande_posten_niveau(af)
    assert niveau == NIVEAU_GEEN


# --- Het profiel ------------------------------------------------------------


def test_het_profiel_benoemt_aanwezig_en_dekking():
    _, huidig_bytes = demopaar()
    af = parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes)
    profiel = build_bestandsprofiel(af).set_index("gegeven")

    assert bool(profiel.loc["Grootboekrekeningen", "aanwezig"])
    assert round(profiel.loc["RGS-codes", "dekking_pct"], 0) == 100
    assert not bool(profiel.loc["Subadministratie mutaties (sbLine, alleen 3.2)", "aanwezig"])
    # Het demobestand van het huidige jaar is XAF 4.0 en vult de openstaande
    # bedragen per relatie; het bestand van vorig jaar is 3.2 en kent ze niet.
    assert bool(profiel.loc["Openstaand bedrag per relatie (clBalDesc, alleen 4.0)", "aanwezig"])
    assert round(profiel.loc["Openstaand bedrag per relatie (clBalDesc, alleen 4.0)", "dekking_pct"], 0) == 100


def test_de_dekking_wordt_per_relatiesoort_gemeten():
    af = _bestand("4.0", journalen=_verkoop(referentie_op_betaling=True))
    dekking = build_relatiedekking(af)
    assert set(dekking["soort"]) == {"debiteur", "crediteur"}
    # Zonder crediteurenboekingen hoort daar geen conclusie over dekking te staan.
    crediteur = dekking.set_index("soort").loc["crediteur"]
    assert crediteur["regels"] == 0
    assert "Geen crediteurenrekening herkend" in crediteur["conclusie"]


def test_bevindingen_melden_dat_de_analyse_niet_mogelijk_is():
    from auditfile.findings import verzamel_bevindingen
    from auditfile.integrity import NIET_MOGELIJK

    af = _bestand("4.0", journalen=_verkoop(referentie_op_betaling=False))
    bevindingen = verzamel_bevindingen(af)
    rij = bevindingen[bevindingen["onderwerp"] == "Openstaande posten niet te bepalen"]
    assert len(rij) == 1
    assert rij.iloc[0]["ernst"] == NIET_MOGELIJK
