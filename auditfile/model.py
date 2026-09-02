"""Datamodel voor een ingelezen auditfile.

Alle analysefuncties werken op een ``Auditfile``. Door de gegevens in een
dataclass te bundelen in plaats van in ``DataFrame.attrs`` blijven ze bewaard
bij ``copy()``, ``merge()`` en het pickelen door de Streamlit-cache.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Kolommen van de grootboekrekeningtabel.
ACCOUNT_COLUMNS = ["accID", "accDesc", "accTp", "RGScode", "RGSbron"]

# Kolommen die per boekingsregel uit de transactie worden overgenomen.
TRANSACTION_COLUMNS = [
    "tx_nr",
    "tx_desc",
    "tx_periodNumber",
    "tx_trDt",
    "tx_jrnID",
    "tx_jrn_desc",
    "tx_jrn_jrnTp",
]

# Kolommen van de boekingsregel zelf.
LINE_COLUMNS = [
    "line_nr",
    "line_accID",
    "line_docRef",
    "line_effDate",
    "line_desc",
    "line_amnt",
    "line_amntTp",
    "line_invRef",
    "line_orderRef",
    "line_custSupID",
    "line_vatID",
]

# Kolommen van het optionele <vat>-blok onder een boekingsregel.
VAT_LINE_COLUMNS = ["vat_vatID", "vat_vatPerc", "vat_vatAmnt", "vat_vatAmntTp"]

VAT_CODE_COLUMNS = ["vatID", "vatDesc", "vatToPayAccID", "vatToClaimAccID"]

RELATION_COLUMNS = [
    "custSupID",
    "custSupName",
    "custSupTp",
    "commerceNr",
    "taxRegIdent",
    "taxRegistrationCountry",
]

SALDO_COLUMNS = [
    "rekening",
    "accDesc",
    "accTp",
    "RGScode",
    "beginsaldo",
    "mutaties_boekjaar",
    "eindsaldo",
    "saldo",
    "aantal_boekingsregels",
]

COMPANY_INFO_COLUMNS = ["Onderdeel", "Waarde"]


def empty_saldo() -> pd.DataFrame:
    return pd.DataFrame(columns=SALDO_COLUMNS)


@dataclass
class ControlTotals:
    """Controletotalen zoals het bronbestand ze zelf opgeeft."""

    lines_count: int | None = None
    total_debit: float | None = None
    total_credit: float | None = None


@dataclass
class Auditfile:
    """Een volledig ingelezen XAF-auditfile."""

    bestandsnaam: str = ""
    xaf_versie: str = ""
    # Vingerafdruk van de bytes van het bronbestand. Twee bestanden met dezelfde
    # naam maar andere inhoud zijn hieraan te onderscheiden; de bestandsnaam
    # alleen is geen betrouwbare sleutel.
    vingerafdruk: str = ""
    company: dict[str, str] = field(default_factory=dict)
    header: dict[str, str] = field(default_factory=dict)
    accounts: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ACCOUNT_COLUMNS))
    vat_codes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=VAT_CODE_COLUMNS))
    relations: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=RELATION_COLUMNS))
    lines: pd.DataFrame = field(default_factory=pd.DataFrame)
    opening_balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    saldo: pd.DataFrame = field(default_factory=empty_saldo)
    periods: pd.DataFrame = field(default_factory=pd.DataFrame)
    opening_totals: ControlTotals = field(default_factory=ControlTotals)
    transaction_totals: ControlTotals = field(default_factory=ControlTotals)
    # Stamgegevens die in het bronbestand meer dan eens voorkwamen, per soort de
    # betrokken identificaties. De parser houdt het eerste record aan; zonder
    # deze vastlegging vóór het opschonen zou de controle op dubbelingen altijd
    # nul vinden en daarmee de indruk wekken dat er geen dubbeling is.
    duplicaten: dict[str, list[str]] = field(default_factory=dict)

    @property
    def boekjaar(self) -> str:
        return self.header.get("fiscalYear", "")

    @property
    def bedrijfsnaam(self) -> str:
        return self.company.get("companyName", "")

    @property
    def period_labels(self) -> dict[int, str]:
        """Periodenummer -> korte maandnaam, voor leesbare periodeaanduidingen."""
        if self.periods.empty or "periodNumber" not in self.periods.columns:
            return {}
        return {
            int(row["periodNumber"]): str(row["maand"])
            for _, row in self.periods.iterrows()
            if pd.notna(row.get("periodNumber"))
        }

    def company_info_frame(self) -> pd.DataFrame:
        """Bedrijfs- en bestandsgegevens als tabel van twee kolommen."""
        rows = [
            ("Bedrijfsnaam", self.company.get("companyName", "")),
            ("KvK-nummer", self.company.get("Commercenr") or self.company.get("companyIdent", "")),
            ("BTW-nummer", self.company.get("taxRegIdent", "")),
            ("BTW-land", self.company.get("taxRegistrationCountry", "")),
            ("Boekjaar", self.header.get("fiscalYear", "")),
            ("Startdatum", self.header.get("startDate", "")),
            ("Einddatum", self.header.get("endDate", "")),
            ("Valuta", self.header.get("curCode", "")),
            ("Aangemaakt op", self.header.get("dateCreated", "")),
            ("Software", self.header.get("softwareDesc", "")),
            ("Softwareversie", self.header.get("softwareVersion", "")),
            ("XAF-versie", self.xaf_versie),
            ("RGS-versie", self.header.get("RGSVersion", "")),
        ]
        return pd.DataFrame(rows, columns=COMPANY_INFO_COLUMNS)
