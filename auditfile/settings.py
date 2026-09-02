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
