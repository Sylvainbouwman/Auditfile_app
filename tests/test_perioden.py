"""Welke perioden zijn boekingsperioden?

De periodetabel van een auditfile bevat niet alleen de gewone maanden of
kwartalen. Pakketten zetten er ook een periode 0 voor de beginbalans in en een
periode 13 of 14 voor de jaarafsluiting. Rekent de tool die mee als gewone
periode, dan meldt zij dat de huur en de lonen "in periode 13 ontbreken".
Alle bestanden hier zijn synthetisch.
"""
from __future__ import annotations

from auditfile.controls import (
    afsluitperioden,
    boekingsperioden,
    build_omzet_per_periode,
    build_periodieke_controles,
)
from auditfile.demo import Account, AuditfileSpec, Journal, Line, Transaction, build_xaf
from auditfile.parsing import parse_auditfile

MAANDEN = [(nummer, f"2025-{nummer:02d}-01", f"2025-{nummer:02d}-28") for nummer in range(1, 13)]


def _auditfile(perioden: list[tuple[int, str, str]] | None):
    """Twaalf maanden huur, plus de periodetabel die wordt meegegeven."""
    spec = AuditfileSpec(
        periods=perioden,
        accounts=[
            Account("1600", "Crediteuren", "B", "BSchCre"),
            Account("4000", "Huur bedrijfspand", "P", "WBedHui"),
            Account("8000", "Omzet", "P", "WOmzNeh"),
            Account("1300", "Debiteuren", "B", "BVorDeb"),
        ],
        journals=[
            Journal(
                "INK",
                "Inkoopboek",
                [
                    Transaction(
                        f"I{maand:02d}",
                        f"2025-{maand:02d}-15",
                        maand,
                        [Line("4000", "1000.00", "D", "Huur"), Line("1600", "1000.00", "C")],
                    )
                    for maand in range(1, 13)
                ],
            ),
            Journal(
                "VRK",
                "Verkoopboek",
                [
                    Transaction(
                        f"V{maand:02d}",
                        f"2025-{maand:02d}-20",
                        maand,
                        [Line("1300", "3000.00", "D"), Line("8000", "3000.00", "C")],
                    )
                    for maand in range(1, 13)
                ],
            ),
        ],
    )
    return parse_auditfile("perioden.xaf", build_xaf(spec))


def test_twaalf_maanden_geeft_twaalf_boekingsperioden():
    af = _auditfile(MAANDEN)
    assert boekingsperioden(af) == list(range(1, 13))
    assert afsluitperioden(af) == []


def test_afsluitperiode_van_een_dag_telt_niet_mee():
    """Periode 13 met begin- en einddatum op 31 december is een afsluiting."""
    af = _auditfile(MAANDEN + [(13, "2025-12-31", "2025-12-31")])
    assert boekingsperioden(af) == list(range(1, 13))
    assert afsluitperioden(af) == [13]


def test_periode_nul_telt_niet_mee():
    af = _auditfile([(0, "2025-01-01", "2025-01-01")] + MAANDEN)
    assert boekingsperioden(af) == list(range(1, 13))
    assert afsluitperioden(af) == [0]


def test_periode_dertien_die_december_overdoet_telt_niet_mee():
    """Sommige pakketten geven de afsluitperiode het bereik van december."""
    af = _auditfile(MAANDEN + [(13, "2025-12-01", "2025-12-28")])
    assert boekingsperioden(af) == list(range(1, 13))
    assert afsluitperioden(af) == [13]


def test_dertien_vierwekelijkse_perioden_blijven_dertien():
    """Een vierwekelijkse administratie heeft dertien echte perioden."""
    reeksen = [
        (nummer, f"2025-{1 + (nummer - 1) // 3:02d}-{1 + ((nummer - 1) % 3) * 9:02d}", "")
        for nummer in range(1, 14)
    ]
    # Bereiken van negen dagen, aansluitend en zonder overlap.
    vierwekelijks = []
    for nummer, start, _ in reeksen:
        dag = int(start[-2:])
        vierwekelijks.append((nummer, start, f"{start[:-2]}{dag + 8:02d}"))
    af = _auditfile(vierwekelijks)
    assert boekingsperioden(af) == list(range(1, 14))
    assert afsluitperioden(af) == []


def test_zonder_datums_gelden_alle_perioden_vanaf_een():
    """Is er niets te toetsen, dan is een aanname over de nummering erger."""
    af = _auditfile([(nummer, "", "") for nummer in range(1, 14)])
    assert boekingsperioden(af) == list(range(1, 14))


def test_afsluitperiode_geeft_geen_ontbrekende_periode():
    """De kern: periode 13 mag geen signaal opleveren bij de vaste lasten."""
    met_afsluiting = _auditfile(MAANDEN + [(13, "2025-12-31", "2025-12-31")])
    controles = build_periodieke_controles(met_afsluiting)
    huur = controles[controles["rekening"] == "4000"].iloc[0]

    assert huur["aantal_perioden"] == 12
    assert huur["ontbrekende_perioden"] == ""
    assert huur["conclusie"] != "Ontbrekende perioden"


def test_omzet_per_periode_laat_de_afsluitperiode_weg():
    af = _auditfile(MAANDEN + [(13, "2025-12-31", "2025-12-31")])
    per_periode = build_omzet_per_periode(af)
    assert list(per_periode["periode"]) == list(range(1, 13))
    assert not (per_periode["signaal"] != "").any()
