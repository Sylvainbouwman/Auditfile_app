"""Borgt dat rekenen met float de centencontroles niet verstoort.

De bedragen staan als float en de controles vergelijken met een marge van
een halve cent (``TOLERANTIE = 0.005``). Die keuze is op 26-09-2026 gemeten
tegen exacte som in hele centen, op synthetische bedragen: bij 1 miljoen
regels tot 100.000 euro blijft de afwijking rond 1e-6, bij 1 miljoen regels
tot 10 miljoen euro rond 3e-4. Pas bij miljoenen regels van elk honderd
miljoen euro, totalen die in een auditfile niet voorkomen, nadert de fout de
halve cent. Deze test houdt die ruimte vast: gaat hij stuk, dan is omzetten
naar hele centen of Decimal alsnog aan de orde (ROADMAP, "Bedragen als float").
"""

import numpy as np
import pandas as pd

from auditfile.integrity import TOLERANTIE


def _centen(aantal: int, maximum_euro: float, zaad: int) -> np.ndarray:
    rng = np.random.default_rng(zaad)
    grens = int(maximum_euro * 100)
    return rng.integers(-grens, grens, aantal)


def test_ruime_administratie_blijft_ver_onder_de_marge():
    centen = _centen(1_000_000, 10_000_000, zaad=1)
    bedragen = pd.Series(centen / 100.0)
    exact = int(centen.sum()) / 100
    # Zowel de pandas-som als een oplopende som, die het slechtst afrondt.
    assert abs(bedragen.sum() - exact) < TOLERANTIE / 10
    assert abs(bedragen.cumsum().iloc[-1] - exact) < TOLERANTIE / 10


def test_gebalanceerde_boekingen_sluiten_binnen_de_marge():
    centen = _centen(1_000_000, 10_000_000, zaad=2)
    bedragen = pd.Series(centen / 100.0)
    rng = np.random.default_rng(3)
    regels = pd.concat([bedragen, -bedragen.iloc[rng.permutation(len(bedragen))]])
    assert abs(regels.sum()) < TOLERANTIE
    assert abs(regels.cumsum().iloc[-1]) < TOLERANTIE


def test_een_echte_cent_verschil_blijft_zichtbaar():
    centen = _centen(1_000_000, 10_000_000, zaad=4)
    bedragen = pd.Series(centen / 100.0)
    regels = pd.concat([bedragen, -bedragen, pd.Series([0.01])])
    regels = regels.sample(frac=1, random_state=5)
    assert abs(regels.sum()) >= TOLERANTIE
    assert abs(regels.sum() - 0.01) < TOLERANTIE / 10


def test_tweedecimale_tekst_wordt_exact_de_dichtstbijzijnde_float():
    # Parsing gaat van tekst met twee decimalen naar float: met honderd
    # vermenigvuldigen en afronden moet exact de centen teruggeven.
    teksten = pd.Series([f"{c / 100:.2f}" for c in _centen(50_000, 1e9, zaad=6)])
    terug = (teksten.astype(float) * 100).round().astype("int64")
    verwacht = teksten.str.replace(".", "", regex=False).astype("int64")
    assert (terug == verwacht).all()
