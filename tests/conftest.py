"""Gedeelde testfixtures.

Alle auditfiles in de tests zijn synthetisch en worden in het geheugen
opgebouwd; er wordt nooit klantdata gelezen.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auditfile.demo import build_xaf, eenvoudige_spec  # noqa: E402

from auditfile.parsing import parse_auditfile  # noqa: E402


@pytest.fixture(scope="session")
def spec_40():
    return eenvoudige_spec("4.0")


@pytest.fixture(scope="session")
def spec_32():
    return eenvoudige_spec("3.2")


@pytest.fixture(scope="session")
def af_40(spec_40):
    """Ingelezen synthetisch auditfile in XAF 4.0."""
    return parse_auditfile("synthetisch_4_0.xaf", build_xaf(spec_40))


@pytest.fixture(scope="session")
def af_32(spec_32):
    """Ingelezen synthetisch auditfile in XAF 3.2."""
    return parse_auditfile("synthetisch_3_2.xaf", build_xaf(spec_32))
