"""Bedragen die het bestand invult maar niet als getal opgeeft.

Een onleesbaar bedrag werd stil 0,00 en rekende zo door in de btw-rondrekening,
de ratio-analyse en de saldering. De parser rekent nog steeds door, want één
rommelige regel mag een auditfile niet onbruikbaar maken, maar houdt nu bij
hoeveel waarden onleesbaar waren en waar, en ``integrity.py`` meldt dat.

Alle auditfiles hier zijn synthetisch en worden in het geheugen opgebouwd; er
wordt nooit klantdata gelezen.
"""
from __future__ import annotations

import pandas as pd

from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    ObSubledger,
    ObSubledgerLine,
    OpeningLine,
    Relation,
    SbLine,
    Subledger,
    Transaction,
    VatCode,
    build_xaf,
)
from auditfile.findings import Materialiteit, verzamel_bevindingen
from auditfile.integrity import controleer_auditfile
from auditfile.model import GEVOLG_LEEG, GEVOLG_NUL
from auditfile.parsing import parse_auditfile

CONTROLE = "Bedragen leesbaar"

# Een bedrag in Nederlandse notatie. Dit is de realistische vorm van de fout:
# geen onzin, maar een pakket dat de komma als decimaalteken wegschrijft.
ONLEESBAAR = "1.234,56"

REKENINGEN = [
    Account("1000", "Kas", "B"),
    Account("1300", "Debiteuren", "B"),
    Account("1800", "Omzetbelasting", "B"),
    Account("8000", "Omzet", "P"),
]


def _lees(spec: AuditfileSpec):
    return parse_auditfile("synthetisch.xaf", build_xaf(spec))


def _bevindingen(af):
    alle = controleer_auditfile(af)
    return alle[alle["controle"] == CONTROLE]


def _sluitende_boeking() -> list[Journal]:
    return [
        Journal(
            "MEM",
            "Memoriaal",
            [
                Transaction(
                    "M1",
                    "2025-01-15",
                    1,
                    [Line("1000", "100.00", "D"), Line("8000", "100.00", "C")],
                )
            ],
        )
    ]


def _spec_met_regels(regels: list[Line], totalen) -> AuditfileSpec:
    """Een spec met één transactie en meegegeven controletotalen.

    Die totalen moeten mee, want de generator berekent ze anders zelf uit de
    bedragen en over een onleesbaar bedrag valt niets te tellen. Ze zijn hier
    dus niet het onderwerp van de test.
    """
    return AuditfileSpec(
        accounts=REKENINGEN,
        journals=[Journal("MEM", "Memoriaal", [Transaction("M1", "2025-01-15", 1, regels)])],
        transaction_totals_override=totalen,
    )


def _spec_met_een_onleesbare_regel() -> AuditfileSpec:
    return _spec_met_regels(
        [Line("1300", ONLEESBAAR, "D"), Line("8000", "100.00", "C")],
        totalen=(2, "1234.56", "100.00"),
    )


# --- Boekingsregels ---------------------------------------------------------


def test_onleesbaar_bedrag_wordt_geteld_met_vindplaats():
    af = _lees(_spec_met_een_onleesbare_regel())

    # De berekening loopt door: het bedrag is nul geworden.
    assert af.lines.loc[0, "bedrag"] == 0.0

    assert len(af.leesfouten) == 1
    rij = af.leesfouten.iloc[0]
    assert rij["blok"] == "boekingsregels"
    assert rij["veld"] == "amnt"
    assert rij["gevolg"] == GEVOLG_NUL
    assert rij["aantal"] == 1
    # De vindplaats wijst de regel aan zoals de gebruiker hem in zijn eigen
    # bestand terugvindt, met de waarde die er stond.
    assert rij["vindplaatsen"] == f'dagboek MEM, transactie M1, regel 1 ("{ONLEESBAAR}")'


def test_onleesbaar_bedrag_is_een_kritieke_bevinding():
    gevonden = _bevindingen(_lees(_spec_met_een_onleesbare_regel()))

    assert len(gevonden) == 1
    assert gevonden.iloc[0]["ernst"] == "kritiek"
    assert gevonden.iloc[0]["aantal"] == 1
    assert "niet als getal" in gevonden.iloc[0]["bevinding"]
    assert GEVOLG_NUL in gevonden.iloc[0]["bevinding"]
    assert ONLEESBAAR in gevonden.iloc[0]["bevinding"]


def test_leeg_bedrag_is_geen_leesfout():
    """Een leeg veld zegt niets en mag nul worden; dat is geen fout."""
    af = _lees(
        _spec_met_regels(
            [Line("1300", "", "D"), Line("8000", "100.00", "C")],
            totalen=(2, "0.00", "100.00"),
        )
    )

    assert af.lines.loc[0, "bedrag"] == 0.0
    assert af.leesfouten.empty
    assert list(_bevindingen(af)["ernst"]) == ["in orde"]


def test_nul_is_geen_leesfout():
    af = _lees(
        _spec_met_regels(
            [Line("1300", "0.00", "D"), Line("8000", "0.00", "C")],
            totalen=(2, "0.00", "0.00"),
        )
    )
    assert af.leesfouten.empty


def test_geen_leesfouten_geeft_in_orde(af_40):
    """Het gewone synthetische bestand is schoon; leeg is dus goed nieuws."""
    assert af_40.leesfouten.empty
    gevonden = _bevindingen(af_40)
    assert len(gevonden) == 1
    assert gevonden.iloc[0]["ernst"] == "in orde"
    assert gevonden.iloc[0]["aantal"] == 0


def test_lege_leesfoutentabel_heeft_een_geheeltallig_aantal(af_40):
    """Zonder type zou een optelling op een schoon bestand anders uitvallen."""
    assert pd.api.types.is_integer_dtype(af_40.leesfouten["aantal"])
    assert int(af_40.leesfouten["aantal"].sum()) == 0


def test_meer_dan_vijf_vindplaatsen_worden_ingekort():
    """De telling blijft volledig; de opsomming wordt leesbaar gehouden."""
    regels = [Line("1300", ONLEESBAAR, "D") for _ in range(7)]
    regels.append(Line("8000", "100.00", "C"))
    af = _lees(_spec_met_regels(regels, totalen=(8, "0.00", "100.00")))

    rij = af.leesfouten.iloc[0]
    assert rij["aantal"] == 7
    assert rij["vindplaatsen"].count("dagboek MEM") == 5
    assert rij["vindplaatsen"].endswith("en nog 2")


# --- Btw op de boekingsregel ------------------------------------------------


def test_onleesbaar_btw_bedrag_blijft_leeg_en_is_een_waarschuwing():
    """Leeg is hier minder schadelijk dan nul, maar het gegeven is wel weg."""
    spec = AuditfileSpec(
        accounts=REKENINGEN,
        vat_codes=[VatCode("1", "Hoog", vatToPayAccID="1800")],
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
                            Line("1300", "121.00", "D"),
                            Line(
                                "8000",
                                "100.00",
                                "C",
                                vatID="1",
                                vatPerc="21",
                                vatAmnt=ONLEESBAAR,
                                vatAmntTp="C",
                            ),
                            Line("1800", "21.00", "C"),
                        ],
                    )
                ],
            )
        ],
        transaction_totals_override=(3, "121.00", "121.00"),
    )
    af = _lees(spec)

    # "Geen btw" en "btw van nul" blijven onderscheiden: de waarde is leeg.
    assert af.lines["btw_bedrag"].isna().all()

    rij = af.leesfouten.iloc[0]
    assert rij["blok"] == "btw op boekingsregels"
    assert rij["veld"] == "vatAmnt"
    assert rij["gevolg"] == GEVOLG_LEEG
    assert _bevindingen(af).iloc[0]["ernst"] == "waarschuwing"


# --- Beginbalans ------------------------------------------------------------


def test_onleesbaar_beginsaldo_wordt_gemeld():
    spec = AuditfileSpec(
        accounts=REKENINGEN,
        opening_lines=[
            OpeningLine("1000", ONLEESBAAR, "D"),
            OpeningLine("8000", "100.00", "C"),
        ],
        journals=_sluitende_boeking(),
        opening_totals_override=(2, "1234.56", "100.00"),
    )
    af = _lees(spec)

    rij = af.leesfouten.iloc[0]
    assert rij["blok"] == "beginbalans"
    assert rij["gevolg"] == GEVOLG_NUL
    assert rij["aantal"] == 1
    assert "beginbalansregel 1 (rekening 1000)" in rij["vindplaatsen"]
    assert _bevindingen(af).iloc[0]["ernst"] == "kritiek"


# --- Openstaande bedragen per relatie (XAF 4.0) -----------------------------


def test_onleesbaar_relatiesaldo_blijft_leeg_en_is_een_waarschuwing():
    """Een onleesbare stand telt als niet aanwezig, niet als nul."""
    spec = AuditfileSpec(
        versie="4.0",
        accounts=REKENINGEN,
        relations=[Relation("D001", "Eerste debiteur", openstaand_begin=ONLEESBAAR)],
        journals=_sluitende_boeking(),
    )
    af = _lees(spec)

    assert pd.isna(af.relations.loc[0, "openstaand_begin"])

    rij = af.leesfouten.iloc[0]
    assert rij["blok"] == "relaties"
    assert rij["gevolg"] == GEVOLG_LEEG
    assert "relatie D001" in rij["vindplaatsen"]
    assert _bevindingen(af).iloc[0]["ernst"] == "waarschuwing"


# --- Subadministratie (XAF 3.2) ---------------------------------------------


def test_onleesbaar_subadministratiebedrag_wordt_gemeld():
    spec = AuditfileSpec(
        versie="3.2",
        accounts=REKENINGEN,
        relations=[Relation("D001", "Eerste debiteur")],
        opening_lines=[
            OpeningLine("1300", "100.00", "D"),
            OpeningLine("8000", "100.00", "C"),
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
                        [Line("1300", "100.00", "D"), Line("8000", "100.00", "C")],
                    )
                ],
            )
        ],
        ob_subledgers=[
            ObSubledger(
                lines=[ObSubledgerLine("1", ONLEESBAAR, "D", custSupID="D001")],
                totals_override=(1, "1234.56", "0.00"),
            )
        ],
        subledgers=[
            Subledger(lines=[SbLine("VRK", "V1", "1", "100.00", "D", custSupID="D001")])
        ],
    )
    af = _lees(spec)

    onleesbaar = af.subadministratie[af.subadministratie["bron"] == "beginbalans"]
    assert list(onleesbaar["bedrag"]) == [0.0]

    gemeld = af.leesfouten[af.leesfouten["blok"] == "subadministratie"]
    assert len(gemeld) == 1
    assert gemeld.iloc[0]["gevolg"] == GEVOLG_NUL
    assert gemeld.iloc[0]["aantal"] == 1
    assert _bevindingen(af).iloc[0]["ernst"] == "kritiek"


# --- Doorwerking naar het bevindingenmodel ----------------------------------


def test_leesfout_komt_zonder_bedrag_in_het_bevindingenmodel():
    """Zonder bedrag valt de bevinding nooit onder de materialiteitsdrempel."""
    af = _lees(_spec_met_een_onleesbare_regel())
    frame = verzamel_bevindingen(af, materialiteit=Materialiteit(grondslag=1_000_000.0))
    leesfout = frame[frame["onderwerp"] == CONTROLE]

    assert len(leesfout) == 1
    assert leesfout.iloc[0]["ernst"] == "kritiek"
    assert pd.isna(leesfout.iloc[0]["bedrag"])
    assert bool(leesfout.iloc[0]["boven_drempel"]) is True
