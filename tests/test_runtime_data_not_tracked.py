"""Runtime-invoer mag nooit in Git terechtkomen, en niet in het verkeerde dossier.

Eigen invoer (aangiftebedragen, grondslagen, de koppeling van btw-codes aan
rubrieken en het aftrekbare aandeel per code) is klant-afgeleid: de btw-codes
komen uit het auditfile van een klant. Deze test borgt twee dingen:

1. **Git.** Elk pad waar de app naar schrijft ligt in de aangewezen lokale
   datamap, wordt door Git genegeerd en wordt niet gevolgd. Een echte
   schrijf-/leesronde met synthetische waarden verandert de Git-status niet.
2. **Dossierscheiding.** Invoer van het ene dossier is niet te lezen vanuit het
   andere, en een auditfile zonder identificatie levert geen opslag op.

Alle Git-subprocessaanroepen controleren expliciet hun returncode. Er worden
uitsluitend synthetische waarden gebruikt.

Draaibaar met pytest of direct:  python tests/test_runtime_data_not_tracked.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app  # noqa: E402
from auditfile import settings  # noqa: E402
from auditfile.demo import AuditfileSpec, build_xaf  # noqa: E402
from auditfile.parsing import parse_auditfile  # noqa: E402

# Git geeft `ls-files --error-unmatch` exact returncode 1 wanneer het pad NIET
# getrackt wordt; 0 betekent getrackt en andere codes (bv. 128/129) duiden op een
# echte Git-fout die de test moet laten falen.
GIT_NIET_GETRACKT = 1

# Sleutel voor het testdossier. Geen echte hash, zodat hij niet met een dossier
# van een klant kan samenvallen.
TESTSLEUTEL = "pytest-synthetisch"


def _git(*args: str) -> subprocess.CompletedProcess:
    """Draai een Git-commando in de repo-root en geef het volledige resultaat terug."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _controleer_pad(pad: Path) -> None:
    """Het pad ligt in de lokale datamap, is genegeerd en wordt niet gevolgd."""
    assert settings.LOCAL_DATA_DIR in pad.parents, (
        f"Schrijfpad '{pad}' ligt niet in '{settings.LOCAL_DATA_DIR}'."
    )
    genegeerd = _git("check-ignore", pad.as_posix())
    assert genegeerd.returncode == 0, (
        f"Schrijfpad '{pad}' is NIET git-ignored (returncode={genegeerd.returncode})."
    )
    getrackt = _git("ls-files", "--error-unmatch", pad.as_posix())
    assert getrackt.returncode == GIT_NIET_GETRACKT, (
        f"Schrijfpad '{pad}' wordt door Git gevolgd of Git gaf een fout "
        f"(returncode={getrackt.returncode}, verwacht {GIT_NIET_GETRACKT})."
    )


def test_alle_schrijfpaden_van_een_dossier_zijn_genegeerd() -> None:
    """Elk bestand dat de app in een dossier schrijft, blijft buiten Git."""
    opslag = settings.DossierOpslag.voor(TESTSLEUTEL)
    bestanden = (
        settings.AANGIFTE_BESTAND,
        settings.MAPPING_BESTAND,
        settings.AFTREK_BESTAND,
        settings.GRONDSLAG_BESTAND,
        settings.DOSSIER_BESTAND,
        settings.REVIEW_BESTAND,
        settings.EXCESSIEF_BESTAND,
    )
    for bestand in bestanden:
        _controleer_pad(opslag.pad(bestand))


def test_oude_paden_blijven_genegeerd() -> None:
    """De paden van vóór de dossierscheiding worden nog gelezen bij overname."""
    for pad in settings.OUDE_PADEN:
        _controleer_pad(pad)


def test_oud_bestand_niet_meer_getrackt() -> None:
    """Het eerder gevolgde testfiles/btw_aangifte.json mag niet meer door Git gevolgd worden."""
    result = _git("ls-files", "--error-unmatch", "testfiles/btw_aangifte.json")
    assert result.returncode == GIT_NIET_GETRACKT, (
        "testfiles/btw_aangifte.json wordt nog door Git gevolgd of Git gaf een fout "
        f"(returncode={result.returncode}, verwacht {GIT_NIET_GETRACKT})."
    )


def test_testmap_is_volledig_genegeerd() -> None:
    """De hele map testfiles/ blijft buiten Git, niet alleen de XAF-bestanden.

    Daar staan echte auditfiles en eigen invoer. Werd alleen op bestandstype
    genegeerd, dan zou een los .csv-, .xlsx- of .pdf-bestand dat daar belandt
    wel worden gevolgd.
    """
    for naam in ("pytest-synthetisch.csv", "pytest-synthetisch.xlsx", "pytest-synthetisch.pdf"):
        genegeerd = _git("check-ignore", f"testfiles/{naam}")
        assert genegeerd.returncode == 0, (
            f"testfiles/{naam} is NIET git-ignored (returncode={genegeerd.returncode}); "
            "negeer de map testfiles/ als geheel."
        )

    gevolgd = _git("ls-files", "testfiles")
    assert gevolgd.returncode == 0, f"'git ls-files' faalde (returncode={gevolgd.returncode})."
    assert gevolgd.stdout.strip() == "", (
        f"Er worden bestanden in testfiles/ door Git gevolgd:\n{gevolgd.stdout}"
    )


def test_lokale_datamap_ligt_in_de_repo() -> None:
    """De datamap is verankerd aan de repo en niet aan de werkmap van het proces.

    Een relatief pad zou de invoer bij een start vanuit een andere map naar een
    .local-testdata/ daar schrijven, buiten het bereik van deze .gitignore en
    mogelijk in een andere repository.
    """
    assert settings.LOCAL_DATA_DIR.is_absolute(), (
        f"'{settings.LOCAL_DATA_DIR}' is een relatief pad en volgt dus de werkmap."
    )
    assert settings.LOCAL_DATA_DIR.parent == REPO_ROOT, (
        f"'{settings.LOCAL_DATA_DIR}' ligt niet direct in de repo-wortel '{REPO_ROOT}'."
    )


def test_synthetische_write_read_zonder_git_wijziging() -> None:
    """Schrijf en lees synthetische invoer via de opslag van een testdossier.

    Gebruikt een eigen dossiersleutel onder de genegeerde datamap, zodat de
    opslag van een echt dossier nooit wordt aangeraakt.
    """
    opslag = settings.DossierOpslag.voor(TESTSLEUTEL)
    assert opslag.bruikbaar
    aangifte = {"1a": 12.34, "1b": 0.0, "5b": 90.0}
    mapping = {"SYN1": "1a", "SYN2": "5b"}

    map_bestond = settings.LOCAL_DATA_DIR.exists()
    if opslag.map.exists():
        shutil.rmtree(opslag.map)

    status_voor = _git("status", "--porcelain")
    assert status_voor.returncode == 0, (
        f"'git status' faalde (returncode={status_voor.returncode})."
    )

    try:
        assert opslag.schrijf_aangifte(aangifte)
        assert opslag.schrijf_mapping(mapping)
        assert opslag.schrijf_label("Synthetisch Testdossier", "2025")

        # 1) Er is daadwerkelijk naar de dossiermap geschreven.
        assert opslag.pad(settings.AANGIFTE_BESTAND).exists()
        assert opslag.heeft_invoer

        # 2) De round-trip levert exact dezelfde waarden op.
        assert opslag.lees_aangifte() == aangifte
        assert opslag.lees_mapping() == mapping
        assert opslag.lees_label()["boekjaar"] == "2025"

        # 3) Elk geschreven bestand blijft buiten Git.
        for bestand in (
            settings.AANGIFTE_BESTAND,
            settings.MAPPING_BESTAND,
            settings.DOSSIER_BESTAND,
        ):
            _controleer_pad(opslag.pad(bestand))

        # 4) De writes hebben de Git-status niet veranderd.
        status_na = _git("status", "--porcelain")
        assert status_na.returncode == 0, (
            f"'git status' faalde na de write (returncode={status_na.returncode})."
        )
        assert status_na.stdout == status_voor.stdout, (
            "De synthetische write veroorzaakte een Git-wijziging in de werkboom."
        )

        # 5) Wissen ruimt het dossier volledig op.
        assert opslag.wis()
        assert not opslag.map.exists()
    finally:
        if opslag.map.exists():
            shutil.rmtree(opslag.map)
        for map_ in (settings.DOSSIER_DIR, settings.LOCAL_DATA_DIR):
            if not map_bestond and map_.exists():
                try:
                    map_.rmdir()
                except OSError:
                    pass


def test_invoer_van_het_ene_dossier_is_onzichtbaar_in_het_andere() -> None:
    """De kern van de scheiding: dossier A mag niets van dossier B zien."""
    eerste = settings.DossierOpslag.voor(f"{TESTSLEUTEL}-a")
    tweede = settings.DossierOpslag.voor(f"{TESTSLEUTEL}-b")
    try:
        assert eerste.schrijf_mapping({"SYN1": "1a"})
        assert tweede.schrijf_mapping({"SYN1": "5b"})

        assert eerste.lees_mapping() == {"SYN1": "1a"}
        assert tweede.lees_mapping() == {"SYN1": "5b"}
        assert eerste.map != tweede.map
    finally:
        for opslag in (eerste, tweede):
            if opslag.map.exists():
                shutil.rmtree(opslag.map)


def test_dossier_zonder_identificatie_bewaart_niets() -> None:
    """Zonder onderneming of boekjaar is er geen sleutel en dus geen opslag.

    Bewaren onder een lege sleutel zou de invoer bij het volgende naamloze
    bestand weer tevoorschijn laten komen, en dat is precies de vermenging die
    deze scheiding moet voorkomen.
    """
    spec = AuditfileSpec(
        company_name="", tax_reg_ident="", commerce_nr="", fiscal_year="", accounts=[], journals=[]
    )
    af = parse_auditfile("naamloos.xaf", build_xaf(spec))
    assert af.dossier_sleutel == ""

    opslag = settings.DossierOpslag.voor(af.dossier_sleutel)
    assert not opslag.bruikbaar
    assert opslag.schrijf_mapping({"SYN1": "1a"}) is False
    assert opslag.lees_mapping() == {}
    assert opslag.heeft_invoer is False


if __name__ == "__main__":
    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"PASS  {_name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {_name}: {exc}")
    sys.exit(1 if failures else 0)
