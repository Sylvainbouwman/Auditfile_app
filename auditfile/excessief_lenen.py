"""Drempeltoets bij de Wet excessief lenen bij eigen vennootschap.

Wat deze toets is
-----------------
Art. 4.14a Wet IB 2001 rekent het bovenmatige deel van de schulden van een
aanmerkelijkbelanghouder aan zijn vennootschap tot de reguliere voordelen uit
aanmerkelijk belang. Bovenmatig is het bedrag waarmee die schulden aan het einde
van het kalenderjaar het maximumbedrag overschrijden. De bedragen per peildatum
en hun vindplaatsen staan in ``docs/btw-bronnen.md``.

Wat deze toets niet is
----------------------
Het auditfile is het grootboek van de **vennootschap**; de wettelijke toets zit
bij de **belastingplichtige**. Daartussen zit een gat dat de tool niet kan
dichten en daarom benoemt:

1. **Peildatum.** De wet peilt op het einde van het kalenderjaar. Alleen bij een
   boekjaar dat op 31 december eindigt valt de balansdatum daarmee samen. Bij een
   gebroken boekjaar geeft de tool de gemeten stand wel, maar niet als toets.
2. **Meer vennootschappen, meer personen.** De schulden aan alle vennootschappen
   waarin de belastingplichtige een aanmerkelijk belang heeft tellen samen, en
   die van de partner tellen mee (lid 3). Eén auditfile ziet één vennootschap, en
   op één rekening-courant kunnen meer personen staan.
3. **Eigenwoningschuld.** Buiten beschouwing voor zover daarvoor een recht van
   hypotheek aan de vennootschap is verstrekt (lid 6), met overgangsrecht voor
   een op 31 december 2022 bestaande schuld (art. 10a.23). Of dat hypotheekrecht
   er is, staat niet in het grootboek.
4. **Verhoogd maximumbedrag.** Het maximumbedrag wordt verhoogd met eerder in
   aanmerking genomen fictief regulier voordeel, zodat hetzelfde bedrag niet
   tweemaal wordt belast. Dat is dossierkennis en geen boekingsgegeven.
5. **Wat er op de rekening staat.** Een creditstand betekent dat de vennootschap
   de aandeelhouder schuldig is; dan speelt de regeling niet.

Punt 3 en 4 komen daarom als invoer van de gebruiker terug in de opbouw, op een
eigen regel en met de bron erbij. De tool signaleert; de conclusie is aan de
gebruiker.

Welke rekeningen meetellen
--------------------------
De RGS-codes hieronder zijn de codes voor rekening-courant en leningen met
aandeelhouders en bestuurders. Commissarissen en "overigen" vallen er bewust
buiten: die zijn niet uit hoofde van die rol aanmerkelijkbelanghouder, en een
lening aan een commissaris in de toets betrekken zou het bedrag te hoog maken.
De keerzijde is dat een rekening-courant met de dga die als "overigen" is
gecodeerd buiten de selectie valt. Daarom staat naast de toets
``build_afwijkende_codering()``: rekeningen waarvan de omschrijving op een
rekening-courant wijst terwijl de RGS-code ze uitsluit. Dat is een signaal over
de codering en geen correctie op het bedrag.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .controls import _selecteer
from .findings import NIET_MOGELIJK, SIGNAAL, WAARSCHUWING
from .model import Auditfile

TOLERANTIE = 0.005

# Maximumbedrag per peildatum 31 december. Vindplaatsen in
# docs/btw-bronnen.md, sectie "Drempel excessief lenen"; grondslag art. 4.14a
# lid 2 Wet IB 2001. Het bedrag wordt niet geïndexeerd: art. 4.14a komt niet
# voor in de opsomming van art. 10.1 Wet IB 2001, dus een nieuw jaar krijgt niet
# vanzelf een nieuw bedrag.
MAXIMUMBEDRAGEN: dict[int, float] = {
    # Invoering op € 700.000: Stb. 2022, 531.
    2023: 700_000.0,
    # Verlaging naar € 500.000 per 1 januari 2024: Belastingplan 2024,
    # Stb. 2023, 499, artikel I onderdeel 0A.
    2024: 500_000.0,
    2025: 500_000.0,
    2026: 500_000.0,
}

# Het eerste jaar waarin de regeling geldt. Voor eerdere peildata bestaat er
# geen drempel en is er dus niets te toetsen.
EERSTE_JAAR = 2023

# Het laatste jaar waarvoor een bedrag is vastgesteld. Voor een later jaar geeft
# de tool geen bedrag: doorschrijven van het laatst bekende bedrag zou een
# aanname zijn die als vaststelling wordt gelezen.
LAATSTE_JAAR = max(MAXIMUMBEDRAGEN)

# Het bedrag per de laatste peildatum staat nog onder voorbehoud van het
# Belastingplan van het jaar daarna.
VOORBEHOUD_JAAR = LAATSTE_JAAR

# RGS-codes voor rekening-courant en leningen met aandeelhouders en bestuurders.
# Verwijzing: het Referentie Grootboekschema, zoals ontsloten via
# boekhoudplaza.nl/wiki_uitleg/210 (rekening-courant) en /53 (leningen).
RGS_VOORVOEGSELS: tuple[str, ...] = (
    "BVorOvrRca",  # Rekening-courant aandeelhouders (kortlopend)
    "BVorOvrRcb",  # Rekening-courant bestuurders (kortlopend)
    "BVorOvrLvb",  # Leningen, voorschotten en garanties bestuurders (kortlopend)
    "BFvaOvrHva",  # Leningen en voorschotten aandeelhouders (langlopend)
    "BFvaOvrVob",  # Leningen, voorschotten e.d. bestuurders (langlopend)
    "BFvaOvrVoa",  # Aflossing van die leningen; hoort bij dezelfde vordering
)

# Terugval voor rekeningen zonder RGS-code. Ruimer dan het patroon in
# FISCALE_SIGNALEN, omdat hier ook de leningvarianten en de gangbare afkortingen
# mee moeten komen.
OMSCHRIJVING_PATROON = (
    r"rekening.courant|\br/?c\b|"
    r"(?:lening|voorschot|vordering).*(?:dga|directie|directeur|bestuurder|aandeelhouder)|"
    r"(?:dga|directie|directeur|bestuurder|aandeelhouder).*(?:lening|voorschot|vordering)"
)

# Onder deze verhouding tot het maximumbedrag volgt geen signaal. Een stand die
# de drempel bijna raakt is het melden waard, omdat één opname in december haar
# overschrijdt. Dit is een werkafspraak en geen norm uit de wet.
NABIJ_AANDEEL = 0.9

REKENING_COLUMNS = ["rekening", "omschrijving", "RGScode", "methode", "eindsaldo"]
OPBOUW_COLUMNS = ["onderdeel", "bron", "bedrag", "toelichting"]
AFWIJKING_COLUMNS = ["rekening", "omschrijving", "RGScode", "eindsaldo", "signaal"]

# De uitkomsten die de toets kan hebben.
STATUS_GEEN_REKENING = "geen rekening gevonden"
STATUS_NIET_MOGELIJK = "niet mogelijk"
STATUS_GEEN_SCHULD = "geen schuld aan de vennootschap"
STATUS_ONDER = "onder de drempel"
STATUS_NABIJ = "nabij de drempel"
STATUS_BOVEN = "boven de drempel"


@dataclass(frozen=True)
class Invoer:
    """Wat de gebruiker toevoegt aan wat het auditfile zegt.

    Alle drie de bedragen zijn dossierkennis die niet in een grootboek staat.
    Ze zijn nul zolang de gebruiker niets invult, en dat is geen vaststelling
    dat ze nul zijn: de opbouw laat de regel zien met de bron ``gebruiker``.
    """

    # Art. 4.14a lid 6: buiten beschouwing voor zover er een recht van hypotheek
    # aan de vennootschap is verstrekt. Vermindert de te toetsen schuld.
    eigenwoningschuld: float = 0.0
    # Schulden aan andere vennootschappen waarin een aanmerkelijk belang wordt
    # gehouden, en schulden van de partner (lid 3). Verhoogt de te toetsen schuld.
    andere_vennootschappen: float = 0.0
    # Art. 4.14a lid 2: eerder in aanmerking genomen fictief regulier voordeel
    # verhoogt het maximumbedrag.
    eerder_belast_voordeel: float = 0.0


@dataclass(frozen=True)
class Peildatum:
    """De peildatum van de toets, en of de balansdatum die kan zijn."""

    datum: pd.Timestamp | None
    jaar: int | None
    geldig: bool
    toelichting: str


@dataclass(frozen=True)
class Toets:
    """De uitkomst van de drempeltoets, los van hoe zij wordt getoond."""

    status: str
    peildatum: Peildatum
    maximum_wettelijk: float | None
    maximum_toelichting: str
    saldo_auditfile: float
    rekeningen: int
    methode: str
    invoer: Invoer

    @property
    def maximum(self) -> float | None:
        """Het maximumbedrag inclusief de verhoging met eerder belast voordeel."""
        if self.maximum_wettelijk is None:
            return None
        return self.maximum_wettelijk + float(self.invoer.eerder_belast_voordeel)

    @property
    def te_toetsen(self) -> float:
        """De schuld die tegenover het maximumbedrag wordt gezet."""
        return (
            self.saldo_auditfile
            - float(self.invoer.eigenwoningschuld)
            + float(self.invoer.andere_vennootschappen)
        )

    @property
    def bovenmatig(self) -> float | None:
        """Het bedrag boven het maximumbedrag, of ``None`` als dat onbekend is."""
        maximum = self.maximum
        if maximum is None:
            return None
        return max(self.te_toetsen - maximum, 0.0)

    @property
    def ernst(self) -> str | None:
        """De ernst voor het bevindingenoverzicht, of ``None`` bij geen bevinding."""
        if self.status == STATUS_BOVEN:
            return WAARSCHUWING
        if self.status == STATUS_NABIJ:
            return SIGNAAL
        if self.status == STATUS_NIET_MOGELIJK:
            return NIET_MOGELIJK
        return None


def maximumbedrag(jaar: int | None) -> tuple[float | None, str]:
    """Het maximumbedrag per peildatum 31 december, met de onderbouwing.

    Buiten de vastgestelde reeks komt er geen bedrag. Voor een peildatum vóór
    2023 bestond de regeling niet; voor een peildatum na het laatst vastgestelde
    jaar is het bedrag nog niet vastgesteld en zou doorschrijven van het laatste
    bedrag een aanname zijn.
    """
    if jaar is None:
        return None, "Zonder peildatum is er geen maximumbedrag."
    if jaar < EERSTE_JAAR:
        return None, (
            f"De Wet excessief lenen bij eigen vennootschap geldt vanaf "
            f"1 januari {EERSTE_JAAR}. Voor peildatum 31 december {jaar} is er "
            "geen maximumbedrag."
        )
    bedrag = MAXIMUMBEDRAGEN.get(jaar)
    if bedrag is None:
        return None, (
            f"Voor peildatum 31 december {jaar} is het maximumbedrag nog niet "
            f"vastgesteld. Het laatst vastgestelde jaar is {LAATSTE_JAAR}; het "
            "bedrag wordt niet geïndexeerd, dus het volgt niet uit een eerder jaar."
        )
    toelichting = (
        f"Maximumbedrag per peildatum 31 december {jaar} op grond van art. 4.14a "
        "lid 2 Wet IB 2001."
    )
    if jaar >= VOORBEHOUD_JAAR:
        toelichting += (
            f" Dit bedrag staat onder voorbehoud van het Belastingplan {jaar + 1}."
        )
    return bedrag, toelichting


def bepaal_peildatum(af: Auditfile) -> Peildatum:
    """De peildatum van de toets, uit de einddatum van het boekjaar.

    De wet peilt op het einde van het kalenderjaar. Eindigt het boekjaar op
    31 december, dan valt de balansdatum daarmee samen en is de stand uit het
    auditfile de stand op de peildatum. Eindigt het boekjaar op een andere
    datum, dan is dat niet zo: de tool geeft dan de gemeten stand wel, maar
    noemt de toets niet mogelijk.
    """
    einddatum = pd.to_datetime(af.header.get("endDate", ""), errors="coerce")
    if pd.isna(einddatum):
        return Peildatum(
            datum=None,
            jaar=None,
            geldig=False,
            toelichting=(
                "Het bestand geeft geen einddatum van het boekjaar, dus de "
                "peildatum is niet vast te stellen."
            ),
        )
    einddatum = pd.Timestamp(einddatum)
    jaar = int(einddatum.year)
    if (einddatum.month, einddatum.day) == (12, 31):
        return Peildatum(
            datum=einddatum,
            jaar=jaar,
            geldig=True,
            toelichting=(
                f"Het boekjaar eindigt op 31 december {jaar} en valt daarmee samen "
                "met de peildatum van art. 4.14a lid 4 Wet IB 2001."
            ),
        )
    return Peildatum(
        datum=einddatum,
        jaar=jaar,
        geldig=False,
        toelichting=(
            f"Het boekjaar eindigt op {einddatum:%d-%m-%Y} en niet op 31 december. "
            "De wet peilt op het einde van het kalenderjaar, dus de balansdatum is "
            "hier niet de peildatum. De stand hieronder is de balansstand en geen "
            "toets."
        ),
    )


def build_rc_rekeningen(af: Auditfile) -> pd.DataFrame:
    """De rekeningen-courant en leningen met aandeelhouders en bestuurders."""
    saldo = af.saldo
    if saldo.empty:
        return pd.DataFrame(columns=REKENING_COLUMNS)

    balans = saldo[saldo["accTp"].astype(str).str.strip().str.upper().eq("B")]
    if balans.empty:
        return pd.DataFrame(columns=REKENING_COLUMNS)

    masker, methode = _selecteer(
        balans, RGS_VOORVOEGSELS, OMSCHRIJVING_PATROON, rekeningtype="B"
    )
    selectie = balans[masker]
    if selectie.empty:
        return pd.DataFrame(columns=REKENING_COLUMNS)

    return (
        pd.DataFrame(
            {
                "rekening": selectie["rekening"].astype(str),
                "omschrijving": selectie["accDesc"].astype(str),
                "RGScode": selectie["RGScode"].astype(str),
                "methode": methode,
                "eindsaldo": selectie["eindsaldo"].astype(float),
            }
        )
        .sort_values("rekening")
        .reset_index(drop=True)
    )


def build_afwijkende_codering(af: Auditfile) -> pd.DataFrame:
    """Rekeningen die op de omschrijving wel, op de RGS-code niet meetellen.

    Een rekening-courant met de dga die als "rekening-courant overigen" of als
    commissarissenrekening is gecodeerd, valt buiten de toets. Dat is de prijs
    van RGS boven omschrijving, en die prijs hoort zichtbaar te zijn: de
    gebruiker kan zelf zien of hier een post bij zit die in de toets thuishoort.
    """
    saldo = af.saldo
    if saldo.empty:
        return pd.DataFrame(columns=AFWIJKING_COLUMNS)

    balans = saldo[saldo["accTp"].astype(str).str.strip().str.upper().eq("B")].copy()
    if balans.empty:
        return pd.DataFrame(columns=AFWIJKING_COLUMNS)

    codes = balans["RGScode"].astype(str).str.strip()
    heeft_rgs = codes != ""
    hoort_erbij = pd.Series(False, index=balans.index)
    for voorvoegsel in RGS_VOORVOEGSELS:
        hoort_erbij |= codes.str.startswith(voorvoegsel)
    op_naam = balans["accDesc"].astype(str).str.contains(
        OMSCHRIJVING_PATROON, case=False, na=False, regex=True
    )

    afwijkend = balans[op_naam & heeft_rgs & ~hoort_erbij]
    if afwijkend.empty:
        return pd.DataFrame(columns=AFWIJKING_COLUMNS)

    return (
        pd.DataFrame(
            {
                "rekening": afwijkend["rekening"].astype(str),
                "omschrijving": afwijkend["accDesc"].astype(str),
                "RGScode": afwijkend["RGScode"].astype(str),
                "eindsaldo": afwijkend["eindsaldo"].astype(float),
                "signaal": (
                    "De omschrijving wijst op een rekening-courant, maar de RGS-code "
                    "hoort niet bij aandeelhouders of bestuurders. Deze rekening telt "
                    "niet mee in de drempeltoets; beoordeel of dat juist is."
                ),
            }
        )
        .sort_values("rekening")
        .reset_index(drop=True)
    )


def beoordeel(af: Auditfile, invoer: Invoer | None = None) -> Toets:
    """De drempeltoets, met de status die eruit volgt."""
    invoer = invoer or Invoer()
    peil = bepaal_peildatum(af)
    wettelijk, wettelijke_toelichting = maximumbedrag(peil.jaar if peil.geldig else None)

    rekeningen = build_rc_rekeningen(af)
    saldo = float(rekeningen["eindsaldo"].sum()) if not rekeningen.empty else 0.0
    methode = str(rekeningen.iloc[0]["methode"]) if not rekeningen.empty else "geen treffers"

    toets = Toets(
        status=STATUS_GEEN_REKENING,
        peildatum=peil,
        maximum_wettelijk=wettelijk,
        maximum_toelichting=wettelijke_toelichting,
        saldo_auditfile=saldo,
        rekeningen=int(len(rekeningen)),
        methode=methode,
        invoer=invoer,
    )

    # Zonder rekening en zonder eigen invoer is er niets te toetsen. Is er wel
    # invoer, dan is er wel iets te toetsen: de gebruiker heeft een schuld aan
    # een andere vennootschap opgegeven.
    heeft_bedrag = bool(rekeningen.shape[0]) or abs(toets.te_toetsen) > TOLERANTIE
    if not heeft_bedrag:
        return toets

    if not peil.geldig or toets.maximum is None:
        return _met_status(toets, STATUS_NIET_MOGELIJK)

    if toets.te_toetsen <= TOLERANTIE:
        return _met_status(toets, STATUS_GEEN_SCHULD)

    maximum = toets.maximum
    if toets.te_toetsen - maximum > TOLERANTIE:
        return _met_status(toets, STATUS_BOVEN)
    if maximum > 0 and toets.te_toetsen >= maximum * NABIJ_AANDEEL:
        return _met_status(toets, STATUS_NABIJ)
    return _met_status(toets, STATUS_ONDER)


def _met_status(toets: Toets, status: str) -> Toets:
    return Toets(
        status=status,
        peildatum=toets.peildatum,
        maximum_wettelijk=toets.maximum_wettelijk,
        maximum_toelichting=toets.maximum_toelichting,
        saldo_auditfile=toets.saldo_auditfile,
        rekeningen=toets.rekeningen,
        methode=toets.methode,
        invoer=toets.invoer,
    )


def build_drempeltoets(af: Auditfile, invoer: Invoer | None = None) -> pd.DataFrame:
    """De opbouw van de toets als tabel: wat uit het bestand komt en wat niet.

    De regels staan in de volgorde waarin de toets wordt gemaakt, en elke regel
    zegt in de kolom ``bron`` of het bedrag uit het auditfile komt, uit de wet,
    of van de gebruiker. Zonder die scheiding is achteraf niet te zien waarop de
    uitkomst rust.
    """
    toets = beoordeel(af, invoer)
    if toets.status == STATUS_GEEN_REKENING:
        return pd.DataFrame(columns=OPBOUW_COLUMNS)
    return opbouw(toets)


def opbouw(toets: Toets) -> pd.DataFrame:
    """De opbouwtabel bij een al berekende toets."""
    invoer = toets.invoer
    rijen: list[dict[str, object]] = [
        {
            "onderdeel": "Saldo rekening-courant en leningen volgens het auditfile",
            "bron": "auditfile",
            "bedrag": toets.saldo_auditfile,
            "toelichting": (
                f"Eindsaldo van {toets.rekeningen} rekening(en), geselecteerd op "
                f"{toets.methode}. Debet is een vordering van de vennootschap en "
                "dus een schuld van de aandeelhouder."
            ),
        },
        {
            "onderdeel": "Af: eigenwoningschuld met recht van hypotheek",
            "bron": "gebruiker",
            "bedrag": -float(invoer.eigenwoningschuld),
            "toelichting": (
                "Art. 4.14a lid 6 Wet IB 2001 laat de eigenwoningschuld buiten "
                "beschouwing voor zover daarvoor een recht van hypotheek aan de "
                "vennootschap is verstrekt. Voor een op 31 december 2022 bestaande "
                "eigenwoningschuld geldt die hypotheekeis niet (art. 10a.23). Het "
                "grootboek zegt niet of dat recht er is."
            ),
        },
        {
            "onderdeel": "Bij: schulden aan andere vennootschappen en van de partner",
            "bron": "gebruiker",
            "bedrag": float(invoer.andere_vennootschappen),
            "toelichting": (
                "De schulden aan alle vennootschappen waarin een aanmerkelijk belang "
                "wordt gehouden tellen samen, en die van de partner tellen mee "
                "(art. 4.14a lid 3). Dit auditfile ziet één vennootschap."
            ),
        },
        {
            "onderdeel": "Te toetsen schuld",
            "bron": "berekend",
            "bedrag": toets.te_toetsen,
            "toelichting": "De som van de drie regels hierboven.",
        },
        {
            "onderdeel": "Maximumbedrag volgens de wet",
            "bron": "wet",
            "bedrag": toets.maximum_wettelijk,
            "toelichting": toets.maximum_toelichting,
        },
        {
            "onderdeel": "Bij: eerder belast fictief regulier voordeel",
            "bron": "gebruiker",
            "bedrag": float(invoer.eerder_belast_voordeel),
            "toelichting": (
                "Art. 4.14a lid 2 verhoogt het maximumbedrag met het eerder in "
                "aanmerking genomen fictieve reguliere voordeel, zodat hetzelfde "
                "bedrag niet tweemaal wordt belast."
            ),
        },
        {
            "onderdeel": "Maximumbedrag na verhoging",
            "bron": "berekend",
            "bedrag": toets.maximum,
            "toelichting": "Het maximumbedrag waaraan de schuld wordt getoetst.",
        },
        {
            "onderdeel": "Bovenmatig deel",
            "bron": "berekend",
            "bedrag": toets.bovenmatig,
            "toelichting": conclusie(toets),
        },
    ]
    return pd.DataFrame(rijen, columns=OPBOUW_COLUMNS)


def conclusie(toets: Toets) -> str:
    """Wat de tool over deze uitkomst zegt, in de taal van een signaal."""
    if toets.status == STATUS_GEEN_REKENING:
        return (
            "Er is geen rekening-courant of lening met een aandeelhouder of "
            "bestuurder gevonden. De regeling is daarmee niet uitgesloten: een "
            "rekening met een andere codering of omschrijving valt buiten de "
            "selectie."
        )
    if toets.status == STATUS_NIET_MOGELIJK:
        return (
            f"De toets is niet te maken. {toets.peildatum.toelichting} "
            f"{toets.maximum_toelichting}"
        ).strip()
    if toets.status == STATUS_GEEN_SCHULD:
        return (
            "Op de peildatum is er geen schuld van de aandeelhouder aan de "
            "vennootschap; het saldo staat credit of is nul. De Wet excessief "
            "lenen speelt dan niet."
        )
    if toets.status == STATUS_BOVEN:
        return (
            "De te toetsen schuld ligt boven het maximumbedrag. Beoordeel of "
            "hier een fictief regulier voordeel in box 2 in aanmerking moet "
            "worden genomen, en of alle schulden en alle vennootschappen in de "
            "opbouw zijn meegenomen."
        )
    if toets.status == STATUS_NABIJ:
        return (
            f"De te toetsen schuld blijft onder het maximumbedrag, maar ligt "
            f"binnen {round((1 - NABIJ_AANDEEL) * 100)}% daarvan. Eén opname voor "
            "het einde van het kalenderjaar brengt haar erboven; beoordeel het "
            "verloop tot de peildatum."
        )
    return (
        "De te toetsen schuld blijft onder het maximumbedrag. Let op dat de "
        "opbouw alleen deze vennootschap bevat, plus wat is ingevoerd."
    )
