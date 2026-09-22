"""De ingediende aangifte omzetbelasting inlezen uit een XBRL-bestand.

Een auditfile bevat geen aangifte. De tool vroeg de aangegeven bedragen daarom
tot nu toe als invoer van de gebruiker, per rubriek, als totaal over het
boekjaar. Dat overtypen is werk en het is de plek waar een tikfout een verschil
maakt dat er niet is. Wie de aangifte elektronisch indient heeft het bestand
zelf al: de btw-aangifte gaat sinds 2014 verplicht als XBRL via Digipoort, en
de gangbare pakketten laten dat bestand exporteren.

Wat deze module doet is dus smal: zij leest zo'n bestand en geeft terug welk
bedrag er per rubriek in staat. Zij dient geen aangifte in, controleert er geen
en zegt niet of de aangifte juist is.

Koppelen op de elementnaam, niet op het rubrieknummer
-----------------------------------------------------
Het nummer op het aangifteformulier is presentatie: het is in het verleden
gewijzigd en kan dat weer doen. De elementnaam in de taxonomie is de vaste
identiteit van het gegeven. De koppeling hieronder gaat daarom van elementnaam
naar rubriekcode en nooit andersom. Dezelfde redenering als bij
``Bevinding.identiteitssleutel`` in ``findings.py``.

De koppeling is niet geraden maar overgenomen uit de taxonomie zelf: elk
element hieronder draagt zijn Nederlandse label en het paragraafnummer van de
officiële definitie van de Belastingdienst. ``docs/xbrl-aangifte.md`` bevat de
volledige tabel met die definities en de vindplaats.

Namespace en versie doen niet ter zake
--------------------------------------
Net als bij XAF wordt de namespace gestript en op de lokale elementnaam
gewerkt. De taxonomie krijgt jaarlijks een nieuwe versie met een nieuwe
namespace, terwijl de elementnamen van de rubrieken al over meerdere versies
ongewijzigd zijn: er kwamen elementen bij, er verdween er geen en er werd er
geen hernoemd. Een versiecontrole zou dus alleen een bestand weigeren dat
prima te lezen is. Wat de tool niet herkent, meldt zij per elementnaam, zodat
een echte wijziging opvalt in plaats van weg te vallen.

Eén bestand is één tijdvak
--------------------------
Een aangifte gaat over een maand, een kwartaal of een jaar; het boekjaar vraagt
er dus meestal meer dan één. ``tel_op()`` telt de bestanden bij elkaar op en
zegt erbij wat er aan het tijdvak opvalt: een gat, een overlap, een tijdvak
buiten het boekjaar, of een ander omzetbelastingnummer dan dat van het
auditfile. Dat laatste is de belangrijkste: het is de controle die voorkomt dat
de aangifte van een ander dossier wordt ingelezen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite
import xml.etree.ElementTree as ET

import pandas as pd

from .parsing import local_name

# Soort bericht. Een suppletie gebruikt dezelfde rubriekelementen als een
# aangifte, met de gecorrigeerde standen erin, en heeft daarnaast eigen velden
# voor wat er eerder was aangegeven.
SOORT_AANGIFTE = "aangifte"
SOORT_SUPPLETIE = "suppletie"
SOORT_ONBEKEND = "onbekend"

# De btw per rubriek: elementnaam -> rubriekcode. Het label en het
# paragraafnummer erachter zijn die van de taxonomie van de Belastingdienst.
BTW_ELEMENTEN: dict[str, str] = {
    # Omzetbelasting leveringen/diensten algemeen tarief (509383)
    "ValueAddedTaxSuppliesServicesGeneralTariff": "1a",
    # Omzetbelasting leveringen/diensten verlaagd tarief (509385)
    "ValueAddedTaxSuppliesServicesReducedTariff": "1b",
    # Omzetbelasting leveringen/diensten overige tarieven (509387)
    "ValueAddedTaxSuppliesServicesOtherRates": "1c",
    # Omzetbelasting over privegebruik (509389)
    "ValueAddedTaxPrivateUse": "1d",
    # Omzetbelasting leveringen/diensten waarbij heffing is verlegd (509395)
    "ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred": "2a",
    # Omzetbelasting leveringen/diensten uit landen buiten de EU (509403)
    "ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC": "4a",
    # Omzetbelasting leveringen/diensten uit landen binnen EU (509405)
    "ValueAddedTaxOnSuppliesFromCountriesWithinTheEC": "4b",
    # Voorbelasting (509407)
    "ValueAddedTaxOnInput": "5b",
}

# Het bedrag waarover de omzetbelasting is berekend: elementnaam -> rubriekcode.
# Bij 1e, 3a, 3b en 3c is dit het enige bedrag dat het formulier vraagt.
GRONDSLAG_ELEMENTEN: dict[str, str] = {
    # Omzet leveringen/diensten belast met algemeen tarief (509382)
    "TaxedTurnoverSuppliesServicesGeneralTariff": "1a",
    # Omzet leveringen/diensten belast met verlaagd tarief (509384)
    "TaxedTurnoverSuppliesServicesReducedTariff": "1b",
    # Omzet leveringen/diensten belast met overige tarieven (509386)
    "TaxedTurnoverSuppliesServicesOtherRates": "1c",
    # Omzet privegebruik (509388)
    "TaxedTurnoverPrivateUse": "1d",
    # Omzet leveringen/diensten belast met nultarief of niet bij u belast (509390)
    "SuppliesServicesNotTaxed": "1e",
    # Omzet leveringen/diensten waarbij heffing is verlegd (509393)
    "TurnoverSuppliesServicesByWhichVATTaxationIsTransferred": "2a",
    # Leveringen naar landen buiten EU (509400)
    "SuppliesToCountriesOutsideTheEC": "3a",
    # Leveringen naar/diensten in landen binnen EU (509398)
    "SuppliesToCountriesWithinTheEC": "3b",
    # Installatie/afstandsverkopen binnen de EU (509401)
    "InstallationDistanceSalesWithinTheEC": "3c",
    # Omzet belaste leveringen/diensten uit landen buiten de EU (509402)
    "TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC": "4a",
    # Omzet belaste leveringen/diensten uit landen binnen EU (509404)
    "TurnoverFromTaxedSuppliesFromCountriesWithinTheEC": "4b",
}

# Totalen en suppletievelden. Deze horen niet bij één rubriek: 5a is het
# berekende subtotaal van de verschuldigde btw en de rest sluit de aangifte of
# de suppletie af.
VERSCHULDIGD = "verschuldigd"
EINDTOTAAL = "eindtotaal"
KOR_VERMINDERING = "kor_vermindering"
SUPPLETIE_EERDER = "suppletie_eerder_aangegeven"
SUPPLETIE_NIEUW = "suppletie_nieuw_totaal"
SUPPLETIE_SALDO = "suppletie_saldo"

TOTAAL_ELEMENTEN: dict[str, str] = {
    # Verschuldigde omzetbelasting, rubriek 5a (509406)
    "ValueAddedTaxOwed": VERSCHULDIGD,
    # Totaal te betalen / terug te vragen (509408). Komt volgens de definitie
    # alleen voor bij een aangifte en niet bij een suppletie.
    "ValueAddedTaxOwedToBePaidBack": EINDTOTAAL,
    # Vermindering volgens de kleineondernemersregeling (516662). Sinds de
    # omzetgerelateerde vrijstelling van 2020 staat deze rubriek niet meer op
    # het formulier; oudere aangiften kunnen haar nog bevatten.
    "SmallEntrepreneurProvisionReduction": KOR_VERMINDERING,
    # Oud totaal bedrag: al aangegeven in de periode van de suppletie (637579)
    "ValueAddedTaxAmountTotalOld": SUPPLETIE_EERDER,
    # Nieuw totaal bedrag (637578)
    "ValueAddedTaxAmountTotalNew": SUPPLETIE_NIEUW,
    # Totaal bij te betalen/terug te vragen over het tijdvak van de suppletie (643303)
    "ValueAddedTaxToBePaidAdditionalToBePaidBack": SUPPLETIE_SALDO,
}

# Velden die het bericht beschrijven in plaats van een bedrag te geven.
OMZETBELASTINGNUMMER_ELEMENTEN = (
    "VATIdentificationNumberNational",
    "VATIdentificationNumberNLFiscalEntityDivision",
)

# Elementen die niets zeggen over de rubrieken en die dus niet als "niet
# herkend" hoeven te worden gemeld. Het zijn de kop- en contactgegevens van het
# bericht.
GENEGEERDE_ELEMENTEN = frozenset(
    {
        "ApplicationId",
        "CompanyName",
        "ContactType",
        "VATReturnReferenceNumber",
        "VATReturnNil",
        "VATReturnDeviatingPeriodStartDate",
        "VATReturnDeviatingPeriodEndDate",
        *OMZETBELASTINGNUMMER_ELEMENTEN,
    }
)

OVERZICHT_COLUMNS = [
    "bestand",
    "soort",
    "begindatum",
    "einddatum",
    "omzetbelastingnummer",
    "verschuldigde_btw",
    "voorbelasting",
    "eindtotaal",
    "meldingen",
]


@dataclass(frozen=True)
class Aangifte:
    """Eén ingelezen XBRL-bericht: een aangifte of een suppletie."""

    bestand: str
    soort: str = SOORT_ONBEKEND
    begindatum: date | None = None
    einddatum: date | None = None
    omzetbelastingnummer: str = ""
    btw: dict[str, float] = field(default_factory=dict)
    grondslag: dict[str, float] = field(default_factory=dict)
    totalen: dict[str, float] = field(default_factory=dict)
    niet_herkend: tuple[str, ...] = ()
    meldingen: tuple[str, ...] = ()

    @property
    def gelezen(self) -> bool:
        """Is er een bedrag uit dit bestand gekomen?"""
        return bool(self.btw or self.grondslag or self.totalen)

    @property
    def tijdvak(self) -> str:
        if not self.begindatum or not self.einddatum:
            return ""
        return f"{self.begindatum.isoformat()} t/m {self.einddatum.isoformat()}"


@dataclass(frozen=True)
class Optelling:
    """Het totaal van meerdere berichten over één boekjaar."""

    btw: dict[str, float] = field(default_factory=dict)
    grondslag: dict[str, float] = field(default_factory=dict)
    totalen: dict[str, float] = field(default_factory=dict)
    meldingen: tuple[str, ...] = ()
    aantal: int = 0


def _tekst_naar_bedrag(tekst: str) -> float | None:
    schoon = (tekst or "").strip().replace(" ", "")
    if not schoon:
        return None
    try:
        bedrag = float(schoon)
    except ValueError:
        return None
    return bedrag if isfinite(bedrag) else None


def _tekst_naar_datum(tekst: str) -> date | None:
    schoon = (tekst or "").strip()
    if not schoon:
        return None
    try:
        return date.fromisoformat(schoon[:10])
    except ValueError:
        return None


def _lees_contexten(wortel: ET.Element) -> dict[str, tuple[date | None, date | None, str]]:
    """Per context-id de periode en de entiteit waar die context bij hoort.

    In XBRL staat het feit zelf los van zijn periode: het verwijst met
    ``contextRef`` naar een context, en daar staan de begin- en einddatum en de
    entiteit. Zonder die stap weet je van een bedrag niet over welk tijdvak het
    gaat.
    """
    contexten: dict[str, tuple[date | None, date | None, str]] = {}
    for element in wortel.iter():
        if local_name(element.tag) != "context":
            continue
        begin = eind = None
        entiteit = ""
        for kind in element.iter():
            naam = local_name(kind.tag)
            tekst = (kind.text or "").strip()
            if naam == "startDate":
                begin = _tekst_naar_datum(tekst)
            elif naam == "endDate":
                eind = _tekst_naar_datum(tekst)
            elif naam == "instant":
                begin = eind = _tekst_naar_datum(tekst)
            elif naam == "identifier" and tekst:
                entiteit = tekst
        contexten[element.get("id", "")] = (begin, eind, entiteit)
    return contexten


def _stel_soort_vast(elementen: set[str], schema: str) -> tuple[str, str]:
    """Aangifte of suppletie, met de reden erbij.

    Twee bronnen, in deze volgorde. De verwijzing naar het taxonomieschema
    bovenin het bestand noemt het berichttype met zoveel woorden en is daarmee
    het sterkst. Ontbreekt die of is zij niet te duiden, dan beslissen de
    aanwezige elementen: de suppletievelden komen alleen in een suppletie voor,
    en het eindtotaal van de aangifte volgens zijn eigen definitie alleen in een
    aangifte.
    """
    schema_klein = schema.lower()
    if "suppletie" in schema_klein:
        return SOORT_SUPPLETIE, "het taxonomieschema noemt het een suppletie"
    if "aangifte" in schema_klein:
        return SOORT_AANGIFTE, "het taxonomieschema noemt het een aangifte"
    if elementen & {"ValueAddedTaxAmountTotalOld", "ValueAddedTaxToBePaidAdditionalToBePaidBack"}:
        return SOORT_SUPPLETIE, "het bericht bevat de suppletievelden"
    if "ValueAddedTaxOwedToBePaidBack" in elementen:
        return SOORT_AANGIFTE, "het bericht bevat het eindtotaal van een aangifte"
    return SOORT_ONBEKEND, "het bericht noemt geen berichttype"


def lees_aangifte(bestand: str, inhoud: bytes | str) -> Aangifte:
    """Lees één XBRL-bestand met een aangifte of suppletie omzetbelasting."""
    try:
        wortel = ET.fromstring(inhoud)
    except ET.ParseError as fout:
        return Aangifte(bestand=bestand, meldingen=(f"Het bestand is geen geldige XML: {fout}.",))

    contexten = _lees_contexten(wortel)
    schema = ""
    for element in wortel.iter():
        if local_name(element.tag) == "schemaRef":
            for sleutel, waarde in element.attrib.items():
                if local_name(sleutel) == "href":
                    schema = waarde
            break

    btw: dict[str, float] = {}
    grondslag: dict[str, float] = {}
    totalen: dict[str, float] = {}
    niet_herkend: list[str] = []
    onleesbare_bedragen: list[str] = []
    gezien: set[str] = set()
    omzetbelastingnummer = ""
    perioden: set[tuple[date | None, date | None]] = set()
    entiteiten: set[str] = set()

    for element in wortel.iter():
        # Alleen een feit draagt een contextRef. Daarmee vallen de
        # structuurelementen van XBRL zelf af (schemaRef, context, unit) zonder
        # dat die bij naam hoeven te worden opgesomd, en worden feiten die in
        # een tuple zijn genest wel gevonden.
        context = element.get("contextRef")
        if context is None:
            continue
        naam = local_name(element.tag)
        gezien.add(naam)
        if context in contexten:
            begin, eind, entiteit = contexten[context]
            perioden.add((begin, eind))
            if entiteit:
                entiteiten.add(entiteit)

        if naam in OMZETBELASTINGNUMMER_ELEMENTEN and (element.text or "").strip():
            omzetbelastingnummer = omzetbelastingnummer or (element.text or "").strip()
            continue
        if naam in GENEGEERDE_ELEMENTEN:
            continue

        bekend_bedrag = (
            naam in BTW_ELEMENTEN or naam in GRONDSLAG_ELEMENTEN or naam in TOTAAL_ELEMENTEN
        )
        bedrag = _tekst_naar_bedrag(element.text or "")
        if bedrag is None:
            if bekend_bedrag:
                onleesbare_bedragen.append(naam)
            continue
        if naam in BTW_ELEMENTEN:
            btw[BTW_ELEMENTEN[naam]] = btw.get(BTW_ELEMENTEN[naam], 0.0) + bedrag
        elif naam in GRONDSLAG_ELEMENTEN:
            code = GRONDSLAG_ELEMENTEN[naam]
            grondslag[code] = grondslag.get(code, 0.0) + bedrag
        elif naam in TOTAAL_ELEMENTEN:
            sleutel = TOTAAL_ELEMENTEN[naam]
            totalen[sleutel] = totalen.get(sleutel, 0.0) + bedrag
        else:
            niet_herkend.append(naam)

    soort, reden = _stel_soort_vast(gezien, schema)
    meldingen: list[str] = []
    if soort == SOORT_ONBEKEND:
        meldingen.append(
            "Of dit een aangifte of een suppletie is, kon niet worden vastgesteld: "
            f"{reden}. De bedragen zijn wel ingelezen."
        )
    if niet_herkend:
        meldingen.append(
            "Niet herkende velden, die dus niet zijn meegeteld: "
            + ", ".join(sorted(set(niet_herkend)))
            + "."
        )
    if onleesbare_bedragen:
        meldingen.append(
            "Onleesbare bedragen, die dus niet zijn meegeteld: "
            + ", ".join(sorted(set(onleesbare_bedragen)))
            + "."
        )
    if not btw and not grondslag and not totalen:
        meldingen.append("Het bestand bevat geen bedragen van een aangifte omzetbelasting.")

    gedateerd = sorted(p for p in perioden if p[0] and p[1])
    begin = gedateerd[0][0] if gedateerd else None
    eind = gedateerd[-1][1] if gedateerd else None
    if not gedateerd:
        meldingen.append("Het bestand noemt geen tijdvak.")
    if len(entiteiten) > 1:
        meldingen.append(
            "Het bestand noemt meer dan één omzetbelastingnummer: " + ", ".join(sorted(entiteiten)) + "."
        )

    return Aangifte(
        bestand=bestand,
        soort=soort,
        begindatum=begin,
        einddatum=eind,
        omzetbelastingnummer=omzetbelastingnummer or (sorted(entiteiten)[0] if entiteiten else ""),
        btw=btw,
        grondslag=grondslag,
        totalen=totalen,
        niet_herkend=tuple(sorted(set(niet_herkend))),
        meldingen=tuple(meldingen),
    )


def build_overzicht(aangiften: list[Aangifte]) -> pd.DataFrame:
    """Eén regel per ingelezen bestand, om te tonen wat er is ingelezen."""
    if not aangiften:
        return pd.DataFrame(columns=OVERZICHT_COLUMNS)
    rijen = []
    for stuk in aangiften:
        rijen.append(
            {
                "bestand": stuk.bestand,
                "soort": stuk.soort,
                "begindatum": stuk.begindatum,
                "einddatum": stuk.einddatum,
                "omzetbelastingnummer": stuk.omzetbelastingnummer,
                "verschuldigde_btw": stuk.totalen.get(VERSCHULDIGD),
                "voorbelasting": stuk.btw.get("5b"),
                "eindtotaal": stuk.totalen.get(EINDTOTAAL, stuk.totalen.get(SUPPLETIE_SALDO)),
                "meldingen": " ".join(stuk.meldingen),
            }
        )
    overzicht = pd.DataFrame(rijen, columns=OVERZICHT_COLUMNS)
    # Als datum en niet als los ``date``-object: pandas maakt van dat laatste een
    # kolom van het type object, en de presentatielaag toont die dan als het
    # getal waar de datum intern op neerkomt in plaats van als datum.
    for kolom in ("begindatum", "einddatum"):
        overzicht[kolom] = pd.to_datetime(overzicht[kolom], errors="coerce")
    return overzicht


def _tijdvakmeldingen(
    aangiften: list[Aangifte], boekjaar: str, omzetbelastingnummer: str
) -> list[str]:
    meldingen: list[str] = []

    if omzetbelastingnummer:
        eigen = _vergelijkbaar(omzetbelastingnummer)
        afwijkend = sorted(
            {
                stuk.omzetbelastingnummer
                for stuk in aangiften
                if stuk.omzetbelastingnummer
                and _vergelijkbaar(stuk.omzetbelastingnummer) != eigen
            }
        )
        if afwijkend:
            meldingen.append(
                "Let op: het omzetbelastingnummer in "
                + ("een bestand" if len(afwijkend) == 1 else "meerdere bestanden")
                + f" ({', '.join(afwijkend)}) wijkt af van dat van het auditfile "
                f"({omzetbelastingnummer}). Hoort dit bij hetzelfde dossier?"
            )

    if boekjaar.isdigit():
        jaar = int(boekjaar)
        begin_boekjaar = date(jaar, 1, 1)
        eind_boekjaar = date(jaar, 12, 31)
        buiten = sorted(
            {
                stuk.bestand
                for stuk in aangiften
                if stuk.begindatum and stuk.begindatum.year != jaar
            }
        )
        if buiten:
            meldingen.append(
                f"Tijdvak buiten boekjaar {boekjaar}, wel meegeteld: {', '.join(buiten)}."
            )

        tijdvakken_boekjaar = sorted(
            (max(stuk.begindatum, begin_boekjaar), min(stuk.einddatum, eind_boekjaar))
            for stuk in aangiften
            if stuk.begindatum
            and stuk.einddatum
            and stuk.einddatum >= begin_boekjaar
            and stuk.begindatum <= eind_boekjaar
        )
        if tijdvakken_boekjaar:
            eerste_begin = tijdvakken_boekjaar[0][0]
            laatste_eind = tijdvakken_boekjaar[-1][1]
            if eerste_begin > begin_boekjaar:
                meldingen.append(
                    f"Tussen het begin van boekjaar {boekjaar} ({begin_boekjaar.isoformat()}) "
                    f"en {eerste_begin.isoformat()} zit een gat: er ontbreekt een tijdvak."
                )
            if laatste_eind < eind_boekjaar:
                meldingen.append(
                    f"Tussen {laatste_eind.isoformat()} en het einde van boekjaar {boekjaar} "
                    f"({eind_boekjaar.isoformat()}) zit een gat: er ontbreekt een tijdvak."
                )

    tijdvakken = sorted(
        (stuk.begindatum, stuk.einddatum, stuk.bestand)
        for stuk in aangiften
        if stuk.begindatum and stuk.einddatum
    )
    vorige_eind = None
    vorige_bestand = ""
    for begin, eind, bestand in tijdvakken:
        if vorige_eind is not None:
            if begin <= vorige_eind:
                meldingen.append(
                    f"De tijdvakken van {vorige_bestand} en {bestand} overlappen elkaar."
                )
            elif (begin - vorige_eind).days > 1:
                meldingen.append(
                    f"Tussen {vorige_eind.isoformat()} en {begin.isoformat()} zit een gat: "
                    "er ontbreekt een tijdvak."
                )
        vorige_eind = eind
        vorige_bestand = bestand

    return meldingen


def _vergelijkbaar(nummer: str) -> str:
    """Een omzetbelastingnummer zonder spaties, punten en hoofdletterverschil."""
    return "".join(teken for teken in str(nummer) if teken.isalnum()).upper()


def tel_op(
    aangiften: list[Aangifte],
    boekjaar: str = "",
    omzetbelastingnummer: str = "",
    soort: str = SOORT_AANGIFTE,
) -> Optelling:
    """Tel de berichten van één soort op tot een totaal over het boekjaar.

    Aangiften en suppleties worden niet bij elkaar opgeteld. Een suppletie geeft
    de gecorrigeerde stand van een tijdvak waarover al aangifte is gedaan; wie
    die twee optelt telt datzelfde tijdvak dubbel. Ze worden daarom apart
    opgeteld en apart getoond.
    """
    gekozen = [stuk for stuk in aangiften if stuk.soort == soort and stuk.gelezen]
    btw: dict[str, float] = {}
    grondslag: dict[str, float] = {}
    totalen: dict[str, float] = {}
    for stuk in gekozen:
        for code, bedrag in stuk.btw.items():
            btw[code] = btw.get(code, 0.0) + bedrag
        for code, bedrag in stuk.grondslag.items():
            grondslag[code] = grondslag.get(code, 0.0) + bedrag
        for sleutel, bedrag in stuk.totalen.items():
            totalen[sleutel] = totalen.get(sleutel, 0.0) + bedrag

    meldingen = _tijdvakmeldingen(gekozen, boekjaar, omzetbelastingnummer)
    return Optelling(
        btw=btw,
        grondslag=grondslag,
        totalen=totalen,
        meldingen=tuple(meldingen),
        aantal=len(gekozen),
    )
