"""Openstaande bedragen per relatie uit XAF 4.0, en hun aansluiting.

Twee dingen moeten hier hard vastliggen. Ten eerste dat ``opBalDesc`` alleen in
XAF 4.0 als bedrag wordt gelezen: in 3.2 heet hetzelfde element een omschrijving
van de beginbalans van het grootboek, en wie daar op tagnaam leest, haalt een
tekst binnen als openstaand bedrag. Ten tweede dat een verschil met het grootboek
zichtbaar wordt en niet stilzwijgend wordt weggerekend.

Alle bestanden in deze test zijn synthetisch en worden in het geheugen
opgebouwd.
"""
from __future__ import annotations

import pandas as pd

from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Relation,
    Transaction,
    build_xaf,
    demopaar,
    vul_relatiesaldi,
)
from auditfile.parsing import parse_auditfile
from auditfile.relatiesaldi import (
    build_relatiesaldi,
    build_relatiesaldo_aansluiting,
    heeft_relatiesaldi,
)

REKENINGEN = [
    Account("1100", "Bank", "B", "BLimBan"),
    Account("1300", "Debiteuren", "B", "BVorDeb"),
    Account("1600", "Crediteuren", "B", "BSchCre"),
    Account("8000", "Omzet", "P", "WOmzNeh"),
]


def _verkoopjaar():
    """Eén verkoopfactuur van 1.210, onbetaald aan het einde van het jaar."""
    return [
        Journal(
            "VRK",
            "Verkoopboek",
            [
                Transaction(
                    "V1",
                    "2025-01-15",
                    1,
                    [
                        Line("1300", "1210.00", "D", custSupID="D001"),
                        Line("8000", "1210.00", "C"),
                    ],
                )
            ],
        )
    ]


def _bestand(versie: str = "4.0", relaties=None, journalen=None, beginbalans_omschrijving: str = ""):
    spec = AuditfileSpec(
        versie=versie,
        accounts=list(REKENINGEN),
        relations=relaties or [],
        opening_balance_desc=beginbalans_omschrijving,
        journals=journalen or [],
    )
    return parse_auditfile(f"synthetisch_{versie}.xaf", build_xaf(spec))


# --- Inlezen ----------------------------------------------------------------


def test_de_stand_wordt_getekend_ingelezen():
    """Debet positief, credit negatief, net als elk ander bedrag in deze tool.

    Daardoor is een debiteurenstand positief en een crediteurenstand negatief,
    gelijk aan het grootboeksaldo, en hoeft er nergens een teken te worden
    omgekeerd.
    """
    af = _bestand(
        "4.0",
        relaties=[
            Relation("D001", "Afnemer Alfa BV", "C", openstaand_begin="100.00", openstaand_eind="1210.00"),
            Relation(
                "C001",
                "Leverancier Beta BV",
                "S",
                openstaand_begin="200.00",
                openstaand_begin_tp="C",
                openstaand_eind="3000.00",
                openstaand_eind_tp="C",
            ),
        ],
    )
    standen = af.relations.set_index("custSupID")
    assert standen.at["D001", "openstaand_begin"] == 100.00
    assert standen.at["D001", "openstaand_eind"] == 1210.00
    assert standen.at["C001", "openstaand_begin"] == -200.00
    assert standen.at["C001", "openstaand_eind"] == -3000.00


def test_in_xaf_32_blijft_de_stand_leeg():
    """``opBalDesc`` betekent daar iets anders en mag geen bedrag worden.

    In XAF 3.2 is dat element een omschrijving van de beginbalans van het
    grootboek. Zou de parser op tagnaam lezen, dan verscheen die tekst hier als
    openstaand bedrag en zou de tool een analyse aanbieden die nergens op rust.
    """
    af = _bestand(
        "3.2",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1210.00")],
        beginbalans_omschrijving="Beginbalans per 1 januari",
    )
    assert af.relations["openstaand_eind"].isna().all()
    assert af.relations["openstaand_begin"].isna().all()
    assert not heeft_relatiesaldi(af)
    assert build_relatiesaldo_aansluiting(af).empty


def test_een_onleesbaar_bedrag_telt_als_afwezig():
    """Een veld dat er staat maar geen getal is, mag niet als nul doorgaan.

    Nul is een stand; onleesbaar is geen stand. Het verschil bepaalt of de tool
    zegt dat er niets openstaat of dat zij het niet weet.
    """
    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="onbekend")],
    )
    assert af.relations["openstaand_eind"].isna().all()
    assert not heeft_relatiesaldi(af)


# --- Aansluiting op het grootboek -------------------------------------------


def test_de_demo_sluit_aan():
    _, huidig_bytes = demopaar()
    af = parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes)
    aansluiting = build_relatiesaldo_aansluiting(af).set_index("soort")

    assert set(aansluiting.index) == {"debiteur", "crediteur"}
    assert (aansluiting["signaal"] == "").all()
    assert aansluiting.at["debiteur", "verschil_eind"] == 0.0
    assert aansluiting.at["crediteur", "verschil_eind"] == 0.0
    # Een crediteurenstand hoort negatief te zijn, net als het grootboeksaldo.
    assert aansluiting.at["crediteur", "openstaand_eind"] < 0
    assert aansluiting.at["debiteur", "openstaand_eind"] > 0


def test_een_verschil_met_het_grootboek_wordt_benoemd():
    """De stand uit het bestand is 210 lager dan het saldo van de rekening."""
    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1000.00")],
        journalen=_verkoopjaar(),
    )
    rij = build_relatiesaldo_aansluiting(af).set_index("soort").loc["debiteur"]

    assert rij["grootboek_eindsaldo"] == 1210.00
    assert rij["openstaand_eind"] == 1000.00
    assert round(rij["verschil_eind"], 2) == 210.00
    assert rij["signaal"] == "verschil"
    assert "210.00 uiteen" in rij["conclusie"]


def test_zonder_relatierekening_wordt_er_niets_vergeleken():
    """Zonder herkende rekening is er geen aansluiting, en geen nul als uitkomst."""
    spec = AuditfileSpec(
        versie="4.0",
        accounts=[Account("8000", "Omzet", "P", "WOmzNeh")],
        relations=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1210.00")],
    )
    af = parse_auditfile("zonder_relatierekening.xaf", build_xaf(spec))
    rij = build_relatiesaldo_aansluiting(af).set_index("soort").loc["debiteur"]

    assert rij["rekeningen"] == 0
    assert pd.isna(rij["grootboek_eindsaldo"])
    assert rij["signaal"] == "niet mogelijk"
    assert "Geen debiteurenrekening herkend" in rij["conclusie"]


# --- Signalen per relatie ---------------------------------------------------


def test_een_debiteur_met_een_creditsaldo_is_een_signaal():
    af = _bestand(
        "4.0",
        relaties=[
            Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="500.00", openstaand_eind_tp="C")
        ],
        journalen=_verkoopjaar(),
    )
    rij = build_relatiesaldi(af).set_index("relatie").loc["D001"]
    assert rij["soort"] == "debiteur"
    assert "creditsaldo" in rij["signaal"]


def test_een_crediteur_met_een_debetsaldo_is_een_signaal():
    af = _bestand(
        "4.0",
        relaties=[Relation("C001", "Leverancier Beta BV", "S", openstaand_eind="500.00")],
    )
    rij = build_relatiesaldi(af).set_index("relatie").loc["C001"]
    assert rij["soort"] == "crediteur"
    assert "debetsaldo" in rij["signaal"]


def test_het_verloop_wordt_tegen_de_boekingen_gehouden():
    """Beginstand plus de mutaties van het jaar hoort de eindstand te geven."""
    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1000.00")],
        journalen=_verkoopjaar(),
    )
    rij = build_relatiesaldi(af).set_index("relatie").loc["D001"]
    assert rij["mutatie_boekjaar"] == 1210.00
    assert round(rij["verloop_verschil"], 2) == -210.00
    assert "geeft niet de eindstand" in rij["signaal"]


def test_een_sluitend_verloop_geeft_geen_signaal():
    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1210.00")],
        journalen=_verkoopjaar(),
    )
    rij = build_relatiesaldi(af).set_index("relatie").loc["D001"]
    assert rij["verloop_verschil"] == 0.0
    assert rij["signaal"] == ""


def test_zonder_soortcode_beslist_het_teken():
    """Ontbreekt ``custSupTp``, dan blijft alleen de kant van de stand over."""
    af = _bestand(
        "4.0",
        relaties=[
            Relation("R001", "Relatie zonder soort", "", openstaand_eind="1210.00"),
            Relation(
                "R002", "Andere relatie", "", openstaand_eind="800.00", openstaand_eind_tp="C"
            ),
        ],
    )
    soorten = build_relatiesaldi(af).set_index("relatie")["soort"].to_dict()
    assert soorten == {"R001": "debiteur", "R002": "crediteur"}


# --- Doorwerking naar de bevindingen ----------------------------------------


def test_het_verschil_komt_in_de_bevindingen():
    from auditfile.findings import verzamel_bevindingen
    from auditfile.integrity import WAARSCHUWING

    af = _bestand(
        "4.0",
        relaties=[Relation("D001", "Afnemer Alfa BV", "C", openstaand_eind="1000.00")],
        journalen=_verkoopjaar(),
    )
    bevindingen = verzamel_bevindingen(af)
    rij = bevindingen[
        bevindingen["onderwerp"] == "Openstaande bedragen debiteuren sluiten niet aan op het grootboek"
    ]
    assert len(rij) == 1
    assert rij.iloc[0]["ernst"] == WAARSCHUWING
    assert round(rij.iloc[0]["bedrag"], 2) == 210.00
    assert rij.iloc[0]["pagina"] == "Relaties"


def test_zonder_relatiesaldi_geen_bevinding():
    """Dat het niet kan, staat al bij de bestandsgegevens en hoort niet dubbel.

    De categorie Relaties blijft wel bestaan: de concentratie per relatie werkt
    ook zonder openstaande bedragen. Alleen de aansluiting hoort te ontbreken.
    """
    from auditfile.findings import verzamel_bevindingen

    af = _bestand("3.2", relaties=[Relation("D001", "Afnemer Alfa BV", "C")], journalen=_verkoopjaar())
    onderwerpen = verzamel_bevindingen(af)["onderwerp"]
    assert not onderwerpen.str.contains("Openstaande bedragen").any()
    assert not onderwerpen.str.contains("Verloop van de openstaande bedragen").any()


# --- Demodata ---------------------------------------------------------------


def test_vul_relatiesaldi_laat_de_bron_ongemoeid():
    """De specs zijn testfixtures met sessiebereik; muteren zou doorwerken."""
    spec = AuditfileSpec(
        versie="4.0",
        accounts=list(REKENINGEN),
        relations=[Relation("D001", "Afnemer Alfa BV", "C")],
        journals=_verkoopjaar(),
    )
    gevuld = vul_relatiesaldi(spec)
    assert spec.relations[0].openstaand_eind == ""
    assert gevuld.relations[0].openstaand_eind == "1210.00"
