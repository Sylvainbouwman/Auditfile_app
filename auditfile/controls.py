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

# Hoofdrubrieken (niveau 2) van het Referentie Grootboekschema. De lijst is
# ontleend aan het overzicht van balans en winst- en verliesrekening op
# boekhoudplaza.nl/cmm/rgs/referentiegrootboekschema_rgs_balans_winst_en_verlies.php.
# Volledigheid telt hier: een rubriek die ontbreekt levert geen foutmelding maar
# een lege rubriek, en daarmee een rekening die stil buiten elke telling valt.
RGS_RUBRIEKEN = {
    # Balans: activa
    "BIva": "Immateriele vaste activa",
    "BMva": "Materiele vaste activa",
    "BVas": "Vastgoedbeleggingen",
    "BFva": "Financiele vaste activa",
    "BVrd": "Voorraden",
    "BPro": "Onderhanden projecten",
    "BVor": "Vorderingen",
    "BEff": "Effecten",
    "BLim": "Liquide middelen",
    # Balans: passiva
    "BEiv": "Eigen vermogen",
    "BVrz": "Voorzieningen",
    "BLas": "Langlopende schulden",
    "BSch": "Kortlopende schulden",
    # Winst- en verliesrekening
    "WOmz": "Netto-omzet",
    "WWiv": "Wijziging voorraden",
    "WOvb": "Overige bedrijfsopbrengsten",
    "WKpr": "Kostprijs van de omzet",
    "WVkf": "Verkoopkosten",
    "WAkf": "Algemene beheerskosten",
    "WPer": "Personeelskosten",
    "WAfs": "Afschrijvingen",
    "WWvi": "Waardeveranderingen vaste activa",
    "WBwv": "Overige waardeveranderingen",
    "WBed": "Bedrijfskosten",
    "WOvt": "Opbrengst vorderingen en effecten",
    "WVhe": "Vrijval herwaarderingsreserve",
    "WWfa": "Waardeveranderingen financiele vaste activa",
    "WFbe": "Financiele baten en lasten",
    "WRed": "Resultaat deelnemingen",
    "WBel": "Belastingen resultaat",
    "WLbe": "Ledenbetalingen",
    "WAad": "Aandeel derden",
    "WNer": "Netto resultaat",
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

            # Benoem de brede selectie zonder de bevindingensleutel (naam)
            # of de bestaande rekeningselectie en berekening te veranderen.
            if rgs_prefix in ("WPer", "WFbe") and "RGScode" in regels:
                if regels["RGScode"].astype(str).str.strip().str.startswith(rgs_prefix).any():
                    scope = (
                        "RGS WPer selecteert alle personeelskosten, niet uitsluitend lonen en salarissen."
                        if rgs_prefix == "WPer" else
                        "RGS WFbe selecteert alle financiële baten en lasten, niet uitsluitend rente."
                    )
                    toelichting = f"{toelichting} {scope}".strip()

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


# Gebruikelijke autorisatiegrenzen voor het splitsingsrisico. Een werkafspraak van
# de tool en geen fiscale waarde of wettelijke grens; een kantoor of klant kan een
# eigen grens hebben die hier niet tussen staat.
SPLITSINGSDREMPELS: tuple[float, ...] = (250.0, 500.0, 1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0)
SPLITSING_BAND_PCT = 10.0
SPLITSING_MIN_BOEKINGEN = 3


def _splitsingsdrempels_tekst() -> str:
    return ", ".join(f"{drempel:,.0f}".replace(",", ".") for drempel in SPLITSINGSDREMPELS)


def _splitsingsrisico(lines: pd.DataFrame) -> pd.DataFrame:
    """Kostenregels die net onder een drempelbedrag liggen, per relatie gegroepeerd.

    Een groep telt pas mee bij minstens ``SPLITSING_MIN_BOEKINGEN`` regels van
    minstens twee verschillende bedragen: een vaste maandhuur van 950 euro is
    geen splitsing. Zonder relatie op de regel wordt per rekening gegroepeerd.
    """
    is_kosten = lines["accTp"].astype(str).str.upper().eq("P") & (lines["bedrag"] > 0)
    kosten = lines[is_kosten]
    if kosten.empty:
        return kosten
    relatie = kosten["line_custSupID"].astype(str).str.strip()
    groep = relatie.where(relatie != "", "rekening " + kosten["line_accID"].astype(str))

    gevonden = []
    for drempel in SPLITSINGSDREMPELS:
        ondergrens = drempel * (1 - SPLITSING_BAND_PCT / 100.0)
        in_band = kosten[(kosten["bedrag"] >= ondergrens) & (kosten["bedrag"] < drempel)]
        for _, deel in in_band.groupby(groep[in_band.index]):
            if len(deel) >= SPLITSING_MIN_BOEKINGEN and deel["bedrag"].round(2).nunique() >= 2:
                gevonden.append(deel)
    if not gevonden:
        return kosten.iloc[0:0]
    return pd.concat(gevonden)


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

    # Veel boekingen net onder een drempelbedrag (splitsingsrisico).
    voeg_toe(
        "Veel boekingen net onder een drempelbedrag",
        _splitsingsrisico(lines),
        f"Per relatie (of per rekening zonder relatie) staan er minstens "
        f"{SPLITSING_MIN_BOEKINGEN} kostenboekingen van verschillend bedrag binnen "
        f"{SPLITSING_BAND_PCT:.0f}% onder een rond bedrag ({_splitsingsdrempels_tekst()}). "
        "Dat kan wijzen op het splitsen van een uitgave onder een interne "
        "autorisatiegrens. Het is geen wettelijke grens en geen oordeel: beoordeel "
        "of de boekingen bij elkaar horen.",
    )

    if not signalen:
        return pd.DataFrame(columns=kolommen)
    return pd.DataFrame(signalen, columns=kolommen)


# --- Relaties: debiteuren en crediteuren ------------------------------------

# Zo worden de debiteuren- en crediteurenrekeningen aangewezen. BVor en BSch
# omvatten alle vorderingen en schulden, dus de specifiekere codes gaan voor.
RELATIEREKENINGEN: dict[str, tuple[str, str]] = {
    "debiteur": ("BVorDeb", r"debiteur|vordering.*handel|accounts receivable"),
    "crediteur": ("BSchCre", r"crediteur|leverancier|accounts payable"),
}

def soort_uit_code(code) -> str | None:
    """Debiteur of crediteur volgens ``custSupTp``, of ``None`` bij onbekend.

    XAF laat de codering aan het boekhoudpakket, dus komen zowel de Engelse
    (C voor customer, S voor supplier) als de Nederlandse letters voor. Zegt de
    code niets, dan geeft deze functie ``None`` terug en beslist de aanroeper met
    zijn eigen terugval; dat is per gebruik iets anders. Deze vertaling staat op
    één plaats zodat de relatie-analyse en de saldoaansluiting een relatie niet
    verschillend kunnen indelen.
    """
    schoon = str(code).strip().upper()
    if schoon in {"C", "D"}:  # customer respectievelijk debiteur
        return "debiteur"
    if schoon in {"S", "K"}:  # supplier respectievelijk crediteur
        return "crediteur"
    return None


RELATIE_COLUMNS = [
    "relatie",
    "naam",
    "soort",
    "methode",
    "aantal_regels",
    "gefactureerd",
    "afgewikkeld",
    "netto_mutatie",
    "aandeel_pct",
]


def build_relatie_analyse(af: Auditfile, soort: str = "debiteur", top: int = 20) -> pd.DataFrame:
    """Wat er in het boekjaar per relatie is gefactureerd en afgewikkeld.

    Dit is geen openstaande-postenlijst en geen omzet. Een auditfile bevat geen
    ouderdom, geen vervaldatum en geen aansluiting op de subadministratie; wat
    er wél in staat is het ``custSupID`` op de boekingsregel. Daarmee is per
    relatie te zien:

    ``gefactureerd``
        de factuurzijde van de mutaties op de debiteuren- respectievelijk
        crediteurenrekening: debet bij een debiteur, credit bij een crediteur.
        Inclusief btw, want dat staat op die rekening. Dit is de maatstaf voor
        concentratie: een grote klant die netjes betaalt zou anders wegvallen.
    ``afgewikkeld``
        de andere zijde: ontvangsten, betalingen en creditnota's.
    ``netto_mutatie``
        het verschil, dus de verandering van het saldo in dit boekjaar. Let op:
        dit is niet het openstaande saldo, want het beginsaldo zit er niet in.

    De rekeningen worden aangewezen op RGS-code met de omschrijving als
    terugval. Levert dat niets op, dan vallen alle balansrekeningen met een
    relatie-id terug in de selectie; de kolom ``methode`` zegt welke van de twee
    is gebruikt, zodat de uitkomst navolgbaar blijft.
    """
    lines = af.lines
    if lines.empty or "line_custSupID" not in lines.columns:
        return pd.DataFrame(columns=RELATIE_COLUMNS)
    if (lines["line_custSupID"] == "").all():
        return pd.DataFrame(columns=RELATIE_COLUMNS)

    rgs_prefix, patroon = RELATIEREKENINGEN.get(soort, (None, None))
    op_rekening, methode = _selecteer(lines, rgs_prefix, patroon, rekeningtype="B")
    if not op_rekening.any():
        op_rekening = lines["accTp"].astype(str).str.upper().eq("B")
        methode = "alle balansrekeningen"
    else:
        methode = f"{methode} ({soort}enrekening)"

    met_relatie = lines[op_rekening & (lines["line_custSupID"] != "")].copy()
    if met_relatie.empty:
        return pd.DataFrame(columns=RELATIE_COLUMNS)

    # Bij een debiteur is de factuur debet, bij een crediteur credit.
    teken = 1 if soort == "debiteur" else -1
    bedrag = met_relatie["bedrag"] * teken
    met_relatie["factuurzijde"] = bedrag.where(bedrag > 0, 0.0)
    met_relatie["afwikkelzijde"] = (-bedrag).where(bedrag < 0, 0.0)

    totalen = (
        met_relatie.groupby("line_custSupID", dropna=False)
        .agg(
            aantal_regels=("bedrag", "size"),
            gefactureerd=("factuurzijde", "sum"),
            afgewikkeld=("afwikkelzijde", "sum"),
        )
        .reset_index()
        .rename(columns={"line_custSupID": "relatie"})
    )
    totalen["netto_mutatie"] = totalen["gefactureerd"] - totalen["afgewikkeld"]

    namen = af.relations.set_index("custSupID")["custSupName"].to_dict() if not af.relations.empty else {}
    soorten = af.relations.set_index("custSupID")["custSupTp"].to_dict() if not af.relations.empty else {}
    totalen["soort"] = totalen["relatie"].map(soorten).fillna("")

    # Een relatie wordt in haar geheel als debiteur of crediteur ingedeeld, niet
    # per boekingsregel: een creditnota aan een klant maakt die klant geen
    # leverancier. De soort uit de relatietabel gaat voor; ontbreekt die, dan
    # geeft de factuurzijde de doorslag.
    def is_gezocht(rij: pd.Series) -> bool:
        volgens_code = soort_uit_code(rij["soort"])
        if volgens_code is not None:
            return volgens_code == soort
        return rij["gefactureerd"] > 0.005

    resultaat = totalen[totalen.apply(is_gezocht, axis=1)].copy()
    if resultaat.empty:
        return pd.DataFrame(columns=RELATIE_COLUMNS)

    resultaat["naam"] = resultaat["relatie"].map(namen).fillna("")
    resultaat["methode"] = methode
    totaal = resultaat["gefactureerd"].sum()
    resultaat["aandeel_pct"] = resultaat["gefactureerd"] / totaal * 100 if totaal else 0.0
    return (
        resultaat.sort_values("gefactureerd", ascending=False)
        .head(top)[RELATIE_COLUMNS]
        .reset_index(drop=True)
    )


def build_relatie_concentratie(af: Auditfile) -> pd.DataFrame:
    """Concentratie van het gefactureerde bedrag over de relaties.

    Gaat over wat er in dit boekjaar is gefactureerd, niet over omzet en niet
    over openstaande posten; zie :func:`build_relatie_analyse`.
    """
    kolommen = ["soort", "aantal_relaties", "aandeel_grootste", "aandeel_top5", "signaal"]
    rijen = []
    for soort, label in (("debiteur", "Debiteuren"), ("crediteur", "Crediteuren")):
        analyse = build_relatie_analyse(af, soort, top=10_000)
        if analyse.empty:
            continue
        grootste = float(analyse["aandeel_pct"].iloc[0])
        top5 = float(analyse["aandeel_pct"].head(5).sum())
        if grootste >= 25:
            signaal = (
                f"Eén relatie is goed voor {grootste:.0f}% van het gefactureerde bedrag; "
                "beoordeel het afhankelijkheidsrisico."
            )
        elif top5 >= 60:
            signaal = f"De vijf grootste relaties vormen samen {top5:.0f}% van het gefactureerde bedrag."
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
    # eindsaldo (1 = debet, -1 = credit). De debiteuren- en de
    # crediteurenrekeningen komen uit `RELATIEREKENINGEN`, zodat één plaats
    # beslist wat een debiteur is. Hier stonden `BVor` en `BSch`, en daaronder
    # vallen ook de omzetbelasting, de rekening-courant met de dga en de
    # vooruitbetaalde kosten: een creditsaldo op zo'n rekening-courant is
    # doodnormaal en werd gemeld als een debiteur die aan de verkeerde kant
    # staat, met "Debiteuren" als categorie erboven. Een bestand dat alleen op
    # niveau 2 codeert (`BVor` zonder subcode) levert daardoor geen signaal
    # meer: dat bestand zegt zelf niet welke vordering een handelsdebiteur is,
    # en de dekking daarvan staat in `capability.py`.
    debiteur_prefix, debiteur_patroon = RELATIEREKENINGEN["debiteur"]
    crediteur_prefix, crediteur_patroon = RELATIEREKENINGEN["crediteur"]
    categorieen: tuple[tuple[str, str | None, str | None, int], ...] = (
        ("Debiteuren", debiteur_prefix, debiteur_patroon, 1),
        ("Crediteuren", crediteur_prefix, crediteur_patroon, -1),
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
    "Geldboeten van de strafrechter; bestuurlijke boeten en daarmee vergelijkbare "
    "buitenlandse boeten; boeten uit bij wet geregeld tuchtrecht; en boeten van een "
    "instelling van de EU. Deze boeten en bestuursrechtelijke dwangsommen zijn van "
    "aftrek uitgesloten op grond van art. 3.14 lid 1 onderdelen c en i Wet IB 2001, "
    "dat via art. 8 lid 1 Wet Vpb 1969 ook voor de vennootschapsbelasting geldt. "
    "Contractuele boetes tussen private partijen en civielrechtelijke dwangsommen "
    "(art. 611a Rv) vallen daar niet onder, dus beoordeel per boeking waar de boete "
    "vandaan komt."
)

# Belastingrente is geen boete en valt dus niet onder art. 3.14 lid 1 onderdeel c
# Wet IB 2001 (en via art. 8 lid 1 Wet Vpb 1969 niet onder de Vpb); een fiscale
# verzuim- of vergrijpboete is wel een bestuurlijke boete (art. 67a, 67c en 67d
# AWR). Dat de rente aftrekbaar is, is geen bron maar een redenering: de wet
# sluit haar niet uit. Die lezing is op 06-10-2026 door Sylvain als uitgangspunt
# gekozen; zie docs/btw-bronnen.md, paragraaf Belastingrente en invorderingsrente.
BELASTINGRENTE_TOELICHTING = (
    "Belastingrente en invorderingsrente zijn geen boete en vallen daarom niet onder "
    "het aftrekverbod van art. 3.14 lid 1 onderdeel c Wet IB 2001 (via art. 8 lid 1 "
    "Wet Vpb 1969 ook niet voor de vennootschapsbelasting). Uitgangspunt: betaalde "
    "rente over een aanslag van de onderneming (btw, loonheffing, vennootschapsbelasting) "
    "is aftrekbaar, omdat de wet haar niet uitsluit; dat is een redenering en geen "
    "uitdrukkelijke bepaling, een officiële bron die het zegt is niet gevonden. Een "
    "verzuim- of vergrijpboete in dezelfde aanslag is wel een bestuurlijke boete en "
    "dus niet aftrekbaar. Beoordeel ontvangen rente apart en rente over de "
    "inkomstenbelasting van de eigenaar, die privé is."
)

FISCALE_SIGNALEN: tuple[tuple[str, str, str], ...] = (
    (
        "Boetes en dwangsommen",
        r"boete|dwangsom|sanctie|bekeuring|naheffing",
        BOETE_TOELICHTING,
    ),
    (
        "Belastingrente en invorderingsrente",
        r"belastingrente|invorderingsrente|heffingsrente|revisierente",
        BELASTINGRENTE_TOELICHTING,
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
        "Privé-opnamen en onttrekkingen",
        r"priv[eé](?!.?gebruik)|onttrekking",
        "Beoordeel bij een vennootschap of dit een uitdeling is, of een lening aan de "
        "aandeelhouder die onder de Wet excessief lenen kan vallen (zie het signaal "
        "Rekening-courant met aandeelhouder of directie), en bij een eenmanszaak of "
        "vof of de opname goed in het eigen vermogen is verwerkt. De tool leest "
        "alleen de omschrijving van de rekening en weet niet wat de opname is.",
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


# Autokosten en de aanwijzingen dat de bijtelling of het privégebruik is verwerkt.
# "auto" als los woord, want "automatisering" is geen autokost.
AUTOKOSTEN_PATROON = r"\bauto\b|autokosten|auto.?lease|leaseauto|brandstof|personenauto|wagenpark"
BIJTELLING_PATROON = r"bijtelling|priv[eé].?gebruik|priv[eé] ?deel"


def _autokosten_zonder_bijtelling(af: Auditfile) -> list[dict]:
    """Autokosten in het grootboek zonder enige aanwijzing dat de bijtelling is verwerkt.

    De bijtelling is een zaak van de loonheffing en hoeft niet in het grootboek
    te staan; ook een correctie van de btw voor privégebruik kan buiten een
    herkenbare rekening of omschrijving zijn geboekt. De tool kan dus niet
    vaststellen dat de bijtelling ontbreekt, alleen dat er in dit grootboek
    geen rekening en geen boeking is die op bijtelling of privégebruik wijst.
    """
    if af.saldo.empty or af.lines.empty:
        return []
    masker, _ = _selecteer(af.saldo, None, AUTOKOSTEN_PATROON, rekeningtype="P")
    autokosten = af.saldo[masker]
    bedrag = float(autokosten["mutaties_boekjaar"].sum())
    if autokosten.empty or abs(bedrag) < 0.005:
        return []

    lines = af.lines
    tekst = (
        lines["accDesc"].astype(str)
        + " "
        + lines["line_desc"].astype(str)
        + " "
        + lines["tx_desc"].astype(str)
    )
    if tekst.str.contains(BIJTELLING_PATROON, case=False, na=False, regex=True).any():
        return []
    return [
        {
            "onderwerp": "Autokosten zonder zichtbare bijtelling",
            "rekening": ", ".join(str(r) for r in autokosten["rekening"]),
            "omschrijving": "Autokosten",
            "aantal_regels": int(autokosten["aantal_boekingsregels"].sum()),
            "bedrag": bedrag,
            "toelichting": (
                "Er zijn autokosten geboekt, maar geen rekening of boeking noemt "
                "bijtelling of privégebruik. Een bijtelling hoeft niet in dit "
                "grootboek te staan en kan dus elders zijn verwerkt; beoordeel of "
                "de bijtelling en de btw-correctie voor privégebruik zijn toegepast."
            ),
        }
    ]


def build_fiscale_signalen(af: Auditfile) -> pd.DataFrame:
    """Posten die om een fiscale beoordeling vragen."""
    kolommen = ["onderwerp", "rekening", "omschrijving", "aantal_regels", "bedrag", "toelichting"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    rijen = _autokosten_zonder_bijtelling(af)
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


def build_inkopen_per_periode(af: Auditfile) -> pd.DataFrame:
    """Inkopen per periode, met signalering van perioden zonder inkopen.

    Alleen zinvol voor een onderneming die inkoopt: herkent de tool geen
    inkoop- of kostprijsrekening, dan is het resultaat leeg en meldt de tool
    niets. Een dienstverlener zonder inkopen krijgt dus geen signaal voor elke
    maand.
    """
    kolommen = ["periode", "maand", "inkopen", "signaal"]
    lines = af.lines
    if lines.empty:
        return pd.DataFrame(columns=kolommen)

    masker, _ = _selecteer(
        lines, "WKpr", r"inkoop|inkopen|kostprijs|handelsgoederen|grondstoffen", rekeningtype="P"
    )
    inkopen = lines[masker & lines["periode"].notna()].copy()
    if inkopen.empty:
        return pd.DataFrame(columns=kolommen)

    per_periode = inkopen.groupby(inkopen["periode"].astype(int))["bedrag"].sum()
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
                "inkopen": bedrag,
                "signaal": "Geen inkopen in deze periode" if abs(bedrag) < 0.005 else "",
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
