"""Nederlandse notatie van losse waarden.

Deze functies stonden in ``formatting.py``, en dat is de presentatielaag van de
app: die module haalt Streamlit binnen. Een analysemodule die een bedrag in een
toelichting zet kon haar daarom niet gebruiken, en bakte zijn eigen notatie of
liet het bedrag als ``2520.00`` staan. Dat viel in een tabel niet op, want daar
staan bedragen als getal met hun eigen kolomopmaak, maar in een doorlopende
tekst wel.

Vandaar deze module: één plaats voor de notatie, zonder Streamlit, zodat elke
laag haar kan gebruiken. ``formatting.py`` neemt de namen over, dus voor de app
verandert er niets.

Let op de scheiding die hier niet verandert: een bedrag blijft in een DataFrame
een getal. Deze functies zijn voor tekst waarin een bedrag wordt genoemd, en
nooit om een bedragkolom te vullen; dan is sorteren en optellen stuk.
"""
from __future__ import annotations

import pandas as pd

# Wat er staat als de waarde er niet is. Een leeg veld zou als nul kunnen worden
# gelezen en dat is iets anders dan onbekend.
GEEN_WAARDE = "—"


def euro(waarde, decimalen: int = 2) -> str:
    """Een bedrag in Nederlandse notatie, bijvoorbeeld ``€ 1.234,56``."""
    getal = pd.to_numeric(waarde, errors="coerce")
    if pd.isna(getal):
        return GEEN_WAARDE
    opgemaakt = f"{float(getal):,.{decimalen}f}"
    opgemaakt = opgemaakt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"€ {opgemaakt}"


def euro_kort(waarde) -> str:
    """Een bedrag zonder centen, voor kerncijfers."""
    return euro(waarde, decimalen=0)


def procent(waarde, decimalen: int = 1) -> str:
    getal = pd.to_numeric(waarde, errors="coerce")
    if pd.isna(getal):
        return GEEN_WAARDE
    opgemaakt = f"{float(getal):,.{decimalen}f}".replace(".", ",")
    return f"{opgemaakt}%"


def datum_nl(waarde) -> str:
    tijdstip = pd.to_datetime(waarde, errors="coerce")
    if pd.isna(tijdstip):
        return ""
    return tijdstip.strftime("%d-%m-%Y")
