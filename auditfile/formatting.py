"""Presentatie van tabellen in de app.

Uitgangspunt: bedragen blijven getallen. Een bedrag dat als tekst wordt
weggeschreven, oogt misschien netjes maar is niet meer te sorteren, niet meer
te filteren en niet meer op te tellen. Streamlit kan getallen zelf opmaken via
``column_config``, dus die weg wordt hier consequent gevolgd.

Deze module vertaalt de technische kolomnamen uit de analysemodules naar
leesbare labels met de juiste opmaak, zodat elke tabel in de app er hetzelfde
uitziet zonder dat elke pagina dat opnieuw moet regelen.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

# Kolomnamen die een geldbedrag bevatten. De vergelijking gaat op hele woorden
# en fragmenten, zodat samengestelde namen als "grondslag_volgens_xaf" ook
# worden herkend.
BEDRAG_FRAGMENTEN = (
    "bedrag",
    "saldo",
    "mutatie",
    "mutaties",
    "grondslag",
    "btw",
    "totaal",
    "verschil",
    "omzet",
    "loonkosten",
    "kosten",
    "afwijking",
    "gemiddeld",
)

PERCENTAGE_FRAGMENTEN = ("pct", "percentage", "aandeel", "perc")

AANTAL_FRAGMENTEN = ("aantal", "regels", "perioden", "periode", "relaties")

DATUM_FRAGMENTEN = ("datum", "date", "dt")

# Leesbare labels voor de kolommen die de analysemodules opleveren.
LABELS: dict[str, str] = {
    "aandeel_grootste": "Aandeel grootste",
    "aandeel_pct": "Aandeel",
    "aandeel_top5": "Aandeel top 5",
    "accDesc": "Omschrijving",
    "accTp": "Type",
    "aantal_boekingsregels": "Regels",
    "aantal_perioden": "Perioden",
    "aantal_regels": "Regels",
    "aantal_relaties": "Relaties",
    "afwijking": "Afwijking",
    "afwijking_pct": "Afwijking",
    "beginsaldo": "Beginsaldo",
    "bevinding": "Bevinding",
    "btw_aangifte": "Btw voor de aangifte",
    "btw_bedrag": "Btw",
    "btw_code": "Btw-code",
    "btw_grootboek": "Btw in het grootboek",
    "btw_volgens_aangifte": "Btw volgens aangifte",
    "btw_volgens_xaf": "Btw volgens auditfile",
    "categorie": "Categorie",
    "conclusie": "Conclusie",
    "controle": "Controle",
    "documentreferentie": "Document",
    "eindsaldo": "Eindsaldo",
    "ernst": "Ernst",
    "gemiddeld_per_periode": "Gemiddeld per periode",
    "grondslag": "Grondslag",
    "grondslag_aangifte": "Grondslag voor de aangifte",
    "grondslag_grootboek": "Grondslag in het grootboek",
    "grondslag_volgens_xaf": "Grondslag volgens auditfile",
    "grootste_afwijking": "Grootste afwijking",
    "hoofdpercentage": "Hoofdtarief",
    "journaal": "Journaal",
    "line_accID": "Rekening",
    "line_desc": "Omschrijving regel",
    "loonkosten": "Loonkosten",
    "maand": "Maand",
    "methode": "Gebaseerd op",
    "mutatie_boekjaar": "Mutatie boekjaar",
    "mutaties_boekjaar": "Mutatie boekjaar",
    "naam": "Naam",
    "omschrijving": "Omschrijving",
    "ontbrekende_perioden": "Ontbrekende perioden",
    "onderwerp": "Onderwerp",
    "percentage": "Tarief",
    "percentages": "Tarieven",
    "periode": "Periode",
    "perioden": "Perioden",
    "post": "Post",
    "reden": "Reden",
    "regels_huidig_jaar": "Regels huidig jaar",
    "regels_vorig_jaar": "Regels vorig jaar",
    "rekening": "Rekening",
    "rekeningomschrijving": "Rekeningomschrijving",
    "relatie": "Relatie",
    "RGScode": "RGS-code",
    "RGS-rubriek": "RGS-rubriek",
    "RGSbron": "RGS-bron",
    "rol": "Rol",
    "rubriek": "Rubriek",
    "rubriek_bron": "Herkomst",
    "aftrekbaar_pct": "Aftrekbaar",
    "btw_aftrekbaar_5b": "Aftrekbaar in 5b",
    "waarvan_uit_verlegging": "Waarvan uit 2a, 4a of 4b",
    "rubriek_voorstel": "Voorgestelde rubriek",
    "signaal": "Signaal",
    "soort": "Soort",
    "status": "Status",
    "toelichting": "Toelichting",
    "totaalbedrag": "Totaalbedrag",
    "transactie": "Transactie",
    "tx_nr": "Transactie",
    "verschil": "Verschil",
    "verschil_bedrag": "Verschil",
    "verschil_pct": "Verschil",
    "verwachte_btw": "Verwachte btw",
    "zekerheid": "Zekerheid",
}

# Kolommen met een lange lopende tekst; die krijgen extra breedte.
BREDE_KOLOMMEN = {"toelichting", "bevinding", "reden", "signaal", "omschrijving regel"}


def label(kolom: str) -> str:
    """Een leesbaar label bij een technische kolomnaam."""
    if kolom in LABELS:
        return LABELS[kolom]
    return kolom.replace("_", " ").capitalize()


def _bevat(kolom: str, fragmenten: tuple[str, ...]) -> bool:
    genormaliseerd = kolom.lower().replace("-", "_")
    return any(fragment in genormaliseerd for fragment in fragmenten)


def kolom_config(df: pd.DataFrame, overrides: dict | None = None) -> dict:
    """Bouw een ``column_config`` voor een tabel.

    Het type wordt afgeleid uit de kolomnaam en het dtype. Percentages en
    aantallen gaan voor op bedragen, omdat een naam als "afwijking_pct" beide
    fragmenten bevat.
    """
    overrides = overrides or {}
    config: dict = {}
    for kolom in df.columns:
        naam = str(kolom)
        if naam in overrides:
            config[naam] = overrides[naam]
            continue

        is_numeriek = pd.api.types.is_numeric_dtype(df[kolom])
        breedte = "large" if naam.lower() in BREDE_KOLOMMEN else None

        if _bevat(naam, DATUM_FRAGMENTEN) and pd.api.types.is_datetime64_any_dtype(df[kolom]):
            config[naam] = st.column_config.DateColumn(label(naam), format="DD-MM-YYYY")
        elif is_numeriek and _bevat(naam, PERCENTAGE_FRAGMENTEN):
            config[naam] = st.column_config.NumberColumn(label(naam), format="%.1f%%")
        elif is_numeriek and _bevat(naam, AANTAL_FRAGMENTEN):
            config[naam] = st.column_config.NumberColumn(label(naam), format="plain")
        elif is_numeriek and _bevat(naam, BEDRAG_FRAGMENTEN):
            config[naam] = st.column_config.NumberColumn(label(naam), format="euro")
        elif is_numeriek:
            config[naam] = st.column_config.NumberColumn(label(naam), format="localized")
        else:
            config[naam] = st.column_config.TextColumn(label(naam), width=breedte)
    return config


def toon_tabel(
    df: pd.DataFrame,
    *,
    overrides: dict | None = None,
    hoogte: int | None = None,
    leegmelding: str = "Geen gegevens gevonden.",
    verberg: tuple[str, ...] = (),
    kleur_op: str | None = None,
    **kwargs,
) -> None:
    """Toon een tabel met consequente opmaak, of een nette melding als hij leeg is.

    ``kleur_op`` geeft de naam van een kolom met een status- of ernstwaarde; die
    rijen krijgen dan een achtergrondkleur.
    """
    if df is None or df.empty:
        st.caption(leegmelding)
        return

    tabel = df.drop(columns=[kolom for kolom in verberg if kolom in df.columns])
    weergave = kleur_rijen(tabel, kleur_op) if kleur_op and kleur_op in tabel.columns else tabel
    # Streamlit accepteert geen height=None; de parameter wordt alleen
    # meegegeven wanneer er een hoogte is opgegeven.
    if hoogte:
        kwargs["height"] = hoogte
    st.dataframe(
        weergave,
        column_config=kolom_config(tabel, overrides),
        hide_index=True,
        width="stretch",
        **kwargs,
    )


# Kleuren per status. Bewust zacht: de tabel moet leesbaar blijven en in een
# donker thema niet gaan schreeuwen.
STATUSKLEUREN: dict[str, str] = {
    "kritiek": "rgba(220, 53, 69, 0.18)",
    "waarschuwing": "rgba(255, 193, 7, 0.18)",
    "in orde": "rgba(25, 135, 84, 0.12)",
    "niet mogelijk": "rgba(120, 120, 120, 0.12)",
    "verschil": "rgba(255, 193, 7, 0.18)",
    "sluit aan": "rgba(25, 135, 84, 0.12)",
    "niet ingevuld": "rgba(120, 120, 120, 0.12)",
    "alleen in de aangifte": "rgba(220, 53, 69, 0.18)",
    "alleen grondslag": "rgba(120, 120, 120, 0.12)",
    "ontbrekende perioden": "rgba(220, 53, 69, 0.18)",
    "tegengestelde boeking": "rgba(255, 193, 7, 0.18)",
    "sterke afwijking": "rgba(255, 193, 7, 0.18)",
    "handmatig beoordelen": "rgba(120, 120, 120, 0.12)",
    "geen bijzonderheden": "rgba(25, 135, 84, 0.12)",
}


def kleur_rijen(df: pd.DataFrame, kolom: str):
    """Geef rijen een achtergrondkleur op basis van een statuskolom."""

    def kleur(rij: pd.Series) -> list[str]:
        waarde = str(rij.get(kolom, "")).strip().lower()
        achtergrond = STATUSKLEUREN.get(waarde, "")
        stijl = f"background-color: {achtergrond}" if achtergrond else ""
        return [stijl] * len(rij)

    return df.style.apply(kleur, axis=1)


# --- Losse waarden ----------------------------------------------------------


def euro(waarde, decimalen: int = 2) -> str:
    """Een bedrag in Nederlandse notatie, bijvoorbeeld ``€ 1.234,56``."""
    getal = pd.to_numeric(waarde, errors="coerce")
    if pd.isna(getal):
        return "—"
    opgemaakt = f"{float(getal):,.{decimalen}f}"
    opgemaakt = opgemaakt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"€ {opgemaakt}"


def euro_kort(waarde) -> str:
    """Een bedrag zonder centen, voor kerncijfers."""
    return euro(waarde, decimalen=0)


def procent(waarde, decimalen: int = 1) -> str:
    getal = pd.to_numeric(waarde, errors="coerce")
    if pd.isna(getal):
        return "—"
    opgemaakt = f"{float(getal):,.{decimalen}f}".replace(".", ",")
    return f"{opgemaakt}%"


def datum_nl(waarde) -> str:
    tijdstip = pd.to_datetime(waarde, errors="coerce")
    if pd.isna(tijdstip):
        return ""
    return tijdstip.strftime("%d-%m-%Y")
