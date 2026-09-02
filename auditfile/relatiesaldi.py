"""Openstaande bedragen per relatie, en hun aansluiting op het grootboek.

XAF 4.0 heeft de subadministratie van 3.2 geschrapt en geeft in plaats daarvan
per debiteur en crediteur één bedrag bij het begin en één bij het einde van het
boekjaar (``opBalDesc``/``clBalDesc``, met ``opBalTp``/``clBalTp`` voor debet of
credit). Dat is bewijsniveau 3 uit ``capability.py``: een eindstand per relatie,
geen lijst van facturen en geen vervaldatum. Er is dus geen ouderdomsanalyse uit
te maken, en deze module doet daar ook geen poging toe.

Wat het bestand op dat niveau wél toelaat is de controle die in de
samenstelpraktijk als eerste komt: telt de subadministratie op tot het saldo van
de debiteuren- en de crediteurenrekening? Loopt dat uiteen, dan staat er iets op
de relatierekening dat niet aan een relatie hangt, of ontbreekt er een relatie in
het bestand.

Een verschil is een signaal en geen fout. Pakketten boeken ook posten op een
relatierekening die niet aan een relatie hangen, zoals een verzamelboeking van
een incasso of een afboeking van een oninbare vordering. De tool benoemt het
verschil; de beoordeling is aan de gebruiker.

De bedragen komen al getekend uit de parser: debet positief, credit negatief.
Een debiteurenstand is daarmee positief en een crediteurenstand negatief, gelijk
aan het grootboeksaldo, zodat hier nergens een teken hoeft te worden omgekeerd.
"""
from __future__ import annotations

import pandas as pd

from .controls import RELATIEREKENINGEN, _selecteer, soort_uit_code
from .model import Auditfile

# Kleiner dan een halve cent is afrondingsruis en geen verschil.
TOLERANTIE = 0.005

SALDO_COLUMNS = [
    "relatie",
    "naam",
    "soort",
    "openstaand_begin",
    "mutatie_boekjaar",
    "openstaand_eind",
    "verloop_verschil",
    "signaal",
]

AANSLUITING_COLUMNS = [
    "soort",
    "methode",
    "rekeningen",
    "aantal_relaties",
    "grootboek_beginsaldo",
    "openstaand_begin",
    "verschil_begin",
    "grootboek_eindsaldo",
    "openstaand_eind",
    "verschil_eind",
    "signaal",
    "conclusie",
]


def heeft_relatiesaldi(af: Auditfile) -> bool:
    """Staan er openstaande bedragen per relatie in dit bestand?

    Alleen XAF 4.0 kent die velden, en ook daar zijn ze optioneel. Zonder deze
    controle zou de aansluiting een grootboeksaldo tegenover nul zetten en dat
    als verschil presenteren, terwijl er niets te vergelijken valt.
    """
    if af.relations.empty:
        return False
    kolommen = [k for k in ("openstaand_begin", "openstaand_eind") if k in af.relations.columns]
    if not kolommen:
        return False
    return bool(af.relations[kolommen].notna().to_numpy().any())


def _soort_van_relatie(rij: pd.Series) -> str:
    """Debiteur of crediteur, met het teken van de stand als terugval.

    ``custSupTp`` gaat voor, want die deelt de relatie in haar geheel in: een
    creditnota maakt een klant geen leverancier. Ontbreekt de code, dan blijft
    alleen het teken over. Dat is zwakker, want juist een debiteur met een
    creditsaldo komt dan bij de crediteuren terecht. Daarom staat de gebruikte
    methode in de aansluiting.
    """
    volgens_code = soort_uit_code(rij.get("custSupTp", ""))
    if volgens_code is not None:
        return volgens_code
    for kolom in ("openstaand_eind", "openstaand_begin"):
        waarde = rij.get(kolom)
        if waarde is not None and pd.notna(waarde) and abs(float(waarde)) > TOLERANTIE:
            return "debiteur" if float(waarde) > 0 else "crediteur"
    return ""


def _mutaties_per_relatie(af: Auditfile) -> dict[tuple[str, str], float]:
    """De mutatie op de relatierekeningen, per soort en per relatie.

    Alleen boekingen op de debiteuren- of crediteurenrekening tellen mee. Een
    betaling die het pakket rechtstreeks op de bankrekening met een relatie-id
    schrijft hoort niet in het verloop van de openstaande post en blijft hier dus
    buiten.
    """
    mutaties: dict[tuple[str, str], float] = {}
    if af.lines.empty or "line_custSupID" not in af.lines.columns:
        return mutaties
    for soort, (rgs_prefix, patroon) in RELATIEREKENINGEN.items():
        masker, _ = _selecteer(af.lines, rgs_prefix, patroon, rekeningtype="B")
        regels = af.lines[masker]
        if regels.empty:
            continue
        sleutel = regels["line_custSupID"].astype(str).str.strip()
        for relatie, bedrag in regels.groupby(sleutel)["bedrag"].sum().items():
            if relatie:
                mutaties[(soort, str(relatie))] = float(bedrag)
    return mutaties


def build_relatiesaldi(af: Auditfile) -> pd.DataFrame:
    """Per relatie de openstaande stand, het verloop en wat daaraan opvalt.

    Twee signalen. Het eerste is een onlogisch teken: een debiteur met een
    creditsaldo is een vooruitbetaling of een niet-verwerkte creditnota, een
    crediteur met een debetsaldo een vooruitbetaling of een dubbele betaling.
    Het tweede is een verloop dat niet sluit: beginstand plus de mutaties van het
    jaar hoort de eindstand te geven. Wijkt dat af, dan is de stand uit het
    bestand niet uit het grootboek af te leiden en verdient zij geen vertrouwen.
    """
    if not heeft_relatiesaldi(af):
        return pd.DataFrame(columns=SALDO_COLUMNS)

    mutaties = _mutaties_per_relatie(af)
    rijen = []
    for _, relatie in af.relations.iterrows():
        begin = relatie.get("openstaand_begin")
        eind = relatie.get("openstaand_eind")
        if pd.isna(begin) and pd.isna(eind):
            continue
        soort = _soort_van_relatie(relatie)
        identificatie = str(relatie.get("custSupID", "")).strip()
        mutatie = mutaties.get((soort, identificatie)) if soort else None
        if mutatie is None or pd.isna(eind):
            verschil = float("nan")
        else:
            verwacht = (0.0 if pd.isna(begin) else float(begin)) + mutatie
            verschil = float(eind) - verwacht
        rijen.append(
            {
                "relatie": identificatie,
                "naam": str(relatie.get("custSupName", "")).strip(),
                "soort": soort,
                "openstaand_begin": float(begin) if pd.notna(begin) else float("nan"),
                "mutatie_boekjaar": float("nan") if mutatie is None else mutatie,
                "openstaand_eind": float(eind) if pd.notna(eind) else float("nan"),
                "verloop_verschil": verschil,
                "signaal": _relatiesignaal(soort, eind, verschil),
            }
        )

    if not rijen:
        return pd.DataFrame(columns=SALDO_COLUMNS)
    saldi = pd.DataFrame(rijen, columns=SALDO_COLUMNS)
    volgorde = saldi["openstaand_eind"].abs().sort_values(ascending=False, na_position="last")
    return saldi.reindex(volgorde.index).reset_index(drop=True)


def _relatiesignaal(soort: str, eind, verschil) -> str:
    signalen = []
    if pd.notna(eind) and abs(float(eind)) > TOLERANTIE:
        if soort == "debiteur" and float(eind) < 0:
            signalen.append("Debiteur met een creditsaldo; vooruitbetaling of creditnota?")
        elif soort == "crediteur" and float(eind) > 0:
            signalen.append("Crediteur met een debetsaldo; vooruitbetaling of dubbele betaling?")
    if pd.notna(verschil) and abs(float(verschil)) > TOLERANTIE:
        signalen.append(
            "Beginstand plus de mutaties van het jaar geeft niet de eindstand uit het bestand."
        )
    return " ".join(signalen)


def build_relatiesaldo_aansluiting(af: Auditfile) -> pd.DataFrame:
    """Telt de subadministratie op tot het saldo van de relatierekening?

    Per soort één regel: het saldo van de debiteuren- of crediteurenrekening
    tegenover de som van de openstaande bedragen per relatie, bij begin en einde
    van het boekjaar. De rekeningen worden op RGS-code geselecteerd met de
    omschrijving als terugval, zoals overal in deze tool; de gebruikte methode
    staat in de tabel zodat zichtbaar blijft waarop de vergelijking rust.

    Leeg zolang het bestand geen openstaande bedragen per relatie geeft. Nul
    tegenover een grootboeksaldo zetten zou een verschil tonen dat alleen bestaat
    omdat het gegeven ontbreekt.
    """
    if not heeft_relatiesaldi(af):
        return pd.DataFrame(columns=AANSLUITING_COLUMNS)

    saldi = build_relatiesaldi(af)
    rijen = []
    for soort, (rgs_prefix, patroon) in RELATIEREKENINGEN.items():
        if af.saldo.empty:
            masker = pd.Series(dtype=bool)
            methode = "geen grootboeksaldi"
        else:
            masker, methode = _selecteer(af.saldo, rgs_prefix, patroon, rekeningtype="B")
        rekeningen = int(masker.sum()) if len(masker) else 0
        eigen = saldi[saldi["soort"] == soort] if not saldi.empty else saldi

        if rekeningen:
            grootboek_begin = float(af.saldo.loc[masker, "beginsaldo"].sum())
            grootboek_eind = float(af.saldo.loc[masker, "eindsaldo"].sum())
        else:
            grootboek_begin = float("nan")
            grootboek_eind = float("nan")
            methode = f"geen {soort}enrekening herkend"

        openstaand_begin = (
            float(eigen["openstaand_begin"].sum(min_count=1)) if not eigen.empty else float("nan")
        )
        openstaand_eind = (
            float(eigen["openstaand_eind"].sum(min_count=1)) if not eigen.empty else float("nan")
        )
        verschil_begin = grootboek_begin - openstaand_begin
        verschil_eind = grootboek_eind - openstaand_eind

        rijen.append(
            {
                "soort": soort,
                "methode": methode,
                "rekeningen": rekeningen,
                "aantal_relaties": len(eigen),
                "grootboek_beginsaldo": grootboek_begin,
                "openstaand_begin": openstaand_begin,
                "verschil_begin": verschil_begin,
                "grootboek_eindsaldo": grootboek_eind,
                "openstaand_eind": openstaand_eind,
                "verschil_eind": verschil_eind,
                "signaal": _aansluitsignaal(verschil_eind),
                "conclusie": _aansluitconclusie(soort, rekeningen, len(eigen), verschil_eind),
            }
        )
    return pd.DataFrame(rijen, columns=AANSLUITING_COLUMNS)


def _aansluitsignaal(verschil_eind) -> str:
    if pd.isna(verschil_eind):
        return "niet mogelijk"
    return "" if abs(float(verschil_eind)) <= TOLERANTIE else "verschil"


def _aansluitconclusie(soort: str, rekeningen: int, relaties: int, verschil_eind) -> str:
    if not rekeningen:
        return (
            f"Geen {soort}enrekening herkend in het rekeningschema, dus er is niets om de "
            "openstaande bedragen tegenover te zetten."
        )
    if not relaties:
        return (
            f"Geen enkele relatie is als {soort} in te delen. Zonder custSupTp en zonder stand "
            "valt niet vast te stellen welke relaties bij deze rekening horen."
        )
    if pd.isna(verschil_eind):
        return "De eindstand ontbreekt bij deze relaties, dus de aansluiting is niet te maken."
    if abs(float(verschil_eind)) <= TOLERANTIE:
        meervoud = soort if relaties == 1 else f"{soort}en"
        return (
            f"De openstaande bedragen van {relaties} {meervoud} tellen op tot het saldo van de "
            f"{soort}enrekening."
        )
    return (
        f"Het saldo van de {soort}enrekening en de som van de openstaande bedragen lopen "
        f"{abs(float(verschil_eind)):.2f} uiteen. Beoordeel wat er op de rekening staat dat niet "
        "aan een relatie hangt, of welke relatie in het bestand ontbreekt."
    )
