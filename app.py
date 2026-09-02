"""Auditfile Analyzer — Streamlit-app.

Dit bestand bevat uitsluitend de interface. Alle inlees- en analyselogica staat
in het pakket ``auditfile``, zodat die zonder Streamlit te testen is.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from auditfile import controls, vat
from auditfile.demo import build_xaf, eenvoudige_spec
from auditfile.comparison import (
    build_opvallende_verschillen,
    build_rubriek_vergelijking,
    compare_saldi,
)
from auditfile.excel import build_excel_export, exportnaam
from auditfile.formatting import euro, euro_kort, procent, toon_tabel
from auditfile.integrity import IN_ORDE, KRITIEK, WAARSCHUWING, controleer_auditfile, samenvatting
from auditfile.model import Auditfile
from auditfile.parsing import parse_auditfile
from auditfile.settings import (
    BTW_AANGIFTE_PATH,
    BTW_MAPPING_PATH,
    LOCAL_DATA_DIR,
    load_declared_vat,
    load_vat_deduction,
    load_vat_mapping,
    save_declared_vat,
    save_vat_deduction,
    save_vat_mapping,
)
from auditfile.vat_rubrics import (
    AFTREKBAAR_IN_5B,
    ONBEKEND,
    RUBRIEK_CODES,
    RUBRIEKEN,
    keuzelijst,
    rubriek,
)

APP_VERSIE = "3.0"

PAGINAS = [
    "Overzicht",
    "Bestandscontrole",
    "Jaarvergelijking",
    "Btw",
    "Analytische controles",
    "Relaties",
    "Fiscale signalen",
    "Grootboekkaarten",
    "Export",
]


@st.cache_data(show_spinner=False)
def bouw_demobestand(versie: str, boekjaar: str) -> bytes:
    """Een volledig verzonnen auditfile, om de tool te tonen zonder klantdata."""
    spec = eenvoudige_spec(versie)
    spec.fiscal_year = boekjaar
    spec.start_date = f"{boekjaar}-01-01"
    spec.end_date = f"{boekjaar}-12-31"
    for journaal in spec.journals:
        for transactie in journaal.transactions:
            transactie.trDt = f"{boekjaar}{transactie.trDt[4:]}"
            for regel in transactie.lines:
                regel.effDate = f"{boekjaar}{regel.effDate[4:]}"
    return build_xaf(spec)


@st.cache_data(show_spinner="Auditfile inlezen…")
def lees_auditfile(bestandsnaam: str, inhoud: bytes) -> Auditfile:
    return parse_auditfile(bestandsnaam, inhoud)


@st.cache_data(show_spinner=False)
def maak_vergelijking(_vorig: Auditfile, _huidig: Auditfile, sleutel: str) -> pd.DataFrame:
    """Vergelijk twee auditfiles; ``sleutel`` bepaalt de cache.

    Streamlit slaat argumenten met een underscore over bij het berekenen van de
    cachesleutel, want een ``Auditfile`` is niet te hashen. De sleutel moet de
    inhoud van beide bestanden dus zelf vastleggen. Met de bestandsnaam alleen
    zou een tweede dossier met gelijknamige bestanden de vergelijking van het
    eerste terugkrijgen; daarom de vingerafdruk van de inhoud.
    """
    del sleutel
    return compare_saldi(_vorig, _huidig)


def vergelijkingssleutel(vorig: Auditfile, huidig: Auditfile) -> str:
    """Cachesleutel voor de vergelijking van twee auditfiles."""
    return f"{vorig.vingerafdruk}|{huidig.vingerafdruk}"


def kop(titel: str, uitleg: str = "") -> None:
    st.subheader(titel)
    if uitleg:
        st.caption(uitleg)


def kerncijfer(kolom, label: str, waarde: str, hulp: str = "") -> None:
    kolom.metric(label, waarde, help=hulp or None)


# --- Bestanden inlezen ------------------------------------------------------


def haal_bestanden_op() -> tuple[tuple[str, bytes], tuple[str, bytes]] | None:
    """Laat de gebruiker twee auditfiles kiezen, of gebruik demo- of testdata."""
    bron = st.sidebar.radio(
        "Gegevensbron",
        ["Eigen bestanden", "Demo (synthetisch)", "Testmap"],
        help=(
            "Demo gebruikt volledig verzonnen gegevens en is bedoeld om de tool te "
            "bekijken of te tonen zonder klantbestand."
        ),
    )

    if bron == "Demo (synthetisch)":
        st.info(
            "Demomodus: de getoonde cijfers zijn verzonnen en komen uit "
            "`auditfile/demo.py`. Er wordt geen klantbestand gelezen."
        )
        return (
            ("demo_vorig_jaar.xaf", bouw_demobestand("3.2", "2024")),
            ("demo_huidig_jaar.xaf", bouw_demobestand("4.0", "2025")),
        )

    if bron == "Testmap":
        vorig_pad = Path("testfiles/vorig_jaar.xaf")
        huidig_pad = Path("testfiles/huidig_jaar.xaf")
        if not vorig_pad.exists() or not huidig_pad.exists():
            st.warning(
                "De testmap is gekozen, maar de bestanden ontbreken. Zet `vorig_jaar.xaf` "
                "en `huidig_jaar.xaf` in de map `testfiles/`, of kies de demomodus."
            )
            return None
        return (vorig_pad.name, vorig_pad.read_bytes()), (huidig_pad.name, huidig_pad.read_bytes())

    links, rechts = st.columns(2)
    with links:
        vorig = st.file_uploader("Auditfile vorig jaar", type=["xaf", "xml"], key="vorig")
    with rechts:
        huidig = st.file_uploader("Auditfile huidig jaar", type=["xaf", "xml"], key="huidig")

    if not vorig or not huidig:
        st.info("Laad beide auditfiles om de analyse te starten.")
        return None
    return (vorig.name, vorig.getvalue()), (huidig.name, huidig.getvalue())


# --- Pagina's ---------------------------------------------------------------


def pagina_overzicht(vorig: Auditfile, huidig: Auditfile, vergelijking: pd.DataFrame) -> None:
    bevindingen = controleer_auditfile(huidig)
    telling = samenvatting(bevindingen)

    if telling[KRITIEK]:
        st.error(
            f"{telling[KRITIEK]} kritieke bevinding(en) bij de bestandscontrole. "
            "Beoordeel die eerst; ze raken de betrouwbaarheid van alle cijfers hieronder."
        )
    elif telling[WAARSCHUWING]:
        st.warning(f"{telling[WAARSCHUWING]} aandachtspunt(en) bij de bestandscontrole.")
    else:
        st.success("Het auditfile is intern consistent.")

    kop("Kerncijfers huidig boekjaar")
    a, b, c, d = st.columns(4)
    kerncijfer(a, "Boekingsregels", f"{len(huidig.lines):n}".replace(",", "."))
    kerncijfer(b, "Grootboekrekeningen", f"{len(huidig.accounts):n}".replace(",", "."))
    kerncijfer(c, "Relaties", f"{len(huidig.relations):n}".replace(",", "."))
    kerncijfer(d, "Btw-codes gebruikt", f"{len(vat.build_vat_usage(huidig))}")

    gebruik = vat.pas_mapping_toe(
        vat.build_vat_usage(huidig), huidige_mapping(), huidige_aftrekbaarheid()
    )
    rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte())
    positie = vat.build_vat_position(rubrieken)

    kop(
        "Btw-positie volgens het auditfile",
        "Verschuldigde btw uit de rubrieken 1 tot en met 4, verminderd met de voorbelasting.",
    )
    toon_voorstelwaarschuwing(gebruik)
    a, b, c = st.columns(3)
    kerncijfer(a, "Verschuldigde btw", euro_kort(positie["af_te_dragen"]))
    kerncijfer(b, "Voorbelasting", euro_kort(positie["voorbelasting"]))
    kerncijfer(
        c,
        "Te betalen" if positie["netto"] >= 0 else "Terug te vragen",
        euro_kort(abs(positie["netto"])),
    )
    if abs(positie["niet_ingedeeld"]) > 0.005:
        st.warning(
            f"{euro(positie['niet_ingedeeld'])} aan btw hoort bij codes zonder aangifterubriek "
            "en telt niet mee. Wijs die codes een rubriek toe op de pagina Btw."
        )

    kop(
        "Grootste verschillen ten opzichte van vorig jaar",
        f"Rekeningen die met meer dan {euro_kort(1000)} en meer dan 25% zijn gewijzigd, "
        "of die nieuw of vervallen zijn.",
    )
    opvallend = build_opvallende_verschillen(vergelijking)
    toon_tabel(
        opvallend.head(15),
        hoogte=400,
        kleur_op="status",
        verberg=("beginsaldo_vorig", "mutatie_vorig", "beginsaldo_huidig", "mutatie_huidig", "accTp"),
        leegmelding="Geen rekeningen die aan beide drempels voldoen.",
    )

    kop("Signalen in één oogopslag")
    signalen = pd.concat(
        [
            vat.build_vat_anomalies(huidig, gebruik).assign(soort="Btw"),
            controls.build_ongebruikelijke_boekingen(huidig).assign(soort="Boekingen"),
        ],
        ignore_index=True,
    )
    if signalen.empty:
        st.caption("Geen signalen gevonden.")
    else:
        toon_tabel(
            signalen[["soort", "signaal", "aantal_regels", "bedrag", "toelichting"]],
            hoogte=320,
        )


def pagina_bestandscontrole(vorig: Auditfile, huidig: Auditfile) -> None:
    kop(
        "Is dit auditfile intern consistent?",
        "Het bestand geeft zelf controletotalen op. Wijkt de inhoud daarvan af, dan "
        "staan alle conclusies uit dit bestand op losse schroeven.",
    )

    for auditfile, aanduiding in ((huidig, "Huidig jaar"), (vorig, "Vorig jaar")):
        bevindingen = controleer_auditfile(auditfile)
        telling = samenvatting(bevindingen)
        titel = (
            f"{aanduiding} — boekjaar {auditfile.boekjaar} (XAF {auditfile.xaf_versie}) — "
            f"{telling[KRITIEK]} kritiek, {telling[WAARSCHUWING]} aandachtspunt, {telling[IN_ORDE]} in orde"
        )
        with st.expander(titel, expanded=bool(telling[KRITIEK])):
            toon_tabel(bevindingen, kleur_op="ernst", hoogte=460)

    if vorig.xaf_versie != huidig.xaf_versie:
        st.info(
            f"De bestanden hebben verschillende XAF-versies ({vorig.xaf_versie} en "
            f"{huidig.xaf_versie}). Dat mag, maar let op: een oudere versie kan velden "
            "missen, zoals de RGS-code."
        )

    kop("Bedrijfsgegevens")
    links, rechts = st.columns(2)
    with links:
        st.caption("Huidig jaar")
        toon_tabel(huidig.company_info_frame())
    with rechts:
        st.caption("Vorig jaar")
        toon_tabel(vorig.company_info_frame())


def pagina_jaarvergelijking(vorig: Auditfile, huidig: Auditfile, vergelijking: pd.DataFrame) -> None:
    kop(
        "Per RGS-rubriek",
        "De hoofdlijn eerst: waar is het jaar veranderd?",
    )
    toon_tabel(build_rubriek_vergelijking(vergelijking), kleur_op="signaal")

    kop("Per grootboekrekening")
    filters = st.columns([2, 2, 3])
    with filters[0]:
        status = st.multiselect(
            "Status", ["bestaand", "nieuw", "vervallen"], default=["bestaand", "nieuw", "vervallen"]
        )
    with filters[1]:
        soort = st.selectbox("Rekeningsoort", ["Alle", "Balans", "Resultaat"])
    with filters[2]:
        drempel = st.number_input(
            "Toon vanaf een verschil van", min_value=0, value=0, step=500, format="%d"
        )

    selectie = vergelijking[vergelijking["status"].isin(status)]
    if soort == "Balans":
        selectie = selectie[selectie["accTp"].str.upper() == "B"]
    elif soort == "Resultaat":
        selectie = selectie[selectie["accTp"].str.upper() == "P"]
    if drempel:
        selectie = selectie[selectie["verschil_bedrag"].abs() >= drempel]

    st.caption(f"{len(selectie)} van de {len(vergelijking)} rekeningen.")
    toon_tabel(selectie, hoogte=560, kleur_op="status")


# --- Btw --------------------------------------------------------------------


def toon_voorstelwaarschuwing(gebruik: pd.DataFrame, verwijs: bool = True) -> None:
    """Meld het wanneer de btw-positie nog op voorstellen van de tool rust.

    De tool rekent met haar eigen voorstel zolang de gebruiker niets heeft
    vastgelegd, anders zou er geen enkel cijfer te zien zijn. Dat mag alleen als
    er ook staat dat het een voorstel is: een voorstel is geen beoordeling.
    """
    status = vat.voorstelstatus(gebruik)
    if not status["voorstellen"]:
        return
    bericht = (
        f"{status['voorstellen']} van de {status['codes']} btw-codes staan nog op een "
        f"voorstel van de tool, samen {euro(status['btw_op_voorstel'])} aan btw. De "
        "uitkomst is daarmee een rekenvoorbeeld en geen beoordeelde btw-positie."
    )
    if verwijs:
        bericht += " Beoordeel de indeling op de pagina Btw en leg die vast."
    st.warning(bericht)


def huidige_mapping() -> dict[str, str]:
    return st.session_state.get("btw_mapping", {})


def huidige_aangifte() -> dict[str, float]:
    return st.session_state.get("btw_aangifte", {})


def huidige_aftrekbaarheid() -> dict[str, float]:
    return st.session_state.get("btw_aftrekbaarheid", {})


def pagina_btw(huidig: Auditfile) -> None:
    gebruik_ruw = vat.build_vat_usage(huidig)
    if gebruik_ruw.empty:
        st.warning("Dit auditfile bevat geen boekingsregels met een btw-code.")
        return

    tabs = st.tabs(
        ["Codes en rubrieken", "Aangifte", "Rondrekening", "Signalen", "Boekingen per code"]
    )

    with tabs[0]:
        kop(
            "Koppel elke btw-code aan een aangifterubriek",
            "Een auditfile bevat geen aangifte. De tool doet een voorstel op grond van de "
            "omschrijving, het tarief en de debet/creditzijde, en zegt erbij waarop dat "
            "voorstel berust. Pas de rubriek aan waar het voorstel niet klopt en leg de "
            "indeling daarna vast; tot dat moment blijft het een voorstel van de tool.",
        )

        opgeslagen = huidige_mapping()
        opgeslagen_aftrek = huidige_aftrekbaarheid()
        bewerkbaar = vat.pas_mapping_toe(gebruik_ruw, opgeslagen, opgeslagen_aftrek)[
            [
                "btw_code",
                "omschrijving",
                "aantal_regels",
                "percentages",
                "grondslag_grootboek",
                "btw_grootboek",
                "rubriek",
                "rubriek_bron",
                "zekerheid",
                "reden",
            ]
        ]

        bewerkt = st.data_editor(
            bewerkbaar,
            hide_index=True,
            width="stretch",
            disabled=[
                "btw_code",
                "omschrijving",
                "aantal_regels",
                "percentages",
                "grondslag_grootboek",
                "btw_grootboek",
                "rubriek_bron",
                "zekerheid",
                "reden",
            ],
            column_config={
                "btw_code": st.column_config.TextColumn("Btw-code", width="small"),
                "omschrijving": st.column_config.TextColumn("Omschrijving in het bestand"),
                "aantal_regels": st.column_config.NumberColumn("Regels", format="plain"),
                "percentages": st.column_config.TextColumn("Tarieven", width="small"),
                "grondslag_grootboek": st.column_config.NumberColumn("Grondslag", format="euro"),
                "btw_grootboek": st.column_config.NumberColumn("Btw", format="euro"),
                "rubriek": st.column_config.SelectboxColumn(
                    "Aangifterubriek", options=keuzelijst(), required=True, width="small"
                ),
                "rubriek_bron": st.column_config.TextColumn(
                    "Herkomst",
                    width="small",
                    help=(
                        "voorstel: van de tool, nog niet beoordeeld. geaccepteerd: u hebt "
                        "het voorstel overgenomen. aangepast: u hebt een andere rubriek "
                        "gekozen."
                    ),
                ),
                "zekerheid": st.column_config.TextColumn("Zekerheid", width="small"),
                "reden": st.column_config.TextColumn("Waarop het voorstel berust", width="large"),
            },
            key="btw_mapping_editor",
        )

        # De indeling wordt pas bewaard als de gebruiker daarvoor kiest. Zou het
        # openen van deze pagina de zichtbare voorstellen al vastleggen, dan
        # gingen ze daarna voor beoordeelde keuzes door.
        nieuwe_mapping = {
            str(code): str(gekozen)
            for code, gekozen in zip(bewerkt["btw_code"], bewerkt["rubriek"])
        }
        # Het aftrekbare aandeel heeft alleen betekenis bij de rubrieken waarin de
        # ondernemer de btw zelf verschuldigd wordt. Een eigen tabel voor die
        # codes is duidelijker dan een kolom die bij de meeste rijen leeg hoort
        # te blijven, en houdt de fiscale uitleg bij de invoer.
        verlegde_codes = [
            str(code)
            for code, gekozen in zip(bewerkt["btw_code"], bewerkt["rubriek"])
            if str(gekozen) in AFTREKBAAR_IN_5B
        ]
        nieuwe_aftrek = {code: opgeslagen_aftrek.get(code, 100.0) for code in verlegde_codes}

        if verlegde_codes:
            kop(
                "Hoeveel van die btw is aftrekbaar?",
                "Bij verlegging, invoer en intracommunautaire verwerving wordt de "
                "onderneming de btw zelf verschuldigd en is diezelfde btw aftrekbaar in "
                "rubriek 5b. Art. 15 lid 1 Wet OB 1968 staat die aftrek toe voor zover de "
                "goederen en diensten worden gebruikt voor belaste handelingen. Bij "
                "uitsluitend belaste prestaties is dat 100% en komt het saldo op nihil; "
                "verlaag het aandeel bij vrijgesteld of gemengd gebruik.",
            )
            aftrek_frame = bewerkt[bewerkt["btw_code"].astype(str).isin(verlegde_codes)][
                ["btw_code", "omschrijving", "rubriek", "btw_grootboek"]
            ].copy()
            aftrek_frame["aftrekbaar_pct"] = [
                nieuwe_aftrek[str(code)] for code in aftrek_frame["btw_code"]
            ]
            aftrek_bewerkt = st.data_editor(
                aftrek_frame,
                hide_index=True,
                width="stretch",
                disabled=["btw_code", "omschrijving", "rubriek", "btw_grootboek"],
                column_config={
                    "btw_code": st.column_config.TextColumn("Btw-code", width="small"),
                    "omschrijving": st.column_config.TextColumn("Omschrijving in het bestand"),
                    "rubriek": st.column_config.TextColumn("Rubriek", width="small"),
                    "btw_grootboek": st.column_config.NumberColumn("Btw", format="euro"),
                    "aftrekbaar_pct": st.column_config.NumberColumn(
                        "Aftrekbaar in 5b",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        format="%.0f%%",
                        required=True,
                    ),
                },
                key="btw_aftrek_editor",
            )
            nieuwe_aftrek = {
                str(code): float(aandeel)
                for code, aandeel in zip(
                    aftrek_bewerkt["btw_code"], aftrek_bewerkt["aftrekbaar_pct"]
                )
                if pd.notna(aandeel)
            }
        # Twee verschillende dingen die de knop rechtvaardigen, met elk hun eigen
        # melding: een keuze die van de getoonde indeling afwijkt, en een code
        # die nog op een voorstel staat. Ze op één hoop gooien zou na het wissen
        # "wijzigingen open" melden terwijl er niets is gewijzigd.
        getoond = {
            str(code): str(waarde)
            for code, waarde in zip(bewerkbaar["btw_code"], bewerkbaar["rubriek"])
        }
        afwijkend = [
            code
            for code, keuze in nieuwe_mapping.items()
            if getoond.get(code) != keuze
            or nieuwe_aftrek.get(code) != opgeslagen_aftrek.get(code, nieuwe_aftrek.get(code))
        ]
        op_voorstel = [code for code in nieuwe_mapping if code not in opgeslagen]

        vastleggen, wissen, melding = st.columns([1, 1, 3])
        if vastleggen.button(
            "Indeling vastleggen",
            type="primary",
            disabled=not (afwijkend or op_voorstel),
            help="Legt de rubriek per btw-code vast als uw keuze. Pas daarna telt die mee.",
        ):
            st.session_state["btw_mapping"] = nieuwe_mapping
            st.session_state["btw_aftrekbaarheid"] = nieuwe_aftrek
            if not (save_vat_mapping(nieuwe_mapping) and save_vat_deduction(nieuwe_aftrek)):
                st.warning(f"De koppeling kon niet worden bewaard in {BTW_MAPPING_PATH}.")
            st.rerun()

        if wissen.button(
            "Vastlegging wissen",
            disabled=not (opgeslagen or opgeslagen_aftrek),
            help="Verwijdert uw keuzes, zodat de tabel weer de voorstellen van de tool toont.",
        ):
            st.session_state["btw_mapping"] = {}
            st.session_state["btw_aftrekbaarheid"] = {}
            st.session_state.pop("btw_mapping_editor", None)
            st.session_state.pop("btw_aftrek_editor", None)
            if not (save_vat_mapping({}) and save_vat_deduction({})):
                st.warning(f"De koppeling kon niet worden gewist in {BTW_MAPPING_PATH}.")
            st.rerun()

        with melding:
            if afwijkend:
                st.info(
                    f"{len(afwijkend)} gewijzigde rubriek(en) zijn nog niet vastgelegd en "
                    "tellen dus nog niet mee."
                )
            elif op_voorstel:
                st.caption(
                    f"{len(op_voorstel)} van de {len(nieuwe_mapping)} btw-codes staan nog op "
                    "een voorstel van de tool. Leg de indeling vast zodra u die hebt beoordeeld."
                )
            else:
                st.caption(f"Alle {len(nieuwe_mapping)} btw-codes zijn beoordeeld en vastgelegd.")

        niet_ingedeeld = bewerkt[bewerkt["rubriek"] == ONBEKEND]
        if not niet_ingedeeld.empty:
            st.warning(
                f"{len(niet_ingedeeld)} btw-code(s) hebben nog geen rubriek en tellen niet mee "
                "in de aangiftevergelijking."
            )

        with st.expander("Wat houden de rubrieken in?"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Rubriek": item.code,
                            "Omschrijving": item.omschrijving,
                            "Btw-bedrag": "ja" if item.heeft_btw else "alleen omzet",
                            "In de eindtelling": item.zijde,
                            "Toelichting": item.toelichting,
                        }
                        for item in RUBRIEKEN
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            st.caption("Vindplaatsen staan in docs/btw-bronnen.md.")

    gebruik = vat.pas_mapping_toe(gebruik_ruw, huidige_mapping(), huidige_aftrekbaarheid())

    with tabs[1]:
        kop(
            "Vergelijk met de ingediende aangiften",
            "Vul per rubriek het totaal in van de aangiften over het boekjaar. Alle "
            "rubrieken van het aangifteformulier staan er, ook die niet in dit auditfile "
            "voorkomen: juist zo'n rubriek is een verschil om naar te kijken. Een leeg "
            "veld betekent niet ingevuld en is iets anders dan een aangifte van nul. De "
            "bedragen worden bewaard op de computer waar de app draait en komen niet in "
            "Git terecht.",
        )
        rubrieken_basis = vat.build_rubric_summary(gebruik)
        bedragen_per_rubriek = dict(
            zip(rubrieken_basis["rubriek"], rubrieken_basis["btw_volgens_xaf"])
        )
        invulbaar = [code for code in RUBRIEK_CODES if rubriek(code).heeft_btw]

        # Een formulier, geen veld dat zichzelf bewaart. Streamlit voert de code
        # van alle tabbladen uit bij elke herberekening, dus een veld dat zijn
        # eigen waarde wegschrijft doet dat ook zonder dat iemand dit tabblad
        # heeft geopend.
        opgeslagen_aangifte = huidige_aangifte()
        # De sleutel mag niet gelijk zijn aan de session-state-sleutel
        # "btw_aangifte": Streamlit staat niet toe dat een waarde onder de
        # sleutel van een widget zelf wordt gezet.
        with st.form("btw_aangifte_formulier"):
            ingevoerd: dict[str, float] = {}
            kolommen = st.columns(4)
            for index, code in enumerate(invulbaar):
                with kolommen[index % len(kolommen)]:
                    bestaand = opgeslagen_aangifte.get(code)
                    volgens_xaf = bedragen_per_rubriek.get(code)
                    if volgens_xaf is None:
                        herkomst = "Komt niet voor in dit auditfile."
                    else:
                        herkomst = f"Volgens dit auditfile {euro(volgens_xaf)}."
                    waarde = st.number_input(
                        f"Rubriek {code}",
                        value=float(bestaand) if bestaand is not None else None,
                        step=1.0,
                        format="%.2f",
                        placeholder="niet ingevuld",
                        help=f"{rubriek(code).omschrijving}. {herkomst}",
                        key=f"aangifte_{code}",
                    )
                    if waarde is not None:
                        ingevoerd[code] = float(waarde)
            bewaren = st.form_submit_button("Aangiftebedragen bewaren", type="primary")
        if bewaren:
            st.session_state["btw_aangifte"] = ingevoerd
            if not save_declared_vat(ingevoerd):
                st.warning(f"De aangiftebedragen konden niet worden bewaard in {BTW_AANGIFTE_PATH}.")
            st.rerun()

        rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte())
        kop("Aansluiting per rubriek")
        toon_voorstelwaarschuwing(gebruik, verwijs=False)
        toon_tabel(rubrieken, kleur_op="status")

        positie = vat.build_vat_position(rubrieken)
        a, b, c = st.columns(3)
        kerncijfer(a, "Verschuldigde btw (5a)", euro(positie["af_te_dragen"]))
        kerncijfer(b, "Voorbelasting (5b)", euro(positie["voorbelasting"]))
        kerncijfer(
            c,
            "Te betalen" if positie["netto"] >= 0 else "Terug te vragen",
            euro(abs(positie["netto"])),
        )

        verschillen = rubrieken[rubrieken["status"] == "Verschil"]
        if not verschillen.empty:
            totaal = verschillen["verschil"].sum()
            st.warning(
                f"{len(verschillen)} rubriek(en) sluiten niet aan; samen {euro(totaal)}. "
                "Beoordeel of een suppletie nodig is."
            )

    with tabs[2]:
        rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte())
        kop(
            "Verloop van de btw-rekeningen",
            "Twee onafhankelijke wegen naar hetzelfde bedrag: de btw-codes op de "
            "boekingsregels, en de mutaties op de rekeningen die de btw-codetabel als "
            "btw-rekening aanwijst.",
        )
        verloop = vat.build_vat_ledger_flow(huidig, rubrieken)
        if verloop.empty:
            st.caption(
                "De btw-codetabel wijst geen btw-grootboekrekeningen aan; een rondrekening "
                "is daardoor niet te maken."
            )
        else:
            toon_tabel(verloop)
            overig = verloop[verloop["post"] == "Overige mutaties"]
            if not overig.empty and abs(float(overig.iloc[0]["bedrag"])) > 0.005:
                st.info(
                    f"{euro(overig.iloc[0]['bedrag'])} aan mutaties volgt niet uit de "
                    "facturatie en niet uit betalingen. Daar zitten correcties en eventuele "
                    "suppleties in."
                )

        kop("Btw-grootboekrekeningen")
        toon_tabel(
            vat.build_ledger_reconciliation(huidig),
            leegmelding="De btw-codetabel wijst geen btw-rekeningen aan.",
        )

    with tabs[3]:
        kop(
            "Btw-signalen",
            "Elk signaal is iets om naar te kijken, geen vastgestelde fout.",
        )
        toon_tabel(
            vat.build_vat_anomalies(huidig, gebruik),
            hoogte=440,
            leegmelding="Geen btw-signalen gevonden.",
        )

    with tabs[4]:
        kop("Boekingen per btw-code")
        codes = list(gebruik["btw_code"])
        etiketten = {
            code: f"{code} — {omschrijving or 'zonder omschrijving'} ({rubriek_code})"
            for code, omschrijving, rubriek_code in zip(
                gebruik["btw_code"], gebruik["omschrijving"], gebruik["rubriek"]
            )
        }
        gekozen = st.selectbox(
            "Btw-code", codes, format_func=lambda code: etiketten.get(code, code)
        )
        regels = vat.build_vat_drilldown(huidig, gekozen)
        alleen_afwijkend = st.checkbox(
            "Alleen regels waar de btw afwijkt van tarief maal grondslag", value=False
        )
        if alleen_afwijkend:
            regels = regels[regels["afwijking"].abs() > vat.AFRONDINGSMARGE_EURO]
        st.caption(f"{len(regels)} boekingsregels.")
        toon_tabel(regels.head(1000), hoogte=520, verberg=("btw_code",))
        if len(regels) > 1000:
            st.caption("De eerste duizend regels worden getoond; de export bevat alle regels.")


# --- Overige pagina's -------------------------------------------------------


def pagina_controles(huidig: Auditfile) -> None:
    kop(
        "Periodieke lasten",
        "Komen vaste lasten in elke periode voor, en zijn de bedragen gelijkmatig?",
    )
    toon_tabel(
        controls.build_periodieke_controles(huidig),
        hoogte=440,
        kleur_op="conclusie",
        leegmelding="Geen periodieke lasten herkend.",
    )

    kop("Ongebruikelijke boekingen")
    toon_tabel(
        controls.build_ongebruikelijke_boekingen(huidig),
        leegmelding="Geen ongebruikelijke patronen gevonden.",
    )

    kop("Balansposten met een onverwacht saldo")
    toon_tabel(
        controls.build_balanspost_signalen(huidig),
        leegmelding="Alle balansposten staan aan de verwachte kant.",
    )

    links, rechts = st.columns(2)
    with links:
        kop("Omzet per periode")
        omzet = controls.build_omzet_per_periode(huidig)
        toon_tabel(omzet, kleur_op="signaal", leegmelding="Geen omzetrekeningen herkend.")
        if not omzet.empty:
            st.bar_chart(omzet.set_index("maand")["omzet"], height=220)
    with rechts:
        kop("Loonkosten per periode")
        loon = controls.build_personeelskosten_per_periode(huidig)
        toon_tabel(loon, kleur_op="signaal", leegmelding="Geen loonrekeningen herkend.")
        if not loon.empty:
            st.bar_chart(loon.set_index("maand")["loonkosten"], height=220)


def pagina_relaties(huidig: Auditfile) -> None:
    if huidig.relations.empty:
        st.info("Dit auditfile bevat geen debiteuren- en crediteurengegevens.")
        return

    kop("Concentratie", "Hoe afhankelijk is de onderneming van enkele relaties?")
    toon_tabel(controls.build_relatie_concentratie(huidig), kleur_op="signaal")

    links, rechts = st.columns(2)
    with links:
        kop("Grootste debiteuren")
        toon_tabel(
            controls.build_relatie_analyse(huidig, "debiteur"),
            hoogte=460,
            leegmelding="Geen debiteuren gevonden.",
        )
    with rechts:
        kop("Grootste crediteuren")
        toon_tabel(
            controls.build_relatie_analyse(huidig, "crediteur"),
            hoogte=460,
            leegmelding="Geen crediteuren gevonden.",
        )

    with st.expander("Alle relaties uit het auditfile"):
        toon_tabel(huidig.relations, hoogte=400)


def pagina_fiscale_signalen(huidig: Auditfile) -> None:
    kop(
        "Posten die om een fiscale beoordeling vragen",
        "De tool signaleert op grond van de rekeningomschrijving en trekt geen conclusie. "
        "Beoordeel elke post afzonderlijk.",
    )
    signalen = controls.build_fiscale_signalen(huidig)
    if signalen.empty:
        st.caption("Geen posten gevonden die om een fiscale beoordeling vragen.")
        return

    for onderwerp in signalen["onderwerp"].unique():
        deel = signalen[signalen["onderwerp"] == onderwerp]
        totaal = deel["bedrag"].sum()
        with st.expander(f"{onderwerp} — {euro(totaal)} over {len(deel)} rekening(en)"):
            st.caption(deel.iloc[0]["toelichting"])
            toon_tabel(deel[["rekening", "omschrijving", "aantal_regels", "bedrag"]])


def pagina_grootboekkaarten(huidig: Auditfile) -> None:
    saldo = huidig.saldo
    if saldo.empty:
        st.info("Geen grootboekrekeningen gevonden.")
        return

    etiketten = {
        rij["rekening"]: f"{rij['rekening']} — {rij['accDesc']} ({euro(rij['saldo'])})"
        for _, rij in saldo.iterrows()
    }
    gekozen = st.selectbox(
        "Grootboekrekening",
        list(saldo["rekening"]),
        format_func=lambda rekening: etiketten.get(rekening, rekening),
    )

    kaart = huidig.lines[huidig.lines["line_accID"] == gekozen].copy()
    if kaart.empty:
        st.info("Op deze rekening zijn geen boekingen gedaan in dit boekjaar.")
        return

    rij = saldo[saldo["rekening"] == gekozen].iloc[0]
    a, b, c, d = st.columns(4)
    kerncijfer(a, "Beginsaldo", euro(rij["beginsaldo"]))
    kerncijfer(b, "Mutatie boekjaar", euro(rij["mutaties_boekjaar"]))
    kerncijfer(c, "Eindsaldo", euro(rij["eindsaldo"]))
    kerncijfer(d, "Boekingsregels", f"{len(kaart)}")

    kaart = kaart.sort_values(["datum", "tx_nr", "line_nr"], na_position="last")
    kaart["loopsaldo"] = float(rij["beginsaldo"]) + kaart["bedrag"].cumsum()
    kolommen = [
        "datum",
        "periode",
        "tx_jrn_desc",
        "tx_nr",
        "line_desc",
        "line_docRef",
        "line_custSupID",
        "bedrag",
        "loopsaldo",
    ]
    toon_tabel(kaart[[k for k in kolommen if k in kaart.columns]], hoogte=520)


def pagina_export(vorig: Auditfile, huidig: Auditfile, vergelijking: pd.DataFrame) -> None:
    kop(
        "Excel-export",
        "Alle analyses in één werkboek, met Nederlandse getalnotatie en filters per tabblad.",
    )
    st.caption(
        "Het bestand bevat klantgegevens. Bewaar het in het dossier en niet in een "
        "map die door Git wordt gevolgd."
    )
    if st.button("Werkboek samenstellen", type="primary"):
        with st.spinner("Bezig met samenstellen…"):
            inhoud = build_excel_export(
                huidig,
                vorig,
                vergelijking,
                huidige_mapping(),
                huidige_aangifte(),
                huidige_aftrekbaarheid(),
            )
        st.download_button(
            "Download het werkboek",
            data=inhoud,
            file_name=exportnaam(huidig, vorig),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# --- Hoofdprogramma ---------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title=f"Auditfile Analyzer {APP_VERSIE}", layout="wide")

    logo = Path("logo.png")
    if logo.exists():
        st.sidebar.image(str(logo), width="stretch")
    st.sidebar.markdown("---")

    st.title("Auditfile Analyzer")
    st.caption(
        "Fiscaal-inhoudelijke analyse van twee XAF-auditfiles. Bij lokale uitvoering "
        "blijven de bestanden op deze computer; draait de app op een server, dan gaan "
        "de gekozen bestanden naar die server."
    )

    bestanden = haal_bestanden_op()
    if bestanden is None:
        st.stop()
    (naam_vorig, inhoud_vorig), (naam_huidig, inhoud_huidig) = bestanden

    try:
        vorig = lees_auditfile(naam_vorig, inhoud_vorig)
        huidig = lees_auditfile(naam_huidig, inhoud_huidig)
    except Exception as fout:
        # Bewust geen volledige traceback: die kan bestandspaden en klantgegevens
        # tonen op een scherm dat wordt gedeeld of vastgelegd.
        st.error(
            "Een van de bestanden kon niet worden gelezen. Controleer of het geldige "
            f"XAF-bestanden zijn. Melding: {type(fout).__name__}."
        )
        st.stop()

    if not huidig.boekjaar or not vorig.boekjaar:
        st.warning("Een van de bestanden vermeldt geen boekjaar; controleer de volgorde.")
    elif huidig.boekjaar < vorig.boekjaar:
        st.warning(
            f"Het bestand voor het huidige jaar heeft boekjaar {huidig.boekjaar} en dat voor "
            f"vorig jaar {vorig.boekjaar}. Zijn de bestanden verwisseld?"
        )

    if "btw_mapping" not in st.session_state:
        st.session_state["btw_mapping"] = load_vat_mapping()
    if "btw_aangifte" not in st.session_state:
        st.session_state["btw_aangifte"] = load_declared_vat()
    if "btw_aftrekbaarheid" not in st.session_state:
        st.session_state["btw_aftrekbaarheid"] = load_vat_deduction()

    st.sidebar.markdown(
        f"**{huidig.bedrijfsnaam or 'Onbekende onderneming'}**  \n"
        f"Boekjaar {huidig.boekjaar} tegenover {vorig.boekjaar}"
    )
    st.sidebar.markdown("---")
    pagina = st.sidebar.radio("Onderdeel", PAGINAS, label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"Versie {APP_VERSIE} · invoer wordt lokaal bewaard in `{LOCAL_DATA_DIR}`"
    )

    vergelijking = maak_vergelijking(vorig, huidig, vergelijkingssleutel(vorig, huidig))

    if pagina == "Overzicht":
        pagina_overzicht(vorig, huidig, vergelijking)
    elif pagina == "Bestandscontrole":
        pagina_bestandscontrole(vorig, huidig)
    elif pagina == "Jaarvergelijking":
        pagina_jaarvergelijking(vorig, huidig, vergelijking)
    elif pagina == "Btw":
        pagina_btw(huidig)
    elif pagina == "Analytische controles":
        pagina_controles(huidig)
    elif pagina == "Relaties":
        pagina_relaties(huidig)
    elif pagina == "Fiscale signalen":
        pagina_fiscale_signalen(huidig)
    elif pagina == "Grootboekkaarten":
        pagina_grootboekkaarten(huidig)
    elif pagina == "Export":
        pagina_export(vorig, huidig, vergelijking)


if __name__ == "__main__":
    main()
