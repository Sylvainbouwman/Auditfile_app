"""De subadministratie van XAF 3.2 inlezen: ``obSbLine`` en ``sbLine``.

Dit is de enige bron in XAF met een echte vervaldatum. De valkuil zit niet in de
velden zelf maar in de rekening: geen van beide regelsoorten draagt een
rekeningnummer. ``obSbLine`` verwijst met ``obLineNr`` naar een regel van de
beginbalans, ``sbLine`` met ``jrnID``, ``trNr`` en ``trLineNr`` naar een
grootboekboeking. De belangrijkste tests hieronder gaan daarom over die
verwijzing, en over wat er gebeurt wanneer zij niet op te lossen is.

Alle bestanden zijn synthetisch en worden in het geheugen opgebouwd.
"""
from __future__ import annotations

import pandas as pd

from auditfile.capability import NIVEAU_VERVALDATUM, openstaande_posten_niveau
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
    build_xaf,
    demopaar,
)
from auditfile.model import SUBADMINISTRATIE_COLUMNS, SUBADMINISTRATIE_TOTALEN_COLUMNS
from auditfile.parsing import NIET_EENDUIDIG, NIET_GEKOPPELD, parse_auditfile

REKENINGEN = [
    Account("1100", "Bank", "B", leadReference="BLimBan"),
    Account("1300", "Debiteuren", "B", leadReference="BVorDeb"),
    Account("8000", "Omzet", "P", leadReference="WOmzNeh"),
]

# De beginbalans van deze fixture. Regel 2 is de debiteurenrekening; naar dat
# nummer verwijzen de openstaande beginposten hieronder.
BEGINBALANS = [
    OpeningLine("1100", "5000.00", "D"),
    OpeningLine("1300", "1210.00", "D"),
]

DEBITEUREN_OB_REGEL = "2"


def _verkoopboek() -> list[Journal]:
    """Eén factuur en één ontvangst, allebei met een regel op de debiteuren."""
    return [
        Journal(
            "VRK",
            "Verkoopboek",
            [
                Transaction(
                    "V001",
                    "2025-01-31",
                    1,
                    [
                        Line("1300", "605.00", "D", "Verkoopfactuur", custSupID="D001", invRef="F001"),
                        Line("8000", "605.00", "C", "Omzet"),
                    ],
                ),
                Transaction(
                    "V002",
                    "2025-02-28",
                    2,
                    [
                        Line("1100", "605.00", "D", "Ontvangst"),
                        Line("1300", "605.00", "C", "Afboeking debiteur", custSupID="D001", invRef="F001"),
                    ],
                ),
            ],
        )
    ]


def _bestand(
    *,
    versie: str = "3.2",
    ob_subledgers: list | None = None,
    subledgers: list | None = None,
    journals: list | None = None,
):
    spec = AuditfileSpec(
        versie=versie,
        accounts=list(REKENINGEN),
        relations=[Relation("D001", "Afnemer Alfa BV", "C")],
        opening_lines=list(BEGINBALANS),
        journals=journals if journals is not None else _verkoopboek(),
        ob_subledgers=ob_subledgers or [],
        subledgers=subledgers or [],
    )
    return parse_auditfile(f"synthetisch_{versie}.xaf", build_xaf(spec))


def _beginpost(**overrides) -> ObSubledger:
    velden = {
        "obLineNr": DEBITEUREN_OB_REGEL,
        "amnt": "1210.00",
        "amntTp": "D",
        "custSupID": "D001",
        "invRef": "F000",
        "invDt": "2024-12-01",
        "invDueDt": "2024-12-31",
        "matchKeyID": "AFL-1",
    }
    velden.update(overrides)
    return ObSubledger([ObSubledgerLine(**velden)])


def _mutatie(**overrides) -> Subledger:
    velden = {
        "jrnID": "VRK",
        "trNr": "V001",
        "trLineNr": "1",
        "amnt": "605.00",
        "amntTp": "D",
        "custSupID": "D001",
        "invRef": "F001",
        "invDt": "2025-01-31",
        "invDueDt": "2025-03-02",
        "matchKeyID": "AFL-2",
    }
    velden.update(overrides)
    return Subledger([SbLine(**velden)])


# --- De verwijzing naar het grootboek ---------------------------------------


def test_de_beginpost_vindt_haar_rekening_via_oblinenr():
    """``obSbLine`` heeft geen ``accID``; de rekening komt van de beginbalansregel."""
    af = _bestand(ob_subledgers=[_beginpost()])
    regel = af.subadministratie.iloc[0]
    assert regel["bron"] == "beginbalans"
    assert regel["rekening"] == "1300"
    assert regel["koppeling"] == "obLineNr"
    assert regel["bedrag"] == 1210.00


def test_de_mutatie_vindt_haar_rekening_via_dagboek_transactie_en_regel():
    """``sbLine`` heeft ook geen ``accID``; de rekening komt van de boekingsregel."""
    af = _bestand(subledgers=[_mutatie()])
    regel = af.subadministratie.iloc[0]
    assert regel["bron"] == "mutatie"
    assert regel["rekening"] == "1300"
    assert regel["koppeling"] == "jrnID/trNr/trLineNr"


def test_een_verwijzing_die_niet_bestaat_levert_geen_rekening():
    """Liever geen rekening dan een verkeerde.

    Een subadministratie die naar een regel wijst die er niet is, hoort niet stil
    op de eerste of op een willekeurige rekening te belanden: dan zou de post op
    het grootboek worden aangesloten dat er niets mee te maken heeft.
    """
    af = _bestand(
        ob_subledgers=[_beginpost(obLineNr="99")],
        subledgers=[_mutatie(trNr="V999")],
    )
    assert list(af.subadministratie["rekening"]) == ["", ""]
    assert set(af.subadministratie["koppeling"]) == {NIET_GEKOPPELD}


def test_een_dubbele_boekingssleutel_naar_twee_rekeningen_is_niet_eenduidig():
    """Alleen ``jrnID`` is in het schema vastgelegd, ``trNr`` niet.

    Hergebruikt een pakket hetzelfde transactienummer, dan wijst één sleutel naar
    twee boekingsregels. Wijzen die naar verschillende rekeningen, dan valt de
    rekening niet vast te stellen en zegt de tool dat, in plaats van de eerste te
    pakken.
    """
    dubbel = [
        Journal(
            "VRK",
            "Verkoopboek",
            [
                Transaction("V001", "2025-01-31", 1, [Line("1300", "605.00", "D", "Factuur")]),
                Transaction("V001", "2025-02-28", 2, [Line("8000", "605.00", "C", "Omzet")]),
            ],
        )
    ]
    af = _bestand(journals=dubbel, subledgers=[_mutatie()])
    regel = af.subadministratie.iloc[0]
    assert regel["rekening"] == ""
    assert regel["koppeling"] == NIET_EENDUIDIG


def test_een_dubbele_sleutel_naar_dezelfde_rekening_blijft_eenduidig():
    """Een terugkerende maandboeking op dezelfde rekening blijft koppelbaar.

    Pakketten schrijven een vaste maandboeking vaak onder hetzelfde
    transactienummer. Zolang die regels naar dezelfde rekening wijzen, is de
    uitkomst niet in twijfel en hoort de koppeling gewoon te lukken.
    """
    maandelijks = [
        Journal(
            "INK",
            "Inkoopboek",
            [
                Transaction(
                    "I001",
                    f"2025-{maand:02d}-15",
                    maand,
                    [Line("1300", "100.00", "D", "Maandfactuur", custSupID="D001")],
                )
                for maand in range(1, 4)
            ],
        )
    ]
    af = _bestand(
        journals=maandelijks,
        subledgers=[_mutatie(jrnID="INK", trNr="I001", trLineNr="1")],
    )
    regel = af.subadministratie.iloc[0]
    assert regel["rekening"] == "1300"
    assert regel["koppeling"] == "jrnID/trNr/trLineNr"


# --- Bedragen en datums -----------------------------------------------------


def test_een_creditregel_komt_negatief_in_het_model():
    """Dezelfde tekenconventie als bij de grootboekregels: debet positief."""
    af = _bestand(subledgers=[_mutatie(trNr="V002", trLineNr="2", amntTp="C")])
    regel = af.subadministratie.iloc[0]
    assert regel["amntTp"] == "C"
    assert regel["bedrag"] == -605.00


def test_de_vervaldatum_wordt_een_datum():
    af = _bestand(ob_subledgers=[_beginpost()], subledgers=[_mutatie()])
    sub = af.subadministratie
    assert pd.api.types.is_datetime64_any_dtype(sub["invDt"])
    assert pd.api.types.is_datetime64_any_dtype(sub["invDueDt"])
    assert sub.loc[sub["bron"] == "beginbalans", "invDueDt"].iloc[0] == pd.Timestamp("2024-12-31")
    assert sub.loc[sub["bron"] == "mutatie", "invDt"].iloc[0] == pd.Timestamp("2025-01-31")


def test_een_ontbrekende_of_onleesbare_datum_blijft_leeg():
    """Een veld dat er niet staat of niet te lezen is, mag geen gegeven worden.

    Zonder deze regel zou een onleesbare datum als vandaag of als 1970 in de
    ouderdomsanalyse belanden, en dat is geen ontbrekend gegeven maar een fout
    gegeven.
    """
    af = _bestand(
        ob_subledgers=[_beginpost(invDt="", invDueDt="")],
        subledgers=[_mutatie(invDueDt="geen datum")],
    )
    sub = af.subadministratie
    assert sub.loc[sub["bron"] == "beginbalans", ["invDt", "invDueDt"]].isna().all().all()
    assert pd.isna(sub.loc[sub["bron"] == "mutatie", "invDueDt"].iloc[0])


def test_een_leeg_optioneel_veld_blijft_leeg_en_wordt_niet_verzonnen():
    af = _bestand(subledgers=[_mutatie(mutTp="", matchKeyID="")])
    regel = af.subadministratie.iloc[0]
    assert regel["mutTp"] == ""
    assert regel["matchKeyID"] == ""


# --- Meerdere subadministraties en hun controletotalen ----------------------


def test_twee_subadministraties_houden_hun_eigen_soort_en_nummer():
    """``sbType`` wordt onveranderd doorgegeven.

    Wat CS, CU, SU en ZZ betekenen is niet uit een gezaghebbende bron vast te
    stellen, dus de tool leidt er niets uit af en geeft de code door.
    """
    af = _bestand(
        subledgers=[
            Subledger([SbLine("VRK", "V001", "1", "605.00", "D")], sbType="CU", sbDesc="Debiteuren"),
            Subledger([SbLine("VRK", "V002", "2", "605.00", "C")], sbType="SU", sbDesc="Crediteuren"),
        ]
    )
    sub = af.subadministratie
    assert list(sub["sbType"]) == ["CU", "SU"]
    assert list(sub["sb_index"]) == [1, 2]
    assert list(af.subadministratie_totalen["sbDesc"]) == ["Debiteuren", "Crediteuren"]


def test_de_controletotalen_van_het_bestand_komen_naast_wat_er_is_gelezen():
    af = _bestand(ob_subledgers=[_beginpost()], subledgers=[_mutatie()])
    totalen = af.subadministratie_totalen.set_index("bron")
    for bron, debet in (("beginbalans", 1210.00), ("mutatie", 605.00)):
        rij = totalen.loc[bron]
        assert rij["regels_volgens_bestand"] == rij["regels_gelezen"] == 1
        assert rij["totaal_debet_volgens_bestand"] == rij["totaal_debet_gelezen"] == debet
        assert rij["totaal_credit_volgens_bestand"] == rij["totaal_credit_gelezen"] == 0.0


def test_een_afwijkend_controletotaal_blijft_zichtbaar_afwijken():
    """De parser rekent het totaal van het bestand niet recht.

    Zou hij het overschrijven met zijn eigen telling, dan viel een onvolledig
    blok nooit meer op.
    """
    subledger = _mutatie()
    subledger.totals_override = (9, "99.00", "0.00")
    af = _bestand(subledgers=[subledger])
    rij = af.subadministratie_totalen.iloc[0]
    assert rij["regels_volgens_bestand"] == 9
    assert rij["regels_gelezen"] == 1
    assert rij["totaal_debet_volgens_bestand"] == 99.00
    assert rij["totaal_debet_gelezen"] == 605.00


# --- Wanneer er niets is ----------------------------------------------------


def test_versie_40_levert_een_lege_subadministratie():
    """XAF 4.0 heeft deze blokken geschrapt, dus valt er niets te lezen.

    De spec draagt hier wél subadministratieregels; de generator schrijft ze bij
    4.0 niet weg, precies zoals een pakket dat niet zou doen.
    """
    af = _bestand(versie="4.0", ob_subledgers=[_beginpost()], subledgers=[_mutatie()])
    assert af.subadministratie.empty
    assert list(af.subadministratie.columns) == SUBADMINISTRATIE_COLUMNS
    assert list(af.subadministratie_totalen.columns) == SUBADMINISTRATIE_TOTALEN_COLUMNS
    # Ook leeg horen de datumkolommen datums te zijn, anders mislukt een filter stil.
    assert pd.api.types.is_datetime64_any_dtype(af.subadministratie["invDueDt"])


def test_een_32_bestand_zonder_subadministratie_geeft_een_lege_tabel():
    af = _bestand()
    assert af.subadministratie.empty
    assert af.subadministratie_totalen.empty
    assert list(af.subadministratie.columns) == SUBADMINISTRATIE_COLUMNS


# --- Het demobestand --------------------------------------------------------


def test_het_demobestand_van_vorig_jaar_draagt_een_gevulde_subadministratie():
    """De demo laat zien hoe een bestand met vervaldatums eruitziet.

    Het huidige jaar in de demo is XAF 4.0 en kent de blokken niet; het vorige
    jaar is 3.2 en vult ze, zodat het hoogste bewijsniveau ook zonder klantdata
    te zien is.
    """
    vorig_bytes, _ = demopaar()
    af = parse_auditfile("demo_vorig_jaar.xaf", vorig_bytes)

    assert not af.subadministratie.empty
    assert af.subadministratie["invDueDt"].notna().all()
    # Elke regel is aan een grootboekrekening gekoppeld; de demo bevat geen
    # verwijzing die nergens heen leidt.
    assert (af.subadministratie["rekening"] != "").all()
    assert set(af.subadministratie["bron"]) == {"beginbalans", "mutatie"}
    assert openstaande_posten_niveau(af)[0] == NIVEAU_VERVALDATUM


def test_de_demosubadministratie_sluit_op_haar_eigen_controletotalen():
    vorig_bytes, _ = demopaar()
    af = parse_auditfile("demo_vorig_jaar.xaf", vorig_bytes)
    totalen = af.subadministratie_totalen
    for kolom in ("regels", "totaal_debet", "totaal_credit"):
        assert (totalen[f"{kolom}_volgens_bestand"] == totalen[f"{kolom}_gelezen"]).all()
