"""Datamodel voor een ingelezen auditfile.

Alle analysefuncties werken op een ``Auditfile``. Door de gegevens in een
dataclass te bundelen in plaats van in ``DataFrame.attrs`` blijven ze bewaard
bij ``copy()``, ``merge()`` en het pickelen door de Streamlit-cache.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

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
    # Het openstaande bedrag per relatie bij begin en einde van het boekjaar.
    # Deze twee bestaan alleen in XAF 4.0 (opBalDesc/clBalDesc met opBalTp/
    # clBalTp); in 3.2 blijven ze leeg. Ze staan hier al getekend, volgens
    # dezelfde regel als elders: debet positief, credit negatief. Daardoor is een
    # debiteurenstand positief en een crediteurenstand negatief, gelijk aan het
    # grootboeksaldo, en hoeft geen enkele analysefunctie het teken nog om te
    # rekenen of naar de XAF-versie te vragen. Leeg is NaN en niet nul: een
    # ongevulde stand is iets anders dan een stand van nul.
    "openstaand_begin",
    "openstaand_eind",
]

# Kolommen van de subadministratie van XAF 3.2: de openstaande posten bij het
# begin van het boekjaar (obSbLine) en de mutaties daarin (sbLine). Beide
# blokken staan in één tabel, want ze delen bijna al hun velden en de
# openstaande post is pas te bepalen uit begin plus verloop. De kolom "bron"
# houdt ze onderscheiden.
#
# Geen van beide regelsoorten heeft een eigen rekeningnummer. De rekening volgt
# uit een verwijzing: obSbLine draagt obLineNr naar een regel van de beginbalans,
# sbLine draagt jrnID, trNr en trLineNr naar een grootboekboeking. De parser lost
# die verwijzing op en legt in "koppeling" vast hoe dat is gegaan, zodat een
# regel zonder rekening zichtbaar niet gekoppeld is in plaats van stil op nul te
# staan.
SUBADMINISTRATIE_COLUMNS = [
    "bron",
    "sb_index",
    "sbType",
    "sbDesc",
    "sb_nr",
    "rekening",
    "koppeling",
    "obLineNr",
    "jrnID",
    "trNr",
    "trLineNr",
    "custSupID",
    "invRef",
    "invTp",
    "invPurSalTp",
    "invDt",
    "invDueDt",
    "matchKeyID",
    "mutTp",
    "omschrijving",
    "documentreferentie",
    "amntTp",
    "bedrag",
]

# Elke subadministratie geeft zijn eigen controletotalen op. Ze staan naast wat
# de parser werkelijk heeft gelezen, zodat een onvolledig ingelezen blok opvalt.
# Het oordeel daarover hoort in integrity.py en niet hier.
SUBADMINISTRATIE_TOTALEN_COLUMNS = [
    "bron",
    "sb_index",
    "sbType",
    "sbDesc",
    "regels_volgens_bestand",
    "totaal_debet_volgens_bestand",
    "totaal_credit_volgens_bestand",
    "regels_gelezen",
    "totaal_debet_gelezen",
    "totaal_credit_gelezen",
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


def empty_subadministratie() -> pd.DataFrame:
    """Een lege subadministratie met de juiste typen.

    De typen worden ook leeg gezet, zodat een analyse op een bestand zonder
    subadministratie dezelfde kolommen en dezelfde dtypes ziet als op een
    bestand met. Een lege objectkolom waar een datum wordt verwacht laat een
    filter stil mislukken.
    """
    leeg = pd.DataFrame(columns=SUBADMINISTRATIE_COLUMNS)
    leeg["sb_index"] = pd.Series(dtype="Int64")
    for kolom in ("invDt", "invDueDt"):
        leeg[kolom] = pd.Series(dtype="datetime64[ns]")
    leeg["bedrag"] = pd.Series(dtype="float64")
    return leeg


def empty_subadministratie_totalen() -> pd.DataFrame:
    return pd.DataFrame(columns=SUBADMINISTRATIE_TOTALEN_COLUMNS)


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
    # De subadministratie van XAF 3.2: openstaande posten bij het begin van het
    # boekjaar en de mutaties daarin, met de factuurdatum, de vervaldatum en het
    # afletterkenmerk. Dit is de enige bron in XAF met een echte vervaldatum. Bij
    # XAF 4.0 zijn deze blokken geschrapt en blijven de tabellen leeg.
    subadministratie: pd.DataFrame = field(default_factory=empty_subadministratie)
    subadministratie_totalen: pd.DataFrame = field(
        default_factory=empty_subadministratie_totalen
    )
    # Tellingen van gegevensblokken die deze tool niet als tabel inleest maar die
    # bepalen wat er aan analyse mogelijk is: de openstaande bedragen per relatie
    # van XAF 4.0 en de leverdatum. Zie capability.py.
    blokken: dict[str, int] = field(default_factory=dict)

    @property
    def boekjaar(self) -> str:
        return self.header.get("fiscalYear", "")

    @property
    def bedrijfsnaam(self) -> str:
        return self.company.get("companyName", "")

    @property
    def valuta(self) -> str:
        return self.header.get("curCode", "")

    @property
    def dossier_identiteit(self) -> str:
        """De sterkste identificatie van de onderneming die het bestand geeft.

        Het btw-identificatienummer gaat voor, dan het KvK-nummer, dan de naam.
        Een naam is de zwakste: die verandert bij een statutaire wijziging en kan
        anders gespeld zijn. Daarom wordt hij pas gebruikt als de nummers
        ontbreken.
        """
        kandidaten = (
            self.company.get("taxRegIdent", ""),
            self.company.get("Commercenr", ""),
            self.company.get("companyIdent", ""),
            self.company.get("companyName", ""),
        )
        for kandidaat in kandidaten:
            schoon = str(kandidaat).strip()
            if schoon:
                return schoon
        return ""

    @property
    def dossier_sleutel(self) -> str:
        """Sleutel voor onderneming plus boekjaar, om invoer aan te hangen.

        Eigen invoer hoort bij één onderneming en één boekjaar, niet bij een
        bestand: levert de klant een gecorrigeerd auditfile over hetzelfde jaar,
        dan blijft de beoordeling geldig. De sleutel is een korte hash, zodat er
        geen ondernemingsnaam of nummer in een mapnaam op schijf komt te staan.

        Zonder identificatie en zonder boekjaar is er geen sleutel: dan valt de
        invoer nergens aan te hangen en zegt de tool dat liever dan iets te
        bewaren onder een sleutel die morgen bij een ander dossier hoort.
        """
        identiteit = self.dossier_identiteit
        if not identiteit or not self.boekjaar:
            return ""
        ruw = f"{identiteit}|{self.boekjaar}".encode("utf-8")
        return hashlib.blake2b(ruw, digest_size=8).hexdigest()

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
