"""Opslag van invoer die de gebruiker zelf doet.

Aangiftebedragen en de koppeling van btw-codes aan aangifterubrieken zijn
klant-afgeleide gegevens: de btw-codes komen uit het auditfile van een klant.
Ze worden daarom uitsluitend bewaard in een door Git genegeerde lokale
datamap, nooit in een gevolgd bestand.

Deze module staat los van Streamlit, zodat de opslag te testen is zonder de app
te starten. ``tests/test_runtime_data_not_tracked.py`` borgt de scheiding.
"""
from __future__ import annotations

import json
from pathlib import Path

# Deze map staat in .gitignore en mag nooit door Git worden gevolgd.
LOCAL_DATA_DIR = Path(".local-testdata")
BTW_AANGIFTE_PATH = LOCAL_DATA_DIR / "btw_aangifte.json"
BTW_MAPPING_PATH = LOCAL_DATA_DIR / "btw_mapping.json"
BTW_AFTREK_PATH = LOCAL_DATA_DIR / "btw_aftrekbaarheid.json"
BTW_GRONDSLAG_PATH = LOCAL_DATA_DIR / "btw_grondslagen.json"


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


def load_declared_vat(path: Path = BTW_AANGIFTE_PATH) -> dict:
    """Eerder ingevoerde aangiftebedragen per rubriek."""
    return _lees(path)


def save_declared_vat(declared: dict, path: Path = BTW_AANGIFTE_PATH) -> bool:
    """Bewaar de ingevoerde aangiftebedragen."""
    return _schrijf(declared, path)


def load_vat_mapping(path: Path = BTW_MAPPING_PATH) -> dict:
    """De vastgelegde koppeling van btw-code aan aangifterubriek."""
    mapping = _lees(path)
    return {str(code): str(rubriek) for code, rubriek in mapping.items()}


def save_vat_mapping(mapping: dict, path: Path = BTW_MAPPING_PATH) -> bool:
    """Bewaar de koppeling van btw-code aan aangifterubriek."""
    return _schrijf(mapping, path)


def load_declared_base(path: Path = BTW_GRONDSLAG_PATH) -> dict:
    """De aangegeven grondslag per rubriek: het bedrag waarover de btw loopt."""
    return _lees(path)


def save_declared_base(grondslagen: dict, path: Path = BTW_GRONDSLAG_PATH) -> bool:
    """Bewaar de aangegeven grondslag per rubriek."""
    return _schrijf(grondslagen, path)


def load_vat_deduction(path: Path = BTW_AFTREK_PATH) -> dict:
    """Het aftrekbare aandeel per btw-code, in procenten.

    Geldt alleen bij de rubrieken waarin de ondernemer de btw zelf verschuldigd
    wordt. Een waarde die geen getal is wordt overgeslagen in plaats van de hele
    invoer te laten vervallen.
    """
    aandelen = {}
    for code, waarde in _lees(path).items():
        try:
            aandelen[str(code)] = float(waarde)
        except (TypeError, ValueError):
            continue
    return aandelen


def save_vat_deduction(aandelen: dict, path: Path = BTW_AFTREK_PATH) -> bool:
    """Bewaar het aftrekbare aandeel per btw-code."""
    return _schrijf(aandelen, path)
