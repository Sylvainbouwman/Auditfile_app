from datetime import date

import pandas as pd

from auditfile.aangifte import (
    EINDTOTAAL,
    SOORT_AANGIFTE,
    SOORT_ONBEKEND,
    SOORT_SUPPLETIE,
    SUPPLETIE_EERDER,
    SUPPLETIE_SALDO,
    build_overzicht,
    lees_aangifte,
    tel_op,
)
from auditfile.demo import DEMO_OMZETBELASTINGNUMMER, build_aangifte_xbrl


def kwartaal(nummer: int, jaar: int = 2025, **rest) -> bytes:
    grenzen = {
        1: ("01-01", "03-31"),
        2: ("04-01", "06-30"),
        3: ("07-01", "09-30"),
        4: ("10-01", "12-31"),
    }
    begin, eind = grenzen[nummer]
    rest.setdefault("grondslag", {"TaxedTurnoverSuppliesServicesGeneralTariff": 100_000})
    rest.setdefault("btw", {"ValueAddedTaxSuppliesServicesGeneralTariff": 21_000})
    return build_aangifte_xbrl(
        begindatum=f"{jaar}-{begin}", einddatum=f"{jaar}-{eind}", **rest
    )


def test_de_rubrieken_komen_uit_de_elementnamen():
    xbrl = build_aangifte_xbrl(
        begindatum="2025-01-01",
        einddatum="2025-03-31",
        grondslag={
            "TaxedTurnoverSuppliesServicesGeneralTariff": 100_000,
            "TaxedTurnoverSuppliesServicesReducedTariff": 20_000,
            "SuppliesToCountriesOutsideTheEC": 5_000,
            "SuppliesToCountriesWithinTheEC": 8_000,
        },
        btw={
            "ValueAddedTaxSuppliesServicesGeneralTariff": 21_000,
            "ValueAddedTaxSuppliesServicesReducedTariff": 1_800,
            "ValueAddedTaxOnInput": 4_500,
        },
    )
    stuk = lees_aangifte("Q1.xbrl", xbrl)

    assert stuk.btw == {"1a": 21_000.0, "1b": 1_800.0, "5b": 4_500.0}
    assert stuk.grondslag["1a"] == 100_000.0
    assert stuk.grondslag["1b"] == 20_000.0
    # De valkuil bij deze twee: het rubrieknummer zegt niets over binnen of
    # buiten de EU, de elementnaam wel.
    assert stuk.grondslag["3a"] == 5_000.0
    assert stuk.grondslag["3b"] == 8_000.0


def test_het_tijdvak_komt_uit_de_context():
    stuk = lees_aangifte("Q2.xbrl", kwartaal(2))

    assert stuk.begindatum == date(2025, 4, 1)
    assert stuk.einddatum == date(2025, 6, 30)
    assert stuk.tijdvak == "2025-04-01 t/m 2025-06-30"
    assert stuk.omzetbelastingnummer == DEMO_OMZETBELASTINGNUMMER


def test_een_aangifte_wordt_herkend_aan_het_schema():
    stuk = lees_aangifte("Q1.xbrl", kwartaal(1))

    assert stuk.soort == SOORT_AANGIFTE
    assert stuk.meldingen == ()


def test_een_suppletie_wordt_herkend_aan_het_schema():
    xbrl = build_aangifte_xbrl(
        begindatum="2025-01-01",
        einddatum="2025-12-31",
        schema="http://www.nltaxonomie.nl/nt16/bd/20220921/entrypoints/bd-rpt-ob-suppletie.xsd",
        btw={"ValueAddedTaxSuppliesServicesGeneralTariff": 22_000},
        totalen={
            "ValueAddedTaxAmountTotalOld": 21_000,
            "ValueAddedTaxToBePaidAdditionalToBePaidBack": 1_000,
        },
    )
    stuk = lees_aangifte("suppletie.xbrl", xbrl)

    assert stuk.soort == SOORT_SUPPLETIE
    assert stuk.totalen[SUPPLETIE_EERDER] == 21_000.0
    assert stuk.totalen[SUPPLETIE_SALDO] == 1_000.0


def test_zonder_schema_beslissen_de_aanwezige_velden():
    aangifte = lees_aangifte(
        "zonder_schema.xbrl",
        build_aangifte_xbrl(
            begindatum="2025-01-01",
            einddatum="2025-03-31",
            schema="",
            totalen={"ValueAddedTaxOwedToBePaidBack": 16_500},
        ),
    )
    suppletie = lees_aangifte(
        "zonder_schema2.xbrl",
        build_aangifte_xbrl(
            begindatum="2025-01-01",
            einddatum="2025-12-31",
            schema="",
            totalen={"ValueAddedTaxAmountTotalOld": 21_000},
        ),
    )

    assert aangifte.soort == SOORT_AANGIFTE
    assert aangifte.totalen[EINDTOTAAL] == 16_500.0
    assert suppletie.soort == SOORT_SUPPLETIE


def test_een_onbekend_berichttype_wordt_gemeld_maar_wel_gelezen():
    stuk = lees_aangifte(
        "onbekend.xbrl",
        build_aangifte_xbrl(
            begindatum="2025-01-01",
            einddatum="2025-03-31",
            schema="",
            btw={"ValueAddedTaxSuppliesServicesGeneralTariff": 21_000},
        ),
    )

    assert stuk.soort == SOORT_ONBEKEND
    assert stuk.btw == {"1a": 21_000.0}
    assert any("aangifte of een suppletie" in melding for melding in stuk.meldingen)


def test_een_onbekend_veld_wordt_gemeld_en_niet_meegeteld():
    stuk = lees_aangifte(
        "nieuw.xbrl",
        build_aangifte_xbrl(
            begindatum="2025-01-01",
            einddatum="2025-03-31",
            btw={"ValueAddedTaxSuppliesServicesGeneralTariff": 21_000},
            totalen={"ValueAddedTaxOnSomethingNew": 999},
        ),
    )

    assert stuk.niet_herkend == ("ValueAddedTaxOnSomethingNew",)
    assert stuk.btw == {"1a": 21_000.0}
    assert any("ValueAddedTaxOnSomethingNew" in melding for melding in stuk.meldingen)


def test_de_structuurelementen_van_xbrl_tellen_niet_als_onbekend_veld():
    stuk = lees_aangifte("Q1.xbrl", kwartaal(1))

    assert stuk.niet_herkend == ()


def test_een_onleesbaar_bestand_geeft_een_melding_en_geen_fout():
    stuk = lees_aangifte("kapot.xbrl", b"<xbrli:xbrl><niet gesloten")

    assert not stuk.gelezen
    assert any("geldige XML" in melding for melding in stuk.meldingen)


def test_een_bestand_zonder_aangiftebedragen_wordt_gemeld():
    stuk = lees_aangifte(
        "leeg.xbrl", build_aangifte_xbrl(begindatum="2025-01-01", einddatum="2025-03-31")
    )

    assert not stuk.gelezen
    assert any("geen bedragen" in melding for melding in stuk.meldingen)


def test_onleesbare_bekende_bedragen_worden_gemeld_en_niet_meegeteld():
    xbrl = build_aangifte_xbrl(
        begindatum="2025-01-01",
        einddatum="2025-03-31",
        grondslag={"TaxedTurnoverSuppliesServicesGeneralTariff": 100_000},
        btw={
            "ValueAddedTaxSuppliesServicesGeneralTariff": 21_000,
            "ValueAddedTaxOnInput": 4_500,
        },
    ).replace(b">100000<", b">NaN<").replace(b">21000<", b">onleesbaar<")

    stuk = lees_aangifte("onleesbaar.xbrl", xbrl)

    assert stuk.btw == {"5b": 4_500.0}
    assert stuk.grondslag == {}
    assert any(
        "TaxedTurnoverSuppliesServicesGeneralTariff" in melding
        and "ValueAddedTaxSuppliesServicesGeneralTariff" in melding
        and "niet zijn meegeteld" in melding
        for melding in stuk.meldingen
    )


def test_vier_kwartalen_worden_opgeteld_tot_het_boekjaar():
    stukken = [lees_aangifte(f"Q{n}.xbrl", kwartaal(n)) for n in (1, 2, 3, 4)]

    totaal = tel_op(stukken, boekjaar="2025", omzetbelastingnummer=DEMO_OMZETBELASTINGNUMMER)

    assert totaal.aantal == 4
    assert totaal.btw["1a"] == 84_000.0
    assert totaal.grondslag["1a"] == 400_000.0
    assert totaal.meldingen == ()


def test_een_ontbrekend_tijdvak_wordt_gemeld():
    stukken = [lees_aangifte(f"Q{n}.xbrl", kwartaal(n)) for n in (1, 2, 4)]

    totaal = tel_op(stukken, boekjaar="2025")

    assert totaal.aantal == 3
    assert any("gat" in melding for melding in totaal.meldingen)


def test_een_onvolledig_boekjaar_aan_begin_en_einde_wordt_gemeld():
    totaal = tel_op([lees_aangifte("Q2.xbrl", kwartaal(2))], boekjaar="2025")

    assert any("begin van boekjaar" in melding for melding in totaal.meldingen)
    assert any("einde van boekjaar" in melding for melding in totaal.meldingen)


def test_overlappende_tijdvakken_worden_gemeld():
    stukken = [
        lees_aangifte("Q1.xbrl", kwartaal(1)),
        lees_aangifte(
            "jaar.xbrl",
            build_aangifte_xbrl(begindatum="2025-01-01", einddatum="2025-12-31", btw={"ValueAddedTaxOnInput": 100}),
        ),
    ]

    totaal = tel_op(stukken, boekjaar="2025")

    assert any("overlappen" in melding for melding in totaal.meldingen)


def test_een_tijdvak_buiten_het_boekjaar_wordt_gemeld_maar_wel_meegeteld():
    stukken = [
        lees_aangifte("Q4-2024.xbrl", kwartaal(4, jaar=2024)),
        lees_aangifte("Q1.xbrl", kwartaal(1)),
    ]

    totaal = tel_op(stukken, boekjaar="2025")

    assert totaal.btw["1a"] == 42_000.0
    assert any("buiten boekjaar" in melding for melding in totaal.meldingen)


def test_een_afwijkend_omzetbelastingnummer_wordt_gemeld():
    stukken = [
        lees_aangifte("Q1.xbrl", kwartaal(1)),
        lees_aangifte("vreemd.xbrl", kwartaal(2, omzetbelastingnummer="NL999999999B01")),
    ]

    totaal = tel_op(stukken, boekjaar="2025", omzetbelastingnummer=DEMO_OMZETBELASTINGNUMMER)

    assert any("NL999999999B01" in melding for melding in totaal.meldingen)


def test_het_nummer_vergelijkt_zonder_spaties_en_hoofdletterverschil():
    stukken = [lees_aangifte("Q1.xbrl", kwartaal(1, omzetbelastingnummer="nl 000000000 b01"))]

    totaal = tel_op(stukken, boekjaar="2025", omzetbelastingnummer=DEMO_OMZETBELASTINGNUMMER)

    assert not any("wijkt af" in melding for melding in totaal.meldingen)


def test_een_suppletie_wordt_niet_bij_de_aangiften_opgeteld():
    stukken = [
        lees_aangifte("Q1.xbrl", kwartaal(1)),
        lees_aangifte(
            "suppletie.xbrl",
            build_aangifte_xbrl(
                begindatum="2025-01-01",
                einddatum="2025-12-31",
                schema="bd-rpt-ob-suppletie.xsd",
                btw={"ValueAddedTaxSuppliesServicesGeneralTariff": 99_000},
            ),
        ),
    ]

    aangiften = tel_op(stukken, boekjaar="2025")
    suppleties = tel_op(stukken, boekjaar="2025", soort=SOORT_SUPPLETIE)

    assert aangiften.btw["1a"] == 21_000.0
    assert suppleties.btw["1a"] == 99_000.0


def test_het_overzicht_toont_een_regel_per_bestand():
    stukken = [
        lees_aangifte(
            "Q1.xbrl",
            kwartaal(1, totalen={"ValueAddedTaxOwed": 21_000, "ValueAddedTaxOwedToBePaidBack": 16_500}),
        ),
        lees_aangifte("Q2.xbrl", kwartaal(2)),
    ]

    overzicht = build_overzicht(stukken)

    assert list(overzicht["bestand"]) == ["Q1.xbrl", "Q2.xbrl"]
    assert overzicht.loc[0, "verschuldigde_btw"] == 21_000.0
    assert overzicht.loc[0, "eindtotaal"] == 16_500.0
    # Als datum, niet als los object: anders toont de app het getal waar de
    # datum intern op neerkomt.
    assert pd.api.types.is_datetime64_any_dtype(overzicht["begindatum"])
    assert overzicht.loc[0, "begindatum"] == pd.Timestamp(2025, 1, 1)


def test_een_leeg_overzicht_houdt_zijn_kolommen():
    overzicht = build_overzicht([])

    assert list(overzicht.columns)[:3] == ["bestand", "soort", "begindatum"]
    assert overzicht.empty


def test_de_namespace_van_de_taxonomieversie_doet_niet_ter_zake():
    nieuw = build_aangifte_xbrl(
        begindatum="2025-01-01", einddatum="2025-03-31", btw={"ValueAddedTaxOnInput": 4_500}
    ).replace(
        b"http://www.nltaxonomie.nl/10.0/basis/bd/items/bd-omzetbelasting",
        b"http://www.nltaxonomie.nl/nt99/bd/20991231/dictionary/bd-omzetbelasting",
    )

    stuk = lees_aangifte("toekomst.xbrl", nieuw)

    assert stuk.btw == {"5b": 4_500.0}
