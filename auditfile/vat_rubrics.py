"""De rubrieken van de Nederlandse aangifte omzetbelasting.

Een auditfile bevat geen aangifte. Wat er wel in zit is per boekingsregel een
btw-code met een percentage en een btw-bedrag. De brug tussen die codes en de
rubrieken van het aangifteformulier moet de tool leggen, en die brug is een
interpretatie: de omschrijving van een btw-code is vrije tekst die per
boekhoudpakket verschilt.

Daarom werkt deze module in twee lagen:

1. een *voorstel* per btw-code, met de reden erbij en hoe hard het voorstel is;
2. een *vastlegging* door de gebruiker, die het voorstel overschrijft.

Alleen de tweede laag telt mee in de eindberekening. De tool doet dus geen
uitspraak die de gebruiker niet heeft kunnen zien en corrigeren.

Bron van de rubriekindeling: het aangifteformulier omzetbelasting van de
Belastingdienst. Zie ``docs/btw-bronnen.md`` voor de vindplaatsen per rubriek.
"""
from __future__ import annotations

from dataclasses import dataclass

# Zijde in de eindtelling van de aangifte.
AFDRACHT = "afdracht"  # verhoogt de verschuldigde omzetbelasting
VOORBELASTING = "voorbelasting"  # vermindert de af te dragen omzetbelasting
INFORMATIEF = "informatief"  # alleen een grondslag, geen btw in de eindtelling


@dataclass(frozen=True)
class Rubriek:
    """Eén rubriek van het aangifteformulier."""

    code: str
    omschrijving: str
    zijde: str
    heeft_btw: bool
    toelichting: str = ""
    # Vraagt het formulier bij deze rubriek ook een bedrag waarover de
    # omzetbelasting wordt berekend? Bij alle rubrieken behalve de voorbelasting
    # is dat zo; zie de tabel in docs/btw-bronnen.md.
    heeft_grondslag: bool = True

    @property
    def label(self) -> str:
        return f"{self.code} — {self.omschrijving}"


# De volgorde en de omschrijvingen zijn die van het aangifteformulier zoals de
# Belastingdienst het voor 2025 en 2026 hanteert. Zie docs/btw-bronnen.md.
RUBRIEKEN: tuple[Rubriek, ...] = (
    Rubriek("1a", "Leveringen/diensten belast met hoog tarief", AFDRACHT, True),
    Rubriek("1b", "Leveringen/diensten belast met laag tarief", AFDRACHT, True),
    Rubriek("1c", "Leveringen/diensten belast met overige tarieven, behalve 0%", AFDRACHT, True),
    Rubriek("1d", "Privegebruik", AFDRACHT, True),
    Rubriek(
        "1e",
        "Leveringen/diensten belast met 0% of niet bij u belast",
        INFORMATIEF,
        False,
        "Hieronder valt onder meer de omzet waarbij de heffing naar een andere "
        "ondernemer is verlegd. De leverancier vermeldt alleen de omzet en draagt "
        "zelf geen btw af.",
    ),
    Rubriek(
        "2a",
        "Leveringen/diensten waarbij de btw naar u is verlegd",
        AFDRACHT,
        True,
        "De afnemer geeft de naar hem verlegde btw hier aan en telt die mee in de "
        "verschuldigde btw. Dezelfde btw is onder de gewone voorwaarden aftrekbaar "
        "en komt dan ook in rubriek 5b terug, zodat het saldo nihil is. Bij "
        "vrijgesteld gebruik vervalt die aftrek.",
    ),
    Rubriek("3a", "Leveringen naar landen buiten de EU (uitvoer)", INFORMATIEF, False),
    Rubriek(
        "3b",
        "Leveringen naar of diensten in landen binnen de EU",
        INFORMATIEF,
        False,
        "Deze omzet moet ook in de opgaaf ICP worden opgenomen.",
    ),
    Rubriek("3c", "Installatie/afstandsverkopen binnen de EU", INFORMATIEF, False),
    Rubriek(
        "4a",
        "Leveringen/diensten uit landen buiten de EU",
        AFDRACHT,
        True,
        "Onder meer invoer waarbij de heffing op grond van artikel 23 Wet OB 1968 "
        "is verlegd. De btw is onder de gewone voorwaarden aftrekbaar in 5b.",
    ),
    Rubriek(
        "4b",
        "Leveringen/diensten uit landen binnen de EU",
        AFDRACHT,
        True,
        "Intracommunautaire verwervingen en naar u verlegde diensten van "
        "EU-ondernemers. Diensten aan onroerende zaken in Nederland horen echter "
        "in rubriek 2a. De btw is onder de gewone voorwaarden aftrekbaar in 5b.",
    ),
    Rubriek(
        "5b",
        "Voorbelasting",
        VOORBELASTING,
        True,
        "De aan de onderneming in rekening gebrachte btw, inclusief de btw uit de "
        "rubrieken 2a, 4a en 4b voor zover die aftrekbaar is.",
        heeft_grondslag=False,
    ),
)

# Rubriek 5a is geen invoerveld maar het berekende subtotaal van de
# verschuldigde btw uit de rubrieken 1 tot en met 4. Het eindtotaal is 5a
# minus 5b. De oude codes 5c tot en met 5g bestaan niet meer op het formulier
# en worden hier bewust niet gebruikt.
SUBTOTAAL_CODE = "5a"
SUBTOTAAL_OMSCHRIJVING = "Verschuldigde btw (rubrieken 1 tot en met 4)"

RUBRIEK_CODES: tuple[str, ...] = tuple(rubriek.code for rubriek in RUBRIEKEN)
RUBRIEK_PER_CODE: dict[str, Rubriek] = {rubriek.code: rubriek for rubriek in RUBRIEKEN}

# Rubrieken waarvan de aangegeven btw onder de gewone voorwaarden óók als
# voorbelasting in 5b terugkomt. Het gaat om btw die de ondernemer zelf
# verschuldigd wordt in plaats van in rekening gebracht krijgt:
#
#   2a  verlegde btw, verschuldigd op grond van art. 12 lid 2 tot en met 5
#       Wet OB 1968 en aftrekbaar op grond van art. 15 lid 1 onderdeel c, 2°;
#   4a  invoer, aftrekbaar op grond van art. 15 lid 1 onderdeel c, 1°;
#   4b  intracommunautaire verwerving, aftrekbaar op grond van art. 15 lid 1
#       onderdeel b.
#
# De aftrek geldt volgens de slotzin van art. 15 lid 1 "voor zover de goederen
# en de diensten door de ondernemer worden gebruikt voor belaste handelingen".
# Dat aandeel is dus geen constante en kan de tool niet uit het auditfile
# afleiden; het staat per btw-code als invoer van de gebruiker, met 100% als
# uitgangspunt. Zie docs/btw-bronnen.md voor de vindplaatsen.
AFTREKBAAR_IN_5B: tuple[str, ...] = ("2a", "4a", "4b")

# De rubriek waarin die aftrek terechtkomt.
AFTREK_RUBRIEK = "5b"

# Uitgangspunt voor het aftrekbare aandeel: volledig aftrekbaar. Dat is het
# normale geval bij een ondernemer met uitsluitend belaste prestaties.
STANDAARD_AFTREK_PCT = 100.0

# Codes die in de eindtelling meetellen aan de afdrachtzijde respectievelijk als
# voorbelasting.
AFDRACHT_CODES: tuple[str, ...] = tuple(r.code for r in RUBRIEKEN if r.zijde == AFDRACHT)
VOORBELASTING_CODES: tuple[str, ...] = tuple(r.code for r in RUBRIEKEN if r.zijde == VOORBELASTING)

# Een btw-code die niet met zekerheid aan een rubriek is toe te wijzen.
ONBEKEND = "onbekend"

ONBEKEND_RUBRIEK = Rubriek(
    ONBEKEND,
    "Niet ingedeeld",
    INFORMATIEF,
    False,
    "Deze btw-code kon niet automatisch aan een rubriek worden gekoppeld en telt "
    "niet mee in de eindberekening zolang er geen rubriek is gekozen.",
    heeft_grondslag=False,
)


def rubriek(code: str) -> Rubriek:
    return RUBRIEK_PER_CODE.get(code, ONBEKEND_RUBRIEK)


def keuzelijst() -> list[str]:
    """Rubriekcodes zoals ze in een keuzelijst worden aangeboden."""
    return [ONBEKEND, *RUBRIEK_CODES]
