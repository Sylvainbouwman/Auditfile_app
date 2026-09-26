"""De synthetische XAF 4.0-bestanden valideren tegen het officiële schema.

De parser wijst niets af, dus een fixture kan ongemerkt afwijken van wat een
echt pakket levert. Deze test houdt de demo gelijk aan het schema. Herkomst van
de bestanden in docs/xaf-schema: zie docs/xaf-velden.md, paragraaf "Schema en
testbestand".
"""

from pathlib import Path

import pytest
from lxml import etree

from auditfile import demo
from auditfile.parsing import parse_auditfile

SCHEMA_MAP = Path(__file__).resolve().parent.parent / "docs" / "xaf-schema"
TESTBESTAND = SCHEMA_MAP / "XAF_4_0_Test_100425.XAF"


@pytest.fixture(scope="module")
def schema_40() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(SCHEMA_MAP / "XmlAuditfileFinancieel4.0.xsd")))


def _fouten(schema: etree.XMLSchema, inhoud: bytes) -> list[str]:
    schema.validate(etree.fromstring(inhoud))
    return [f"regel {f.line}: {f.message}" for f in schema.error_log]


def test_het_officiele_testbestand_valideert(schema_40):
    assert _fouten(schema_40, TESTBESTAND.read_bytes()) == []


def test_het_schema_wijst_een_fout_bestand_af(schema_40):
    # Zonder deze tegenproef zou een schema dat niets toetst de andere tests
    # ook laten slagen.
    inhoud = demo.build_xaf(demo.eenvoudige_spec("4.0")).replace(b"<docRef>", b"<docRefX>", 1)
    inhoud = inhoud.replace(b"</docRef>", b"</docRefX>", 1)
    assert _fouten(schema_40, inhoud)


def test_de_eenvoudige_demo_valideert(schema_40):
    assert _fouten(schema_40, demo.build_xaf(demo.eenvoudige_spec("4.0"))) == []


def test_het_demopaar_in_40_valideert(schema_40):
    # Het huidige jaar van het demopaar bevat de rekening-courant, de suppletie,
    # de ratioposten en de relatiesaldi, dus vrijwel alles wat de generator kan.
    vorig, huidig = demo.demopaar(versie_vorig="4.0", versie_huidig="4.0")
    assert _fouten(schema_40, vorig) == []
    assert _fouten(schema_40, huidig) == []


def test_de_parser_leest_het_officiele_testbestand():
    af = parse_auditfile(TESTBESTAND.name, TESTBESTAND.read_bytes())
    assert af.xaf_versie == "4.0"
    assert not af.accounts.empty
    assert len(af.lines) == af.transaction_totals.lines_count
    assert af.lines["bedrag"].sum() == pytest.approx(0.0, abs=0.005)
