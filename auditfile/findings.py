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

# Vierde niveau naast die van integrity.py: iets om naar te kijken.
SIGNAAL = "signaal"

# Van zwaar naar licht, voor de sortering.
ERNST_ORDE: tuple[str, ...] = (KRITIEK, WAARSCHUWING, SIGNAAL, NIET_MOGELIJK, IN_ORDE)

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
                        f"{rij['eindsaldo_vorig']:.2f} tegenover beginsaldo "
                        f"{rij['beginsaldo_huidig']:.2f}."
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
                f"{rij['grondslag_volgens_xaf']:.2f} tegenover "
                f"{rij['grondslag_volgens_aangifte']:.2f} volgens de aangifte."
            )
        else:
            bedrag = _getal(rij.get("verschil"))
            toelichting = (
                f"Volgens het auditfile {rij['btw_volgens_xaf']:.2f} tegenover "
                f"{rij['btw_volgens_aangifte']:.2f} volgens de aangifte."
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
                    f"Rekening {rij['rekening']}: {rij['saldo_vorig']:.2f} vorig jaar tegenover "
                    f"{rij['saldo_huidig']:.2f} dit jaar."
                ),
                bedrag=_getal(rij.get("verschil_bedrag")),
                rekening=str(rij["rekening"]),
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

    if af.saldo.empty:
        return 0.0
    masker, _ = _selecteer(
        af.saldo, "WOmz", r"omzet|opbrengst|verkoop|provisie|\brevenue\b", rekeningtype="P"
    )
    return abs(float(af.saldo.loc[masker, "mutaties_boekjaar"].sum()))


def verzamel_bevindingen(
    huidig: Auditfile,
    vorig: Auditfile | None = None,
    gebruik: pd.DataFrame | None = None,
    vergelijking: pd.DataFrame | None = None,
    aangifte: dict[str, float] | None = None,
    grondslagen: dict[str, float] | None = None,
    materialiteit: Materialiteit | None = None,
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
    bevindingen += _uit_btw(huidig, gebruik, samenvatting)
    bevindingen += _uit_controles(huidig)

    return naar_frame(bevindingen, materialiteit)
