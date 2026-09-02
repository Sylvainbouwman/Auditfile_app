"""Synthetische XAF-auditfiles: demodata voor de app en fixtures voor de tests.

Alle gegevens die hiermee ontstaan zijn verzonnen. Er wordt nooit klantdata
gebruikt, ook niet als voorbeeld: rekeningnamen, relaties en bedragen komen uit
deze module en nergens anders vandaan. Daardoor kan de tool worden getoond en
uitgeprobeerd zonder dat er een klantbestand aan te pas komt.

Ondersteunt zowel XAF 3.2 als 4.0, zodat de parser tegen beide varianten kan
worden getest.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

NAMESPACES = {
    "3.2": "http://www.auditfiles.nl/XAF/3.2",
    "4.0": (
        "http://www.odb.belastingdienst.nl/Belastingdienst/BCPP/1.1/structures/"
        "XmlauditfileXAF_4.0"
    ),
}


@dataclass
class Account:
    accID: str
    accDesc: str
    accTp: str = "P"
    RGScode: str = ""
    leadReference: str = ""


@dataclass
class VatCode:
    vatID: str
    vatDesc: str
    vatToPayAccID: str = ""
    vatToClaimAccID: str = ""


@dataclass
class Relation:
    custSupID: str
    custSupName: str
    custSupTp: str = "C"
    country: str = "NL"
    # Het openstaande bedrag per relatie bij begin en einde van het boekjaar.
    # Bestaat alleen in XAF 4.0 (opBalDesc/clBalDesc met een D/C-indicatie) en
    # wordt daar als bedrag geschreven, niet als omschrijving.
    openstaand_begin: str = ""
    openstaand_begin_tp: str = "D"
    openstaand_eind: str = ""
    openstaand_eind_tp: str = "D"


@dataclass
class Line:
    """Een boekingsregel.

    ``amnt`` wordt letterlijk weggeschreven, dus ook een negatieve waarde. Dat
    is nodig om het gedrag te kunnen testen van pakketten die een tegenboeking
    als negatief bedrag binnen dezelfde debet/credit-zijde schrijven.
    """

    accID: str
    amnt: str
    amntTp: str
    desc: str = "Boekingsregel"
    effDate: str = "2025-01-15"
    docRef: str = ""
    invRef: str = ""
    custSupID: str = ""
    vatID: str = ""
    vatPerc: str = ""
    vatAmnt: str = ""
    vatAmntTp: str = ""


@dataclass
class Transaction:
    nr: str
    trDt: str
    periodNumber: int
    lines: list[Line]
    desc: str = "Transactie"


@dataclass
class Journal:
    jrnID: str
    desc: str
    transactions: list[Transaction]
    jrnTp: str = "M"


@dataclass
class OpeningLine:
    accID: str
    amnt: str
    amntTp: str


@dataclass
class AuditfileSpec:
    """Volledige beschrijving van een te genereren auditfile."""

    versie: str = "4.0"
    company_name: str = "Testbedrijf Synthetisch BV"
    tax_reg_ident: str = "NL000000000B01"
    commerce_nr: str = "00000000"
    fiscal_year: str = "2025"
    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"
    accounts: list[Account] = field(default_factory=list)
    vat_codes: list[VatCode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    opening_lines: list[OpeningLine] = field(default_factory=list)
    # Omschrijving van de beginbalans van het grootboek. In XAF 3.2 heet dat veld
    # opBalDesc, dezelfde naam die XAF 4.0 gebruikt voor een bedrag per relatie.
    # Nodig om te kunnen testen dat die twee niet worden verward.
    opening_balance_desc: str = ""
    journals: list[Journal] = field(default_factory=list)
    period_count: int = 12
    # Eigen periodetabel als (nummer, begindatum, einddatum). Nodig om een
    # afsluitperiode of een periode 0 te kunnen nabouwen; is die leeg, dan
    # worden period_count maandperioden gegenereerd.
    periods: list[tuple[int, str, str]] | None = None
    # Laat de controletotalen bewust afwijken om de integriteitscontrole te testen.
    opening_totals_override: tuple[int, str, str] | None = None
    transaction_totals_override: tuple[int, str, str] | None = None


def _tag(name: str, value: str, indent: int = 0) -> str:
    if value is None or value == "":
        return ""
    return f"{' ' * indent}<{name}>{escape(str(value))}</{name}>\n"


def _totals(lines: list[tuple[str, str]]) -> tuple[int, str, str]:
    """Bereken linesCount, totalDebit en totalCredit uit (amnt, amntTp)-paren.

    De totalen worden opgebouwd uit het getékende bedrag per debet/credit-zijde,
    net zoals de boekhoudpakketten die de echte auditfiles schrijven dat doen:
    de zijde volgt uit ``amntTp`` en een negatieve regel verlaagt het totaal van
    de eigen zijde. Zo toetst de test de parser aan de werkelijke conventie en
    niet aan een eigen aanname.
    """
    debit = 0.0
    credit = 0.0
    for amount, kind in lines:
        value = float(amount)
        if kind.upper() == "C":
            credit += value
        else:
            debit += value
    return len(lines), f"{debit:.2f}", f"{credit:.2f}"


def build_xaf(spec: AuditfileSpec) -> bytes:
    """Genereer een XAF-bestand als bytes."""
    namespace = NAMESPACES[spec.versie]
    is_40 = spec.versie == "4.0"
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n']
    out.append(f'<auditfile xmlns="{namespace}">\n')

    out.append("  <header>\n")
    out.append(_tag("fiscalYear", spec.fiscal_year, 4))
    out.append(_tag("startDate", spec.start_date, 4))
    out.append(_tag("endDate", spec.end_date, 4))
    out.append(_tag("curCode", "EUR", 4))
    out.append(_tag("dateCreated", "2026-01-15", 4))
    out.append(_tag("softwareDesc", "Synthetische testgenerator", 4))
    out.append(_tag("softwareVersion", "1.0", 4))
    if is_40:
        out.append(_tag("RGSVersion", "3.5", 4))
    out.append("  </header>\n")

    out.append("  <company>\n")
    out.append(_tag("companyName", spec.company_name, 4))
    if is_40:
        out.append(_tag("Commercenr", spec.commerce_nr, 4))
    else:
        out.append(_tag("companyIdent", spec.commerce_nr, 4))
    out.append(_tag("taxRegIdent", spec.tax_reg_ident, 4))
    out.append(_tag("taxRegistrationCountry", "NL", 4))

    if spec.relations:
        out.append("    <customersSuppliers>\n")
        for relation in spec.relations:
            out.append("      <customerSupplier>\n")
            out.append(_tag("custSupID", relation.custSupID, 8))
            out.append(_tag("custSupName", relation.custSupName, 8))
            out.append(_tag("custSupTp", relation.custSupTp, 8))
            if is_40:
                out.append(_tag("opBalDesc", relation.openstaand_begin, 8))
                if relation.openstaand_begin:
                    out.append(_tag("opBalTp", relation.openstaand_begin_tp, 8))
                out.append(_tag("clBalDesc", relation.openstaand_eind, 8))
                if relation.openstaand_eind:
                    out.append(_tag("clBalTp", relation.openstaand_eind_tp, 8))
            out.append("        <streetAddress>\n")
            out.append(_tag("streetname", "Teststraat", 10))
            out.append(_tag("city", "Testplaats", 10))
            out.append(_tag("country", relation.country, 10))
            out.append("        </streetAddress>\n")
            out.append("      </customerSupplier>\n")
        out.append("    </customersSuppliers>\n")

    out.append("    <generalLedger>\n")
    for account in spec.accounts:
        out.append("      <ledgerAccount>\n")
        out.append(_tag("accID", account.accID, 8))
        out.append(_tag("accDesc", account.accDesc, 8))
        out.append(_tag("accTp", account.accTp, 8))
        if is_40:
            out.append(_tag("RGScode", account.RGScode, 8))
        else:
            out.append(_tag("leadReference", account.leadReference, 8))
        out.append("      </ledgerAccount>\n")
    out.append("    </generalLedger>\n")

    if spec.vat_codes:
        out.append("    <vatCodes>\n")
        for code in spec.vat_codes:
            out.append("      <vatCode>\n")
            out.append(_tag("vatID", code.vatID, 8))
            out.append(_tag("vatDesc", code.vatDesc, 8))
            out.append(_tag("vatToPayAccID", code.vatToPayAccID, 8))
            out.append(_tag("vatToClaimAccID", code.vatToClaimAccID, 8))
            out.append("      </vatCode>\n")
        out.append("    </vatCodes>\n")

    out.append("    <periods>\n")
    perioden = spec.periods or [
        (
            nummer,
            f"{spec.fiscal_year}-{nummer:02d}-01",
            f"{spec.fiscal_year}-{nummer:02d}-28",
        )
        for nummer in range(1, spec.period_count + 1)
    ]
    for nummer, start_datum, eind_datum in perioden:
        out.append("      <period>\n")
        out.append(_tag("periodNumber", str(nummer), 8))
        out.append(_tag("startDatePeriod", start_datum, 8))
        out.append(_tag("endDatePeriod", eind_datum, 8))
        out.append("      </period>\n")
    out.append("    </periods>\n")

    opening_pairs = [(line.amnt, line.amntTp) for line in spec.opening_lines]
    count, debit, credit = spec.opening_totals_override or _totals(opening_pairs)
    out.append("    <openingBalance>\n")
    if not is_40 and spec.opening_balance_desc:
        out.append(_tag("opBalDate", spec.start_date, 6))
        out.append(_tag("opBalDesc", spec.opening_balance_desc, 6))
    out.append(_tag("linesCount", str(count), 6))
    out.append(_tag("totalDebit", debit, 6))
    out.append(_tag("totalCredit", credit, 6))
    for index, line in enumerate(spec.opening_lines, start=1):
        out.append("      <obLine>\n")
        out.append(_tag("nr", str(index), 8))
        out.append(_tag("accID", line.accID, 8))
        out.append(_tag("amnt", line.amnt, 8))
        out.append(_tag("amntTp", line.amntTp, 8))
        out.append("      </obLine>\n")
    out.append("    </openingBalance>\n")

    all_pairs = [
        (line.amnt, line.amntTp)
        for journal in spec.journals
        for transaction in journal.transactions
        for line in transaction.lines
    ]
    count, debit, credit = spec.transaction_totals_override or _totals(all_pairs)
    out.append("    <transactions>\n")
    out.append(_tag("linesCount", str(count), 6))
    out.append(_tag("totalDebit", debit, 6))
    out.append(_tag("totalCredit", credit, 6))
    for journal in spec.journals:
        out.append("      <journal>\n")
        out.append(_tag("jrnID", journal.jrnID, 8))
        out.append(_tag("desc", journal.desc, 8))
        out.append(_tag("jrnTp", journal.jrnTp, 8))
        for transaction in journal.transactions:
            out.append("        <transaction>\n")
            out.append(_tag("nr", transaction.nr, 10))
            out.append(_tag("desc", transaction.desc, 10))
            out.append(_tag("periodNumber", str(transaction.periodNumber), 10))
            out.append(_tag("trDt", transaction.trDt, 10))
            for index, line in enumerate(transaction.lines, start=1):
                out.append("          <trLine>\n")
                out.append(_tag("nr", str(index), 12))
                out.append(_tag("accID", line.accID, 12))
                out.append(_tag("docRef", line.docRef, 12))
                out.append(_tag("effDate", line.effDate, 12))
                out.append(_tag("desc", line.desc, 12))
                out.append(_tag("amnt", line.amnt, 12))
                out.append(_tag("amntTp", line.amntTp, 12))
                out.append(_tag("custSupID", line.custSupID, 12))
                out.append(_tag("invRef", line.invRef, 12))
                if line.vatID:
                    out.append("            <vat>\n")
                    out.append(_tag("vatID", line.vatID, 14))
                    out.append(_tag("vatPerc", line.vatPerc, 14))
                    out.append(_tag("vatAmnt", line.vatAmnt, 14))
                    out.append(_tag("vatAmntTp", line.vatAmntTp, 14))
                    out.append("            </vat>\n")
                out.append("          </trLine>\n")
            out.append("        </transaction>\n")
        out.append("      </journal>\n")
    out.append("    </transactions>\n")
    out.append("  </company>\n")
    out.append("</auditfile>\n")
    return "".join(out).encode("utf-8")


# --- Standaardvoorbeeld -----------------------------------------------------

STANDAARD_REKENINGEN = [
    Account("0100", "Inventaris", "B", "BMvaBeg", "BMvaBeg"),
    Account("0500", "Eigen vermogen", "B", "BEivKap", "BEivKap"),
    Account("1000", "Kas", "B", "BLimKas", "BLimKas"),
    Account("1100", "Bank", "B", "BLimBan", "BLimBan"),
    Account("1300", "Debiteuren", "B", "BVorDeb", "BVorDeb"),
    Account("1600", "Crediteuren", "B", "BSchCre", "BSchCre"),
    Account("1800", "Omzetbelasting", "B", "BSchObr", "BSchObr"),
    Account("1810", "Te vorderen omzetbelasting", "B", "BVorVbb", "BVorVbb"),
    Account("2900", "Nog te betalen kosten", "B", "BSchOva", "BSchOva"),
    Account("4000", "Huur bedrijfspand", "P", "WBedHui", "WBedHui"),
    Account("4100", "Autolease", "P", "WBedAut", "WBedAut"),
    Account("4200", "Brutolonen", "P", "WPerLes", "WPerLes"),
    Account("4300", "Afschrijving inventaris", "P", "WAfsIna", "WAfsIna"),
    Account("4400", "Advocaatkosten", "P", "WBedAlg", "WBedAlg"),
    Account("4500", "Boetes en dwangsommen", "P", "WBedAlg", "WBedAlg"),
    Account("8000", "Omzet hoog tarief", "P", "WOmzNeh", "WOmzNeh"),
    Account("8100", "Omzet laag tarief", "P", "WOmzNel", "WOmzNel"),
    Account("8200", "Omzet verlegd", "P", "WOmzNeo", "WOmzNeo"),
]

STANDAARD_BTW_CODES = [
    VatCode("1", "Omzet hoog 21%", vatToPayAccID="1800"),
    VatCode("2", "Omzet laag 9%", vatToPayAccID="1800"),
    VatCode("3", "Voorbelasting hoog 21%", vatToClaimAccID="1810"),
    VatCode("4", "Omzet verlegd", vatToPayAccID="1800"),
    VatCode("5", "Btw verlegd ontvangen", vatToPayAccID="1800", vatToClaimAccID="1810"),
]


def eenvoudige_spec(versie: str = "4.0") -> AuditfileSpec:
    """Een klein, sluitend auditfile met een handvol herkenbare boekingen."""
    journals = [
        Journal(
            "VRK",
            "Verkoopboek",
            [
                Transaction(
                    "V001",
                    "2025-01-31",
                    1,
                    [
                        Line("1300", "1210.00", "D", "Verkoopfactuur", custSupID="D001", invRef="F001"),
                        Line(
                            "8000",
                            "1000.00",
                            "C",
                            "Omzet hoog",
                            vatID="1",
                            vatPerc="21",
                            vatAmnt="210.00",
                            vatAmntTp="C",
                        ),
                        Line("1800", "210.00", "C", "Btw hoog"),
                    ],
                ),
                Transaction(
                    "V002",
                    "2025-02-28",
                    2,
                    [
                        Line("1300", "109.00", "D", "Verkoopfactuur laag", custSupID="D001"),
                        Line(
                            "8100",
                            "100.00",
                            "C",
                            "Omzet laag",
                            vatID="2",
                            vatPerc="9",
                            vatAmnt="9.00",
                            vatAmntTp="C",
                        ),
                        Line("1800", "9.00", "C", "Btw laag"),
                    ],
                ),
                # Creditnota geschreven als negatief bedrag binnen dezelfde zijde.
                Transaction(
                    "V003",
                    "2025-03-31",
                    3,
                    [
                        Line("1300", "-242.00", "D", "Creditnota", custSupID="D001"),
                        Line(
                            "8000",
                            "-200.00",
                            "C",
                            "Omzetcorrectie",
                            vatID="1",
                            vatPerc="21",
                            vatAmnt="-42.00",
                            vatAmntTp="C",
                        ),
                        Line("1800", "-42.00", "C", "Btw-correctie"),
                    ],
                ),
            ],
        ),
        Journal(
            "INK",
            "Inkoopboek",
            [
                Transaction(
                    "I001",
                    f"2025-{maand:02d}-15",
                    maand,
                    [
                        Line(
                            "4000",
                            "1000.00",
                            "D",
                            "Huur bedrijfspand",
                            vatID="3",
                            vatPerc="21",
                            vatAmnt="210.00",
                            vatAmntTp="D",
                        ),
                        Line("1810", "210.00", "D", "Voorbelasting"),
                        Line("1600", "1210.00", "C", "Crediteur", custSupID="C001"),
                    ],
                )
                for maand in range(1, 13)
            ],
        ),
        Journal(
            "MEM",
            "Memoriaal",
            [
                Transaction(
                    "M001",
                    "2025-12-31",
                    12,
                    [
                        Line("4300", "2400.00", "D", "Afschrijving"),
                        Line("0100", "2400.00", "C", "Afschrijving inventaris"),
                    ],
                ),
                Transaction(
                    "M002",
                    "2025-12-31",
                    12,
                    [
                        Line("4400", "5000.00", "D", "Advocaatkosten"),
                        Line("4500", "750.00", "D", "Verkeersboete"),
                        Line("2900", "5750.00", "C", "Nog te betalen"),
                    ],
                ),
            ],
        ),
    ]

    return AuditfileSpec(
        versie=versie,
        accounts=list(STANDAARD_REKENINGEN),
        vat_codes=list(STANDAARD_BTW_CODES),
        relations=[
            Relation("D001", "Afnemer Alfa BV", "C"),
            Relation("C001", "Leverancier Beta BV", "S"),
        ],
        opening_lines=[
            OpeningLine("0100", "12000.00", "D"),
            OpeningLine("1100", "8000.00", "D"),
            OpeningLine("1600", "20000.00", "C"),
        ],
        journals=journals,
    )


# --- Twee opeenvolgende boekjaren -------------------------------------------

# De rekening waarop het resultaat van vorig jaar wordt bestemd.
EIGEN_VERMOGEN_REKENING = "0500"


def verschuif_boekjaar(spec: AuditfileSpec, boekjaar: str) -> AuditfileSpec:
    """Zet een spec om naar een ander boekjaar.

    Alle datums schuiven mee, zodat de boekingen binnen het boekjaar blijven
    vallen en de periodencontrole klopt.
    """
    spec.fiscal_year = boekjaar
    spec.start_date = f"{boekjaar}-01-01"
    spec.end_date = f"{boekjaar}-12-31"
    for journaal in spec.journals:
        for transactie in journaal.transactions:
            transactie.trDt = f"{boekjaar}{transactie.trDt[4:]}"
            for regel in transactie.lines:
                regel.effDate = f"{boekjaar}{regel.effDate[4:]}"
    return spec


def beginbalans_uit(xaf_bytes: bytes, eigen_vermogen: str = EIGEN_VERMOGEN_REKENING) -> list[OpeningLine]:
    """De beginbalans die volgt op een gegeven auditfile.

    Per balansrekening het eindsaldo, met het resultaat van dat jaar bestemd op
    de eigenvermogensrekening. Zo sluit het volgende boekjaar aan, precies zoals
    de jaarovergangscontrole verwacht: buiten het eigen vermogen gelijk aan de
    eindstand, en het eigen vermogen toegenomen met het resultaat.
    """
    from .parsing import parse_auditfile

    af = parse_auditfile("vorig_jaar.xaf", xaf_bytes)
    if af.saldo.empty:
        return []
    is_balans = af.saldo["accTp"].astype(str).str.upper().eq("B")
    resultaat = float(af.saldo.loc[~is_balans, "mutaties_boekjaar"].sum())

    saldi: dict[str, float] = {
        str(rij.rekening): float(rij.eindsaldo) for rij in af.saldo[is_balans].itertuples()
    }
    saldi[eigen_vermogen] = saldi.get(eigen_vermogen, 0.0) + resultaat

    regels = []
    for rekening, saldo in sorted(saldi.items()):
        if abs(saldo) < 0.005:
            continue
        regels.append(
            OpeningLine(rekening, f"{abs(saldo):.2f}", "D" if saldo > 0 else "C")
        )
    return regels


# In de demo boekt elke relatie op één eigen balansrekening. Daardoor is de
# openstaande stand per relatie gelijk aan het saldo van die rekening en laat de
# demo een sluitende aansluiting zien. Een verschil hoort in een test thuis en
# niet in de demodata, want daar zou het op een fout in de tool lijken.
DEMO_RELATIEREKENING = {"D001": "1300", "C001": "1600"}


def vul_relatiesaldi(spec: AuditfileSpec) -> AuditfileSpec:
    """Geef elke relatie het openstaande bedrag van haar grootboekrekening.

    Alleen zinvol bij XAF 4.0; in 3.2 worden de velden niet weggeschreven. De
    saldi worden uit het bestand zelf gehaald in plaats van ingetypt, zodat de
    demo blijft aansluiten wanneer de boekingen veranderen.

    Werkt op een kopie: de specs zijn testfixtures met sessiebereik en een
    wijziging in het ene geval zou anders in het andere opduiken.
    """
    from .parsing import parse_auditfile

    kopie = deepcopy(spec)
    saldi = parse_auditfile("demo.xaf", build_xaf(kopie)).saldo.set_index("rekening")
    for relatie in kopie.relations:
        rekening = DEMO_RELATIEREKENING.get(relatie.custSupID)
        if rekening is None or rekening not in saldi.index:
            continue
        for saldokolom, bedrag_attr, type_attr in (
            ("beginsaldo", "openstaand_begin", "openstaand_begin_tp"),
            ("eindsaldo", "openstaand_eind", "openstaand_eind_tp"),
        ):
            saldo = float(saldi.at[rekening, saldokolom])
            setattr(relatie, bedrag_attr, f"{abs(saldo):.2f}")
            setattr(relatie, type_attr, "C" if saldo < 0 else "D")
    return kopie


def demopaar(
    vorig_jaar: str = "2024",
    huidig_jaar: str = "2025",
    versie_vorig: str = "3.2",
    versie_huidig: str = "4.0",
) -> tuple[bytes, bytes]:
    """Twee synthetische auditfiles die op elkaar aansluiten.

    Het tweede jaar begint met de eindbalans van het eerste, inclusief de
    bestemming van het resultaat. Daardoor laat de demo zien hoe een kloppende
    jaarovergang eruitziet, in plaats van een verschil te tonen dat alleen aan
    de demodata ligt. De twee XAF-versies verschillen bewust, zodat ook de
    RGS-herkomst zichtbaar is.
    """
    vorige_bytes = build_xaf(verschuif_boekjaar(eenvoudige_spec(versie_vorig), vorig_jaar))
    huidige_spec = verschuif_boekjaar(eenvoudige_spec(versie_huidig), huidig_jaar)
    huidige_spec.opening_lines = beginbalans_uit(vorige_bytes)
    if versie_huidig == "4.0":
        huidige_spec = vul_relatiesaldi(huidige_spec)
    return vorige_bytes, build_xaf(huidige_spec)
