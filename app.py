"""Auditfile Analyzer — Streamlit-app.

Dit bestand bevat uitsluitend de interface. Alle inlees- en analyselogica staat
in het pakket ``auditfile``, zodat die zonder Streamlit te testen is.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from auditfile import controls, relatiesaldi, vat
from auditfile.demo import demopaar
from auditfile.capability import (
    NIVEAU_GEEN,
    NIVEAU_NAAM,
    NIVEAU_VERVALDATUM,
    build_bestandsprofiel,
    build_relatiedekking,
    openstaande_posten_niveau,
)
from auditfile.comparison import (
    build_jaarovergang,
    build_jaarovergang_verloop,
    build_opvallende_verschillen,
    build_rubriek_vergelijking,
    compare_saldi,
    controleer_bestandenpaar,
    jaarovergang_sluit_aan,
)
from auditfile.excel import build_excel_export, exportnaam
from auditfile.findings import (
    REVIEWSTATUSSEN,
    SIGNAAL,
    TE_BEOORDELEN,
    Materialiteit,
    grondslag_omzet,
    openstaande_bevindingen,
    pas_review_toe,
    samenvatting_per_ernst,
    verzamel_bevindingen,
)
from auditfile.formatting import euro, euro_kort, procent, toon_tabel
from auditfile.integrity import (
    IN_ORDE,
    KRITIEK,
    NIET_MOGELIJK,
    WAARSCHUWING,
    controleer_auditfile,
    samenvatting,
)
from auditfile.model import Auditfile
from auditfile.parsing import parse_auditfile
from auditfile.settings import (
    DOSSIER_DIR,
    DossierOpslag,
    bekende_dossiers,
    lees_oude_invoer,
    oude_invoer_aanwezig,
    verwijder_oude_invoer,
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
    "Bevindingen",
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
def bouw_demobestanden() -> tuple[bytes, bytes]:
    """Twee volledig verzonnen auditfiles die op elkaar aansluiten.

    Om de tool te kunnen tonen zonder klantdata, inclusief de jaarovergang: het
    tweede jaar begint met de eindbalans van het eerste.
    """
    return demopaar()


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
        vorig_bytes, huidig_bytes = bouw_demobestanden()
        return (
            ("demo_vorig_jaar.xaf", vorig_bytes),
            ("demo_huidig_jaar.xaf", huidig_bytes),
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


SIGNAALCATEGORIEEN: tuple[tuple[str, str], ...] = (
    ("Btw", "Btw"),
    ("Boekingen", "Analytische controles"),
    ("Periodieke lasten", "Analytische controles"),
    ("Balansposten", "Analytische controles"),
    ("Omzet per periode", "Analytische controles"),
    ("Loonkosten per periode", "Analytische controles"),
    ("Relaties", "Relaties"),
    ("Fiscaal", "Fiscale signalen"),
)


def tel_signalen(huidig: Auditfile, gebruik: pd.DataFrame) -> pd.DataFrame:
    """Hoeveel signalen elke categorie oplevert, en waar ze staan.

    Het overzicht toonde alleen de btw-signalen en de ongebruikelijke boekingen.
    Een leeg blok wekte daardoor de indruk dat er niets was, terwijl de
    periodieke, balans-, relatie- en fiscale signalen op andere pagina's stonden.
    Deze telling maakt zichtbaar wat er te beoordelen valt zonder alles op één
    pagina te dumpen.
    """
    periodiek = controls.build_periodieke_controles(huidig)
    balans = controls.build_balanspost_signalen(huidig)
    omzet = controls.build_omzet_per_periode(huidig)
    loon = controls.build_personeelskosten_per_periode(huidig)
    concentratie = controls.build_relatie_concentratie(huidig)

    aantallen = {
        "Btw": len(vat.build_vat_anomalies(huidig, gebruik)),
        "Boekingen": len(controls.build_ongebruikelijke_boekingen(huidig)),
        "Periodieke lasten": int((periodiek["conclusie"] != "Geen bijzonderheden").sum())
        if not periodiek.empty
        else 0,
        "Balansposten": len(balans),
        "Omzet per periode": int((omzet["signaal"] != "").sum()) if not omzet.empty else 0,
        "Loonkosten per periode": int((loon["signaal"] != "").sum()) if not loon.empty else 0,
        "Relaties": int((concentratie["signaal"] != "").sum()) if not concentratie.empty else 0,
        "Fiscaal": len(controls.build_fiscale_signalen(huidig)),
    }
    return pd.DataFrame(
        [
            {"categorie": categorie, "aantal_signalen": aantallen[categorie], "pagina": pagina}
            for categorie, pagina in SIGNAALCATEGORIEEN
        ],
        columns=["categorie", "aantal_signalen", "pagina"],
    )


# --- Pagina's ---------------------------------------------------------------


def pagina_overzicht(vorig: Auditfile, huidig: Auditfile, vergelijking: pd.DataFrame) -> None:
    # De vergelijking gebruikt beide bestanden, dus telt de betrouwbaarheid van
    # beide mee, plus de vraag of ze wel bij elkaar horen.
    bevindingen = pd.concat(
        [
            controleer_bestandenpaar(vorig, huidig),
            controleer_auditfile(huidig),
            controleer_auditfile(vorig),
        ],
        ignore_index=True,
    )
    telling = samenvatting(bevindingen)

    if telling[KRITIEK]:
        st.error(
            f"{telling[KRITIEK]} kritieke bevinding(en) bij de bestandscontrole, over de "
            "twee bestanden samen. Beoordeel die eerst; ze raken de betrouwbaarheid van "
            "alle cijfers hieronder."
        )
    elif telling[WAARSCHUWING]:
        st.warning(
            f"{telling[WAARSCHUWING]} aandachtspunt(en) bij de bestandscontrole. "
            "Zie de pagina Bestandscontrole."
        )
    else:
        st.success("Beide auditfiles zijn intern consistent en horen bij elkaar.")

    kop("Kerncijfers huidig boekjaar")
    a, b, c, d = st.columns(4)
    kerncijfer(a, "Boekingsregels", f"{len(huidig.lines):n}".replace(",", "."))
    kerncijfer(b, "Grootboekrekeningen", f"{len(huidig.accounts):n}".replace(",", "."))
    kerncijfer(c, "Relaties", f"{len(huidig.relations):n}".replace(",", "."))
    kerncijfer(d, "Btw-codes gebruikt", f"{len(vat.build_vat_usage(huidig))}")

    gebruik = vat.pas_mapping_toe(
        vat.build_vat_usage(huidig), huidige_mapping(), huidige_aftrekbaarheid()
    )
    rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte(), huidige_grondslagen())
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

    kop(
        "Signalen per categorie",
        "Waar valt iets te beoordelen? De categorie wijst de pagina aan waar de "
        "signalen met hun onderbouwing staan.",
    )
    telling = tel_signalen(huidig, gebruik)
    toon_tabel(telling)
    if int(telling["aantal_signalen"].sum()) == 0:
        st.caption("Geen signalen in alle categorieën.")

    kop(
        "Btw en boekingen in detail",
        "De twee categorieën die het vaakst tot een correctie leiden. De andere "
        "categorieën staan op hun eigen pagina.",
    )
    signalen = pd.concat(
        [
            vat.build_vat_anomalies(huidig, gebruik).assign(soort="Btw"),
            controls.build_ongebruikelijke_boekingen(huidig).assign(soort="Boekingen"),
        ],
        ignore_index=True,
    )
    if signalen.empty:
        st.caption("Geen btw- of boekingssignalen gevonden.")
    else:
        toon_tabel(
            signalen[["soort", "signaal", "aantal_regels", "bedrag", "toelichting"]],
            hoogte=320,
        )


def huidige_materialiteit(huidig: Auditfile) -> Materialiteit:
    """De materialiteit zoals de gebruiker die heeft ingesteld."""
    return Materialiteit(
        absoluut=float(st.session_state.get("materialiteit_absoluut", 1000.0)),
        relatief_pct=float(st.session_state.get("materialiteit_pct", 1.0)),
        grondslag=grondslag_omzet(huidig),
    )


def pagina_bevindingen(vorig: Auditfile, huidig: Auditfile, vergelijking: pd.DataFrame) -> None:
    kop(
        "Alle bevindingen op één plek",
        "Elke controle levert zijn eigen tabel op; hier staan ze in één vorm, gesorteerd "
        "op ernst en bedrag. Dit is de lijst waaruit een reviewmemorandum kan worden "
        "opgebouwd.",
    )

    grondslag = grondslag_omzet(huidig)
    links, midden, rechts = st.columns([1, 1, 2])
    absoluut = links.number_input(
        "Drempel in euro",
        min_value=0.0,
        value=float(st.session_state.get("materialiteit_absoluut", 1000.0)),
        step=100.0,
        key="materialiteit_absoluut",
        help="Bedragen onder deze grens worden gemarkeerd, niet weggelaten.",
    )
    relatief = midden.number_input(
        "Of percentage van de omzet",
        min_value=0.0,
        max_value=100.0,
        value=float(st.session_state.get("materialiteit_pct", 1.0)),
        step=0.1,
        key="materialiteit_pct",
        help="De hoogste van de twee grenzen geldt.",
    )
    materialiteit = Materialiteit(absoluut=absoluut, relatief_pct=relatief, grondslag=grondslag)
    with rechts:
        st.caption(
            f"Omzet volgens dit auditfile {euro(grondslag)}, dus {relatief:g}% is "
            f"{euro(grondslag * relatief / 100)}. De gebruikte drempel is "
            f"**{euro(materialiteit.drempel)}**. Dit is een werkafspraak van uzelf en geen "
            "norm uit wet of standaard."
        )

    opslag = huidige_opslag()
    bevindingen = verzamel_bevindingen(
        huidig,
        vorig,
        gebruik=vat.pas_mapping_toe(
            vat.build_vat_usage(huidig), huidige_mapping(), huidige_aftrekbaarheid()
        ),
        vergelijking=vergelijking,
        aangifte=huidige_aangifte(),
        grondslagen=huidige_grondslagen(),
        materialiteit=materialiteit,
    )
    bevindingen = pas_review_toe(bevindingen, opslag.lees_review())
    telling = samenvatting_per_ernst(bevindingen)

    a, b, c, d = st.columns(4)
    kerncijfer(a, "Kritiek", str(telling[KRITIEK]), "De cijfers zijn zo niet te gebruiken.")
    kerncijfer(b, "Waarschuwing", str(telling[WAARSCHUWING]), "Afwijking die beoordeling vraagt.")
    kerncijfer(c, "Signaal", str(telling[SIGNAAL]), "Iets om naar te kijken.")
    kerncijfer(
        d,
        "Nog te beoordelen",
        str(openstaande_bevindingen(bevindingen)),
        "Bevindingen zonder vastgelegde status.",
    )
    if telling[NIET_MOGELIJK]:
        st.caption(
            f"{telling[NIET_MOGELIJK]} controle(s) konden niet worden uitgevoerd. Ook dat "
            "hoort in een memorandum te staan; ze staan onderaan de lijst."
        )

    if bevindingen.empty:
        st.success("Geen bevindingen. Dat is zeldzaam: controleer of de bestanden kloppen.")
        return

    alleen_boven = st.checkbox(
        "Alleen bevindingen boven de drempel",
        value=False,
        help="Onder de drempel betekent: het bedrag is kleiner dan de materialiteit. "
        "Bevindingen zonder bedrag zijn niet te wegen en blijven altijd staan.",
    )
    zichtbaar = bevindingen[bevindingen["boven_drempel"]] if alleen_boven else bevindingen

    categorieen = sorted(set(bevindingen["categorie"]))
    gekozen = st.multiselect("Categorie", categorieen, default=[])
    if gekozen:
        zichtbaar = zichtbaar[zichtbaar["categorie"].isin(gekozen)]

    if zichtbaar.empty:
        st.caption("Geen bevindingen binnen deze selectie.")
        return

    bewerkt = st.data_editor(
        zichtbaar,
        hide_index=True,
        width="stretch",
        height=560,
        disabled=[kolom for kolom in zichtbaar.columns if kolom not in ("status", "notitie")],
        column_order=[
            "ernst",
            "categorie",
            "onderwerp",
            "bedrag",
            "status",
            "notitie",
            "aantal_regels",
            "rekening",
            "boven_drempel",
            "methode",
            "toelichting",
            "pagina",
        ],
        column_config={
            "ernst": st.column_config.TextColumn("Ernst", width="small"),
            "categorie": st.column_config.TextColumn("Categorie", width="small"),
            "onderwerp": st.column_config.TextColumn("Onderwerp", width="large"),
            "bedrag": st.column_config.NumberColumn("Bedrag", format="euro"),
            "status": st.column_config.SelectboxColumn(
                "Beoordeling", options=list(REVIEWSTATUSSEN), required=True, width="medium"
            ),
            "notitie": st.column_config.TextColumn(
                "Notitie", width="large", help="Wat u hebt vastgesteld of afgesproken."
            ),
            "aantal_regels": st.column_config.NumberColumn("Regels", format="plain"),
            "rekening": st.column_config.TextColumn("Rekening", width="small"),
            "boven_drempel": st.column_config.CheckboxColumn("Boven de drempel"),
            "methode": st.column_config.TextColumn("Gebaseerd op", width="small"),
            "toelichting": st.column_config.TextColumn("Toelichting", width="large"),
            "pagina": st.column_config.TextColumn("Te vinden op", width="small"),
        },
        key=f"bevindingen_editor_{opslag.sleutel}",
    )

    # Alleen wat de gebruiker heeft ingevuld wordt bewaard, op sleutel. Een
    # bevinding op "Te beoordelen" zonder notitie is geen invoer en hoort niet in
    # het bestand.
    opgeslagen_review = opslag.lees_review()
    nieuwe_review = dict(opgeslagen_review)
    for sleutel, status, notitie in zip(bewerkt["sleutel"], bewerkt["status"], bewerkt["notitie"]):
        sleutel = str(sleutel)
        status = str(status)
        notitie = str(notitie or "")
        if status == TE_BEOORDELEN and not notitie:
            nieuwe_review.pop(sleutel, None)
        else:
            nieuwe_review[sleutel] = {"status": status, "notitie": notitie}

    openstaand = nieuwe_review != opgeslagen_review
    bewaren, melding = st.columns([1, 4])
    if bewaren.button(
        "Beoordeling vastleggen",
        type="primary",
        disabled=not openstaand or not opslag.bruikbaar,
        help="Bewaart de beoordeling en de notities bij dit dossier.",
    ):
        if not opslag.schrijf_review(nieuwe_review):
            st.warning(f"De beoordeling kon niet worden bewaard in {opslag.map}.")
        elif not opslag.schrijf_label(huidig.bedrijfsnaam, huidig.boekjaar):
            st.warning(f"Het dossierlabel kon niet worden bewaard in {opslag.map}.")
        st.rerun()

    with melding:
        if not opslag.bruikbaar:
            st.caption(
                "Dit auditfile is niet aan een dossier te koppelen, dus de beoordeling "
                "wordt niet bewaard. Zie de pagina Btw voor de reden."
            )
        elif openstaand:
            st.info("Er staan wijzigingen open die nog niet zijn vastgelegd.")
        else:
            st.caption(
                f"{len(zichtbaar)} van de {len(bevindingen)} bevindingen in beeld. "
                "De kolom Te vinden op wijst de pagina aan met de onderbouwing."
            )


def pagina_bestandscontrole(vorig: Auditfile, huidig: Auditfile) -> None:
    kop(
        "Horen deze twee bestanden bij elkaar?",
        "De vergelijking rekent alles door zonder dat zelf te vragen. Twee auditfiles "
        "van verschillende ondernemingen leveren dan een plausibel ogende jaarvergelijking "
        "op, en dat is gevaarlijker dan een lege uitkomst.",
    )
    toon_tabel(controleer_bestandenpaar(vorig, huidig), kleur_op="ernst")

    kop(
        "Is elk auditfile intern consistent?",
        "Het bestand geeft zelf controletotalen op. Wijkt de inhoud daarvan af, dan "
        "staan alle conclusies uit dat bestand op losse schroeven.",
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

    kop(
        "Sluit de jaarovergang aan?",
        "De eindbalans van vorig jaar hoort, na bestemming van het resultaat, gelijk te "
        "zijn aan de beginbalans van dit jaar.",
    )
    verloop = build_jaarovergang_verloop(vorig, huidig)
    toon_tabel(verloop)
    if not verloop.empty:
        if jaarovergang_sluit_aan(verloop):
            st.success(
                "De jaarovergang sluit aan: de beginbalans komt overeen met de eindbalans "
                "van vorig jaar, en de toename van het eigen vermogen met het resultaat."
            )
        else:
            per_post = verloop.set_index("post")["bedrag"]
            buiten = float(per_post.get("Verschil buiten het eigen vermogen", 0.0))
            binnen = float(per_post.get("Onverklaard in het eigen vermogen", 0.0))
            meldingen = []
            if abs(buiten) >= 0.005:
                meldingen.append(
                    f"{euro(buiten)} verschil tussen de beginbalans en de eindstand van "
                    "vorig jaar, buiten het eigen vermogen"
                )
            if abs(binnen) >= 0.005:
                meldingen.append(
                    f"{euro(binnen)} in het eigen vermogen dat niet uit het resultaat van "
                    "vorig jaar volgt"
                )
            st.error(
                "De jaarovergang sluit niet aan: "
                + "; ".join(meldingen)
                + ". Beoordeel dit voordat u de jaarvergelijking gebruikt."
            )

    overgang = build_jaarovergang(vorig, huidig)
    afwijkend = overgang[overgang["signaal"] != ""] if not overgang.empty else overgang
    with st.expander(f"Per balansrekening ({len(afwijkend)} met een verschil)"):
        st.caption(
            "Een verschil op één rekening is niet meteen een fout: bij de "
            "resultaatbestemming verschuift het resultaat binnen het eigen vermogen, en "
            "bij een omnummering verhuist een saldo naar een ander nummer. Het totaal "
            "hierboven is de harde controle."
        )
        toon_tabel(overgang, kleur_op="signaal", hoogte=420)

    kop(
        "Wat bevat dit bestand?",
        "Een auditfile is geen vaste hoeveelheid gegevens: bijna alles is optioneel en "
        "het boekhoudpakket bepaalt wat er in staat. Twee bestanden van dezelfde "
        "onderneming kunnen dus verschillende analyses toelaten.",
    )
    niveau, uitleg = openstaande_posten_niveau(huidig)
    if niveau == NIVEAU_GEEN:
        st.error(f"**{NIVEAU_NAAM[niveau]}.** {uitleg}")
    elif niveau == NIVEAU_VERVALDATUM:
        st.success(f"**{NIVEAU_NAAM[niveau]}.** {uitleg}")
    else:
        st.warning(f"**{NIVEAU_NAAM[niveau]}.** {uitleg}")

    toon_tabel(build_bestandsprofiel(huidig), hoogte=520)
    kop(
        "Dekking op de debiteuren- en crediteurenrekeningen",
        "Voor openstaande posten is niet het aantal factuurreferenties beslissend, maar of "
        "de referentie op beide zijden staat: op de factuur én op de betaling. Alleen dan "
        "is per factuur te salderen tot een openstaand bedrag.",
    )
    toon_tabel(
        build_relatiedekking(huidig),
        leegmelding="Geen boekingsregels met relatiegegevens.",
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


def huidige_opslag() -> DossierOpslag:
    """De lokale opslag van het dossier dat nu geladen is."""
    return DossierOpslag.voor(st.session_state.get("dossier_sleutel", ""))


def huidige_mapping() -> dict[str, str]:
    return st.session_state.get("btw_mapping", {})


def huidige_aangifte() -> dict[str, float]:
    return st.session_state.get("btw_aangifte", {})


def huidige_aftrekbaarheid() -> dict[str, float]:
    return st.session_state.get("btw_aftrekbaarheid", {})


def huidige_grondslagen() -> dict[str, float]:
    return st.session_state.get("btw_grondslagen", {})


def stel_dossier_in(huidig: Auditfile) -> DossierOpslag:
    """Laad de invoer van dit dossier, en niets van een ander.

    Wordt een ander auditfile geladen, dan hoort de invoer van het vorige
    dossier te verdwijnen: uit de sessie én uit de invulvelden. Anders staat de
    beoordeling van de ene klant bij de andere in beeld.
    """
    opslag = DossierOpslag.voor(huidig.dossier_sleutel)
    if st.session_state.get("dossier_sleutel") == opslag.sleutel:
        return opslag

    st.session_state["dossier_sleutel"] = opslag.sleutel
    st.session_state["btw_mapping"] = opslag.lees_mapping()
    st.session_state["btw_aangifte"] = opslag.lees_aangifte()
    st.session_state["btw_aftrekbaarheid"] = opslag.lees_aftrekbaarheid()
    st.session_state["btw_grondslagen"] = opslag.lees_grondslagen()
    # De widgets houden hun eigen waarde vast; die moet mee met het dossier.
    for sleutel in [
        naam
        for naam in st.session_state
        if str(naam).startswith(
            (
                "btw_mapping_editor",
                "btw_aftrek_editor",
                "bevindingen_editor",
                "aangifte_",
                "grondslag_",
            )
        )
    ]:
        st.session_state.pop(sleutel, None)
    return opslag


def bewaar_invoer(opslag: DossierOpslag, huidig: Auditfile, **onderdelen) -> bool:
    """Bewaar invoer in de map van dit dossier, met het label erbij.

    Het label wordt hier geschreven en niet bij het openen van een bestand: het
    inlezen van een auditfile hoort geen spoor op schijf achter te laten.
    """
    if not opslag.bruikbaar:
        return False
    gelukt = opslag.schrijf_label(huidig.bedrijfsnaam, huidig.boekjaar)
    schrijvers = {
        "mapping": opslag.schrijf_mapping,
        "aftrekbaarheid": opslag.schrijf_aftrekbaarheid,
        "aangifte": opslag.schrijf_aangifte,
        "grondslagen": opslag.schrijf_grondslagen,
    }
    for naam, inhoud in onderdelen.items():
        gelukt = schrijvers[naam](inhoud) and gelukt
    return gelukt


def toon_oude_invoer(opslag: DossierOpslag, huidig: Auditfile) -> None:
    """Bied invoer uit de versie zonder dossierscheiding aan om over te nemen.

    Die invoer stond op één vaste plek en hoort dus bij een onbekend dossier.
    Hem stilzwijgend aan het eerst geopende bestand toekennen zou precies de
    vermenging opleveren die de scheiding moet voorkomen. Daarom vraagt de tool
    het, in plaats van te kiezen.
    """
    if not oude_invoer_aanwezig():
        return
    with st.container(border=True):
        st.warning(
            "Er staat invoer uit een eerdere versie van de tool, die nog niet aan een "
            "dossier was gekoppeld. Die wordt niet meer gebruikt. Neem hem over in dit "
            "dossier als hij bij deze onderneming en dit boekjaar hoort, of verwijder hem."
        )
        overnemen, verwijderen, _ = st.columns([1, 1, 3])
        if overnemen.button(
            "Overnemen in dit dossier",
            disabled=not opslag.bruikbaar,
            help="Zet de oude invoer over naar de map van dit dossier.",
        ):
            oud = lees_oude_invoer()
            st.session_state["btw_mapping"] = oud["mapping"]
            st.session_state["btw_aftrekbaarheid"] = oud["aftrekbaarheid"]
            st.session_state["btw_aangifte"] = oud["aangifte"]
            st.session_state["btw_grondslagen"] = oud["grondslagen"]
            if bewaar_invoer(opslag, huidig, **oud):
                verwijder_oude_invoer()
            else:
                st.warning(f"De invoer kon niet worden bewaard in {opslag.map}.")
            st.rerun()
        if verwijderen.button("Oude invoer verwijderen"):
            if not verwijder_oude_invoer():
                st.warning("De oude invoer kon niet worden verwijderd.")
            st.rerun()


def pagina_btw(huidig: Auditfile) -> None:
    gebruik_ruw = vat.build_vat_usage(huidig)
    if gebruik_ruw.empty:
        st.warning("Dit auditfile bevat geen boekingsregels met een btw-code.")
        return

    opslag = huidige_opslag()
    if not opslag.bruikbaar:
        st.warning(
            "Dit auditfile vermeldt geen btw-nummer, KvK-nummer of naam, of geen boekjaar. "
            "De invoer op deze pagina is daardoor niet aan een dossier te koppelen en wordt "
            "niet bewaard: bij het volgende bestand zou hij bij de verkeerde klant kunnen "
            "opduiken. De analyse zelf werkt gewoon."
        )
    toon_oude_invoer(opslag, huidig)

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
            key=f"btw_mapping_editor_{opslag.sleutel}",
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
                key=f"btw_aftrek_editor_{opslag.sleutel}",
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
            if not bewaar_invoer(
                opslag, huidig, mapping=nieuwe_mapping, aftrekbaarheid=nieuwe_aftrek
            ):
                st.warning(f"De koppeling kon niet worden bewaard in {opslag.map}.")
            st.rerun()

        if wissen.button(
            "Vastlegging wissen",
            disabled=not (opgeslagen or opgeslagen_aftrek),
            help="Verwijdert uw keuzes, zodat de tabel weer de voorstellen van de tool toont.",
        ):
            st.session_state["btw_mapping"] = {}
            st.session_state["btw_aftrekbaarheid"] = {}
            st.session_state.pop(f"btw_mapping_editor_{opslag.sleutel}", None)
            st.session_state.pop(f"btw_aftrek_editor_{opslag.sleutel}", None)
            if not bewaar_invoer(opslag, huidig, mapping={}, aftrekbaarheid={}):
                st.warning(f"De koppeling kon niet worden gewist in {opslag.map}.")
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
        btw_per_rubriek = dict(
            zip(rubrieken_basis["rubriek"], rubrieken_basis["btw_volgens_xaf"])
        )
        grondslag_per_rubriek = dict(
            zip(rubrieken_basis["rubriek"], rubrieken_basis["grondslag_volgens_xaf"])
        )

        def invoervelden(
            codes: list[str], opgeslagen: dict[str, float], volgens_xaf: dict[str, float], soort: str
        ) -> dict[str, float]:
            """Eén rij invoervelden per rubriek; een leeg veld blijft leeg."""
            ingevoerd: dict[str, float] = {}
            kolommen = st.columns(4)
            for index, code in enumerate(codes):
                with kolommen[index % len(kolommen)]:
                    bestaand = opgeslagen.get(code)
                    bedrag = volgens_xaf.get(code)
                    herkomst = (
                        "Komt niet voor in dit auditfile."
                        if bedrag is None
                        else f"Volgens dit auditfile {euro(bedrag)}."
                    )
                    waarde = st.number_input(
                        f"Rubriek {code}",
                        value=float(bestaand) if bestaand is not None else None,
                        step=1.0,
                        format="%.2f",
                        placeholder="niet ingevuld",
                        help=f"{rubriek(code).omschrijving}. {herkomst}",
                        key=f"{soort}_{opslag.sleutel}_{code}",
                    )
                    if waarde is not None:
                        ingevoerd[code] = float(waarde)
            return ingevoerd

        # Een formulier, geen veld dat zichzelf bewaart. Streamlit voert de code
        # van alle tabbladen uit bij elke herberekening, dus een veld dat zijn
        # eigen waarde wegschrijft doet dat ook zonder dat iemand dit tabblad
        # heeft geopend.
        opgeslagen_aangifte = huidige_aangifte()
        opgeslagen_grondslagen = huidige_grondslagen()
        # De sleutel mag niet gelijk zijn aan de session-state-sleutel
        # "btw_aangifte": Streamlit staat niet toe dat een waarde onder de
        # sleutel van een widget zelf wordt gezet.
        with st.form("btw_aangifte_formulier"):
            st.markdown("**Omzetbelasting per rubriek**")
            ingevoerd = invoervelden(
                [code for code in RUBRIEK_CODES if rubriek(code).heeft_btw],
                opgeslagen_aangifte,
                btw_per_rubriek,
                "aangifte",
            )
            st.markdown("**Bedrag waarover de omzetbelasting wordt berekend**")
            st.caption(
                "Bij 1e, 3a, 3b en 3c vraagt het formulier alleen dit bedrag. Zonder deze "
                "invoer zijn die rubrieken nergens mee te vergelijken."
            )
            ingevoerde_grondslagen = invoervelden(
                [code for code in RUBRIEK_CODES if rubriek(code).heeft_grondslag],
                opgeslagen_grondslagen,
                grondslag_per_rubriek,
                "grondslag",
            )
            bewaren = st.form_submit_button("Aangiftebedragen bewaren", type="primary")
        if bewaren:
            st.session_state["btw_aangifte"] = ingevoerd
            st.session_state["btw_grondslagen"] = ingevoerde_grondslagen
            if not bewaar_invoer(
                opslag, huidig, aangifte=ingevoerd, grondslagen=ingevoerde_grondslagen
            ):
                st.warning(f"De aangiftebedragen konden niet worden bewaard in {opslag.map}.")
            st.rerun()

        rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte(), huidige_grondslagen())
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
        rubrieken = vat.build_rubric_summary(gebruik, huidige_aangifte(), huidige_grondslagen())
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
    buiten_beschouwing = controls.afsluitperioden(huidig)
    if buiten_beschouwing:
        st.caption(
            "Periode "
            + ", ".join(str(periode) for periode in buiten_beschouwing)
            + " uit de periodetabel telt hier niet mee: die beslaat geen eigen tijdvak "
            "en is een beginbalans- of afsluitperiode. Boekingen daarin komen wel in de "
            "grootboekkaarten terug."
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


def toon_relatiesaldi(huidig: Auditfile) -> None:
    """De openstaande bedragen per relatie uit XAF 4.0, met hun aansluiting.

    Alleen zichtbaar wanneer het bestand die bedragen geeft. Een lege tabel met
    nullen zou de indruk wekken dat er niets openstaat, terwijl het gegeven
    ontbreekt; wat het bestand niet toelaat, staat op de Bestandscontrole.
    """
    if not relatiesaldi.heeft_relatiesaldi(huidig):
        return

    kop(
        "Openstaande bedragen per relatie",
        "XAF 4.0 geeft per debiteur en crediteur het openstaande bedrag bij begin en "
        "einde van het boekjaar. Dat is een eindstand, geen factuurlijst en geen "
        "ouderdom. De eerste controle is of die standen optellen tot het saldo van de "
        "debiteuren- en de crediteurenrekening.",
    )
    aansluiting = relatiesaldi.build_relatiesaldo_aansluiting(huidig)
    toon_tabel(aansluiting, kleur_op="signaal")
    if not aansluiting.empty and (aansluiting["signaal"] == "verschil").any():
        st.warning(
            "De openstaande bedragen sluiten niet aan op het grootboek. Dat hoeft geen "
            "fout te zijn: op een relatierekening staan vaker posten die niet aan een "
            "relatie hangen, zoals een verzamelboeking of een afboeking. Beoordeel het "
            "verschil voordat u de standen gebruikt."
        )

    with st.expander("Per relatie"):
        st.caption(
            "Het verloopverschil is de eindstand uit het bestand min de beginstand plus "
            "de mutaties van het boekjaar op de relatierekening. Is dat niet nul, dan is "
            "de stand niet uit het grootboek af te leiden."
        )
        toon_tabel(
            relatiesaldi.build_relatiesaldi(huidig),
            kleur_op="signaal",
            hoogte=460,
            leegmelding="Geen relatie met een openstaand bedrag.",
        )


def pagina_relaties(huidig: Auditfile) -> None:
    # De relatietabel en de relatie-id's op de boekingsregels komen los van
    # elkaar voor. Ontbreekt de tabel maar staan de id's er wel, dan is de
    # analyse gewoon te maken; alleen de namen ontbreken dan. Blokkeren op een
    # lege tabel gooide bruikbare gegevens weg.
    heeft_relatie_ids = (
        not huidig.lines.empty
        and "line_custSupID" in huidig.lines.columns
        and (huidig.lines["line_custSupID"].astype(str).str.strip() != "").any()
    )
    if huidig.relations.empty and not heeft_relatie_ids:
        st.info(
            "Dit auditfile bevat geen debiteuren- en crediteurengegevens: geen "
            "relatietabel en geen relatie-id op de boekingsregels."
        )
        return
    if huidig.relations.empty:
        st.warning(
            "Dit auditfile heeft geen relatietabel, maar de boekingsregels dragen wel "
            "relatie-id's. De analyse werkt daarmee; alleen de namen ontbreken."
        )

    st.info(
        "Wat hier staat is wat er in dit boekjaar per relatie is gefactureerd en "
        "afgewikkeld op de debiteuren- en crediteurenrekeningen, inclusief btw. Het is "
        "geen omzet en geen openstaande-postenlijst. De netto mutatie is de verandering "
        "van het saldo in dit jaar, zonder het beginsaldo, en dus niet het openstaande "
        "bedrag. Een auditfile kán openstaande posten met een vervaldatum bevatten, maar "
        "alleen in XAF 3.2 en alleen wanneer het boekhoudpakket die subadministratie "
        "vult; die leest deze tool nog niet. XAF 4.0 heeft die velden geschrapt en geeft "
        "in plaats daarvan een openstaand bedrag per relatie; dat leest de tool wel, en "
        "het staat hieronder zodra het bestand het geeft."
    )

    toon_relatiesaldi(huidig)

    kop(
        "Concentratie",
        "Hoe groot is het aandeel van de grootste relaties in het gefactureerde bedrag?",
    )
    toon_tabel(controls.build_relatie_concentratie(huidig), kleur_op="signaal")

    links, rechts = st.columns(2)
    with links:
        kop("Debiteuren met het hoogste gefactureerde bedrag")
        toon_tabel(
            controls.build_relatie_analyse(huidig, "debiteur"),
            hoogte=460,
            leegmelding="Geen debiteuren gevonden.",
        )
    with rechts:
        kop("Crediteuren met het hoogste gefactureerde bedrag")
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
                huidige_grondslagen(),
                huidige_materialiteit(huidig),
                huidige_opslag().lees_review(),
            )
        st.download_button(
            "Download het werkboek",
            data=inhoud,
            file_name=exportnaam(huidig, vorig),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def toon_lokale_opslag(opslag: DossierOpslag) -> None:
    """Laat zien wat er lokaal is bewaard, en laat het wissen.

    Opslag die niet te overzien is, is niet te beheren: wie niet ziet welke
    dossiers op zijn computer staan, kan ze ook niet opruimen.
    """
    dossiers = bekende_dossiers()
    with st.sidebar.expander(f"Lokale opslag ({len(dossiers)})"):
        st.caption(
            f"Eigen invoer staat per dossier in `{DOSSIER_DIR}`. Auditfiles worden nooit "
            "bewaard; die verdwijnen bij het afsluiten."
        )
        if not dossiers:
            st.caption("Er is nog niets bewaard.")
        for dossier in dossiers:
            dit = " (dit dossier)" if dossier["sleutel"] == opslag.sleutel else ""
            naam = dossier["naam"] or "onbekende onderneming"
            jaar = dossier["boekjaar"] or "onbekend jaar"
            st.write(f"- {naam}, {jaar}{dit}")
        if opslag.heeft_invoer and st.button(
            "Invoer van dit dossier wissen",
            help=(
                "Verwijdert de rubriekindeling, het aftrekbare aandeel, de "
                "aangiftebedragen en de grondslagen van dit dossier."
            ),
        ):
            if opslag.wis():
                for sleutel in [
                    naam
                    for naam in st.session_state
                    if str(naam).startswith(
                        ("btw_", "dossier_sleutel", "aangifte_", "grondslag_")
                    )
                ]:
                    st.session_state.pop(sleutel, None)
                st.rerun()
            else:
                st.warning(f"De invoer kon niet worden verwijderd uit {opslag.map}.")


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

    opslag = stel_dossier_in(huidig)

    st.sidebar.markdown(
        f"**{huidig.bedrijfsnaam or 'Onbekende onderneming'}**  \n"
        f"Boekjaar {huidig.boekjaar} tegenover {vorig.boekjaar}"
    )
    if opslag.bruikbaar:
        st.sidebar.caption(f"Dossier `{opslag.sleutel}`")
    else:
        st.sidebar.caption("Dossier niet te bepalen; eigen invoer wordt niet bewaard.")
    st.sidebar.markdown("---")
    pagina = st.sidebar.radio("Onderdeel", PAGINAS, label_visibility="collapsed")
    st.sidebar.markdown("---")
    toon_lokale_opslag(opslag)
    st.sidebar.caption(f"Versie {APP_VERSIE}")

    vergelijking = maak_vergelijking(vorig, huidig, vergelijkingssleutel(vorig, huidig))

    if pagina == "Overzicht":
        pagina_overzicht(vorig, huidig, vergelijking)
    elif pagina == "Bevindingen":
        pagina_bevindingen(vorig, huidig, vergelijking)
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
