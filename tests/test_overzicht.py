"""De signaaltelling op de overzichtspagina.

Het overzicht toonde alleen de btw-signalen en de ongebruikelijke boekingen. Een
leeg blok wekte daardoor de indruk dat er niets te beoordelen was, terwijl de
periodieke, balans-, relatie- en fiscale signalen op andere pagina's stonden.
Deze test bewaakt dat elke categorie in de telling blijft meedoen.
"""
from __future__ import annotations

import app
from auditfile import controls, vat
from auditfile.demo import demopaar
from auditfile.parsing import parse_auditfile


def _demo_met_gebruik():
    _, huidig_bytes = demopaar()
    af = parse_auditfile("demo_huidig_jaar.xaf", huidig_bytes)
    return af, vat.pas_mapping_toe(vat.build_vat_usage(af), {}, {})


def test_elke_categorie_staat_in_de_telling():
    af, gebruik = _demo_met_gebruik()
    telling = app.tel_signalen(af, gebruik)

    assert list(telling["categorie"]) == [categorie for categorie, _ in app.SIGNAALCATEGORIEEN]
    assert (telling["pagina"].str.len() > 0).all()
    assert (telling["aantal_signalen"] >= 0).all()


def test_de_telling_klopt_met_de_onderliggende_controles():
    af, gebruik = _demo_met_gebruik()
    telling = app.tel_signalen(af, gebruik).set_index("categorie")["aantal_signalen"]

    assert telling["Btw"] == len(vat.build_vat_anomalies(af, gebruik))
    assert telling["Boekingen"] == len(controls.build_ongebruikelijke_boekingen(af))
    assert telling["Fiscaal"] == len(controls.build_fiscale_signalen(af))

    omzet = controls.build_omzet_per_periode(af)
    assert telling["Omzet per periode"] == int((omzet["signaal"] != "").sum())


def test_de_demo_levert_signalen_buiten_btw_en_boekingen():
    """Anders zou deze test niets aantonen over het probleem dat hij dekt."""
    af, gebruik = _demo_met_gebruik()
    telling = app.tel_signalen(af, gebruik).set_index("categorie")["aantal_signalen"]
    buiten = telling.drop(["Btw", "Boekingen"])
    assert int(buiten.sum()) > 0
