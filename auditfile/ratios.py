"""Ratio-analyse jaar op jaar: brutomarge, personeelsquote, solvabiliteit en liquiditeit.

Wat hier moeilijk is, is niet de breuk maar de afbakening. Een ratio is pas
bruikbaar als navolgbaar is welke rekeningen in de teller en de noemer zitten en
hoe die zijn aangewezen. Daarom staat naast elke uitkomst een opbouw met per
bouwsteen het bedrag, het aantal rekeningen en de gebruikte methode, en zegt de
tool dat een ratio niet mogelijk is zodra de grondslag ontbreekt of de indeling
te weinig van de balans dekt.

Over de brede RGS-voorvoegsels
------------------------------
``BVor`` als *debiteuren* en ``BSch`` als *crediteuren* is te ruim; dat staat als
openstaand punt in de roadmap. Voor een liquiditeitsratio is diezelfde breedte
juist wat nodig is: RGS zet de vlottende vorderingen onder ``BVor`` en de
langlopende onder ``BFva``, en ``BSch`` is per definitie de kortlopende schuld.
De rubrieken worden hier dus gebruikt waarvoor ze bedoeld zijn en niet als
benadering van een enkele post.

Wat de tool niet doet
---------------------
Geen normwaarden en geen branchevergelijking. Of een solvabiliteit van 18% laag
is, hangt af van de sector, de financieringsvorm en de levensfase, en die kennis
zit niet in een auditfile. Gesignaleerd wordt daarom alleen wat feitelijk is
vast te stellen: een verschuiving tussen twee jaren boven een werkafspraak, een
negatief eigen vermogen en kortlopende schulden die de vlottende activa
overtreffen.

Het teken van de bedragen
-------------------------
In het model is een bedrag getekend: debet positief. Hier worden de bouwstenen
gepresenteerd zoals in een jaarrekening, dus omzet, eigen vermogen en schulden
positief. Het teken per groep staat in ``BALANSGROEPEN`` en ``RESULTAATGROEPEN``.
Een rekening volgt haar eigen rubriek: een bankrekening met een creditstand
verlaagt de liquide middelen en wordt niet naar de schulden verplaatst. Dat is
in de opbouw per rekening terug te zien.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .controls import _selecteer
from .findings import IN_ORDE, NIET_MOGELIJK, SIGNAAL, WAARSCHUWING
from .model import Auditfile
from .notatie import getal, procent

TOLERANTIE = 0.01

# Onder deze dekking van de balansindeling geeft de tool geen balansratio. Een
# solvabiliteit waarvan een tiende van de balans niet is ingedeeld, valt niet te
# verdedigen: in dat niet-ingedeelde deel kan eigen vermogen zitten.
MINIMALE_DEKKING = 0.90

# Werkafspraken, geen normen. Ze bepalen alleen wanneer een verschuiving het
# melden waard is; de beoordeling blijft aan de gebruiker.
VERSCHUIVING_MARGE_PP = 5.0
VERSCHUIVING_QUOTE_PP = 5.0
DALING_SOLVABILITEIT_PP = 10.0
LIQUIDITEIT_ONDERGRENS = 1.0

# De omzetrubriek staat hier omdat meer dan één plaats in de tool haar nodig
# heeft. Eén definitie, anders rekent de materialiteit met een andere omzet dan
# de brutomarge.
OMZET_RGS: tuple[str, ...] = ("WOmz",)
# De uitsluiting vooraf is nodig omdat het woord "omzet" ook in een
# kostenrekening staat: "Inkoopwaarde van de omzet" is geen opbrengst, en zonder
# RGS-code is de omschrijving het enige waarop de tool kan afgaan. Zonder die
# uitsluiting zou zo'n rekening de omzet verlagen en de brutomarge onbruikbaar
# maken. Hetzelfde geldt voor "Verkoopkosten".
OMZET_PATROON = (
    r"^(?!.*(?:inkoop|kostprijs|verbruik|kosten))"
    r".*(?:omzet|opbrengst|verkoop|provisie|\brevenue\b)"
)

# Per groep: naam, RGS-voorvoegsels, omschrijvingspatroon als terugval, en het
# teken waarmee het getekende saldo naar een gepresenteerd bedrag gaat.
#
# De volgorde telt: een rekening valt in de eerste groep die haar aanwijst. Dat
# is nodig omdat de omschrijvingsterugval kan overlappen, bijvoorbeeld bij
# "Te vorderen omzetbelasting", dat zowel op een vordering als op een
# belastingschuld lijkt. Bij een rekening met een RGS-code speelt dat niet: die
# valt maar in één rubriek.
BALANSGROEPEN: tuple[tuple[str, tuple[str, ...], str, int], ...] = (
    (
        "Vaste activa",
        ("BIva", "BMva", "BVas", "BFva"),
        r"goodwill|deelneming|inventaris|machine|gebouw|bedrijfspand|verbouwing|"
        r"installatie|transportmiddel|vaste activa",
        1,
    ),
    (
        "Vlottende activa",
        ("BVrd", "BPro", "BVor", "BEff", "BLim"),
        r"voorraad|onderhanden|debiteur|vordering|te vorderen|overlopende activa|"
        r"vooruitbetaald|effect|\bbank\b|\bkas\b|giro|liquide",
        1,
    ),
    (
        "Eigen vermogen",
        ("BEiv",),
        r"eigen vermogen|kapitaal|reserve|onverdeeld|winstsaldo|resultaat.*boekjaar|agio",
        -1,
    ),
    ("Voorzieningen", ("BVrz",), r"voorziening", -1),
    (
        "Langlopende schulden",
        ("BLas",),
        r"langlopend|hypothe|lening o/?g|onderhandse lening",
        -1,
    ),
    (
        "Kortlopende schulden",
        ("BSch",),
        r"crediteur|leverancier|kortlopend|nog te betalen|te betalen|overlopende passiva|"
        r"vooruitontvangen|omzetbelasting|loonheffing|belastingen en premies",
        -1,
    ),
)

# De voorraad apart, voor de quick ratio. Deze rekeningen zitten ook in
# "Vlottende activa"; dit is een uitsplitsing en geen eigen groep.
VOORRAAD_RGS: tuple[str, ...] = ("BVrd",)
VOORRAAD_PATROON = r"voorraad|inventory|grond.*hulpstof|handelsgoederen"

# De kostprijs staat voor de omzet: zij is de specifiekere groep, en bij een
# schema zonder RGS-codes beslist de eerste groep die een rekening herkent.
RESULTAATGROEPEN: tuple[tuple[str, tuple[str, ...], str, int], ...] = (
    (
        "Kostprijs van de omzet",
        ("WKpr",),
        r"kostprijs|inkoopwaarde|inkoop.*omzet|cost of (?:goods|sales)",
        1,
    ),
    (
        "Personeelskosten",
        ("WPer",),
        r"loon|salaris|personeel|sociale lasten|pensioenpremie|vakantiegeld|uitzendkracht",
        1,
    ),
    ("Netto-omzet", OMZET_RGS, OMZET_PATROON, -1),
)

OPBOUW_COLUMNS = ["bouwsteen", "bron", "methode", "aantal_rekeningen", "bedrag", "toelichting"]

RATIO_COLUMNS = [
    "ratio",
    "eenheid",
    "waarde_vorig",
    "waarde_huidig",
    "verschuiving",
    "teller_bedrag",
    "noemer_bedrag",
    "ernst",
    "methode",
    "signaal",
    "definitie",
]


@dataclass(frozen=True)
class Groep:
    """Eén bouwsteen van een ratio, zoals gemeten in één auditfile."""

    naam: str
    bedrag: float | None
    aantal: int
    methode: str


@dataclass(frozen=True)
class Grootheden:
    """Alles wat uit één auditfile nodig is om de ratio's te berekenen.

    Een bedrag is ``None`` wanneer de bijbehorende groep geen enkele rekening
    heeft opgeleverd. Dat is iets anders dan nul: nul is een gemeten stand, en
    ``None`` betekent dat er niets te meten viel.
    """

    groepen: dict[str, Groep] = field(default_factory=dict)
    resultaat: float = 0.0
    # True als het resultaat van het boekjaar al op de balans staat, False als
    # het er nog buiten staat, None als geen van beide uit de balans blijkt.
    resultaat_verwerkt: bool | None = None
    balanstotaal: float = 0.0
    dekking: float = 0.0
    niet_ingedeeld: float = 0.0
    aantal_resultaatrekeningen: int = 0

    def bedrag(self, naam: str) -> float | None:
        groep = self.groepen.get(naam)
        return None if groep is None else groep.bedrag

    def methode(self, *namen: str) -> str:
        """De methoden achter de gebruikte bouwstenen, samengevat tot één woord."""
        gebruikt: list[str] = []
        for naam in namen:
            groep = self.groepen.get(naam)
            if groep is None or groep.methode == "geen treffers":
                continue
            if groep.methode not in gebruikt:
                gebruikt.append(groep.methode)
        if not gebruikt:
            return "geen treffers"
        if len(gebruikt) == 1:
            return gebruikt[0]
        if all(methode == "RGS-code" for methode in gebruikt):
            return "RGS-code"
        return "RGS-code en omschrijving"

    @property
    def eigen_vermogen(self) -> float | None:
        """Het eigen vermogen inclusief het resultaat dat nog niet is bestemd.

        Een auditfile is doorgaans opgemaakt voordat het resultaat is bestemd.
        Het eigen vermogen op de balans is dan te laag met precies het resultaat
        van het boekjaar. Of dat zo is, wordt niet aangenomen maar gemeten; zie
        ``resultaat_verwerkt``.
        """
        op_balans = self.bedrag("Eigen vermogen")
        if op_balans is None or self.resultaat_verwerkt is None:
            return None
        if self.resultaat_verwerkt:
            return op_balans
        return op_balans + self.resultaat


def _deel_in(
    saldo: pd.DataFrame,
    groepen: tuple[tuple[str, tuple[str, ...], str, int], ...],
    rekeningtype: str,
) -> tuple[pd.Series, dict[str, Groep]]:
    """Wijs elke rekening toe aan de eerste groep die haar herkent."""
    toewijzing = pd.Series("", index=saldo.index, dtype=object)
    gemeten: dict[str, Groep] = {}
    for naam, prefixen, patroon, teken in groepen:
        vrij = saldo[toewijzing == ""]
        if vrij.empty:
            gemeten[naam] = Groep(naam, None, 0, "geen treffers")
            continue
        masker, methode = _selecteer(vrij, prefixen, patroon, rekeningtype=rekeningtype)
        gekozen = masker[masker].index
        if len(gekozen) == 0:
            gemeten[naam] = Groep(naam, None, 0, methode)
            continue
        toewijzing.loc[gekozen] = naam
        bedrag = teken * float(saldo.loc[gekozen, "saldo"].sum())
        gemeten[naam] = Groep(naam, bedrag, len(gekozen), methode)
    return toewijzing, gemeten


def meet(af: Auditfile) -> Grootheden:
    """De bouwstenen van de ratio's, gemeten in één auditfile."""
    if af.saldo.empty:
        return Grootheden()

    saldo = af.saldo.copy()
    saldo["saldo"] = pd.to_numeric(saldo["saldo"], errors="coerce").fillna(0.0)
    soort = saldo["accTp"].astype(str).str.strip().str.upper()
    balans = saldo[soort.eq("B")]
    resultaatrekeningen = saldo[soort.eq("P")]

    _, resultaatgroepen = _deel_in(resultaatrekeningen, RESULTAATGROEPEN, "P")
    toewijzing, balansgroepen = _deel_in(balans, BALANSGROEPEN, "B")
    groepen = {**resultaatgroepen, **balansgroepen}

    # De voorraad is een uitsplitsing binnen de vlottende activa en geen eigen
    # groep: ze mag niet twee keer in het balanstotaal terechtkomen. Alleen wat
    # ook werkelijk als vlottend is ingedeeld telt mee, anders zou een
    # voorraadrekening die buiten de indeling valt de quick ratio verhogen.
    if balans.empty:
        groepen["Voorraden"] = Groep("Voorraden", None, 0, "geen treffers")
    else:
        voorraad, voorraadmethode = _selecteer(
            balans, VOORRAAD_RGS, VOORRAAD_PATROON, rekeningtype="B"
        )
        voorraad &= toewijzing.eq("Vlottende activa")
        aantal = int(voorraad.sum())
        groepen["Voorraden"] = Groep(
            "Voorraden",
            float(balans.loc[voorraad, "saldo"].sum()) if aantal else None,
            aantal,
            voorraadmethode if aantal else "geen treffers",
        )

    resultaat = -float(resultaatrekeningen["saldo"].sum())
    som_balans = float(balans["saldo"].sum())
    if abs(som_balans) <= TOLERANTIE:
        resultaat_verwerkt: bool | None = True
    elif abs(som_balans - resultaat) <= TOLERANTIE:
        resultaat_verwerkt = False
    else:
        resultaat_verwerkt = None

    balanstotaal = float(balans.loc[balans["saldo"] > 0, "saldo"].sum())
    totaal_absoluut = float(balans["saldo"].abs().sum())
    niet_ingedeeld = float(balans.loc[toewijzing.eq(""), "saldo"].abs().sum())
    dekking = 1.0 - niet_ingedeeld / totaal_absoluut if totaal_absoluut > TOLERANTIE else 0.0

    return Grootheden(
        groepen=groepen,
        resultaat=resultaat,
        resultaat_verwerkt=resultaat_verwerkt,
        balanstotaal=balanstotaal,
        dekking=dekking,
        niet_ingedeeld=niet_ingedeeld,
        aantal_resultaatrekeningen=len(resultaatrekeningen),
    )


def build_ratio_opbouw(af: Auditfile) -> pd.DataFrame:
    """De bouwstenen achter de ratio's, met per regel de bron.

    Dezelfde vorm als de opbouw van de drempeltoets excessief lenen: wie de
    uitkomst wil narekenen, moet kunnen zien waar elk bedrag vandaan komt.
    """
    grootheden = meet(af)
    if not grootheden.groepen:
        return pd.DataFrame(columns=OPBOUW_COLUMNS)

    def uit_groep(naam: str, toelichting: str) -> dict:
        groep = grootheden.groepen.get(naam)
        return {
            "bouwsteen": naam,
            "bron": "auditfile",
            "methode": groep.methode if groep else "geen treffers",
            "aantal_rekeningen": groep.aantal if groep else 0,
            "bedrag": groep.bedrag if groep else None,
            "toelichting": toelichting,
        }

    if grootheden.resultaat_verwerkt is None:
        bestemming_bedrag: float | None = None
        bestemming_toelichting = (
            "De balans telt niet op tot nul en ook niet tot het resultaat van het "
            "boekjaar. Of het resultaat al in het eigen vermogen zit, is daarmee niet "
            "vast te stellen."
        )
    elif grootheden.resultaat_verwerkt:
        bestemming_bedrag = 0.0
        bestemming_toelichting = "Het resultaat staat al op de balans; er wordt niets bijgeteld."
    else:
        bestemming_bedrag = grootheden.resultaat
        bestemming_toelichting = (
            "Het resultaat staat nog niet op de balans en wordt bij het eigen vermogen "
            "geteld. Zonder die bijtelling zou de solvabiliteit te laag uitkomen."
        )

    rijen = [
        uit_groep("Netto-omzet", "Grondslag van de brutomarge en van de personeelsquote."),
        uit_groep(
            "Kostprijs van de omzet", "Zonder deze rubriek is er geen brutomarge te bepalen."
        ),
        uit_groep(
            "Personeelskosten", "Inclusief sociale lasten, pensioen en ingeleend personeel."
        ),
        {
            "bouwsteen": "Resultaat boekjaar",
            "bron": "berekend",
            "methode": "som van de resultaatrekeningen",
            "aantal_rekeningen": grootheden.aantal_resultaatrekeningen,
            "bedrag": grootheden.resultaat,
            "toelichting": (
                "Winst positief: het tegengestelde van de som van de mutaties op de "
                "resultaatrekeningen."
            ),
        },
        uit_groep("Vaste activa", "Immaterieel, materieel, vastgoedbeleggingen en financieel."),
        uit_groep(
            "Vlottende activa",
            "Voorraden, onderhanden projecten, vorderingen, effecten en liquide middelen.",
        ),
        uit_groep("Voorraden", "Uitsplitsing binnen de vlottende activa, voor de quick ratio."),
        uit_groep(
            "Eigen vermogen", "Zoals het op de balans staat, dus zonder het resultaat van dit jaar."
        ),
        uit_groep("Voorzieningen", ""),
        uit_groep("Langlopende schulden", ""),
        uit_groep("Kortlopende schulden", "Noemer van de current ratio en de quick ratio."),
        {
            "bouwsteen": "Resultaat nog niet bestemd",
            "bron": "berekend",
            "methode": "balanstelling",
            "aantal_rekeningen": 0,
            "bedrag": bestemming_bedrag,
            "toelichting": bestemming_toelichting,
        },
        {
            "bouwsteen": "Eigen vermogen voor de toets",
            "bron": "berekend",
            "methode": "",
            "aantal_rekeningen": 0,
            "bedrag": grootheden.eigen_vermogen,
            "toelichting": "Teller van de solvabiliteit.",
        },
        {
            "bouwsteen": "Balanstotaal",
            "bron": "berekend",
            "methode": "som van de debetzijde",
            "aantal_rekeningen": 0,
            "bedrag": grootheden.balanstotaal,
            "toelichting": (
                "De som van de balansrekeningen die debet staan. Bewust niet de som van "
                "een lijst activarubrieken, want die lijst kan onvolledig zijn."
            ),
        },
        {
            "bouwsteen": "Niet ingedeeld",
            "bron": "berekend",
            "methode": "",
            "aantal_rekeningen": 0,
            "bedrag": grootheden.niet_ingedeeld,
            "toelichting": (
                f"Balansrekeningen die in geen enkele rubriek vallen. De indeling dekt "
                f"{procent(grootheden.dekking * 100)} van de balans; onder "
                f"{MINIMALE_DEKKING * 100:.0f}% geeft de tool geen balansratio."
            ),
        },
    ]
    return pd.DataFrame(rijen, columns=OPBOUW_COLUMNS)


# --- De ratio's zelf --------------------------------------------------------


@dataclass(frozen=True)
class Uitkomst:
    """Eén ratio in één jaar: de waarde, of de reden waarom die er niet is."""

    waarde: float | None = None
    teller: float | None = None
    noemer: float | None = None
    reden: str = ""


def _balans_bruikbaar(grootheden: Grootheden) -> str:
    """De reden waarom een balansratio niet kan, of een lege tekst."""
    if grootheden.balanstotaal <= TOLERANTIE:
        return "Er zijn geen balansrekeningen met een debetsaldo; het balanstotaal is nul."
    if grootheden.dekking < MINIMALE_DEKKING:
        return (
            f"De rubrieksindeling dekt {procent(grootheden.dekking * 100)} van de balans, minder "
            f"dan de vereiste {MINIMALE_DEKKING * 100:.0f}%. In het niet-ingedeelde deel kan "
            "eigen vermogen of een kortlopende schuld zitten."
        )
    return ""


def _brutomarge(grootheden: Grootheden) -> Uitkomst:
    omzet = grootheden.bedrag("Netto-omzet")
    kostprijs = grootheden.bedrag("Kostprijs van de omzet")
    if omzet is None or omzet <= TOLERANTIE:
        return Uitkomst(reden="Er is geen omzetrekening met een creditsaldo gevonden.")
    if kostprijs is None:
        return Uitkomst(
            reden=(
                "Er is geen rekening voor de kostprijs van de omzet gevonden. Een marge van "
                "100% zou hier het gevolg zijn van een ontbrekende rubriek en niet van de "
                "cijfers."
            )
        )
    return Uitkomst(waarde=(omzet - kostprijs) / omzet * 100.0, teller=omzet - kostprijs, noemer=omzet)


def _personeelsquote(grootheden: Grootheden) -> Uitkomst:
    omzet = grootheden.bedrag("Netto-omzet")
    personeel = grootheden.bedrag("Personeelskosten")
    if omzet is None or omzet <= TOLERANTIE:
        return Uitkomst(reden="Er is geen omzetrekening met een creditsaldo gevonden.")
    if personeel is None:
        return Uitkomst(reden="Er is geen personeelskostenrekening gevonden.")
    return Uitkomst(waarde=personeel / omzet * 100.0, teller=personeel, noemer=omzet)


def _solvabiliteit(grootheden: Grootheden) -> Uitkomst:
    belet = _balans_bruikbaar(grootheden)
    if belet:
        return Uitkomst(reden=belet)
    if grootheden.resultaat_verwerkt is None:
        return Uitkomst(
            reden=(
                "De balans telt niet op tot nul en ook niet tot het resultaat van het "
                "boekjaar, dus of het resultaat al in het eigen vermogen zit is niet vast "
                "te stellen."
            )
        )
    eigen_vermogen = grootheden.eigen_vermogen
    if eigen_vermogen is None:
        return Uitkomst(reden="Er is geen rekening voor het eigen vermogen gevonden.")
    return Uitkomst(
        waarde=eigen_vermogen / grootheden.balanstotaal * 100.0,
        teller=eigen_vermogen,
        noemer=grootheden.balanstotaal,
    )


def _liquiditeit(grootheden: Grootheden, met_voorraad: bool) -> Uitkomst:
    belet = _balans_bruikbaar(grootheden)
    if belet:
        return Uitkomst(reden=belet)
    vlottend = grootheden.bedrag("Vlottende activa")
    kortlopend = grootheden.bedrag("Kortlopende schulden")
    if vlottend is None:
        return Uitkomst(reden="Er zijn geen vlottende activa herkend.")
    if kortlopend is None or abs(kortlopend) <= TOLERANTIE:
        return Uitkomst(reden="Er zijn geen kortlopende schulden herkend; delen door nul kan niet.")
    teller = vlottend
    if not met_voorraad:
        teller = vlottend - (grootheden.bedrag("Voorraden") or 0.0)
    return Uitkomst(waarde=teller / kortlopend, teller=teller, noemer=kortlopend)


def _verschuiving(huidig: Uitkomst, vorig: Uitkomst | None) -> float | None:
    if vorig is None or huidig.waarde is None or vorig.waarde is None:
        return None
    return huidig.waarde - vorig.waarde


def _beoordeel_brutomarge(uit: Uitkomst, verschuiving: float | None) -> tuple[str, str]:
    if verschuiving is None or abs(verschuiving) < VERSCHUIVING_MARGE_PP:
        return IN_ORDE, ""
    richting = "gestegen" if verschuiving > 0 else "gedaald"
    return SIGNAAL, (
        f"De brutomarge is met {getal(abs(verschuiving), 1)} procentpunt {richting}. Beoordeel "
        "de prijsstelling, de inkoopwaarde en de voorraadwaardering, en of de afgrenzing "
        "van kostprijs en overige kosten tussen beide jaren gelijk is."
    )


def _beoordeel_quote(uit: Uitkomst, verschuiving: float | None) -> tuple[str, str]:
    if verschuiving is None or abs(verschuiving) < VERSCHUIVING_QUOTE_PP:
        return IN_ORDE, ""
    richting = "gestegen" if verschuiving > 0 else "gedaald"
    return SIGNAAL, (
        f"De personeelskosten als deel van de omzet zijn met {getal(abs(verschuiving), 1)} "
        f"procentpunt {richting}. Beoordeel de aansluiting op de salarisadministratie en de "
        "verhouding tussen eigen personeel en inleen."
    )


def _beoordeel_solvabiliteit(uit: Uitkomst, verschuiving: float | None) -> tuple[str, str]:
    if uit.teller is not None and uit.teller < -TOLERANTIE:
        return WAARSCHUWING, (
            "Het eigen vermogen is negatief. Beoordeel de continuiteitsveronderstelling, de "
            "ruimte voor uitkeringen en of een toelichting nodig is."
        )
    if verschuiving is not None and verschuiving <= -DALING_SOLVABILITEIT_PP:
        return SIGNAAL, (
            f"De solvabiliteit is met {getal(abs(verschuiving), 1)} procentpunt gedaald. Beoordeel "
            "waar dat vandaan komt: het resultaat, een uitkering of een toename van de "
            "schulden."
        )
    return IN_ORDE, ""


def _beoordeel_current(uit: Uitkomst, verschuiving: float | None) -> tuple[str, str]:
    if uit.waarde is not None and uit.waarde < LIQUIDITEIT_ONDERGRENS:
        return SIGNAAL, (
            "De kortlopende schulden zijn groter dan de vlottende activa. Beoordeel de "
            "continuiteitsveronderstelling en de beschikbare kredietruimte."
        )
    return IN_ORDE, ""


def build_ratios(huidig: Auditfile, vorig: Auditfile | None = None) -> pd.DataFrame:
    """De ratio's van het huidige jaar, waar mogelijk naast die van vorig jaar.

    Zonder een bestand van vorig jaar blijven de kolommen voor dat jaar leeg en
    volgt er geen signaal over een verschuiving: één jaar is geen reeks.
    """
    nu = meet(huidig)
    toen = meet(vorig) if vorig is not None else None

    huidige = {
        "Brutomarge": _brutomarge(nu),
        "Personeelskosten in % van de omzet": _personeelsquote(nu),
        "Solvabiliteit": _solvabiliteit(nu),
        "Current ratio": _liquiditeit(nu, met_voorraad=True),
        "Quick ratio": _liquiditeit(nu, met_voorraad=False),
    }
    if toen is None:
        vorige: dict[str, Uitkomst | None] = {naam: None for naam in huidige}
    else:
        vorige = {
            "Brutomarge": _brutomarge(toen),
            "Personeelskosten in % van de omzet": _personeelsquote(toen),
            "Solvabiliteit": _solvabiliteit(toen),
            "Current ratio": _liquiditeit(toen, met_voorraad=True),
            "Quick ratio": _liquiditeit(toen, met_voorraad=False),
        }

    definities = {
        "Brutomarge": "(netto-omzet - kostprijs van de omzet) / netto-omzet",
        "Personeelskosten in % van de omzet": "personeelskosten / netto-omzet",
        "Solvabiliteit": "eigen vermogen inclusief onbestemd resultaat / balanstotaal",
        "Current ratio": "vlottende activa / kortlopende schulden",
        "Quick ratio": "(vlottende activa - voorraden) / kortlopende schulden",
    }
    eenheden = {
        "Brutomarge": "%",
        "Personeelskosten in % van de omzet": "%",
        "Solvabiliteit": "%",
        "Current ratio": "x",
        "Quick ratio": "x",
    }
    methoden = {
        "Brutomarge": nu.methode("Netto-omzet", "Kostprijs van de omzet"),
        "Personeelskosten in % van de omzet": nu.methode("Netto-omzet", "Personeelskosten"),
        "Solvabiliteit": nu.methode("Eigen vermogen"),
        "Current ratio": nu.methode("Vlottende activa", "Kortlopende schulden"),
        "Quick ratio": nu.methode("Vlottende activa", "Voorraden", "Kortlopende schulden"),
    }
    beoordelaars = {
        "Brutomarge": _beoordeel_brutomarge,
        "Personeelskosten in % van de omzet": _beoordeel_quote,
        "Solvabiliteit": _beoordeel_solvabiliteit,
        "Current ratio": _beoordeel_current,
    }

    rijen = []
    for naam, uit in huidige.items():
        verschuiving = _verschuiving(uit, vorige[naam])
        if uit.waarde is None:
            ernst, signaal = NIET_MOGELIJK, uit.reden
        elif naam == "Quick ratio":
            ernst, signaal = _beoordeel_quick(uit, huidige["Current ratio"])
        else:
            ernst, signaal = beoordelaars[naam](uit, verschuiving)
        rijen.append(
            {
                "ratio": naam,
                "eenheid": eenheden[naam],
                "waarde_vorig": vorige[naam].waarde if vorige[naam] else None,
                "waarde_huidig": uit.waarde,
                "verschuiving": verschuiving,
                "teller_bedrag": uit.teller,
                "noemer_bedrag": uit.noemer,
                "ernst": ernst,
                "methode": methoden[naam],
                "signaal": signaal,
                "definitie": definities[naam],
            }
        )
    return pd.DataFrame(rijen, columns=RATIO_COLUMNS)


def _beoordeel_quick(uit: Uitkomst, current: Uitkomst) -> tuple[str, str]:
    """De quick ratio meldt alleen wat de current ratio nog niet heeft gemeld.

    Staat de current ratio al onder 1, dan is dat signaal er al; een tweede
    bevinding over dezelfde verhouding voegt niets toe.
    """
    if uit.waarde is None or uit.waarde >= LIQUIDITEIT_ONDERGRENS:
        return IN_ORDE, ""
    if current.waarde is not None and current.waarde < LIQUIDITEIT_ONDERGRENS:
        return IN_ORDE, ""
    return SIGNAAL, (
        "Zonder de voorraad dekken de vlottende activa de kortlopende schulden niet. "
        "Beoordeel de omloopsnelheid en de waardering van de voorraad."
    )
