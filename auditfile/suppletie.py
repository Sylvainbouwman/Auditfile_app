"""Suppletiedetectie: is er een btw-suppletie geboekt, en waarop slaat die?

De btw-rondrekening in ``vat.py`` vangt een suppletie op als "overige
mutaties": wat niet uit de facturatie en niet uit de betalingen volgt. Dat is
een restpost en daarmee een antwoord op een andere vraag dan die van de
assistent. Die vraag luidt: ik zie een verschil tussen het auditfile en de
aangifte - is daarvoor al een suppletie geboekt, en sluit die op het verschil
aan?

Deze module beantwoordt het eerste deel met het bestand in de hand: er is een
boeking die zichzelf een suppletie noemt, van dit bedrag, in deze periode en
over dit tijdvak. Het tweede deel zet zij ernaast: het verschil met de
ingediende aangifte, en wat er na de geboekte suppletie van dat verschil
overblijft. Of er nog een suppletie moet worden ingediend, staat er niet: de
tool ziet een boeking en geen indiening, en of het restant een suppletie
rechtvaardigt is een oordeel van de gebruiker.

Twee lagen, zoals bij het memorandum: ``bouw_aansluiting()`` stelt vast wat er
is en formuleert dat, ``naar_tabel()`` maakt er een overzicht van.

Tekens
------
De tabel houdt het grootboekbedrag aan, net als de rondrekening: debet
positief, dus een extra schuld aan de Belastingdienst staat er negatief in. Pas
in de aansluiting wordt dat omgerekend naar een aangiftebedrag, waar een af te
dragen bedrag positief is. Zo staat de omrekening op één plek en valt een
onverwacht teken in de tabel op in plaats van weg.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd

from .controls import _selecteer
from .model import Auditfile
from .notatie import euro
from .vat import AFRONDINGSMARGE_EURO, btw_grootboekrekeningen
from .vat_rubrics import AFDRACHT_CODES, VOORBELASTING_CODES

# Rekeningen waarop een suppletie terecht kan komen. De btw-codetabel wijst de
# rekeningen aan waarop de btw uit de facturatie wordt geboekt, maar een
# suppletie gaat daar vaak langs: pakketten boeken haar op een eigen "nog te
# betalen omzetbelasting" die in die tabel niet voorkomt. Daarom ook een
# selectie op omschrijving. RGS kent hiervoor geen bruikbaar voorvoegsel op
# hoofdrubriekniveau - de btw-schuld valt onder de kortlopende schulden en de
# voorbelasting onder de vorderingen, samen met van alles wat hier niet hoort -
# dus is de omschrijving de enige methode en geldt zij voor alle
# balansrekeningen. Het rekeningtype sluit de resultaatrekeningen uit.
BTW_REKENING_PATROON = r"omzetbelasting|\bbtw\b|\bob\b"

# Zekerheid van een treffer. Hoog is een boeking die zichzelf een suppletie of
# naheffing noemt; middel is een btw-correctie, die net zo goed een
# herrubricering kan zijn.
HOOG = "hoog"
MIDDEL = "middel"

# Trefwoorden met hoge zekerheid, elk met het etiket dat in de uitkomst komt.
TREFWOORDEN: tuple[tuple[str, str], ...] = (
    (r"suppleti|\bsuppl\.?\b", "suppletie"),
    (r"naheffing", "naheffingsaanslag"),
    (r"aanvullende\s+(?:aangifte|ob\b|omzetbelasting)|extra\s+aangifte", "aanvullende aangifte"),
)

# Een correctie telt alleen mee als in dezelfde tekst ook de btw wordt genoemd.
# Zonder die eis vangt het woord elke memoriaalcorrectie op de rekening op.
CORRECTIE_PATROON = r"correcti|\bcorr\.?\b"
BTW_WOORD_PATROON = r"\bbtw\b|\bob\b|omzetbelasting"

# Tijdvakken zoals ze in een omschrijving worden geschreven.
_KWARTAAL_PATRONEN: tuple[str, ...] = (
    r"\bq\s*([1-4])\b",
    r"\b([1-4])(?:e|de|ste)?\s*kwartaal\b",
    r"\bkwartaal\s*([1-4])\b",
)
_MAANDEN: tuple[str, ...] = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)
_JAAR_PATROON = r"\b(20\d{2})\b"

SUPPLETIE_COLUMNS = [
    "datum",
    "periode",
    "journaal",
    "transactie",
    "rekening",
    "omschrijving",
    "bedrag",
    "tijdvak",
    "jaar",
    "hoort_bij_boekjaar",
    "trefwoord",
    "zekerheid",
]

# De uitkomsten van de aansluiting. Elke status stelt de gebruiker een andere
# vraag; ze worden daarom uit elkaar gehouden en niet samengevat tot "afwijking
# ja of nee".
GEEN_BTW_REKENINGEN = "Btw-rekeningen niet aangewezen"
GEEN_VERGELIJKING = "Verschil met de aangifte niet vast te stellen"
SUPPLETIE_ZONDER_VERGELIJKING = "Suppletie geboekt, verschil niet vast te stellen"
GEEN_AANLEIDING = "Geen suppletie en geen verschil"
GEEN_SUPPLETIE = "Verschil zonder geboekte suppletie"
SLUIT_AAN = "Geboekte suppletie sluit aan op het verschil"
DEELS = "Geboekte suppletie verklaart het verschil deels"
ZONDER_VERSCHIL = "Suppletie geboekt zonder verschil met de aangifte"


# --- Rekeningen en trefwoorden ----------------------------------------------


def btw_balansrekeningen(af: Auditfile) -> tuple[list[str], str]:
    """De balansrekeningen waarop een btw-suppletie terecht kan komen.

    Geeft de rekeningen terug plus de methode waarmee ze zijn gevonden, zodat de
    tool kan tonen waarop de detectie zich baseert.
    """
    uit_codetabel = sorted(btw_grootboekrekeningen(af))
    rekeningen = set(uit_codetabel)
    methoden: list[str] = ["btw-codetabel"] if uit_codetabel else []

    if not af.saldo.empty:
        masker, _ = _selecteer(af.saldo, None, BTW_REKENING_PATROON, rekeningtype="B")
        extra = {str(waarde) for waarde in af.saldo.loc[masker, "rekening"]} - rekeningen
        if extra:
            methoden.append("omschrijving")
            rekeningen |= extra

    return sorted(rekeningen), " en ".join(methoden)


def _trefwoord(tekst: str) -> tuple[str, str]:
    """Het trefwoord en de zekerheid van een omschrijving, of twee lege waarden."""
    laag = tekst.lower()
    for patroon, etiket in TREFWOORDEN:
        if re.search(patroon, laag):
            return etiket, HOOG
    if re.search(CORRECTIE_PATROON, laag) and re.search(BTW_WOORD_PATROON, laag):
        return "btw-correctie", MIDDEL
    return "", ""


def _tijdvak(tekst: str) -> tuple[str, str]:
    """Het tijdvak en het jaar uit een omschrijving, elk leeg als het ontbreekt."""
    laag = tekst.lower()
    tijdvak = ""
    for patroon in _KWARTAAL_PATRONEN:
        gevonden = re.search(patroon, laag)
        if gevonden:
            tijdvak = f"Q{gevonden.group(1)}"
            break
    if not tijdvak:
        for maand in _MAANDEN:
            if re.search(rf"\b{maand}\b", laag):
                tijdvak = maand
                break
    jaar = re.search(_JAAR_PATROON, laag)
    return tijdvak, jaar.group(1) if jaar else ""


# --- Detectie ---------------------------------------------------------------


def _uit_facturatie(lines: pd.DataFrame) -> pd.Series:
    """Regels in een transactie waarin ergens een btw-code voorkomt.

    Een suppletie is geen facturatieboeking. Zonder deze afbakening vangt het
    woord "correctie" ook de tegenboeking van een creditnota op, want die heet
    op de btw-rekening net zo goed "btw-correctie". Het is dezelfde afbakening
    die de rondrekening gebruikt om de facturatiestroom af te zonderen.
    """
    heeft_code = (lines["vat_vatID"] != "") | (lines["line_vatID"] != "")
    sleutel = lines["tx_jrnID"].astype(str) + "\x1f" + lines["tx_nr"].astype(str)
    return sleutel.isin(set(sleutel[heeft_code]))


def detecteer_suppleties(af: Auditfile) -> pd.DataFrame:
    """Boekingen op een btw-rekening die zichzelf een suppletie noemen.

    Er wordt gezocht in de omschrijving van de transactie, van de boekingsregel,
    van het dagboek en in de documentreferentie: pakketten zetten de aanduiding
    op wisselende plekken en één daarvan is genoeg. Boekingen uit de facturatie
    vallen af.
    """
    rekeningen, _ = btw_balansrekeningen(af)
    if not rekeningen or af.lines.empty:
        return pd.DataFrame(columns=SUPPLETIE_COLUMNS)

    lines = af.lines[af.lines["line_accID"].isin(rekeningen) & ~_uit_facturatie(af.lines)].copy()
    if lines.empty:
        return pd.DataFrame(columns=SUPPLETIE_COLUMNS)

    velden = ["tx_desc", "line_desc", "tx_jrn_desc", "line_docRef"]
    tekst = lines[velden[0]].astype(str)
    for veld in velden[1:]:
        tekst = tekst + " " + lines[veld].astype(str)

    treffers = [_trefwoord(waarde) for waarde in tekst]
    lines["trefwoord"] = [etiket for etiket, _ in treffers]
    lines["zekerheid"] = [zekerheid for _, zekerheid in treffers]
    lines["tijdvak"] = [_tijdvak(waarde)[0] for waarde in tekst]
    lines["jaar"] = [_tijdvak(waarde)[1] for waarde in tekst]
    lines = lines[lines["trefwoord"] != ""].copy()
    if lines.empty:
        return pd.DataFrame(columns=SUPPLETIE_COLUMNS)

    # Een suppletie over een ander jaar verklaart het verschil van dit boekjaar
    # niet. Een boeking zonder jaartal telt wel mee: dat is de gewone manier om
    # een suppletie over het eigen jaar te omschrijven, en haar buiten de
    # aansluiting laten zou meer verbergen dan meenemen.
    boekjaar = str(af.boekjaar or "")
    lines["hoort_bij_boekjaar"] = [
        jaar == "" or boekjaar == "" or jaar == boekjaar for jaar in lines["jaar"]
    ]
    lines["omschrijving"] = [
        _omschrijving(rij)
        for _, rij in lines[["tx_desc", "line_desc", "line_docRef"]].iterrows()
    ]

    resultaat = lines.rename(
        columns={"tx_jrnID": "journaal", "tx_nr": "transactie", "line_accID": "rekening"}
    )
    return resultaat[SUPPLETIE_COLUMNS].sort_values(["datum", "transactie"]).reset_index(drop=True)


def _omschrijving(rij: pd.Series) -> str:
    """De meest sprekende omschrijving van een regel, zonder herhaling."""
    delen: list[str] = []
    for waarde in [rij["line_desc"], rij["tx_desc"], rij["line_docRef"]]:
        tekst = str(waarde or "").strip()
        if tekst and tekst not in delen:
            delen.append(tekst)
    return " / ".join(delen)


# --- Aansluiting op het verschil met de aangifte ----------------------------


def _rubrieken(aantal: int) -> str:
    """"1 rubriek" of "3 rubrieken"; een tekst met haakjes leest slecht in een memo."""
    return f"{aantal} {'rubriek' if aantal == 1 else 'rubrieken'}"


@dataclass(frozen=True)
class Suppletieaansluiting:
    """Wat er is geboekt, waartegen het is afgezet en wat er overblijft.

    ``geboekt`` en ``restant`` staan als aangiftebedrag: positief is af te
    dragen. ``verschil_met_aangifte`` volgt dezelfde richting, dus positief
    betekent dat er volgens het auditfile meer verschuldigd is dan er is
    aangegeven.
    """

    status: str
    geboekt: float = 0.0
    geboekt_ander_jaar: float = 0.0
    aantal: int = 0
    tijdvakken: tuple[str, ...] = ()
    verschil_met_aangifte: float | None = None
    restant: float | None = None
    rubrieken_zonder_aangifte: int = 0
    overige_mutaties: float | None = None
    methode: str = ""

    @property
    def toelichting(self) -> str:
        """De uitkomst in één alinea, in de bewoording van het memorandum."""
        return " ".join(deel for deel in self._delen() if deel)

    def _delen(self) -> list[str]:
        if self.status == GEEN_BTW_REKENINGEN:
            return [
                "De btw-codetabel wijst geen btw-rekening aan en geen enkele balansrekening is "
                "op haar omschrijving als btw-rekening te herkennen. Er is daardoor niet vast "
                "te stellen of er een suppletie is geboekt."
            ]

        delen = [self._geboekt_zin()]
        if self.status in (GEEN_VERGELIJKING, SUPPLETIE_ZONDER_VERGELIJKING):
            delen.append(
                "Er is geen aangiftebedrag ingevoerd, dus het verschil tussen het auditfile en "
                "de aangifte is niet bepaald en er valt niets tegenover te zetten."
            )
            return delen

        delen.append(
            f"Het verschil tussen het auditfile en de aangifte bedraagt "
            f"{euro(self.verschil_met_aangifte)}"
            + (
                f"; {_rubrieken(self.rubrieken_zonder_aangifte)} "
                f"{'bleef' if self.rubrieken_zonder_aangifte == 1 else 'bleven'} buiten die "
                "vergelijking omdat daarvoor geen bedrag is ingevoerd."
                if self.rubrieken_zonder_aangifte
                else "."
            )
        )
        delen.append(self._restant_zin())
        if self.geboekt_ander_jaar:
            delen.append(
                f"Daarnaast is {euro(self.geboekt_ander_jaar)} geboekt met een tijdvak van een "
                "ander jaar; dat bedrag staat buiten deze aansluiting."
            )
        if self.overige_mutaties is not None and abs(self.overige_mutaties) >= AFRONDINGSMARGE_EURO:
            delen.append(
                f"De rondrekening laat {euro(self.overige_mutaties)} aan overige mutaties zien; "
                "daarvan is dit deel als suppletie herkenbaar."
            )
        return delen

    def _geboekt_zin(self) -> str:
        if not self.aantal:
            return "In het boekjaar is geen boeking aangetroffen die zichzelf een suppletie noemt."
        tijdvak = f" over {', '.join(self.tijdvakken)}" if self.tijdvakken else ""
        if self.aantal == 1:
            return (
                f"In het boekjaar is één boeking{tijdvak} aangetroffen die als suppletie "
                f"herkenbaar is, van {euro(self.geboekt)}."
            )
        return (
            f"In het boekjaar zijn {self.aantal} boekingen{tijdvak} aangetroffen die als "
            f"suppletie herkenbaar zijn, samen {euro(self.geboekt)}."
        )

    def _restant_zin(self) -> str:
        if self.status == SLUIT_AAN:
            return (
                "De geboekte suppletie sluit daarop aan. Of zij ook is ingediend, blijkt niet "
                "uit het auditfile."
            )
        if self.status == DEELS:
            return (
                f"Na de geboekte suppletie blijft {euro(self.restant)} van het verschil over. "
                "Beoordeel waaruit dat restant bestaat."
            )
        if self.status == GEEN_SUPPLETIE:
            return "Er staat geen geboekte suppletie tegenover. Beoordeel of dat terecht is."
        if self.status == ZONDER_VERSCHIL:
            return (
                "Tegenover de geboekte suppletie staat geen verschil met de aangifte. Beoordeel "
                "waarop de boeking dan betrekking heeft."
            )
        return ""


def _verschil_met_aangifte(samenvatting: pd.DataFrame) -> tuple[float | None, int]:
    """Het netto verschil tussen auditfile en aangifte, over de ingevulde rubrieken.

    Per rubriek staat het verschil als aangiftebedrag. Optellen mag pas na
    omrekening naar één richting: bij een afdrachtrubriek verhoogt een verschil
    het te betalen bedrag, bij een voorbelastingrubriek verlaagt het dat juist.
    Dat is dezelfde rekenwijze als ``vat.build_vat_position()``.
    """
    if samenvatting.empty or "verschil" not in samenvatting.columns:
        return None, 0

    niet_ingevuld = int((samenvatting["status"] == "Niet ingevuld").sum())
    ingevuld = samenvatting["verschil"].notna()
    if not ingevuld.any():
        return None, niet_ingevuld

    def teken(code: str) -> float:
        if code in AFDRACHT_CODES:
            return 1.0
        if code in VOORBELASTING_CODES:
            return -1.0
        return 0.0

    tekens = samenvatting["rubriek"].map(teken)
    return float((samenvatting.loc[ingevuld, "verschil"] * tekens[ingevuld]).sum()), niet_ingevuld


def bouw_aansluiting(
    af: Auditfile,
    samenvatting: pd.DataFrame,
    suppleties: pd.DataFrame | None = None,
    verloop: pd.DataFrame | None = None,
) -> Suppletieaansluiting:
    """Zet de geboekte suppleties naast het verschil met de aangifte.

    ``suppleties`` en ``verloop`` mogen worden meegegeven wanneer ze elders al
    zijn berekend; anders worden ze hier bepaald.
    """
    from .vat import build_vat_ledger_flow

    rekeningen, methode = btw_balansrekeningen(af)
    if not rekeningen:
        return Suppletieaansluiting(status=GEEN_BTW_REKENINGEN)

    if suppleties is None:
        suppleties = detecteer_suppleties(af)
    if verloop is None:
        verloop = build_vat_ledger_flow(af, samenvatting)

    if suppleties.empty:
        eigen_jaar = ander_jaar = suppleties
    else:
        hoort_erbij = suppleties["hoort_bij_boekjaar"].astype(bool)
        eigen_jaar = suppleties[hoort_erbij]
        ander_jaar = suppleties[~hoort_erbij]

    # Van grootboeksaldo naar aangiftebedrag: een extra schuld staat credit.
    geboekt = -float(eigen_jaar["bedrag"].sum()) if not eigen_jaar.empty else 0.0
    geboekt_ander_jaar = -float(ander_jaar["bedrag"].sum()) if not ander_jaar.empty else 0.0
    tijdvakken = tuple(
        dict.fromkeys(
            f"{rij['tijdvak']} {rij['jaar']}".strip()
            for _, rij in eigen_jaar.iterrows()
            if rij["tijdvak"] or rij["jaar"]
        )
    )

    overige = None
    if not verloop.empty:
        regel = verloop[verloop["post"] == "Overige mutaties"]
        if not regel.empty:
            overige = float(regel.iloc[0]["bedrag"])

    verschil, zonder_aangifte = _verschil_met_aangifte(samenvatting)
    heeft_suppletie = len(eigen_jaar) > 0

    if verschil is None:
        status = SUPPLETIE_ZONDER_VERGELIJKING if heeft_suppletie else GEEN_VERGELIJKING
        restant = None
    else:
        restant = verschil - geboekt
        if not heeft_suppletie:
            status = GEEN_SUPPLETIE if abs(verschil) >= AFRONDINGSMARGE_EURO else GEEN_AANLEIDING
        elif abs(verschil) < AFRONDINGSMARGE_EURO:
            status = ZONDER_VERSCHIL
        elif abs(restant) < AFRONDINGSMARGE_EURO:
            status = SLUIT_AAN
        else:
            status = DEELS

    return Suppletieaansluiting(
        status=status,
        geboekt=geboekt,
        geboekt_ander_jaar=geboekt_ander_jaar,
        aantal=len(eigen_jaar),
        tijdvakken=tijdvakken,
        verschil_met_aangifte=verschil,
        restant=restant,
        rubrieken_zonder_aangifte=zonder_aangifte,
        overige_mutaties=overige,
        methode=methode,
    )


def naar_tabel(aansluiting: Suppletieaansluiting) -> pd.DataFrame:
    """De aansluiting als overzicht, in dezelfde vorm als de rondrekening."""
    kolommen = ["post", "bedrag", "toelichting"]
    if aansluiting.status == GEEN_BTW_REKENINGEN:
        return pd.DataFrame(columns=kolommen)

    posten = [
        {
            "post": "Verschil tussen auditfile en aangifte",
            "bedrag": aansluiting.verschil_met_aangifte,
            "toelichting": "Positief is meer verschuldigd volgens het auditfile dan er is "
            "aangegeven."
            + (
                f" {_rubrieken(aansluiting.rubrieken_zonder_aangifte)} zonder ingevoerd bedrag "
                f"{'blijft' if aansluiting.rubrieken_zonder_aangifte == 1 else 'blijven'} buiten "
                "de vergelijking."
                if aansluiting.rubrieken_zonder_aangifte
                else ""
            ),
        },
        {
            "post": "Geboekte suppletie",
            "bedrag": aansluiting.geboekt,
            "toelichting": f"{aansluiting.aantal} "
            f"{'boeking' if aansluiting.aantal == 1 else 'boekingen'} op de btw-rekeningen, "
            f"aangewezen op {aansluiting.methode or 'geen methode'}. Een boeking is geen "
            "indiening.",
        },
        {
            "post": "Restant",
            "bedrag": aansluiting.restant,
            "toelichting": "Wat er van het verschil overblijft na de geboekte suppletie.",
        },
    ]
    if aansluiting.geboekt_ander_jaar:
        posten.insert(
            2,
            {
                "post": "Geboekte suppletie over een ander jaar",
                "bedrag": aansluiting.geboekt_ander_jaar,
                "toelichting": "Het genoemde tijdvak valt buiten dit boekjaar; telt niet mee in "
                "het restant.",
            },
        )
    return pd.DataFrame(posten, columns=kolommen)
