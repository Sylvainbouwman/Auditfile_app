"""Wat één boeking is, en waarom dagboek plus transactienummer dat niet bepaalt.

De aansluitcontrole groepeerde op dagboek en transactienummer. Komt hetzelfde
nummer binnen één dagboek twee keer voor, dan telde zij beide boekingen bij
elkaar op en kon een echte onbalans in de ene wegvallen tegen de andere; de
controle meldde dan "in balans".

Gemeten op 11-09-2026 met het bestand dat ``_dubbel_transactienummer()``
hieronder opbouwt. Met de modules van de standaardbranch: "Alle 1 transacties
zijn in evenwicht", ernst in orde, en ook de controletotalen, de debet-credit-
toets en het aantal regels alle in orde, dus geen enkel ander signaal. Met deze
wijziging: "2 van de 2 transacties zijn niet in evenwicht", ernst kritiek, een
verschil van 200,00 en daarnaast een waarschuwing over het hergebruikte nummer.
Op een groter bestand (``eenvoudige_spec("4.0")`` met dit dagboek erbij) gaf de
standaardbranch "Alle 18 transacties zijn in evenwicht" en deze wijziging
"2 van de 19 transacties zijn niet in evenwicht".

Alle auditfiles hier zijn synthetisch en worden in het geheugen opgebouwd; er
wordt nooit klantdata gelezen.
"""
from __future__ import annotations

import pandas as pd
import pytest

from auditfile import suppletie as sup
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Transaction,
    VatCode,
    build_xaf,
    eenvoudige_spec,
    vul_suppletie,
)
from auditfile.integrity import controleer_auditfile
from auditfile.parsing import parse_auditfile, transactie_sleutel

BALANS = "Iedere transactie sluit op nul"
EENDUIDIG = "Transactienummer eenduidig binnen het dagboek"

# De afwijking per boeking. De twee boekingen staan even veel scheef naar de
# andere kant, zodat ze samen precies sluiten: dat is het geval waarin de oude
# controle niets zag.
SCHEEF = 100.0

REKENINGEN = [
    Account("1000", "Kas", "B"),
    Account("1300", "Debiteuren", "B"),
    Account("1800", "Omzetbelasting", "B"),
    Account("8000", "Omzet", "P"),
]


def _dubbel_transactienummer(nummer: str = "5") -> AuditfileSpec:
    """Eén dagboek, tweemaal hetzelfde transactienummer, samen sluitend.

    De eerste boeking staat 100,00 debet te veel, de tweede precies 100,00
    credit te veel. Het bestand als geheel sluit dus, en ook de controletotalen
    die het zelf opgeeft kloppen. Alleen de boekingen afzonderlijk niet.
    """
    return AuditfileSpec(
        accounts=REKENINGEN,
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        nummer,
                        "2025-06-30",
                        6,
                        [
                            Line("1300", f"{1000.0 + SCHEEF:.2f}", "D"),
                            Line("8000", "1000.00", "C"),
                        ],
                    ),
                    Transaction(
                        nummer,
                        "2025-07-31",
                        7,
                        [
                            Line("1300", f"{1000.0 - SCHEEF:.2f}", "D"),
                            Line("8000", "1000.00", "C"),
                        ],
                    ),
                ],
            )
        ],
    )


def _lees(spec: AuditfileSpec):
    return parse_auditfile("synthetisch.xaf", build_xaf(spec))


def _bevinding(af, controle: str):
    alle = controleer_auditfile(af)
    gevonden = alle[alle["controle"] == controle]
    assert len(gevonden) == 1, f"{controle}: {len(gevonden)} bevindingen"
    return gevonden.iloc[0]


# --- De aansluitcontrole ----------------------------------------------------


def test_hergebruikt_nummer_maskeert_de_onbalans_niet_meer():
    af = _lees(_dubbel_transactienummer())

    regel = _bevinding(af, BALANS)
    assert regel["ernst"] == "kritiek"
    assert regel["aantal"] == 2
    # De som van de absolute afwijkingen. De gewone som zou hier nul zijn en de
    # bevinding onder elke materialiteitsdrempel laten vallen.
    assert regel["verschil"] == pytest.approx(2 * SCHEEF)


def test_het_bestand_zelf_geeft_geen_enkel_ander_signaal():
    """Juist daarom is de maskering gevaarlijk: er is niets anders dat opvalt."""
    af = _lees(_dubbel_transactienummer())
    alle = controleer_auditfile(af)

    for controle in (
        "Totaal debet",
        "Totaal credit",
        "Aantal boekingsregels",
        "Debet is gelijk aan credit",
    ):
        assert alle[alle["controle"] == controle].iloc[0]["ernst"] == "in orde"


def test_groeperen_op_dagboek_en_nummer_zag_het_niet():
    """De oude sleutel nagerekend op hetzelfde bestand, als bewijs."""
    af = _lees(_dubbel_transactienummer())

    oud = af.lines.groupby(["tx_jrnID", "tx_nr"], dropna=False)["bedrag"].sum()
    assert oud.abs().max() < 0.005

    nieuw = af.lines.groupby(transactie_sleutel(af.lines), dropna=False)["bedrag"].sum()
    assert sorted(nieuw[nieuw.abs() >= 0.005].round(2)) == [-SCHEEF, SCHEEF]


def test_twee_afzonderlijke_nummers_blijven_afzonderlijk():
    """Zonder hergebruik verandert er niets aan de uitkomst."""
    spec = _dubbel_transactienummer()
    spec.journals[0].transactions[1].nr = "6"
    af = _lees(spec)

    regel = _bevinding(af, BALANS)
    assert regel["ernst"] == "kritiek"
    assert regel["aantal"] == 2


# --- Het hergebruik zelf ----------------------------------------------------


def test_hergebruikt_nummer_wordt_apart_gemeld():
    af = _lees(_dubbel_transactienummer())

    regel = _bevinding(af, EENDUIDIG)
    assert regel["ernst"] == "waarschuwing"
    assert regel["aantal"] == 1
    assert "MEM 5" in regel["bevinding"]


def test_uniek_nummer_geeft_in_orde(af_40):
    regel = _bevinding(af_40, EENDUIDIG)
    assert regel["ernst"] == "in orde"
    assert regel["aantal"] == 0


def test_hetzelfde_nummer_in_twee_dagboeken_is_geen_hergebruik():
    """De eis geldt binnen het dagboek; daarbuiten zegt het nummer niets."""
    spec = AuditfileSpec(
        accounts=REKENINGEN,
        journals=[
            Journal(
                dagboek,
                f"Dagboek {dagboek}",
                [
                    Transaction(
                        "1",
                        "2025-05-31",
                        5,
                        [Line("1300", "100.00", "D"), Line("8000", "100.00", "C")],
                    )
                ],
            )
            for dagboek in ("MEM", "VRK")
        ],
    )
    af = _lees(spec)

    assert _bevinding(af, EENDUIDIG)["ernst"] == "in orde"
    assert _bevinding(af, BALANS)["ernst"] == "in orde"


# --- De sleutel zelf --------------------------------------------------------


def test_volgnummer_telt_door_over_de_dagboeken(af_40):
    """Elke transactie in het bestand heeft een eigen volgnummer."""
    per_transactie = af_40.lines[["tx_jrnID", "tx_nr", "tx_volgnr"]].drop_duplicates()
    assert not per_transactie["tx_volgnr"].duplicated().any()
    assert set(per_transactie["tx_volgnr"]) == {
        str(nummer) for nummer in range(1, len(per_transactie) + 1)
    }


def test_sleutel_valt_terug_op_het_bestandsnummer_zonder_volgnummer():
    """Een met de hand opgebouwd frame heeft de kolom niet; dan het nummer."""
    lines = pd.DataFrame({"tx_jrnID": ["MEM", "MEM"], "tx_nr": ["1", "2"]})
    sleutel = transactie_sleutel(lines)
    assert sleutel.nunique() == 2
    assert sleutel.iloc[0] != sleutel.iloc[1]


def test_sleutel_valt_terug_bij_een_half_gevulde_kolom():
    """Half gevuld zou alle regels zonder volgnummer op één hoop gooien."""
    lines = pd.DataFrame(
        {"tx_jrnID": ["MEM", "MEM"], "tx_nr": ["1", "2"], "tx_volgnr": ["1", ""]}
    )
    sleutel = transactie_sleutel(lines)
    assert sleutel.nunique() == 2
    assert list(sleutel) == list(transactie_sleutel(lines.drop(columns=["tx_volgnr"])))


def test_zonder_volgnummer_meldt_de_controle_dat_zij_niet_kan():
    """Geen volgnummer: dan is hergebruik niet vast te stellen, en dat zegt zij."""
    from auditfile.integrity import _controleer_transactienummers
    from auditfile.model import Auditfile

    af = Auditfile(
        bestandsnaam="handmatig.xaf",
        lines=pd.DataFrame({"tx_jrnID": ["MEM"], "tx_nr": ["1"], "bedrag": [0.0]}),
    )
    regel = _controleer_transactienummers(af)[0]
    assert regel["ernst"] == "niet mogelijk"
    assert regel["controle"] == EENDUIDIG


# --- Dezelfde sleutel in de btw-analyse en de suppletiedetectie -------------


def test_facturatie_afbakening_gebruikt_dezelfde_sleutel():
    """Een btw-code in de ene boeking mag de andere niet meesleuren."""
    spec = AuditfileSpec(
        accounts=REKENINGEN,
        vat_codes=[VatCode("1", "Hoog", vatToPayAccID="1800")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "7",
                        "2025-03-31",
                        3,
                        [
                            Line("1300", "121.00", "D"),
                            Line(
                                "8000",
                                "100.00",
                                "C",
                                vatID="1",
                                vatPerc="21",
                                vatAmnt="21.00",
                                vatAmntTp="C",
                            ),
                            Line("1800", "21.00", "C"),
                        ],
                    ),
                    Transaction(
                        "7",
                        "2025-04-30",
                        4,
                        [Line("1000", "50.00", "D"), Line("8000", "50.00", "C")],
                    ),
                ],
            )
        ],
    )
    af = _lees(spec)
    uit_facturatie = sup._uit_facturatie(af.lines)

    met_code = af.lines["tx_periodNumber"] == "3"
    assert uit_facturatie[met_code].all()
    assert not uit_facturatie[~met_code].any()


def test_suppletie_verdwijnt_niet_door_een_hergebruikt_nummer():
    """Onder de oude sleutel viel de suppletie weg als facturatieboeking."""
    spec = vul_suppletie(eenvoudige_spec("4.0"), 1_500.0)
    memoriaal = next(journaal for journaal in spec.journals if journaal.jrnID == "MEM")
    suppletie = next(tx for tx in memoriaal.transactions if tx.nr == "M910")
    # Een verkoopboeking in hetzelfde dagboek met hetzelfde transactienummer.
    memoriaal.transactions.append(
        Transaction(
            suppletie.nr,
            "2025-11-30",
            11,
            [
                Line("1300", "121.00", "D", "Verkoop in het memoriaal"),
                Line(
                    "8000",
                    "100.00",
                    "C",
                    "Omzet hoog",
                    vatID="1",
                    vatPerc="21",
                    vatAmnt="21.00",
                    vatAmntTp="C",
                ),
                Line("1800", "21.00", "C", "Btw hoog"),
            ],
        )
    )
    af = _lees(spec)

    gevonden = sup.detecteer_suppleties(af)
    assert len(gevonden) == 1
    assert gevonden.iloc[0]["bedrag"] == pytest.approx(-1_500.0)
