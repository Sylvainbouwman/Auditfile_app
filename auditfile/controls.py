"""Analytische controles op de auditfile.

De controles hier zijn signalen, geen oordelen. Elke uitkomst benoemt wat er is
gezien en wat er beoordeeld moet worden; de tool trekt geen fiscale conclusie
die de gebruiker niet kan narekenen.

Rekeningen worden zoveel mogelijk ingedeeld op RGS-code, omdat die uit het
bestand zelf komt. Alleen wanneer die ontbreekt of niets oplevert, valt de
indeling terug op de omschrijving. Welke weg is gebruikt, staat in de uitkomst.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import Auditfile

# Hoofdrubrieken van het Referentiemodel Generieke Structuur.
RGS_RUBRIEKEN = {
    "BEiv": "Eigen vermogen",
    "BIva": "Immateriele vaste activa",
    "BLas": "Langlopende schulden",
    "BLim": "Liquide middelen",
    "BMva": "Materiele vaste activa",
    "BSch": "Kortlopende schulden",
    "BVor": "Vorderingen",
    "BVrd": "Voorraden",
    "WAfs": "Afschrijvingen",
    "WBed": "Bedrijfskosten",
    "WBel": "Belastingen resultaat",
    "WFbe": "Financiele baten en lasten",
    "WKpr": "Kostprijs van de omzet",
    "WOmz": "Netto-omzet",
    "WPer": "Personeelskosten",
}


def rgs_rubriek(code) -> str:
    """De hoofdrubriek bij een RGS-code, of leeg als die onbekend is."""
    tekst = str(code or "").strip()
    if not tekst:
        return ""
    return RGS_RUBRIEKEN.get(tekst[:4], "")


def voeg_rgs_rubriek_toe(df: pd.DataFrame, kolom: str = "RGScode") -> pd.DataFrame:
    result = df.copy()
    result["RGS-rubriek"] = result[kolom].map(rgs_rubriek)
    return result


def _selecteer(
    df: pd.DataFrame,
    rgs_prefix: str | tuple[str, ...] | None,
    patroon: str | None,
    omschrijvingskolom: str = "accDesc",
    rekeningtype: str | None = None,
) -> tuple[pd.Series, str]:
    """Selecteer rekeningen op RGS-code, met de omschrijving als terugval.

    De keuze valt per rekening, niet per controle. Heeft een rekening een
    RGS-code, dan beslist die code: matcht het voorvoegsel niet, dan hoort de
    rekening er niet bij, ook al zegt de omschrijving iets anders. Heeft een
    rekening geen RGS-code, dan is de omschrijving het enige dat er is en beslist
    die.

    Waarom per rekening en niet per controle: in een schema waarin één rekening
    een RGS-code heeft, schakelde de hele controle over op RGS en vielen alle
    niet-gecodeerde rekeningen buiten de selectie. Dat komt voor, want een
    XAF 3.2 levert hooguit een ``leadReference`` en pakketten coderen soms maar
    een deel van het schema.

    Waarom niet de unie van beide: dan zou een zoekterm als "omzet" ook
    "Omzetbelasting" vinden, en dat is een balansrekening. Doordat de
    omschrijving alleen wordt gebruikt bij rekeningen zonder RGS-code, blijft de
    RGS-code beslissend waar hij er is. Het ``rekeningtype`` sluit balans- en
    resultaatrekeningen bovendien hard van elkaar af.

    Geeft het masker terug plus de gebruikte methode, zodat de tool kan tonen
    waarop een controle zich baseert.
    """
    if rekeningtype:
        toegestaan = df["accTp"].astype(str).str.strip().str.upper().eq(rekeningtype.upper())
    else:
        toegestaan = pd.Series(True, index=df.index)

    codes = df["RGScode"].astype(str).str.strip() if "RGScode" in df.columns else pd.Series(
        "", index=df.index
    )
    heeft_rgs = codes != ""

    op_rgs = pd.Series(False, index=df.index)
    if rgs_prefix:
        prefixen = (rgs_prefix,) if isinstance(rgs_prefix, str) else rgs_prefix
        for prefix in prefixen:
            op_rgs |= codes.str.startswith(prefix)
    op_rgs &= toegestaan

    op_naam = pd.Series(False, index=df.index)
    if patroon:
        op_naam = df[omschrijvingskolom].astype(str).str.contains(
            patroon, case=False, na=False, regex=True
        )
        op_naam &= toegestaan
        if rgs_prefix:
            # Alleen waar geen RGS-code staat; anders zou de omschrijving een
            # code kunnen overrulen die deze rekening juist uitsluit. Is er geen
            # RGS-voorvoegsel voor deze controle, dan valt er niets te
            # overrulen: RGS kent niet voor alles een rubriek, en dan is de
            # omschrijving de enige methode die er is.
            op_naam &= ~heeft_rgs

    masker = op_rgs | op_naam
    if not masker.any():
        return masker, "geen treffers"
    if op_rgs.any() and op_naam.any():
        return masker, "RGS-code en omschrijving"
    return masker, "RGS-code" if op_rgs.any() else "omschrijving"


# --- Boekingsperioden -------------------------------------------------------


def _periodenreeksen(af: Auditfile) -> list[tuple[int, str, str]]:
    """Periodenummer met begin- en einddatum, op nummer gesorteerd."""
    if af.periods.empty or "periodNumber" not in af.periods.columns:
        return []
    reeksen = []
    for _, rij in af.periods.iterrows():
        nummer = pd.to_numeric(rij.get("periodNumber"), errors="coerce")
        if pd.isna(nummer):
            continue
        reeksen.append(
            (
                int(nummer),
                str(rij.get("startDatePeriod", "") or "").strip(),
                str(rij.get("endDatePeriod", "") or "").strip(),
            )
        )
    return sorted(reeksen)


def boekingsperioden(af: Auditfile) -> list[int]:
    """De perioden waarin je boekingen mag verwachten.

    De periodetabel bevat niet alleen de gewone boekingsperioden. Pakketten
    zetten er ook een periode 0 in voor de beginbalans en een periode 13 of 14
    voor de jaarafsluiting. Die meerekenen levert onterechte signalen op: dan
    ontbreken de huur en de lonen "in periode 13", terwijl daar niets hoort te
    staan.

    Een periode geldt als boekingsperiode wanneer zij een echt tijdvak beslaat
    (einddatum na begindatum) en niet overlapt met een eerder aanvaarde periode.
    Daarmee vallen een afsluitperiode van één dag en een periode 13 die december
    nog eens overdoet er allebei buiten, terwijl een administratie met dertien
    vierwekelijkse perioden gewoon dertien perioden houdt.

    Ontbreken de datums, dan is er niets te toetsen en gelden alle perioden vanaf
    1; het alternatief zou een aanname over de nummering zijn.
    """
    reeksen = _periodenreeksen(af)
    if not reeksen:
        return []
    if any(not start or not eind for _, start, eind in reeksen):
        return [nummer for nummer, _, _ in reeksen if nummer >= 1]

    aanvaard: list[tuple[int, str, str]] = []
    for nummer, start, eind in reeksen:
        if nummer < 1 or eind <= start:
            continue
        if any(start <= eerder_eind and eerder_start <= eind for _, eerder_start, eerder_eind in aanvaard):
            continue
        aanvaard.append((nummer, start, eind))
    return [nummer for nummer, _, _ in aanvaard]


def afsluitperioden(af: Auditfile) -> list[int]:
    """De perioden uit de tabel die geen gewone boekingsperiode zijn."""
    regulier = set(boekingsperioden(af))
    return [nummer for nummer, _, _ in _periodenreeksen(af) if nummer not in regulier]


# --- Periodieke controles ---------------------------------------------------

# Kostensoorten waarvan een boeking in elke periode wordt verwacht, met de
# zoektermen en of het ontbreken van een periode een signaal is.
PERIODIEKE_CONTROLES: tuple[tuple[str, str | tuple[str, ...] | None, str, bool], ...] = (
    ("Huur en pacht", None, r"\bhuur\b|pacht", True),
    ("Lease", None, r"lease|leasing", True),
    ("Lonen en salarissen", "WPer", r"loon|salaris|wages|payroll", True),
    ("Afschrijvingen", "WAfs", r"afschrijving|depreciation", True),
    ("Verzekeringen", None, r"verzekering|insurance", False),
    ("Rente", "WFbe", r"rentelast|rentekost|rentebat|\binterest\b", False),
    ("Abonnementen en contributies", None, r"abonnement|contributie|licentie", False),
)

# Een periode wijkt sterk af als hij meer dan de helft van het gemiddelde
# afwijkt. Bewust ruim: maandelijkse kosten schommelen.
AFWIJKINGSDREMPEL = 0.5


def build_periodieke_controles(af: Auditfile) -> pd.DataFrame:
    """Controleer of periodieke kosten in elke periode voorkomen."""
    kolommen = [
        "controle",
        "rekening",
        "omschrijving",
        "methode",
        "aantal_perioden",
        "perioden",
        "ontbrekende_perioden",
        "totaalbedrag",
        "gemiddeld_per_periode",
        "grootste_afwijking",
        "conclusie",
        "toelichting",
    ]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    lines = lines[lines["periode"].notna()].copy()
    if lines.empty:
        return pd.DataFrame(columns=kolommen)
    lines["periode"] = lines["periode"].astype(int)

    # Het aantal perioden komt uit de periodetabel; alleen als die ontbreekt
    # wordt teruggevallen op de hoogste periode die daadwerkelijk voorkomt.
    regulier = boekingsperioden(af)
    if regulier:
        verwachte_perioden = set(regulier)
    else:
        verwachte_perioden = set(range(1, int(lines["periode"].max()) + 1))

    rijen = []
    for naam, rgs_prefix, patroon, verwacht_alle_perioden in PERIODIEKE_CONTROLES:
        masker, methode = _selecteer(lines, rgs_prefix, patroon, rekeningtype="P")
        selectie = lines[masker]
        if selectie.empty:
            continue

        for (rekening, omschrijving), regels in selectie.groupby(["line_accID", "accDesc"], dropna=False):
            per_periode = regels.groupby("periode")["bedrag"].sum().sort_index()
            aanwezig = [int(periode) for periode in per_periode.index]
            aantal = len(aanwezig)
            totaal = float(per_periode.sum())
            gemiddelde = totaal / aantal if aantal else 0.0
            afwijking = float((per_periode - gemiddelde).abs().max()) if aantal else 0.0

            ontbrekend: list[int] = []
            if verwacht_alle_perioden or aantal >= len(verwachte_perioden) - 2:
                ontbrekend = sorted(verwachte_perioden - set(aanwezig))

            sterke_afwijking = (
                aantal > 1
                and abs(gemiddelde) > 0.005
                and afwijking > abs(gemiddelde) * AFWIJKINGSDREMPEL
            )
            positief = per_periode[per_periode > 0.005]
            negatief = per_periode[per_periode < -0.005]
            tegengesteld: list[int] = []
            if len(positief) and len(negatief):
                if len(negatief) >= 2 * len(positief):
                    tegengesteld = sorted(int(p) for p in positief.index)
                elif len(positief) >= 2 * len(negatief):
                    tegengesteld = sorted(int(p) for p in negatief.index)

            if ontbrekend:
                conclusie = "Ontbrekende perioden"
                toelichting = (
                    f"In {len(ontbrekend)} van de {len(verwachte_perioden)} perioden is niets geboekt. "
                    "Controleer of de last is doorgeboekt of dat een overlopende post ontbreekt."
                )
            elif tegengesteld:
                conclusie = "Tegengestelde boeking"
                toelichting = (
                    f"Periode {', '.join(str(p) for p in tegengesteld)} heeft een tegengesteld teken. "
                    "Beoordeel of dit een correctie of een terugboeking is."
                )
            elif sterke_afwijking:
                percentage = round(afwijking / abs(gemiddelde) * 100)
                conclusie = "Sterke afwijking"
                toelichting = (
                    f"De grootste afwijking is {percentage}% van het gemiddelde, "
                    f"boven de drempel van {round(AFWIJKINGSDREMPEL * 100)}%."
                )
            elif not verwacht_alle_perioden and aantal < len(verwachte_perioden) - 2:
                conclusie = "Handmatig beoordelen"
                toelichting = "Deze post komt niet in elke periode voor; dat hoeft niet onjuist te zijn."
            else:
                conclusie = "Geen bijzonderheden"
                toelichting = ""

            rijen.append(
                {
                    "controle": naam,
                    "rekening": str(rekening),
                    "omschrijving": str(omschrijving),
                    "methode": methode,
                    "aantal_perioden": aantal,
                    "perioden": compacte_perioden(aanwezig, af.period_labels),
                    "ontbrekende_perioden": compacte_perioden(ontbrekend, af.period_labels),
                    "totaalbedrag": totaal,
                    "gemiddeld_per_periode": gemiddelde,
                    "grootste_afwijking": afwijking,
                    "conclusie": conclusie,
                    "toelichting": toelichting,
                }
            )

    if not rijen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(rijen, columns=kolommen).sort_values(["controle", "rekening"]).reset_index(drop=True)


def compacte_perioden(perioden: list[int], labels: dict[int, str] | None = None) -> str:
    """Vat een reeks perioden samen als ``jan-mrt, jun``."""
    if not perioden:
        return ""
    labels = labels or {}
    reeksen = []
    start = vorige = perioden[0]
    for periode in perioden[1:]:
        if periode == vorige + 1:
            vorige = periode
            continue
        reeksen.append((start, vorige))
        start = vorige = periode
    reeksen.append((start, vorige))

    def naam(periode: int) -> str:
        return labels.get(periode, str(periode))

    return ", ".join(naam(begin) if begin == eind else f"{naam(begin)}-{naam(eind)}" for begin, eind in reeksen)


# --- Ongebruikelijke boekingen ----------------------------------------------


def build_ongebruikelijke_boekingen(af: Auditfile, drempel_rond_bedrag: float = 1000.0) -> pd.DataFrame:
    """Boekingen met een patroon dat om een verklaring vraagt."""
    kolommen = ["signaal", "aantal_regels", "bedrag", "toelichting"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    signalen: list[dict] = []

    def voeg_toe(signaal: str, selectie: pd.DataFrame, toelichting: str) -> None:
        if selectie.empty:
            return
        signalen.append(
            {
                "signaal": signaal,
                "aantal_regels": len(selectie),
                "bedrag": float(selectie["bedrag"].abs().sum()),
                "toelichting": toelichting,
            }
        )

    datums = lines["datum"]
    met_datum = lines[datums.notna()]
    if not met_datum.empty:
        weekend = met_datum[met_datum["datum"].dt.dayofweek >= 5]
        voeg_toe(
            "Boeking op zaterdag of zondag",
            weekend,
            "Boekdatum in het weekend. Bij een geautomatiseerde administratie is dat "
            "normaal; bij handmatige invoer is het een aandachtspunt.",
        )

    # Grote memoriaalboekingen in de laatste periode.
    laatste = int(af.periods["periodNumber"].max()) if not af.periods.empty else 12
    is_memoriaal = lines["tx_jrn_jrnTp"].astype(str).str.upper().eq("M") | lines[
        "tx_jrn_desc"
    ].astype(str).str.contains("memoriaal", case=False, na=False)
    grens = float(lines["bedrag"].abs().quantile(0.95)) if len(lines) > 20 else 0.0
    voeg_toe(
        f"Grote memoriaalboeking in periode {laatste}",
        lines[is_memoriaal & (lines["periode"] == laatste) & (lines["bedrag"].abs() > grens)],
        "Memoriaalboekingen in de laatste periode boven de 95e percentiel van alle "
        "bedragen. Dit zijn doorgaans de jaarafsluitposten; beoordeel de onderbouwing.",
    )

    # Ronde bedragen boven een drempel.
    rond = (lines["bedrag"].abs() >= drempel_rond_bedrag) & (lines["bedrag"] % 1000 == 0)
    voeg_toe(
        "Rond bedrag",
        lines[rond],
        f"Bedragen van minimaal {drempel_rond_bedrag:.0f} euro die een veelvoud van 1.000 zijn. "
        "Vaak schattingen, reserveringen of doorbelastingen.",
    )

    # Negatieve omzet en negatieve loonkosten.
    is_omzet, _ = _selecteer(lines, "WOmz", r"omzet|opbrengst", rekeningtype="P")
    voeg_toe(
        "Omzetboeking aan de debetzijde",
        lines[is_omzet & (lines["bedrag"] > 0)],
        "Omzet staat normaal credit. Debetboekingen zijn creditnota's of correcties.",
    )

    is_loon, _ = _selecteer(lines, "WPer", r"loon|salaris", rekeningtype="P")
    voeg_toe(
        "Loonkosten aan de creditzijde",
        lines[is_loon & (lines["bedrag"] < 0)],
        "Loonkosten staan normaal debet. Creditboekingen zijn terugboekingen of "
        "doorbelastingen; beoordeel de aansluiting met de salarisadministratie.",
    )

    if not signalen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(signalen, columns=kolommen)


# --- Relaties: debiteuren en crediteuren ------------------------------------


def build_relatie_analyse(af: Auditfile, soort: str = "debiteur", top: int = 20) -> pd.DataFrame:
    """Omzet of inkoop per relatie, met concentratie.

    Gebruikt ``custSupID`` op de boekingsregel; die staat in de auditfile maar
    bleef tot nu toe ongebruikt.
    """
    kolommen = ["relatie", "naam", "soort", "aantal_regels", "bedrag", "aandeel_pct"]
    lines = af.lines
    if lines.empty or (lines["line_custSupID"] == "").all():
        return pd.DataFrame(columns=kolommen)

    met_relatie = lines[lines["line_custSupID"] != ""].copy()
    is_balans = met_relatie["accTp"].astype(str).str.upper().eq("B")
    met_relatie = met_relatie[is_balans]
    if met_relatie.empty:
        return pd.DataFrame(columns=kolommen)

    namen = af.relations.set_index("custSupID")["custSupName"].to_dict() if not af.relations.empty else {}
    soorten = af.relations.set_index("custSupID")["custSupTp"].to_dict() if not af.relations.empty else {}

    # Een relatie wordt in haar geheel als debiteur of crediteur ingedeeld, niet
    # per boekingsregel: een creditnota aan een klant maakt die klant geen
    # leverancier. De soort uit de relatietabel gaat voor; ontbreekt die, dan
    # geeft het teken van het totaal van de relatie de doorslag.
    totalen = (
        met_relatie.groupby("line_custSupID", dropna=False)
        .agg(aantal_regels=("bedrag", "size"), bedrag=("bedrag", "sum"))
        .reset_index()
        .rename(columns={"line_custSupID": "relatie"})
    )
    totalen["soort"] = totalen["relatie"].map(soorten).fillna("")

    def is_gezocht(rij: pd.Series) -> bool:
        soort_code = str(rij["soort"]).strip().upper()
        if soort_code in {"C", "D"}:  # customer respectievelijk debiteur
            return soort == "debiteur"
        if soort_code in {"S", "K"}:  # supplier respectievelijk crediteur
            return soort == "crediteur"
        return rij["bedrag"] > 0 if soort == "debiteur" else rij["bedrag"] < 0

    resultaat = totalen[totalen.apply(is_gezocht, axis=1)].copy()
    if resultaat.empty:
        return pd.DataFrame(columns=kolommen)
    resultaat["bedrag"] = resultaat["bedrag"].abs()
    resultaat["naam"] = resultaat["relatie"].map(namen).fillna("")
    totaal = resultaat["bedrag"].sum()
    resultaat["aandeel_pct"] = resultaat["bedrag"] / totaal * 100 if totaal else 0.0
    return (
        resultaat.sort_values("bedrag", ascending=False)
        .head(top)[kolommen]
        .reset_index(drop=True)
    )


def build_relatie_concentratie(af: Auditfile) -> pd.DataFrame:
    """Concentratierisico bij debiteuren en crediteuren."""
    kolommen = ["soort", "aantal_relaties", "aandeel_grootste", "aandeel_top5", "signaal"]
    rijen = []
    for soort, label in (("debiteur", "Debiteuren"), ("crediteur", "Crediteuren")):
        analyse = build_relatie_analyse(af, soort, top=10_000)
        if analyse.empty:
            continue
        grootste = float(analyse["aandeel_pct"].iloc[0])
        top5 = float(analyse["aandeel_pct"].head(5).sum())
        if grootste >= 25:
            signaal = f"Eén relatie is goed voor {grootste:.0f}% van het totaal; beoordeel het afhankelijkheidsrisico."
        elif top5 >= 60:
            signaal = f"De vijf grootste relaties vormen samen {top5:.0f}% van het totaal."
        else:
            signaal = ""
        rijen.append(
            {
                "soort": label,
                "aantal_relaties": len(analyse),
                "aandeel_grootste": grootste,
                "aandeel_top5": top5,
                "signaal": signaal,
            }
        )
    if not rijen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(rijen, columns=kolommen)


# --- Balansposten -----------------------------------------------------------


def build_balanspost_signalen(af: Auditfile) -> pd.DataFrame:
    """Balansposten met een saldo dat aan de verkeerde kant staat."""
    kolommen = ["categorie", "rekening", "omschrijving", "methode", "eindsaldo", "signaal"]
    saldo = af.saldo[af.saldo["accTp"].astype(str).str.upper().eq("B")].copy()
    if saldo.empty:
        return pd.DataFrame(columns=kolommen)

    # Per categorie: RGS-prefix, zoekterm, en het verwachte teken van het
    # eindsaldo (1 = debet, -1 = credit).
    categorieen: tuple[tuple[str, str | None, str | None, int], ...] = (
        ("Debiteuren", "BVor", r"debiteur|vordering.*handel|accounts receivable", 1),
        ("Crediteuren", "BSch", r"crediteur|leverancier|accounts payable", -1),
        ("Liquide middelen", "BLim", r"\bbank\b|\bkas\b|giro", 1),
        ("Voorraden", "BVrd", r"voorraad|inventory", 1),
    )

    rijen = []
    for naam, rgs_prefix, patroon, verwacht_teken in categorieen:
        masker, methode = _selecteer(saldo, rgs_prefix, patroon, rekeningtype="B")
        selectie = saldo[masker]
        for _, rij in selectie.iterrows():
            eindsaldo = float(rij["eindsaldo"])
            onverwacht = (verwacht_teken > 0 and eindsaldo < -0.005) or (
                verwacht_teken < 0 and eindsaldo > 0.005
            )
            if not onverwacht:
                continue
            zijde = "debet" if eindsaldo > 0 else "credit"
            verwacht = "debet" if verwacht_teken > 0 else "credit"
            rijen.append(
                {
                    "categorie": naam,
                    "rekening": str(rij["rekening"]),
                    "omschrijving": str(rij["accDesc"]),
                    "methode": methode,
                    "eindsaldo": eindsaldo,
                    "signaal": f"Saldo staat {zijde} terwijl {verwacht} wordt verwacht.",
                }
            )

    if not rijen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(rijen, columns=kolommen).sort_values(["categorie", "rekening"]).reset_index(drop=True)


# --- Fiscale aandachtspunten ------------------------------------------------

# Toelichting bij boetes. De formulering is bewust genuanceerd: niet elke boete
# is van aftrek uitgesloten. Zie docs/btw-bronnen.md voor de vindplaatsen.
BOETE_TOELICHTING = (
    "Geldboeten (strafrechtelijk, bestuurlijk, tuchtrechtelijk, van een instelling "
    "van de EU en daarmee vergelijkbare buitenlandse boeten) en bestuursrechtelijke "
    "dwangsommen zijn van aftrek uitgesloten op grond van art. 3.14 lid 1 onderdelen "
    "c en i Wet IB 2001, dat via art. 8 lid 1 Wet Vpb 1969 ook voor de "
    "vennootschapsbelasting geldt. Contractuele boetes tussen private partijen en "
    "civielrechtelijke dwangsommen (art. 611a Rv) vallen daar niet onder, dus "
    "beoordeel per boeking waar de boete vandaan komt."
)

FISCALE_SIGNALEN: tuple[tuple[str, str, str], ...] = (
    (
        "Boetes en dwangsommen",
        r"boete|dwangsom|sanctie|bekeuring|naheffing",
        BOETE_TOELICHTING,
    ),
    (
        "Juridische kosten",
        r"juridisch|advocaat|notaris|rechtbank|geschil|proceskosten|deurwaarder",
        "Juridische kosten kunnen wijzen op een lopend geschil. Beoordeel of een "
        "voorziening of een toelichting op niet in de balans opgenomen verplichtingen "
        "nodig is.",
    ),
    (
        "Representatie en horeca",
        r"representat|relatiegeschenk|horeca|restaurant|kantine|personeelsfeest|personeelsuitje",
        "Op deze posten kan de btw-aftrek beperkt of uitgesloten zijn (Besluit "
        "uitsluiting aftrek omzetbelasting 1968) en kan voor de loonheffing een "
        "eindheffing of werkkostenregeling spelen.",
    ),
    (
        "Rekening-courant met aandeelhouder of directie",
        r"rekening.courant|r/c|\brc\b.*(?:dga|directie|aandeelhouder)|(?:dga|directie|aandeelhouder).*\brc\b|lening.*(?:dga|directeur|aandeelhouder)",
        "Beoordeel de zakelijkheid van rente en aflossing, en of de schuld boven de "
        "drempel van de Wet excessief lenen bij eigen vennootschap uitkomt.",
    ),
    (
        "Auto en privegebruik",
        r"auto|bijtelling|privegebruik|prive gebruik|brandstof|leaseauto",
        "Beoordeel of de bijtelling voor de loonheffing en de btw-correctie voor "
        "privegebruik zijn verwerkt.",
    ),
    (
        "Giften en sponsoring",
        r"gift|donatie|sponsor|schenking",
        "Beoordeel of dit een zakelijke uitgave is of een aftrekbeperkte gift.",
    ),
)


def build_fiscale_signalen(af: Auditfile) -> pd.DataFrame:
    """Posten die om een fiscale beoordeling vragen."""
    kolommen = ["onderwerp", "rekening", "omschrijving", "aantal_regels", "bedrag", "toelichting"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    rijen = []
    for onderwerp, patroon, toelichting in FISCALE_SIGNALEN:
        selectie = lines[
            lines["accDesc"].astype(str).str.contains(patroon, case=False, na=False, regex=True)
        ]
        if selectie.empty:
            continue
        per_rekening = (
            selectie.groupby(["line_accID", "accDesc"], dropna=False)
            .agg(aantal_regels=("bedrag", "size"), bedrag=("bedrag", "sum"))
            .reset_index()
        )
        for _, rij in per_rekening.iterrows():
            rijen.append(
                {
                    "onderwerp": onderwerp,
                    "rekening": str(rij["line_accID"]),
                    "omschrijving": str(rij["accDesc"]),
                    "aantal_regels": int(rij["aantal_regels"]),
                    "bedrag": float(rij["bedrag"]),
                    "toelichting": toelichting,
                }
            )

    if not rijen:
        return pd.DataFrame(columns=kolommen)
    return (
        pd.DataFrame(rijen, columns=kolommen)
        .sort_values(["onderwerp", "bedrag"], ascending=[True, False])
        .reset_index(drop=True)
    )


# --- Omzet en personeel -----------------------------------------------------


def build_omzet_per_periode(af: Auditfile) -> pd.DataFrame:
    """Omzet per periode, met signalering van perioden zonder omzet."""
    kolommen = ["periode", "maand", "omzet", "signaal"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    # Het rekeningtype uit het auditfile hoort erbij: zonder die grens vindt de
    # zoekterm "omzet" ook "Omzetbelasting", en dat is een balansrekening.
    masker, _ = _selecteer(
        lines, "WOmz", r"omzet|opbrengst|verkoop|provisie|\brevenue\b", rekeningtype="P"
    )
    omzet = lines[masker & lines["periode"].notna()].copy()
    if omzet.empty:
        return pd.DataFrame(columns=kolommen)

    per_periode = omzet.groupby(omzet["periode"].astype(int))["bedrag"].sum()
    # Omzet staat credit; als positief bedrag getoond.
    per_periode = -per_periode

    regulier = boekingsperioden(af)
    perioden = regulier if regulier else sorted(per_periode.index)
    labels = af.period_labels
    rijen = []
    for periode in perioden:
        bedrag = float(per_periode.get(periode, 0.0))
        rijen.append(
            {
                "periode": periode,
                "maand": labels.get(periode, str(periode)),
                "omzet": bedrag,
                "signaal": "Geen omzet in deze periode" if abs(bedrag) < 0.005 else "",
            }
        )
    return pd.DataFrame(rijen, columns=kolommen)


def build_personeelskosten_per_periode(af: Auditfile) -> pd.DataFrame:
    """Loonkosten per periode, met signalering van perioden zonder loonkosten.

    Er wordt bewust geen aantal medewerkers geschat: het gemiddelde loon per
    medewerker staat niet in de auditfile en elke deling daarop levert een getal
    op dat betrouwbaarder oogt dan het is.
    """
    kolommen = ["periode", "maand", "loonkosten", "afwijking_pct", "signaal"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    masker, _ = _selecteer(
        lines, "WPer", r"loon|salaris|wages|payroll|sociale lasten|pensioenpremie", rekeningtype="P"
    )
    loon = lines[masker & lines["periode"].notna()].copy()
    if loon.empty:
        return pd.DataFrame(columns=kolommen)

    per_periode = loon.groupby(loon["periode"].astype(int))["bedrag"].sum()
    regulier = boekingsperioden(af)
    perioden = regulier if regulier else sorted(per_periode.index)
    bedragen = [float(per_periode.get(periode, 0.0)) for periode in perioden]
    gevuld = [bedrag for bedrag in bedragen if abs(bedrag) > 0.005]
    gemiddelde = float(np.mean(gevuld)) if gevuld else 0.0

    labels = af.period_labels
    rijen = []
    for periode, bedrag in zip(perioden, bedragen):
        if abs(gemiddelde) > 0.005:
            afwijking = (bedrag - gemiddelde) / abs(gemiddelde) * 100
        else:
            afwijking = 0.0
        if abs(bedrag) < 0.005:
            signaal = "Geen loonkosten in deze periode"
        elif abs(afwijking) >= 50:
            signaal = "Wijkt sterk af van het gemiddelde"
        else:
            signaal = ""
        rijen.append(
            {
                "periode": periode,
                "maand": labels.get(periode, str(periode)),
                "loonkosten": bedrag,
                "afwijking_pct": afwijking,
                "signaal": signaal,
            }
        )
    return pd.DataFrame(rijen, columns=kolommen)
