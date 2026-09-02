"""Regressietest voor punt 12 uit de review.

Runtime-invoer (zoals ingevoerde aangiftebedragen) mag nooit in een door Git
gevolgd bestand terechtkomen. Deze test borgt dat:

1. het pad waar de app aangiftebedragen wegschrijft door Git genegeerd is;
2. het eerder gevolgde ``testfiles/btw_aangifte.json`` niet langer wordt getrackt;
3. dat pad in de aangewezen lokale datamap ligt;
4. een echte synthetische write/read via de app-helpers naar een unieke testfile
   onder ``.local-testdata/`` gaat en geen Git-wijziging veroorzaakt (het echte
   runtimebestand wordt daarbij nooit overschreven).

Alle Git-subprocessaanroepen controleren expliciet hun returncode.
Er worden uitsluitend synthetische waarden gebruikt.

Draaibaar met pytest of direct:  python tests/test_runtime_data_not_tracked.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app  # noqa: E402


def _git(*args: str) -> subprocess.CompletedProcess:
    """Draai een Git-commando in de repo-root en geef het volledige resultaat terug."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_runtime_btw_pad_is_git_ignored() -> None:
    """Het pad waar de app aangiftebedragen wegschrijft, moet door Git genegeerd zijn."""
    pad = app.BTW_AANGIFTE_PATH
    result = _git("check-ignore", pad.as_posix())
    # returncode 0 = genegeerd, 1 = niet genegeerd, >1 = Git-fout.
    assert result.returncode == 0, (
        f"Runtime-pad '{pad}' is NIET git-ignored (returncode={result.returncode}); "
        f"aangiftebedragen kunnen in Git belanden."
    )


# Git geeft `ls-files --error-unmatch` exact returncode 1 wanneer het pad NIET
# getrackt wordt; 0 betekent getrackt en andere codes (bv. 128/129) duiden op een
# echte Git-fout die de test moet laten falen.
GIT_NIET_GETRACKT = 1


def test_oud_bestand_niet_meer_getrackt() -> None:
    """Het eerder gevolgde testfiles/btw_aangifte.json mag niet meer door Git gevolgd worden."""
    result = _git("ls-files", "--error-unmatch", "testfiles/btw_aangifte.json")
    assert result.returncode == GIT_NIET_GETRACKT, (
        "testfiles/btw_aangifte.json wordt nog door Git gevolgd of Git gaf een fout "
        f"(returncode={result.returncode}, verwacht {GIT_NIET_GETRACKT})."
    )


def test_runtime_pad_ligt_in_lokale_datamap() -> None:
    """De app schrijft naar de aangewezen lokale datamap, niet naar testfiles/."""
    assert app.LOCAL_DATA_DIR in app.BTW_AANGIFTE_PATH.parents, (
        f"Runtime-pad '{app.BTW_AANGIFTE_PATH}' ligt niet in '{app.LOCAL_DATA_DIR}'."
    )


def test_alle_schrijfpaden_zijn_genegeerd() -> None:
    """Elk pad waar de app naar schrijft moet door Git genegeerd zijn.

    Niet alleen de aangiftebedragen: de btw-koppeling en het aftrekbare aandeel
    per code zijn even klant-afgeleid, want de btw-codes komen uit het auditfile
    van een klant. Komt er een schrijfpad bij, dan hoort het hier ook in.
    """
    from auditfile import settings

    paden = [
        settings.BTW_AANGIFTE_PATH,
        settings.BTW_MAPPING_PATH,
        settings.BTW_AFTREK_PATH,
        settings.BTW_GRONDSLAG_PATH,
    ]
    for pad in paden:
        assert settings.LOCAL_DATA_DIR in pad.parents, (
            f"Schrijfpad '{pad}' ligt niet in '{settings.LOCAL_DATA_DIR}'."
        )
        result = _git("check-ignore", pad.as_posix())
        assert result.returncode == 0, (
            f"Schrijfpad '{pad}' is NIET git-ignored (returncode={result.returncode})."
        )
        getrackt = _git("ls-files", "--error-unmatch", pad.as_posix())
        assert getrackt.returncode == GIT_NIET_GETRACKT, (
            f"Schrijfpad '{pad}' wordt door Git gevolgd "
            f"(returncode={getrackt.returncode}, verwacht {GIT_NIET_GETRACKT})."
        )


def test_synthetische_write_read_zonder_git_wijziging() -> None:
    """Schrijf en lees synthetische aangiftebedragen via de app-helpers.

    Gebruikt een UNIEKE synthetische testfile onder de genegeerde lokale datamap en
    raakt het echte runtimebestand ``BTW_AANGIFTE_PATH`` uitsluitend aan via pad- en
    ignorecontroles, zodat lokale runtime-inhoud nooit overschreven kan worden.
    Verifieert dat de round-trip klopt en dat de write geen Git-wijziging veroorzaakt.
    """
    # Pad-/ignorecontroles op het ECHTE runtimebestand (nooit lezen/schrijven).
    runtime_pad = app.BTW_AANGIFTE_PATH
    assert app.LOCAL_DATA_DIR in runtime_pad.parents, (
        f"Runtime-pad '{runtime_pad}' ligt niet in '{app.LOCAL_DATA_DIR}'."
    )
    runtime_genegeerd = _git("check-ignore", runtime_pad.as_posix())
    assert runtime_genegeerd.returncode == 0, (
        f"Runtime-pad '{runtime_pad}' is niet git-ignored "
        f"(returncode={runtime_genegeerd.returncode})."
    )

    # Unieke synthetische testfile onder dezelfde genegeerde map — NIET het echte bestand.
    test_pad = app.LOCAL_DATA_DIR / "pytest_synthetic_btw.json"
    assert test_pad != runtime_pad, "De testfile mag niet het echte runtimebestand zijn."
    synthetische_bedragen = {"1a": 12.34, "1e": 0.0, "2a/5b": 56.78, "5b": 90.0}

    # Oorspronkelijke staat vastleggen; een eventueel stale eigen artefact opruimen.
    map_bestond = app.LOCAL_DATA_DIR.exists()
    if test_pad.exists():
        test_pad.unlink()

    status_voor = _git("status", "--porcelain")
    assert status_voor.returncode == 0, (
        f"'git status' faalde (returncode={status_voor.returncode})."
    )

    try:
        app.save_declared_vat(synthetische_bedragen, test_pad)

        # 1) Er is daadwerkelijk naar de lokale datamap geschreven.
        assert test_pad.exists(), f"Testbestand '{test_pad}' is niet geschreven."

        # 2) De round-trip via de leeshelper levert exact dezelfde waarden op.
        gelezen = app.load_declared_vat(test_pad)
        assert gelezen == synthetische_bedragen, (
            "Gelezen waarden wijken af van de geschreven synthetische waarden."
        )

        # 3) Het geschreven bestand is en blijft door Git genegeerd.
        genegeerd = _git("check-ignore", test_pad.as_posix())
        assert genegeerd.returncode == 0, (
            f"Testbestand '{test_pad}' is niet git-ignored (returncode={genegeerd.returncode})."
        )

        # 4) Het geschreven bestand wordt niet door Git gevolgd (exact returncode 1).
        getrackt = _git("ls-files", "--error-unmatch", test_pad.as_posix())
        assert getrackt.returncode == GIT_NIET_GETRACKT, (
            f"Testbestand '{test_pad}' wordt door Git gevolgd of Git gaf een fout "
            f"(returncode={getrackt.returncode}, verwacht {GIT_NIET_GETRACKT})."
        )

        # 5) De write heeft de Git-status niet veranderd.
        status_na = _git("status", "--porcelain")
        assert status_na.returncode == 0, (
            f"'git status' faalde na de write (returncode={status_na.returncode})."
        )
        assert status_na.stdout == status_voor.stdout, (
            "De synthetische write veroorzaakte een Git-wijziging in de werkboom."
        )
    finally:
        # Uitsluitend het eigen testartefact opruimen; de map alleen verwijderen
        # wanneer die door deze test is aangemaakt en leeg is.
        if test_pad.exists():
            test_pad.unlink()
        if not map_bestond and app.LOCAL_DATA_DIR.exists():
            try:
                app.LOCAL_DATA_DIR.rmdir()
            except OSError:
                pass


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
