"""Het uniforme bevindingenmodel.

Elke controle heeft zijn eigen tabelvorm. Deze laag zet ze om naar één
structuur, zodat er materialiteit op kan en er een reviewmemorandum uit kan
komen. Alle bestanden hier zijn synthetisch.
"""
from __future__ import annotations

import pandas as pd

from auditfile import vat
from auditfile.demo import (
    DEMO_RATIO_BTW,
    DEMO_RATIO_OMZET,
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Transaction,
    build_xaf,
    demopaar,
)
from auditfile.findings import (
    BEVINDING_COLUMNS,
    SIGNAAL,
    Bevinding,
    Materialiteit,
    TE_BEOORDELEN,
    grondslag_omzet,
    naar_frame,
    openstaande_bevindingen,
    pas_review_toe,
    samenvatting_per_ernst,
    verzamel_bevindingen,
)
from auditfile.integrity import IN_ORDE, KRITIEK, NIET_MOGELIJK, WAARSCHUWING
from auditfile.parsing import parse_auditfile


def _demopaar():
    vorig_bytes, huidig_bytes = demopaar()
    return (
        parse_auditfile("demo_vorig_jaar.xaf", vorig_bytes),
        parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes),
    )


# --- Het model --------------------------------------------------------------


def test_de_sleutel_is_stabiel_en_onderscheidend():
    """Aan de sleutel hangt straks de reviewstatus; die mag niet verschuiven."""
    eerste = Bevinding("Btw", "Rubriek 1a: verschil", SIGNAAL, bedrag=100.0)
    zelfde = Bevinding("Btw", "Rubriek 1a: verschil", KRITIEK, bedrag=900.0)
    andere = Bevinding("Btw", "Rubriek 1b: verschil", SIGNAAL, bedrag=100.0)

    # Ernst en bedrag zitten er bewust niet in: een gewijzigd bedrag mag de
    # status niet weggooien.
    assert eerste.sleutel == zelfde.sleutel
    assert eerste.sleutel != andere.sleutel


def test_rekening_maakt_bevindingen_van_elkaar_te_onderscheiden():
    eerste = Bevinding("Balansposten", "Saldo aan de verkeerde kant", WAARSCHUWING, rekening="1300")
    tweede = Bevinding("Balansposten", "Saldo aan de verkeerde kant", WAARSCHUWING, rekening="1600")
    assert eerste.sleutel != tweede.sleutel


def test_sortering_zet_het_zwaarste_bovenaan():
    frame = naar_frame(
        [
            Bevinding("A", "klein signaal", SIGNAAL, bedrag=10.0),
            Bevinding("B", "kritiek", KRITIEK, bedrag=1.0),
            Bevinding("C", "groot signaal", SIGNAAL, bedrag=5000.0),
            Bevinding("D", "waarschuwing", WAARSCHUWING, bedrag=2.0),
        ]
    )
    assert list(frame["ernst"]) == [KRITIEK, WAARSCHUWING, SIGNAAL, SIGNAAL]
    # Binnen dezelfde ernst het grootste bedrag eerst.
    signalen = frame[frame["ernst"] == SIGNAAL]
    assert list(signalen["onderwerp"]) == ["groot signaal", "klein signaal"]


def test_bedragen_blijven_getallen():
    frame = naar_frame([Bevinding("A", "zonder bedrag", SIGNAAL), Bevinding("B", "met", SIGNAAL, bedrag=5.0)])
    assert pd.api.types.is_numeric_dtype(frame["bedrag"])
    assert list(frame.columns) == BEVINDING_COLUMNS


def test_een_lege_lijst_geeft_een_lege_tabel_met_dezelfde_kolommen():
    frame = naar_frame([])
    assert frame.empty
    assert list(frame.columns) == BEVINDING_COLUMNS
    assert samenvatting_per_ernst(frame) == {
        KRITIEK: 0,
        WAARSCHUWING: 0,
        SIGNAAL: 0,
        NIET_MOGELIJK: 0,
    }


# --- Materialiteit ----------------------------------------------------------


def test_de_hoogste_van_de_twee_grenzen_geldt():
    klein = Materialiteit(absoluut=1000.0, relatief_pct=1.0, grondslag=50_000.0)
    groot = Materialiteit(absoluut=1000.0, relatief_pct=1.0, grondslag=500_000.0)
    assert klein.drempel == 1000.0  # 1% van 50.000 is 500, dus het vaste bedrag
    assert groot.drempel == 5000.0  # 1% van 500.000 is meer dan 1.000


def test_bevindingen_onder_de_drempel_worden_gemarkeerd_niet_weggelaten():
    """Weglaten zou betekenen dat de tool bepaalt wat de gebruiker niet ziet."""
    frame = naar_frame(
        [
            Bevinding("A", "groot", SIGNAAL, bedrag=5000.0),
            Bevinding("A", "klein", SIGNAAL, bedrag=50.0),
        ],
        Materialiteit(absoluut=1000.0, relatief_pct=0.0),
    )
    assert len(frame) == 2
    assert dict(zip(frame["onderwerp"], frame["boven_drempel"])) == {"groot": True, "klein": False}


def test_een_bevinding_zonder_bedrag_valt_nooit_onder_de_drempel():
    """Wat niet te wegen is, mag niet stilzwijgend als onbelangrijk gelden."""
    frame = naar_frame(
        [Bevinding("A", "geen bedrag", NIET_MOGELIJK)], Materialiteit(absoluut=1_000_000.0)
    )
    assert bool(frame.iloc[0]["boven_drempel"])


def test_grondslag_is_de_omzet_van_het_boekjaar():
    _, huidig = _demopaar()
    # De demo boekt 1.000 hoog, 100 laag en een creditnota van 200, plus de
    # verkoop van handelsgoederen die de ratio-analyse nodig heeft.
    assert round(grondslag_omzet(huidig), 2) == round(900.00 + DEMO_RATIO_OMZET, 2)


def test_zonder_omzetrekening_is_er_geen_grondslag():
    """Een verzonnen grondslag zou de drempel onnavolgbaar maken."""
    spec = AuditfileSpec(
        accounts=[Account("1000", "Kas", "B", "BLimKas"), Account("4000", "Kosten", "P", "WBedAlg")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "M1",
                        "2025-01-01",
                        1,
                        [Line("4000", "100.00", "D"), Line("1000", "100.00", "C")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("zonder_omzet.xaf", build_xaf(spec))
    assert grondslag_omzet(af) == 0.0
    assert Materialiteit(absoluut=1000.0, relatief_pct=5.0, grondslag=0.0).drempel == 1000.0


# --- Verzamelen -------------------------------------------------------------


def test_alle_categorieen_komen_uit_de_verzamelaar():
    vorig, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, vorig)
    categorieen = set(bevindingen["categorie"])

    for verwacht in ("Btw", "Boekingen", "Fiscaal", "Jaarvergelijking", "Periodieke lasten"):
        assert verwacht in categorieen, f"{verwacht} ontbreekt: {sorted(categorieen)}"
    assert (bevindingen["pagina"].str.len() > 0).all()
    assert bevindingen["sleutel"].is_unique


def test_geen_bevinding_met_ernst_in_orde():
    """Een controle zonder afwijking is geen bevinding."""
    vorig, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, vorig)
    assert IN_ORDE not in set(bevindingen["ernst"])


def test_zonder_vorig_jaar_blijven_de_paarcontroles_weg():
    _, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig)
    assert "Bestandenpaar" not in set(bevindingen["categorie"])
    assert "Jaarovergang" not in set(bevindingen["categorie"])
    assert not bevindingen.empty


def test_een_kritieke_bevinding_komt_bovenaan():
    """Twee keer hetzelfde bestand: dat moet de lijst openen."""
    _, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, huidig)
    assert bevindingen.iloc[0]["ernst"] == KRITIEK
    assert "Bestandenpaar" in set(bevindingen.loc[bevindingen["ernst"] == KRITIEK, "categorie"])


def test_onbeoordeelde_btw_indeling_is_een_waarschuwing():
    """Zolang de rubrieken op een voorstel staan, is de btw-positie voorlopig."""
    vorig, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, vorig)
    rij = bevindingen[bevindingen["onderwerp"] == "Btw-indeling nog niet beoordeeld"]
    assert len(rij) == 1
    assert rij.iloc[0]["ernst"] == WAARSCHUWING

    # Na vastleggen van de indeling hoort die bevinding te verdwijnen.
    gebruik = vat.build_vat_usage(huidig)
    mapping = dict(zip(gebruik["btw_code"], gebruik["rubriek_voorstel"]))
    beoordeeld = verzamel_bevindingen(
        huidig, vorig, gebruik=vat.pas_mapping_toe(gebruik, mapping)
    )
    assert "Btw-indeling nog niet beoordeeld" not in set(beoordeeld["onderwerp"])


def test_ontbrekende_aangifte_is_niet_mogelijk_in_plaats_van_in_orde():
    vorig, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, vorig)
    rij = bevindingen[bevindingen["onderwerp"] == "Aansluiting met de aangifte niet gemaakt"]
    assert len(rij) == 1
    assert rij.iloc[0]["ernst"] == NIET_MOGELIJK


def test_een_verschil_met_de_aangifte_wordt_een_waarschuwing():
    vorig, huidig = _demopaar()
    gebruik = vat.pas_mapping_toe(vat.build_vat_usage(huidig))
    # De btw in rubriek 1a is 210 min 42 plus de btw over de verkoop van
    # handelsgoederen. De aangifte ligt daar 68 onder, zodat het verschil is wat
    # deze test wil zien en niet de omvang van de demodata.
    aangegeven_1a = 168.0 + DEMO_RATIO_BTW - 68.0
    bevindingen = verzamel_bevindingen(
        huidig, vorig, gebruik=gebruik, aangifte={"1a": aangegeven_1a, "1b": 9.0, "5b": 2520.0}
    )
    rubriek_1a = bevindingen[bevindingen["onderwerp"].str.startswith("Rubriek 1a")]
    assert len(rubriek_1a) == 1
    assert rubriek_1a.iloc[0]["ernst"] == WAARSCHUWING
    assert round(float(rubriek_1a.iloc[0]["bedrag"]), 2) == 68.00


def test_jaarovergang_die_niet_aansluit_is_kritiek():
    """Een niet overgenomen beginbalans hoort de lijst te openen."""
    vorig, _ = _demopaar()
    spec = AuditfileSpec(
        fiscal_year="2025",
        start_date="2025-01-01",
        end_date="2025-12-31",
        accounts=[Account("1100", "Bank", "B", "BLimBan"), Account("8000", "Omzet", "P", "WOmzNeh")],
        opening_lines=[],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "V1",
                        "2025-06-30",
                        6,
                        [Line("1100", "100.00", "D"), Line("8000", "100.00", "C")],
                    )
                ],
            )
        ],
    )
    huidig = parse_auditfile("zonder_beginbalans.xaf", build_xaf(spec))
    bevindingen = verzamel_bevindingen(huidig, vorig)
    jaarovergang = bevindingen[bevindingen["categorie"] == "Jaarovergang"]
    assert KRITIEK in set(jaarovergang["ernst"])


def test_perioden_zonder_omzet_worden_samengevat():
    """Twaalf losse bevindingen voor twaalf maanden maken de lijst onleesbaar."""
    vorig, huidig = _demopaar()
    bevindingen = verzamel_bevindingen(huidig, vorig)
    omzet = bevindingen[bevindingen["categorie"] == "Omzet per periode"]
    assert len(omzet) == 1
    assert int(omzet.iloc[0]["aantal_regels"]) > 1
    # Een signaal over afwezigheid krijgt geen bedrag: nul zou het onder elke
    # drempel duwen terwijl juist de afwezigheid het punt is.
    assert pd.isna(omzet.iloc[0]["bedrag"])
    assert bool(omzet.iloc[0]["boven_drempel"])


# --- Reviewstatus -----------------------------------------------------------


def test_zonder_vastgelegde_status_staat_alles_te_beoordelen():
    frame = pas_review_toe(naar_frame([Bevinding("A", "iets", SIGNAAL)]))
    assert list(frame["status"]) == [TE_BEOORDELEN]
    assert list(frame["notitie"]) == [""]
    assert openstaande_bevindingen(frame) == 1


def test_de_status_hangt_aan_de_sleutel_en_niet_aan_de_plaats():
    """De lijst staat bij een volgende analyse anders gesorteerd."""
    eerste = Bevinding("Btw", "Rubriek 1a: verschil", WAARSCHUWING, bedrag=100.0)
    tweede = Bevinding("Boekingen", "Rond bedrag", SIGNAAL, bedrag=9000.0)
    review = {eerste.sleutel: {"status": "Opgelost", "notitie": "Suppletie ingediend"}}

    # Zelfde bevindingen, andere volgorde en een ander bedrag bij de eerste.
    frame = pas_review_toe(
        naar_frame(
            [
                tweede,
                Bevinding("Btw", "Rubriek 1a: verschil", WAARSCHUWING, bedrag=250.0),
            ]
        ),
        review,
    )
    per_onderwerp = frame.set_index("onderwerp")
    assert per_onderwerp.loc["Rubriek 1a: verschil", "status"] == "Opgelost"
    assert per_onderwerp.loc["Rubriek 1a: verschil", "notitie"] == "Suppletie ingediend"
    assert per_onderwerp.loc["Rond bedrag", "status"] == TE_BEOORDELEN
    assert openstaande_bevindingen(frame) == 1


def test_een_status_van_een_verdwenen_bevinding_stoort_niet():
    """Een oude status hoort niet als losse regel op te duiken."""
    frame = pas_review_toe(
        naar_frame([Bevinding("A", "bestaat nog", SIGNAAL)]),
        {"onbekende-sleutel": {"status": "Opgelost", "notitie": "oud"}},
    )
    assert len(frame) == 1
    assert list(frame["status"]) == [TE_BEOORDELEN]


def test_review_op_een_lege_lijst_houdt_de_kolommen():
    frame = pas_review_toe(naar_frame([]))
    assert frame.empty
    assert "status" in frame.columns and "notitie" in frame.columns
    assert openstaande_bevindingen(frame) == 0


def test_de_reviewstatus_wordt_per_dossier_bewaard(tmp_path):
    """Twee dossiers mogen elkaars beoordeling niet zien."""
    from auditfile.settings import DossierOpslag

    eerste = DossierOpslag.voor("dossier-a", basis=tmp_path)
    tweede = DossierOpslag.voor("dossier-b", basis=tmp_path)
    bevinding = Bevinding("Btw", "Rubriek 1a: verschil", WAARSCHUWING)

    assert eerste.schrijf_review({bevinding.sleutel: {"status": "Opgelost", "notitie": "ok"}})

    assert eerste.lees_review()[bevinding.sleutel]["status"] == "Opgelost"
    assert tweede.lees_review() == {}

    frame = pas_review_toe(naar_frame([bevinding]), tweede.lees_review())
    assert list(frame["status"]) == [TE_BEOORDELEN]
