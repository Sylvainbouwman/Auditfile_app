"""Openstaande posten en hun ouderdom, uit de subadministratie van XAF 3.2.

Dit is de analyse die in de samenstelpraktijk als eerste wordt gevraagd: welke
facturen staan op de balansdatum nog open, hoe oud zijn ze en sluit het geheel
aan op de debiteuren- en de crediteurenrekening. Zij is alleen mogelijk op
bewijsniveau 1 of 2 uit ``capability.py``, dus wanneer het bestand een gevulde
subadministratie heeft. Niveau 3 (een eindstand per relatie uit XAF 4.0) geeft
geen facturen en geen datums, en een reconstructie uit boekingsregels (niveau 4)
valt bewust buiten deze module: die vraagt een eigen methode met de gemeten
dekking en een door de gebruiker opgegeven betalingstermijn in beeld.

Van regels naar posten
----------------------
Een openstaande post is een groep subadministratieregels. De regels van de
beginbalans (``obSbLine``) en die van de mutaties (``sbLine``) tellen samen mee,
want de stand van een post is de beginstand plus haar verloop. De sleutel volgt
dezelfde hiërarchie als elders in deze tool, en de gebruikte sleutel staat per
post in de kolom ``sleutelsoort``:

1. het afletterkenmerk ``matchKeyID`` - de enige koppeling zonder aanname;
2. anders de factuurreferentie ``invRef``;
3. anders staat de regel op zichzelf.

De keuze valt per regel en niet per bestand, om dezelfde reden als bij
``_selecteer()``: in een gedeeltelijk gevulde subadministratie zou anders alles
zonder afletterkenmerk buiten de groepering vallen. Draagt de ene regel van een
post wel een afletterkenmerk en de andere alleen een factuurreferentie, dan
vallen ze uiteen in twee posten. Dat is zichtbaar in ``sleutelsoort`` en het is
te verkiezen boven het samenvoegen van regels waarvan het bestand niet zegt dat
ze bij elkaar horen.

Ouderdom
--------
Vanaf de vervaldatum ``invDueDt`` wanneer die er is, anders vanaf de
factuurdatum ``invDt``. Welke van de twee het is geworden, staat in de kolom
``basis``; de ouderdomstabel splitst daarop, zodat dagen te laat en dagen sinds
factuurdatum nooit bij elkaar worden opgeteld. Ontbreken beide datums, dan is de
ouderdom niet te bepalen en valt de post in de klasse ``datum onbekend``. Hij
verdwijnt daarmee niet: een post zonder datum stilzwijgend in de laagste klasse
zetten zou de ouderdomsopbouw gunstiger laten lijken dan het bestand toelaat.

Peildatum
---------
De einddatum van het boekjaar, want de vraag is hoe de post er op de balansdatum
bij stond. De datum van vandaag zou een auditfile over een afgesloten jaar elke
dag een ander antwoord geven. ``bepaal_peildatum()`` geeft de herkomst terug,
zodat zichtbaar blijft waarop de ouderdom rust.

Tekens
------
``bedrag`` komt getekend uit de parser: debet positief, credit negatief. Een
openstaande debiteurenpost is daardoor positief en een crediteurenpost negatief,
gelijk aan het grootboeksaldo. Nergens in deze module wordt een teken omgekeerd,
en de aansluiting op het grootboek is daarmee een rechtstreekse vergelijking.
"""
from __future__ import annotations

import pandas as pd

from .controls import RELATIEREKENINGEN, _selecteer, soort_uit_code
from .model import Auditfile
from .notatie import euro

# Kleiner dan een halve cent is afrondingsruis en geen openstaand bedrag.
TOLERANTIE = 0.005

SLEUTEL_AFLETTER = "afletterkenmerk"
SLEUTEL_FACTUUR = "factuurreferentie"
SLEUTEL_LOS = "losse regel"

BASIS_VERVALDATUM = "vervaldatum"
BASIS_FACTUURDATUM = "factuurdatum"
BASIS_ONBEKEND = "onbekend"

NIET_VERVALLEN = "nog niet vervallen"
KLASSE_OUDER_DAN_90 = "meer dan 90 dagen"
KLASSE_ONBEKEND = "datum onbekend"

# De indeling uit de roadmap, met twee toevoegingen die de tool nodig heeft om
# niets te verzwijgen: een post die op de peildatum nog niet vervallen is, en
# een post waarvan de ouderdom niet te bepalen valt.
OUDERDOMSKLASSEN: tuple[str, ...] = (
    NIET_VERVALLEN,
    "0-30 dagen",
    "31-60 dagen",
    "61-90 dagen",
    KLASSE_OUDER_DAN_90,
    KLASSE_ONBEKEND,
)

# Kolomnaam per klasse in de ouderdomstabel. Het voorvoegsel "bedrag_" is niet
# cosmetisch: de presentatielaag leidt de opmaak af uit de kolomnaam, en zonder
# dat voorvoegsel zou een bedrag als een gewoon getal worden getoond.
KLASSE_KOLOMMEN: dict[str, str] = {
    NIET_VERVALLEN: "bedrag_niet_vervallen",
    "0-30 dagen": "bedrag_0_30",
    "31-60 dagen": "bedrag_31_60",
    "61-90 dagen": "bedrag_61_90",
    KLASSE_OUDER_DAN_90: "bedrag_ouder_dan_90",
    KLASSE_ONBEKEND: "bedrag_datum_onbekend",
}

POST_COLUMNS = [
    "soort",
    "soort_bron",
    "relatie",
    "naam",
    "rekening",
    "koppeling",
    "sleutel",
    "sleutelsoort",
    "factuurdatum",
    "vervaldatum",
    "basis",
    "dagen",
    "ouderdomsklasse",
    "bedrag_debet",
    "bedrag_credit",
    "openstaand",
    "aantal_regels",
    "signaal",
]

OUDERDOM_COLUMNS = (
    ["soort", "basis", "aantal_posten"]
    + [KLASSE_KOLOMMEN[klasse] for klasse in OUDERDOMSKLASSEN]
    + ["openstaand"]
)

AANSLUITING_COLUMNS = [
    "soort",
    "methode",
    "rekeningen",
    "aantal_posten",
    "grootboek_eindsaldo",
    "openstaand",
    "verschil",
    "signaal",
    "conclusie",
]


def heeft_openstaande_posten(af: Auditfile) -> bool:
    """Laat dit bestand een openstaande-postenanalyse toe?

    De vraag is niet welke XAF-versie het is maar of er een subadministratie is
    ingelezen. Dat is precies wat ``capability.py`` als niveau 1 of 2 aanwijst,
    en het houdt de versiekennis waar zij hoort: in de parser.
    """
    return not af.subadministratie.empty


def bepaal_peildatum(af: Auditfile) -> tuple[pd.Timestamp | None, str]:
    """De datum waarop de ouderdom wordt gemeten, met de herkomst ervan.

    De einddatum van het boekjaar gaat voor. Ontbreekt die, dan is de laatste
    datum in de subadministratie de enige aanwijzing die het bestand zelf geeft;
    dat is zwakker, want de peildatum hangt dan van de gegevens af. Daarom komt
    de herkomst mee terug en staat zij in de app bij de uitkomst.
    """
    einddatum = pd.to_datetime(af.header.get("endDate", ""), errors="coerce")
    if pd.notna(einddatum):
        return einddatum, "einddatum van het boekjaar"

    sub = af.subadministratie
    if not sub.empty:
        datums = pd.concat([sub["invDueDt"], sub["invDt"]]).dropna()
        if not datums.empty:
            return pd.Timestamp(datums.max()), "laatste datum in de subadministratie"
    return None, "niet vast te stellen"


def _klasse(dagen: float | None) -> str:
    if dagen is None or pd.isna(dagen):
        return KLASSE_ONBEKEND
    getal = float(dagen)
    if getal < 0:
        return NIET_VERVALLEN
    if getal <= 30:
        return "0-30 dagen"
    if getal <= 60:
        return "31-60 dagen"
    if getal <= 90:
        return "61-90 dagen"
    return KLASSE_OUDER_DAN_90


def _soortkaart_rekeningen(af: Auditfile) -> dict[str, str]:
    """Grootboekrekening -> debiteur of crediteur, volgens dezelfde selectie.

    De relatierekeningen worden op RGS-code gekozen met de omschrijving als
    terugval, precies zoals de rest van de tool dat doet. Zou deze module een
    eigen indeling maken, dan kon dezelfde rekening hier anders uitvallen dan op
    de relatiepagina.
    """
    kaart: dict[str, str] = {}
    if af.saldo.empty or "rekening" not in af.saldo.columns:
        return kaart
    for soort, (rgs_prefix, patroon) in RELATIEREKENINGEN.items():
        masker, _ = _selecteer(af.saldo, rgs_prefix, patroon, rekeningtype="B")
        for rekening in af.saldo.loc[masker, "rekening"].astype(str).str.strip():
            if rekening:
                kaart.setdefault(rekening, soort)
    return kaart


def _soortkaart_relaties(af: Auditfile) -> dict[str, str]:
    kaart: dict[str, str] = {}
    if af.relations.empty or "custSupID" not in af.relations.columns:
        return kaart
    for _, relatie in af.relations.iterrows():
        soort = soort_uit_code(relatie.get("custSupTp", ""))
        identificatie = str(relatie.get("custSupID", "")).strip()
        if soort and identificatie:
            kaart[identificatie] = soort
    return kaart


def _namenkaart(af: Auditfile) -> dict[str, str]:
    if af.relations.empty or "custSupID" not in af.relations.columns:
        return {}
    return {
        str(rij.get("custSupID", "")).strip(): str(rij.get("custSupName", "")).strip()
        for _, rij in af.relations.iterrows()
    }


# Inkoop levert een crediteur op, verkoop een debiteur. Dit is de zwakste van de
# drie methoden: het veld beschrijft de factuur en niet de relatie, dus een
# creditnota van een leverancier blijft er een inkoop mee.
SOORT_UIT_INKOOP_VERKOOP = {"P": "crediteur", "S": "debiteur"}


def _soort_van_post(
    rekening: str,
    relatie: str,
    inkoop_verkoop: str,
    per_rekening: dict[str, str],
    per_relatie: dict[str, str],
) -> tuple[str, str]:
    """Debiteur of crediteur, met de methode waarop dat berust.

    De grootboekrekening gaat voor: die is per post opgelost uit de verwijzing
    en deelt de post in zoals het grootboek hem indeelt. Daarna ``custSupTp``,
    dat de relatie in haar geheel indeelt, en pas als laatste ``invPurSalTp``.
    Lukt geen van drieën, dan blijft de soort leeg; die posten vallen buiten de
    aansluiting per soort en worden daar geteld in plaats van naar een van beide
    kanten te worden geraden.
    """
    volgens_rekening = per_rekening.get(rekening)
    if volgens_rekening:
        return volgens_rekening, "grootboekrekening"
    volgens_relatie = per_relatie.get(relatie)
    if volgens_relatie:
        return volgens_relatie, "custSupTp"
    volgens_factuur = SOORT_UIT_INKOOP_VERKOOP.get(str(inkoop_verkoop).strip().upper())
    if volgens_factuur:
        return volgens_factuur, "invPurSalTp"
    return "", ""


def _sleutels(sub: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Per regel de groeperingssleutel en de soort sleutel."""
    afletter = sub["matchKeyID"].astype(str).str.strip()
    factuur = sub["invRef"].astype(str).str.strip()
    los = (
        sub["bron"].astype(str)
        + ":"
        + sub["sb_index"].astype(str)
        + ":"
        + sub["sb_nr"].astype(str)
    )
    sleutel = afletter.where(afletter != "", factuur.where(factuur != "", los))
    soort = pd.Series(SLEUTEL_LOS, index=sub.index)
    soort = soort.where(factuur == "", SLEUTEL_FACTUUR)
    soort = soort.where(afletter == "", SLEUTEL_AFLETTER)
    return sleutel, soort


def _rekening_van_groep(groep: pd.DataFrame) -> tuple[str, str]:
    """De rekening van een post, of geen rekening met de reden erbij.

    Een post die over twee grootboekrekeningen verspreid staat, is niet aan een
    van beide toe te wijzen. Er dan een kiezen zou een post op de verkeerde
    rekening aansluiten, en dat is erger dan een post die niet aansluit.
    """
    rekeningen = sorted({r for r in groep["rekening"].astype(str).str.strip() if r})
    if len(rekeningen) == 1:
        methoden = sorted({k for k in groep["koppeling"].astype(str).str.strip() if k})
        return rekeningen[0], " en ".join(methoden)
    if len(rekeningen) > 1:
        return "", "meerdere rekeningen"
    return "", "niet gekoppeld"


def build_openstaande_posten(
    af: Auditfile, peil: pd.Timestamp | None = None, alleen_open: bool = True
) -> pd.DataFrame:
    """De openstaande posten van dit bestand, met hun ouderdom.

    Met ``alleen_open`` vallen de afgeletterde posten weg: die zijn in het
    boekjaar volledig afgewikkeld en horen niet in een openstaande-postenlijst.
    Ze zijn met ``alleen_open=False`` op te vragen, wat de controle mogelijk
    maakt dat het totaal van alle posten aansluit op de subadministratie.
    """
    sub = af.subadministratie
    if sub.empty:
        return pd.DataFrame(columns=POST_COLUMNS)

    if peil is None:
        peil, _ = bepaal_peildatum(af)

    werk = sub.copy()
    werk["sleutel"], werk["sleutelsoort"] = _sleutels(werk)
    werk["relatie"] = werk["custSupID"].astype(str).str.strip()

    per_rekening = _soortkaart_rekeningen(af)
    per_relatie = _soortkaart_relaties(af)
    namen = _namenkaart(af)

    rijen = []
    for (relatie, sleutel), groep in werk.groupby(["relatie", "sleutel"], sort=False):
        rekening, koppeling = _rekening_van_groep(groep)
        inkoop_verkoop = next(
            (w for w in groep["invPurSalTp"].astype(str).str.strip() if w), ""
        )
        soort, soort_bron = _soort_van_post(
            rekening, relatie, inkoop_verkoop, per_rekening, per_relatie
        )

        bedragen = pd.to_numeric(groep["bedrag"], errors="coerce").fillna(0.0)
        openstaand = float(bedragen.sum())
        factuurdatum = groep["invDt"].min()
        vervaldatum = groep["invDueDt"].min()

        if pd.notna(vervaldatum):
            basis, vanaf = BASIS_VERVALDATUM, vervaldatum
        elif pd.notna(factuurdatum):
            basis, vanaf = BASIS_FACTUURDATUM, factuurdatum
        else:
            basis, vanaf = BASIS_ONBEKEND, None

        dagen = (
            float((peil - pd.Timestamp(vanaf)).days)
            if vanaf is not None and peil is not None
            else float("nan")
        )
        klasse = _klasse(dagen)

        rijen.append(
            {
                "soort": soort,
                "soort_bron": soort_bron,
                "relatie": relatie,
                "naam": namen.get(relatie, ""),
                "rekening": rekening,
                "koppeling": koppeling,
                "sleutel": sleutel,
                "sleutelsoort": str(groep["sleutelsoort"].iloc[0]),
                "factuurdatum": factuurdatum,
                "vervaldatum": vervaldatum,
                "basis": basis,
                "dagen": dagen,
                "ouderdomsklasse": klasse,
                "bedrag_debet": float(bedragen[bedragen > 0].sum()),
                "bedrag_credit": float(bedragen[bedragen < 0].sum()),
                "openstaand": openstaand,
                "aantal_regels": len(groep),
                "signaal": _postsignaal(soort, openstaand, rekening, basis, klasse),
            }
        )

    posten = pd.DataFrame(rijen, columns=POST_COLUMNS)
    if posten.empty:
        return posten
    if alleen_open:
        posten = posten[posten["openstaand"].abs() > TOLERANTIE]
    volgorde = posten["openstaand"].abs().sort_values(ascending=False, na_position="last")
    return posten.reindex(volgorde.index).reset_index(drop=True)


def _postsignaal(soort: str, openstaand: float, rekening: str, basis: str, klasse: str) -> str:
    signalen = []
    if abs(openstaand) > TOLERANTIE:
        if soort == "debiteur" and openstaand < 0:
            signalen.append("Debiteur met een creditstand; vooruitbetaling of creditnota?")
        elif soort == "crediteur" and openstaand > 0:
            signalen.append("Crediteur met een debetstand; vooruitbetaling of dubbele betaling?")
    if klasse == KLASSE_OUDER_DAN_90:
        signalen.append(
            "Ouder dan 90 dagen"
            + (" na de vervaldatum." if basis == BASIS_VERVALDATUM else " na de factuurdatum.")
        )
    if klasse == KLASSE_ONBEKEND:
        signalen.append("Geen factuur- of vervaldatum; de ouderdom is niet te bepalen.")
    if not rekening:
        signalen.append("Niet aan een grootboekrekening gekoppeld.")
    return " ".join(signalen)


def build_ouderdom(af: Auditfile, peil: pd.Timestamp | None = None) -> pd.DataFrame:
    """De ouderdomsopbouw per soort, gesplitst naar de gebruikte basis.

    De splitsing op ``basis`` is geen detail. Een post die 45 dagen over zijn
    vervaldatum is, is iets anders dan een post van 45 dagen oud met een
    betalingstermijn die het bestand niet noemt. Die twee in één kolom optellen
    zou een getal opleveren dat niets betekent.

    De bedragen blijven getekend, dus een crediteurenregel staat negatief. Dat
    houdt de optelling gelijk aan het grootboeksaldo en maakt de aansluiting een
    rechtstreekse vergelijking.
    """
    posten = build_openstaande_posten(af, peil)
    if posten.empty:
        return pd.DataFrame(columns=OUDERDOM_COLUMNS)

    rijen = []
    for (soort, basis), groep in posten.groupby(["soort", "basis"], sort=False):
        rij = {
            "soort": soort or "niet ingedeeld",
            "basis": basis,
            "aantal_posten": len(groep),
            "openstaand": float(groep["openstaand"].sum()),
        }
        for klasse, kolom in KLASSE_KOLOMMEN.items():
            rij[kolom] = float(groep.loc[groep["ouderdomsklasse"] == klasse, "openstaand"].sum())
        rijen.append(rij)

    ouderdom = pd.DataFrame(rijen, columns=OUDERDOM_COLUMNS)
    return ouderdom.sort_values(["soort", "basis"]).reset_index(drop=True)


def build_openstaand_aansluiting(
    af: Auditfile, peil: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Telt de openstaande-postenlijst op tot het saldo van de relatierekening?

    Dezelfde controle als bij de relatiesaldi van XAF 4.0, nu op de posten uit
    de subadministratie. Een verschil is een signaal en geen fout: op een
    relatierekening staan vaker boekingen die niet in de subadministratie zijn
    opgenomen, zoals een verzamelboeking of de afboeking van een oninbare
    vordering.

    Posten die niet als debiteur of crediteur zijn in te delen, krijgen een
    eigen regel. Zij bij een van beide soorten optellen zou de aansluiting
    kloppend maken op een indeling die het bestand niet geeft.
    """
    if not heeft_openstaande_posten(af):
        return pd.DataFrame(columns=AANSLUITING_COLUMNS)

    posten = build_openstaande_posten(af, peil)
    rijen = []
    for soort, (rgs_prefix, patroon) in RELATIEREKENINGEN.items():
        if af.saldo.empty:
            masker = pd.Series(dtype=bool)
            methode = "geen grootboeksaldi"
        else:
            masker, methode = _selecteer(af.saldo, rgs_prefix, patroon, rekeningtype="B")
        rekeningen = int(masker.sum()) if len(masker) else 0
        eigen = posten[posten["soort"] == soort] if not posten.empty else posten

        if rekeningen:
            grootboek = float(af.saldo.loc[masker, "eindsaldo"].sum())
        else:
            grootboek = float("nan")
            methode = f"geen {soort}enrekening herkend"

        openstaand = float(eigen["openstaand"].sum()) if not eigen.empty else 0.0
        verschil = grootboek - openstaand
        rijen.append(
            {
                "soort": soort,
                "methode": methode,
                "rekeningen": rekeningen,
                "aantal_posten": len(eigen),
                "grootboek_eindsaldo": grootboek,
                "openstaand": openstaand,
                "verschil": verschil,
                "signaal": _aansluitsignaal(verschil),
                "conclusie": _aansluitconclusie(soort, rekeningen, len(eigen), verschil),
            }
        )

    zonder_soort = posten[posten["soort"] == ""] if not posten.empty else posten
    if not zonder_soort.empty:
        rijen.append(
            {
                "soort": "niet ingedeeld",
                "methode": "geen indeling mogelijk",
                "rekeningen": 0,
                "aantal_posten": len(zonder_soort),
                "grootboek_eindsaldo": float("nan"),
                "openstaand": float(zonder_soort["openstaand"].sum()),
                "verschil": float("nan"),
                "signaal": "niet mogelijk",
                "conclusie": (
                    f"{len(zonder_soort)} post(en) zijn niet als debiteur of crediteur in te "
                    "delen: de verwijzing naar de grootboekrekening lost niet op en er is geen "
                    "custSupTp of invPurSalTp. Zij tellen daarom in geen van beide "
                    "aansluitingen mee."
                ),
            }
        )
    return pd.DataFrame(rijen, columns=AANSLUITING_COLUMNS)


def _aansluitsignaal(verschil) -> str:
    if pd.isna(verschil):
        return "niet mogelijk"
    return "" if abs(float(verschil)) <= TOLERANTIE else "verschil"


def _aansluitconclusie(soort: str, rekeningen: int, posten: int, verschil) -> str:
    if not rekeningen:
        return (
            f"Geen {soort}enrekening herkend in het rekeningschema, dus er is niets om de "
            "openstaande posten tegenover te zetten."
        )
    if not posten:
        return (
            f"Geen openstaande post is als {soort} in te delen, terwijl er wel een "
            f"{soort}enrekening is. Beoordeel of de subadministratie deze kant van de "
            "administratie wel bevat."
        )
    if pd.isna(verschil):
        return "Het eindsaldo van de rekening ontbreekt, dus de aansluiting is niet te maken."
    if abs(float(verschil)) <= TOLERANTIE:
        meervoud = "post" if posten == 1 else "posten"
        return (
            f"De {posten} openstaande {meervoud} tellen op tot het eindsaldo van de "
            f"{soort}enrekening."
        )
    return (
        f"Het eindsaldo van de {soort}enrekening en de som van de openstaande posten lopen "
        f"{euro(abs(float(verschil)))} uiteen. Beoordeel welke boekingen op de rekening staan "
        "die niet in de subadministratie zijn opgenomen."
    )
