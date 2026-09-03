"""De ratio-analyse: brutomarge, personeelsquote, solvabiliteit en liquiditeit.

Alle bestanden hier zijn synthetisch en worden in het geheugen opgebouwd.
"""
from __future__ import annotations

import pandas as pd

from auditfile.demo import (
    DEMO_RATIO_KOSTPRIJS,
    DEMO_RATIO_LOON_PER_MAAND,
    DEMO_RATIO_OMZET,
    DEMO_RATIO_VOORRAAD_BEGIN,
    Account,
    AuditfileSpec,
    Journal,
    Line,
    OpeningLine,
    Transaction,
    build_xaf,
    eenvoudige_spec,
    vul_ratioposten,
)
from auditfile.findings import IN_ORDE, NIET_MOGELIJK, SIGNAAL, WAARSCHUWING, verzamel_bevindingen
from auditfile.parsing import parse_auditfile
from auditfile.ratios import (
    MINIMALE_DEKKING,
    build_ratio_opbouw,
    build_ratios,
    meet,
)


# --- Hulpmiddelen -----------------------------------------------------------


def _bouw(accounts, opening_lines, regels, boekjaar: str = "2025"):
    """Een klein, sluitend auditfile met één memoriaaltransactie."""
    spec = AuditfileSpec(
        versie="4.0",
        fiscal_year=boekjaar,
        start_date=f"{boekjaar}-01-01",
        end_date=f"{boekjaar}-12-31",
        accounts=accounts,
        opening_lines=opening_lines,
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [Transaction("M001", f"{boekjaar}-06-30", 6, regels)],
            )
        ],
    )
    return parse_auditfile(f"ratio_{boekjaar}.xaf", build_xaf(spec))


def _ratiofixture(boekjaar: str = "2025"):
    spec = eenvoudige_spec("4.0")
    spec.fiscal_year = boekjaar
    return parse_auditfile(f"ratio_{boekjaar}.xaf", build_xaf(vul_ratioposten(spec)))


def _rij(ratios: pd.DataFrame, naam: str) -> pd.Series:
    treffers = ratios[ratios["ratio"] == naam]
    assert len(treffers) == 1, f"ratio {naam} niet gevonden"
    return treffers.iloc[0]


def _bouwsteen(opbouw: pd.DataFrame, naam: str) -> pd.Series:
    treffers = opbouw[opbouw["bouwsteen"] == naam]
    assert len(treffers) == 1, f"bouwsteen {naam} niet gevonden"
    return treffers.iloc[0]


# Een balans die zichzelf sluit en waarvan elke post herkenbaar is. Wordt in
# meer dan een test aangepast, dus als functie en niet als constante.
def _balansrekeningen():
    return [
        Account("0100", "Inventaris", "B", "BMvaBeg"),
        Account("0500", "Eigen vermogen", "B", "BEivKap"),
        Account("1100", "Bank", "B", "BLimBan"),
        Account("1300", "Debiteuren", "B", "BVorDeb"),
        Account("1600", "Crediteuren", "B", "BSchCre"),
        Account("3000", "Voorraad", "B", "BVrdHan"),
    ]


# --- De bouwstenen ----------------------------------------------------------


def test_de_opbouw_wijst_de_bouwstenen_aan_op_rgs_code():
    opbouw = build_ratio_opbouw(_ratiofixture())
    omzet = _bouwsteen(opbouw, "Netto-omzet")
    assert omzet["methode"] == "RGS-code"
    assert omzet["bron"] == "auditfile"
    # De demo boekt 1.000 hoog, 100 laag, een creditnota van 200 en de verkoop
    # van handelsgoederen.
    assert round(omzet["bedrag"], 2) == round(900.0 + DEMO_RATIO_OMZET, 2)
    assert round(_bouwsteen(opbouw, "Kostprijs van de omzet")["bedrag"], 2) == DEMO_RATIO_KOSTPRIJS
    assert round(_bouwsteen(opbouw, "Personeelskosten")["bedrag"], 2) == round(
        12 * DEMO_RATIO_LOON_PER_MAAND, 2
    )
    # De demo koopt in en verbruikt evenveel, dus de voorraad staat op zijn
    # beginstand.
    voorraad = _bouwsteen(opbouw, "Voorraden")
    assert round(voorraad["bedrag"], 2) == DEMO_RATIO_VOORRAAD_BEGIN


def test_bedragen_in_de_opbouw_blijven_getallen():
    opbouw = build_ratio_opbouw(_ratiofixture())
    assert pd.api.types.is_numeric_dtype(opbouw["bedrag"])
    assert pd.api.types.is_numeric_dtype(opbouw["aantal_rekeningen"])


def test_de_voorraad_telt_niet_twee_keer_in_het_balanstotaal():
    """De voorraad is een uitsplitsing binnen de vlottende activa."""
    grootheden = meet(_ratiofixture())
    vlottend = grootheden.bedrag("Vlottende activa")
    vast = grootheden.bedrag("Vaste activa")
    assert round(grootheden.balanstotaal, 2) == round(vlottend + vast, 2)


def test_de_debetzijde_en_de_creditzijde_van_de_balans_zijn_gelijk():
    grootheden = meet(_ratiofixture())
    passiva = sum(
        grootheden.bedrag(naam) or 0.0
        for naam in ("Voorzieningen", "Langlopende schulden", "Kortlopende schulden")
    )
    assert round(grootheden.eigen_vermogen + passiva, 2) == round(grootheden.balanstotaal, 2)


# --- Het resultaat van het boekjaar -----------------------------------------


def test_een_onbestemd_resultaat_wordt_bij_het_eigen_vermogen_geteld():
    """Een auditfile is doorgaans opgemaakt voordat het resultaat is bestemd."""
    grootheden = meet(_ratiofixture())
    assert grootheden.resultaat_verwerkt is False
    op_balans = grootheden.bedrag("Eigen vermogen")
    assert round(grootheden.eigen_vermogen, 2) == round(op_balans + grootheden.resultaat, 2)

    opbouw = build_ratio_opbouw(_ratiofixture())
    regel = _bouwsteen(opbouw, "Resultaat nog niet bestemd")
    assert round(regel["bedrag"], 2) == round(grootheden.resultaat, 2)
    assert regel["bron"] == "berekend"


def test_een_bestemd_resultaat_wordt_niet_nog_eens_bijgeteld():
    """Sluit de balans al op nul, dan zit het resultaat er al in."""
    af = _bouw(
        _balansrekeningen(),
        [
            OpeningLine("1100", "50000.00", "D"),
            OpeningLine("0500", "50000.00", "C"),
        ],
        [
            Line("1100", "8000.00", "D", "Ontvangst", effDate="2025-06-30"),
            Line("0500", "8000.00", "C", "Resultaat rechtstreeks in het vermogen", effDate="2025-06-30"),
        ],
    )
    grootheden = meet(af)
    assert grootheden.resultaat == 0.0
    assert grootheden.resultaat_verwerkt is True
    assert round(grootheden.eigen_vermogen, 2) == 58_000.00


def test_een_balans_die_nergens_op_uitkomt_geeft_geen_solvabiliteit():
    """Zonder sluitende balans is niet vast te stellen of het resultaat erin zit.

    De beginbalans is hier bewust niet in evenwicht. Dat is een kapot bestand,
    en de integriteitscontrole meldt dat afzonderlijk; de ratio-analyse hoort in
    dat geval geen getal te produceren dat er goed uitziet.
    """
    accounts = _balansrekeningen() + [Account("8000", "Omzet", "P", "WOmzNeh")]
    af = _bouw(
        accounts,
        [OpeningLine("1100", "10000.00", "D"), OpeningLine("0500", "8000.00", "C")],
        [
            Line("1100", "5000.00", "D", "Verkoop", effDate="2025-06-30"),
            Line("8000", "5000.00", "C", "Omzet", effDate="2025-06-30"),
        ],
    )
    grootheden = meet(af)
    assert grootheden.resultaat_verwerkt is None
    assert grootheden.eigen_vermogen is None
    rij = _rij(build_ratios(af), "Solvabiliteit")
    assert rij["ernst"] == NIET_MOGELIJK
    assert "niet vast te stellen" in rij["signaal"]


# --- De ratio's zelf --------------------------------------------------------


def test_de_ratios_van_de_fixture_zijn_narekenbaar():
    ratios = build_ratios(_ratiofixture())
    assert round(_rij(ratios, "Brutomarge")["waarde_huidig"], 2) == 55.67
    assert round(_rij(ratios, "Personeelskosten in % van de omzet")["waarde_huidig"], 2) == 17.12
    assert round(_rij(ratios, "Solvabiliteit")["waarde_huidig"], 2) == 61.29
    assert round(_rij(ratios, "Current ratio")["waarde_huidig"], 2) == 2.45
    assert round(_rij(ratios, "Quick ratio")["waarde_huidig"], 2) == 1.34
    assert set(ratios["eenheid"]) == {"%", "x"}


def test_de_quick_ratio_blijft_onder_de_current_ratio():
    """Bij een positieve voorraad kan het niet anders.

    Komt de quick ratio er toch boven, dan staat de voorraad credit. Dat is een
    fout in de administratie en geen eigenschap van de ratio; de
    balanssignalering meldt zo'n stand afzonderlijk.
    """
    ratios = build_ratios(_ratiofixture())
    assert meet(_ratiofixture()).bedrag("Voorraden") > 0
    assert _rij(ratios, "Quick ratio")["waarde_huidig"] < _rij(ratios, "Current ratio")["waarde_huidig"]


def test_zonder_kostprijsrekening_is_er_geen_brutomarge():
    """Een marge van 100% zou een ontbrekende rubriek verbergen."""
    rij = _rij(build_ratios(parse_auditfile("t.xaf", build_xaf(eenvoudige_spec("4.0")))), "Brutomarge")
    assert rij["ernst"] == NIET_MOGELIJK
    assert "kostprijs" in rij["signaal"].lower()
    assert pd.isna(rij["waarde_huidig"])


def test_zonder_omzet_is_er_geen_marge_en_geen_quote():
    af = _bouw(
        _balansrekeningen() + [Account("7000", "Inkoopwaarde", "P", "WKprInk")],
        [OpeningLine("1100", "1000.00", "D"), OpeningLine("0500", "1000.00", "C")],
        [
            Line("7000", "400.00", "D", "Inkoop", effDate="2025-06-30"),
            Line("1100", "400.00", "C", "Betaling", effDate="2025-06-30"),
        ],
    )
    ratios = build_ratios(af)
    for naam in ("Brutomarge", "Personeelskosten in % van de omzet"):
        rij = _rij(ratios, naam)
        assert rij["ernst"] == NIET_MOGELIJK
        assert "omzet" in rij["signaal"].lower()


def test_zonder_vorig_jaar_is_er_geen_verschuiving():
    ratios = build_ratios(_ratiofixture())
    assert ratios["waarde_vorig"].isna().all()
    assert ratios["verschuiving"].isna().all()


# --- Dekking ----------------------------------------------------------------


def test_te_weinig_dekking_geeft_geen_balansratio():
    """In een niet-ingedeeld deel van de balans kan eigen vermogen zitten."""
    accounts = _balansrekeningen() + [Account("9999", "Tussenpost zonder aanduiding", "B")]
    af = _bouw(
        accounts,
        [
            OpeningLine("1100", "1000.00", "D"),
            OpeningLine("9999", "20000.00", "D"),
            OpeningLine("0500", "21000.00", "C"),
        ],
        [
            Line("1100", "100.00", "D", "Ontvangst", effDate="2025-06-30"),
            Line("0500", "100.00", "C", "Storting", effDate="2025-06-30"),
        ],
    )
    grootheden = meet(af)
    assert grootheden.dekking < MINIMALE_DEKKING
    for naam in ("Solvabiliteit", "Current ratio", "Quick ratio"):
        rij = _rij(build_ratios(af), naam)
        assert rij["ernst"] == NIET_MOGELIJK
        assert "dekt" in rij["signaal"]


def test_de_dekking_staat_in_de_opbouw():
    opbouw = build_ratio_opbouw(_ratiofixture())
    regel = _bouwsteen(opbouw, "Niet ingedeeld")
    assert round(regel["bedrag"], 2) == 0.0
    assert "100,0%".replace(",", ".") in regel["toelichting"]


# --- Signalen ---------------------------------------------------------------


def test_negatief_eigen_vermogen_is_een_waarschuwing():
    # Het eigen vermogen staat debet: de verliezen zijn groter dan het
    # ingebrachte kapitaal. Zonder resultaatrekeningen sluit de balans op nul en
    # komt het eigen vermogen dus rechtstreeks uit de balans.
    af = _bouw(
        _balansrekeningen(),
        [
            OpeningLine("1100", "1000.00", "D"),
            OpeningLine("0500", "1000.00", "D"),
            OpeningLine("1600", "2000.00", "C"),
        ],
        [
            Line("1100", "500.00", "D", "Ontvangst", effDate="2025-06-30"),
            Line("1600", "500.00", "C", "Inkoopfactuur", effDate="2025-06-30"),
        ],
    )
    grootheden = meet(af)
    assert grootheden.resultaat_verwerkt is True
    assert grootheden.eigen_vermogen is not None and grootheden.eigen_vermogen < 0
    rij = _rij(build_ratios(af), "Solvabiliteit")
    assert rij["ernst"] == WAARSCHUWING
    assert "negatief" in rij["signaal"]


def test_kortlopende_schulden_boven_de_vlottende_activa_zijn_een_signaal():
    af = _bouw(
        _balansrekeningen(),
        [
            OpeningLine("0100", "50000.00", "D"),
            OpeningLine("1100", "1000.00", "D"),
            OpeningLine("1600", "20000.00", "C"),
            OpeningLine("0500", "31000.00", "C"),
        ],
        [
            Line("1600", "5000.00", "C", "Inkoopfactuur", effDate="2025-06-30"),
            Line("0100", "5000.00", "D", "Investering", effDate="2025-06-30"),
        ],
    )
    ratios = build_ratios(af)
    current = _rij(ratios, "Current ratio")
    assert current["waarde_huidig"] < 1
    assert current["ernst"] == SIGNAAL
    # Geen tweede bevinding over dezelfde verhouding.
    assert _rij(ratios, "Quick ratio")["ernst"] == IN_ORDE


def test_een_verschuiving_van_de_brutomarge_is_een_signaal():
    def bestand(omzet: float, kostprijs: float, boekjaar: str):
        accounts = _balansrekeningen() + [
            Account("7000", "Inkoopwaarde", "P", "WKprInk"),
            Account("8000", "Omzet", "P", "WOmzNeh"),
        ]
        return _bouw(
            accounts,
            [
                OpeningLine("1100", "40000.00", "D"),
                OpeningLine("0500", "40000.00", "C"),
            ],
            [
                Line("1300", f"{omzet:.2f}", "D", "Verkoop", effDate=f"{boekjaar}-06-30"),
                Line("8000", f"{omzet:.2f}", "C", "Omzet", effDate=f"{boekjaar}-06-30"),
                Line("7000", f"{kostprijs:.2f}", "D", "Inkoopwaarde", effDate=f"{boekjaar}-06-30"),
                Line("1600", f"{kostprijs:.2f}", "C", "Inkoopfactuur", effDate=f"{boekjaar}-06-30"),
            ],
            boekjaar=boekjaar,
        )

    # 40% marge vorig jaar, 25% dit jaar: vijftien procentpunt.
    vorig = bestand(100_000.0, 60_000.0, "2024")
    huidig = bestand(100_000.0, 75_000.0, "2025")
    rij = _rij(build_ratios(huidig, vorig), "Brutomarge")
    assert round(rij["waarde_vorig"], 2) == 40.00
    assert round(rij["waarde_huidig"], 2) == 25.00
    assert round(rij["verschuiving"], 2) == -15.00
    assert rij["ernst"] == SIGNAAL
    assert "gedaald" in rij["signaal"]

    # Een kleine verschuiving blijft onder de werkafspraak.
    bijna_gelijk = bestand(100_000.0, 62_000.0, "2025")
    rustig = _rij(build_ratios(bijna_gelijk, vorig), "Brutomarge")
    assert round(rustig["verschuiving"], 2) == -2.00
    assert rustig["ernst"] == IN_ORDE


# --- Aansluiting op de rest van de tool -------------------------------------


def test_de_ratios_komen_in_de_bevindingen():
    huidig = _ratiofixture("2025")
    bevindingen = verzamel_bevindingen(huidig)
    ratios = bevindingen[bevindingen["categorie"] == "Ratio's"]
    # De fixture is gezond, dus alleen de ratio's die niet in orde zijn komen
    # door; dat de categorie bestaat is hier wat telt.
    assert set(ratios["pagina"]) <= {"Jaarvergelijking"}
    assert IN_ORDE not in set(ratios["ernst"])


def test_een_niet_mogelijke_ratio_wordt_een_bevinding():
    huidig = parse_auditfile("t.xaf", build_xaf(eenvoudige_spec("4.0")))
    bevindingen = verzamel_bevindingen(huidig)
    marge = bevindingen[
        (bevindingen["categorie"] == "Ratio's") & (bevindingen["onderwerp"] == "Brutomarge")
    ]
    assert len(marge) == 1
    assert marge.iloc[0]["ernst"] == NIET_MOGELIJK
    assert pd.isna(marge.iloc[0]["bedrag"])
    # Een bevinding zonder bedrag is niet te wegen en valt dus nooit weg.
    assert bool(marge.iloc[0]["boven_drempel"])


def test_de_omschrijving_is_de_terugval_zonder_rgs_code():
    accounts = [
        Account("0500", "Eigen vermogen", "B"),
        Account("1100", "Bank", "B"),
        Account("1600", "Crediteuren", "B"),
        Account("7000", "Inkoopwaarde van de omzet", "P"),
        Account("8000", "Omzet handelsgoederen", "P"),
    ]
    af = _bouw(
        accounts,
        [OpeningLine("1100", "10000.00", "D"), OpeningLine("0500", "10000.00", "C")],
        [
            Line("1100", "50000.00", "D", "Verkoop", effDate="2025-06-30"),
            Line("8000", "50000.00", "C", "Omzet", effDate="2025-06-30"),
            Line("7000", "30000.00", "D", "Inkoopwaarde", effDate="2025-06-30"),
            Line("1600", "30000.00", "C", "Inkoopfactuur", effDate="2025-06-30"),
        ],
    )
    rij = _rij(build_ratios(af), "Brutomarge")
    assert rij["methode"] == "omschrijving"
    assert round(rij["waarde_huidig"], 2) == 40.00


def test_de_export_bevat_de_ratios_en_hun_opbouw():
    from auditfile.comparison import compare_saldi
    from auditfile.excel import bouw_werkbladen

    huidig = _ratiofixture("2025")
    vorig = _ratiofixture("2024")
    bladen = bouw_werkbladen(huidig, vorig, compare_saldi(vorig, huidig))
    assert "Ratio's" in bladen
    assert "Ratio-opbouw 2025" in bladen
    assert "Ratio-opbouw 2024" in bladen
    assert not bladen["Ratio's"].empty
    assert "Brutomarge" in set(bladen["Ratio's"]["ratio"])
