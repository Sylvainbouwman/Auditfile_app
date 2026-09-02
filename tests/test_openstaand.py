"""Openstaande posten en ouderdom uit de subadministratie van XAF 3.2.

De engine maakt van losse subadministratieregels posten en hangt daar een
ouderdom aan. De tests hieronder gaan vooral over de plekken waar dat mis kan
gaan: de sleutel waarop wordt gegroepeerd, een post die niet aan een rekening of
aan een soort is toe te wijzen, en een post zonder datum. Dat laatste is het
gevaarlijkst, want een post die stilzwijgend in de laagste ouderdomsklasse valt
maakt de opbouw gunstiger dan het bestand toelaat.

Alle bestanden zijn synthetisch en worden in het geheugen opgebouwd.
"""
from __future__ import annotations

import pandas as pd
import pytest

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
    eenvoudige_spec,
    verschuif_boekjaar,
    vul_subadministratie,
)
from auditfile.findings import verzamel_bevindingen
from auditfile.integrity import NIET_MOGELIJK, WAARSCHUWING
from auditfile.openstaand import (
    BASIS_FACTUURDATUM,
    BASIS_ONBEKEND,
    BASIS_VERVALDATUM,
    KLASSE_ONBEKEND,
    NIET_VERVALLEN,
    POST_COLUMNS,
    bepaal_peildatum,
    build_openstaand_aansluiting,
    build_openstaande_posten,
    build_ouderdom,
    heeft_openstaande_posten,
)
from auditfile.parsing import parse_auditfile

REKENINGEN = [
    Account("1100", "Bank", "B", leadReference="BLimBan"),
    Account("1300", "Debiteuren", "B", leadReference="BVorDeb"),
    Account("1600", "Crediteuren", "B", leadReference="BSchCre"),
    Account("8000", "Omzet", "P", leadReference="WOmzNeh"),
]

# Regel 2 van de beginbalans is de debiteurenrekening; daarnaar verwijzen de
# beginposten met hun ``obLineNr``.
BEGINBALANS = [
    OpeningLine("1100", "5000.00", "D"),
    OpeningLine("1300", "1210.00", "D"),
]
DEBITEUREN_OB_REGEL = "2"

# Het boekjaar van de fixture loopt tot en met 31 december 2025; dat is dus de
# peildatum waarop de ouderdom wordt gemeten.
PEILDATUM = pd.Timestamp("2025-12-31")


def _verkoopboek() -> list[Journal]:
    """Een factuur op de debiteuren en een ontvangst op de bank."""
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
                        Line("1300", "605.00", "C", "Afboeking", custSupID="D001", invRef="F001"),
                    ],
                ),
            ],
        )
    ]


def _bestand(*, ob_subledgers=None, subledgers=None, relations=None, **spec_overrides):
    spec = AuditfileSpec(
        versie="3.2",
        accounts=list(REKENINGEN),
        relations=[Relation("D001", "Afnemer Alfa BV", "C")] if relations is None else relations,
        opening_lines=list(BEGINBALANS),
        journals=_verkoopboek(),
        ob_subledgers=ob_subledgers or [],
        subledgers=subledgers or [],
        **spec_overrides,
    )
    return parse_auditfile("synthetisch_3_2.xaf", build_xaf(spec))


def _beginregel(**overrides) -> ObSubledgerLine:
    velden = {
        "obLineNr": DEBITEUREN_OB_REGEL,
        "amnt": "1210.00",
        "amntTp": "D",
        "custSupID": "D001",
        "invRef": "F000",
        "invDt": "2025-09-01",
        "invDueDt": "2025-10-01",
        "matchKeyID": "AFL-1",
    }
    velden.update(overrides)
    return ObSubledgerLine(**velden)


def _mutatieregel(**overrides) -> SbLine:
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
    return SbLine(**velden)


def _demo_32():
    """Het synthetische 3.2-bestand met een gevulde subadministratie."""
    spec = vul_subadministratie(verschuif_boekjaar(eenvoudige_spec("3.2"), "2025"))
    return parse_auditfile("demo_3_2.xaf", build_xaf(spec))


# --- Wat het bestand toelaat ------------------------------------------------


def test_zonder_subadministratie_blijft_alles_leeg(af_40):
    """XAF 4.0 kent de subadministratie niet; dan is er niets te tonen.

    Niet een foutmelding en niet een lijst van nul euro, maar lege tabellen met
    de juiste kolommen. Een nul zou als uitkomst worden gelezen.
    """
    assert not heeft_openstaande_posten(af_40)
    assert build_openstaande_posten(af_40).empty
    assert list(build_openstaande_posten(af_40).columns) == POST_COLUMNS
    assert build_ouderdom(af_40).empty
    assert build_openstaand_aansluiting(af_40).empty


def test_peildatum_is_de_einddatum_van_het_boekjaar():
    """De vraag is hoe de post er op de balansdatum bij stond, niet vandaag."""
    af = _bestand(ob_subledgers=[ObSubledger([_beginregel()])])
    datum, herkomst = bepaal_peildatum(af)
    assert datum == PEILDATUM
    assert herkomst == "einddatum van het boekjaar"


def test_peildatum_valt_terug_op_de_laatste_datum_in_het_bestand():
    """Zonder einddatum is de laatste datum in de subadministratie het enige dat er is.

    Dat is zwakker, want de peildatum hangt dan van de gegevens zelf af. Daarom
    komt de herkomst mee terug in plaats van stil te worden gebruikt.
    """
    af = _bestand(
        end_date="",
        ob_subledgers=[ObSubledger([_beginregel(invDueDt="2025-10-01")])],
    )
    datum, herkomst = bepaal_peildatum(af)
    assert datum == pd.Timestamp("2025-10-01")
    assert herkomst == "laatste datum in de subadministratie"


# --- Van regels naar posten -------------------------------------------------


def test_het_afletterkenmerk_bindt_de_regels_van_een_post():
    """Beginstand en mutatie met hetzelfde kenmerk zijn één post.

    Beide blokken tellen mee, want de stand van een post is de beginstand plus
    haar verloop. Vallen ze uiteen, dan staat een betaalde factuur nog open.
    """
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(amnt="605.00", matchKeyID="AFL-9")])],
        subledgers=[
            Subledger([_mutatieregel(amnt="605.00", amntTp="C", matchKeyID="AFL-9")])
        ],
    )
    alle = build_openstaande_posten(af, alleen_open=False)
    assert len(alle) == 1
    assert alle.iloc[0]["sleutel"] == "AFL-9"
    assert alle.iloc[0]["sleutelsoort"] == "afletterkenmerk"
    assert alle.iloc[0]["aantal_regels"] == 2
    assert alle.iloc[0]["openstaand"] == pytest.approx(0.0)


def test_een_afgeletterde_post_staat_niet_in_de_openstaande_lijst():
    """Wat is afgewikkeld staat niet meer open, maar is wel op te vragen."""
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(amnt="605.00", matchKeyID="AFL-9")])],
        subledgers=[
            Subledger([_mutatieregel(amnt="605.00", amntTp="C", matchKeyID="AFL-9")])
        ],
    )
    assert build_openstaande_posten(af).empty
    assert len(build_openstaande_posten(af, alleen_open=False)) == 1


def test_zonder_afletterkenmerk_groepeert_de_factuurreferentie():
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(matchKeyID="", invRef="F123")])],
        subledgers=[
            Subledger(
                [_mutatieregel(matchKeyID="", invRef="F123", amnt="10.00", amntTp="D")]
            )
        ],
    )
    posten = build_openstaande_posten(af)
    assert len(posten) == 1
    assert posten.iloc[0]["sleutel"] == "F123"
    assert posten.iloc[0]["sleutelsoort"] == "factuurreferentie"
    assert posten.iloc[0]["openstaand"] == pytest.approx(1220.0)


def test_zonder_kenmerk_en_referentie_staat_elke_regel_op_zichzelf():
    """Twee regels zonder enige sleutel horen niet zomaar bij elkaar.

    Ze samenvoegen zou een openstaand bedrag salderen dat het bestand niet als
    één post aanwijst.
    """
    af = _bestand(
        ob_subledgers=[
            ObSubledger(
                [
                    _beginregel(matchKeyID="", invRef="", amnt="100.00"),
                    _beginregel(matchKeyID="", invRef="", amnt="200.00"),
                ]
            )
        ]
    )
    posten = build_openstaande_posten(af)
    assert len(posten) == 2
    assert set(posten["sleutelsoort"]) == {"losse regel"}


# --- Ouderdom ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("vervaldatum", "verwacht"),
    [
        ("2026-01-01", NIET_VERVALLEN),
        ("2025-12-31", "0-30 dagen"),
        ("2025-12-01", "0-30 dagen"),
        ("2025-11-30", "31-60 dagen"),
        ("2025-11-01", "31-60 dagen"),
        ("2025-10-31", "61-90 dagen"),
        ("2025-10-02", "61-90 dagen"),
        ("2025-10-01", "meer dan 90 dagen"),
    ],
)
def test_de_ouderdomsklasse_volgt_de_dagen_sinds_de_vervaldatum(vervaldatum, verwacht):
    af = _bestand(ob_subledgers=[ObSubledger([_beginregel(invDueDt=vervaldatum)])])
    post = build_openstaande_posten(af).iloc[0]
    assert post["basis"] == BASIS_VERVALDATUM
    assert post["dagen"] == (PEILDATUM - pd.Timestamp(vervaldatum)).days
    assert post["ouderdomsklasse"] == verwacht


def test_zonder_vervaldatum_telt_de_ouderdom_vanaf_de_factuurdatum():
    """XAF 3.2 mag ``invDueDt`` weglaten; dan is ``invDt`` het vertrekpunt.

    De basis staat in de tabel, want dagen te laat en dagen sinds de factuur
    betekenen niet hetzelfde.
    """
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(invDueDt="", invDt="2025-12-11")])]
    )
    post = build_openstaande_posten(af).iloc[0]
    assert post["basis"] == BASIS_FACTUURDATUM
    assert post["dagen"] == 20
    assert post["ouderdomsklasse"] == "0-30 dagen"


def test_een_post_zonder_datum_valt_niet_in_de_laagste_klasse():
    """Zonder datum is de ouderdom niet te bepalen, en dat hoort zichtbaar te zijn.

    Zulke posten stil in de klasse 0-30 zetten zou de ouderdomsopbouw gunstiger
    laten lijken dan het bestand toelaat; ze weglaten zou het openstaande totaal
    te laag maken.
    """
    af = _bestand(ob_subledgers=[ObSubledger([_beginregel(invDueDt="", invDt="")])])
    post = build_openstaande_posten(af).iloc[0]
    assert post["basis"] == BASIS_ONBEKEND
    assert pd.isna(post["dagen"])
    assert post["ouderdomsklasse"] == KLASSE_ONBEKEND
    assert "niet te bepalen" in post["signaal"]

    ouderdom = build_ouderdom(af)
    assert ouderdom["bedrag_datum_onbekend"].sum() == pytest.approx(1210.0)
    assert ouderdom["openstaand"].sum() == pytest.approx(1210.0)


def test_de_ouderdomstabel_splitst_op_de_gebruikte_basis():
    """Dagen te laat en dagen sinds factuurdatum staan nooit in dezelfde rij."""
    af = _bestand(
        ob_subledgers=[
            ObSubledger(
                [
                    _beginregel(matchKeyID="MET", invDueDt="2025-06-30"),
                    _beginregel(matchKeyID="ZONDER", invDueDt="", invDt="2025-06-30"),
                ]
            )
        ]
    )
    ouderdom = build_ouderdom(af)
    assert len(ouderdom) == 2
    assert set(ouderdom["basis"]) == {BASIS_VERVALDATUM, BASIS_FACTUURDATUM}


# --- Rekening, soort en aansluiting -----------------------------------------


def test_een_post_over_twee_rekeningen_krijgt_geen_rekening():
    """Liever geen rekening dan de verkeerde.

    De ene regel wijst naar de debiteuren, de andere naar de bank. Er dan een
    kiezen zou de post aansluiten op een rekening die er niets mee te maken heeft.
    """
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(matchKeyID="AFL-X")])],
        subledgers=[
            Subledger([_mutatieregel(trNr="V002", trLineNr="1", matchKeyID="AFL-X")])
        ],
    )
    post = build_openstaande_posten(af).iloc[0]
    assert post["rekening"] == ""
    assert post["koppeling"] == "meerdere rekeningen"
    assert "Niet aan een grootboekrekening gekoppeld" in post["signaal"]


def test_de_soort_komt_van_de_rekening_en_valt_terug_op_de_relatie():
    """De grootboekrekening gaat voor, want die deelt de post in zoals het grootboek.

    Lost de verwijzing niet op, dan is ``custSupTp`` de terugval en staat dat in
    ``soort_bron``, zodat zichtbaar blijft waarop de indeling rust.
    """
    via_rekening = _bestand(ob_subledgers=[ObSubledger([_beginregel()])])
    post = build_openstaande_posten(via_rekening).iloc[0]
    assert (post["soort"], post["soort_bron"]) == ("debiteur", "grootboekrekening")

    via_relatie = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(obLineNr="99")])]
    )
    post = build_openstaande_posten(via_relatie).iloc[0]
    assert (post["soort"], post["soort_bron"]) == ("debiteur", "custSupTp")


def test_zonder_rekening_en_zonder_relatiecode_valt_de_soort_terug_op_de_factuur():
    af = _bestand(
        relations=[Relation("D001", "Afnemer Alfa BV", "")],
        ob_subledgers=[ObSubledger([_beginregel(obLineNr="99", invPurSalTp="S")])],
    )
    post = build_openstaande_posten(af).iloc[0]
    assert (post["soort"], post["soort_bron"]) == ("debiteur", "invPurSalTp")


def test_een_post_zonder_enige_indeling_krijgt_een_eigen_aansluitregel():
    """Niet raden naar welke kant hij hoort, maar apart tellen.

    Zou zo'n post bij de debiteuren worden opgeteld, dan kon de aansluiting
    kloppend lijken op een indeling die het bestand nergens geeft.
    """
    af = _bestand(
        relations=[Relation("D001", "Afnemer Alfa BV", "")],
        ob_subledgers=[
            ObSubledger([_beginregel(obLineNr="99", invPurSalTp="", custSupID="")])
        ],
    )
    post = build_openstaande_posten(af).iloc[0]
    assert post["soort"] == ""

    aansluiting = build_openstaand_aansluiting(af)
    niet_ingedeeld = aansluiting[aansluiting["soort"] == "niet ingedeeld"]
    assert len(niet_ingedeeld) == 1
    assert niet_ingedeeld.iloc[0]["aantal_posten"] == 1
    assert niet_ingedeeld.iloc[0]["signaal"] == "niet mogelijk"


def test_een_debiteur_met_een_creditstand_geeft_een_signaal():
    af = _bestand(
        ob_subledgers=[ObSubledger([_beginregel(amnt="500.00", amntTp="C")])]
    )
    post = build_openstaande_posten(af).iloc[0]
    assert post["openstaand"] == pytest.approx(-500.0)
    assert "creditstand" in post["signaal"]


def test_de_openstaande_posten_sluiten_aan_op_het_grootboek():
    """Op het synthetische bestand telt de lijst op tot het saldo van de rekening.

    Dat is de controle die in de samenstelpraktijk als eerste komt. Loopt zij
    hier uiteen, dan zit er een fout in de groepering of in het teken en niet in
    de administratie.
    """
    af = _demo_32()
    aansluiting = build_openstaand_aansluiting(af)
    assert set(aansluiting["soort"]) == {"debiteur", "crediteur"}
    for _, rij in aansluiting.iterrows():
        assert rij["signaal"] == ""
        assert rij["verschil"] == pytest.approx(0.0, abs=0.005)


def test_de_ouderdomsopbouw_telt_op_tot_het_openstaande_totaal():
    """De klassen samen zijn het totaal; er verdwijnt geen post tussenuit."""
    af = _demo_32()
    ouderdom = build_ouderdom(af)
    klassen = [kolom for kolom in ouderdom.columns if kolom.startswith("bedrag_")]
    assert ouderdom[klassen].sum(axis=1).sum() == pytest.approx(
        ouderdom["openstaand"].sum()
    )
    assert ouderdom["aantal_posten"].sum() == len(build_openstaande_posten(af))


# --- Bevindingen ------------------------------------------------------------


def _categorie(af, categorie="Openstaande posten"):
    bevindingen = verzamel_bevindingen(af)
    return bevindingen[bevindingen["categorie"] == categorie]


def test_zonder_subadministratie_zijn_er_geen_bevindingen_over_openstaande_posten(af_40):
    """Dat de analyse niet kan, staat al bij de bestandscontrole.

    Hem hier nog eens als bevinding opvoeren zou dezelfde beperking twee keer in
    het reviewmemorandum zetten.
    """
    assert _categorie(af_40).empty


def test_oude_posten_komen_als_bevinding_in_de_lijst():
    """Zonder deze bevinding ontbreekt de ouderdom in het reviewmemorandum."""
    bevindingen = _categorie(_demo_32())
    ouder_dan_90 = bevindingen[bevindingen["onderwerp"].str.contains("ouder dan 90 dagen")]
    assert not ouder_dan_90.empty
    assert (ouder_dan_90["ernst"] == WAARSCHUWING).all()
    assert (ouder_dan_90["bedrag"].abs() > 0).all()
    assert (ouder_dan_90["pagina"] == "Relaties").all()


def test_een_post_zonder_datum_wordt_gemeld_als_niet_mogelijk():
    af = _bestand(ob_subledgers=[ObSubledger([_beginregel(invDueDt="", invDt="")])])
    bevindingen = _categorie(af)
    niet_mogelijk = bevindingen[bevindingen["ernst"] == NIET_MOGELIJK]
    assert "Ouderdom van openstaande posten niet te bepalen" in set(
        niet_mogelijk["onderwerp"]
    )


def test_een_verschil_met_het_grootboek_wordt_een_waarschuwing():
    """De subadministratie telt op tot 500 terwijl de rekening op 1210 sluit."""
    af = _bestand(ob_subledgers=[ObSubledger([_beginregel(amnt="500.00")])])
    bevindingen = _categorie(af)
    verschil = bevindingen[bevindingen["onderwerp"].str.contains("sluiten niet aan")]
    assert len(verschil) == 1
    assert verschil.iloc[0]["ernst"] == WAARSCHUWING
    assert verschil.iloc[0]["bedrag"] == pytest.approx(710.0)
