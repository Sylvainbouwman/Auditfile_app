"""Eén bevindingenmodel voor alle controles.

Elke controle levert zijn eigen tabel op, met de kolommen die daar horen: bij de
periodieke lasten hoort een lijst met ontbrekende perioden, bij de btw een
rubriek. Die tabellen blijven zoals ze zijn, want op hun eigen pagina zijn ze
juist bruikbaar.

Wat ontbrak is de laag erboven: één lijst waarin al die uitkomsten dezelfde vorm
hebben. Zonder die laag is er geen reviewmemorandum te maken, geen materialiteit
toe te passen en niet bij te houden wat al is beoordeeld, want elke controle zou
dat apart moeten regelen. Deze module verzamelt de uitkomsten en zet ze om naar
één structuur.

Ernst
-----
``kritiek``       de cijfers zijn niet te gebruiken zonder dit eerst op te lossen
``waarschuwing``  een afwijking die verklaard kan zijn maar beoordeling vraagt
``signaal``       iets om naar te kijken; geen vastgestelde afwijking
``niet mogelijk`` de controle kon niet worden uitgevoerd; ook dat is een bevinding

``in orde`` komt hier niet voor: een controle zonder afwijking is geen bevinding.
De tellingen per controle staan op de eigen pagina's.

Materialiteit
-------------
Een bevinding wordt niet weggelaten omdat het bedrag klein is; wel gemarkeerd.
Weglaten zou betekenen dat de tool een oordeel geeft over wat de gebruiker niet
hoeft te zien. De drempel is een werkafspraak van de gebruiker en geen norm:
hij staat daarom als invoer en niet als vaste waarde in de code.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import pandas as pd

from .integrity import IN_ORDE, KRITIEK, NIET_MOGELIJK, WAARSCHUWING
from .model import Auditfile
from .notatie import euro, getal, procent

# Vierde niveau naast die van integrity.py: iets om naar te kijken.
SIGNAAL = "signaal"

# Van zwaar naar licht, voor de sortering.
ERNST_ORDE: tuple[str, ...] = (KRITIEK, WAARSCHUWING, SIGNAAL, NIET_MOGELIJK, IN_ORDE)

# De statussen die een beoordelaar aan een bevinding kan hangen. Bewust kort en
# in de taal van een dossier, want ze komen straks in het reviewmemorandum.
TE_BEOORDELEN = "Te beoordelen"
REVIEWSTATUSSEN: tuple[str, ...] = (
    TE_BEOORDELEN,
    "Beoordeeld, geen actie",
    "Actie nodig",
    "Opgelost",
    "Niet van toepassing",
)

# Welke van die statussen betekenen dat de bevinding is afgehandeld. Het
# memorandum zet die achteraan in plaats van tussen de punten die nog aandacht
# vragen; "Actie nodig" hoort daar niet bij, want dat is juist een openstaand
# punt. Deze indeling staat hier omdat de statussen hier worden vastgesteld:
# wordt er een status bij gezet of hernoemd, dan valt het hier op en niet pas
# in het document.
AFGEHANDELDE_STATUSSEN: tuple[str, ...] = (
    "Beoordeeld, geen actie",
    "Opgelost",
    "Niet van toepassing",
)

BEVINDING_COLUMNS = [
    "ernst",
    "categorie",
    "onderwerp",
    "bedrag",
    "aantal_regels",
    "rekening",
    "boven_drempel",
    "methode",
    "toelichting",
    "pagina",
    "sleutel",
]


@dataclass(frozen=True)
class Bevinding:
    """Eén bevinding, los van de controle die haar heeft opgeleverd."""

    categorie: str
    onderwerp: str
    ernst: str
    toelichting: str = ""
    bedrag: float | None = None
    aantal_regels: int | None = None
    rekening: str = ""
    methode: str = ""
    pagina: str = ""

    @property
    def sleutel(self) -> str:
        """Stabiele verwijzing naar deze bevinding.

        Nodig om er iets aan te kunnen hangen dat de gebruiker invoert, zoals
        een reviewstatus of een notitie: die moet dezelfde bevinding terugvinden
        bij een volgende analyse van hetzelfde dossier. Daarom geen index of
        rijnummer, maar een hash van wat de bevinding aanwijst. Het bedrag zit er
        bewust niet in, zodat een gewijzigd bedrag de status niet weggooit; de
        gebruiker ziet het bedrag zelf en beoordeelt opnieuw als dat nodig is.
        """
        ruw = "|".join([self.categorie, self.onderwerp, self.rekening]).encode("utf-8")
        return hashlib.blake2b(ruw, digest_size=6).hexdigest()


@dataclass(frozen=True)
class Materialiteit:
    """De drempel waarboven een bedrag de moeite van beoordelen waard is.

    Twee grenzen naast elkaar, zoals in de praktijk: een vast bedrag en een
    percentage van een grondslag. De hoogste van de twee geldt, zodat een klein
    dossier niet op een absolute drempel vastloopt en een groot dossier niet in
    kleine posten verzuipt. Dit is een werkafspraak van de gebruiker en geen
    norm uit wet of standaard.
    """

    absoluut: float = 1000.0
    relatief_pct: float = 1.0
    grondslag: float = 0.0

    @property
    def drempel(self) -> float:
        return max(float(self.absoluut), abs(float(self.grondslag)) * float(self.relatief_pct) / 100.0)

    def boven_drempel(self, bedrag: float | None) -> bool:
        """Een bevinding zonder bedrag telt altijd mee: die is niet te wegen."""
        if bedrag is None or pd.isna(bedrag):
            return True
        return abs(float(bedrag)) >= self.drempel


def naar_frame(bevindingen: list[Bevinding], materialiteit: Materialiteit | None = None) -> pd.DataFrame:
    """Zet bevindingen om naar één tabel, gesorteerd op ernst en bedrag."""
    materialiteit = materialiteit or Materialiteit()
    if not bevindingen:
        return pd.DataFrame(columns=BEVINDING_COLUMNS)

    rijen = []
    for bevinding in bevindingen:
        rijen.append(
            {
                "ernst": bevinding.ernst,
                "categorie": bevinding.categorie,
                "onderwerp": bevinding.onderwerp,
                "bedrag": bevinding.bedrag,
                "aantal_regels": bevinding.aantal_regels,
                "rekening": bevinding.rekening,
                "boven_drempel": materialiteit.boven_drempel(bevinding.bedrag),
                "methode": bevinding.methode,
                "toelichting": bevinding.toelichting,
                "pagina": bevinding.pagina,
                "sleutel": bevinding.sleutel,
            }
        )
    frame = pd.DataFrame(rijen, columns=BEVINDING_COLUMNS)
    # Een bevinding zonder bedrag laat de kolom als object-dtype achter; de
    # omzetting houdt hem numeriek, zoals elke bedragkolom in deze tool.
    frame["bedrag"] = pd.to_numeric(frame["bedrag"], errors="coerce")
    frame["aantal_regels"] = pd.to_numeric(frame["aantal_regels"], errors="coerce").astype("Int64")
    orde = {ernst: index for index, ernst in enumerate(ERNST_ORDE)}
    frame["_ernst"] = frame["ernst"].map(lambda ernst: orde.get(ernst, len(orde)))
    frame["_bedrag"] = frame["bedrag"].abs().fillna(0.0)
    return (
        frame.sort_values(["_ernst", "_bedrag"], ascending=[True, False])
        .drop(columns=["_ernst", "_bedrag"])
        .reset_index(drop=True)
    )


def pas_review_toe(
    bevindingen: pd.DataFrame, review: dict[str, dict[str, str]] | None = None
) -> pd.DataFrame:
    """Voeg de reviewstatus en de notitie van de gebruiker toe.

    De status hangt aan de sleutel van de bevinding en niet aan haar plaats in de
    lijst: bij een volgende analyse van hetzelfde dossier staat de lijst anders
    gesorteerd en kunnen er bevindingen bij komen of wegvallen. Een bevinding
    zonder vastgelegde status staat op "Te beoordelen"; dat is een feitelijke
    beschrijving en geen oordeel.
    """
    review = review or {}
    result = bevindingen.copy()
    if result.empty:
        result["status"] = pd.Series(dtype="object")
        result["notitie"] = pd.Series(dtype="object")
        return result

    result["status"] = [
        str(review.get(str(sleutel), {}).get("status") or TE_BEOORDELEN)
        for sleutel in result["sleutel"]
    ]
    result["notitie"] = [
        str(review.get(str(sleutel), {}).get("notitie") or "") for sleutel in result["sleutel"]
    ]
    return result


def openstaande_bevindingen(bevindingen: pd.DataFrame) -> int:
    """Hoeveel bevindingen nog een beoordeling missen."""
    if bevindingen.empty or "status" not in bevindingen.columns:
        return len(bevindingen)
    return int((bevindingen["status"] == TE_BEOORDELEN).sum())


def samenvatting_per_ernst(bevindingen: pd.DataFrame) -> dict[str, int]:
    """Aantal bevindingen per ernstniveau."""
    niveaus = (KRITIEK, WAARSCHUWING, SIGNAAL, NIET_MOGELIJK)
    if bevindingen.empty:
        return {niveau: 0 for niveau in niveaus}
    telling = bevindingen["ernst"].value_counts().to_dict()
    return {niveau: int(telling.get(niveau, 0)) for niveau in niveaus}


# --- Verzamelen -------------------------------------------------------------

# Verschillen kleiner dan een halve cent zijn afrondingsruis.
TOLERANTIE = 0.005


def _getal(waarde) -> float | None:
    """Een bedrag als getal, of niets wanneer het er niet is."""
    if waarde is None:
        return None
    getal = pd.to_numeric(waarde, errors="coerce")
    return None if pd.isna(getal) else float(getal)


def _aantal(waarde) -> int | None:
    getal = pd.to_numeric(waarde, errors="coerce")
    return None if pd.isna(getal) else int(getal)


def _uit_bestandenpaar(vorig: Auditfile, huidig: Auditfile) -> list[Bevinding]:
    from .comparison import controleer_bestandenpaar

    bevindingen = []
    for _, rij in controleer_bestandenpaar(vorig, huidig).iterrows():
        if rij["ernst"] == IN_ORDE:
            continue
        bevindingen.append(
            Bevinding(
                categorie="Bestandenpaar",
                onderwerp=str(rij["controle"]),
                ernst=str(rij["ernst"]),
                toelichting=str(rij["bevinding"]),
                pagina="Bestandscontrole",
            )
        )
    return bevindingen


def _uit_integriteit(af: Auditfile, aanduiding: str) -> list[Bevinding]:
    from .integrity import controleer_auditfile

    bevindingen = []
    for _, rij in controleer_auditfile(af).iterrows():
        if rij["ernst"] == IN_ORDE:
            continue
        bevindingen.append(
            Bevinding(
                categorie=f"Bestandscontrole {aanduiding}",
                onderwerp=str(rij["controle"]),
                ernst=str(rij["ernst"]),
                toelichting=str(rij["bevinding"]),
                bedrag=_getal(rij.get("verschil")),
                aantal_regels=_aantal(rij.get("aantal")),
                pagina="Bestandscontrole",
            )
        )
    return bevindingen


def _uit_jaarovergang(vorig: Auditfile, huidig: Auditfile) -> list[Bevinding]:
    from .comparison import build_jaarovergang, build_jaarovergang_verloop

    bevindingen = []
    verloop = build_jaarovergang_verloop(vorig, huidig)
    if not verloop.empty:
        per_post = verloop.set_index("post")["bedrag"]
        for post, onderwerp in (
            ("Verschil buiten het eigen vermogen", "Beginbalans sluit niet aan op vorig jaar"),
            (
                "Onverklaard in het eigen vermogen",
                "Verandering in het eigen vermogen volgt niet uit het resultaat",
            ),
        ):
            bedrag = _getal(per_post.get(post))
            if bedrag is None or abs(bedrag) < TOLERANTIE:
                continue
            toelichting = str(
                verloop.loc[verloop["post"] == post, "toelichting"].iloc[0]
            )
            bevindingen.append(
                Bevinding(
                    categorie="Jaarovergang",
                    onderwerp=onderwerp,
                    ernst=KRITIEK,
                    toelichting=toelichting,
                    bedrag=bedrag,
                    pagina="Bestandscontrole",
                )
            )

    overgang = build_jaarovergang(vorig, huidig)
    if not overgang.empty:
        afwijkend = overgang[
            (overgang["signaal"] != "") & (overgang["signaal"] != "Resultaatbestemming eigen vermogen")
        ]
        for _, rij in afwijkend.iterrows():
            bevindingen.append(
                Bevinding(
                    categorie="Jaarovergang",
                    onderwerp=str(rij["signaal"]),
                    ernst=SIGNAAL,
                    toelichting=(
                        f"Rekening {rij['rekening']} {rij['accDesc']}: eindsaldo vorig jaar "
                        f"{euro(rij['eindsaldo_vorig'])} tegenover beginsaldo "
                        f"{euro(rij['beginsaldo_huidig'])}."
                    ),
                    bedrag=_getal(rij["verschil"]),
                    rekening=str(rij["rekening"]),
                    pagina="Bestandscontrole",
                )
            )
    return bevindingen


def _uit_btw(af: Auditfile, gebruik: pd.DataFrame, samenvatting: pd.DataFrame) -> list[Bevinding]:
    from . import vat

    bevindingen = []
    for _, rij in vat.build_vat_anomalies(af, gebruik).iterrows():
        bevindingen.append(
            Bevinding(
                categorie="Btw",
                onderwerp=str(rij["signaal"]),
                ernst=SIGNAAL,
                toelichting=str(rij["toelichting"]),
                bedrag=_getal(rij.get("bedrag")),
                aantal_regels=_aantal(rij.get("aantal_regels")),
                pagina="Btw",
            )
        )

    status = vat.voorstelstatus(gebruik)
    if status["voorstellen"]:
        bevindingen.append(
            Bevinding(
                categorie="Btw",
                onderwerp="Btw-indeling nog niet beoordeeld",
                ernst=WAARSCHUWING,
                toelichting=(
                    f"{status['voorstellen']} van de {status['codes']} btw-codes staan nog op "
                    "een voorstel van de tool. De btw-positie is daarmee een rekenvoorbeeld "
                    "en geen beoordeelde uitkomst."
                ),
                bedrag=_getal(status["btw_op_voorstel"]),
                pagina="Btw",
            )
        )

    if samenvatting.empty:
        return bevindingen

    niet_ingevuld = samenvatting[samenvatting["status"] == "Niet ingevuld"]
    if not niet_ingevuld.empty:
        bevindingen.append(
            Bevinding(
                categorie="Btw",
                onderwerp="Aansluiting met de aangifte niet gemaakt",
                ernst=NIET_MOGELIJK,
                toelichting=(
                    f"Voor {len(niet_ingevuld)} rubriek(en) is geen aangiftebedrag ingevoerd: "
                    + ", ".join(niet_ingevuld["rubriek"])
                    + ". De vergelijking met de ingediende aangifte is daarmee niet gemaakt."
                ),
                pagina="Btw",
            )
        )

    ernst_per_status = {
        "Verschil": WAARSCHUWING,
        "Alleen in de aangifte": WAARSCHUWING,
        "Verschil in grondslag": SIGNAAL,
    }
    for _, rij in samenvatting.iterrows():
        ernst = ernst_per_status.get(str(rij["status"]))
        if ernst is None:
            continue
        if str(rij["status"]) == "Verschil in grondslag":
            bedrag = _getal(rij.get("verschil_grondslag"))
            toelichting = (
                f"De btw sluit aan, maar de grondslag wijkt af: volgens het auditfile "
                f"{euro(rij['grondslag_volgens_xaf'])} tegenover "
                f"{euro(rij['grondslag_volgens_aangifte'])} volgens de aangifte."
            )
        else:
            bedrag = _getal(rij.get("verschil"))
            toelichting = (
                f"Volgens het auditfile {euro(rij['btw_volgens_xaf'])} tegenover "
                f"{euro(rij['btw_volgens_aangifte'])} volgens de aangifte."
            )
        bevindingen.append(
            Bevinding(
                categorie="Btw",
                onderwerp=f"Rubriek {rij['rubriek']}: {str(rij['status']).lower()}",
                ernst=ernst,
                toelichting=toelichting,
                bedrag=bedrag,
                aantal_regels=_aantal(rij.get("aantal_regels")),
                pagina="Btw",
            )
        )
    return bevindingen


def _uit_controles(af: Auditfile) -> list[Bevinding]:
    from . import controls

    bevindingen = []

    periodiek = controls.build_periodieke_controles(af)
    if not periodiek.empty:
        for _, rij in periodiek[periodiek["conclusie"] != "Geen bijzonderheden"].iterrows():
            ernst = WAARSCHUWING if rij["conclusie"] == "Ontbrekende perioden" else SIGNAAL
            bevindingen.append(
                Bevinding(
                    categorie="Periodieke lasten",
                    onderwerp=f"{rij['controle']}: {str(rij['conclusie']).lower()}",
                    ernst=ernst,
                    toelichting=str(rij["toelichting"]),
                    bedrag=_getal(rij.get("totaalbedrag")),
                    rekening=str(rij["rekening"]),
                    methode=str(rij.get("methode", "")),
                    pagina="Analytische controles",
                )
            )

    for _, rij in controls.build_ongebruikelijke_boekingen(af).iterrows():
        bevindingen.append(
            Bevinding(
                categorie="Boekingen",
                onderwerp=str(rij["signaal"]),
                ernst=SIGNAAL,
                toelichting=str(rij["toelichting"]),
                bedrag=_getal(rij.get("bedrag")),
                aantal_regels=_aantal(rij.get("aantal_regels")),
                pagina="Analytische controles",
            )
        )

    for _, rij in controls.build_balanspost_signalen(af).iterrows():
        bevindingen.append(
            Bevinding(
                categorie="Balansposten",
                onderwerp=f"{rij['categorie']}: saldo aan de verkeerde kant",
                ernst=WAARSCHUWING,
                toelichting=str(rij["signaal"]),
                bedrag=_getal(rij.get("eindsaldo")),
                rekening=str(rij["rekening"]),
                methode=str(rij.get("methode", "")),
                pagina="Analytische controles",
            )
        )

    for _, rij in controls.build_fiscale_signalen(af).iterrows():
        bevindingen.append(
            Bevinding(
                categorie="Fiscaal",
                onderwerp=f"{rij['onderwerp']}: {rij['omschrijving']}",
                ernst=SIGNAAL,
                toelichting=str(rij["toelichting"]),
                bedrag=_getal(rij.get("bedrag")),
                aantal_regels=_aantal(rij.get("aantal_regels")),
                rekening=str(rij["rekening"]),
                pagina="Fiscale signalen",
            )
        )

    # Perioden zonder omzet of loonkosten worden samengevat. Twaalf losse
    # bevindingen voor twaalf maanden maken de lijst onleesbaar, terwijl het om
    # één vaststelling gaat.
    for bouwer, categorie, kolom in (
        (controls.build_omzet_per_periode, "Omzet per periode", "omzet"),
        (controls.build_personeelskosten_per_periode, "Loonkosten per periode", "loonkosten"),
    ):
        frame = bouwer(af)
        if frame.empty:
            continue
        for signaal, groep in frame[frame["signaal"] != ""].groupby("signaal"):
            perioden = controls.compacte_perioden(
                [int(periode) for periode in groep["periode"]], af.period_labels
            )
            # Bij een signaal over het ontbreken van iets is de som nul. Dat als
            # bedrag meegeven zou de bevinding onder elke materialiteitsdrempel
            # duwen, terwijl juist de afwezigheid het punt is.
            totaal = _getal(groep[kolom].sum())
            bedrag = totaal if totaal is not None and abs(totaal) >= TOLERANTIE else None
            bevindingen.append(
                Bevinding(
                    categorie=categorie,
                    onderwerp=str(signaal),
                    ernst=SIGNAAL,
                    toelichting=f"Betreft {len(groep)} periode(n): {perioden}.",
                    bedrag=bedrag,
                    aantal_regels=len(groep),
                    pagina="Analytische controles",
                )
            )

    for _, rij in controls.build_relatie_concentratie(af).iterrows():
        if not str(rij["signaal"]):
            continue
        bevindingen.append(
            Bevinding(
                categorie="Relaties",
                onderwerp=f"Concentratie {str(rij['soort']).lower()}",
                ernst=SIGNAAL,
                toelichting=str(rij["signaal"]),
                aantal_regels=_aantal(rij.get("aantal_relaties")),
                pagina="Relaties",
            )
        )
    return bevindingen


def _uit_capability(af: Auditfile) -> list[Bevinding]:
    """Wat het bestand niet toelaat, is ook een bevinding.

    Een memorandum dat zwijgt over een controle die niet kon worden uitgevoerd,
    wekt de indruk dat er niets aan de hand is. Daarom komt het bewijsniveau voor
    openstaande posten hier terug zodra het de uitspraak beperkt, en de
    RGS-dekking zodra de indeling op omschrijvingen moet terugvallen.
    """
    from .capability import (
        NIVEAU_GEEN,
        NIVEAU_NAAM,
        NIVEAU_RECONSTRUCTIE,
        NIVEAU_VERVALDATUM,
        openstaande_posten_niveau,
    )

    bevindingen = []
    niveau, uitleg = openstaande_posten_niveau(af)
    if niveau == NIVEAU_GEEN:
        bevindingen.append(
            Bevinding(
                categorie="Bestandsgegevens",
                onderwerp="Openstaande posten niet te bepalen",
                ernst=NIET_MOGELIJK,
                toelichting=uitleg,
                pagina="Bestandscontrole",
            )
        )
    elif niveau > NIVEAU_VERVALDATUM:
        bevindingen.append(
            Bevinding(
                categorie="Bestandsgegevens",
                onderwerp=f"Openstaande posten alleen op niveau {niveau}: {NIVEAU_NAAM[niveau].lower()}",
                ernst=SIGNAAL if niveau < NIVEAU_RECONSTRUCTIE else WAARSCHUWING,
                toelichting=uitleg,
                pagina="Bestandscontrole",
            )
        )

    rekeningen = len(af.accounts)
    if rekeningen:
        met_rgs = int((af.accounts["RGScode"].astype(str).str.strip() != "").sum())
        aandeel = met_rgs / rekeningen * 100
        if met_rgs == 0:
            bevindingen.append(
                Bevinding(
                    categorie="Bestandsgegevens",
                    onderwerp="Geen RGS-codes in het rekeningschema",
                    ernst=WAARSCHUWING,
                    toelichting="Elke controle die rekeningen selecteert valt terug op de "
                    "omschrijving. Dat werkt, maar het is minder hard dan een code uit het "
                    "bestand; de gebruikte methode staat per controle in de tabel.",
                    aantal_regels=rekeningen,
                    pagina="Bestandscontrole",
                )
            )
        elif aandeel < 99.5:
            bronnen = sorted({bron for bron in af.accounts["RGSbron"].astype(str) if bron})
            bevindingen.append(
                Bevinding(
                    categorie="Bestandsgegevens",
                    onderwerp="Rekeningschema maar gedeeltelijk van RGS-codes voorzien",
                    ernst=SIGNAAL,
                    toelichting=f"{met_rgs} van de {rekeningen} rekeningen hebben een code "
                    f"({aandeel:.0f}%), herkomst {' en '.join(bronnen) or 'onbekend'}. Voor de "
                    "rekeningen zonder code beslist de omschrijving.",
                    aantal_regels=rekeningen - met_rgs,
                    pagina="Bestandscontrole",
                )
            )
    return bevindingen


def _uit_relatiesaldi(af: Auditfile, top: int = 10) -> list[Bevinding]:
    """De openstaande bedragen per relatie uit XAF 4.0.

    Levert niets zolang het bestand die bedragen niet geeft; dat het niet kan,
    staat al in ``_uit_capability``. Een verschil met het grootboek is een
    waarschuwing en geen fout: er staan op een relatierekening vaker posten die
    niet aan een relatie hangen, zoals een verzamelboeking of een afboeking.
    """
    from .relatiesaldi import build_relatiesaldi, build_relatiesaldo_aansluiting

    aansluiting = build_relatiesaldo_aansluiting(af)
    if aansluiting.empty:
        return []

    bevindingen = []
    for _, rij in aansluiting.iterrows():
        if rij["signaal"] != "verschil":
            continue
        bevindingen.append(
            Bevinding(
                categorie="Relaties",
                onderwerp=f"Openstaande bedragen {rij['soort']}en sluiten niet aan op het grootboek",
                ernst=WAARSCHUWING,
                toelichting=str(rij["conclusie"]),
                bedrag=_getal(rij.get("verschil_eind")),
                aantal_regels=_aantal(rij.get("aantal_relaties")),
                methode=str(rij["methode"]),
                pagina="Relaties",
            )
        )

    saldi = build_relatiesaldi(af)
    if saldi.empty:
        return bevindingen

    afwijkend_teken = saldi[
        saldi["signaal"].str.startswith(("Debiteur", "Crediteur"))
    ].reindex(saldi["openstaand_eind"].abs().sort_values(ascending=False).index).dropna(how="all")
    for _, rij in afwijkend_teken.head(top).iterrows():
        naam = rij["naam"] or rij["relatie"]
        bevindingen.append(
            Bevinding(
                categorie="Relaties",
                onderwerp=f"{rij['soort'].capitalize()} {rij['relatie']} staat aan de andere kant",
                ernst=SIGNAAL,
                toelichting=f"{naam}: {rij['signaal']}",
                bedrag=_getal(rij.get("openstaand_eind")),
                pagina="Relaties",
            )
        )

    verloop = saldi[saldi["verloop_verschil"].abs() > 0.005]
    if not verloop.empty:
        bevindingen.append(
            Bevinding(
                categorie="Relaties",
                onderwerp="Verloop van de openstaande bedragen sluit niet op de boekingen aan",
                ernst=WAARSCHUWING,
                toelichting=f"Bij {len(verloop)} relatie(s) geeft de beginstand plus de mutaties "
                "van het boekjaar niet de eindstand uit het bestand. De standen zijn dan niet uit "
                "het grootboek af te leiden; beoordeel welke boekingen buiten de relatierekening "
                "om zijn gegaan.",
                bedrag=float(verloop["verloop_verschil"].abs().sum()),
                aantal_regels=len(verloop),
                pagina="Relaties",
            )
        )
    return bevindingen


def _uit_openstaande_posten(af: Auditfile, top: int = 10) -> list[Bevinding]:
    """De openstaande posten uit de subadministratie van XAF 3.2.

    Levert niets zolang het bestand geen subadministratie heeft; dat het niet
    kan, staat al in ``_uit_capability``. De ouderdom is hier het zwaarste
    punt: een post die lang over de vervaldatum is, vraagt om een oordeel over
    de inbaarheid, en een post waarvan de ouderdom niet te bepalen valt vraagt
    om een oordeel over het bestand.
    """
    from .openstaand import (
        BASIS_VERVALDATUM,
        KLASSE_ONBEKEND,
        KLASSE_OUDER_DAN_90,
        bepaal_peildatum,
        build_openstaand_aansluiting,
        build_openstaande_posten,
        heeft_openstaande_posten,
    )

    if not heeft_openstaande_posten(af):
        return []

    peil, herkomst = bepaal_peildatum(af)
    posten = build_openstaande_posten(af, peil)
    bevindingen = []

    for _, rij in build_openstaand_aansluiting(af, peil).iterrows():
        if rij["signaal"] == "verschil":
            bevindingen.append(
                Bevinding(
                    categorie="Openstaande posten",
                    onderwerp=f"Openstaande posten {rij['soort']}en sluiten niet aan op het grootboek",
                    ernst=WAARSCHUWING,
                    toelichting=str(rij["conclusie"]),
                    bedrag=_getal(rij.get("verschil")),
                    aantal_regels=_aantal(rij.get("aantal_posten")),
                    methode=str(rij["methode"]),
                    pagina="Relaties",
                )
            )
        elif rij["signaal"] == "niet mogelijk" and rij["soort"] == "niet ingedeeld":
            bevindingen.append(
                Bevinding(
                    categorie="Openstaande posten",
                    onderwerp="Openstaande posten zonder indeling als debiteur of crediteur",
                    ernst=NIET_MOGELIJK,
                    toelichting=str(rij["conclusie"]),
                    bedrag=_getal(rij.get("openstaand")),
                    aantal_regels=_aantal(rij.get("aantal_posten")),
                    pagina="Relaties",
                )
            )

    if posten.empty:
        return bevindingen

    oud = posten[posten["ouderdomsklasse"] == KLASSE_OUDER_DAN_90]
    for soort, groep in oud.groupby("soort", sort=False):
        vanaf_vervaldatum = int((groep["basis"] == BASIS_VERVALDATUM).sum())
        bevindingen.append(
            Bevinding(
                categorie="Openstaande posten",
                onderwerp=f"Openstaande posten ouder dan 90 dagen bij de {soort or 'niet ingedeelde'}en",
                ernst=WAARSCHUWING,
                toelichting=(
                    f"{len(groep)} post(en) staan op {herkomst} meer dan 90 dagen open, "
                    f"waarvan {vanaf_vervaldatum} gerekend vanaf de vervaldatum en de rest "
                    "vanaf de factuurdatum. Beoordeel de inbaarheid en de noodzaak van een "
                    "voorziening."
                ),
                bedrag=float(groep["openstaand"].sum()),
                aantal_regels=len(groep),
                pagina="Relaties",
            )
        )

    onbekend = posten[posten["ouderdomsklasse"] == KLASSE_ONBEKEND]
    if not onbekend.empty:
        bevindingen.append(
            Bevinding(
                categorie="Openstaande posten",
                onderwerp="Ouderdom van openstaande posten niet te bepalen",
                ernst=NIET_MOGELIJK,
                toelichting=(
                    f"{len(onbekend)} post(en) hebben geen factuur- en geen vervaldatum. Zij "
                    "staan wel in het totaal maar vallen buiten de ouderdomsopbouw; de "
                    "opbouw is daardoor onvolledig."
                ),
                bedrag=float(onbekend["openstaand"].sum()),
                aantal_regels=len(onbekend),
                pagina="Relaties",
            )
        )

    # Op teken en soort, niet op de tekst van het signaal: een post aan de
    # verkeerde kant blijft dat ook wanneer de formulering verandert.
    verkeerde_kant = posten[
        ((posten["soort"] == "debiteur") & (posten["openstaand"] < 0))
        | ((posten["soort"] == "crediteur") & (posten["openstaand"] > 0))
    ]
    for _, rij in verkeerde_kant.head(top).iterrows():
        naam = rij["naam"] or rij["relatie"] or rij["sleutel"]
        bevindingen.append(
            Bevinding(
                categorie="Openstaande posten",
                onderwerp=f"Post {rij['sleutel']} staat aan de andere kant",
                ernst=SIGNAAL,
                toelichting=f"{naam}: {rij['signaal']}",
                bedrag=_getal(rij.get("openstaand")),
                rekening=str(rij["rekening"]),
                pagina="Relaties",
            )
        )
    return bevindingen


def _uit_excessief_lenen(af: Auditfile, invoer=None) -> list[Bevinding]:
    """De drempeltoets bij de Wet excessief lenen bij eigen vennootschap.

    De ernst is een waarschuwing en geen kritieke bevinding, ook boven de
    drempel. De tool meet één vennootschap op de balansdatum; de wettelijke
    toets gaat over alle vennootschappen van de belastingplichtige en zijn
    partner op 31 december. Wat de tool ziet is dus een sterk signaal en geen
    vaststelling. Zie ``excessief_lenen.py`` voor de vijf punten die daartussen
    zitten.
    """
    from .excessief_lenen import (
        STATUS_BOVEN,
        STATUS_GEEN_REKENING,
        beoordeel,
        conclusie,
    )

    toets = beoordeel(af, invoer)
    if toets.status == STATUS_GEEN_REKENING:
        # Geen rekening-courant gevonden is geen bevinding: er is niets gezien.
        # Dat de selectie een afwijkend gecodeerde rekening kan missen, staat op
        # de eigen pagina en niet als bevinding, want anders zou elk dossier
        # zonder rekening-courant er een bevinding bij krijgen.
        return []

    ernst = toets.ernst
    if ernst is None:
        return []

    bedrag = toets.bovenmatig if toets.status == STATUS_BOVEN else toets.te_toetsen
    rekeningen = ", ".join(
        str(rekening) for rekening in build_rc_rekeningnummers(af)
    )
    return [
        Bevinding(
            categorie="Fiscaal",
            onderwerp=f"Rekening-courant en leningen aandeelhouder: {toets.status}",
            ernst=ernst,
            toelichting=conclusie(toets),
            bedrag=_getal(bedrag),
            aantal_regels=toets.rekeningen or None,
            rekening=rekeningen,
            methode=toets.methode,
            pagina="Fiscale signalen",
        )
    ]


def build_rc_rekeningnummers(af: Auditfile) -> list[str]:
    """De rekeningnummers achter de drempeltoets, voor de bevinding."""
    from .excessief_lenen import build_rc_rekeningen

    rekeningen = build_rc_rekeningen(af)
    if rekeningen.empty:
        return []
    return [str(nummer) for nummer in rekeningen["rekening"]]


def _uit_jaarvergelijking(vergelijking: pd.DataFrame, top: int = 10) -> list[Bevinding]:
    from .comparison import build_opvallende_verschillen

    opvallend = build_opvallende_verschillen(vergelijking)
    if opvallend.empty:
        return []
    bevindingen = []
    for _, rij in opvallend.head(top).iterrows():
        bevindingen.append(
            Bevinding(
                categorie="Jaarvergelijking",
                onderwerp=f"{rij['status'].capitalize()}: {rij['accDesc'] or rij['rekening']}",
                ernst=SIGNAAL,
                toelichting=(
                    f"Rekening {rij['rekening']}: {euro(rij['saldo_vorig'])} vorig jaar "
                    f"tegenover {euro(rij['saldo_huidig'])} dit jaar."
                ),
                bedrag=_getal(rij.get("verschil_bedrag")),
                rekening=str(rij["rekening"]),
                pagina="Jaarvergelijking",
            )
        )
    return bevindingen


def _uit_ratios(huidig: Auditfile, vorig: Auditfile | None) -> list[Bevinding]:
    """De ratio-analyse als bevindingen.

    Het bedrag bij een verschuiving is het geldeffect ervan: de verschuiving in
    procentpunten toegepast op de noemer van dit jaar. Zonder zo'n bedrag zou de
    materialiteit niets op deze bevindingen kunnen toepassen, en vijf procentpunt
    betekent bij een kleine omzet iets anders dan bij een grote. De toelichting
    zegt erbij hoe het bedrag is bepaald, zodat het niet voor een gemeten post
    wordt aangezien.
    """
    from .ratios import build_ratios

    ratios = build_ratios(huidig, vorig)
    if ratios.empty:
        return []

    bevindingen = []
    for _, rij in ratios.iterrows():
        ernst = str(rij["ernst"])
        if ernst == IN_ORDE:
            continue
        naam = str(rij["ratio"])
        signaal = str(rij["signaal"] or "")
        eenheid = str(rij["eenheid"])
        bedrag = None
        if ernst == NIET_MOGELIJK:
            toelichting = signaal or f"De {naam.lower()} is niet te bepalen."
        else:
            waarde = _getal(rij.get("waarde_huidig"))
            stand = ""
            if waarde is not None:
                stand = procent(waarde) if eenheid == "%" else getal(waarde)
            toelichting = f"{naam}: {stand}. {signaal}".strip() if stand else signaal
            verschuiving = _getal(rij.get("verschuiving"))
            teller = _getal(rij.get("teller_bedrag"))
            noemer = _getal(rij.get("noemer_bedrag"))
            if naam == "Solvabiliteit" and teller is not None and teller < 0:
                bedrag = teller
            elif eenheid == "%" and verschuiving is not None and noemer is not None:
                bedrag = abs(verschuiving) / 100.0 * abs(noemer)
                toelichting += (
                    f" Het bedrag is de verschuiving van {getal(abs(verschuiving), 1)} procentpunt "
                    "toegepast op de noemer van dit jaar."
                )
            elif eenheid == "x" and teller is not None and noemer is not None:
                bedrag = noemer - teller
                toelichting += (
                    " Het bedrag is het tekort ten opzichte van de kortlopende schulden."
                )
        bevindingen.append(
            Bevinding(
                categorie="Ratio's",
                onderwerp=naam,
                ernst=ernst,
                toelichting=toelichting,
                bedrag=bedrag,
                methode=str(rij["methode"]),
                pagina="Jaarvergelijking",
            )
        )
    return bevindingen


def grondslag_omzet(af: Auditfile) -> float:
    """De omzet van het boekjaar, als grondslag voor de materialiteit.

    De omzet is in de samenstelpraktijk de gebruikelijke grondslag. Wordt er
    geen omzetrekening herkend, dan is de grondslag nul en geldt alleen de
    absolute drempel; een verzonnen grondslag zou de drempel onnavolgbaar maken.
    """
    from .controls import _selecteer
    from .ratios import OMZET_PATROON, OMZET_RGS

    if af.saldo.empty:
        return 0.0
    # Dezelfde omzetdefinitie als de ratio-analyse. Twee definities zouden een
    # materialiteit opleveren die op een andere omzet rust dan de brutomarge.
    masker, _ = _selecteer(af.saldo, OMZET_RGS, OMZET_PATROON, rekeningtype="P")
    return abs(float(af.saldo.loc[masker, "mutaties_boekjaar"].sum()))


def verzamel_bevindingen(
    huidig: Auditfile,
    vorig: Auditfile | None = None,
    gebruik: pd.DataFrame | None = None,
    vergelijking: pd.DataFrame | None = None,
    aangifte: dict[str, float] | None = None,
    grondslagen: dict[str, float] | None = None,
    materialiteit: Materialiteit | None = None,
    excessief_lenen=None,
) -> pd.DataFrame:
    """Alle bevindingen van alle controles in één tabel.

    Ontbreken ``gebruik`` of ``vergelijking``, dan worden ze hier berekend, zodat
    deze functie ook buiten de app te gebruiken is.
    """
    from . import vat
    from .comparison import compare_saldi

    if gebruik is None:
        gebruik = vat.pas_mapping_toe(vat.build_vat_usage(huidig))
    samenvatting = vat.build_rubric_summary(gebruik, aangifte, grondslagen)

    bevindingen: list[Bevinding] = []
    if vorig is not None:
        bevindingen += _uit_bestandenpaar(vorig, huidig)
        bevindingen += _uit_integriteit(vorig, f"{vorig.boekjaar or 'vorig jaar'}")
        bevindingen += _uit_jaarovergang(vorig, huidig)
        if vergelijking is None:
            vergelijking = compare_saldi(vorig, huidig)
        bevindingen += _uit_jaarvergelijking(vergelijking)
    bevindingen += _uit_integriteit(huidig, f"{huidig.boekjaar or 'huidig jaar'}")
    bevindingen += _uit_capability(huidig)
    bevindingen += _uit_btw(huidig, gebruik, samenvatting)
    bevindingen += _uit_controles(huidig)
    bevindingen += _uit_relatiesaldi(huidig)
    bevindingen += _uit_openstaande_posten(huidig)
    bevindingen += _uit_excessief_lenen(huidig, excessief_lenen)
    bevindingen += _uit_ratios(huidig, vorig)

    return naar_frame(bevindingen, materialiteit)
