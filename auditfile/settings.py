"""Opslag van invoer die de gebruiker zelf doet, gescheiden per dossier.

Aangiftebedragen, grondslagen, de koppeling van btw-codes aan aangifterubrieken
en het aftrekbare aandeel per code zijn klant-afgeleide gegevens: de btw-codes
komen uit het auditfile van een klant. Ze worden daarom uitsluitend bewaard in
een door Git genegeerde lokale datamap, nooit in een gevolgd bestand.

Scheiding per dossier
---------------------
Die invoer hoort bij één onderneming en één boekjaar. Werd hij op één vaste plek
bewaard, dan verscheen de beoordeling van dossier A bij dossier B zodra daar
dezelfde btw-codes voorkwamen, en dat is zowel fiscaal als qua privacy
onaanvaardbaar. Elk dossier heeft daarom zijn eigen map onder
``.local-testdata/dossiers/<sleutel>``.

De sleutel is een korte hash van onderneming plus boekjaar (zie
``Auditfile.dossier_sleutel``), zodat er geen ondernemingsnaam of nummer in een
mapnaam op schijf staat. Binnen die map staat een ``dossier.json`` met naam en
boekjaar, zodat te zien is welke dossiers er lokaal liggen; die inhoud valt
onder dezelfde genegeerde datamap als de rest.

Er wordt niets weggeschreven bij het openen van een auditfile. Pas wanneer de
gebruiker invoer bewaart, ontstaat de map. Het openen van een bestand laat dus
geen spoor achter.

Deze module staat los van Streamlit, zodat de opslag te testen is zonder de app
te starten. ``tests/test_runtime_data_not_tracked.py`` borgt de scheiding.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
from pathlib import Path

# Deze map staat in .gitignore en mag nooit door Git worden gevolgd.
LOCAL_DATA_DIR = Path(".local-testdata")
DOSSIER_DIR = LOCAL_DATA_DIR / "dossiers"

# Bestandsnamen binnen een dossiermap.
AANGIFTE_BESTAND = "btw_aangifte.json"
MAPPING_BESTAND = "btw_mapping.json"
AFTREK_BESTAND = "btw_aftrekbaarheid.json"
GRONDSLAG_BESTAND = "btw_grondslagen.json"
DOSSIER_BESTAND = "dossier.json"
REVIEW_BESTAND = "bevindingen_review.json"
EXCESSIEF_BESTAND = "excessief_lenen.json"

# De paden van vóór de scheiding per dossier. Ze worden niet meer geschreven,
# alleen nog gelezen om invoer uit een oudere versie te kunnen overnemen.
BTW_AANGIFTE_PATH = LOCAL_DATA_DIR / AANGIFTE_BESTAND
BTW_MAPPING_PATH = LOCAL_DATA_DIR / MAPPING_BESTAND
BTW_AFTREK_PATH = LOCAL_DATA_DIR / AFTREK_BESTAND
BTW_GRONDSLAG_PATH = LOCAL_DATA_DIR / GRONDSLAG_BESTAND

OUDE_PADEN = (
    BTW_AANGIFTE_PATH,
    BTW_MAPPING_PATH,
    BTW_AFTREK_PATH,
    BTW_GRONDSLAG_PATH,
)


def _lees(path: Path) -> dict:
    """Lees een JSON-object; geef een lege dict bij elk probleem.

    Leest uitsluitend en veroorzaakt geen Git-wijziging.
    """
    if not path.exists():
        return {}
    try:
        inhoud = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return inhoud if isinstance(inhoud, dict) else {}


def _schrijf(inhoud: dict, path: Path) -> bool:
    """Schrijf een JSON-object naar de lokale datamap.

    Geeft terug of het schrijven is gelukt. Een schrijfprobleem mag de app niet
    onderbreken, maar wordt wel gemeld in plaats van stil te verdwijnen.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inhoud, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        return False
    return True


def _als_getallen(inhoud: dict) -> dict[str, float]:
    """Alleen de waarden die een getal zijn.

    Een onleesbare waarde wordt overgeslagen in plaats van de hele invoer te
    laten vervallen.
    """
    waarden: dict[str, float] = {}
    for sleutel, waarde in inhoud.items():
        try:
            waarden[str(sleutel)] = float(waarde)
        except (TypeError, ValueError):
            continue
    return waarden


@dataclass(frozen=True)
class DossierOpslag:
    """De lokale opslag van één dossier: één onderneming, één boekjaar.

    Een lege sleutel betekent dat het dossier niet te identificeren is. Dan
    wordt er niets gelezen en niets geschreven, in plaats van invoer te bewaren
    op een plek die morgen bij een ander dossier hoort.
    """

    sleutel: str
    map: Path

    @classmethod
    def voor(cls, sleutel: str, basis: Path = DOSSIER_DIR) -> DossierOpslag:
        return cls(sleutel=sleutel, map=basis / sleutel if sleutel else basis)

    @property
    def bruikbaar(self) -> bool:
        return bool(self.sleutel)

    def pad(self, bestand: str) -> Path:
        return self.map / bestand

    def _lees_bestand(self, bestand: str) -> dict:
        return _lees(self.pad(bestand)) if self.bruikbaar else {}

    def _schrijf_bestand(self, inhoud: dict, bestand: str) -> bool:
        if not self.bruikbaar:
            return False
        return _schrijf(inhoud, self.pad(bestand))

    # --- Eigen invoer -------------------------------------------------------

    def lees_aangifte(self) -> dict[str, float]:
        """De aangegeven omzetbelasting per rubriek."""
        return _als_getallen(self._lees_bestand(AANGIFTE_BESTAND))

    def schrijf_aangifte(self, aangifte: dict) -> bool:
        return self._schrijf_bestand(aangifte, AANGIFTE_BESTAND)

    def lees_grondslagen(self) -> dict[str, float]:
        """Het aangegeven bedrag waarover de omzetbelasting is berekend."""
        return _als_getallen(self._lees_bestand(GRONDSLAG_BESTAND))

    def schrijf_grondslagen(self, grondslagen: dict) -> bool:
        return self._schrijf_bestand(grondslagen, GRONDSLAG_BESTAND)

    def lees_mapping(self) -> dict[str, str]:
        """De vastgelegde koppeling van btw-code aan aangifterubriek."""
        return {
            str(code): str(rubriek)
            for code, rubriek in self._lees_bestand(MAPPING_BESTAND).items()
        }

    def schrijf_mapping(self, mapping: dict) -> bool:
        return self._schrijf_bestand(mapping, MAPPING_BESTAND)

    def lees_aftrekbaarheid(self) -> dict[str, float]:
        """Het aftrekbare aandeel per btw-code, in procenten."""
        return _als_getallen(self._lees_bestand(AFTREK_BESTAND))

    def schrijf_aftrekbaarheid(self, aandelen: dict) -> bool:
        return self._schrijf_bestand(aandelen, AFTREK_BESTAND)

    def lees_review(self) -> dict[str, dict[str, str]]:
        """De reviewstatus en notitie per bevinding, op sleutel.

        Een status van een bevinding die niet meer voorkomt blijft staan. Dat is
        opzet: komt de bevinding terug, dan is de notitie er weer. Stilzwijgend
        opruimen zou invoer van de gebruiker weggooien.
        """
        review = {}
        for sleutel, waarde in self._lees_bestand(REVIEW_BESTAND).items():
            if not isinstance(waarde, dict):
                continue
            review[str(sleutel)] = {
                "status": str(waarde.get("status", "")),
                "notitie": str(waarde.get("notitie", "")),
            }
        return review

    def schrijf_review(self, review: dict) -> bool:
        return self._schrijf_bestand(review, REVIEW_BESTAND)

    def lees_excessief_lenen(self) -> dict[str, float]:
        """De dossiergegevens bij de drempeltoets excessief lenen.

        Dit zijn bedragen die niet in een grootboek staan: de eigenwoningschuld
        met hypotheekrecht, de schulden aan andere vennootschappen en het eerder
        belaste fictieve reguliere voordeel.
        """
        return _als_getallen(self._lees_bestand(EXCESSIEF_BESTAND))

    def schrijf_excessief_lenen(self, gegevens: dict) -> bool:
        return self._schrijf_bestand(gegevens, EXCESSIEF_BESTAND)

    # --- Dossiergegevens ----------------------------------------------------

    def lees_label(self) -> dict[str, str]:
        """Naam en boekjaar van het dossier, om het terug te kunnen vinden."""
        return {
            str(sleutel): str(waarde)
            for sleutel, waarde in self._lees_bestand(DOSSIER_BESTAND).items()
        }

    def schrijf_label(self, naam: str, boekjaar: str) -> bool:
        return self._schrijf_bestand(
            {"naam": str(naam), "boekjaar": str(boekjaar)}, DOSSIER_BESTAND
        )

    @property
    def heeft_invoer(self) -> bool:
        """Staat er invoer van de gebruiker in dit dossier?"""
        if not self.bruikbaar:
            return False
        return any(
            self.pad(bestand).exists()
            for bestand in (
                AANGIFTE_BESTAND,
                MAPPING_BESTAND,
                AFTREK_BESTAND,
                GRONDSLAG_BESTAND,
                REVIEW_BESTAND,
            )
        )

    def wis(self) -> bool:
        """Verwijder alle lokale invoer van dit dossier."""
        if not self.bruikbaar or not self.map.exists():
            return True
        try:
            shutil.rmtree(self.map)
        except OSError:
            return False
        return True


def bekende_dossiers(basis: Path = DOSSIER_DIR) -> list[dict[str, str]]:
    """De dossiers waarvan lokaal invoer is bewaard.

    Nodig om te kunnen zien wat er op deze computer staat en om het te kunnen
    wissen: een opslag die niet te overzien is, is niet te beheren.
    """
    if not basis.exists():
        return []
    dossiers = []
    for map_ in sorted(pad for pad in basis.iterdir() if pad.is_dir()):
        label = DossierOpslag(sleutel=map_.name, map=map_).lees_label()
        dossiers.append(
            {
                "sleutel": map_.name,
                "naam": label.get("naam", ""),
                "boekjaar": label.get("boekjaar", ""),
            }
        )
    return dossiers


def oude_invoer_aanwezig() -> bool:
    """Staat er nog invoer uit de versie zonder scheiding per dossier?"""
    return any(pad.exists() for pad in OUDE_PADEN)


def lees_oude_invoer() -> dict[str, dict]:
    """De invoer van vóór de scheiding per dossier, om te kunnen overnemen."""
    return {
        "aangifte": _als_getallen(_lees(BTW_AANGIFTE_PATH)),
        "grondslagen": _als_getallen(_lees(BTW_GRONDSLAG_PATH)),
        "mapping": {
            str(code): str(rubriek) for code, rubriek in _lees(BTW_MAPPING_PATH).items()
        },
        "aftrekbaarheid": _als_getallen(_lees(BTW_AFTREK_PATH)),
    }


def verwijder_oude_invoer() -> bool:
    """Ruim de bestanden van vóór de scheiding per dossier op."""
    gelukt = True
    for pad in OUDE_PADEN:
        try:
            pad.unlink(missing_ok=True)
        except OSError:
            gelukt = False
    return gelukt
