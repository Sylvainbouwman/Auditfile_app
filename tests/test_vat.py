"""Tests op de btw-analyse."""
from __future__ import annotations

import pandas as pd
import pytest

from auditfile.parsing import parse_auditfile
from auditfile.vat import (
    AANGEPAST,
    GEACCEPTEERD,
    VOORSTEL,
    build_ledger_reconciliation,
    build_rubric_summary,
    build_vat_anomalies,
    build_vat_drilldown,
    build_vat_ledger_flow,
    build_vat_position,
    build_vat_usage,
    btw_grootboekrekeningen,
    pas_mapping_toe,
    voorstelstatus,
)
from auditfile.vat_rubrics import ONBEKEND, RUBRIEK_CODES
from auditfile.demo import (
    Account,
    AuditfileSpec,
    Journal,
    Line,
    Transaction,
    VatCode,
    build_xaf,
)


@pytest.fixture
def usage(af_40):
    return build_vat_usage(af_40)


# --- Gebruik per code -------------------------------------------------------


def test_alle_gebruikte_codes_komen_terug(usage):
    assert set(usage["btw_code"]) == {"1", "2", "3"}


def test_grondslag_en_btw_behouden_hun_teken(usage):
    """Omzet staat credit, voorbelasting debet; dat moet zichtbaar blijven."""
    per_code = usage.set_index("btw_code")
    assert per_code.loc["1", "grondslag_grootboek"] < 0
    assert per_code.loc["1", "btw_grootboek"] < 0
    assert per_code.loc["3", "grondslag_grootboek"] > 0
    assert per_code.loc["3", "btw_grootboek"] > 0


def test_grondslag_telt_creditnota_mee(usage):
    """Omzet hoog is 1.000 minus een creditnota van 200."""
    per_code = usage.set_index("btw_code")
    assert round(per_code.loc["1", "grondslag_grootboek"], 2) == -800.00
    assert round(per_code.loc["1", "btw_grootboek"], 2) == -168.00


def test_voorbelasting_over_twaalf_maanden(usage):
    per_code = usage.set_index("btw_code")
    assert round(per_code.loc["3", "grondslag_grootboek"], 2) == 12000.00
    assert round(per_code.loc["3", "btw_grootboek"], 2) == 2520.00
    assert per_code.loc["3", "aantal_regels"] == 12


# --- Rubrieksuggestie -------------------------------------------------------


def test_omzetcode_hoog_wordt_1a(usage):
    per_code = usage.set_index("btw_code")
    assert per_code.loc["1", "rubriek_voorstel"] == "1a"


def test_omzetcode_laag_wordt_1b(usage):
    per_code = usage.set_index("btw_code")
    assert per_code.loc["2", "rubriek_voorstel"] == "1b"


def test_inkoopcode_wordt_voorbelasting(usage):
    per_code = usage.set_index("btw_code")
    assert per_code.loc["3", "rubriek_voorstel"] == "5b"


def test_elke_suggestie_heeft_een_reden(usage):
    assert (usage["reden"].str.len() > 0).all()
    assert set(usage["zekerheid"]) <= {"hoog", "middel", "laag", "geen"}


def _usage_voor_code(vat_code: VatCode, regels: list[Line]) -> pd.DataFrame:
    """Bouw een minimaal auditfile met één btw-code en geef het gebruik terug."""
    spec = AuditfileSpec(
        accounts=[
            Account("1300", "Debiteuren", "B"),
            Account("1600", "Crediteuren", "B"),
            Account("4000", "Kosten", "P"),
            Account("8000", "Omzet", "P"),
        ],
        vat_codes=[vat_code],
        journals=[Journal("MEM", "Memoriaal", [Transaction("T1", "2025-01-01", 1, regels)])],
    )
    return build_vat_usage(parse_auditfile("test.xaf", build_xaf(spec)))


def test_expliciete_rubriekcode_in_omschrijving_wint():
    usage = _usage_voor_code(
        VatCode("H", "1c Overige tarieven"),
        [
            Line("8000", "100.00", "C", vatID="H", vatPerc="21", vatAmnt="21.00", vatAmntTp="C"),
            Line("1300", "121.00", "D"),
        ],
    )
    rij = usage.iloc[0]
    assert rij["rubriek_voorstel"] == "1c"
    assert rij["zekerheid"] == "hoog"


def test_verlegging_bij_omzet_wordt_1e():
    usage = _usage_voor_code(
        VatCode("V", "Btw verlegd"),
        [
            Line("8000", "1000.00", "C", vatID="V", vatPerc="0", vatAmnt="0.00", vatAmntTp="C"),
            Line("1300", "1000.00", "D"),
        ],
    )
    assert usage.iloc[0]["rubriek_voorstel"] == "1e"


def test_verlegging_bij_inkoop_wordt_2a():
    """Dezelfde term aan de inkoopkant betekent een andere rubriek."""
    usage = _usage_voor_code(
        VatCode("V", "Btw verlegd"),
        [
            Line("4000", "1000.00", "D", vatID="V", vatPerc="21", vatAmnt="210.00", vatAmntTp="D"),
            Line("1600", "1000.00", "C"),
        ],
    )
    assert usage.iloc[0]["rubriek_voorstel"] == "2a"


def test_code_zonder_aanwijzing_blijft_onbekend():
    usage = _usage_voor_code(
        VatCode("X", "Code X"),
        [
            Line("4000", "1000.00", "D", vatID="X", vatPerc="0", vatAmnt="0.00", vatAmntTp="D"),
            Line("1600", "1000.00", "C"),
        ],
    )
    rij = usage.iloc[0]
    assert rij["rubriek_voorstel"] == ONBEKEND
    assert rij["zekerheid"] in {"laag", "geen"}


# --- Mapping ----------------------------------------------------------------


def test_keuze_van_gebruiker_gaat_voor_op_voorstel(usage):
    toegepast = pas_mapping_toe(usage, {"1": "1c"})
    per_code = toegepast.set_index("btw_code")
    assert per_code.loc["1", "rubriek"] == "1c"
    assert per_code.loc["1", "rubriek_bron"] == AANGEPAST
    assert per_code.loc["2", "rubriek_bron"] == VOORSTEL


def test_overgenomen_voorstel_heet_geaccepteerd(usage):
    """Een vastgelegde keuze die gelijk is aan het voorstel is beoordeeld.

    Zonder dit onderscheid is niet te zien of iemand naar een code heeft
    gekeken, en gaat een voorstel voor een keuze door.
    """
    per_code = usage.set_index("btw_code")
    voorstel = per_code.loc["1", "rubriek_voorstel"]
    toegepast = pas_mapping_toe(usage, {"1": voorstel})
    assert toegepast.set_index("btw_code").loc["1", "rubriek_bron"] == GEACCEPTEERD


def test_voorstelstatus_telt_wat_nog_niet_is_beoordeeld(usage):
    zonder = voorstelstatus(pas_mapping_toe(usage, {}))
    assert zonder["codes"] == 3
    assert zonder["voorstellen"] == 3
    assert zonder["codes_beoordeeld"] == 0
    assert zonder["btw_op_voorstel"] > 0

    met_een = voorstelstatus(pas_mapping_toe(usage, {"1": "1c"}))
    assert met_een["voorstellen"] == 2
    assert met_een["codes_beoordeeld"] == 1
    # De btw van de beoordeelde code telt niet meer als openstaand voorstel.
    assert met_een["btw_op_voorstel"] < zonder["btw_op_voorstel"]


def test_voorstelstatus_op_een_lege_tabel():
    leeg = voorstelstatus(pd.DataFrame())
    assert leeg == {"codes": 0, "voorstellen": 0, "btw_op_voorstel": 0.0, "codes_beoordeeld": 0}


def test_aangiftebedragen_zijn_positief_bij_normale_boekingen(usage):
    toegepast = pas_mapping_toe(usage)
    per_code = toegepast.set_index("btw_code")
    # Omzet: grootboek credit, aangifte positief.
    assert per_code.loc["1", "grondslag_aangifte"] > 0
    assert per_code.loc["1", "btw_aangifte"] > 0
    # Voorbelasting: grootboek debet, aangifte positief.
    assert per_code.loc["3", "btw_aangifte"] > 0


# --- Optelling per rubriek --------------------------------------------------


def test_rubrieksamenvatting_behoudt_teken_van_verschil(usage):
    toegepast = pas_mapping_toe(usage)
    samenvatting = build_rubric_summary(toegepast, {"1a": 1000.00, "1b": 0.00, "5b": 1.00})
    per_rubriek = samenvatting.set_index("rubriek")
    # Aangifte hoger dan de auditfile geeft een negatief verschil; dat mag niet
    # worden weggenomen met een absolute waarde.
    assert per_rubriek.loc["1a", "verschil"] < 0
    assert per_rubriek.loc["5b", "verschil"] > 0


def test_verschillen_heffen_elkaar_niet_op():
    """Een plus en een min in verschillende rubrieken blijven zichtbaar."""
    usage = pd.DataFrame(
        {
            "btw_code": ["A", "B"],
            "omschrijving": ["1a hoog", "5b voorbelasting"],
            "aantal_regels": [1, 1],
            "grondslag_grootboek": [-1000.0, 1000.0],
            "btw_grootboek": [-210.0, 210.0],
            "percentages": ["21%", "21%"],
            "hoofdpercentage": [21.0, 21.0],
            "aandeel_credit": [1.0, 0.0],
            "rubriek_voorstel": ["1a", "5b"],
            "zekerheid": ["hoog", "hoog"],
            "reden": ["", ""],
        }
    )
    toegepast = pas_mapping_toe(usage)
    samenvatting = build_rubric_summary(toegepast, {"1a": 110.0, "5b": 310.0})
    per_rubriek = samenvatting.set_index("rubriek")
    assert round(per_rubriek.loc["1a", "verschil"], 2) == 100.00
    assert round(per_rubriek.loc["5b", "verschil"], 2) == -100.00


def test_rubrieken_staan_in_volgorde_van_het_aangifteformulier(usage):
    samenvatting = build_rubric_summary(pas_mapping_toe(usage))
    aanwezig = [code for code in samenvatting["rubriek"] if code in RUBRIEK_CODES]
    volgorde = [code for code in RUBRIEK_CODES if code in aanwezig]
    assert aanwezig == volgorde


def test_status_meldt_ontbrekende_aangifte(usage):
    samenvatting = build_rubric_summary(pas_mapping_toe(usage), {})
    assert set(samenvatting.loc[samenvatting["rubriek"] != ONBEKEND, "status"]) <= {
        "Geen aangifte ingevuld",
        "Alleen grondslag",
    }


# --- Netto positie ----------------------------------------------------------


def test_netto_positie_is_afdracht_min_voorbelasting(usage):
    samenvatting = build_rubric_summary(pas_mapping_toe(usage))
    positie = build_vat_position(samenvatting)
    assert round(positie["af_te_dragen"], 2) == 177.00  # 168 hoog + 9 laag
    assert round(positie["voorbelasting"], 2) == 2520.00
    assert round(positie["netto"], 2) == round(177.00 - 2520.00, 2)


def test_verlegde_btw_telt_mee_in_de_afdracht():
    """Rubriek 2a hoort in de afdracht; dat ging in de oude opzet mis."""
    spec = AuditfileSpec(
        accounts=[Account("4000", "Kosten", "P"), Account("1600", "Crediteuren", "B")],
        vat_codes=[VatCode("V", "Btw verlegd")],
        journals=[
            Journal(
                "INK",
                "Inkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [
                            Line("4000", "1000.00", "D", vatID="V", vatPerc="21", vatAmnt="210.00", vatAmntTp="D"),
                            Line("1600", "1000.00", "C"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("verlegd.xaf", build_xaf(spec))
    samenvatting = build_rubric_summary(pas_mapping_toe(build_vat_usage(af)))
    positie = build_vat_position(samenvatting)
    assert "2a" in set(samenvatting["rubriek"])
    assert round(positie["af_te_dragen"], 2) != 0.00


def test_niet_ingedeelde_codes_worden_apart_gemeld():
    usage = pd.DataFrame(
        {
            "btw_code": ["X"],
            "omschrijving": ["Onbekend"],
            "aantal_regels": [1],
            "grondslag_grootboek": [1000.0],
            "btw_grootboek": [210.0],
            "percentages": [""],
            "hoofdpercentage": [float("nan")],
            "aandeel_credit": [0.0],
            "rubriek_voorstel": [ONBEKEND],
            "zekerheid": ["geen"],
            "reden": [""],
        }
    )
    samenvatting = build_rubric_summary(pas_mapping_toe(usage))
    positie = build_vat_position(samenvatting)
    assert positie["af_te_dragen"] == 0.0
    assert positie["niet_ingedeeld"] != 0.0


# --- Aansluiting met het grootboek ------------------------------------------


def test_btw_rekeningen_komen_uit_de_codetabel(af_40):
    """De codetabel wijst de btw-rekeningen zelf aan; niet zoeken op nummer."""
    assert btw_grootboekrekeningen(af_40) == ["1800", "1810"]


def test_grootboekaansluiting_toont_beide_rollen(af_40):
    aansluiting = build_ledger_reconciliation(af_40)
    assert set(aansluiting["rekening"]) == {"1800", "1810"}
    assert set(aansluiting["rol"]) == {"Te betalen", "Te vorderen"}


def test_rondrekening_sluit_aan_op_de_fixture(af_40):
    """In de fixture is elke btw-boeking ook op de btw-rekening geboekt."""
    samenvatting = build_rubric_summary(pas_mapping_toe(build_vat_usage(af_40)))
    verloop = build_vat_ledger_flow(af_40, samenvatting).set_index("post")
    controle = verloop.loc["Controle: btw uit facturatie tegenover de btw-codes", "bedrag"]
    assert round(float(controle), 2) == 0.00


def test_rondrekening_verklaart_het_saldoverloop(af_40):
    """Begin plus alle mutaties moet gelijk zijn aan het eindsaldo."""
    samenvatting = build_rubric_summary(pas_mapping_toe(build_vat_usage(af_40)))
    verloop = build_vat_ledger_flow(af_40, samenvatting).set_index("post")["bedrag"]
    opgebouwd = (
        verloop["Beginsaldo btw-rekeningen"]
        + verloop["Btw uit facturatie"]
        + verloop["Afdrachten en teruggaven"]
        + verloop["Overige mutaties"]
    )
    assert round(float(opgebouwd), 2) == round(float(verloop["Eindsaldo btw-rekeningen"]), 2)


def test_rondrekening_scheidt_afdracht_van_facturatie():
    """Een betaling aan de Belastingdienst mag niet als facturatie tellen."""
    spec = AuditfileSpec(
        accounts=[
            Account("1100", "Bank", "B", "BLimBan", "BLimBan"),
            Account("1800", "Omzetbelasting", "B"),
            Account("1300", "Debiteuren", "B"),
            Account("8000", "Omzet", "P"),
        ],
        vat_codes=[VatCode("1", "1a Omzet hoog", vatToPayAccID="1800")],
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
                            Line("8000", "1000.00", "C", vatID="1", vatPerc="21", vatAmnt="210.00", vatAmntTp="C"),
                            Line("1800", "210.00", "C"),
                        ],
                    )
                ],
            ),
            Journal(
                "BNK",
                "Bank",
                [
                    Transaction(
                        "B1",
                        "2025-04-30",
                        4,
                        [Line("1800", "210.00", "D", "Afdracht btw"), Line("1100", "210.00", "C")],
                    )
                ],
            ),
        ],
    )
    af = parse_auditfile("afdracht.xaf", build_xaf(spec))
    samenvatting = build_rubric_summary(pas_mapping_toe(build_vat_usage(af)))
    verloop = build_vat_ledger_flow(af, samenvatting).set_index("post")["bedrag"]
    assert round(float(verloop["Btw uit facturatie"]), 2) == -210.00
    assert round(float(verloop["Afdrachten en teruggaven"]), 2) == 210.00
    assert round(float(verloop["Overige mutaties"]), 2) == 0.00
    assert round(float(verloop["Eindsaldo btw-rekeningen"]), 2) == 0.00


def test_rondrekening_toont_correctie_als_overige_mutatie():
    """Een suppletieboeking zonder btw-code en zonder bank valt op als 'overig'."""
    spec = AuditfileSpec(
        accounts=[
            Account("1800", "Omzetbelasting", "B"),
            Account("2900", "Nog te betalen", "B"),
        ],
        vat_codes=[VatCode("1", "1a Omzet hoog", vatToPayAccID="1800")],
        journals=[
            Journal(
                "MEM",
                "Memoriaal",
                [
                    Transaction(
                        "M1",
                        "2025-12-31",
                        12,
                        [Line("1800", "500.00", "C", "Suppletie"), Line("2900", "500.00", "D")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("suppletie.xaf", build_xaf(spec))
    samenvatting = build_rubric_summary(pas_mapping_toe(build_vat_usage(af)))
    verloop = build_vat_ledger_flow(af, samenvatting).set_index("post")["bedrag"]
    assert round(float(verloop["Overige mutaties"]), 2) == -500.00


def test_signaal_grondslag_inclusief_btw():
    """Een code die aan een bedrag inclusief btw hangt krijgt een eigen signaal."""
    spec = AuditfileSpec(
        accounts=[Account("4000", "Kosten", "P"), Account("1600", "Crediteuren", "B")],
        vat_codes=[VatCode("3", "5b Voorbelasting", vatToClaimAccID="1810")],
        journals=[
            Journal(
                "INK",
                "Inkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [
                            # 210 btw op een grondslag van 1.210 is 21% inclusief.
                            Line("4000", "1210.00", "D", vatID="3", vatPerc="21", vatAmnt="210.00", vatAmntTp="D"),
                            Line("1600", "1210.00", "C"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("inclusief.xaf", build_xaf(spec))
    signalen = set(build_vat_anomalies(af)["signaal"])
    assert "Grondslag lijkt inclusief btw geboekt" in signalen
    assert "Btw-bedrag past niet bij grondslag maal percentage" not in signalen


# --- Anomalieën -------------------------------------------------------------


def test_anomalie_btw_bedrag_wijkt_af_van_percentage():
    spec = AuditfileSpec(
        accounts=[Account("8000", "Omzet", "P"), Account("1300", "Debiteuren", "B")],
        vat_codes=[VatCode("1", "Omzet hoog 21%")],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [
                            # 21% van 1.000 is 210, hier staat 300.
                            Line("8000", "1000.00", "C", vatID="1", vatPerc="21", vatAmnt="300.00", vatAmntTp="C"),
                            Line("1300", "1300.00", "D"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("afwijkend.xaf", build_xaf(spec))
    anomalieen = build_vat_anomalies(af)
    assert "Btw-bedrag past niet bij grondslag maal percentage" in set(anomalieen["signaal"])


def test_afronding_per_regel_geeft_geen_signaal(af_40):
    """De standaardfixture is boekhoudkundig correct en mag niet piepen."""
    anomalieen = build_vat_anomalies(af_40)
    assert "Btw-bedrag past niet bij grondslag maal percentage" not in set(anomalieen["signaal"])


def test_anomalie_omzet_zonder_btw_code():
    spec = AuditfileSpec(
        accounts=[Account("8000", "Omzet", "P"), Account("1300", "Debiteuren", "B")],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [Line("8000", "1000.00", "C"), Line("1300", "1000.00", "D")],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("zonder_code.xaf", build_xaf(spec))
    anomalieen = build_vat_anomalies(af).set_index("signaal")
    assert "Omzetboeking zonder btw-code" in anomalieen.index
    assert anomalieen.loc["Omzetboeking zonder btw-code", "aantal_regels"] == 1


def test_lonen_geven_geen_signaal_kosten_zonder_btw(af_40):
    """Op loonkosten hoort geen btw; dat mag geen ruis opleveren."""
    anomalieen = build_vat_anomalies(af_40)
    rij = anomalieen[anomalieen["signaal"] == "Kostenboeking zonder btw-code"]
    if not rij.empty:
        drilldown = build_vat_drilldown(af_40)
        assert "Brutolonen" not in set(drilldown["rekeningomschrijving"])


def test_anomalie_meerdere_tarieven_in_afdrachtrubriek():
    spec = AuditfileSpec(
        accounts=[Account("8000", "Omzet", "P"), Account("1300", "Debiteuren", "B")],
        vat_codes=[VatCode("1", "Omzet")],
        journals=[
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [
                            Line("8000", "1000.00", "C", vatID="1", vatPerc="21", vatAmnt="210.00", vatAmntTp="C"),
                            Line("8000", "1000.00", "C", vatID="1", vatPerc="9", vatAmnt="90.00", vatAmntTp="C"),
                            Line("1300", "2300.00", "D"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("twee_tarieven.xaf", build_xaf(spec))
    usage = pas_mapping_toe(build_vat_usage(af))
    anomalieen = build_vat_anomalies(af, usage)
    assert "Btw-code met meerdere tarieven in een afdrachtrubriek" in set(anomalieen["signaal"])


# --- Drilldown --------------------------------------------------------------


def test_drilldown_toont_verwachte_btw_en_afwijking(af_40):
    drilldown = build_vat_drilldown(af_40, "3")
    assert len(drilldown) == 12
    assert (drilldown["afwijking"].abs() < 0.005).all()


def test_drilldown_vervangt_relatienummer_door_naam(af_40):
    drilldown = build_vat_drilldown(af_40)
    relaties = set(drilldown["relatie"]) - {""}
    assert relaties <= {"Afnemer Alfa BV", "Leverancier Beta BV"}


def test_drilldown_zonder_code_bevat_alle_codes(af_40):
    drilldown = build_vat_drilldown(af_40)
    assert set(drilldown["btw_code"]) == {"1", "2", "3"}


def test_voorbelastingcode_met_meerdere_tarieven_geeft_geen_signaal():
    """Een inkoopcode dekt normaal alle tarieven; dat is geen bijzonderheid."""
    spec = AuditfileSpec(
        accounts=[Account("4000", "Kosten", "P"), Account("1600", "Crediteuren", "B")],
        vat_codes=[VatCode("3", "5b Voorbelasting")],
        journals=[
            Journal(
                "INK",
                "Inkoopboek",
                [
                    Transaction(
                        "T1",
                        "2025-01-01",
                        1,
                        [
                            Line("4000", "1000.00", "D", vatID="3", vatPerc="21", vatAmnt="210.00", vatAmntTp="D"),
                            Line("4000", "1000.00", "D", vatID="3", vatPerc="9", vatAmnt="90.00", vatAmntTp="D"),
                            Line("1600", "2300.00", "C"),
                        ],
                    )
                ],
            )
        ],
    )
    af = parse_auditfile("inkoop_tarieven.xaf", build_xaf(spec))
    usage = pas_mapping_toe(build_vat_usage(af))
    signalen = set(build_vat_anomalies(af, usage)["signaal"])
    assert "Btw-code met meerdere tarieven in een afdrachtrubriek" not in signalen
